import sys

import pcbnew

# plane hookups that never reach their plane: with all zones filled, a via on a plane net that touches no
# filled copper of its net on any layer (it sits in a void or in another rail's region) is removed together
# with the track stubs that only lead to it; planestitch.py then re-stitches the orphaned pads.
# usage: fixplanevias.py <board>
PCB = sys.argv[1]
MM = 1e6
b = pcbnew.LoadBoard(PCB)
zs = b.Zones()
pcbnew.ZONE_FILLER(b).Fill([zs[i] for i in range(len(zs))])
zs = b.Zones()
byn = {}
for i in range(len(zs)):
    z = zs[i]
    if not z.GetIsRuleArea():
        byn.setdefault(z.GetNetname(), []).append(z)
ts = b.Tracks()
items = [ts[i] for i in range(len(ts))]
kill, keep = [], []
for v in items:
    if v.GetClass() != 'PCB_VIA' or v.GetNetname() not in byn:
        continue
    p = v.GetPosition()
    hit = any(z.HitTestFilledArea(ly, p, int(0.1 * MM)) for z in byn[v.GetNetname()] for ly in z.GetLayerSet().Seq())
    if hit:
        continue
    kill.append(v)
    # stubs ending on this via
    for t in items:
        if t.GetClass() != 'PCB_VIA' and t.GetNetname() == v.GetNetname() and (t.GetStart() == p or t.GetEnd() == p):
            kill.append(t)
for it in {id(k): k for k in kill}.values():
    b.Remove(it)
keep = kill
b.Save(PCB)
print('removed %d plane vias touching no filled copper of their net, with their stubs (%d items)'
      % (sum(1 for k in kill if k.GetClass() == 'PCB_VIA'), len(kill)))
