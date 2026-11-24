import json
import math
import re
import subprocess
import sys

import pcbnew

import proute
import pslib

# via-in-pad for bga balls that have no escape: every ball of a net that drc reports open, with no dogbone
# and no copper of its own, gets a 0.4/0.2 mm via in its pad (resin filled and capped at fab). the 0.8 mm
# stm32 pads of these balls grow from 0.325 to 0.4 mm so the via fits. other nets' tracks crossing the ball
# position on inner layers (at most 3 nets, never ddr / vita / transceivers / pairs) are ripped and listed
# in <board>.viprip for re-routing. usage: vipads.py <board>
PCB = sys.argv[1]
MM = 1e6
PROTECT = re.compile(r'^(DDR_|MEZZ_|GTP|/FPGA_GTP|SFP\d_(TD|RD)|USBH_D|USBHS)|_[PN]$')
RPT = PCB + '.vip.json'
subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--refill-zones', '-o', RPT, PCB],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
d = json.load(open(RPT))
opn = set()
for v in d.get('unconnected_items', []):
    m = re.search(r'\[([^\]]+)\]', v['items'][0]['description'])
    if m:
        opn.add(m.group(1))
r = pslib.Router(PCB, ['U11', 'U100'])
bd = r.bd
b = bd.b
zs = b.Zones()
planes = {zs[i].GetNetname() for i in range(len(zs)) if not zs[i].GetIsRuleArea()} | {'GND'}
grave = []
targets = []
for ref in ('U11', 'U100'):
    f = b.FindFootprintByReference(ref)
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        n = p.GetNetname()
        if n not in opn or n in planes:
            continue
        x, y = p.GetPosition().x / MM, p.GetPosition().y / MM
        own = any(abs(t[0] - x) < 0.01 and abs(t[1] - y) < 0.01 or abs(t[2] - x) < 0.01 and abs(t[3] - y) < 0.01
                  for t in bd.tracks if t[5] == n) or proute.existing_via(bd, (x, y), n, maxd=0.95)
        if not own:
            targets.append((ref, p, n, x, y))
print('balls of open nets without any escape: %d' % len(targets), flush=True)
ripnets = set()
placed = []
for ref, p, n, x, y in targets:
    if ref == 'U11' and p.GetSize().x < 0.4 * MM:
        p.SetSize(pcbnew.VECTOR2I(int(0.4 * MM), int(0.4 * MM)))
    # what crosses the ball on any layer, other than this net
    blk = set()
    for (xa, ya, xb, yb, hw, tn, ly) in bd.tracks:
        if tn == n:
            continue
        dx, dy = xb - xa, yb - ya
        L2 = dx * dx + dy * dy
        u = 0 if L2 == 0 else max(0, min(1, ((x - xa) * dx + (y - ya) * dy) / L2))
        if math.hypot(x - xa - u * dx, y - ya - u * dy) < 0.2 + hw + 0.09:
            blk.add(tn)
    for (vx, vy, vr, vn) in bd.vias:
        if vn != n and math.hypot(vx - x, vy - y) < 0.2 + vr + 0.09:
            blk.add(vn)
    if any(o in planes or PROTECT.search(o) for o in blk) or len(blk) > int(__import__("os").environ.get("VIP_MAXBLK", "3")):
        continue
    placed.append((ref, p.GetNumber(), n, x, y))
    ripnets |= blk
# rip the crossing nets' copper near the balls only: whole tracks that pass within reach of a placed via
ts = b.Tracks()
kill = []
for i in range(len(ts)):
    t = ts[i]
    if t.GetNetname() not in ripnets:
        continue
    if t.GetClass() == 'PCB_VIA':
        pts = [(t.GetPosition().x / MM, t.GetPosition().y / MM)]
        if any(math.hypot(pts[0][0] - x, pts[0][1] - y) < 0.7 for _, _, _, x, y in placed):
            kill.append(t)
        continue
    a = (t.GetStart().x / MM, t.GetStart().y / MM)
    z = (t.GetEnd().x / MM, t.GetEnd().y / MM)
    dx, dy = z[0] - a[0], z[1] - a[1]
    L2 = dx * dx + dy * dy
    for _, _, _, x, y in placed:
        u = 0 if L2 == 0 else max(0, min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / L2))
        if math.hypot(x - a[0] - u * dx, y - a[1] - u * dy) < 0.5:
            kill.append(t)
            break
for t in kill:
    b.Remove(t)
grave.extend(kill)
for ref, num, n, x, y in placed:
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM))))
    v.SetWidth(int(0.4 * MM))
    v.SetDrill(int(0.2 * MM))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetNet(b.FindNet(n))
    b.Add(v)
    grave.append(v)
b.Save(PCB)
open(PCB + '.viprip', 'w').write(' '.join(sorted(ripnets | {t[2] for t in placed})))
print('vias in pad: %d of %d (%s); crossing nets cut near them: %d' % (len(placed), len(targets),
      ' '.join('%s:%s' % (t[0], t[1]) for t in placed), len(ripnets)))
