import math
import sys

import pcbnew

import pslib

# pull the stm32 decaps (bottom side, +3V3 / VCAP / VDDA to GND) back toward the BGA: each one moves to the
# nearest free bottom spot that is closer to the package than it is now, clear of the area under the BGA,
# of other parts and of other nets' copper; its old stitching is ripped and planestitch.py re-stitches it.
# usage: decapback.py <board>
PCB = sys.argv[1]
MM = 1e6
b = pcbnew.LoadBoard(PCB)
u = b.FindFootprintByReference('U11')
kc = u.GetCourtyard(pcbnew.F_CrtYd).BBox()
K = (kc.GetLeft() / MM - 1.5, kc.GetTop() / MM - 1.5, kc.GetRight() / MM + 1.5, kc.GetBottom() / MM + 1.5)
cx, cy = (K[0] + K[2]) / 2, (K[1] + K[3]) / 2
hit = lambda c, q: c[0] < q[2] and c[2] > q[0] and c[1] < q[3] and c[3] > q[1]
dist = lambda x, y: math.hypot(max(K[0] - x, 0, x - K[2]), max(K[1] - y, 0, y - K[3]))


STITCH = '--stitch' in sys.argv
rt = pslib.Router(PCB, []) if STITCH else None
import proute


def stitchable(f):
    # each pad must have a via spot within 1 mm on its own net (checked against the current copper)
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        x, y, n = p.GetPosition().x / MM, p.GetPosition().y / MM, p.GetNetname()
        spots = [(x + dx * 0.25, y + dy * 0.25) for dx in range(-4, 5) for dy in range(-4, 5) if 0.5 <= math.hypot(dx * 0.25, dy * 0.25) <= 1.0]
        if not any(proute.via_spot_exact(rt.bd, q[0], q[1], n, r=0.2, clr=0.127) for q in spots):
            return False
    return True


class P(pslib.Placer):
    def ok(self, f, gap=0.15, ignore=()):
        if f.IsFlipped() and hit(self.crt(f), K):
            return False
        if not pslib.Placer.ok(self, f, gap, ignore):
            return False
        return stitchable(f) if STITCH else True


pl = P(b)
STM_NETS = {'+3V3', '/STM32/VCAP', '+3V3_VDDA'}
cands = []
for r, f in pl.fps.items():
    if not f.IsFlipped() or not r.startswith('C') or len(f.Pads()) != 2:
        continue
    nets = {f.Pads()[k].GetNetname() for k in range(2)}
    if 'GND' not in nets or not (nets & STM_NETS):
        continue
    x, y = f.GetPosition().x / MM, f.GetPosition().y / MM
    if 2.0 < dist(x, y) < 16.0 and abs(x - cx) < 20 and abs(y - cy) < 26:
        cands.append((dist(x, y), r))
moved = []
for d0, r in sorted(cands, reverse=True):
    f = pl.fps[r]
    x0, y0 = f.GetPosition().x / MM, f.GetPosition().y / MM
    rot0 = f.GetOrientationDegrees()
    # aim at the nearest point just outside the keep area
    tx = min(max(x0, K[0] - 0.8), K[2] + 0.8)
    ty = min(max(y0, K[1] - 0.8), K[3] + 0.8)
    if K[0] < tx < K[2] and K[1] < ty < K[3]:
        ty = K[1] - 0.8 if y0 < cy else K[3] + 0.8
    pl.rip([r])
    f.SetPosition(pcbnew.VECTOR2I(int(10 * MM), int(10 * MM)))
    try:
        got = pl.place(r, tx, ty, bottom=True, rmax=max(0.5, d0 - 1.0))
    except SystemExit:
        got = None
    if got and dist(got[0], got[1]) < d0 - 1.0:
        moved.append((r, round(d0, 1), round(dist(got[0], got[1]), 1)))
    else:
        f.SetPosition(pcbnew.VECTOR2I(int(x0 * MM), int(y0 * MM)))
        f.SetOrientationDegrees(rot0)
b.Save(PCB)
print('stm32 decaps pulled closer: %d of %d: %s' % (len(moved), len(cands), ' '.join('%s %.1f->%.1f' % m for m in moved)))
