import re
import sys

import pcbnew

# bring freerouting's new copper into the project board without touching anything else: import the
# session into a scratch copy, then add to the real board only tracks/vias on the routed (dsn) nets
# that the board does not already have. arcs and existing copper are never rewritten
PCB, SCRATCH, SES, DSN = sys.argv[1:5]
MM = 1e6
allowed = set()
net_block = open(DSN).read()
for m in re.finditer(r'^    \(net ("[^"]*"|\S+)', net_block, re.M):
    allowed.add(m.group(1).strip('"'))
b = pcbnew.LoadBoard(PCB)
c = pcbnew.LoadBoard(SCRATCH)
if not pcbnew.ImportSpecctraSES(c, SES):
    raise SystemExit('session import failed')


def key(t):
    if t.GetClass() == 'PCB_VIA':
        return ('v', t.GetNetname(), round(t.GetPosition().x / 1e3), round(t.GetPosition().y / 1e3))
    a = (round(t.GetStart().x / 1e3), round(t.GetStart().y / 1e3))
    z = (round(t.GetEnd().x / 1e3), round(t.GetEnd().y / 1e3))
    return ('t', t.GetNetname(), t.GetLayer()) + tuple(sorted([a, z]))


have = set()
segs, vias0 = {}, {}
ts = b.Tracks()
for i in range(len(ts)):
    t = ts[i]
    have.add(key(t))
    if t.GetClass() == 'PCB_VIA':
        vias0.setdefault(t.GetNetname(), []).append((t.GetPosition().x / MM, t.GetPosition().y / MM))
    else:
        segs.setdefault((t.GetNetname(), t.GetLayer()), []).append(
            (t.GetStart().x / MM, t.GetStart().y / MM, t.GetEnd().x / MM, t.GetEnd().y / MM))


def on_copper(net, layer, p, tol=0.03):
    for (x1, y1, x2, y2) in segs.get((net, layer), []):
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        u = 0 if L2 == 0 else max(0, min(1, ((p[0] - x1) * dx + (p[1] - y1) * dy) / L2))
        if ((p[0] - x1 - u * dx) ** 2 + (p[1] - y1 - u * dy) ** 2) ** 0.5 < tol:
            return True
    return False


def existing(t):
    # freerouting hands the locked copper back rounded to its 1 um grid: treat anything lying on
    # existing same-net copper as already there
    n = t.GetNetname()
    if t.GetClass() == 'PCB_VIA':
        p = (t.GetPosition().x / MM, t.GetPosition().y / MM)
        return any(abs(p[0] - v[0]) < 0.03 and abs(p[1] - v[1]) < 0.03 for v in vias0.get(n, []))
    a = (t.GetStart().x / MM, t.GetStart().y / MM)
    z = (t.GetEnd().x / MM, t.GetEnd().y / MM)
    return on_copper(n, t.GetLayer(), a) and on_copper(n, t.GetLayer(), z)
ct = c.Tracks()
nt = nv = 0
nets = set()
for i in range(len(ct)):
    t = ct[i]
    n = t.GetNetname()
    if n not in allowed or key(t) in have or t.GetClass() == 'PCB_ARC' or existing(t):
        continue
    net = b.FindNet(n)
    if t.GetClass() == 'PCB_VIA':
        v = pcbnew.PCB_VIA(b)
        v.SetPosition(t.GetPosition())
        v.SetWidth(pcbnew.Cast_to_PCB_VIA(t).GetWidth(pcbnew.F_Cu))
        v.SetDrill(pcbnew.Cast_to_PCB_VIA(t).GetDrillValue())
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(net)
        b.Add(v)
        nv += 1
    else:
        s = pcbnew.PCB_TRACK(b)
        s.SetStart(t.GetStart())
        s.SetEnd(t.GetEnd())
        s.SetWidth(t.GetWidth())
        s.SetLayer(t.GetLayer())
        s.SetNet(net)
        b.Add(s)
        nt += 1
    nets.add(n)
b.Save(PCB)
print('added %d tracks, %d vias on %d nets' % (nt, nv, len(nets)))
