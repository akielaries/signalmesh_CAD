import json
import math
import os
import re
import sys

import numpy as np
import pcbnew

import pslib
from scipy.optimize import linear_sum_assignment

# fpga pin swap for the flexible 3.3 V nets (pmods, sfp sideband, audio dac, irqs, leds, buttons, uarts,
# soft-core debug, tdm data): re-assigned over the balls they already occupy in banks 13/14/15 (all
# LVCMOS33) so each lands on the ball nearest where it goes, favouring the outer rows that escape easily.
# clocks, configuration pins and the fmc bus stay put. writes flex_swap.json {net now on a ball: net it
# carries}, applied by dfpga.py. usage: flexswap.py <board>
b = pcbnew.LoadBoard(sys.argv[1])
HERE = os.path.dirname(os.path.abspath(__file__))
FLEX = re.compile(r'^(PMOD[AB]_IO\d|SFP[01]_(LOS|MOD_ABS|SCL|SDA|TX_DIS|TX_FAULT|RS)|/FPGA_GTP/SFP[01]_RS|AUD_DAC_(LRCK|MCLK|SCLK|SDIN)|'
                  r'FPGA_IRQ\d|FPGA_LED\d|FPGA_BTN\d|MCU_UART_(TX|RX)|SC_(UART_TX|UART_RX|SWO|SWDIO|SWCLK|NRST)|'
                  r'BP_TDM_(FS|DOUT|DIN)|FPGA_RST_N)$')
txt = open(os.path.join(HERE, '..', 'docs', 'pinout.md')).read()
bank_of = {}
for sec in re.finditer(r'^### bank (\d+) \(VCCO ([^)]+)\)\n(.*?)(?=^#)', txt, re.M | re.S):
    for m in re.finditer(r'^\| (\w+) \| (\w+) \| ([^ |]+) \|', sec.group(3), re.M):
        bank_of[m.group(1)] = (sec.group(1), m.group(2))
u = b.FindFootprintByReference('U100')
ux, uy = u.GetPosition().x / 1e6, u.GetPosition().y / 1e6
balls = {}
for k in range(len(u.Pads())):
    p = u.Pads()[k]
    n = p.GetNetname()
    bk = bank_of.get(p.GetNumber(), ('', ''))[0]
    if bk in ('13', '14', '15') and FLEX.match(n):
        balls[p.GetNumber()] = (n, p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)
# destination of each net: centroid of its pads off the fpga
dest = {}
for f in b.Footprints():
    if f.GetReference() == 'U100':
        continue
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        if p.GetNetname() in {v[0] for v in balls.values()}:
            dest.setdefault(p.GetNetname(), []).append((p.GetPosition().x / 1e6, p.GetPosition().y / 1e6))
# only nets that are still open move: routed ones keep their copper
r = pslib.Router(sys.argv[1], [])
T = {}
for (x, y, hx, hy, n, lays, rnd, p) in r.bd.pads:
    if n in {v[0] for v in balls.values()}:
        T.setdefault(n, []).append((p.GetParentFootprint().GetReference() + ':' + p.GetNumber(), (x, y), lays, (hx, hy)))
openn = {n for n, ts in T.items() if len(ts) > 1 and len(set(r.comp(n, ts))) > 1}
balls = {k: v for k, v in balls.items() if v[0] in openn}
nets = sorted({v[0] for v in balls.values()})
print('open flexible nets: %d' % len(nets))
bl = sorted(balls)
half = 10.5      # fgg484: 22 x 22 balls, 1 mm pitch


def depth(x, y):
    # rows in from the package edge (0 = outer ring)
    return min(half - abs(x - ux), half - abs(y - uy))


cost = np.zeros((len(nets), len(bl)))
for i, n in enumerate(nets):
    pts = dest.get(n, [(ux, uy)])
    cx, cy = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    for j, ball in enumerate(bl):
        _, x, y = balls[ball]
        cost[i, j] = math.hypot(x - cx, y - cy) + 3.0 * max(0.0, depth(x, y))
before = sum(cost[nets.index(balls[ball][0]), j] for j, ball in enumerate(bl))
r_, c_ = linear_sum_assignment(cost)
after = cost[r_, c_].sum()
swap = {}
for i, j in zip(r_, c_):
    old = balls[bl[j]][0]
    if old != nets[i]:
        swap[old] = nets[i]
json.dump(swap, open(os.path.join(HERE, 'flex_swap.json'), 'w'), indent=1, sort_keys=True)
print('flexible nets: %d on %d balls; cost %.0f -> %.0f; %d nets move' % (len(nets), len(bl), before, after, len(swap)))
