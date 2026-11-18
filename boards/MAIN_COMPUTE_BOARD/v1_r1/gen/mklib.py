from sx import Q, dump

F = ['effects', ['font', ['size', 1.27, 1.27]]]


def prop(k, v, x, y, hide=False):
    p = ['property', Q(k), Q(v), ['at', x, y, 0]]
    if hide:
        p.append(['hide', 'yes'])
    return p + [F]


def symbol(name, ref, fp, left, right, top=(), bottom=(), desc=''):
    # pins: (num, name, type)
    rows = max(len(left), len(right))
    h = (rows + 1) * 2.54
    w = 12.7
    pins = []
    y0 = h / 2 - 2.54

    def pin(num, nm, ty, x, y, ang):
        pins.append(['pin', ty, 'line', ['at', x, y, ang], ['length', 2.54],
                     ['name', Q(nm), F], ['number', Q(num), F]])

    for i, (n, nm, ty) in enumerate(left):
        pin(n, nm, ty, -w - 2.54, round(y0 - i * 2.54, 2), 0)
    for i, (n, nm, ty) in enumerate(right):
        pin(n, nm, ty, w + 2.54, round(y0 - i * 2.54, 2), 180)
    for i, (n, nm, ty) in enumerate(top):
        pin(n, nm, ty, round(-2.54 * (len(top) - 1) / 2 + i * 2.54, 2), h / 2 + 2.54 + 2.54, 270)
    for i, (n, nm, ty) in enumerate(bottom):
        pin(n, nm, ty, round(-2.54 * (len(bottom) - 1) / 2 + i * 2.54, 2), -h / 2 - 2.54 - 2.54, 90)
    ht = h / 2 + 2.54
    return ['symbol', Q(name), ['exclude_from_sim', 'no'], ['in_bom', 'yes'], ['on_board', 'yes'],
            prop('Reference', ref, 0, ht + 1.27), prop('Value', name, 0, -ht - 1.27),
            prop('Footprint', fp, 0, -ht - 3.81, True), prop('Datasheet', '', 0, 0, True),
            prop('Description', desc, 0, 0, True),
            ['symbol', Q(name + '_0_1'),
             ['rectangle', ['start', -w, ht], ['end', w, -ht], ['stroke', ['width', 0.254], ['type', 'default']],
              ['fill', ['type', 'background']]]],
            ['symbol', Q(name + '_1_1')] + pins]


def build(path):
    syms = []
    syms.append(symbol(
        'QSPI_NOR_SOIC16W', 'U', 'Package_SO:SOIC-16W_7.5x10.3mm_P1.27mm',
        left=[('7', '~{CS}', 'input'), ('16', 'SCLK', 'input'), ('3', '~{RESET}', 'input')],
        right=[('15', 'SI/SIO0', 'bidirectional'), ('8', 'SO/SIO1', 'bidirectional'),
               ('9', '~{WP}/SIO2', 'bidirectional'), ('1', '~{HOLD}/SIO3', 'bidirectional')],
        top=[('2', 'VCC', 'power_in')],
        bottom=[('10', 'GND', 'power_in'), ('4', 'NC', 'no_connect'), ('5', 'NC', 'no_connect'),
                ('6', 'NC', 'no_connect'), ('11', 'NC', 'no_connect'), ('12', 'NC', 'no_connect'),
                ('13', 'NC', 'no_connect'), ('14', 'NC', 'no_connect')],
        desc='1Gb 3V quad SPI NOR, 16-SOIC 300mil (W25Q01JVSFIQ / MX66L1G45GMI pinout)'))
    # winbond 8-pad wson 8x6; exposed pad may float or go to gnd (tied to gnd here)
    syms.append(symbol(
        'QSPI_NOR_WSON8', 'U', 'Package_SON:WSON-8-1EP_8x6mm_P1.27mm_EP3.4x4.3mm',
        left=[('1', '~{CS}', 'input'), ('6', 'CLK', 'input')],
        right=[('5', 'DI/IO0', 'bidirectional'), ('2', 'DO/IO1', 'bidirectional'),
               ('3', '~{WP}/IO2', 'bidirectional'), ('7', '~{HOLD}/IO3', 'bidirectional')],
        top=[('8', 'VCC', 'power_in')],
        bottom=[('4', 'GND', 'power_in'), ('9', 'EP', 'passive')],
        desc='1Gb 3V quad SPI NOR, WSON-8 8x6 (W25Q01JVZEIQ)'))
    lib = ['kicad_symbol_lib', ['version', 20251024], ['generator', Q('kicad_symbol_editor')],
           ['generator_version', Q('10.0')]] + syms
    open(path, 'w').write(dump(lib) + '\n')
