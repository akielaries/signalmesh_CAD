import math
import sys

import pcbnew

import proute
import pslib

# U8 stage fix-up: re-route the +1V35 output without neck-down (U8 is sot-23, no escape box):
# L7 -> C41 wide, L7 -> In4 pour over In2, and the divider top
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
ts = b.Tracks()
box = (92.0, 103.0, 102.0, 110.5)
kill = []
for i in range(len(ts)):
    t = ts[i]
    if t.GetNetname() != '+1V35':
        continue
    pts = [t.GetPosition()] if t.GetClass() == 'PCB_VIA' else [t.GetStart(), t.GetEnd()]
    if all(box[0] < p.x / 1e6 < box[2] and box[1] < p.y / 1e6 < box[3] for p in pts):
        kill.append(t)
for t in kill:
    b.Remove(t)
P._removed = kill
b.Save(PCB)
print('ripped %d +1V35 items' % len(kill))
r = pslib.Router(PCB, ['U6'])
r.keepout_courtyards(['L1', 'L4', 'L5', 'L7'])
r.net('+1V35', r.terms('+1V35', {'L7', 'C41'}), 0.6)
bd = r.bd
l7 = [t for t in r.terms('+1V35', {'L7'})][0][1]
st = []
va = proute.drop_via(bd, l7, '+1V35', (101.0, 104.0), st, radii=tuple(0.5 + 0.25 * i for i in range(10)), w=0.6)
spot = None
for rad in [0.25 * i for i in range(0, 30)]:
    m = max(1, int(2 * math.pi * rad / 0.25))
    for k in range(m):
        x, y = 100.8 + rad * math.cos(2 * math.pi * k / m), 104.0 + rad * math.sin(2 * math.pi * k / m)
        if x > 99.6 and proute.via_spot_ok(bd, x, y, '+1V35'):
            spot = (x, y)
            break
    if spot:
        break
pts = bd.path('In2.Cu', va, spot, 0.3, {'+1V35'}, 0.15, margin=6.0) if va and spot else None
if pts:
    bd.stage_track(pts, 0.6, '+1V35', 'In2.Cu', st)
    bd.stage_via(spot[0], spot[1], '+1V35', st)
    bd.commit(st)
    print('pour feed via %s, In2 %.1f mm' % (tuple(round(v, 2) for v in spot),
          sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts, pts[1:]))))
else:
    bd.unstage(st)
    r.open.append(('+1V35', 'L7', 'pour'))
r.net('+1V35', r.terms('+1V35', {'R28'}) + ([r.via_term(spot)] if spot else []), 0.2)
bd.save()
print('open:', r.open)
