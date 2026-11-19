import math
import os
import shutil
import sys
import time

import numpy as np
from scipy import ndimage
from skimage.graph import MCP_Geometric

import ddr
import proute
import rlib

# stm32 fmc + fpga config lines with negotiated congestion (as ddr2.py): every net gets its end vias
# first (fpga dogbone or a stub out of the ball field, one beside the stm32 pin), then all legs share
# the four signal layers until no two conflict. 125 MHz, no length matching. the ddr area is blocked
PCB = sys.argv[1]
SRC = sys.argv[2] if len(sys.argv) > 2 else PCB
G = rlib.G
FPGA_R = (109.5, 79.5, 134.5, 104.5)
rlib.BGA_RECTS[:] = [FPGA_R + (0.09,), (120.8, 62.35, 179.3, 76.65, 0.10)]
proute.ESC[:] = [FPGA_R]
rlib.TIGHT = True
WIN = (106.0, 74.0, 188.0, 122.0)
CLR = 0.127
WIDTH = {'In2.Cu': (0.23, 0.10), 'In5.Cu': (0.23, 0.10), 'B.Cu': (0.127, 0.10), 'F.Cu': (0.127, 0.10)}
LAYER_COST = {'In2.Cu': 1.0, 'In5.Cu': 1.0, 'B.Cu': 1.15, 'F.Cu': 1.1}
ITERS = int(os.environ.get('FMC_ITERS', '40'))
DDR_BLOCK = [(95.0, 94.0), (121.2, 94.0), (121.2, 135.5), (95.0, 135.5)]
OUTER = tuple(0.75 + 0.25 * i for i in range(22))

if os.path.abspath(SRC) != os.path.abspath(PCB):
    shutil.copy(SRC, PCB)
bd = rlib.Board(PCB)
bd.keepouts.append((DDR_BLOCK, set(rlib.LAYERS)))
STM = ddr.ref_of(bd, 'STM32H755')


def pads_of(ref):
    return {n: (x, y) for (x, y, hx, hy, n, lays, rnd, p) in bd.pads if p.GetParentFootprint().GetReference() == ref and n}


fp, sp = pads_of('U100'), pads_of(STM)
nets = sorted(n for n in set(fp) & set(sp) if n.startswith(('FMC_', 'FPGA_')))


def connected(net, a, b_):
    # copper path between the two pads already (kept from an earlier run)
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


already = [n for n in nets if connected(n, fp[n], sp[n])]
nets = [n for n in nets if n not in already]
print('already routed %d, to route %d' % (len(already), len(nets)), flush=True)

# 1) end vias
legs = []
for net in sorted(nets, key=lambda n: math.hypot(fp[n][0] - sp[n][0], fp[n][1] - sp[n][1])):
    st = []
    try:
        va = ddr.via_of(bd, net, 'U100')
    except KeyError:
        va = proute.drop_via(bd, fp[net], net, sp[net], st, radii=OUTER)
    if va:
        bd.commit(st)
        legs.append({'net': net, 'a': va})
    else:
        bd.unstage(st)
        print('no fpga via', net)
for leg in legs:
    st = []
    vb = proute.drop_via(bd, sp[leg['net']], leg['net'], leg['a'], st, radii=OUTER)
    if vb:
        bd.commit(st)
        leg['b'] = vb
    else:
        bd.unstage(st)
        print('no stm32 via', leg['net'])
legs = [l for l in legs if 'b' in l]
bd.reload()
SE = sorted({l['net'] for l in legs})
x0, y0, x1, y1 = WIN
NX, NY = int(round((x1 - x0) / G)) + 1, int(round((y1 - y0) / G)) + 1
XS = x0 + np.arange(NX) * G
YS = y0 + np.arange(NY) * G
inbga = np.zeros((NY, NX), bool)
inbga[np.ix_((YS >= FPGA_R[1]) & (YS <= FPGA_R[3]), (XS >= FPGA_R[0]) & (XS <= FPGA_R[2]))] = True


def cell(p):
    return (int(round((p[1] - y0) / G)), int(round((p[0] - x0) / G)))


# 2) obstacles
t0 = time.time()
FIX, OWN, CNT = {}, {}, {}
for ly, (w, win) in WIDTH.items():
    FIX[ly], _, _ = bd.grid(ly, WIN, w / 2, set(SE), CLR, half_in=win / 2)
    CNT[ly] = np.zeros((NY, NX), np.int16)
    for n in SE:
        mo, _, _ = bd._raster(ly, WIN, w / 2 + CLR + rlib.MARGIN, set(), only=n)
        mi, _, _ = bd._raster(ly, WIN, win / 2 + 0.09 + rlib.MARGIN, set(), only=n)
        OWN[(ly, n)] = np.where(inbga, mi, mo)
        CNT[ly] += OWN[(ly, n)]
print('obstacles %.0fs, %d legs' % (time.time() - t0, len(legs)), flush=True)
D = {ly: np.zeros((NY, NX), np.float32) for ly in WIDTH}
H = {ly: np.zeros((NY, NX), np.float32) for ly in WIDTH}


def keep_mask(path, ly, box):
    j0, j1, i0, i1 = box
    sub = np.zeros((j1 - j0, i1 - i0), bool)
    for (j, i) in path:
        sub[j - j0, i - i0] = True
    dist = ndimage.distance_transform_edt(~sub) * G
    w, win = WIDTH[ly]
    return np.where(inbga[j0:j1, i0:i1], dist < win + 0.09 + rlib.MARGIN, dist < w + CLR + rlib.MARGIN)


def box_of(path):
    return (max(0, min(p[0] for p in path) - 30), min(NY, max(p[0] for p in path) + 30),
            max(0, min(p[1] for p in path) - 30), min(NX, max(p[1] for p in path) + 30))


def route_leg(leg, pres):
    ja, ia = cell(leg['a'])
    jb, ib = cell(leg['b'])
    m = int(5.0 / G)
    j0, j1 = max(0, min(ja, jb) - m), min(NY, max(ja, jb) + m)
    i0, i1 = max(0, min(ia, ib) - m), min(NX, max(ia, ib) + m)
    best = None
    for ly in WIDTH:
        blocked = FIX[ly][j0:j1, i0:i1] | ((CNT[ly][j0:j1, i0:i1] - OWN[(ly, leg['net'])][j0:j1, i0:i1]) > 0)
        cost = LAYER_COST[ly] * (1.0 + H[ly][j0:j1, i0:i1] + pres * D[ly][j0:j1, i0:i1])
        cost = np.where(blocked, np.inf, cost)
        for (j, i) in ((ja - j0, ia - i0), (jb - j0, ib - i0)):
            cost[max(0, j - 6):j + 7, max(0, i - 6):i + 7] = np.minimum(cost[max(0, j - 6):j + 7, max(0, i - 6):i + 7], 1.0)
        mcp = MCP_Geometric(cost, fully_connected=True)
        cum, _ = mcp.find_costs([(ja - j0, ia - i0)], [(jb - j0, ib - i0)])
        c = cum[jb - j0, ib - i0]
        if np.isfinite(c) and (best is None or c < best[0]):
            best = (c, ly, [(j + j0, i + i0) for (j, i) in mcp.traceback((jb - j0, ib - i0))])
    if not best:
        return
    _, ly, path = best
    box = box_of(path)
    km = keep_mask(path, ly, box)
    leg.update({'layer': ly, 'path': path, 'box': box, 'keep': km})
    D[ly][box[0]:box[1], box[2]:box[3]] += km


def rip(leg):
    if 'keep' in leg:
        b4 = leg['box']
        D[leg['layer']][b4[0]:b4[1], b4[2]:b4[3]] -= leg['keep']
        del leg['keep']


def conflicted(leg):
    if 'keep' not in leg:
        return True
    j0, j1, i0, i1 = leg['box']
    od = D[leg['layer']][j0:j1, i0:i1] - leg['keep']
    return any(od[j - j0, i - i0] > 0.5 for (j, i) in leg['path'])


pres = 0.5
for it in range(ITERS):
    t0 = time.time()
    todo = legs if it == 0 else [l for l in legs if conflicted(l)]
    if it and not todo:
        break
    for leg in todo:
        rip(leg)
        route_leg(leg, pres)
    bad = [l for l in legs if conflicted(l)]
    print('iter %d rerouted %d conflicts %d (%.0fs)' % (it, len(todo), len(bad), time.time() - t0), flush=True)
    if not bad:
        break
    for ly in D:
        H[ly] += 0.3 * (D[ly] > 1.5)
    pres *= 1.6


# 3) smooth (pull tight against everything else) and commit the conflict-free legs
def tight(leg):
    ly, net = leg['layer'], leg['net']
    rip(leg)
    bl = FIX[ly] | ((CNT[ly] - OWN[(ly, net)]) > 0) | (D[ly] > 0.5)
    for (j, i) in (cell(leg['a']), cell(leg['b'])):
        bl[max(0, j - 6):j + 7, max(0, i - 6):i + 7] = False
    pts = [(XS[i], YS[j]) for (j, i) in leg['path']]
    pts[0], pts[-1] = leg['a'], leg['b']
    pts = rlib.pull_tight(rlib.simplify(pts), bl, x0, y0)
    cells = []
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(xb - xa, yb - ya) / (G / 2)))
        for k in range(n + 1):
            c = cell((xa + (xb - xa) * k / n, ya + (yb - ya) * k / n))
            if not cells or cells[-1] != c:
                cells.append(c)
    box = box_of(cells)
    km = keep_mask(cells, ly, box)
    leg.update({'path': cells, 'box': box, 'keep': km, 'pts': pts})
    D[ly][box[0]:box[1], box[2]:box[3]] += km


bad = {id(l) for l in legs if conflicted(l)}
for leg in legs:
    if id(leg) not in bad:
        tight(leg)
done, left = 0, []
for leg in legs:
    if id(leg) in bad or 'pts' not in leg:
        left.append(leg)
        continue
    w, win = WIDTH[leg['layer']]
    st = []
    for seg, inside in rlib.split_neck(leg['pts']):
        bd.stage_track(seg, win if inside else w, leg['net'], leg['layer'], st)
    bd.commit(st)
    done += 1
# 4) completion against everything committed
still = []
for leg in left:
    got = None
    for ly in sorted(WIDTH, key=lambda l: LAYER_COST[l]):
        w, win = WIDTH[ly]
        pts = bd.path(ly, leg['a'], leg['b'], w / 2, {leg['net']}, CLR, margin=10.0, half_in=win / 2)
        if pts:
            got = (ly, pts)
            break
    if not got:
        still.append(leg['net'])
        continue
    ly, pts = got
    w, win = WIDTH[ly]
    st = []
    for seg, inside in rlib.split_neck(pts):
        bd.stage_track(seg, win if inside else w, leg['net'], ly, st)
    bd.commit(st)
    done += 1
bd.save()
print('routed %d of %d nets; open: %s' % (done, len(nets), still + [n for n in nets if n not in SE]))
