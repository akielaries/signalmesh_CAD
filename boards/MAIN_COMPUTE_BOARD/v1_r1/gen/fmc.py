import math
import sys

import ddr
import proute
import rlib

# stm32 fmc + fpga config lines, stm32 lqfp <-> fpga banks 14/15. completion routing (125 MHz, timing
# budget ~8 ns: a few mm of skew is irrelevant). additive: loads the project board, adds what routes,
# saves. the ddr region is blocked so this never touches it
PCB = sys.argv[1]
FPGA_R = (109.5, 79.5, 134.5, 104.5)
rlib.BGA_RECTS[:] = [FPGA_R + (0.09,), (120.8, 62.35, 179.3, 76.65, 0.10)]
proute.ESC[:] = [FPGA_R]
rlib.TIGHT = True
W = {'F.Cu': 0.127, 'B.Cu': 0.127, 'In2.Cu': 0.23, 'In5.Cu': 0.23}   # SE50
CLR = 0.127
DDR_BLOCK = [(95.0, 94.0), (121.2, 94.0), (121.2, 135.5), (95.0, 135.5)]

bd = rlib.Board(PCB)
bd.keepouts.append((DDR_BLOCK, set(rlib.LAYERS)))
STM = ddr.ref_of(bd, 'STM32H755')


def pads_of(ref):
    out = {}
    for (x, y, hx, hy, n, lays, rnd, p) in bd.pads:
        if p.GetParentFootprint().GetReference() == ref and n:
            out[n] = (x, y)
    return out


fp, sp = pads_of('U100'), pads_of(STM)
nets = sorted(n for n in set(fp) & set(sp) if n.startswith(('FMC_', 'FPGA_')))
nets.sort(key=lambda n: math.hypot(fp[n][0] - sp[n][0], fp[n][1] - sp[n][1]))
done, fail = [], []
OUTER = tuple(0.75 + 0.25 * i for i in range(22))   # up to 6 mm from the pin


def neck(pts, net, ly, st):
    for seg, inside in rlib.split_neck(pts):
        bd.stage_track(seg, 0.1 if inside else W[ly], net, ly, st)


def connected(net, a, b_):
    # copper path between the two pads already (a previous pass routed it)
    k = lambda x, y: (round(x, 3), round(y, 3))
    g = {}
    for (xa, ya, xb, yb, hw, n, ly) in bd.tracks:
        if n == net:
            g.setdefault(k(xa, ya), set()).add(k(xb, yb))
            g.setdefault(k(xb, yb), set()).add(k(xa, ya))
    seen, todo = {k(*a)}, [k(*a)]
    while todo:
        u = todo.pop()
        if u == k(*b_):
            return True
        for v in g.get(u, ()):
            if v not in seen:
                seen.add(v)
                todo.append(v)
    return False


why = {}
for net in nets:
    a, s = fp[net], sp[net]
    if connected(net, a, s):
        continue
    st = []
    ok = False
    try:
        fv = ddr.via_of(bd, net, 'U100')
    except KeyError:
        fv = None
    # outer-ring ball: straight across the top corridor
    if fv is None:
        pts = bd.path('F.Cu', a, s, W['F.Cu'] / 2, {net}, CLR, margin=6.0, half_in=0.05)
        if pts:
            neck(pts, net, 'F.Cu', st)
            ok = 'F.Cu'
    if not ok:
        va = fv or proute.drop_via(bd, a, net, s, st, radii=OUTER)
        vs = proute.drop_via(bd, s, net, a, st, radii=OUTER) if va else None
        why[net] = 'no fpga via' if not va else ('no stm32 via' if not vs else 'no path')
        if va and vs:
            for ly in ('In5.Cu', 'In2.Cu', 'B.Cu'):
                pts = bd.path(ly, va, vs, W[ly] / 2, {net}, CLR, margin=8.0, half_in=0.05)
                if pts:
                    neck(pts, net, ly, st)
                    ok = ly
                    break
    if ok:
        bd.commit(st)
        done.append((net, ok))
    else:
        bd.unstage(st)
        fail.append(net)
bd.save()
print('routed %d of %d' % (len(done), len(nets)))
print('by layer', {ly: sum(1 for _, l in done if l == ly) for ly in W})
print('not routed:', [(n, why.get(n, 'f.cu only')) for n in fail])
