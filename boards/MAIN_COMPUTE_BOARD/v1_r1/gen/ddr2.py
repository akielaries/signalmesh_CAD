import json
import math
import os
import shutil
import sys
import time

import numpy as np
from scipy import ndimage
from skimage.graph import MCP_Geometric

import proute
import rlib

# ddr3 router with negotiated congestion (pathfinder): every single-ended leg is routed each round
# against fixed copper plus a growing penalty for sharing space with other ddr legs, until no two
# legs conflict. dqs/ck pairs are routed first with the coupled pair router and become fixed.
PCB = sys.argv[1]
SRC = sys.argv[2] if len(sys.argv) > 2 else PCB
HERE = os.path.dirname(os.path.abspath(__file__))
G = rlib.G
FPGA_R = (109.5, 79.5, 134.5, 104.5)
DRAM_R = (100.955, 107.355, 117.045, 117.445)
rlib.BGA_RECTS[:] = [FPGA_R + (0.09,), (120.8, 62.35, 179.3, 76.65, 0.10), DRAM_R + (0.09,)]
proute.ESC[:] = [FPGA_R, DRAM_R]
WIN = (95.0, 91.0, 125.0, 135.0)
CLR = 0.15
WIDTH = {'In2.Cu': (0.23, 0.10), 'In5.Cu': (0.23, 0.10), 'B.Cu': (0.127, 0.10), 'F.Cu': (0.127, 0.10)}
LAYER_COST = {'In2.Cu': 1.0, 'In5.Cu': 1.0, 'B.Cu': 1.25, 'F.Cu': 1.3}
PW, PG, PCLR = 0.115, 0.10, 0.15
LANES = {0: ['DDR_DQ%d' % i for i in range(8)] + ['DDR_DM0'],
         1: ['DDR_DQ%d' % i for i in range(8, 16)] + ['DDR_DM1']}
CMD = ['DDR_A%d' % i for i in range(15)] + ['DDR_BA0', 'DDR_BA1', 'DDR_BA2', 'DDR_RAS_N', 'DDR_CAS_N', 'DDR_WE_N',
                                            'DDR_CKE', 'DDR_ODT']
PAIRS = [('DQS0', 'DDR_DQS0_P', 'DDR_DQS0_N', 'In2.Cu'), ('DQS1', 'DDR_DQS1_P', 'DDR_DQS1_N', 'In2.Cu'),
         ('CK', 'DDR_CK_P', 'DDR_CK_N', 'In5.Cu')]
# every group may use all three routing layers; the layer cost keeps lanes on in2 and cmd on in5 when
# there is room
ALL3 = ('In2.Cu', 'In5.Cu', 'B.Cu', 'F.Cu')
ALLOWED = {'LANE0': ALL3, 'LANE1': ALL3, 'CMD': ALL3, 'TAIL': ALL3, 'RESET': ALL3, 'LANE0P': ALL3, 'LANE1P': ALL3,
           'CMDP': ALL3}
PREF = {'LANE0': 'In2.Cu', 'LANE1': 'In2.Cu', 'CMD': 'In5.Cu', 'TAIL': 'In5.Cu', 'RESET': 'In5.Cu', 'LANE0P': 'In2.Cu',
        'LANE1P': 'In2.Cu', 'CMDP': 'In5.Cu'}
ITERS = int(os.environ.get('ITERS', '14'))

import ddr  # noqa: E402  (helpers only; ddr.py's routing loop is guarded below)

shutil.copy(SRC, PCB)
bd = rlib.Board(PCB)
U100 = 'U100'
U21 = ddr.ref_of(bd, 'MT41K256M16TW')

# 1) pairs with the coupled router, fixed from here on
meta = {}
pair_fallback = []
for name, p, n, ly in PAIRS:
    pre = []
    dm = proute.mid(ddr.pad_xy(bd, p, U21), ddr.pad_xy(bd, n, U21))
    fm = proute.mid(ddr.pad_xy(bd, p, U100), ddr.pad_xy(bd, n, U100))
    ends = [ddr.end_via(bd, p, U100, dm, pre), ddr.end_via(bd, n, U100, dm, pre),
            ddr.end_via(bd, p, U21, fm, pre), ddr.end_via(bd, n, U21, fm, pre)]
    ok = None
    if all(ends):
        for lyr in (ly, 'In5.Cu' if ly == 'In2.Cu' else 'In2.Cu'):
            s, l = proute.route_pair(bd, p, n, *ends, lyr, PW, PG, PCLR)
            if s:
                ok = (s, lyr)
                break
    if not ok:
        bd.unstage(pre)
        # fall back to two matched single-ended legs with the byte (skew is tuned afterwards)
        print('pair failed', name, '-> routed as two single-ended legs')
        pair_fallback.append((name, p, n))
        continue
    bd.commit(pre + ok[0])
    meta[p] = meta[n] = {'group': name, 'layer': ok[1]}
bd.reload()

# 2) end vias for every single-ended leg (dogbone or new via), and the terminator tail vias
tasks = []
for k, nets in LANES.items():
    for n in nets:
        tasks.append([n, 'LANE%d' % k])
for n in CMD:
    tasks.append([n, 'CMD'])
tasks.append(['DDR_RESET_N', 'RESET'])
for name, p, n in pair_fallback:
    g = {'DQS0': 'LANE0', 'DQS1': 'LANE1', 'CK': 'CMD'}[name]
    tasks += [[p, g + 'P'], [n, g + 'P']]
legs = []
for net, grp in tasks:
    st = []
    b_ = ddr.end_via(bd, net, U21, ddr.pad_xy(bd, net, U100), st)
    a = ddr.end_via(bd, net, U100, b_ or ddr.pad_xy(bd, net, U21), st) if b_ else None
    if not (a and b_):
        bd.unstage(st)
        print('no end via', net)
        continue
    bd.commit(st)
    legs.append({'net': net, 'group': grp, 'a': a, 'b': b_})
    if grp == 'CMD':
        st = []
        tv = proute.drop_via(bd, ddr.term_pad(bd, net), net, b_, st, radii=ddr.OUTER)
        if tv:
            bd.commit(st)
            legs.append({'net': net, 'group': 'TAIL', 'a': b_, 'b': tv})
        else:
            print('no terminator via', net)
bd.reload()
SE = sorted({l['net'] for l in legs})
x0, y0, x1, y1 = WIN
NX, NY = int(round((x1 - x0) / G)) + 1, int(round((y1 - y0) / G)) + 1
XS = x0 + np.arange(NX) * G
YS = y0 + np.arange(NY) * G
inbga = np.zeros((NY, NX), bool)
for r in (FPGA_R, DRAM_R):
    inbga[np.ix_((YS >= r[1]) & (YS <= r[3]), (XS >= r[0]) & (XS <= r[2]))] = True


def cell(p):
    return (int(round((p[1] - y0) / G)), int(round((p[0] - x0) / G)))


# 3) fixed obstacles per layer (everything except the single-ended ddr nets), and each ddr net's own
#    vias/dogbones so other ddr legs keep clear of them
t0 = time.time()
FIX, OWN, CNT = {}, {}, {}
for ly, (w, win) in WIDTH.items():
    FIX[ly], _, _ = bd.grid(ly, WIN, w / 2, set(SE), CLR, half_in=win / 2)
    CNT[ly] = np.zeros((NY, NX), np.int16)
    for n in SE:
        mo, _, _ = bd._raster(ly, WIN, w / 2 + CLR + rlib.MARGIN, set(), only=n)
        mi, _, _ = bd._raster(ly, WIN, win / 2 + 0.09 + rlib.MARGIN, set(), only=n)
        m = np.where(inbga, mi, mo)
        OWN[(ly, n)] = m
        CNT[ly] += m
print('obstacles %.0fs' % (time.time() - t0), flush=True)

D = {ly: np.zeros((NY, NX), np.float32) for ly in WIDTH}
H = {ly: np.zeros((NY, NX), np.float32) for ly in WIDTH}


def keep_mask(path_cells, ly, box):
    # cells another leg's centre may not enter: within w + clr of this centre line
    j0, j1, i0, i1 = box
    sub = np.zeros((j1 - j0, i1 - i0), bool)
    for (j, i) in path_cells:
        sub[j - j0, i - i0] = True
    dist = ndimage.distance_transform_edt(~sub) * G
    w, win = WIDTH[ly]
    ib = inbga[j0:j1, i0:i1]
    r_out = w + CLR + rlib.MARGIN
    r_in = win + 0.09 + rlib.MARGIN
    return np.where(ib, dist < r_in, dist < r_out)


def others(ly, box, net, skip=None):
    # congestion from legs of other nets only (a net's own legs may touch at its vias)
    j0, j1, i0, i1 = box
    d = D[ly][j0:j1, i0:i1].copy()
    for o in legs:
        if o is skip or o['net'] != net or 'keep' not in o or o['layer'] != ly:
            continue
        a0, a1, b0, b1 = o['box']
        c0, c1, e0, e1 = max(j0, a0), min(j1, a1), max(i0, b0), min(i1, b1)
        if c0 < c1 and e0 < e1:
            d[c0 - j0:c1 - j0, e0 - i0:e1 - i0] -= o['keep'][c0 - a0:c1 - a0, e0 - b0:e1 - b0]
    return d


def route_leg(leg, pres):
    a, b_ = leg['a'], leg['b']
    ja, ia = cell(a)
    jb, ib_ = cell(b_)
    m = int(6.0 / G)
    j0, j1 = max(0, min(ja, jb) - m), min(NY, max(ja, jb) + m)
    i0, i1 = max(0, min(ia, ib_) - m), min(NX, max(ia, ib_) + m)
    best = None
    for ly in ALLOWED[leg['group']]:
        blocked = FIX[ly][j0:j1, i0:i1] | ((CNT[ly][j0:j1, i0:i1] - OWN[(ly, leg['net'])][j0:j1, i0:i1]) > 0)
        lc = LAYER_COST[ly] * (1.0 if ly == PREF[leg['group']] else 1.15)
        cost = lc * (1.0 + H[ly][j0:j1, i0:i1] + pres * others(ly, (j0, j1, i0, i1), leg['net']))
        cost = np.where(blocked, np.inf, cost)
        for (j, i) in ((ja - j0, ia - i0), (jb - j0, ib_ - i0)):
            cost[max(0, j - 6):j + 7, max(0, i - 6):i + 7] = np.minimum(cost[max(0, j - 6):j + 7, max(0, i - 6):i + 7], 1.0)
        mcp = MCP_Geometric(cost, fully_connected=True)
        cum, _ = mcp.find_costs([(ja - j0, ia - i0)], [(jb - j0, ib_ - i0)])
        c = cum[jb - j0, ib_ - i0]
        if np.isfinite(c) and (best is None or c < best[0]):
            path = [(j + j0, i + i0) for (j, i) in mcp.traceback((jb - j0, ib_ - i0))]
            best = (c, ly, path)
    if not best:
        return False
    _, ly, path = best
    box = (max(0, min(p[0] for p in path) - 30), min(NY, max(p[0] for p in path) + 30),
           max(0, min(p[1] for p in path) - 30), min(NX, max(p[1] for p in path) + 30))
    km = keep_mask(path, ly, box)
    leg.update({'layer': ly, 'path': path, 'box': box, 'keep': km})
    D[ly][box[0]:box[1], box[2]:box[3]] += km
    return True


def rip(leg):
    if 'keep' in leg:
        b4 = leg['box']
        D[leg['layer']][b4[0]:b4[1], b4[2]:b4[3]] -= leg['keep']
        del leg['keep']


def conflicts():
    bad = []
    for leg in legs:
        if 'keep' not in leg:
            bad.append(leg)
            continue
        ly = leg['layer']
        # another net's keep-out covers this centre line
        od = others(ly, leg['box'], leg['net'], skip=leg) - leg['keep']
        j0, i0 = leg['box'][0], leg['box'][2]
        if any(od[j - j0, i - i0] > 0.5 for (j, i) in leg['path']):
            bad.append(leg)
    return bad


pres = 0.5
order = sorted(legs, key=lambda l: math.hypot(l['a'][0] - l['b'][0], l['a'][1] - l['b'][1]))
for it in range(ITERS):
    t0 = time.time()
    todo = order if it == 0 else conflicts()
    if it and not todo:
        break
    for leg in todo:
        rip(leg)
        route_leg(leg, pres)
    bad = conflicts()
    print('iter %d rerouted %d conflicts %d unrouted %d (%.0fs)' % (
        it, len(todo), len(bad), sum('keep' not in l for l in legs), time.time() - t0), flush=True)
    if not bad:
        break
    for ly in D:
        H[ly] += 0.3 * (D[ly] > 1.5)
    pres *= 1.6

if os.environ.get('DIAG'):
    from collections import Counter
    spots = Counter()
    for leg in conflicts():
        if 'keep' not in leg:
            continue
        ly = leg['layer']
        od = others(ly, leg['box'], leg['net'], skip=leg) - leg['keep']
        j0, i0 = leg['box'][0], leg['box'][2]
        hits = [(j, i) for (j, i) in leg['path'] if od[j - j0, i - i0] > 0.5]
        if hits:
            j, i = hits[len(hits) // 2]
            ea = math.hypot(XS[hits[0][1]] - leg['a'][0], YS[hits[0][0]] - leg['a'][1])
            eb = math.hypot(XS[hits[-1][1]] - leg['b'][0], YS[hits[-1][0]] - leg['b'][1])
            print('conflict', leg['net'], leg['group'], ly, 'cells', len(hits), 'at (%.2f, %.2f)' % (XS[i], YS[j]),
                  'from a %.2f, to b %.2f' % (ea, eb))
def detour(leg, pts):
    direct = math.hypot(leg['a'][0] - leg['b'][0], leg['a'][1] - leg['b'][1])
    return rlib.length(pts) > 1.35 * direct + 4.0


# 4) commit legs that ended conflict free; conflicted ones are reported and left open
bad = {id(l) for l in conflicts()}
done, left = 0, []
for leg in legs:
    if id(leg) in bad or 'path' not in leg:
        left.append((leg['net'], leg['group']))
        continue
    pts = [(XS[i], YS[j]) for (j, i) in leg['path']]
    pts[0], pts[-1] = leg['a'], leg['b']
    pts = rlib.simplify(pts)
    if detour(leg, pts):
        left.append((leg['net'], leg['group']))
        continue
    w, win = WIDTH[leg['layer']]
    st = []
    for seg, inside in rlib.split_neck(pts):
        bd.stage_track(seg, win if inside else w, leg['net'], leg['layer'], st)
    bd.commit(st)
    done += 1
    if leg['group'].endswith('P'):
        nm = {'LANE0P': 'DQS0', 'LANE1P': 'DQS1', 'CMDP': 'CK'}[leg['group']]
        meta[leg['net']] = {'group': nm, 'layer': leg['layer']}
    elif leg['group'] != 'TAIL':
        meta[leg['net']] = {'group': leg['group'], 'layer': leg['layer']}
# 5) completion: leftover legs search against everything committed so far, any layer
still = []
for leg in legs:
    if (leg['net'], leg['group']) not in left:
        continue
    got = None
    for ly in sorted(ALLOWED[leg['group']], key=lambda l: (l != PREF[leg['group']], LAYER_COST[l])):
        w, win = WIDTH[ly]
        pts = bd.path(ly, leg['a'], leg['b'], w / 2, {leg['net']}, CLR, margin=8.0, half_in=win / 2)
        if pts and not detour(leg, pts):
            got = (ly, pts)
            break
    if not got:
        still.append((leg['net'], leg['group']))
        continue
    ly, pts = got
    w, win = WIDTH[ly]
    st = []
    for seg, inside in rlib.split_neck(pts):
        bd.stage_track(seg, win if inside else w, leg['net'], ly, st)
    bd.commit(st)
    done += 1
    if leg['group'].endswith('P'):
        meta[leg['net']] = {'group': {'LANE0P': 'DQS0', 'LANE1P': 'DQS1', 'CMDP': 'CK'}[leg['group']], 'layer': ly}
    elif leg['group'] != 'TAIL':
        meta[leg['net']] = {'group': leg['group'], 'layer': ly}
bd.save()
json.dump(meta, open(os.path.join(HERE, 'ddr_routes.json'), 'w'))
print('committed', done, 'legs; left open:', still)
