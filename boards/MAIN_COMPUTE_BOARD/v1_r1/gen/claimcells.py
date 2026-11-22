import math
import re
import subprocess
import sys

import proute
import pslib

# bga balls of open nets with no dogbone and no free diagonal cell: take the cell whose occupants are fewest
# (other nets' vias and tracks over it; planes and protected groups are never moved), rip those nets, and
# put the dogbone there. the ripped nets are re-routed afterwards (drcpairs.py). usage: claimcells.py <board>
PCB = sys.argv[1]
PROTECT = re.compile(r'^(DDR_|MEZZ_|GTP|/FPGA_GTP|SFP\d_(TD|RD)|USBH_D|USBHS)|_[PN]$')
r = pslib.Router(PCB, ['U11', 'U100'])
bd = r.bd
zs = bd.b.Zones()
planes = {zs[i].GetNetname() for i in range(len(zs)) if not zs[i].GetIsRuleArea()} | {'GND'}
claims, ripset = [], set()
for ref, h in (('U11', 0.4), ('U100', 0.5)):
    f = bd.b.FindFootprintByReference(ref)
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        n = p.GetNetname()
        if not n or n.startswith('unconnected') or n in planes or PROTECT.search(n):
            continue
        x, y = p.GetPosition().x / 1e6, p.GetPosition().y / 1e6
        if any(abs(t[0] - x) < 0.01 and abs(t[1] - y) < 0.01 or abs(t[2] - x) < 0.01 and abs(t[3] - y) < 0.01
               for t in bd.tracks if t[5] == n) or proute.existing_via(bd, (x, y), n, maxd=0.95):
            continue
        ts = r.terms(n)
        if len(ts) < 2 or len(set(r.comp(n, ts))) == 1:
            continue
        best = None
        for sx in (-1, 1):
            for sy in (-1, 1):
                q = (x + sx * h, y + sy * h)
                occ = {vn for (vx, vy, vr, vn) in bd.vias if vn != n and math.hypot(vx - q[0], vy - q[1]) < 0.5}
                for (xa, ya, xb, yb, hw, tn, ly) in bd.tracks:
                    if tn == n:
                        continue
                    dx, dy = xb - xa, yb - ya
                    L2 = dx * dx + dy * dy
                    u = 0 if L2 == 0 else max(0, min(1, ((q[0] - xa) * dx + (q[1] - ya) * dy) / L2))
                    if math.hypot(q[0] - xa - u * dx, q[1] - ya - u * dy) < 0.2 + hw + 0.1:
                        occ.add(tn)
                # the pad's own surface stub must not cross other copper on F.Cu either
                if any(o in planes or PROTECT.search(o) for o in occ):
                    continue
                if best is None or len(occ) < len(best[1]):
                    best = (q, occ)
        if best and len(best[1]) <= 3:
            claims.append((n, (x, y), best[0]))
            ripset |= best[1]
print('balls to claim: %d; nets to rip: %d %s' % (len(claims), len(ripset), ' '.join(sorted(ripset))[:300]), flush=True)
open(PCB + '.claim', 'w').write(repr(claims))
open(PCB + '.ripset', 'w').write(' '.join(sorted(ripset)))
