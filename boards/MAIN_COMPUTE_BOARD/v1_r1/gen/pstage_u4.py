import sys

import pcbnew

import pslib
from pslib import track, via

# power stage of U4 (TPS62130, 12 V -> +3V3_MEZZ). U4 turns 90 deg so its switch pins face south into
# L3; PVIN then faces north (mounting hole H there), so the input caps go on the bottom under PVIN.
# fb divider, soft-start cap, output caps and the EN_12V divider come in beside their pins
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
G = ['U4', 'L3', 'C19', 'C20', 'C21', 'C22', 'C23', 'R11', 'R12', 'R3', 'R4']
n = P.rip(G, nets={'/POWER/SW_3V3M', '/POWER/FB_3V3M', '/POWER/SS_3V3M'})
print('ripped %d items' % n)
for r in G[2:]:
    P.fps[r].SetPosition(pslib.V(60.0, 60.0))
u4 = P.fps['U4']
u4.SetOrientationDegrees(90)
u4.SetPosition(pslib.V(186.0, 63.0))
u = P.pads('U4')
sw = [u[k] for k in ('1', '2', '3')]
pv = [u[k] for k in ('10', '11', '12')]
print('U4 SW pins', sw, 'PVIN pins', pv, 'FB', u['5'], 'SS', u['9'], 'EN', u['13'], 'VOS', u['14'], 'PG', u['4'])
swx = sum(p[0] for p in sw) / 3
l3 = P.fps['L3']
for rot in (90, 270):
    l3.SetOrientationDegrees(rot)
    l3.SetPosition(pslib.V(swx, 67.7))
    lp = P.pads('L3')
    if lp['1'][1] < lp['2'][1]:        # switch pad (1) north, toward U4
        break
x = swx
while not P.ok(l3, ignore=('U4',)) and x < swx + 1.6:
    x += 0.1
    l3.SetPosition(pslib.V(x, 67.7))
lp = P.pads('L3')
print('L3 at (%.2f, 67.70), pads %s' % (x, lp))
got = {}


def place_any(ref, x, y, bottom=False, rmax=7.0):
    try:
        return P.place(ref, x, y, bottom=bottom, rmax=rmax)
    except SystemExit:
        return P.place(ref, x, y, bottom=not bottom, rmax=rmax)


pvx = sum(p[0] for p in pv) / 3
pvy = pv[0][1]
got['C20'] = place_any('C20', pvx, pvy - 0.6, bottom=True)
got['C21'] = place_any('C21', pvx + 1.6, pvy - 0.6, bottom=True)
got['C22'] = place_any('C22', lp['2'][0] - 2.6, lp['2'][1] + 1.0)
got['C23'] = place_any('C23', lp['2'][0] - 2.6, lp['2'][1] + 3.2)
got['R12'] = place_any('R12', u['5'][0] + 1.2, u['5'][1])
got['R11'] = place_any('R11', u['5'][0] + 1.2, u['5'][1] + 1.6)
got['C19'] = place_any('C19', u['9'][0] + 1.2, u['9'][1])
got['R3'] = place_any('R3', u['13'][0] - 1.4, u['13'][1] - 0.8)
got['R4'] = place_any('R4', u['13'][0] - 1.4, u['13'][1] + 0.8)
for k, v in got.items():
    print('  %-4s at (%.2f, %.2f) rot %d, %.2f mm from target%s' % ((k,) + v[:3] + (v[3], ' (bottom)' if P.fps[k].IsFlipped() else '')))
# switch pins joined on their outer edge, straight down into L3's switch pad
F = pcbnew.F_Cu
ys = max(p[1] for p in sw) + 0.25
track(b, (min(p[0] for p in sw), ys), (max(p[0] for p in sw), ys), 0.25, '/POWER/SW_3V3M', F)
track(b, (swx, ys), (swx, lp['1'][1]), 0.9, '/POWER/SW_3V3M', F)
if abs(swx - lp['1'][0]) > 0.3:
    track(b, (swx, lp['1'][1]), lp['1'], 0.9, '/POWER/SW_3V3M', F)
# PVIN pins joined on their outer edge, a via just beyond for the bottom input caps
yp = min(p[1] for p in pv) - 0.25
track(b, (min(p[0] for p in pv), yp), (max(p[0] for p in pv), yp), 0.25, '+12V', F)
track(b, (pvx, yp), (pvx, yp - 0.75), 0.4, '+12V', F)
via(b, (pvx, yp - 0.75), '+12V')
b.Save(PCB)

r = pslib.Router(PCB, ['U4'])
r.keepout_courtyards(['L3'])
T = r.terms
r.net('+12V', T('+12V', {'C20', 'C21'}) + [r.via_term((pvx, yp - 0.75))], 0.5)
r.net('+3V3_MEZZ', T('+3V3_MEZZ', {'L3', 'C22', 'C23'}), 0.8)
r.net('+3V3_MEZZ', T('+3V3_MEZZ', {'L3', 'C22', 'C23', 'U4', 'R11'}), 0.2)
r.net('/POWER/FB_3V3M', T('/POWER/FB_3V3M'), 0.15)
r.net('/POWER/SS_3V3M', T('/POWER/SS_3V3M'), 0.15)
r.net('/POWER/EN_12V', T('/POWER/EN_12V', {'U4', 'R3', 'R4'}), 0.15)
r.net('/POWER/PG_3V3M', T('/POWER/PG_3V3M'), 0.15)
k = r.stitch(G, nets=('GND', '+12V', '+3V3_MEZZ'))
r.bd.save()
print('stitched %d plane pads' % k)
print('open:', r.open)
