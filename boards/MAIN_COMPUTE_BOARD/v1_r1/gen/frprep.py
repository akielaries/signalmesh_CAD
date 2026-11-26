import math
import re
import sys

import pcbnew

# prepare a board for a clean freerouting pass: keep (and lock) the copper worth keeping - planes and
# power nets, ddr, vita la, transceiver / usb / ethernet pairs, and the bga fanout (dogbone stubs and
# vias within FAN mm of a same-net ball of U11 / U100 / U21) of every other net - and remove all other
# signal tracks and vias. then export the specctra dsn. usage: frprep.py <board> <out.dsn>
PCB, DSN = sys.argv[1], sys.argv[2]
MM = 1e6
FAN = 0.95
KEEP = re.compile(r'^(\+|-|GND|VTT|VADJ|VCC|VREF|/POWER/|DDR_|/DDR3/|MEZZ_|GTP|/FPGA_GTP|SFP\d_(TD|RD)|USB|ETH_(TX|RX)[PN]|/MCU_IO/ETH_(TX|RX)[PN]|ETH_AVDD|/MCU_IO/ULPI_1V8)')
b = pcbnew.LoadBoard(PCB)
zs = b.Zones()
planes = {zs[i].GetNetname() for i in range(len(zs)) if not zs[i].GetIsRuleArea()}
balls = {}
for ref in ('U11', 'U100', 'U21'):
    f = b.FindFootprintByReference(ref)
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        balls.setdefault(p.GetNetname(), []).append((p.GetPosition().x / MM, p.GetPosition().y / MM))


def near_ball(n, x, y):
    return any(math.hypot(x - bx, y - by) <= FAN for bx, by in balls.get(n, ()))


ts = b.Tracks()
kill, keep = [], 0
for i in range(len(ts)):
    t = ts[i]
    n = t.GetNetname()
    if n in planes or KEEP.search(n):
        t.SetLocked(True)
        keep += 1
        continue
    if t.GetClass() == 'PCB_VIA':
        ok = near_ball(n, t.GetPosition().x / MM, t.GetPosition().y / MM)
    else:
        ok = near_ball(n, t.GetStart().x / MM, t.GetStart().y / MM) and near_ball(n, t.GetEnd().x / MM, t.GetEnd().y / MM)
    if ok:
        t.SetLocked(True)
        keep += 1
    else:
        kill.append(t)
ripped = sorted({t.GetNetname() for t in kill})
for t in kill:
    b.Remove(t)
b.Save(PCB)
if not pcbnew.ExportSpecctraDSN(b, DSN):
    raise SystemExit('dsn export failed')
open(PCB + '.ripped', 'w').write('\n'.join(ripped))
print('kept and locked %d items; removed %d items on %d nets; dsn written' % (keep, len(kill), len(ripped)))
