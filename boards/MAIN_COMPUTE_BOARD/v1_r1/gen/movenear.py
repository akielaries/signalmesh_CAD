import math
import sys

import pcbnew

import proute
import rlib

# move small parts next to a pad, same side, nearest free spot; drop their old stitching and
# re-stitch their plane pads. usage: movenear.py board REF:TOREF:PIN [...]
PCB = sys.argv[1]
MM = 1e6
b = pcbnew.LoadBoard(PCB)
fs = b.Footprints()
fps = [fs[i] for i in range(len(fs))]
key = lambda v: (round(v.x / MM, 3), round(v.y / MM, 3))


def crt(f):
    c = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
    return (bb.GetLeft() / MM, bb.GetTop() / MM, bb.GetRight() / MM, bb.GetBottom() / MM)


def tht(f):
    return any(f.Pads()[k].GetAttribute() == pcbnew.PAD_ATTRIB_PTH for k in range(len(f.Pads())))


def hit(a, c, gap=0.2):
    return a[0] - gap < c[2] and a[2] + gap > c[0] and a[1] - gap < c[3] and a[3] + gap > c[1]


def free(f):
    r = crt(f)
    if r[0] < 50.5 or r[2] > 190.6 or r[1] < 53.1 or r[3] > 146.9:
        return False
    return not any(o.GetReference() != f.GetReference() and (o.IsFlipped() == f.IsFlipped() or tht(o) or tht(f))
                   and hit(r, crt(o)) for o in fps)


jobs = [a.split(':') for a in sys.argv[2:]]
refs = [j[0] for j in jobs]
old = set()
for r in refs:
    f = b.FindFootprintByReference(r)
    old |= {key(f.Pads()[k].GetPosition()) for k in range(len(f.Pads()))}
ts = b.Tracks()
items = [ts[i] for i in range(len(ts))]
vias, kill = set(), []
for t in items:
    if t.GetClass() != 'PCB_VIA':
        s, e = key(t.GetStart()), key(t.GetEnd())
        if s in old or e in old:
            kill.append(t)
            vias.add((t.GetNetname(), e if s in old else s))
kill += [t for t in items if t.GetClass() == 'PCB_VIA' and (t.GetNetname(), key(t.GetPosition())) in vias]
for t in kill:
    b.Remove(t)
out = []
for r, to, pin in jobs:
    f = b.FindFootprintByReference(r)
    tf = b.FindFootprintByReference(to)
    tp = [tf.Pads()[k] for k in range(len(tf.Pads())) if tf.Pads()[k].GetNumber() == pin][0].GetPosition()
    x0, y0 = tp.x / MM, tp.y / MM
    got = None
    for rad in [1.5 + 0.25 * i for i in range(48)]:
        n = max(8, int(2 * math.pi * rad / 0.25))
        for k in range(n):
            a = 2 * math.pi * k / n
            for rot in (0, 90):
                f.SetOrientationDegrees(rot)
                f.SetPosition(pcbnew.VECTOR2I(int((x0 + rad * math.cos(a)) * MM), int((y0 + rad * math.sin(a)) * MM)))
                if free(f):
                    got = (round(f.GetPosition().x / MM, 2), round(f.GetPosition().y / MM, 2), rot)
                    break
            if got:
                break
        if got:
            break
    if not got:
        raise SystemExit('no spot for ' + r)
    out.append((r, got))
b.Save(PCB)
bd = rlib.Board(PCB)
zs = b.Zones()
planes = {zs[i].GetNetname() for i in range(len(zs)) if zs[i].GetNetname()} | {'GND'}
ok = fail = 0
for (x, y, hx, hy, n, lays, rnd, p) in list(bd.pads):
    fp = p.GetParentFootprint()
    if fp.GetReference() not in refs or n not in planes:
        continue
    ly = 'B.Cu' if fp.IsFlipped() else 'F.Cu'
    st = []
    if proute.drop_via(bd, (x, y), n, (x, y + 1.0), st, radii=(0.6, 0.75, 0.9, 1.1, 1.3, 1.6), layer=ly):
        bd.commit(st)
        ok += 1
    else:
        bd.unstage(st)
        fail += 1
bd.save()
print('moved', out, '; removed %d old stitch items; stitched %d plane pads, %d without room' % (len(kill), ok, fail))
