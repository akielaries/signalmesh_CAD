import json
import os
import re

import sch
from dcommon import C, FB, R, decap, header, button, led_to_gnd, tp, MIPI10, OSC3225, C0201, C1210, C1206

LIB = ('FPGA_Xilinx_Artix7', 'XC7A100T-FGG484')
LIBID = 'FPGA_Xilinx_Artix7:XC7A100T-FGG484'


def _pins():
    node = sch.flat(*LIB)
    out = []
    for u in sch.nunits(node):
        ps, _ = sch.geom(node, u)
        for p in ps:
            p['unit'] = u
            out.append(p)
    return out


PINS = _pins()
BYNAME = {p['name']: p['num'] for p in PINS}


def io(bank, pat):
    r = [n for n in BYNAME if n.startswith('IO_') and n.endswith('_%d' % bank) and re.search(pat, n)]
    if len(r) != 1:
        raise ValueError('io %s %s -> %s' % (bank, pat, r))
    return BYNAME[r[0]]


def pair(bank, n):
    return io(bank, r'^IO_L%dP_' % n), io(bank, r'^IO_L%dN_' % n)


def bank_balls(bank):
    l = [n for n in BYNAME if n.startswith('IO_') and n.endswith('_%d' % bank)]

    def key(n):
        m = re.match(r'IO_L?(\d+)([PN]?)', n)
        return (int(m.group(1)), m.group(2))
    return [BYNAME[n] for n in sorted(l, key=key)]


def plan():
    m = {}

    # fmc layout swap (fmcswap.py): within d16-d31, a0-a18 and the controls, nets follow the
    # crossing-free pairing with the stm32 pins. d0-d15, fmc_clk and config pins are fixed
    fsw = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fmc_swap.json')
    fswap = json.load(open(fsw)) if os.path.exists(fsw) else {}
    # vita la pair swap (laswap.py), same idea: whole pairs within each bank, cc pairs and clocks fixed
    lsw = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'la_swap.json')
    if os.path.exists(lsw):
        fswap.update(json.load(open(lsw)))

    def put(ball, net):
        net = fswap.get(net, net)
        if ball in m:
            raise ValueError('ball %s used twice (%s, %s)' % (ball, m[ball], net))
        m[ball] = net

    # bank 14: fmc data on selectmap d00-d31, controls
    for i in range(32):
        put(io(14, r'_D%02d(_|$)' % i), 'FMC_D%d' % i)
    put(io(14, 'CSI_B'), 'FPGA_CSI_B')
    put(io(14, 'RDWR_B'), 'FPGA_RDWR_B')
    put(io(14, 'PUDC_B'), 'FPGA_PUDC_B')
    put(io(14, r'^IO_L12P_'), 'FMC_CLK')
    put(io(14, r'^IO_0_'), 'FMC_NOE')
    put(io(14, r'^IO_25_'), 'FMC_NWE')
    put(io(14, 'EMCCLK'), 'FMC_NE1')
    put(io(14, 'FCS_B'), 'FMC_NWAIT')
    put(io(14, 'DOUT_CSO_B'), 'FPGA_IRQ0')
    put(io(14, r'^IO_L9P_'), 'FMC_NBL0')
    put(io(14, r'^IO_L21P_'), 'FMC_NBL1')
    put(io(14, r'^IO_L11N_'), 'FMC_NBL2')
    put(io(14, r'^IO_L11P_'), 'FMC_NBL3')
    put(io(14, r'^IO_L12N_'), 'FPGA_RST_N')
    put(io(14, r'^IO_L13P_'), 'MCU_UART_TX')
    put(io(14, r'^IO_L13N_'), 'MCU_UART_RX')
    put(io(14, r'^IO_L14N_'), 'FPGA_IRQ1')
    put(io(14, r'^IO_L14P_'), 'FPGA_IRQ2')

    # bank 15: clocks, fmc address, irqs, debug, leds, backplane tdm
    put(io(15, r'^IO_L12P_'), 'SYSCLK_100M')
    put(io(15, r'^IO_L13P_'), 'AUD_CLK_48K')
    put(io(15, r'^IO_L11P_'), 'AUD_CLK_44K')
    sigs = ['FMC_A%d' % i for i in range(19)] + ['FPGA_IRQ3', 'FPGA_IRQ4', 'FPGA_IRQ5',
                                                 'SC_SWDIO', 'SC_SWCLK', 'SC_SWO', 'SC_NRST',
                                                 'SC_UART_TX', 'SC_UART_RX',
                                                 'FPGA_LED0', 'FPGA_LED1', 'FPGA_LED2', 'FPGA_LED3',
                                                 'FPGA_BTN0', 'FPGA_BTN1',
                                                 'BP_TDM_MCLK', 'BP_TDM_BCLK', 'BP_TDM_FS', 'BP_TDM_DOUT',
                                                 'BP_TDM_DIN']
    free = [b for b in bank_balls(15) if b not in m]
    for b, n in zip(free, sigs):
        put(b, n)

    # bank 13: pmods, audio dac, sfp sideband
    sigs = (['PMODA_IO%d' % i for i in range(1, 9)] + ['PMODB_IO%d' % i for i in range(1, 9)] +
            ['AUD_DAC_MCLK', 'AUD_DAC_SCLK', 'AUD_DAC_LRCK', 'AUD_DAC_SDIN'])
    for k in (0, 1):
        sigs += ['SFP%d_%s' % (k, x) for x in ('MOD_ABS', 'LOS', 'TX_FAULT', 'TX_DIS', 'SCL', 'SDA')]
    for b, n in zip(bank_balls(13), sigs):
        put(b, n)

    # bank 34: ddr3l x16
    ddr = {
        # t0 data byte 0, t1 data byte 1, t2 and t3 addr/cmd (ck in t3 so io_25 may carry odt)
        1: ('DDR_DQ0', 'DDR_DQ1'), 2: ('DDR_DQ2', 'DDR_DQ3'), 3: ('DDR_DQS0_P', 'DDR_DQS0_N'),
        4: ('DDR_DQ4', 'DDR_DQ5'), 5: ('DDR_DQ6', 'DDR_DQ7'), 6: ('DDR_DM0', None),
        7: ('DDR_DQ8', 'DDR_DQ9'), 8: ('DDR_DQ10', 'DDR_DQ11'), 9: ('DDR_DQS1_P', 'DDR_DQS1_N'),
        10: ('DDR_DQ12', 'DDR_DQ13'), 11: ('DDR_DQ14', 'DDR_DQ15'), 12: ('DDR_DM1', None),
        13: ('DDR_A10', 'DDR_A11'), 14: ('DDR_A12', 'DDR_A13'), 15: ('DDR_A14', 'DDR_BA0'),
        16: ('DDR_BA1', 'DDR_BA2'), 17: ('DDR_RAS_N', 'DDR_CAS_N'), 18: ('DDR_WE_N', 'DDR_CKE'),
        19: ('DDR_A0', 'DDR_A1'), 20: ('DDR_A2', 'DDR_A3'), 21: ('DDR_CK_P', 'DDR_CK_N'),
        22: ('DDR_A4', 'DDR_A5'), 23: ('DDR_A6', 'DDR_A7'), 24: ('DDR_A8', 'DDR_A9'),
    }
    # layout pin swap (swap.py): whole bytes, dq bits within a byte and addr/cmd among the addr/cmd
    # balls are re-paired so the bus to the dram runs without crossings. the map is relative to the
    # table above; dqs, ck, dm, odt and reset keep their pins, so the mig pin rules still hold
    sw = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ddr_swap.json')
    if os.path.exists(sw):
        swap = json.load(open(sw))
        ddr = {n: tuple(swap.get(x, x) if x else x for x in v) for n, v in ddr.items()}
    for n, (pn, nn) in ddr.items():
        bp, bn = pair(34, n)
        if pn:
            put(bp, pn)
        if nn:
            put(bn, nn)
    # odt is length-matched to ck, reset is not: odt takes the single pin nearer the dram
    put(io(34, r'^IO_0_'), 'DDR_ODT')
    put(io(34, r'^IO_25_'), 'DDR_RESET_N')

    # banks 35 and 16: vita la pairs at vadj
    for bank, clk, cc, las in ((35, 'CLK0_M2C', ('LA00_CC', 'LA01_CC'), range(2, 17)),
                               (16, 'CLK1_M2C', ('LA17_CC', 'LA18_CC'), range(19, 34))):
        bp, bn = pair(bank, 12)
        put(bp, 'MEZZ_%s_P' % clk)
        put(bn, 'MEZZ_%s_N' % clk)
        for n, name in zip((13, 14), cc):
            bp, bn = pair(bank, n)
            put(bp, 'MEZZ_%s_P' % name)
            put(bn, 'MEZZ_%s_N' % name)
        slots = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 15, 16, 17, 18]
        for n, la in zip(slots, las):
            bp, bn = pair(bank, n)
            put(bp, 'MEZZ_LA%02d_P' % la)
            put(bn, 'MEZZ_LA%02d_N' % la)

    # gtp quad 216
    gtp = {'MGTPTXP0_216': 'GTP0_TX_P', 'MGTPTXN0_216': 'GTP0_TX_N', 'MGTPRXP0_216': 'GTP0_RX_P',
           'MGTPRXN0_216': 'GTP0_RX_N', 'MGTPTXP1_216': 'GTP1_TX_P', 'MGTPTXN1_216': 'GTP1_TX_N',
           'MGTPRXP1_216': 'GTP1_RX_P', 'MGTPRXN1_216': 'GTP1_RX_N',
           'MGTPTXP2_216': 'GTP2_TX_P', 'MGTPTXN2_216': 'GTP2_TX_N',
           'MGTPRXP2_216': 'MEZZ_DP0_M2C_P', 'MGTPRXN2_216': 'MEZZ_DP0_M2C_N',
           'MGTPTXP3_216': 'GTP3_TX_P', 'MGTPTXN3_216': 'GTP3_TX_N',
           'MGTPRXP3_216': 'MEZZ_DP1_M2C_P', 'MGTPRXN3_216': 'MEZZ_DP1_M2C_N',
           'MGTREFCLK0P_216': 'GTP_REFCLK0_P', 'MGTREFCLK0N_216': 'GTP_REFCLK0_N',
           'MGTREFCLK1P_216': 'GTP_REFCLK1_P', 'MGTREFCLK1N_216': 'GTP_REFCLK1_N',
           'MGTRREF_216': 'GTP_RREF'}
    for nm, net in gtp.items():
        put(BYNAME[nm], net)

    # flexible-net ball remap (flexmove.py): a low-speed net may move to any free 3.3 V io ball, chosen so
    # it can escape the ball field toward where it goes
    rsw = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ball_remap.json')
    if os.path.exists(rsw):
        for net, ball in json.load(open(rsw)).items():
            for b0 in [b0 for b0, nn in m.items() if nn == net]:
                del m[b0]
            if ball in m:
                raise ValueError('remap: ball %s already carries %s' % (ball, m[ball]))
            m[ball] = net

    # config bank 0 and power
    cfg = {'CCLK_0': 'FPGA_CCLK', 'PROGRAM_B_0': 'FPGA_PROGRAM_B', 'INIT_B_0': 'FPGA_INIT_B',
           'DONE_0': 'FPGA_DONE', 'M0_0': 'FPGA_M0', 'M1_0': 'FPGA_M1', 'M2_0': 'FPGA_M2', 'CFGBVS_0': '+3V3',
           'TCK_0': 'FPGA_TCK', 'TMS_0': 'FPGA_TMS', 'TDI_0': 'FPGA_TDI', 'TDO_0': 'FPGA_TDO',
           'VREFP_0': 'GNDADC', 'VREFN_0': 'GNDADC', 'VP_0': 'GNDADC', 'VN_0': 'GNDADC',
           'DXP_0': 'GND', 'DXN_0': 'GND', 'VCCBATT_0': 'GND', 'VCCADC_0': 'VCCADC', 'GNDADC_0': 'GNDADC'}
    for nm, net in cfg.items():
        put(BYNAME[nm], net)
    vcco = {'0': '+3V3', '13': '+3V3', '14': '+3V3', '15': '+3V3', '34': '+1V35', '35': 'VADJ', '16': 'VADJ'}
    for p in PINS:
        n = p['name']
        if p['num'] in m:
            continue
        if n.startswith('VCCO_'):
            m[p['num']] = vcco[n.split('_')[1]]
        elif n in ('VCCINT', 'VCCBRAM'):
            m[p['num']] = '+1V0'
        elif n == 'VCCAUX':
            m[p['num']] = '+1V8'
        elif n == 'MGTAVCC':
            m[p['num']] = '+1V0_MGT'
        elif n == 'MGTAVTT':
            m[p['num']] = '+1V2_MGT'
        elif n == 'GND':
            m[p['num']] = 'GND'
        elif n.startswith('IO_'):
            m[p['num']] = 'NC'
        else:
            raise ValueError('unplanned fpga pin %s %s' % (p['num'], n))
    return m


PLAN = plan()


def units_of(pred):
    return sorted({p['unit'] for p in PINS if pred(p)})


def build_banks(d):
    s = d.sheet('FPGA_BANKS', 'XC7A100T-2FGG484 IO banks', width=900)
    s.note('Bank 14 (3V3): FMC D0-D31 on SelectMAP D00-D31, FMC controls, CSI_B/RDWR_B. Bank 15 (3V3): FMC A0-A18, clocks, debug')
    s.note('Bank 13 (3V3): Pmods, audio DAC, SFP sideband. Bank 34 (1V35): DDR3L x16, internal VREF. Banks 35/16 (VADJ): VITA LA00-LA33')
    s.note('DDR3: data T0/T1, addr/cmd T2/T3 + IO_0 (ODT), RESET_N IO_25, CS_N tied low (MIG chip select off). Checked vs UG586 rules')
    s.add(LIBID, PLAN, value='XC7A100T-2FGG484I', fp='Package_BGA:Xilinx_FGG484', ref='U100', units=[1, 2, 3])
    # ug483 table 2-2: per bank 2x4.7u + 4x0.47u, one 47u per same-voltage group of up to 4 banks
    for net, n in (('+3V3', 3), ('+1V35', 1), ('VADJ', 2)):
        decap(s, net, ['47uF'])
        for _ in range(n):
            decap(s, net, ['4.7uF', '4.7uF', '470nF', '470nF', '470nF', '470nF'])
    R(s, 'FPGA_PUDC_B', '+3V3', '1k')
    return s


def build_cfg(d):
    s = d.sheet('FPGA_CFG', 'FPGA configuration, JTAG, core power, XADC', width=560)
    s.note('Slave SelectMAP (M[2:0]=110) driven by STM32: PROGRAM_B/INIT_B/DONE/CCLK/CSI_B/RDWR_B + FMC D0-D15')
    s.note('JTAG always available (Xilinx 2x7 2mm + 6-pin 0.1in). Bitstream golden/apps live in STM32 QSPI flash')
    s.add(LIBID, PLAN, value='XC7A100T-2FGG484I', fp='Package_BGA:Xilinx_FGG484', ref='U100', units=[6, 7])
    R(s, 'FPGA_M2', '+3V3', '1k')
    R(s, 'FPGA_M1', '+3V3', '1k')
    R(s, 'FPGA_M0', 'GND', '1k')
    R(s, 'FPGA_PROGRAM_B', '+3V3', '4.7k')
    R(s, 'FPGA_INIT_B', '+3V3', '4.7k')
    R(s, 'FPGA_DONE', '+3V3', '330')
    R(s, 'FPGA_CSI_B', '+3V3', '4.7k')
    R(s, 'FPGA_RDWR_B', '+3V3', '4.7k')
    button(s, 'FPGA_PROGRAM_B', 'GND', 'FPGA_PROG')
    s.add('Transistor_FET:2N7002', {'G': 'FPGA_DONE', 'S': 'GND', 'D': '.DONE_LED_K'}, value='2N7002', prefix='Q')
    s.add('Device:LED_Small', {'1': '.DONE_LED_K', '2': '.DONE_LED_A'}, value='GREEN DONE',
          fp='LED_SMD:LED_0603_1608Metric', prefix='D')
    R(s, '.DONE_LED_A', '+3V3', '1k')
    tp(s, 'FPGA_DONE', 'DONE')
    tp(s, 'FPGA_INIT_B', 'INIT')
    # jtag
    header(s, ['GND', '+3V3', 'GND', 'FPGA_TMS', 'GND', 'FPGA_TCK', 'GND', 'FPGA_TDO', 'GND', 'FPGA_TDI',
               'GND', 'NC', 'GND', 'NC'], rows=2, value='FPGA_JTAG Xilinx',
           fp='Connector_PinHeader_2.00mm:PinHeader_2x07_P2.00mm_Vertical')
    header(s, ['+3V3', 'GND', 'FPGA_TCK', 'FPGA_TDO', 'FPGA_TDI', 'FPGA_TMS'], value='FPGA_JTAG 6p')
    R(s, 'FPGA_TMS', '+3V3', '10k')
    # core rails
    # ug483 table 2-2 for xc7a100t fgg484
    C(s, '+1V0', 'GND', '330uF 2.5V polymer', fp='Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D')
    decap(s, '+1V0', ['4.7uF'] * 6 + ['470nF'] * 8)
    decap(s, '+1V0', ['100uF', '470nF', '470nF'])  # vccbram pins
    decap(s, '+1V8', ['47uF'] + ['4.7uF'] * 3 + ['470nF'] * 5)
    decap(s, '+3V3', ['47uF'])  # vcco_0
    FB(s, '+1V8', 'VCCADC')
    decap(s, 'VCCADC', ['10uF', '100nF'], gnd='GNDADC')
    FB(s, 'GNDADC', 'GND')
    s.pwr_flag('VCCADC', 330.2, 12.7)
    s.pwr_flag('GNDADC', 342.9, 12.7)
    return s


def build_io(d):
    s = d.sheet('FPGA_IO', 'FPGA clocks, Pmods, LEDs, buttons, soft-core debug', width=560)
    s.note('Soft core SWD on MIPI-10 (Black Magic Probe) and FTDI-pinout UART, both on FPGA user IO (bank 15)')
    s.note('Pmods are Digilent-compatible 12-pin hosts (3V3), vertical sockets (front panel is the only rack-accessible edge). Audio MCLK families: 24.576 / 22.5792 MHz')
    for net, freq in (('SYSCLK_100M', '100MHz'), ('AUD_CLK_48K', '24.576MHz'), ('AUD_CLK_44K', '22.5792MHz')):
        s.add('Oscillator:SiT8008xx-1x-xxE', {'OE': '+3V3', 'GND': 'GND', 'OUT': net, 'Vdd': '+3V3'},
              value='%s 3V3 CMOS' % freq, fp=OSC3225, prefix='X')
        C(s, '+3V3', 'GND', '100nF')
    for i in range(4):
        led_to_gnd(s, 'FPGA_LED%d' % i, 'GREEN', '1k')
    for i in range(2):
        button(s, 'FPGA_BTN%d' % i, '+3V3', 'FPGA_BTN%d' % i)
        R(s, 'FPGA_BTN%d' % i, 'GND', '10k')
    s.add('Connector:Conn_ARM_JTAG_SWD_10',
          {'1': '+3V3', '2': 'SC_SWDIO', '3': 'GND', '4': 'SC_SWCLK', '5': 'GND', '6': 'SC_SWO', '8': 'NC',
           '9': 'GND', '10': 'SC_NRST'}, value='SOFTCORE_SWD MIPI-10', fp=MIPI10, prefix='J')
    R(s, 'SC_NRST', '+3V3', '10k')
    header(s, ['GND', 'NC', 'NC', 'SC_UART_RX', 'SC_UART_TX', 'NC'], value='SOFTCORE_UART FTDI')
    for pm in ('PMODA', 'PMODB'):
        # pmod pin k top row -> fp 2k-1, bottom row -> fp 2k
        nets = {}
        top = ['%s_IO1' % pm, '%s_IO2' % pm, '%s_IO3' % pm, '%s_IO4' % pm, 'GND', '+3V3']
        bot = ['%s_IO5' % pm, '%s_IO6' % pm, '%s_IO7' % pm, '%s_IO8' % pm, 'GND', '+3V3']
        for k in range(6):
            nets[str(2 * k + 1)] = top[k]
            nets[str(2 * k + 2)] = bot[k]
        s.add('Connector_Generic:Conn_02x06_Odd_Even', nets, value=pm,
              fp='Connector_PinSocket_2.54mm:PinSocket_2x06_P2.54mm_Vertical', prefix='J')
        decap(s, '+3V3', ['10uF'])
    return s


def build_gtp(d):
    s = d.sheet('FPGA_GTP', 'GTP quad 216, SFP cages, reference clocks', width=560)
    s.note('Lane 0 -> SFP0, lane 1 -> SFP1, lane 2/3 -> VITA DP0/DP1. REFCLK0 125 MHz LVDS XO, REFCLK1 = VITA GBTCLK0_M2C')
    s.note('TX AC caps on carrier for all lanes. VITA M2C caps are on the mezzanine per VITA 57.1')
    s.add(LIBID, PLAN, value='XC7A100T-2FGG484I', fp='Package_BGA:Xilinx_FGG484', ref='U100', units=[4, 5])
    R(s, 'GTP_RREF', '+1V2_MGT', '100 1%')
    s.pwr_flag('GTP_RREF', 355.6, 12.7)
    # ug482 table 5-7: 4.7u at bga edge + 2x0.1u on bottom side per supply
    decap(s, '+1V0_MGT', ['4.7uF', '100nF', '100nF'])
    decap(s, '+1V2_MGT', ['4.7uF', '100nF', '100nF'])

    def ac(a, b):
        C(s, a, b, '100nF', fp=C0201)

    for k in (0, 1):
        ac('GTP%d_TX_P' % k, 'SFP%d_TD_P' % k)
        ac('GTP%d_TX_N' % k, 'SFP%d_TD_N' % k)
        ac('SFP%d_RD_P' % k, 'GTP%d_RX_P' % k)
        ac('SFP%d_RD_N' % k, 'GTP%d_RX_N' % k)
    for lane, dp in ((2, 0), (3, 1)):
        ac('GTP%d_TX_P' % lane, 'MEZZ_DP%d_C2M_P' % dp)
        ac('GTP%d_TX_N' % lane, 'MEZZ_DP%d_C2M_N' % dp)
    s.add('Oscillator:SiT9365xx-xBx-xxE', {'OE': '+3V3', 'GND': 'GND', 'OUT+': '.REFCLK0_OSC_P',
                                           'OUT-': '.REFCLK0_OSC_N', 'VDD': '+3V3'},
          value='125MHz LVDS', prefix='X')
    C(s, '+3V3', 'GND', '100nF')
    ac('.REFCLK0_OSC_P', 'GTP_REFCLK0_P')
    ac('.REFCLK0_OSC_N', 'GTP_REFCLK0_N')
    ac('MEZZ_GBTCLK0_M2C_P', 'GTP_REFCLK1_P')
    ac('MEZZ_GBTCLK0_M2C_N', 'GTP_REFCLK1_N')
    for k in (0, 1):
        v = '+3V3_SFP%d' % k
        FB(s, '+3V3', v)
        decap(s, v, ['22uF', '100nF'])
        s.add('Interface_Optical:SFP',
              {'VeeT': 'GND', 'VeeR': 'GND', 'VccT': v, 'VccR': v, 'TX_FAULT': 'SFP%d_TX_FAULT' % k,
               'TX_DISABLE': 'SFP%d_TX_DIS' % k, 'MOD_DEF2': 'SFP%d_SDA' % k, 'MOD_DEF1': 'SFP%d_SCL' % k,
               'MOD_DEF0': 'SFP%d_MOD_ABS' % k, 'RATE_SELECT': '.SFP%d_RS' % k, 'RX_LOS': 'SFP%d_LOS' % k,
               'RD-': 'SFP%d_RD_N' % k, 'RD+': 'SFP%d_RD_P' % k, 'TD+': 'SFP%d_TD_P' % k,
               'TD-': 'SFP%d_TD_N' % k, 'CAGE': 'GND'},
              value='SFP cage', fp='Connector:Connector_SFP_and_Cage', prefix='J')
        for sig in ('TX_FAULT', 'SDA', 'SCL', 'MOD_ABS', 'LOS'):
            R(s, 'SFP%d_%s' % (k, sig), '+3V3', '4.7k')
        R(s, 'SFP%d_TX_DIS' % k, '+3V3', '10k')
        R(s, '.SFP%d_RS' % k, 'GND', '10k')
        s.pwr_flag(v, 330.2 + 12.7 * k, 12.7)
    return s
