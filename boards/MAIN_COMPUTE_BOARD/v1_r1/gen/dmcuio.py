from dcommon import C, FB, R, decap, header, XTAL3225, C0402

USBC = 'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12'
USBA = 'Connector_USB:USB_A_Molex_67643_Horizontal'


def build(d):
    s = d.sheet('MCU_IO', 'STM32 peripherals: USB HS (ULPI), USB host, Ethernet, QSPI flash, CAN', width=560)
    s.note('USB-C device port -> USB3300 ULPI PHY (480 Mbps) for DFU / mass storage / UAC2 / bulk updates')
    s.note('USB-A host on OTG_FS for USB-MIDI controllers. LAN8742A RMII, PHY drives 50 MHz REF_CLK')
    s.note('2x W25Q01JVZEIQ (WSON-8, bottom side) in QUADSPI dual-flash mode (8-bit, 256 MB mapped). Both CS from BK1_NCS')

    # usb hs phy
    s.add('Interface_USB:USB3300-EZK',
          {'1': 'GND', '2': 'GND', '33': 'GND', 'EXTVBUS': 'GND', 'NXT': 'ULPI_NXT', 'DIR': 'ULPI_DIR',
           'STP': 'ULPI_STP', 'CLKOUT': 'ULPI_CK', 'VDD1.8': '.ULPI_1V8', 'VDD3.3': '+3V3',
           'DATA7': 'ULPI_D7', 'DATA6': 'ULPI_D6', 'DATA5': 'ULPI_D5', 'DATA4': 'ULPI_D4',
           'DATA3': 'ULPI_D3', 'DATA2': 'ULPI_D2', 'DATA1': 'ULPI_D1', 'DATA0': 'ULPI_D0',
           'XO': '.ULPI_XO', 'XI': '.ULPI_XI', 'VDDA1.8': '.ULPI_1V8A', 'CPEN': 'NC', 'REG_EN': '+3V3',
           'RBIAS': '.ULPI_RBIAS', 'VBUS': 'VBUS_HS', 'ID': 'NC', 'DP': 'USBHS_DP', 'DM': 'USBHS_DM',
           'RESET': 'ULPI_RST'}, value='USB3300-EZK')
    R(s, 'ULPI_RST', 'GND', '10k')
    R(s, '.ULPI_RBIAS', 'GND', '12k 1%')
    s.add('Device:Crystal_GND24', {'1': '.ULPI_XI', '3': '.ULPI_XO', '2': 'GND', '4': 'GND'},
          value='24MHz 12pF', fp=XTAL3225, prefix='Y')
    C(s, '.ULPI_XI', 'GND', '18pF')
    C(s, '.ULPI_XO', 'GND', '18pF')
    decap(s, '+3V3', ['100nF'] * 4 + ['4.7uF'])
    decap(s, '.ULPI_1V8', ['100nF', '100nF', '4.7uF'])
    decap(s, '.ULPI_1V8A', ['100nF', '1uF'])
    s.add('Connector:USB_C_Receptacle_USB2.0_16P',
          {'A1': 'GND', 'A12': 'GND', 'B1': 'GND', 'B12': 'GND', 'A4': 'VBUS_HS', 'A9': 'VBUS_HS',
           'B4': 'VBUS_HS', 'B9': 'VBUS_HS', 'A5': '.CC1', 'B5': '.CC2', 'A6': 'USBHS_DP', 'B6': 'USBHS_DP',
           'A7': 'USBHS_DM', 'B7': 'USBHS_DM', 'A8': 'NC', 'B8': 'NC', 'SH': 'GND'},
          value='USB-C HS', fp=USBC, prefix='J')
    R(s, '.CC1', 'GND', '5.1k')
    R(s, '.CC2', 'GND', '5.1k')
    s.add('Power_Protection:USBLC6-2SC6', {'1': 'USBHS_DP', '6': 'USBHS_DP', '3': 'USBHS_DM', '4': 'USBHS_DM',
                                            '2': 'GND', '5': 'VBUS_HS'}, value='USBLC6-2SC6')
    C(s, 'VBUS_HS', 'GND', '1uF')

    # usb fs host
    s.add('Power_Management:TPS2051CDBV', {'OUT': '+5V_USBH', 'GND': 'GND', '~{FLT}': 'USBH_OC_N',
                                            'EN': 'USBH_VBUS_EN', 'IN': '+5V'}, value='TPS2051C')
    R(s, 'USBH_OC_N', '+3V3', '10k')
    R(s, 'USBH_VBUS_EN', 'GND', '100k')
    C(s, '+5V', 'GND', '1uF')
    s.add('Device:C_Polarized_Small', {'1': '+5V_USBH', '2': 'GND'}, value='100uF 10V',
          fp='Capacitor_SMD:CP_Elec_6.3x7.7', prefix='C')
    s.add('Connector:USB_A', {'VBUS': '+5V_USBH', 'D-': 'USBH_DM', 'D+': 'USBH_DP', 'GND': 'GND', 'SH': 'GND'},
          value='USB-A HOST MIDI', fp=USBA, prefix='J')
    s.add('Power_Protection:USBLC6-2SC6', {'1': 'USBH_DP', '6': 'USBH_DP', '3': 'USBH_DM', '4': 'USBH_DM',
                                            '2': 'GND', '5': '+5V_USBH'}, value='USBLC6-2SC6')

    # ethernet
    s.add('Interface_Ethernet:LAN8742A',
          {'VDD2A': 'ETH_AVDD', 'VDD1A': 'ETH_AVDD', 'VDDIO': '+3V3', 'VDDCR': 'ETH_VDDCR', 'VSS': 'GND',
           'RXER/PHYAD0': '.ETH_PHYAD0', 'CRS_DV/MODE2': 'ETH_CRS_DV', 'MDIO': 'ETH_MDIO', 'MDC': 'ETH_MDC',
           '~{INT}/REFCLKO': 'ETH_REF_CLK', '~{RST}': 'ETH_NRST', 'TXEN': 'ETH_TX_EN', 'TXD0': 'ETH_TXD0',
           'TXD1': 'ETH_TXD1', 'LED2/~{INTSEL}': '.ETH_INTSEL', 'LED1/REGOFF': '.ETH_REGOFF',
           'XTAL2': '.ETH_XO', 'XTAL1/CLKIN': '.ETH_XI', 'RXD1/MODE1': 'ETH_RXD1', 'RXD0/MODE0': 'ETH_RXD0',
           'TXN': '.ETH_TXN', 'TXP': '.ETH_TXP', 'RXN': '.ETH_RXN', 'RXP': '.ETH_RXP', 'RBIAS': '.ETH_RBIAS'},
          value='LAN8742A-CZ')
    R(s, '.ETH_PHYAD0', 'GND', '10k')
    R(s, '.ETH_INTSEL', 'GND', '10k')
    R(s, '.ETH_REGOFF', 'GND', '10k')
    R(s, 'ETH_NRST', '+3V3', '10k')
    R(s, 'ETH_MDIO', '+3V3', '1.5k')
    R(s, '.ETH_RBIAS', 'GND', '12.1k 1%')
    s.add('Device:Crystal_GND24', {'1': '.ETH_XI', '3': '.ETH_XO', '2': 'GND', '4': 'GND'},
          value='25MHz 10pF', fp=XTAL3225, prefix='Y')
    C(s, '.ETH_XI', 'GND', '15pF')
    C(s, '.ETH_XO', 'GND', '15pF')
    decap(s, 'ETH_VDDCR', ['1uF', '470pF'])
    FB(s, '+3V3', 'ETH_AVDD')
    decap(s, 'ETH_AVDD', ['10uF', '100nF', '100nF'])
    decap(s, '+3V3', ['100nF'])
    for n in ('.ETH_TXP', '.ETH_TXN', '.ETH_RXP', '.ETH_RXN'):
        R(s, n, 'ETH_AVDD', '49.9 1%')
    s.add('Connector:RJ45_Hanrun_HR911105A_Horizontal',
          {'1': '.ETH_TXP', '2': '.ETH_TXN', '3': '.ETH_RXP', '6': '.ETH_RXN', '4': '.ETH_CT', '5': '.ETH_CT',
           '8': 'GND', '9': 'NC', '10': 'NC', '11': 'NC', '12': 'NC', 'SH': 'GND'},
          value='HR911105A', prefix='J')
    R(s, '.ETH_CT', 'ETH_AVDD', '0')
    C(s, '.ETH_CT', 'GND', '100nF')

    # quadspi flashes
    for bk, cs in (('BK1', 'QSPI_NCS'), ('BK2', 'QSPI_NCS')):
        # wson-8 so both sit flat on the bottom under the stm32 quadspi pins
        s.add('MCB:QSPI_NOR_WSON8',
              {'~{CS}': cs, 'CLK': 'QSPI_CLK', 'DI/IO0': 'QSPI_%s_IO0' % bk, 'DO/IO1': 'QSPI_%s_IO1' % bk,
               '~{WP}/IO2': 'QSPI_%s_IO2' % bk, '~{HOLD}/IO3': 'QSPI_%s_IO3' % bk, 'VCC': '+3V3', 'GND': 'GND',
               'EP': 'GND'},
              value='W25Q01JVZEIQ', props={'LCSC': 'C6926235'})
        decap(s, '+3V3', ['100nF', '1uF'])
    R(s, 'QSPI_NCS', '+3V3', '10k')

    # can-fd transceiver to backplane
    s.add('Interface_CAN_LIN:SN65HVD230', {'D': 'FDCAN1_TX', 'GND': 'GND', 'VCC': '+3V3', 'R': 'FDCAN1_RX',
                                            'Vref': 'NC', 'CANL': 'BP_CANL', 'CANH': 'BP_CANH', 'Rs': 'GND'},
          value='SN65HVD230')
    C(s, '+3V3', 'GND', '100nF')
    s.add('Jumper:SolderJumper_2_Open', {'A': 'BP_CANH', 'B': '.CAN_TERM'}, value='CAN_TERM',
          fp='Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm', prefix='JP')
    R(s, '.CAN_TERM', 'BP_CANL', '120')
    header(s, ['BP_CANH', 'BP_CANL', 'GND'], value='CAN')
    for i, n in enumerate(('VBUS_HS', 'ETH_VDDCR', 'ETH_AVDD')):
        s.pwr_flag(n, 330.2 + 12.7 * i, 12.7)
    return s
