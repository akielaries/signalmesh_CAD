import json
import math
import os
import sys

import pcbnew
from shapely.geometry import LineString, Point, box
from shapely.strtree import STRtree

# widen short pad -> via stubs on ground/power nets (decap and power-pad hookups) to 0.3 mm, else
# 0.25 mm, wherever clearance to other nets' copper on that layer stays >= CLR. writes the board
PCB = sys.argv[1]
MM = 1e6
CLR = 0.15
MAXLEN = 2.5
TRY = (0.3, 0.25)
b = pcbnew.LoadBoard(PCB)
# leave fanout under fine-pitch parts alone: wider dogbones there eat escape channels
DENSE = ['U100', 'U11', 'J20', 'U17', 'U13'] + [f.GetReference() for f in b.Footprints() if f.GetValue().startswith('MT41K')]
dense = []
for ref in DENSE:
    bb = b.FindFootprintByReference(ref).GetBoundingBox(False)
    dense.append((bb.GetLeft() / MM - 0.5, bb.GetTop() / MM - 0.5, bb.GetRight() / MM + 0.5, bb.GetBottom() / MM + 0.5))
prj = json.load(open(os.path.splitext(PCB)[0] + '.kicad_pro'))
zs = b.Zones()
power = {zs[i].GetNetname() for i in range(len(zs)) if zs[i].GetNetname()} | {'GND'}
for pat in prj['net_settings'].get('netclass_patterns', []):
    if pat['netclass'] == 'PWR':
        power.add(pat['pattern'])
pwr_class = set()
ns = b.GetNetsByName()
for name in ns.keys():
    n = str(name)
    if b.FindNet(n).GetNetClassName() in ('PWR',) or n in power:
        pwr_class.add(n)

# copper per layer: (geometry, net)
shapes = {}
fs = b.Footprints()
for i in range(len(fs)):
    f = fs[i]
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        bb = p.GetBoundingBox()
        g = box(bb.GetLeft() / MM, bb.GetTop() / MM, bb.GetRight() / MM, bb.GetBottom() / MM)
        for ly in ('F.Cu', 'B.Cu', 'In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu', 'In5.Cu', 'In6.Cu'):
            lid = b.GetLayerID(ly)
            if p.IsOnLayer(lid):
                shapes.setdefault(lid, []).append((g, p.GetNetname(), ('pad', id(p))))
ts = b.Tracks()
items = [ts[i] for i in range(len(ts))]
vias = {}
for t in items:
    if t.GetClass() == 'PCB_VIA':
        c = (t.GetPosition().x / MM, t.GetPosition().y / MM)
        r = pcbnew.Cast_to_PCB_VIA(t).GetWidth(pcbnew.F_Cu) / MM / 2
        vias.setdefault(t.GetNetname(), []).append(c)
        for lid in (pcbnew.F_Cu, pcbnew.B_Cu):
            shapes.setdefault(lid, []).append((Point(c).buffer(r), t.GetNetname(), ('via', id(t))))
    else:
        a = (t.GetStart().x / MM, t.GetStart().y / MM)
        z = (t.GetEnd().x / MM, t.GetEnd().y / MM)
        g = LineString([a, z]).buffer(t.GetWidth() / MM / 2) if a != z else Point(a).buffer(t.GetWidth() / MM / 2)
        shapes.setdefault(t.GetLayer(), []).append((g, t.GetNetname(), ('trk', id(t))))
trees = {lid: STRtree([s[0] for s in lst]) for lid, lst in shapes.items()}


def pad_at(net, p, lid):
    for g, n, tag in shapes.get(lid, []):
        if tag[0] == 'pad' and n == net and g.buffer(0.01).contains(Point(p)):
            return True
    return False


done = {0.3: 0, 0.25: 0}
kept = 0
for t in items:
    if t.GetClass() != 'PCB_TRACK' or t.GetNetname() not in pwr_class or t.GetWidth() / MM >= 0.25 - 1e-6:
        continue
    if t.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu) or t.GetLength() / MM > MAXLEN:
        continue
    net, lid = t.GetNetname(), t.GetLayer()
    a = (t.GetStart().x / MM, t.GetStart().y / MM)
    z = (t.GetEnd().x / MM, t.GetEnd().y / MM)
    mx, my = (a[0] + z[0]) / 2, (a[1] + z[1]) / 2
    if any(x0 < mx < x1 and y0 < my < y1 for x0, y0, x1, y1 in dense):
        continue
    vs = vias.get(net, [])
    at_via = lambda q: any(math.hypot(q[0] - v[0], q[1] - v[1]) < 0.02 for v in vs)
    if not ((at_via(a) and pad_at(net, z, lid)) or (at_via(z) and pad_at(net, a, lid))):
        continue
    me = ('trk', id(t))
    for w in TRY:
        g = LineString([a, z]).buffer(w / 2)
        ok = True
        lst = shapes[lid]
        for idx in trees[lid].query(g.buffer(CLR)):
            og, on, tag = lst[idx]
            if on == net or tag == me:
                continue
            if g.distance(og) < CLR:
                ok = False
                break
        if ok:
            t.SetWidth(int(w * MM))
            done[w] += 1
            break
    else:
        kept += 1
b.Save(PCB)
print('stubs widened: %d to 0.3 mm, %d to 0.25 mm; %d left (no clearance)' % (done[0.3], done[0.25], kept))
