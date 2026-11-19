import math
import sys
import time

import ddr
import proute
import rlib

# rmii + mdc/mdio: stm32 (top) to the lan8742 (top, left of the ddr). 50 MHz, no matching needed
# (setup/hold margin is several ns). a via beside each pin (or a straight f.cu run), one layer
# between, ddr region and fpga ball field blocked. additive, skips connected nets
PCB = sys.argv[1]
rlib.BGA_RECTS[:] = []
proute.ESC[:] = []
rlib.TIGHT = True
W = {'In5.Cu': 0.23, 'In2.Cu': 0.23, 'B.Cu': 0.127, 'F.Cu': 0.127}
CLR = 0.127
MARGIN = 28.0
OUTER = tuple(0.75 + 0.25 * i for i in range(30))
DDR_BLOCK = [(95.0, 94.0), (121.2, 94.0), (121.2, 135.5), (95.0, 135.5)]
FPGA_BLOCK = [(109.5, 79.5), (134.5, 79.5), (134.5, 104.5), (109.5, 104.5)]
NETS = ['ETH_CRS_DV', 'ETH_RXD0', 'ETH_RXD1', 'ETH_TXD0', 'ETH_TXD1', 'ETH_TX_EN', 'ETH_REF_CLK', 'ETH_MDC', 'ETH_MDIO']

bd = rlib.Board(PCB)
bd.keepouts.append((DDR_BLOCK, set(rlib.LAYERS)))
bd.keepouts.append((FPGA_BLOCK, set(rlib.LAYERS)))
STM = ddr.ref_of(bd, 'STM32H755')
PHY = ddr.ref_of(bd, 'LAN8742')
ends = {}
for (x, y, hx, hy, n, lays, rnd, p) in bd.pads:
    if n in NETS:
        ends.setdefault(n, []).append((p.GetParentFootprint().GetReference(), (x, y)))


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


def pin(net, ref):
    return [p for r, p in ends[net] if r == ref][0]


done, fail = [], []
order = sorted(NETS, key=lambda n: math.hypot(pin(n, STM)[0] - pin(n, PHY)[0], pin(n, STM)[1] - pin(n, PHY)[1]))
for net in order:
    s, e = pin(net, STM), pin(net, PHY)
    extra = [p for r, p in ends[net] if r not in (STM, PHY)]
    if connected(net, s, e) and all(connected(net, e, x) for x in extra):
        continue
    t0 = time.time()
    st = []
    got = None
    pts = bd.path('F.Cu', s, e, W['F.Cu'] / 2, {net}, CLR, margin=MARGIN)
    if pts:
        bd.stage_track(pts, W['F.Cu'], net, 'F.Cu', st)
        got = 'F.Cu'
    else:
        va = proute.drop_via(bd, s, net, e, st, radii=OUTER)
        vb = proute.drop_via(bd, e, net, s, st, radii=OUTER) if va else None
        if va and vb:
            for ly in ('In5.Cu', 'In2.Cu', 'B.Cu'):
                pts = bd.path(ly, va, vb, W[ly] / 2, {net}, CLR, margin=MARGIN)
                if pts:
                    bd.stage_track(pts, W[ly], net, ly, st)
                    got = ly
                    break
        else:
            got = None
    # pull-ups etc beside the phy: short top run from the phy pin
    for x in extra if got else []:
        pts = bd.path('F.Cu', e, x, W['F.Cu'] / 2, {net}, CLR, margin=3.0)
        if not pts:
            got = None
            break
        bd.stage_track(pts, W['F.Cu'], net, 'F.Cu', st)
    if got:
        bd.commit(st)
        L = sum(math.hypot(b_[0] - a[0], b_[1] - a[1]) for a, b_ in zip(pts, pts[1:])) if pts else 0
        done.append((net, got))
        print('%-12s %-7s (%.0fs)' % (net, got, time.time() - t0), flush=True)
    else:
        bd.unstage(st)
        fail.append(net)
        print('%-12s open (%.0fs)' % (net, time.time() - t0), flush=True)
bd.save()
print('rmii: routed %d of %d; open: %s' % (len(done), len(NETS), fail))
