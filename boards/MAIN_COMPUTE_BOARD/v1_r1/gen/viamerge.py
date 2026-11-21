import math
import sys

import pcbnew

# merge clustered vias of one net: vias of the same net closer than MIN (hole to hole) collapse onto one
# (the one most tracks already end on); every track end that sat on a removed via is joined to the kept
# via by a short 0/45/90 jog on its own layer. usage: viamerge.py <board>
PCB = sys.argv[1]
MIN = 0.5
MM = 1e6
b = pcbnew.LoadBoard(PCB)
ts = b.Tracks()
items = [ts[i] for i in range(len(ts))]
vias = [t for t in items if t.GetClass() == 'PCB_VIA']
tracks = [t for t in items if t.GetClass() != 'PCB_VIA']
P = lambda v: (v.x / MM, v.y / MM)
ends = {}
for t in tracks:
    for e in (t.GetStart(), t.GetEnd()):
        k = (t.GetNetname(), round(e.x / MM, 3), round(e.y / MM, 3))
        ends[k] = ends.get(k, 0) + 1
bynet = {}
for v in vias:
    bynet.setdefault(v.GetNetname(), []).append(v)
keep, removed, jogs = [], [], 0


def dogleg(a, z):
    dx, dy = z[0] - a[0], z[1] - a[1]
    k = min(abs(dx), abs(dy))
    m = (a[0] + math.copysign(k, dx), a[1] + math.copysign(k, dy))
    pts = [a]
    if math.hypot(m[0] - a[0], m[1] - a[1]) > 1e-4:
        pts.append(m)
    if math.hypot(z[0] - m[0], z[1] - m[1]) > 1e-4:
        pts.append(z)
    return pts


for net, vs in bynet.items():
    if not net or net == 'GND' or len(vs) < 2:
        continue
    alive = list(vs)
    changed = True
    while changed:
        changed = False
        for i in range(len(alive)):
            for j in range(i + 1, len(alive)):
                a, c = alive[i], alive[j]
                if math.dist(P(a.GetPosition()), P(c.GetPosition())) < MIN:
                    na = ends.get((net, round(a.GetPosition().x / MM, 3), round(a.GetPosition().y / MM, 3)), 0)
                    nc = ends.get((net, round(c.GetPosition().x / MM, 3), round(c.GetPosition().y / MM, 3)), 0)
                    kv, rv = (a, c) if na >= nc else (c, a)
                    kp, rp = P(kv.GetPosition()), P(rv.GetPosition())
                    # tracks ending on the removed via get a jog to the kept one, on their own layer
                    lays = set()
                    for t in tracks:
                        if t.GetNetname() != net:
                            continue
                        for e in (t.GetStart(), t.GetEnd()):
                            if math.dist(P(e), rp) < 0.005:
                                lays.add(t.GetLayer())
                    for ly in lays:
                        pts = dogleg(rp, kp)
                        for p0, p1 in zip(pts, pts[1:]):
                            nt = pcbnew.PCB_TRACK(b)
                            nt.SetStart(pcbnew.VECTOR2I(int(round(p0[0] * MM)), int(round(p0[1] * MM))))
                            nt.SetEnd(pcbnew.VECTOR2I(int(round(p1[0] * MM)), int(round(p1[1] * MM))))
                            nt.SetWidth(int(0.1 * MM))
                            nt.SetLayer(ly)
                            nt.SetNet(kv.GetNet())
                            b.Add(nt)
                            keep.append(nt)
                            tracks.append(nt)
                            jogs += 1
                    b.Remove(rv)
                    removed.append(rv)
                    alive.remove(rv)
                    changed = True
                    break
            if changed:
                break
b.Save(PCB)
print('merged %d clustered vias, added %d jog segments' % (len(removed), jogs))
