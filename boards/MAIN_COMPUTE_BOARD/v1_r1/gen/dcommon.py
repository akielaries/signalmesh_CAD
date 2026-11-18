R0402 = 'Resistor_SMD:R_0402_1005Metric'
R0603 = 'Resistor_SMD:R_0603_1608Metric'
C0201 = 'Capacitor_SMD:C_0201_0603Metric'
C0402 = 'Capacitor_SMD:C_0402_1005Metric'
C0603 = 'Capacitor_SMD:C_0603_1608Metric'
C0805 = 'Capacitor_SMD:C_0805_2012Metric'
C1206 = 'Capacitor_SMD:C_1206_3216Metric'
C1210 = 'Capacitor_SMD:C_1210_3225Metric'
FB0603 = 'Inductor_SMD:L_0603_1608Metric'
LED0603 = 'LED_SMD:LED_0603_1608Metric'
HDR = 'Connector_PinHeader_2.54mm:PinHeader_%dx%02d_P2.54mm_Vertical'
MIPI10 = 'Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical_SMD'
OSC3225 = 'Oscillator:Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm'
XTAL3225 = 'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm'
BTN = 'Button_Switch_SMD:SW_SPST_TL3342'
TP_PAD = 'TestPoint:TestPoint_Pad_D1.5mm'
TP_LOOP = 'TestPoint:TestPoint_Keystone_5015_Micro_Mini'


def cfp(val):
    v = val.lower().replace('uf', 'u').replace('nf', 'n').replace('pf', 'p').split()[0]
    big = {'100u': C1210, '47u': C1206, '22u': C0805, '10u': C0805, '4.7u': C0603, '2.2u': C0603}
    return big.get(v, C0402)


def R(s, a, b, val, fp=R0402, **kw):
    return s.add('Device:R_Small', {'1': a, '2': b}, value=val, fp=fp, prefix='R', **kw)


def C(s, a, b, val, fp=None, **kw):
    return s.add('Device:C_Small', {'1': a, '2': b}, value=val, fp=fp or cfp(val), prefix='C', **kw)


def FB(s, a, b, val='600R@100MHz', fp=FB0603):
    return s.add('Device:FerriteBead_Small', {'1': a, '2': b}, value=val, fp=fp, prefix='FB')


def LED(s, k, a, val, fp=LED0603):
    return s.add('Device:LED_Small', {'1': k, '2': a}, value=val, fp=fp, prefix='D')


def decap(s, net, vals, gnd='GND'):
    for v in vals:
        C(s, net, gnd, v)


def led_to_gnd(s, sig, color, res='1k'):
    # gpio drives high to light
    a = '.' + sig + '_LED'
    R(s, sig, a, res)
    LED(s, 'GND', a, color)


def header(s, nets, rows=1, value=None, fp=None):
    n = len(nets)
    cols = n // rows
    if rows == 1:
        lib = 'Connector_Generic:Conn_01x%02d' % n
    else:
        lib = 'Connector_Generic:Conn_02x%02d_Odd_Even' % cols
    m = {str(i + 1): v for i, v in enumerate(nets)}
    return s.add(lib, m, value=value or lib.split(':')[1], fp=fp or HDR % (rows, cols), prefix='J')


def tp(s, net, label, fp=TP_PAD):
    # value carries the silk label, e.g. 'TP 1V0'
    return s.add('Connector:TestPoint', {'1': net}, value='TP ' + label, fp=fp, prefix='TP')


def button(s, a, b, val='SW'):
    return s.add('Switch:SW_Push', {'1': a, '2': b}, value=val, fp=BTN, prefix='SW')
