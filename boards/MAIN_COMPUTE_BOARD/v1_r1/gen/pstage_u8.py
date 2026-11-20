import math
import sys

import pcbnew

import proute
import pslib
from pslib import track

# power stage of U8 (TLV62568, 5 V -> +1V35 for the ddr). U8 and L7 turn 180 deg so the switch pin
# faces L7's switch pad. C39 (input), C41 (one output cap), the fb divider go on the bottom under
# them; TP6 (+1V8 test point) moves next to C33. C40 stays at the ddr as bulk at the load. L7's
# output reaches the +1V35 In4 pour over In2
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
n = P.rip(['U8', 'L7', 'C39', 'C41', 'R28', 'R29', 'TP6'],
          nets={'/POWER/SW_1V35', '/POWER/FB_1V35', 'PG_1V8'}, near=[('+1V8', (96.5, 107.0), 0.9)])
print('ripped %d items' % n)
P.fps['U8'].SetOrientationDegrees(270)
P.fps['L7'].SetOrientationDegrees(270)
u8, l7 = P.pads('U8'), P.pads('L7')
print('U8 pins', u8)
print('L7 pads', l7)
got = {}
c33 = P.pads('C33')['1']
got['TP6'] = P.place('TP6', c33[0], c33[1], bottom=True)
got['C39'] = P.place('C39', u8['4'][0] - 0.6, u8['4'][1] - 0.6, bottom=True)
got['C41'] = P.place('C41', l7['2'][0], l7['2'][1] - 0.8, bottom=True)
got['R28'] = P.place('R28', u8['5'][0] + 0.6, u8['5'][1] - 1.0, bottom=True)
got['R29'] = P.place('R29', u8['5'][0] + 1.6, u8['5'][1] - 1.0, bottom=True)
print('placed', got)
for r in ('U8', 'L7'):
    if not P.ok(P.fps[r]):
        print('note: %s fixed spot is tighter than the placer margin' % r)
# switch node: U8 pin 3 straight to L7 pin 1
a, z = u8['3'], l7['1']
if abs(a[1] - z[1]) < 0.01:
    track(b, a, z, 0.6, '/POWER/SW_1V35', pcbnew.F_Cu)
else:
    d = abs(a[1] - z[1])
    mid = (a[0] - d if z[0] < a[0] else a[0] + d, z[1])
    track(b, a, mid, 0.6, '/POWER/SW_1V35', pcbnew.F_Cu)
    track(b, mid, z, 0.6, '/POWER/SW_1V35', pcbnew.F_Cu)
b.Save(PCB)

r = pslib.Router(PCB, ['U8', 'U6'])
r.keepout_courtyards(['L1', 'L4', 'L5', 'L7'])
r.net('+1V35', r.terms('+1V35', {'L7', 'C41'}), 0.6)
r.net('+5V', r.terms('+5V', {'U8', 'C39', 'U6'}), 0.4)
r.net('/POWER/FB_1V35', r.terms('/POWER/FB_1V35'), 0.15)
r.net('+1V35', r.terms('+1V35', {'L7', 'C41', 'R28'}), 0.2)
r.net('PG_1V8', r.terms('PG_1V8', {'U6', 'U8', 'R19', 'TP17'}), 0.15)
r.net('+1V8', r.terms('+1V8', {'TP6', 'C33'}), 0.2)
# output to the In4 +1V35 pour: a via beside L7's output, In2 to a via inside the pour
bd = r.bd
st = []
va = proute.drop_via(bd, l7['2'], '+1V35', (100.5, 104.0), st, radii=tuple(0.5 + 0.25 * i for i in range(10)))
spot = None
for rad in [0.25 * i for i in range(0, 30)]:
    for k in range(max(1, int(2 * math.pi * rad / 0.25))):
        x = 100.6 + rad * math.cos(2 * math.pi * k / max(1, int(2 * math.pi * rad / 0.25)))
        y = 103.8 + rad * math.sin(2 * math.pi * k / max(1, int(2 * math.pi * rad / 0.25)))
        if x > 99.6 and y > 96.0 and proute.via_spot_ok(bd, x, y, '+1V35'):
            spot = (x, y)
            break
    if spot:
        break
pts = bd.path('In2.Cu', va, spot, 0.3, {'+1V35'}, 0.15, margin=6.0) if va and spot else None
if pts:
    bd.stage_track(pts, 0.6, '+1V35', 'In2.Cu', st)
    bd.stage_via(spot[0], spot[1], '+1V35', st)
    bd.commit(st)
    print('pour feed: In2 %.1f mm to a via at (%.2f, %.2f)' % (
        sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts, pts[1:])), spot[0], spot[1]))
else:
    bd.unstage(st)
    r.open.append(('+1V35', 'L7 output', 'In4 pour'))
k = r.stitch(['U8', 'C39', 'C41', 'R29'], nets=('GND',))
bd.save()
print('stitched %d GND pads' % k)
print('open:', r.open)
