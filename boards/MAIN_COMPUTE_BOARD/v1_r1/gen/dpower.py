from dcommon import C, FB, LED, R, decap, tp, C1206, C1210, R0603, TP_LOOP

L_BUCK = 'Inductor_SMD:L_Bourns_SRP6060FA'
L_SMALL = 'Inductor_SMD:L_APV_ANR4020'
L_1008 = 'Inductor_SMD:L_1008_2520Metric'


def lmr33630(s, tag, vout_net, en, pg, rtop, rbot, pg_pull='+5V'):
    sw, boot, fb, vcc = '.SW_' + tag, '.BOOT_' + tag, '.FB_' + tag, '.VCC_' + tag
    s.add('Regulator_Switching:LMR33630ADDA',
          {'1': 'GND', '9': 'GND', 'VIN': '+12V', 'EN': en, 'PG': pg, 'FB': fb, 'VCC': vcc,
           'BOOT': boot, 'SW': sw}, value='LMR33630ADDA')
    C(s, vcc, 'GND', '1uF')
    C(s, boot, sw, '100nF')
    s.add('Device:L', {'1': sw, '2': vout_net}, value='6.8uH 6A', fp=L_BUCK, prefix='L')
    R(s, vout_net, fb, rtop)
    R(s, fb, 'GND', rbot)
    if pg.startswith('.') or pg.startswith('PG_'):
        R(s, pg, pg_pull, '100k')
    C(s, '+12V', 'GND', '10uF 25V', fp=C1206)
    C(s, '+12V', 'GND', '10uF 25V', fp=C1206)
    C(s, '+12V', 'GND', '100nF 25V')
    decap(s, vout_net, ['22uF', '22uF', '22uF'])


def tps62130(s, tag, vin, vout_net, en, pg, rtop, rbot, pg_pull):
    sw, fb, ss = '.SW_' + tag, '.FB_' + tag, '.SS_' + tag
    s.add('Regulator_Switching:TPS62130',
          {'SW': sw, 'PG': pg, 'FB': fb, 'GND': 'GND', 'FSW': vin, 'DEF': 'GND', 'SS/TR': ss,
           'VIN': vin, 'EN': en, 'VOS': vout_net}, value='TPS62130RGT')
    C(s, ss, 'GND', '3.3nF')
    s.add('Device:L', {'1': sw, '2': vout_net}, value='2.2uH 4A', fp=L_SMALL, prefix='L')
    R(s, vout_net, fb, rtop)
    if rbot:
        R(s, fb, 'GND', rbot)
    R(s, pg, pg_pull, '100k' if pg_pull == '+5V' else '10k')
    decap(s, vin, ['10uF 25V', '100nF 25V'])
    decap(s, vout_net, ['22uF', '22uF'])


def build(d):
    s = d.sheet('POWER', 'Power: 12V input, bucks, FPGA rails, VADJ', width=520)
    s.note('12V barrel in -> 5V/3V3 (LMR33630), 3V3_MEZZ and VADJ (TPS62130). 5V -> 1V0 VCCINT, 1V8 VCCAUX (TPS62130), 1V35 DDR (TLV62568)')
    s.note('Sequence: 12V -> 5V -> 1V0 -> 1V8 (+MGT LDOs, 1V35) -> 3V3. VADJ (12V, TPS62130) enabled by STM32 via IO expander')
    s.note('VADJ_SEL1:0 = 00 1.8V, 01 2.5V, 10 2.6V, 11 3.3V')

    # input protection and monitor
    s.add('Connector:Barrel_Jack_Switch', {'1': '+12V_JACK', '2': 'GND', '3': 'NC'}, value='12V IN 5.5x2.1',
          fp='Connector_BarrelJack:BarrelJack_Horizontal', prefix='J')
    s.add('Device:Polyfuse', {'1': '+12V_JACK', '2': '.12V_FUSED'}, value='3A hold 1812',
          fp='Fuse:Fuse_1812_4532Metric', prefix='F')
    s.add('Device:D_Zener_Small', {'1': '.12V_FUSED', '2': 'GND'}, value='SMAJ15A', fp='Diode_SMD:D_SMA', prefix='D')
    s.add('Transistor_FET:DMP3013SFV', {'D': '.12V_FUSED', 'S': '.12V_PROT', 'G': '.QREV_G'},
          value='DMP3013SFV', prefix='Q')
    R(s, '.QREV_G', 'GND', '10k')
    s.add('Device:D_Zener_Small', {'1': '.12V_PROT', '2': '.QREV_G'}, value='BZT52C10',
          fp='Diode_SMD:D_SOD-123', prefix='D')
    s.add('Device:R_Shunt', {'1': '.12V_PROT', '2': '+12V', '3': '.ISNS_P', '4': '.ISNS_N'}, value='10m 1W',
          fp='Resistor_SMD:R_Shunt_Vishay_WSK2512_6332Metric_T1.19mm', prefix='R')
    s.add('Sensor_Energy:INA219AxD',
          {'IN+': '.ISNS_P', 'IN-': '.ISNS_N', 'VS': '+3V3', 'GND': 'GND', 'SCL': 'I2C1_SCL',
           'SDA': 'I2C1_SDA', 'A0': 'GND', 'A1': 'GND'}, value='INA219 0x40')
    C(s, '+3V3', 'GND', '100nF')
    # 12v input bulk: two 1210 ceramics (about 10-15 uF effective at 12 V bias), fixed refs
    for ref in ('C2', 'C300'):
        s.add('Device:C_Small', {'1': '+12V', '2': 'GND'}, value='22uF 25V X5R', fp=C1210, ref=ref)
    R(s, '+12V', '.EN_12V', '100k')
    R(s, '.EN_12V', 'GND', '15k')

    # 5V, 3V3, 3V3_MEZZ
    lmr33630(s, '5V', '+5V', '.EN_12V', '.PG_5V', '100k', '24.9k')
    lmr33630(s, '3V3', '+3V3', 'PG_1V8', '.PG_3V3', '100k', '43.2k')
    # small buck so it fits on top next to the vita supply pins
    tps62130(s, '3V3M', '+12V', '+3V3_MEZZ', '.EN_12V', '.PG_3V3M', '309k', '100k', '+5V')

    # fpga core and aux
    tps62130(s, '1V0', '+5V', '+1V0', '.PG_5V', '.PG_1V0', '49.9k', '200k', '+5V')
    tps62130(s, '1V8', '+5V', '+1V8', '.PG_1V0', 'PG_1V8', '249k', '200k', '+5V')

    # vadj with fet switched feedback
    tps62130(s, 'VADJ', '+12V', 'VADJ', 'VADJ_EN', 'VADJ_PG', '249k', '200k', '+3V3')
    R(s, 'VADJ_EN', 'GND', '100k')
    R(s, '.FB_VADJ', '.VSEL0_D', '280k')
    R(s, '.FB_VADJ', '.VSEL1_D', '249k')
    s.add('Transistor_FET:2N7002', {'G': 'VADJ_SEL0', 'S': 'GND', 'D': '.VSEL0_D'}, value='2N7002', prefix='Q')
    s.add('Transistor_FET:2N7002', {'G': 'VADJ_SEL1', 'S': 'GND', 'D': '.VSEL1_D'}, value='2N7002', prefix='Q')
    R(s, 'VADJ_SEL0', 'GND', '100k')
    R(s, 'VADJ_SEL1', 'GND', '100k')

    # ddr 1v35
    s.add('Regulator_Switching:TLV62568DBV', {'EN': 'PG_1V8', 'GND': 'GND', 'SW': '.SW_1V35', 'VIN': '+5V',
                                               'FB': '.FB_1V35'}, value='TLV62568DBV')
    s.add('Device:L', {'1': '.SW_1V35', '2': '+1V35'}, value='2.2uH 1.5A', fp=L_1008, prefix='L')
    R(s, '+1V35', '.FB_1V35', '150k')
    R(s, '.FB_1V35', 'GND', '120k')
    decap(s, '+5V', ['10uF'])
    decap(s, '+1V35', ['22uF', '22uF'])

    # gtp rails from 1v8
    s.add('Regulator_Linear:TLV75801PDBV', {'IN': '+1V8', 'GND': 'GND', 'EN': '+1V8', 'FB': '.FB_MGTAVCC',
                                             'OUT': '+1V0_MGT'}, value='TLV75801 MGTAVCC 1V0')
    R(s, '+1V0_MGT', '.FB_MGTAVCC', '90.9k')
    R(s, '.FB_MGTAVCC', 'GND', '110k')
    decap(s, '+1V8', ['1uF'])
    decap(s, '+1V0_MGT', ['4.7uF'])
    # rc delay so mgtavtt ramps after mgtavcc (ds181)
    R(s, '+1V8', '.EN_MGTAVTT', '100k')
    C(s, '.EN_MGTAVTT', 'GND', '1uF')
    s.add('Regulator_Linear:TLV75801PDBV', {'IN': '+1V8', 'GND': 'GND', 'EN': '.EN_MGTAVTT', 'FB': '.FB_MGTAVTT',
                                             'OUT': '+1V2_MGT'}, value='TLV75801 MGTAVTT 1V2')
    R(s, '+1V2_MGT', '.FB_MGTAVTT', '130k')
    R(s, '.FB_MGTAVTT', 'GND', '110k')
    decap(s, '+1V8', ['1uF'])
    decap(s, '+1V2_MGT', ['4.7uF'])

    # filtered rails
    FB(s, '+5V', '+5V_AUD')
    decap(s, '+5V_AUD', ['10uF', '100nF'])
    FB(s, '+3V3', '+3V3_AUD')
    decap(s, '+3V3_AUD', ['10uF', '100nF'])
    s.add('Device:Polyfuse', {'1': '+12V', '2': '+12V_MEZZ'}, value='1.1A hold 1206',
          fp='Fuse:Fuse_1206_3216Metric', prefix='F')
    decap(s, '+12V_MEZZ', ['10uF 25V'])

    # power leds
    R(s, '+12V', '.LED12', '10k')
    LED(s, 'GND', '.LED12', 'RED 12V')
    R(s, '+3V3', '.LED33', '1k')
    LED(s, 'GND', '.LED33', 'GREEN 3V3')

    # test points: every rail, the power-good chain, and ground loops for scope probes
    for net, lab in (('+12V_JACK', '12VIN'), ('+12V', '12V'), ('+5V', '5V'), ('+3V3', '3V3'), ('+1V0', '1V0'),
                     ('+1V8', '1V8'), ('+1V35', '1V35'), ('VADJ', 'VADJ'), ('+3V3_MEZZ', '3V3M'),
                     ('+12V_MEZZ', '12VM'), ('+1V0_MGT', 'MGTAVCC'), ('+1V2_MGT', 'MGTAVTT'), ('+5V_AUD', '5VA'),
                     ('+3V3_AUD', '3V3A'), ('.PG_5V', 'PG5V'), ('.PG_1V0', 'PG1V0'), ('PG_1V8', 'PG1V8'),
                     ('.PG_3V3', 'PG3V3'), ('.PG_3V3M', 'PG3V3M'), ('VADJ_PG', 'PGVADJ')):
        tp(s, net, lab)
    for _ in range(4):
        tp(s, 'GND', 'GND', fp=TP_LOOP)

    # mounting: four corners of the free area (front panel and din carry the card at the edges)
    for _ in range(4):
        s.add('Mechanical:MountingHole_Pad', {'1': 'GND'}, value='M3',
              fp='MountingHole:MountingHole_3.2mm_M3_Pad_Via', prefix='H')

    flags = ['+12V_JACK', 'GND', '+12V', '+5V', '+3V3', '+3V3_MEZZ', '+1V0', '+1V8', 'VADJ', '+1V35',
             '+12V_MEZZ', '+5V_AUD', '+3V3_AUD']
    for i, n in enumerate(flags):
        s.pwr_flag(n, 304.8 + 12.7 * (i % 8), 12.7 + 12.7 * (i // 8))
    return s
