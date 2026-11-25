import math
import sys

import pcbnew

import proute
import pslib

# move unconnected decoupling caps the least distance to a spot where both pads can be stitched: each named
# cap is lifted (its own stitching ripped) and placed at the nearest free spot on its side where every pad
# has a via spot of its own net within 1 mm; planestitch.py then stitches it. usage: decapmove.py <board> REF...
PCB, REFS = sys.argv[1], sys.argv[2:]
MM = 1e6
b = pcbnew.LoadBoard(PCB)
rt = pslib.Router(PCB, [])


def stitchable(f):
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        x, y, n = p.GetPosition().x / MM, p.GetPosition().y / MM, p.GetNetname()
        spots = [(x + dx * 0.2, y + dy * 0.2) for dx in range(-5, 6) for dy in range(-5, 6) if 0.45 <= math.hypot(dx * 0.2, dy * 0.2) <= 1.0]
        if not any(proute.via_spot_exact(rt.bd, q[0], q[1], n, r=0.2, clr=0.1) for q in spots):
            return False
    return True


class P(pslib.Placer):
    def ok(self, f, gap=0.15, ignore=()):
        return pslib.Placer.ok(self, f, gap, ignore) and stitchable(f)


pl = P(b)
moved = []
for r in REFS:
    f = pl.fps.get(r)
    if f is None:
        continue
    x0, y0 = f.GetPosition().x / MM, f.GetPosition().y / MM
    rot0 = f.GetOrientationDegrees()
    pl.rip([r])
    f.SetPosition(pcbnew.VECTOR2I(int(10 * MM), int(10 * MM)))
    try:
        got = pl.place(r, x0, y0, bottom=f.IsFlipped(), rmax=4.0)
    except SystemExit:
        got = None
    if got:
        moved.append('%s %.1f mm' % (r, math.hypot(got[0] - x0, got[1] - y0)))
    else:
        f.SetPosition(pcbnew.VECTOR2I(int(x0 * MM), int(y0 * MM)))
        f.SetOrientationDegrees(rot0)
b.Save(PCB)
print('decaps moved to stitchable spots: %d of %d: %s' % (len(moved), len(REFS), ', '.join(moved)))
