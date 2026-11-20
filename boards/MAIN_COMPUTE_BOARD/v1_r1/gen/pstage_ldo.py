import sys

import pcbnew

import pslib

# U9 (MGTAVCC 1.0 V) and U10 (MGTAVTT 1.2 V) LDOs: their input/output caps, feedback dividers and U10's
# enable RC sat 15-25 mm away; they come in beside the pins, then everything is routed
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
G9 = ['U9', 'C42', 'C43', 'R30', 'R31']
G10 = ['U10', 'C45', 'C46', 'R33', 'R34', 'R32', 'C44']
n = P.rip(G9 + G10, nets={'/POWER/FB_MGTAVCC', '/POWER/FB_MGTAVTT', '/POWER/EN_MGTAVTT'})
print('ripped %d' % n)
for r in G9[1:] + G10[1:]:
    P.fps[r].SetPosition(pslib.V(60.0, 60.0))


def place_any(ref, x, y, rmax=6.0):
    try:
        return P.place(ref, x, y, rmax=rmax)
    except SystemExit:
        return P.place(ref, x, y, bottom=True, rmax=rmax)


got = {}
for U, cin, cout, rt, rb in (('U9', 'C42', 'C43', 'R30', 'R31'), ('U10', 'C45', 'C46', 'R33', 'R34')):
    u = P.pads(U)
    got[cin] = place_any(cin, u['1'][0] - 1.2, u['1'][1])     # IN
    got[cout] = place_any(cout, u['5'][0] + 1.4, u['5'][1])   # OUT
    got[rb] = place_any(rb, u['4'][0] + 1.2, u['4'][1] + 1.0)  # FB
    got[rt] = place_any(rt, u['4'][0] + 1.2, u['4'][1] + 2.2)
u = P.pads('U10')
got['C44'] = place_any('C44', u['3'][0] - 1.2, u['3'][1] + 1.0)  # EN
got['R32'] = place_any('R32', u['3'][0] - 1.2, u['3'][1] + 2.2)
for k, v in got.items():
    print('  %-4s at (%.2f, %.2f) rot %d, %.2f mm from target%s' % ((k,) + v[:3] + (v[3], ' (bottom)' if P.fps[k].IsFlipped() else '')))
b.Save(PCB)
r = pslib.Router(PCB, [])
T = r.terms
for net, refs, w in (('+1V8', {'U9', 'C42'}, 0.4), ('+1V8', {'U10', 'C45'}, 0.4), ('+1V0_MGT', {'U9', 'C43', 'R30'}, 0.4),
                     ('+1V2_MGT', {'U10', 'C46', 'R33'}, 0.4), ('/POWER/FB_MGTAVCC', None, 0.15),
                     ('/POWER/FB_MGTAVTT', None, 0.15), ('/POWER/EN_MGTAVTT', None, 0.15), ('+1V8', {'U10', 'R32'}, 0.2)):
    r.net(net, T(net, refs), w)
k = r.stitch(G9 + G10, nets=('GND',))
r.bd.save()
print('stitched %d GND pads' % k)
print('open:', r.open)
