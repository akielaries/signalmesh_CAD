import math
import sys

import pcbnew

import proute
import rlib

# after vitamove.py: re-place the top parts the connector now overlaps (nearest free spot, same side),
# drop their old stitching, then stitch the connector's and those parts' plane pads with short
# octilinear stubs to vias (rlib.drop_via checks clearance)
PCB = sys.argv[1]
MM = 1e6
b = pcbnew.LoadBoard(PCB)
fs = b.Footprints()
fps = {fs[i].GetReference(): fs[i] for i in range(len(fs))}
FIXED = ['J20'] + [r for r, f in fps.items() if f.GetValue() == 'M2.5 VITA']


def crt(f):
    c = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
    return (bb.GetLeft() / MM, bb.GetTop() / MM, bb.GetRight() / MM, bb.GetBottom() / MM)


def tht(f):
    return any(f.Pads()[k].GetAttribute() == pcbnew.PAD_ATTRIB_PTH for k in range(len(f.Pads())))


def hit(a, c, gap=0.2):
    return a[0] - gap < c[2] and a[2] + gap > c[0] and a[1] - gap < c[3] and a[3] + gap > c[1]


def overlaps(f, others):
    r = crt(f)
    if r[0] < 50.5 or r[2] > 190.6 or r[1] < 53.1 or r[3] > 146.9:
        return True
    for o in others:
        if o is f:
            continue
        if (o.IsFlipped() == f.IsFlipped() or tht(o) or tht(f)) and hit(r, crt(o)):
            return True
    return False


allf = list(fps.values())
fixed_boxes = [fps[r] for r in FIXED]
bad = [r for r, f in fps.items() if r not in FIXED and not f.IsFlipped()
       and any(hit(crt(f), crt(x), 0.0) for x in fixed_boxes)]
key = lambda v: (round(v.x / MM, 3), round(v.y / MM, 3))
moved = []
# drop the old stitching of all the parts to move in one pass (track from a pad + the via at its far end)
allpads = set()
for r in bad:
    f = fps[r]
    allpads |= {key(f.Pads()[k].GetPosition()) for k in range(len(f.Pads()))}
ts = b.Tracks()
items = [ts[i] for i in range(len(ts))]
vias, kill = set(), []
for t in items:
    if t.GetClass() != 'PCB_VIA':
        s, e = key(t.GetStart()), key(t.GetEnd())
        if s in allpads or e in allpads:
            kill.append(t)
            vias.add((t.GetNetname(), e if s in allpads else s))
kill += [t for t in items if t.GetClass() == 'PCB_VIA' and (t.GetNetname(), key(t.GetPosition())) in vias]
for t in kill:
    b.Remove(t)
for r in bad:
    f = fps[r]
    x0, y0 = f.GetPosition().x / MM, f.GetPosition().y / MM
    done = False
    for rad in [i * 0.25 for i in range(1, 120)]:
        n = max(8, int(2 * math.pi * rad / 0.25))
        for k in range(n):
            a = 2 * math.pi * k / n
            f.SetPosition(pcbnew.VECTOR2I(int((x0 + rad * math.cos(a)) * MM), int((y0 + rad * math.sin(a)) * MM)))
            if not overlaps(f, allf):
                done = True
                break
        if done:
            break
    moved.append((r, f.GetValue(), round(f.GetPosition().x / MM, 2), round(f.GetPosition().y / MM, 2), done))
b.Save(PCB)
print('re-placed:', moved)

# stitch plane pads of the connector and the moved parts
rlib.BGA_RECTS[:] = [(120.8, 62.35, 179.3, 76.65, 0.10)]
bd = rlib.Board(PCB)
planes = {z[2] for z in bd.pours} | {'GND'}
targets = FIXED[:1] + [m[0] for m in moved]
ok = fail = 0
for (x, y, hx, hy, n, lays, rnd, p) in list(bd.pads):
    ref = p.GetParentFootprint().GetReference()
    if ref not in targets or n not in planes or 'F.Cu' not in lays or p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
        continue
    st = []
    v = proute.drop_via(bd, (x, y), n, (x, y + 1.0), st, radii=(0.6, 0.75, 0.9, 1.1, 1.3, 1.6))
    if v:
        bd.commit(st)
        ok += 1
    else:
        bd.unstage(st)
        fail += 1
bd.save()
print('stitched %d plane pads, %d without room' % (ok, fail))
