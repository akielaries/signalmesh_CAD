import json
import math
import os
import re
import sys

import numpy as np
from scipy.optimize import linear_sum_assignment

import proute
import pslib

# move open flexible fpga nets (sfp sideband, pmod, tdm data, leds, debug uart) to the 3.3 V io balls
# (banks 13/14/15) that can actually escape: the pool is these nets' own balls plus the spare io balls; each
# net takes the ball that is near where it goes, shallow, and has a dogbone (or room for one). routed nets
# never move. writes ball_remap.json {net: ball}, applied by dfpga.py. usage: flexmove.py <board>
PCB = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
FLEX = re.compile(r'^(PMOD[AB]_IO\d|SFP[01]_(LOS|MOD_ABS|SCL|SDA|TX_DIS|TX_FAULT)|AUD_DAC_(LRCK|MCLK|SCLK|SDIN)|'
                  r'FPGA_LED\d|FPGA_BTN\d|SC_(UART_TX|UART_RX|SWO|SWDIO|SWCLK|NRST)|BP_TDM_(FS|DOUT|DIN))$')
r = pslib.Router(PCB, ['U100'])
bd = r.bd
u = bd.b.FindFootprintByReference('U100')
cx, cy = u.GetPosition().x / 1e6, u.GetPosition().y / 1e6
lib = open('/usr/share/kicad/symbols/FPGA_Xilinx_Artix7.kicad_sym').read()
i = lib.find('(symbol "XC7A100T-FGG484"')
j = lib.find('\n\t(symbol "', i + 10)
blk = lib[i:j if j > 0 else len(lib)]
pinname = {m.group(2): m.group(1) for m in re.finditer(r'\(name "([^"]+)".*?\(number "([^"]+)"', blk, re.S)}
balls = {}
for k in range(len(u.Pads())):
    p = u.Pads()[k]
    nm = pinname.get(p.GetNumber(), '')
    bank = re.search(r'_(\d+)$', nm)
    if nm.startswith('IO_') and bank and bank.group(1) in ('13', '14', '15'):
        balls[p.GetNumber()] = (p.GetNetname(), p.GetPosition().x / 1e6, p.GetPosition().y / 1e6, nm)


def complete(n):
    ts = r.terms(n)
    return len(ts) > 1 and len(set(r.comp(n, ts))) == 1


movers = sorted({v[0] for v in balls.values() if FLEX.match(v[0]) and not complete(v[0])})
spare = [b for b, v in balls.items() if v[0].startswith('unconnected') or not v[0]]
# dual-purpose config pins stay out of the pool (selectmap, emcclk...) unless they are plain io
spare = [b for b in spare if not re.search(r'_(D\d\d|A\d\d|FCS|EMCCLK|CSI|RDWR|PUDC|DOUT|MOSI|DIN|RS\d)', balls[b][3])]
pool = sorted({b for b, v in balls.items() if v[0] in movers} | set(spare))
dest = {}
for n in movers:
    pts = [t[1] for t in r.terms(n) if not t[0].startswith('U100:')]
    dest[n] = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
H = 0.5


def escapable(ball):
    net, x, y, nm = balls[ball]
    if proute.existing_via(bd, (x, y), net, maxd=0.95):
        return True
    for sx in (-1, 1):
        for sy in (-1, 1):
            if proute.via_spot_exact(bd, x + sx * H, y + sy * H, net or 'xx'):
                return True
    return min(10.5 - abs(x - cx), 10.5 - abs(y - cy)) < 0.6     # outer ring: escapes on F.Cu


esc = {b: escapable(b) for b in pool}
depth = {b: max(0.0, min(10.5 - abs(balls[b][1] - cx), 10.5 - abs(balls[b][2] - cy))) for b in pool}
cost = np.zeros((len(movers), len(pool)))
for a, n in enumerate(movers):
    for c, b in enumerate(pool):
        _, x, y, _ = balls[b]
        cost[a, c] = 0.3 * math.hypot(x - dest[n][0], y - dest[n][1]) + 6.0 * depth[b] + (0 if esc[b] else 60)
cur = {n: [b for b, v in balls.items() if v[0] == n][0] for n in movers}
before = sum(cost[a, pool.index(cur[n])] for a, n in enumerate(movers))
ra, ca = linear_sum_assignment(cost)
after = cost[ra, ca].sum()
remap = {movers[a]: pool[c] for a, c in zip(ra, ca) if pool[c] != cur[movers[a]]}
json.dump(remap, open(os.path.join(HERE, 'ball_remap.json'), 'w'), indent=1, sort_keys=True)
print('open flexible nets %d, pool %d balls (%d spare, %d escapable); cost %.0f -> %.0f; %d nets move'
      % (len(movers), len(pool), len(spare), sum(esc.values()), before, after, len(remap)))
for n, b in sorted(remap.items()):
    print('  %-15s %s (d%.0f%s) -> %s (d%.0f%s)' % (n, cur[n], depth[cur[n]], '' if esc[cur[n]] else ' boxed', b, depth[b], '' if esc[b] else ' boxed'))
