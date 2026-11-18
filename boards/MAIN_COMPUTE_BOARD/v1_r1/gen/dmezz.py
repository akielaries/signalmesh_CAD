import os

from dcommon import C, R, decap

HERE = os.path.dirname(os.path.abspath(__file__))


def vita_map():
    m = {}
    for line in open(os.path.join(HERE, 'vita57_hpc.txt')):
        if line.strip():
            pin, sig = line.split()
            m[pin] = sig
    return m


def build(d):
    s = d.sheet('MEZZ', 'VITA 57.1 HPC mezzanine site + DIN 41612 backplane (provisional)', width=760)
    s.note('VITA 57.1 HPC connector, LPC-compatible. Routed: LA00-LA33, CLK0/1_M2C, GBTCLK0_M2C, DP0-DP1, I2C, PG/PRSNT')
    s.note('VADJ set by STM32 after reading mezzanine EEPROM (I2C1 0x50, GA=00). HA/HB/DP2-9 not connected')
    s.note('DIN 41612 3x32 backplane pinout is PROVISIONAL (12V in/out shared with barrel jack, TDM audio bus, CAN). Use one 12V source at a time')
    s.note('DIN a28/c28 = -12V and a30/c30 = +5V are reserved for other cards and left unconnected here (do not back-feed this board)')
    vm = vita_map()
    nets = {}
    for pin, sig in vm.items():
        if sig == 'GND':
            n = 'GND'
        elif sig.startswith('LA') or sig.startswith('CLK0_M2C') or sig.startswith('CLK1_M2C') \
                or sig.startswith('GBTCLK0_M2C') or sig[:3] in ('DP0', 'DP1'):
            n = 'MEZZ_' + sig.replace('_P_CC', '_CC_P').replace('_N_CC', '_CC_N')
        elif sig == 'SCL':
            n = 'I2C1_SCL'
        elif sig == 'SDA':
            n = 'I2C1_SDA'
        elif sig in ('GA0', 'GA1'):
            n = 'GND'
        elif sig == 'PG_C2M':
            n = 'MEZZ_PG_C2M'
        elif sig == 'PG_M2C':
            n = 'MEZZ_PG_M2C'
        elif sig == 'PRSNT_M2C_L':
            n = 'MEZZ_PRSNT_L'
        elif sig == '12P0V':
            n = '+12V_MEZZ'
        elif sig == '3P3V':
            n = '+3V3_MEZZ'
        elif sig == '3P3VAUX':
            n = '+3V3'
        elif sig == 'VADJ':
            n = 'VADJ'
        else:
            n = 'NC'
        nets[pin] = n
    s.add('Connector:Samtec_ASP-134486-01', nets, value='VITA57.1 HPC ASP-134486-01',
          fp='Connector_Samtec:Samtec_FMC_ASP-134486-01_10x40_P1.27mm_Vertical', prefix='J')
    R(s, 'MEZZ_PRSNT_L', '+3V3', '10k')
    R(s, 'MEZZ_PG_M2C', '+3V3', '10k')
    R(s, 'MEZZ_PG_C2M', 'GND', '100k')
    decap(s, '+3V3_MEZZ', ['47uF', '10uF', '100nF', '100nF'])
    decap(s, 'VADJ', ['47uF', '10uF', '100nF', '100nF'])
    decap(s, '+12V_MEZZ', ['10uF 25V', '100nF 25V'])

    # backplane, provisional
    bp = {}
    for r in 'abc':
        for i in range(1, 33):
            bp['%s%d' % (r, i)] = 'NC'
    for r in 'abc':
        for i in (1, 2):
            bp['%s%d' % (r, i)] = '+12V_JACK'
        for i in (3, 32):
            bp['%s%d' % (r, i)] = 'GND'
    for i in range(4, 32, 2):
        bp['b%d' % i] = 'GND'
    bp.update({'a5': 'BP_TDM_MCLK', 'a7': 'BP_TDM_BCLK', 'a9': 'BP_TDM_FS', 'a11': 'BP_TDM_DOUT',
               'a13': 'BP_TDM_DIN', 'c5': 'BP_CANH', 'c6': 'BP_CANL'})
    s.add('Connector:DIN41612_03x32_C_Split', bp, value='DIN41612 C 3x32 BACKPLANE',
          fp='Connector_DIN:DIN41612_C_3x32_Male_Horizontal_THT', prefix='J')
    # vita 57.1 module standoffs at the connector ends (m2.5, 10 mm spacers); also hold the card down
    for _ in range(2):
        s.add('Mechanical:MountingHole_Pad', {'1': 'GND'}, value='M2.5 VITA',
              fp='MountingHole:MountingHole_2.7mm_M2.5_Pad_Via', prefix='H')
    return s
