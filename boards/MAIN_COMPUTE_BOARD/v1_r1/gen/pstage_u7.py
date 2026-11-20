import sys

import pcbnew

import pslib
from pslib import track, via

# power stage of U7 (TPS62130, 12 V -> VADJ). L6 turns 180 deg so its switch pad faces U7's switch pins.
# input caps C35/C36 come from the top right to the bottom under PVIN. the whole feedback network
# (R20, R21, the vsel resistors R24/R25 and their fets Q2/Q3, which sat 75 mm away by the io expander)
# gathers round the FB pin; the fet gates (slow dc from the expander) may run long
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
G = ['U7', 'L6', 'C34', 'C35', 'C36', 'R20', 'R21', 'R24', 'R25', 'Q2', 'Q3']
n = P.rip(G, nets={'/POWER/SW_VADJ', '/POWER/FB_VADJ', '/POWER/SS_VADJ', '/POWER/VSEL0_D', '/POWER/VSEL1_D'})
print('ripped %d items' % n)
for r in G[2:]:
    P.fps[r].SetPosition(pslib.V(60.0, 60.0))
u = P.pads('U7')
l6 = P.fps['L6']
l6.SetOrientationDegrees((l6.GetOrientationDegrees() + 180) % 360)
lp = P.pads('L6')
print('L6 pads after turn', lp)
sw = [u[k] for k in ('1', '2', '3')]
pv = [u[k] for k in ('10', '11', '12')]
got = {}


def place_any(ref, x, y, bottom=False, rmax=7.0):
    try:
        return P.place(ref, x, y, bottom=bottom, rmax=rmax)
    except SystemExit:
        return P.place(ref, x, y, bottom=not bottom, rmax=rmax)


pvx, pvy = pv[0][0], sum(p[1] for p in pv) / 3
got['C35'] = place_any('C35', pvx + 0.6, pvy, bottom=True)
got['C36'] = place_any('C36', pvx + 1.8, pvy, bottom=True)
fb = u['5']
got['R21'] = place_any('R21', fb[0] - 0.4, fb[1] + 1.6)
got['R20'] = place_any('R20', fb[0] - 1.6, fb[1] + 1.6)
got['R24'] = place_any('R24', fb[0] + 0.8, fb[1] + 2.8)
got['R25'] = place_any('R25', fb[0] - 0.8, fb[1] + 2.8)
got['Q2'] = place_any('Q2', fb[0] + 1.0, fb[1] + 3.0, bottom=True)
got['Q3'] = place_any('Q3', fb[0] - 1.6, fb[1] + 3.0, bottom=True)
got['C34'] = place_any('C34', u['9'][0] + 1.3, u['9'][1] + 0.4)
for k, v in got.items():
    print('  %-4s at (%.2f, %.2f) rot %d, %.2f mm from target%s' % ((k,) + v[:3] + (v[3], ' (bottom)' if P.fps[k].IsFlipped() else '')))
F = pcbnew.F_Cu
# switch pins joined on their outer edge, wide run into L6's switch pad
xs = min(p[0] for p in sw) - 0.25
track(b, (xs, sw[0][1]), (xs, sw[2][1]), 0.25, '/POWER/SW_VADJ', F)
swy = sum(p[1] for p in sw) / 3
track(b, (xs, swy), (lp['1'][0], swy), 0.9, '/POWER/SW_VADJ', F)
# PVIN pins joined, one via beyond them for the bottom input caps (inside the planned 12 V top strip)
xp = max(p[0] for p in pv) + 0.25
track(b, (xp, pv[0][1]), (xp, pv[2][1]), 0.25, '+12V', F)
track(b, (xp, pvy), (xp + 0.75, pvy), 0.4, '+12V', F)
via(b, (xp + 0.75, pvy), '+12V')
b.Save(PCB)

r = pslib.Router(PCB, ['U7'])
r.keepout_courtyards(['L6'])
T = r.terms
r.net('+12V', T('+12V', {'C35', 'C36'}) + [r.via_term((xp + 0.75, pvy))], 0.5)
r.net('VADJ', T('VADJ', {'L6', 'C37', 'C38'}), 0.8)
r.net('VADJ', T('VADJ', {'L6', 'C37', 'U7', 'R20'}), 0.2)
r.net('/POWER/FB_VADJ', T('/POWER/FB_VADJ'), 0.15)
r.net('/POWER/VSEL0_D', T('/POWER/VSEL0_D'), 0.15)
r.net('/POWER/VSEL1_D', T('/POWER/VSEL1_D'), 0.15)
r.net('/POWER/SS_VADJ', T('/POWER/SS_VADJ'), 0.15)
r.net('VADJ_SEL0', T('VADJ_SEL0'), 0.15, inner=('In2.Cu', 'In5.Cu'))
r.net('VADJ_SEL1', T('VADJ_SEL1'), 0.15, inner=('In2.Cu', 'In5.Cu'))
k = r.stitch(G, nets=('GND', '+12V'))
r.bd.save()
print('stitched %d plane pads' % k)
print('open:', r.open)
