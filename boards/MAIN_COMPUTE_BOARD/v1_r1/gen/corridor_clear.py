import math
import re
import sys

import pcbnew

import pslib

# clear the STM32 <-> FPGA corridor of parts: every footprint whose courtyard touches the corridor box is
# moved to the nearest free spot outside it (and outside the area under the STM32), its stitching and the
# copper of its signal nets are ripped (re-routed afterwards; the ripped net names are written to
# corridor_nets.txt). parts on the stm32 half go to the BGA's north/south edges, the rest north/south of
# the corridor; the stm32 crystals go next to their balls on the far side.
# usage: corridor_clear.py <board> <nets_out>
PCB, OUT = sys.argv[1:3]
MM = 1e6
CB = (134.6, 83.0, 151.0, 109.0)
HAND = re.compile(r'^(DDR_|MEZZ_|GTP|/FPGA_GTP|SFP\d_(TD|RD)|USBH|USBHS|/MCU_IO/ETH_(TX|RX))|_[PN]$')
b = pcbnew.LoadBoard(PCB)
zs = b.Zones()
planes = {zs[i].GetNetname() for i in range(len(zs)) if not zs[i].GetIsRuleArea()} | {'GND'}
u11 = b.FindFootprintByReference('U11')
kc = u11.GetCourtyard(pcbnew.F_CrtYd).BBox()
K = (kc.GetLeft() / MM - 1.5, kc.GetTop() / MM - 1.5, kc.GetRight() / MM + 1.5, kc.GetBottom() / MM + 1.5)
hit = lambda c, q: c[0] < q[2] and c[2] > q[0] and c[1] < q[3] and c[3] > q[1]


class P(pslib.Placer):
    def ok(self, f, gap=0.15, ignore=()):
        c = self.crt(f)
        if hit(c, CB) or (f.IsFlipped() and hit(c, K)):
            return False
        return pslib.Placer.ok(self, f, gap, ignore)


pl = P(b)
movers = [r for r, f in pl.fps.items() if r not in ('U11', 'U100') and hit(pl.crt(f), CB)]
nets = set()
for r in movers:
    f = pl.fps[r]
    for k in range(len(f.Pads())):
        n = f.Pads()[k].GetNetname()
        if n and n not in planes and not n.startswith('unconnected') and not HAND.search(n):
            nets.add(n)
# rip: the movers' stitching, plus all copper of their signal nets
pl.rip(movers, nets=nets)
ballpos = {u11.Pads()[k].GetNetname(): (u11.Pads()[k].GetPosition().x / MM, u11.Pads()[k].GetPosition().y / MM)
           for k in range(len(u11.Pads()))}
cx, cy = (K[0] + K[2]) / 2, (K[1] + K[3]) / 2
moved = []
for r in sorted(movers, key=lambda r: -len(pl.fps[r].Pads())):
    f = pl.fps[r]
    x, y = f.GetPosition().x / MM, f.GetPosition().y / MM
    fn = {f.Pads()[k].GetNetname() for k in range(len(f.Pads()))}
    to_stm = [ballpos[n] for n in fn if n in ballpos and n not in planes]
    if to_stm:
        # crystal / stm32 signal part: beside its ball, on the side away from the corridor
        bx, by = to_stm[0]
        tx, ty = (bx, K[1] - 1.5) if by < cy else (bx, K[3] + 1.5)
    elif x > 142.0:
        # stm32 decap: along the BGA's north or south edge
        tx, ty = (min(max(x + 10.0, K[0] + 2), K[2] - 2), K[1] - 1.5) if y < cy else (min(max(x + 10.0, K[0] + 2), K[2] - 2), K[3] + 1.5)
    else:
        tx, ty = (x, CB[1] - 1.5) if y < (CB[1] + CB[3]) / 2 else (x, CB[3] + 1.5)
    bottom = f.IsFlipped()
    f.SetPosition(pcbnew.VECTOR2I(int(10 * MM), int(10 * MM)))
    try:
        got = pl.place(r, tx, ty, bottom=bottom, rmax=14.0)
    except SystemExit:
        got = pl.place(r, tx, ty, bottom=not bottom, rmax=14.0)
    moved.append((r, got))
b.Save(PCB)
open(OUT, 'w').write(' '.join(sorted(nets)) + '\n')
print('moved %d parts out of the corridor; ripped %d signal nets' % (len(moved), len(nets)))
for r, g in moved:
    print('  %-5s -> (%.2f, %.2f) rot %d, %.1f mm from target' % (r, g[0], g[1], g[2], g[3]))
