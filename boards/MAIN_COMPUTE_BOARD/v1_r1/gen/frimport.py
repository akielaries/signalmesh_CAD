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
ts = b.Tracks()
for i in range(len(ts)):
    have.add(key(ts[i]))
ct = c.Tracks()
nt = nv = 0
nets = set()
for i in range(len(ct)):
    t = ct[i]
    n = t.GetNetname()
    if n not in allowed or key(t) in have or t.GetClass() == 'PCB_ARC':
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
