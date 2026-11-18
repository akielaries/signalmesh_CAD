import json
import math
import os
import re
import sys
import uuid

import pcbnew
from sx import parse, find, first

PRJ = sys.argv[1]
NET = sys.argv[2]
OUTF = sys.argv[3]
FPDIR = '/usr/share/kicad/footprints/'
MM = 1e6
X0, Y0, W, H = 50.0, 50.0, 160.0, 100.0
GUIDE = 3.0

# jlc08161h-1080: l1 | 1080 0.0764 | l2 | core 0.3 | l3 | 7628 0.2104 | l4 | core 0.3 | l5 | 7628 0.2104 | l6 | core 0.3 | l7 | 1080 0.0764 | l8
CU = [('F.Cu', 0, 'signal', 0.035), ('In1.Cu', 4, 'power', 0.0152), ('In2.Cu', 6, 'signal', 0.0152),
      ('In3.Cu', 8, 'power', 0.0152), ('In4.Cu', 10, 'power', 0.0152), ('In5.Cu', 12, 'signal', 0.0152),
      ('In6.Cu', 14, 'power', 0.0152), ('B.Cu', 2, 'signal', 0.035)]
DIEL = [('prepreg', 0.0764, 3.91, '1080'), ('core', 0.3, 4.41, 'Core'), ('prepreg', 0.2104, 4.4, '7628'),
        ('core', 0.3, 4.41, 'Core'), ('prepreg', 0.2104, 4.4, '7628'), ('core', 0.3, 4.41, 'Core'),
        ('prepreg', 0.0764, 3.91, '1080')]


def header():
    src = open('/home/akiel/trunk/pub/signalmesh_CAD/boards/APM/v7_r1/APM.kicad_pcb').read()
    tail = src[src.find('\t\t(pad_to_mask_clearance'):src.find('\t\t\t(outputdirectory')]
    lay = src[src.find('\t(layers'):src.find('\t(setup')]
    users = [l for l in lay.splitlines() if re.match(r'\s*\((\d+) "[^"]+" user', l)]
    o = ['(kicad_pcb', '\t(version 20260206)', '\t(generator "pcbnew")', '\t(generator_version "10.0")',
         '\t(general', '\t\t(thickness 1.6)', '\t\t(legacy_teardrops no)', '\t)', '\t(paper "A3")',
         '\t(title_block', '\t\t(title "MAIN_COMPUTE_BOARD")', '\t\t(rev "v1_r1")',
         '\t\t(comment 1 "stackup JLC08161H-1080 (JLC 8L 1.6mm, 1oz outer, 0.5oz inner)")', '\t)', '\t(layers']
    o += ['\t\t(%d "%s" %s)' % (i, n, t) for n, i, t, _ in CU] + users + ['\t)', '\t(setup', '\t\t(stackup']

    def L(name, body):
        return ['\t\t\t(layer "%s"' % name] + ['\t\t\t\t' + b for b in body] + ['\t\t\t)']
    o += L('F.SilkS', ['(type "Top Silk Screen")']) + L('F.Paste', ['(type "Top Solder Paste")'])
    o += L('F.Mask', ['(type "Top Solder Mask")', '(thickness 0.015)', '(epsilon_r 3.8)'])
    for k, (n, i, t, th) in enumerate(CU):
        o += L(n, ['(type "copper")', '(thickness %g)' % th])
        if k < 7:
            ty, dt, er, mat = DIEL[k]
            o += L('dielectric %d' % (k + 1), ['(type "%s")' % ty, '(thickness %g)' % dt,
                                               '(material "NP-155F %s")' % mat, '(epsilon_r %g)' % er,
                                               '(loss_tangent 0.02)'])
    o += L('B.Mask', ['(type "Bottom Solder Mask")', '(thickness 0.015)', '(epsilon_r 3.8)'])
    o += L('B.Paste', ['(type "Bottom Solder Paste")']) + L('B.SilkS', ['(type "Bottom Silk Screen")'])
    o += ['\t\t\t(copper_finish "ENIG")', '\t\t\t(dielectric_constraints yes)', '\t\t)']
    o.append(tail.rstrip('\n'))
    o += ['\t\t\t(outputdirectory "fab/")', '\t\t)', '\t)', '\t(net 0 "")']
    rr = 1.5
    k = rr * (1 - 0.7071067811865476)
    st = ['\t\t(stroke', '\t\t\t(width 0.05)', '\t\t\t(type default)', '\t\t)', '\t\t(layer "Edge.Cuts")']
    segs = [((rr, 0), (W - rr, 0)), ((W, rr), (W, H - rr)), ((W - rr, H), (rr, H)), ((0, H - rr), (0, rr))]
    arcs = [((W - rr, 0), (W - k, k), (W, rr)), ((W, H - rr), (W - k, H - k), (W - rr, H)),
            ((rr, H), (k, H - k), (0, H - rr)), ((0, rr), (k, k), (rr, 0))]
    for a, b in segs:
        o += ['\t(gr_line', '\t\t(start %g %g)' % (a[0] + X0, a[1] + Y0), '\t\t(end %g %g)' % (b[0] + X0, b[1] + Y0)] + st + \
             ['\t\t(uuid "%s")' % uuid.uuid4(), '\t)']
    for a, m, b in arcs:
        o += ['\t(gr_arc', '\t\t(start %g %g)' % (a[0] + X0, a[1] + Y0), '\t\t(mid %.4f %.4f)' % (m[0] + X0, m[1] + Y0),
              '\t\t(end %g %g)' % (b[0] + X0, b[1] + Y0)] + st + ['\t\t(uuid "%s")' % uuid.uuid4(), '\t)']
    o += ['\t(embedded_fonts no)', ')']
    open(OUTF, 'w').write('\n'.join(o) + '\n')


def L(v):
    return [v[i] for i in range(v.size())]


header()
b = pcbnew.LoadBoard(OUTF)

# netlist
root = parse(open(NET).read())
comps = []
for c in find(first(root, 'components'), 'comp'):
    props = {first(p, 'name')[1]: (first(p, 'value') or [0, ''])[1] for p in find(c, 'property')}
    sp = first(c, 'sheetpath')
    flds = {}
    for f in find(first(c, 'fields') or [], 'field'):
        nm = first(f, 'name')[1]
        vals = [x for x in f[1:] if not isinstance(x, list)]
        flds[nm] = vals[0] if vals else ''
    comps.append(dict(flds=flds, ref=first(c, 'ref')[1], value=first(c, 'value')[1],
                      fp=(first(c, 'footprint') or [0, ''])[1], props=props,
                      sheet=first(sp, 'names')[1].strip('/'), spath=first(sp, 'tstamps')[1],
                      ts=first(c, 'tstamps')[1].split()[0]))
pinnet = {}
netnames = []
for n in find(first(root, 'nets'), 'net'):
    name = first(n, 'name')[1]
    netnames.append(name)
    for x in find(n, 'node'):
        pinnet[(first(x, 'ref')[1], first(x, 'pin')[1])] = name
nets = {}
for name in netnames:
    ni = pcbnew.NETINFO_ITEM(b, name)
    b.Add(ni)
    nets[name] = ni

fps = {}
for c in comps:
    lib, name = c['fp'].split(':')
    fp = pcbnew.FootprintLoad(FPDIR + lib + '.pretty', name)
    if fp is None:
        raise SystemExit('cannot load ' + c['fp'])
    fp.SetReference(c['ref'])
    fp.SetValue(c['value'])
    fp.SetFPIDAsString(c['fp'])
    fp.SetPath(pcbnew.KIID_PATH(c['spath'] + c['ts']))
    fp.SetSheetname(c['sheet'])
    fp.SetSheetfile(c['props'].get('Sheetfile', ''))
    if 'dnp' in c['props']:
        fp.SetDNP(True)
    for nm, v in c['flds'].items():
        if nm in ('Footprint', 'Reference', 'Value'):
            continue
        fp.SetField(nm, v)
    for p in L(fp.Pads()):
        nn = pinnet.get((c['ref'], p.GetNumber()))
        if nn:
            p.SetNet(nets[nn])
    b.Add(fp)
    fps[c['ref']] = (fp, c)
print('footprints', len(fps), 'nets', len(nets))

# placement helpers
occupied = {'F': [], 'B': []}


def crt(fp):
    s = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
    bb = s.BBox() if s.OutlineCount() else fp.GetBoundingBox(False)
    return (bb.GetX() / MM, bb.GetY() / MM, bb.GetRight() / MM, bb.GetBottom() / MM)


def is_tht(fp):
    return any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH for p in L(fp.Pads()))


def put(fp, x, y, rot=0, side='F'):
    if side == 'B' and not fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))


def overlaps(r, side, gap):
    for q in occupied[side]:
        if r[0] < q[2] + gap and r[2] > q[0] - gap and r[1] < q[3] + gap and r[3] > q[1] - gap:
            return True
    return False


def inside(r):
    return r[0] >= X0 + 0.3 and r[2] <= X0 + W - 0.3 and r[1] >= Y0 + GUIDE and r[3] <= Y0 + H - GUIDE


def commit(fp, side):
    r = crt(fp)
    occupied[side].append(r)
    if is_tht(fp):
        occupied['B' if side == 'F' else 'F'].append(r)


def fix(ref, x, y, rot=0, side='F'):
    fp = fps[ref][0]
    put(fp, x, y, rot, side)
    commit(fp, side)
    placed.add(ref)


LOW = re.compile(r'^(C|R|L)_(0201|0402|0603|0805)_|^SOT-23|^TSSOP|^SOT-363|^SC-70|^TestPoint_Pad_|^WSON-')


def low_profile(fp):
    # bottom side faces the next card in a subrack: keep it under about 1.5 mm
    return bool(LOW.match(str(fp.GetFPID().GetUniStringLibItemName())))


def spiral(ref, tx, ty, side='F', rots=(0, 90), gap=0.25, region=None):
    fp = fps[ref][0]
    if side == 'B' and not low_profile(fp):
        side = 'F'
    tht = is_tht(fp)
    for rad in [i * 0.5 for i in range(0, 240)]:
        n = max(1, int(2 * math.pi * rad / 0.5))
        for k in range(n):
            a = 2 * math.pi * k / n
            x, y = tx + rad * math.cos(a), ty + rad * math.sin(a)
            for rot in rots:
                put(fp, round(x * 4) / 4, round(y * 4) / 4, rot, side)
                r = crt(fp)
                if not inside(r) or overlaps(r, side, gap):
                    continue
                if tht and overlaps(r, 'B' if side == 'F' else 'F', gap):
                    continue
                if region and not (r[0] >= region[0] and r[2] <= region[2] and r[1] >= region[1] and r[3] <= region[3]):
                    continue
                if not region and fps[ref][1]['sheet'] != 'AUDIO' and side == 'F':
                    bad = False
                    for z in [AUDIO_ZONE] + CORRIDORS:
                        if r[0] < z[2] and r[2] > z[0] and r[1] < z[3] and r[3] > z[1]:
                            bad = True
                    if bad:
                        continue
                commit(fp, side)
                placed.add(ref)
                return True
    print('could not place', ref)
    return False


def byval(sub, sheet=None):
    return [r for r, (fp, c) in fps.items() if sub in c['value'] and (sheet is None or c['sheet'] == sheet)]


def one(sub, sheet=None):
    r = byval(sub, sheet)
    assert len(r) == 1, (sub, r)
    return r[0]


placed = set()

# fixed: front panel connectors (left edge), rear din, main ics
# front panel stack, top to bottom. courtyards abut; spare height goes to the tightest body gap.
# barrel jack first so its tall side-pad courtyard faces the card guide instead of a neighbour
FRONT = [(one('12V IN'), 0, 0.0), (sorted(byval('SFP cage'))[0], 0, 0.0), (sorted(byval('SFP cage'))[1], 0, 0.0),
         (one('HR911105A'), 270, 0.0), (one('USB-A HOST'), 270, 0.0), (one('USB-C HS'), 270, 0.0)]
FACE_X = 48.45  # body front face, 1.55 mm proud of the edge for the panel


def fab_bb(fp):
    xs, ys = [], []
    for g in L(fp.GraphicalItems()):
        if g.GetLayer() in (pcbnew.F_Fab, pcbnew.B_Fab):
            bb = g.GetBoundingBox()
            xs += [bb.GetX(), bb.GetRight()]
            ys += [bb.GetY(), bb.GetBottom()]
    return min(xs) / MM, min(ys) / MM, max(xs) / MM, max(ys) / MM


tot = 0.0
for ref, rot, _ in FRONT:
    fp = fps[ref][0]
    put(fp, 0, 0, rot)
    r = crt(fp)
    tot += r[3] - r[1]
slack = (H - 2 * GUIDE - 0.1) - tot
ytop = Y0 + GUIDE + 0.05
for i, (ref, rot, _) in enumerate(FRONT):
    fp = fps[ref][0]
    put(fp, 0, 0, rot)
    r = crt(fp)
    f = fab_bb(fp)
    x = FACE_X - f[0]
    y = ytop - r[1]
    fix(ref, x, y, rot)
    ytop = crt(fp)[3] + (slack if ref == one('USB-A HOST') else 0.0)
for ref, rot, _ in FRONT:
    print('front', ref, fps[ref][1]['value'][:14], 'body y %.2f..%.2f' % fab_bb(fps[ref][0])[1::2])
fix(one('DIN41612'), 197.7, 52.45 + 8.2, 270)
fix('U100', 122.0, 92.0, 0)
# dram right under bank 34 (short fly-by), between the fpga and the button row
DRAM_C = (107.6, 116.5)
fix(one('MT41K256M16TW'), DRAM_C[0], DRAM_C[1], 90)
fix(one('STM32H755BIT6'), 165.0, 99.0, 0)
VITA_C = (150.0, 69.5)
fix(one('VITA57.1'), VITA_C[0], VITA_C[1], 0)
# module standoffs relative to the connector centre (pin 1 at -x, row a at -y): 2.0 mm toward
# the module at +-31.5 mm
for r, (dx, dy) in zip(sorted(byval('M2.5 VITA')), ((-31.5, 2.0), (31.5, 2.0))):
    fix(r, VITA_C[0] + dx, VITA_C[1] + dy)
fix(one('MCU_BREAKOUT'), 186.6, 73.9, 0)

# hand layout: mirrored l/r audio chain (dac top, opamp centre a=left b=right, outputs bottom)
AUDIO_FIX = {
    'U11': ('CS4344', 175.0, 126.0, 0), 'U12': ('OPA1656ID', 175.0, 135.5, 0), 'U14': ('LM2662M', 186.5, 127.5, 0),
    'R57': ('22', 170.6, 124.5, 90), 'R56': ('22', 169.6, 125.5, 90), 'R55': ('22', 170.6, 126.5, 90), 'R54': ('22', 169.6, 127.5, 90),
    'C26': ('10uF', 171.0, 129.6, 0), 'C29': ('10uF', 179.4, 123.6, 0), 'C28': ('0.1uF', 179.4, 125.3, 0),
    'C32': ('10uF', 179.4, 127.6, 0), 'C33': ('0.1uF', 179.4, 129.3, 0),
    'R59': ('560', 168.4, 131.4, 0), 'C31': ('2.7nF', 165.9, 133.0, 90), 'C35': ('10uF', 168.2, 133.6, 0), 'R52': ('47k', 168.4, 135.6, 0),
    'R58': ('560', 181.6, 131.4, 0), 'C30': ('2.7nF', 184.5, 133.0, 90), 'C34': ('10uF', 182.2, 133.6, 0), 'R51': ('47k', 181.6, 135.6, 0),
    'R62': ('1k', 170.4, 138.4, 0), 'R65': ('2k', 168.4, 138.4, 0), 'R63': ('1k', 179.6, 138.4, 0), 'R64': ('2k', 181.6, 138.4, 0),
    'C44': ('10uF', 175.0, 139.8, 0), 'C45': ('0.1uF', 175.0, 141.4, 0), 'C42': ('10uF', 179.25, 133.2, 90), 'C43': ('0.1uF', 178.6, 130.6, 0),
    'C38': ('10uF', 171.0, 140.4, 0), 'R61': ('100', 171.4, 142.4, 0), 'C47': ('47pF', 166.4, 141.0, 90), 'J13': ('ACM_DAC_L', 168.8, 143.3, 0),
    'C39': ('10uF', 179.0, 140.4, 0), 'R60': ('100', 178.6, 142.4, 0), 'C41': ('47pF', 183.6, 141.0, 90), 'J9': ('ACM_DAC_R', 181.2, 143.3, 0),
    'C46': ('10uF', 186.5, 131.8, 0), 'C37': ('100uF', 186.5, 134.4, 0),
    'J11': ('DAC_L_PRB', 163.4, 126.0, 0), 'TP1': ('DAC_L', 163.4, 129.2, 0),
}
# keys are the apm v7 refs; build.py writes the apm -> current ref map
AUDIO_MAP = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'audio_refmap.json')))
for apm, (val, x, y, rot) in AUDIO_FIX.items():
    ref = AUDIO_MAP[apm]
    assert fps[ref][1]['value'] == val, (apm, ref, fps[ref][1]['value'], val)
    fix(ref, x, y, rot)

# user leds in a row just above the buttons
for (v, sh), xs in ((('GREEN', 'FPGA_IO'), (119.0, 122.0, 125.0, 128.0)), (('GREEN', 'STM32'), (150.0,)),
                    (('BLUE', 'STM32'), (153.0,))):
    for r_, x in zip(sorted([r for r, (f, c) in fps.items() if c['value'] == v and c['sheet'] == sh],
                            key=lambda r: int(re.sub(r'\D', '', r))), xs):
        fix(r_, x, 116.4, 0)

# one labelled button row below the fpga/stm32
BTN_ROW = [('FPGA_PROG', 'PROG'), ('FPGA_BTN0', 'BTN0'), ('FPGA_BTN1', 'BTN1'), ('MCU_RESET', 'RESET'), ('MCU_USER', 'USER')]
LABELS = []
for (val, lab), x in zip(BTN_ROW, (120.0, 129.5, 139.0, 148.0, 157.0)):
    fix(one(val), x, 120.5, 0)
    LABELS.append((lab, x, 124.6))
LABELS += [('L OUT', 167.4, 141.9 - 4.5), ('R OUT', 182.6, 141.9 - 4.5)]
LABELS = [l for l in LABELS if not l[0].endswith('OUT')] + [('L', 166.0, 144.4), ('R', 184.0, 144.4), ('DAC1', 160.0, 125.0)]

pm = byval('PMOD')
fix(sorted(pm)[0], 112.5, 142.0, 90)
fix(sorted(pm)[1], 129.5, 142.0, 90)
# header field along the bottom edge, three aligned rows, pin 1 at the left of every header.
# rows b and c sit below the mezzanine footprint (y > 131.9) so debug stays reachable with a card
# fitted; row a holds the dupont duplicates and boot0 under the mezzanine edge
HDR_FIX = {
    # row a
    'FPGA_JTAG 6p': (117.0, 128.4, 90), 'MCU_SWD': (134.0, 128.4, 90), 'BOOT0': (151.0, 128.4, 90),
    # row b
    'FPGA_JTAG Xilinx': (112.1, 135.9, 90), 'MCU_UART FTDI': (128.4, 134.3, 90),
    'SOFTCORE_UART FTDI': (145.7, 134.3, 90),
    # row c: pmods (above), then both mipi-10s side by side, same orientation
    'MCU_SWD MIPI-10': (148.75, 142.55, 90), 'SOFTCORE_SWD MIPI-10': (157.25, 142.55, 90),
}
for v, (x, y, rot) in HDR_FIX.items():
    fix([r for r, (f, c) in fps.items() if c['value'] == v][0], x, y, rot)

# ddr3 fly-by termination: two rows of 0402s just past the dram, signal pads on the outside,
# vtt pads facing a vtt strip between the rows (planes.py pours it). columns follow the dram
# ball x order so the in5 fan from the balls does not cross itself
TERM_X0, TERM_DX, TERM_Y = 101.0, 1.2, (DRAM_C[1] + 6.1, DRAM_C[1] + 8.7)
u21 = fps[one('MT41K256M16TW')][0]
ballx = {p.GetNetname(): (p.GetPosition().x / MM, p.GetPosition().y / MM) for p in L(u21.Pads())}
terms = [r for r, (f, c) in fps.items() if c['value'].startswith('39.2')]
sig = {}
for r in terms:
    for p in L(fps[r][0].Pads()):
        if p.GetNetname() != 'VTT_DDR':
            sig[r] = p.GetNetname()
terms.sort(key=lambda r: (ballx[sig[r]][0], ballx[sig[r]][1]))
for k, r in enumerate(terms):
    col, row = k // 2, k % 2
    # rot 270 puts pad 1 (the ddr net) above centre, rot 90 below
    fix(r, TERM_X0 + col * TERM_DX, TERM_Y[row], 270 if row == 0 else 90)
    pad1 = [p for p in L(fps[r][0].Pads()) if p.GetNumber() == '1'][0]
    assert (pad1.GetPosition().y / MM < TERM_Y[row]) == (row == 0), (r, 'pad orientation')

# vtt decoupling on the bottom right under the strip (planes.py pours vtt on b.cu there too),
# vtt pad toward the strip
vtt_caps = [r for r, (f, c) in fps.items() if c['sheet'] == 'DDR3' and r.startswith('C')
            and any(p.GetNetname() == 'VTT_DDR' for p in L(f.Pads()))]
vtt_caps.sort(key=lambda r: (fps[r][1]['value'] != '10uF', int(re.sub(r'\D', '', r))))
cur = 98.6
for r in vtt_caps:
    fp = fps[r][0]
    big = fps[r][1]['value'] == '10uF'
    wcap = 1.7 if big else 0.94
    for rot in (90, 270):
        put(fp, cur + wcap / 2, TERM_Y[1] + 1.4, rot, 'B')
        pv = [p for p in L(fp.Pads()) if p.GetNetname() == 'VTT_DDR'][0]
        pg = [p for p in L(fp.Pads()) if p.GetNetname() != 'VTT_DDR'][0]
        if pv.GetPosition().y < pg.GetPosition().y:
            break
    fix(r, cur + wcap / 2, TERM_Y[1] + 1.4, rot, 'B')
    cur += wcap + 0.15

# ck 100 r differential termination at the dram, bottom side, in the gap between the ball groups
ckt = [r for r, (f, c) in fps.items() if {p.GetNetname() for p in L(f.Pads())} == {'DDR_CK_P', 'DDR_CK_N'}][0]
fix(ckt, DRAM_C[0] + 0.8, DRAM_C[1], 0, 'B')

HZ = (90,)
ANCHOR_T = {
    'USB3300': (76, 140), 'LAN8742A': (80, 109), 'TPS2051C': (74, 127), 'USBLC6-2SC6': None,
    # flat wson flashes on the bottom inside the stm32 outline, between its quadspi pins
    'W25Q01JVZEIQ': (160, 104, (0, 90), 'B'), 'SN65HVD230': (176, 73),
    'TCA9535': (176, 100, (0, 90), 'B'), '24AA025E48': (172, 80, (0, 90), 'F'),
    'IOX_SPARE': (156, 141, HZ, 'F'), 'CAN': (170, 79),
    
    '100MHz': (133, 108), '24.576MHz': (137, 108), '22.5792MHz': (141, 108), '125MHz LVDS': (106, 90),
    'TPS62130RGT': (92, 112), 'LMR33630ADDA': (85, 133), 'TLV62568DBV': (100, 108), 'TLV75801': (104, 101),
    'TPS51200DRC': (97.6, 123.9, (0, 90), 'F'),  # vtt source at the end of the termination strip 'INA219': (80, 58), 'DMP3013SFV': (70, 58), '25MHz 8pF': (150, 85),
    '32.768kHz': (150, 90), '24MHz 12pF': (80, 136), '25MHz 10pF': (84, 112),
    'M3': None, 'M2.5 VITA': None, 'MCU_BREAKOUT': None,
    '1.1A hold': (167, 70),  # vita 12P0V polyfuse next to the connector
}
AUDIO_ZONE = (162, 123.0, 191.0, 147)
# routing channels kept free on the top side: gtp to sfp, fmc to stm32, vita la to fpga
CORRIDORS = [(98.6, 60, 112, 100), (134.6, 79, 147.5, 116.5), (109, 76.8, 152, 79.4),
             (115.5, 123.5, 165.0, 125.7),  # label strip under the button row
             (117.0, 115.2, 156.0, 117.4),  # led row
             (110.0, 126.0, 162.0, 147.0),  # header field: headers and their labels only
             (100.0, 104.8, 121.0, 111.3)]  # ddr3 top-layer gap between fpga and dram
POWER_ZONE = (67, 105, 106, 147)

# mounting holes
holes = byval('M3')
for r, (x, y) in zip(sorted(holes), ((187.8, 143.3), (61.0, 143.5), (67.5, 57.0), (187.8, 57.0))):
    fix(r, x, y)

# remaining anchors (multi-pin parts)
for ref, (fp, c) in sorted(fps.items(), key=lambda kv: (kv[1][1]['sheet'] != 'AUDIO', -kv[1][0].GetPadCount())):
    if ref in placed or fp.GetPadCount() <= 3 and not ref.startswith('U') and '1.1A hold' not in c['value']:
        continue
    tgt = None
    for k, v in ANCHOR_T.items():
        if k in c['value']:
            tgt = v
            break
    # bucks feeding the vita site sit on the bottom side under the connector, next to its power pins
    pnets = {p.GetNetname() for p in L(fp.Pads())}
    if 'VADJ' in pnets and 'TPS62130' in c['value']:
        tgt = (106, 64, (0, 90), 'F')
    if any('3V3M' in n for n in pnets) and 'TPS62130' in c['value']:
        tgt = (186, 62, (0, 90), 'F')
    if tgt is None:
        if c['sheet'] == 'AUDIO':
            tgt = ((AUDIO_ZONE[0] + AUDIO_ZONE[2]) / 2, (AUDIO_ZONE[1] + AUDIO_ZONE[3]) / 2)
        elif c['sheet'] == 'POWER':
            tgt = (88, 128)
        else:
            continue
    rots, sd = (tgt[2], tgt[3]) if len(tgt) > 2 else ((0, 90), 'F')
    spiral(ref, tgt[0], tgt[1], side=sd, rots=rots, gap=0.6 if c['value'].startswith(('MCU_', 'FPGA_', 'SOFT', 'BOOT', 'IOX', 'CAN')) else 0.25,
           region=AUDIO_ZONE if c['sheet'] == 'AUDIO' else None)

# satellites: near the placed part pad sharing a non-ground net
padpos = {}
for ref in list(placed):
    fp = fps[ref][0]
    for p in L(fp.Pads()):
        nn = p.GetNetname()
        if nn and nn != 'GND':
            padpos.setdefault(nn, []).append((ref, p.GetPosition().x / MM, p.GetPosition().y / MM, fp.GetPadCount()))

todo = [r for r in fps if r not in placed]
# larger parts first
# test points go last so they never take a decoupling spot next to a pin
todo.sort(key=lambda r: (r.startswith('TP'), fps[r][1]['sheet'] != 'AUDIO',
                         -(crt(fps[r][0])[2] - crt(fps[r][0])[0]) * (crt(fps[r][0])[3] - crt(fps[r][0])[1])))
# scope ground loops on top: power corner, debug headers, stm32 side, audio corner
GND_TP = [((79, 118), None), ((150, 140), None), ((183, 112), None), ((178, 134), AUDIO_ZONE)]
for ref in todo:
    fp, c = fps[ref]
    if ref.startswith('TP') and c['value'] == 'TP GND':
        (gx, gy), reg = GND_TP.pop(0)
        spiral(ref, gx, gy, side='F', gap=0.5, region=reg)
        continue
    cands = []
    for p in L(fp.Pads()):
        nn = p.GetNetname()
        for (r2, x, y, npads) in padpos.get(nn, []):
            if fps[r2][1]['sheet'] == c['sheet'] or npads < 300:
                cands.append((npads, x, y, r2, nn))
    if not cands:
        tgt = (88, 128)
        side = 'F'
    else:
        # prefer the pad of the biggest anchor in the same sheet on a local/signal net
        cands.sort(key=lambda t: (fps[t[3]][1]['sheet'] != c['sheet'], -t[0]))
        _, x, y, r2, nn = cands[0]
        tgt = (x, y)
        side = 'B' if (r2 in ('U100', 'U11') and ref.startswith('C')) or fps[r2][0].IsFlipped() else 'F'
    region = AUDIO_ZONE if c['sheet'] == 'AUDIO' else None
    if ref.startswith('TP') and c['value'].startswith('TP '):
        # flat pads under their source on the bottom, spaced for a silk label, clear of the
        # fpga ball field where escape and gtp routing use the bottom layer
        bx0, by0, bx1, by1 = 107.0, 77.0, 137.0, 107.0
        tx, ty = tgt
        if bx0 < tx < bx1 and by0 < ty < by1:
            dl, dr, dt, db = tx - bx0, bx1 - tx, ty - by0, by1 - ty
            m = min(dl, dr, dt, db)
            tx, ty = (bx0 - 1, ty) if m == dl else (bx1 + 1, ty) if m == dr else (tx, by0 - 1) if m == dt else (tx, by1 + 1)
        spiral(ref, tx, ty, side='B', rots=(0,), gap=1.4)
        r = crt(fp)
        if r[0] < bx1 and r[2] > bx0 and r[1] < by1 and r[3] > by0:
            print('test point in bga zone', ref)
        continue
    if not spiral(ref, tgt[0], tgt[1], side=side, region=region):
        if c['sheet'] == 'AUDIO':
            spiral(ref, 175, 120, side=side, region=(150, 112, 191, 147.5))
        else:
            spiral(ref, tgt[0], tgt[1], side=side)
    for p in L(fp.Pads()):
        nn = p.GetNetname()
        if nn and nn != 'GND' and len(padpos.get(nn, [])) < 3:
            padpos.setdefault(nn, []).append((ref, p.GetPosition().x / MM, p.GetPosition().y / MM, fp.GetPadCount()))

print('placed', len(placed), 'of', len(fps))


# silkscreen: only reference text, small; passive refs moved to fab
M3D = '${KICAD10_3DMODEL_DIR}/'
SUB3D = {
    'Xilinx_FGG484': 'Package_BGA.3dshapes/BGA-484_23.0x23.0mm_Layout22x22_P1.0mm.step',
    'Samtec_FMC_ASP-134486-01_10x40_P1.27mm_Vertical': 'Connector_Samtec.3dshapes/Samtec_FMC_ASP-134602-01_10x40_P1.27mm_Vertical.step',
    'Texas_HSOP-8-1EP_3.9x4.9mm_P1.27mm_ThermalVias': 'Package_SO.3dshapes/HTSOP-8-1EP_3.9x4.9mm_P1.27mm.step',
    'VQFN-16-1EP_3x3mm_P0.5mm_EP1.68x1.68mm_ThermalVias': 'Package_DFN_QFN.3dshapes/QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm.step',
    'VQFN-24-1EP_4x4mm_P0.5mm_EP2.5x2.5mm_ThermalVias': 'Package_DFN_QFN.3dshapes/HVQFN-24-1EP_4x4mm_P0.5mm_EP2.1x2.1mm.step',
    'USB_C_Receptacle_HRO_TYPE-C-31-M-12': 'Connector_USB.3dshapes/USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal.step',
    'Oscillator_SMD_Abracon_ASE-4Pin_3.2x2.5mm': 'Crystal.3dshapes/Crystal_SMD_3225-4Pin_3.2x2.5mm.step',
    'Oscillator_SMD_SiTime_PQFD-6L_3.2x2.5mm': 'Crystal.3dshapes/Crystal_SMD_3225-4Pin_3.2x2.5mm.step',
    'Fuse_1812_4532Metric': 'Resistor_SMD.3dshapes/R_1812_4532Metric.step',
    'R_Shunt_Vishay_WSK2512_6332Metric_T1.19mm': 'Resistor_SMD.3dshapes/R_2512_6332Metric.step',
}
SILK_PREFIX = ('U', 'J', 'SW', 'Y', 'X', 'Q', 'H', 'TP', 'JP', 'F', 'D', 'L')
# lcsc/easyeda models in the project, aligned by matching pad positions to the kicad footprints
# (name, offset in footprint coords x, y, rotation z)
PRJ3D = {
    'Micron_FBGA-96_8x14mm_Layout9x16_P0.8mm': [('FBGA-96_L14.0-W8.0-H1.1-P0.8.step', 0.0, 0.0, 0)],
    'RJ45_Hanrun_HR911105A_Horizontal': [('RJ45-TH_HR911105A.step', 4.45, 4.35, 0)],
    'Connector_SFP_and_Cage': [('SPF-SMD_744410001-1.step', -6.2, 0.0, -90), ('CONN-TH_HCSFP01.step', -18.55, 0.0, 0, 27.9)],
    # kicad ships no 8x6 wson model; lcsc C6926235, same pad frame as the kicad footprint
    'WSON-8-1EP_8x6mm_P1.27mm_EP3.4x4.3mm': [('WSON-8_L8.0-W6.0-P1.27-TL-EP-1.step', 0.0, 0.0, 0)],
}


def set_models(fp, specs):
    ms = fp.Models()
    while ms.size():
        ms.pop_back()
    for spec in specs:
        name, ox, oy, rz = spec[:4]
        oz = spec[4] if len(spec) > 4 else 0.0
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = '${KIPRJMOD}/3dmodels/' + name
        m.m_Offset = pcbnew.VECTOR3D(ox, -oy, oz)
        m.m_Rotation = pcbnew.VECTOR3D(0, 0, rz)
        m.m_Scale = pcbnew.VECTOR3D(1, 1, 1)
        m.m_Show = True
        ms.push_back(m)


for ref, (fp, c) in fps.items():
    item = str(fp.GetFPID().GetUniStringLibItemName())
    if item in PRJ3D:
        set_models(fp, PRJ3D[item])
    if item in SUB3D:
        ms = fp.Models()
        if ms.size():
            ms[0].m_Filename = M3D + SUB3D[item]
            if item.startswith('Samtec_FMC'):
                ms[0].m_Rotation = pcbnew.VECTOR3D(0, 0, 90)
    flds = fp.GetFields()
    for i in range(len(flds)):
        f = flds[i]
        if f.GetName() != 'Reference':
            f.SetVisible(False)
    rf = fp.Reference()
    pre = re.match(r'[A-Z]+', ref).group(0)
    small = fp.GetPadCount() <= 3 and pre in ('R', 'C', 'FB', 'D', 'L', 'Q', 'TP', 'JP', 'F')
    if small and pre in ('R', 'C', 'FB'):
        rf.SetLayer(pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab)
    rf.SetTextSize(pcbnew.VECTOR2I(int(0.8 * MM), int(0.8 * MM)))
    rf.SetTextThickness(int(0.15 * MM))

# card guide keepouts along the long edges (eurocard)
for y0 in (Y0, Y0 + H - GUIDE):
    z = pcbnew.ZONE(b)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowFootprints(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowPads(True)
    z.SetDoNotAllowZoneFills(False)
    ls = pcbnew.LSET()
    for n, i, t, th in CU:
        ls.AddLayer(b.GetLayerID(n))
    z.SetLayerSet(ls)
    z.SetZoneName('CARD_GUIDE')
    o = z.Outline()
    o.NewOutline()
    for x, y in ((X0, y0), (190.8, y0), (190.8, y0 + GUIDE), (X0, y0 + GUIDE)):
        o.Append(int(x * MM), int(y * MM))
    b.Add(z)
import silkplace  # noqa: E402
import labels  # noqa: E402
byvalue = {}
for r_, (f_, c_) in fps.items():
    byvalue.setdefault(c_['value'], r_)
NAMED = labels.build(byvalue, [(AUDIO_MAP['J13'], 'L'), (AUDIO_MAP['J9'], 'R'), (AUDIO_MAP['J11'], 'DAC1')])
NAMED += [(r_, 'GND') for r_, (f_, c_) in fps.items() if c_['value'] == 'TP GND']
st = silkplace.place_refs(b, X0, Y0, X0 + W, Y0 + H, labels=NAMED)
print('ref labels', st)
b.Save(OUTF)
