import math
import sys

import pcbnew

# move the vita connector (and its standoffs) by DY in place: rip up the vita dp / refclk1 / la routes
# (fpga dogbones kept) and the stitching on the connector's own pads, then move. re-stitch and re-route
# afterwards (vitastitch.py, gtp.py ONLY=..., la.py)
PCB, DY = sys.argv[1], float(sys.argv[2])
MM = 1e6
b = pcbnew.LoadBoard(PCB)
fs = b.Footprints()
fps = {fs[i].GetReference(): fs[i] for i in range(len(fs))}
j20 = fps['J20']
holes = [r for r, f in fps.items() if f.GetValue() == 'M2.5 VITA']
u100 = fps['U100']
key = lambda v: (round(v.x / MM, 3), round(v.y / MM, 3))
jpads = {key(j20.Pads()[k].GetPosition()) for k in range(len(j20.Pads()))}
balls = {key(u100.Pads()[k].GetPosition()): u100.Pads()[k].GetNetname() for k in range(len(u100.Pads()))}
VITA = ('GTP2_TX', 'GTP3_TX', 'GTP_REFCLK1', 'MEZZ_DP', 'MEZZ_GBTCLK0', 'MEZZ_LA', 'MEZZ_CLK')
ts = b.Tracks()
items = [ts[i] for i in range(len(ts))]
# fpga dogbones on vita nets stay: ball -> via, short, same net
keep_via = set()
keep = set()
for t in items:
    if t.GetClass() == 'PCB_VIA' or not t.GetNetname().startswith(VITA):
        continue
    for e, o in ((key(t.GetStart()), key(t.GetEnd())), (key(t.GetEnd()), key(t.GetStart()))):
        if balls.get(e) == t.GetNetname() and math.hypot(e[0] - o[0], e[1] - o[1]) < 1.2:
            keep.add(id(t))
            keep_via.add((t.GetNetname(), o))
# stitching on the connector's pads: a track from a pad, and the via at its other end
stitch_via = set()
stitch = set()
for t in items:
    if t.GetClass() == 'PCB_VIA' or t.GetNetname().startswith(VITA):
        continue
    for e, o in ((key(t.GetStart()), key(t.GetEnd())), (key(t.GetEnd()), key(t.GetStart()))):
        if e in jpads:
            stitch.add(id(t))
            stitch_via.add((t.GetNetname(), o))
removed = 0
for t in items:
    n = t.GetNetname()
    if t.GetClass() == 'PCB_VIA':
        pos = (n, key(t.GetPosition()))
        if (n.startswith(VITA) and pos not in keep_via) or pos in stitch_via:
            b.Remove(t)
            removed += 1
    elif (n.startswith(VITA) and id(t) not in keep) or id(t) in stitch:
        b.Remove(t)
        removed += 1
for r in ['J20'] + holes:
    f = fps[r]
    p = f.GetPosition()
    f.SetPosition(pcbnew.VECTOR2I(p.x, p.y + int(DY * MM)))
# top-side parts the connector or standoffs now overlap
moved = []
for r in ['J20'] + holes:
    cy = fps[r].GetCourtyard(pcbnew.F_CrtYd).BBox()
    for o, f in fps.items():
        if o in ['J20'] + holes or f.IsFlipped():
            continue
        oc = f.GetCourtyard(pcbnew.F_CrtYd)
        if oc.OutlineCount() and cy.Intersects(oc.BBox()):
            moved.append((o, f.GetValue(), round(f.GetPosition().x / MM, 2), round(f.GetPosition().y / MM, 2)))
b.Save(PCB)
print('removed %d route/stitch items; moved J20 and %s by %.2f mm' % (removed, holes, DY))
print('now overlapping:', moved)
