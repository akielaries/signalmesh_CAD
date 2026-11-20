import sys

import pcbnew
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

# copper-geometry connectivity of one net (pads, tracks, vias, filled zones), independent of the drc
# report's 499-item cap: prints the pieces and which pads are in each
PCB, NET = sys.argv[1], sys.argv[2]
MM = 1e6
b = pcbnew.LoadBoard(PCB)
f = pcbnew.ZONE_FILLER(b)
zs = b.Zones()
f.Fill([zs[i] for i in range(len(zs))])
layers = [b.GetLayerID(n) for n in ('F.Cu', 'In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu', 'In5.Cu', 'In6.Cu', 'B.Cu')]
items = []    # (layer set, geometry, label)
for fp in b.Footprints():
    for k in range(len(fp.Pads())):
        p = fp.Pads()[k]
        if p.GetNetname() != NET:
            continue
        bb = p.GetBoundingBox()
        g = box(bb.GetLeft() / MM, bb.GetTop() / MM, bb.GetRight() / MM, bb.GetBottom() / MM)
        items.append(({l for l in layers if p.IsOnLayer(l)}, g, fp.GetReference() + ':' + p.GetNumber()))
ts = b.Tracks()
for i in range(len(ts)):
    t = ts[i]
    if t.GetNetname() != NET:
        continue
    if t.GetClass() == 'PCB_VIA':
        items.append((set(layers), Point(t.GetPosition().x / MM, t.GetPosition().y / MM).buffer(0.22), 'via'))
    else:
        a, z = (t.GetStart().x / MM, t.GetStart().y / MM), (t.GetEnd().x / MM, t.GetEnd().y / MM)
        g = LineString([a, z]).buffer(t.GetWidth() / MM / 2) if a != z else Point(a).buffer(t.GetWidth() / MM / 2)
        items.append(({t.GetLayer()}, g, 'trk'))
for i in range(len(zs)):
    z = zs[i]
    if z.GetNetname() != NET:
        continue
    for l in z.GetLayerSet().Seq():
        fp = z.GetFilledPolysList(l)
        for j in range(fp.OutlineCount()):
            o = fp.COutline(j)
            pts = [(o.CPoint(k).x / MM, o.CPoint(k).y / MM) for k in range(o.PointCount())]
            if len(pts) >= 3:
                items.append(({l}, Polygon(pts).buffer(0), 'zone'))
n = len(items)
par = list(range(n))


def fd(a):
    while par[a] != a:
        par[a] = par[par[a]]
        a = par[a]
    return a


for i in range(n):
    for j in range(i + 1, n):
        if items[i][0] & items[j][0] and items[i][1].intersects(items[j][1]):
            par[fd(i)] = fd(j)
groups = {}
for i in range(n):
    groups.setdefault(fd(i), []).append(items[i][2])
pieces = [sorted(x for x in g if x not in ('via', 'trk', 'zone')) for g in groups.values()]
pieces = [p for p in pieces if p]
pieces.sort(key=len, reverse=True)
print('%s: %d piece(s) with pads' % (NET, len(pieces)))
for p in pieces:
    print('  %d pads: %s' % (len(p), ' '.join(p[:30]) + (' ...' if len(p) > 30 else '')))
