from dcommon import C, FB, R, decap, header, button, led_to_gnd, tp, MIPI10, XTAL3225, C0603, HDR

FMC_D = ['PD14', 'PD15', 'PD0', 'PD1', 'PE7', 'PE8', 'PE9', 'PE10', 'PE11', 'PE12', 'PE13', 'PE14', 'PE15',
         'PD8', 'PD9', 'PD10', 'PH8', 'PH9', 'PH10', 'PH11', 'PH12', 'PH13', 'PH14', 'PH15',
         'PI0', 'PI1', 'PI2', 'PI3', 'PI6', 'PI7', 'PI9', 'PI10']
FMC_A = ['PF0', 'PF1', 'PF2', 'PF3', 'PF4', 'PF5', 'PF12', 'PF13', 'PF14', 'PF15',
         'PG0', 'PG1', 'PG2', 'PG3', 'PG4', 'PG5', 'PD11', 'PD12', 'PD13']

PINMAP = {}
for i, p in enumerate(FMC_D):
    PINMAP[p] = ('FMC_D%d' % i, 'FMC_D%d' % i)
for i, p in enumerate(FMC_A):
    PINMAP[p] = ('FMC_A%d' % i, 'FMC_A%d' % i)
PINMAP.update({
    'PD4': ('FMC_NOE', 'FMC_NOE'), 'PD5': ('FMC_NWE', 'FMC_NWE'), 'PD6': ('FMC_NWAIT', 'FMC_NWAIT'),
    'PD7': ('FMC_NE1', 'FMC_NE1'), 'PE0': ('FMC_NBL0', 'FMC_NBL0'), 'PE1': ('FMC_NBL1', 'FMC_NBL1'),
    'PI4': ('FMC_NBL2', 'FMC_NBL2'), 'PI5': ('FMC_NBL3', 'FMC_NBL3'), 'PD3': ('FMC_CLK', 'FMC_CLK'),
    # usb hs ulpi
    'PA5': ('ULPI_CK', 'USB_OTG_HS_ULPI_CK'), 'PI11': ('ULPI_DIR', 'USB_OTG_HS_ULPI_DIR'),
    'PH4': ('ULPI_NXT', 'USB_OTG_HS_ULPI_NXT'), 'PC0': ('ULPI_STP', 'USB_OTG_HS_ULPI_STP'),
    'PA3': ('ULPI_D0', 'USB_OTG_HS_ULPI_D0'), 'PB0': ('ULPI_D1', 'USB_OTG_HS_ULPI_D1'),
    'PB1': ('ULPI_D2', 'USB_OTG_HS_ULPI_D2'), 'PB10': ('ULPI_D3', 'USB_OTG_HS_ULPI_D3'),
    'PB11': ('ULPI_D4', 'USB_OTG_HS_ULPI_D4'), 'PB12': ('ULPI_D5', 'USB_OTG_HS_ULPI_D5'),
    'PB13': ('ULPI_D6', 'USB_OTG_HS_ULPI_D6'), 'PB5': ('ULPI_D7', 'USB_OTG_HS_ULPI_D7'),
    # ethernet rmii
    'PA1': ('ETH_REF_CLK', 'ETH_REF_CLK'), 'PA2': ('ETH_MDIO', 'ETH_MDIO'), 'PC1': ('ETH_MDC', 'ETH_MDC'),
    'PA7': ('ETH_CRS_DV', 'ETH_CRS_DV'), 'PC4': ('ETH_RXD0', 'ETH_RXD0'), 'PC5': ('ETH_RXD1', 'ETH_RXD1'),
    'PG11': ('ETH_TX_EN', 'ETH_TX_EN'), 'PG13': ('ETH_TXD0', 'ETH_TXD0'), 'PG12': ('ETH_TXD1', 'ETH_TXD1'),
    # quadspi dual flash
    'PF10': ('QSPI_CLK', 'QUADSPI_CLK'), 'PG6': ('QSPI_NCS', 'QUADSPI_BK1_NCS'),
    'PF8': ('QSPI_BK1_IO0', 'QUADSPI_BK1_IO0'), 'PF9': ('QSPI_BK1_IO1', 'QUADSPI_BK1_IO1'),
    'PF7': ('QSPI_BK1_IO2', 'QUADSPI_BK1_IO2'), 'PF6': ('QSPI_BK1_IO3', 'QUADSPI_BK1_IO3'),
    'PH2': ('QSPI_BK2_IO0', 'QUADSPI_BK2_IO0'), 'PH3': ('QSPI_BK2_IO1', 'QUADSPI_BK2_IO1'),
    'PG9': ('QSPI_BK2_IO2', 'QUADSPI_BK2_IO2'), 'PG14': ('QSPI_BK2_IO3', 'QUADSPI_BK2_IO3'),
    # usb fs host
    'PA11': ('USBH_DM', 'USB_OTG_FS_DM'), 'PA12': ('USBH_DP', 'USB_OTG_FS_DP'),
    # debug
    'PA13': ('SWDIO', 'DEBUG_JTMS-SWDIO'), 'PA14': ('SWCLK', 'DEBUG_JTCK-SWCLK'), 'PB3': ('SWO', 'DEBUG_JTDO-SWO'),
    # misc peripherals
    'PA4': ('STM32_DAC1_OUT1', 'DAC1_OUT1'),
    'PB6': ('I2C1_SCL', 'I2C1_SCL'), 'PB7': ('I2C1_SDA', 'I2C1_SDA'),
    'PB8': ('FDCAN1_RX', 'FDCAN1_RX'), 'PB9': ('FDCAN1_TX', 'FDCAN1_TX'),
    'PB14': ('CONSOLE_TX', 'USART1_TX'), 'PB15': ('CONSOLE_RX', 'USART1_RX'),
    'PJ8': ('MCU_UART_TX', 'UART8_TX'), 'PJ9': ('MCU_UART_RX', 'UART8_RX'),
    'PH0': ('.HSE_IN', 'RCC_OSC_IN'), 'PH1': ('.HSE_OUT', 'RCC_OSC_OUT'),
    'PC14': ('.LSE_IN', 'RCC_OSC32_IN'), 'PC15': ('.LSE_OUT', 'RCC_OSC32_OUT'),
    # fpga control, gpio
    'PG7': ('FPGA_IRQ0', None), 'PG8': ('FPGA_IRQ1', None), 'PG10': ('FPGA_IRQ2', None),
    'PG15': ('FPGA_IRQ3', None), 'PJ6': ('FPGA_IRQ4', None), 'PK0': ('FPGA_IRQ5', None),
    'PJ7': ('FPGA_PROGRAM_B', None), 'PJ10': ('FPGA_INIT_B', None), 'PK1': ('FPGA_DONE', None),
    'PI8': ('FPGA_CCLK', None), 'PH6': ('FPGA_CSI_B', None), 'PH7': ('FPGA_RDWR_B', None),
    'PH5': ('FPGA_RST_N', None),
    'PK2': ('IOX_INT_N', None), 'PC13': ('MCU_BTN', None), 'PI15': ('MCU_LED0', None), 'PJ11': ('MCU_LED1', None),
})
BREAKOUT = ['PA0', 'PA6', 'PA8', 'PA9', 'PA10', 'PA15', 'PB2', 'PB4', 'PC2_C', 'PC3_C', 'PC6', 'PC7',
            'PE2', 'PE3', 'PE4', 'PE5', 'PE6', 'PF11', 'PC8', 'PC9', 'PC10', 'PC11', 'PC12', 'PD2']
for p in BREAKOUT:
    PINMAP[p] = ('MCU_' + p.replace('_C', ''), None)


def check_af(pins):
    bad = []
    by = {p['name']: p for p in pins}
    for pn, (net, af) in PINMAP.items():
        if pn not in by:
            bad.append('missing pin %s' % pn)
        elif af and af not in by[pn]['alts']:
            bad.append('%s lacks %s' % (pn, af))
    return bad


def build(d):
    import sch
    s = d.sheet('STM32', 'STM32H755BIT6 (LQFP208), clocks, debug, IO expander, breakout', width=640)
    s.note('LDO supply mode (VOS0 480 MHz): VDDLDO=VDD, VCAP tied 2x2.2uF, VDDSMPS/VFBSMPS/VSSSMPS=GND, VLXSMPS open (RM0399 fig 22)')
    s.note('FMC bank1 NOR/PSRAM sync burst, 32-bit, non-muxed, A0-A18 (2 MB window). NL not used')
    s.note('slow controls on TCA9535 0x20 (I2C1): VADJ, mezz PG/PRSNT, PHY resets, USB host power')
    node = sch.flat('MCU_ST_STM32H7', 'STM32H755BITx')
    pins, _ = sch.geom(node, 1)
    bad = check_af(pins)
    if bad:
        raise ValueError('pinmux: ' + '; '.join(bad))
    nets = {}
    for p in pins:
        n = p['name']
        if n in PINMAP:
            nets[p['num']] = PINMAP[n][0]
        elif n in ('VDD', 'VDDLDO', 'PDR_ON', 'VBAT', 'VDD33_USB', 'VDD50_USB'):
            nets[p['num']] = '+3V3'
        elif n in ('VSS', 'VSSA', 'VSSSMPS', 'VDDSMPS', 'VFBSMPS'):
            nets[p['num']] = 'GND'
        elif n == 'VLXSMPS':
            nets[p['num']] = 'NC'
        elif n in ('VDDA', 'VREF+'):
            nets[p['num']] = '+3V3_VDDA'
        elif n == 'VCAP':
            nets[p['num']] = '.VCAP'
        elif n == 'NRST':
            nets[p['num']] = 'NRST'
        elif n == 'BOOT0':
            nets[p['num']] = '.BOOT0'
        else:
            nets[p['num']] = 'NC'
    unused = [p['name'] for p in pins if nets[p['num']] == 'NC']
    s.add('MCU_ST_STM32H7:STM32H755BITx', nets, value='STM32H755BIT6', props={'LCSC': 'C730208'})
    nvdd = sum(1 for p in pins if p['name'] in ('VDD', 'VDDLDO'))
    decap(s, '+3V3', ['100nF'] * nvdd + ['4.7uF', '4.7uF', '10uF'])
    decap(s, '.VCAP', ['2.2uF', '2.2uF'])  # an4938: 2x2.2uF total, vcap pins tied
    decap(s, '+3V3', ['1uF', '100nF'])  # usb supplies
    FB(s, '+3V3', '+3V3_VDDA')
    decap(s, '+3V3_VDDA', ['1uF', '100nF', '10nF'])
    s.pwr_flag('+3V3_VDDA', 330.2, 12.7)

    # clocks
    s.add('Device:Crystal_GND24', {'1': '.HSE_IN', '3': '.HSE_OUT', '2': 'GND', '4': 'GND'},
          value='25MHz 8pF', fp=XTAL3225, prefix='Y')
    C(s, '.HSE_IN', 'GND', '10pF')
    C(s, '.HSE_OUT', 'GND', '10pF')
    s.add('Device:Crystal_Small', {'1': '.LSE_IN', '2': '.LSE_OUT'}, value='32.768kHz 6pF',
          fp='Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm', prefix='Y')
    C(s, '.LSE_IN', 'GND', '8.2pF')
    C(s, '.LSE_OUT', 'GND', '8.2pF')

    # reset, boot
    C(s, 'NRST', 'GND', '100nF')
    button(s, 'NRST', 'GND', 'MCU_RESET')
    tp(s, 'NRST', 'NRST')
    R(s, '.BOOT0', 'GND', '10k')
    header(s, ['.BOOT0', '+3V3'], value='BOOT0')

    # debug: mipi-10 for black magic probe, dupont swd, console uart (ftdi pinout)
    s.add('Connector:Conn_ARM_JTAG_SWD_10',
          {'1': '+3V3', '2': 'SWDIO', '3': 'GND', '4': 'SWCLK', '5': 'GND', '6': 'SWO', '8': 'NC', '9': 'GND',
           '10': 'NRST'}, value='MCU_SWD MIPI-10', fp=MIPI10, prefix='J')
    header(s, ['+3V3', 'SWCLK', 'GND', 'SWDIO', 'NRST', 'SWO'], value='MCU_SWD')
    header(s, ['GND', 'NC', 'NC', 'CONSOLE_RX', 'CONSOLE_TX', 'NC'], value='MCU_UART FTDI')

    # user io
    led_to_gnd(s, 'MCU_LED0', 'GREEN')
    led_to_gnd(s, 'MCU_LED1', 'BLUE')
    button(s, 'MCU_BTN', '+3V3', 'MCU_USER')
    R(s, 'MCU_BTN', 'GND', '10k')

    # i2c1 and expander
    R(s, 'I2C1_SCL', '+3V3', '2.2k')
    R(s, 'I2C1_SDA', '+3V3', '2.2k')
    R(s, 'IOX_INT_N', '+3V3', '10k')
    s.add('Interface_Expansion:TCA9535PWR',
          {'~{INT}': 'IOX_INT_N', 'A0': 'GND', 'A1': 'GND', 'A2': 'GND', 'SCL': 'I2C1_SCL', 'SDA': 'I2C1_SDA',
           'VCC': '+3V3', 'GND': 'GND',
           'P00': 'VADJ_EN', 'P01': 'VADJ_SEL0', 'P02': 'VADJ_SEL1', 'P03': 'VADJ_PG',
           'P04': 'MEZZ_PRSNT_L', 'P05': 'MEZZ_PG_M2C', 'P06': 'MEZZ_PG_C2M', 'P07': 'PG_1V8',
           'P10': 'ETH_NRST', 'P11': 'ULPI_RST', 'P12': 'USBH_VBUS_EN', 'P13': 'USBH_OC_N',
           'P14': 'IOX_P14', 'P15': 'IOX_P15', 'P16': 'IOX_P16', 'P17': 'IOX_P17'},
          value='TCA9535PWR 0x20')
    C(s, '+3V3', 'GND', '100nF')
    header(s, ['IOX_P14', 'IOX_P15', 'IOX_P16', 'IOX_P17', '+3V3', 'GND'], value='IOX_SPARE')
    # board id: factory eui-48 (ethernet mac) + 128 b user area. a2=1 puts it at 0x54, clear of a vita
    # module eeprom (0x50-0x53 by ga)
    s.add('Memory_EEPROM:24AA025E-SN',
          {'A0': 'GND', 'A1': 'GND', 'A2': '+3V3', 'V_{SS}': 'GND', 'SDA': 'I2C1_SDA', 'SCL': 'I2C1_SCL',
           'NC': 'NC', 'V_{CC}': '+3V3'}, value='24AA025E48 0x54 MAC', by='name', ref='U200')
    C(s, '+3V3', 'GND', '100nF')

    # breakout header
    # pc8-pc12/pd2 also carry sdmmc1 if an sd card is wanted on a daughter board
    b = ['+3V3', '+5V', 'MCU_PA0', 'MCU_PA6', 'MCU_PA8', 'MCU_PA9', 'MCU_PA10', 'MCU_PA15', 'GND', 'GND',
         'MCU_PB2', 'MCU_PB4', 'MCU_PC2', 'MCU_PC3', 'MCU_PC6', 'MCU_PC7', 'MCU_PC8', 'MCU_PC9', 'GND', 'GND',
         'MCU_PC10', 'MCU_PC11', 'MCU_PC12', 'MCU_PD2', 'MCU_PE2', 'MCU_PE3', 'MCU_PE4', 'MCU_PE5', 'GND', 'GND',
         'MCU_PE6', 'MCU_PF11', 'I2C1_SCL', 'I2C1_SDA', 'FDCAN1_TX', 'FDCAN1_RX', 'NRST', 'GND', '+3V3', '+5V']
    header(s, b, rows=2, value='MCU_BREAKOUT')
    return s, unused
