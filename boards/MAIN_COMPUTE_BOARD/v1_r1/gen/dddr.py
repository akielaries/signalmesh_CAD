from dcommon import C, R, decap, tp


def build(d):
    s = d.sheet('DDR3', 'DDR3L x16 4Gb (MT41K256M16TW), VTT termination', width=520)
    s.note('Fitted by default. To build without DDR, mark U/termination/TPS51200 and the 1V35 rail parts DNP')
    s.note('Single device, fly-by addr/cmd terminated to VTT (39.2R), CK 100R differential. ZQ 240R 1%')
    nets = {'V_{DDQ}': '+1V35', 'V_{DD}': '+1V35', 'V_{SS}': 'GND', 'V_{SSQ}': 'GND',
            'V_{REFDQ}': 'VREF_DDR', 'V_{REFCA}': 'VREF_DDR', 'ZQ': '.DDR_ZQ',
            'LDQS': 'DDR_DQS0_P', '~{LDQS}': 'DDR_DQS0_N', 'UDQS': 'DDR_DQS1_P', '~{UDQS}': 'DDR_DQS1_N',
            'LDM': 'DDR_DM0', 'UDM': 'DDR_DM1', 'CK': 'DDR_CK_P', '~{CK}': 'DDR_CK_N', 'CKE': 'DDR_CKE',
            'ODT': 'DDR_ODT', '~{RAS}': 'DDR_RAS_N', '~{CAS}': 'DDR_CAS_N', '~{WE}': 'DDR_WE_N',
            '~{CS}': 'GND', '~{RESET}': 'DDR_RESET_N', 'BA0': 'DDR_BA0', 'BA1': 'DDR_BA1', 'BA2': 'DDR_BA2',
            'A10/AP': 'DDR_A10', 'A12/~{BC}': 'DDR_A12'}
    for i in range(16):
        nets['DQ%d' % i] = 'DDR_DQ%d' % i
    for i in range(15):
        if i not in (10, 12):
            nets['A%d' % i] = 'DDR_A%d' % i
    s.add('Memory_RAM:MT41K256M16TW', nets, value='MT41K256M16TW-107', by='name')
    R(s, '.DDR_ZQ', 'GND', '240 1%')
    decap(s, '+1V35', ['10uF', '10uF'] + ['100nF'] * 10)
    R(s, 'DDR_RESET_N', 'GND', '10k')
    R(s, 'DDR_CK_P', 'DDR_CK_N', '100 1%')
    term = ['DDR_A%d' % i for i in range(15)] + ['DDR_BA0', 'DDR_BA1', 'DDR_BA2', 'DDR_RAS_N', 'DDR_CAS_N',
                                                 'DDR_WE_N', 'DDR_CKE', 'DDR_ODT']
    for n in term:
        R(s, n, 'VTT_DDR', '39.2 1%')
    decap(s, 'VTT_DDR', ['10uF', '10uF'] + ['100nF'] * 6)
    s.add('Regulator_Linear:TPS51200DRC',
          {'REFIN': '.VTT_REFIN', 'VLDOIN': '+1V35', 'VO': 'VTT_DDR', 'GND': 'GND', 'VOSNS': 'VTT_DDR',
           'REFOUT': 'VREF_DDR', 'EN': '+3V3', 'PGOOD': 'NC', 'VIN': '+3V3'}, value='TPS51200DRC')
    R(s, '+1V35', '.VTT_REFIN', '10k 1%')
    R(s, '.VTT_REFIN', 'GND', '10k 1%')
    C(s, '.VTT_REFIN', 'GND', '100nF')
    decap(s, '+3V3', ['1uF'])
    decap(s, 'VREF_DDR', ['100nF', '100nF'])
    tp(s, 'VTT_DDR', 'VTT')
    tp(s, 'VREF_DDR', 'VREF')
    return s
