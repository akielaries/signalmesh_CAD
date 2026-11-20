import re
import sys

import pslib

# low-speed leftovers: nets in the routing guide's "everything else" group plus enable / power-good
# lines, joined leg by leg with the pslib router (legs already joined are skipped). the hand-routed
# groups and power rails are left alone
PCB = sys.argv[1]
r = pslib.Router(PCB, [])
T = r.terms
zs = r.bd.b.Zones()
planes = {zs[i].GetNetname() for i in range(len(zs))} | {'GND'}
HAND = re.compile(r'^(DDR_|FMC_|FPGA_D|QSPI_|ETH_|ULPI_|/MCU_IO/ETH_(TX|RX)|USBH|USBHS|VBUS|MEZZ_|GTP|SFP\d_(TD|RD)|/FPGA_GTP)')
RAIL = re.compile(r'^(\+|-5V|VADJ$|VTT|VREF|ETH_AVDD|ETH_VDDCR|/POWER/SW_|/POWER/BOOT_|/POWER/12V)')
nets = {}
for (x, y, hx, hy, n, lays, rnd, p) in r.bd.pads:
    if n and not n.startswith('unconnected') and n not in planes and not HAND.match(n) and not RAIL.match(n):
        nets.setdefault(n, 0)
        nets[n] += 1
before = 0
todo = []
for n in sorted(nets):
    ts = T(n)
    if len(ts) >= 2 and len(set(r.comp(n, ts))) > 1:
        todo.append(n)
print('open low-speed nets considered: %d' % len(todo))
for n in todo:
    r.net(n, T(n), 0.15 if n.startswith(('/POWER/', 'PG_')) else 0.127, inner=('In2.Cu', 'In5.Cu'))
r.bd.save()
done = [n for n in todo if len(set(r.comp(n, T(n)))) == 1]
print('completed %d: %s' % (len(done), ' '.join(done[:40])))
print('still open %d' % (len(todo) - len(done)))
