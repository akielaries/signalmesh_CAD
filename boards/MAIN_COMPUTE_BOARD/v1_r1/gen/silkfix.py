import json
import subprocess
import sys

import pcbnew

# silkscreen cleanup for reference designators: every reference text that drc flags (over a pad's mask
# opening, overlapping other silk, or clipped by the board edge) is moved to the first spot around its
# footprint where it clears pads, other silk and the edge; a 2-character-high shrink is tried next, and
# passives that still have no room get their reference hidden (it stays on the fab layer).
# usage: silkfix.py <board>
PCB = sys.argv[1]
MM = 1e6
RPT = PCB + '.silk.json'
subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', RPT, PCB],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
d = json.load(open(RPT))
flag = set()
for v in d.get('violations', []):
    if v['type'] in ('silk_over_copper', 'silk_overlap', 'silk_edge_clearance'):
        for it in v.get('items', []):
            flag.add(it.get('uuid'))
b = pcbnew.LoadBoard(PCB)
edge = b.GetBoardEdgesBoundingBox()
E = (edge.GetLeft() / MM + 0.3, edge.GetTop() / MM + 0.3, edge.GetRight() / MM - 0.3, edge.GetBottom() / MM - 0.3)


def box(bb, grow=0.0):
    return (bb.GetLeft() / MM - grow, bb.GetTop() / MM - grow, bb.GetRight() / MM + grow, bb.GetBottom() / MM + grow)


hit = lambda a, c: a[0] < c[2] and a[2] > c[0] and a[1] < c[3] and a[3] > c[1]
_fs = b.Footprints()
fps = [_fs[i] for i in range(len(_fs))]
obst = {pcbnew.F_SilkS: [], pcbnew.B_SilkS: []}
for f in fps:
    side = pcbnew.B_SilkS if f.IsFlipped() else pcbnew.F_SilkS
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        for s in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            if (s == pcbnew.F_SilkS and p.IsOnLayer(pcbnew.F_Mask)) or (s == pcbnew.B_SilkS and p.IsOnLayer(pcbnew.B_Mask)):
                obst[s].append(('pad', box(p.GetBoundingBox(), 0.1)))
    gi = f.GraphicalItems()
    for gk in range(len(gi)):
        g = gi[gk]
        if g.GetLayer() in obst:
            obst[g.GetLayer()].append(('g', box(g.GetBoundingBox(), 0.05)))
texts = []
for f in fps:
    rf = f.Reference()
    if rf.GetLayer() in obst and rf.IsVisible():
        texts.append((f, rf))
        obst[rf.GetLayer()].append((rf.m_Uuid.AsString(), box(rf.GetBoundingBox(), 0.05)))
moved = shrunk = hidden = 0
for f, rf in texts:
    if rf.m_Uuid.AsString() not in flag:
        continue
    ly = rf.GetLayer()
    me = rf.m_Uuid.AsString()
    others = [o for o in obst[ly] if o[0] != me]
    fb = box(f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd).BBox() if
             f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd).OutlineCount() else f.GetBoundingBox(False, False))
    ok = None
    for size in (None, 0.8):
        if size:
            rf.SetTextSize(pcbnew.VECTOR2I(int(size * MM), int(size * MM)))
            rf.SetTextThickness(int(size * 0.15 * MM))
        tb = box(rf.GetBoundingBox())
        w, h = tb[2] - tb[0], tb[3] - tb[1]
        cx, cy = (fb[0] + fb[2]) / 2, (fb[1] + fb[3]) / 2
        cands = [(cx, fb[1] - h / 2 - 0.15), (cx, fb[3] + h / 2 + 0.15), (fb[0] - w / 2 - 0.15, cy), (fb[2] + w / 2 + 0.15, cy)]
        for step in (0.5, 1.0, 1.5):
            cands += [(cx, fb[1] - h / 2 - 0.15 - step), (cx, fb[3] + h / 2 + 0.15 + step),
                      (fb[0] - w / 2 - 0.15 - step, cy), (fb[2] + w / 2 + 0.15 + step, cy)]
        for (x, y) in cands:
            nb = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
            if nb[0] < E[0] or nb[1] < E[1] or nb[2] > E[2] or nb[3] > E[3]:
                continue
            if any(hit(nb, o[1]) for o in others):
                continue
            ok = (x, y)
            break
        if ok:
            break
    if ok:
        rf.SetPosition(pcbnew.VECTOR2I(int(ok[0] * MM), int(ok[1] * MM)))
        obst[ly] = others + [(me, box(rf.GetBoundingBox(), 0.05))]
        moved += 1
        shrunk += 1 if rf.GetTextSize().x < 0.9 * MM else 0
    elif f.GetReference()[:1] in ('C', 'R', 'L', 'D', 'F') or f.GetReference().startswith('FB') or f.GetReference().startswith('TP'):
        rf.SetVisible(False)
        obst[ly] = others
        hidden += 1
b.Save(PCB)
print('references flagged %d; moved %d (%d at 0.8 mm), hidden %d' % (sum(1 for f, rf in texts if rf.m_Uuid.AsString() in flag), moved, shrunk, hidden))
