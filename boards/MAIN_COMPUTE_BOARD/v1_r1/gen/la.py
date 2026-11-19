import math
import os
import sys

import ddr
import proute
import rlib

# vita 57.1 la pairs + clk0/1_m2c: coupled 100 ohm pairs from the connector to fpga banks 35/16.
# additive (keeps everything on the board), skips pairs already connected, ddr area blocked
PCB = sys.argv[1]
FPGA_R = (109.5, 79.5, 134.5, 104.5)
rlib.BGA_RECTS[:] = [FPGA_R + (0.09,), (120.8, 62.35, 179.3, 76.65, 0.10)]
proute.ESC[:] = [FPGA_R]
CLR = 0.15
LAYERS = tuple(os.environ.get('LA_LAYERS', 'F.Cu,In2.Cu,In5.Cu,B.Cu').split(','))
DDR_BLOCK = [(95.0, 94.0), (121.2, 94.0), (121.2, 135.5), (95.0, 135.5)]

bd = rlib.Board(PCB)
bd.keepouts.append((DDR_BLOCK, set(rlib.LAYERS)))


def pads_of(ref):
    return {n: (x, y) for (x, y, hx, hy, n, lays, rnd, p) in bd.pads if p.GetParentFootprint().GetReference() == ref and n}


fu, fj = pads_of('U100'), pads_of('J20')
pairs = sorted(n[:-2] for n in set(fu) & set(fj) if n.startswith(('MEZZ_LA', 'MEZZ_CLK')) and n.endswith('_P'))
pairs.sort(key=lambda p: math.hypot(fu[p + '_P'][0] - fj[p + '_P'][0], fu[p + '_P'][1] - fj[p + '_P'][1]))


def connected(net, a, b_):
    k = lambda x, y: (round(x, 3), round(y, 3))
    g = {}
    for (xa, ya, xb, yb, hw, n, ly) in bd.tracks:
        if n == net:
            g.setdefault(k(xa, ya), set()).add(k(xb, yb))
            g.setdefault(k(xb, yb), set()).add(k(xa, ya))
    seen, todo = {k(*a)}, [k(*a)]
    while todo:
        x = todo.pop()
        if x == k(*b_):
            return True
        for y in g.get(x, ()):
            if y not in seen:
                seen.add(y)
                todo.append(y)
    return False


done, fail, skip = [], [], 0
for base in pairs:
    p, n = base + '_P', base + '_N'
    if connected(p, fu[p], fj[p]) and connected(n, fu[n], fj[n]):
        skip += 1
        continue
    s, l = proute.route_pair_any(bd, p, n, fu[p], fu[n], fj[p], fj[n], CLR, layers=LAYERS)
    if s:
        bd.commit(s)
        done.append((base, l[0] if isinstance(l, tuple) else '?'))
    else:
        fail.append(base)
bd.save()
print('la pairs: %d routed now, %d already routed, %d open of %d' % (len(done), skip, len(fail), len(pairs)))
print('by layer', {ly: sum(1 for _, x in done if x == ly) for ly in LAYERS})
print('open:', fail)
