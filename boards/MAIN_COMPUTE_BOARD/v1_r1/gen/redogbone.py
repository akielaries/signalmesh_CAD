import math
import sys

import proute
import pslib

# put back dogbones on bga balls of open nets that have no copper at all: a via at a free diagonal cell
# centre with a 0.1 mm stub (outer-ring balls without room stay as they are, they escape on the surface)
# usage: redogbone.py <board>
PCB = sys.argv[1]
r = pslib.Router(PCB, ['U11', 'U100'])
bd = r.bd
zs = bd.b.Zones()
planes = {zs[i].GetNetname() for i in range(len(zs)) if not zs[i].GetIsRuleArea()} | {'GND'}
made, skip = 0, 0
for ref, h in (('U11', 0.4), ('U100', 0.5)):
    f = bd.b.FindFootprintByReference(ref)
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        n = p.GetNetname()
        if not n or n.startswith('unconnected') or n in planes:
            continue
        x, y = p.GetPosition().x / 1e6, p.GetPosition().y / 1e6
        has = any(abs(t[0] - x) < 0.01 and abs(t[1] - y) < 0.01 or abs(t[2] - x) < 0.01 and abs(t[3] - y) < 0.01
                  for t in bd.tracks if t[5] == n)
        if has or proute.existing_via(bd, (x, y), n, maxd=0.95):
            continue
        ts = r.terms(n)
        if len(ts) > 1 and len(set(r.comp(n, ts))) == 1:
            continue
        done = False
        for sx in (-1, 1):
            for sy in (-1, 1):
                q = (x + sx * h, y + sy * h)
                if proute.via_spot_exact(bd, q[0], q[1], n):
                    st = []
                    bd.stage_track([(x, y), q], 0.1, n, 'F.Cu', st)
                    bd.stage_via(q[0], q[1], n, st, d=0.4)
                    bd.commit(st)
                    made += 1
                    done = True
                    break
            if done:
                break
        if not done:
            skip += 1
bd.save()
print('dogbones restored: %d; balls without a free cell: %d' % (made, skip))
