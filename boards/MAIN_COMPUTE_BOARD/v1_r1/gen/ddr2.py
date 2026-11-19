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
DRAM_R = (105.455, 115.505, 121.545, 125.595)
rlib.BGA_RECTS[:] = [FPGA_R + (0.09,), (120.8, 62.35, 179.3, 76.65, 0.10), DRAM_R + (0.09,)]
proute.ESC[:] = [FPGA_R, DRAM_R]
rlib.TIGHT = True
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
# two runs: PHASE=measure writes per-group target lengths from the natural routes, PHASE=route
# stretches pairs and legs to them (waypoint detours); ddr_tune.py trims what is left
PHASE = os.environ.get('PHASE', 'route')
TFILE = os.environ.get('TFILE', os.path.join(HERE, 'ddr_targets.json'))
ROUTES = os.environ.get('ROUTES', os.path.join(HERE, 'ddr_routes.json'))
SEED = os.environ.get('SEED')
TARGETS = json.load(open(TFILE)) if PHASE == 'route' and os.path.exists(TFILE) else {}
PAIR_GROUP = {'DQS0': 'LANE0', 'DQS1': 'LANE1', 'CK': 'CMD'}
# extra spacing between ddr legs outside the ball fields, room for in-place serpentines (ddr_tune)
SPREAD = float(os.environ.get('SPREAD', '0.4'))
SPREAD_CMD = float(os.environ.get('SPREAD_CMD', '0.2'))
# nets that took long detours last time: lower congestion penalty so the others make way
PRIO = set(TARGETS.get('prio', []))

import ddr  # noqa: E402  (helpers only; ddr.py's routing loop is guarded below)

shutil.copy(SRC, PCB)
bd = rlib.Board(PCB)
U100 = 'U100'
U21 = ddr.ref_of(bd, 'MT41K256M16TW')

x0, y0, x1, y1 = WIN
NX, NY = int(round((x1 - x0) / G)) + 1, int(round((y1 - y0) / G)) + 1
XS = x0 + np.arange(NX) * G
YS = y0 + np.arange(NY) * G
inbga = np.zeros((NY, NX), bool)
for r in (FPGA_R, DRAM_R):
    inbga[np.ix_((YS >= r[1]) & (YS <= r[3]), (XS >= r[0]) & (XS <= r[2]))] = True


def cell(p):
    return (int(round((p[1] - y0) / G)), int(round((p[0] - x0) / G)))


def stub(net, via, ref):
    # ball to its end via (dogbone or the stub to a dropped via)
    b = ddr.pad_xy(bd, net, ref)
    return math.hypot(b[0] - via[0], b[1] - via[1])


def plen(pts):
    return sum(math.hypot(q[0] - p[0], q[1] - p[1]) for p, q in zip(pts, pts[1:]))


def pick(blocked, a_cell, b_cell, need, bad_zone, clear_r):
    # waypoint cell whose shortest a->w->b length is closest to need, with room to turn around
    cost = np.where(blocked, np.inf, 1.0)
    for (j, i) in (a_cell, b_cell):
        cost[max(0, j - 6):j + 7, max(0, i - 6):i + 7] = 1.0
    ma = MCP_Geometric(cost, fully_connected=True)
    ca, _ = ma.find_costs([a_cell])
    mb = MCP_Geometric(cost, fully_connected=True)
    cb, _ = mb.find_costs([b_cell])
    tot = (ca + cb) * G
    room = ndimage.distance_transform_edt(~blocked) * G
    ok = np.isfinite(tot) & ~bad_zone & (room > clear_r)
    return tot, ok, ma, cost


def stretch_pair(p, n, ends, lyr, fl, tgt, stubs, staged):
    # re-route the pair centreline through a waypoint so its length lands on the group target
    cs, ce, rs, re_, half = proute.pair_frame(*ends, lyr, PW, PG)
    blocked, xs, ys = bd.grid(lyr, WIN, half, {p, n}, PCLR)
    bd.unstage(staged)
    tot, ok, _, _ = pick(blocked, cell(cs), cell(ce), 0, inbga, half + 0.3)
    # shortest centreline today plus what the pair is short by
    base = tot[cell(ce)] if np.isfinite(tot[cell(ce)]) else plen([cs, ce])
    need = base + (tgt - fl)
    for attempt in range(4):
        err = np.where(ok, np.abs(tot - need), np.inf)
        k = np.unravel_index(np.argmin(err), err.shape)
        if not np.isfinite(err[k]) or err[k] > 1.0:
            break
        wpt = (XS[k[1]], YS[k[0]])
        s, l = proute.route_pair_c(bd, p, n, *ends, lyr, PW, PG, PCLR, waypoint=wpt)
        if not s:
            ok[max(0, k[0] - 8):k[0] + 9, max(0, k[1] - 8):k[1] + 9] = False
            continue
        got = sum(l) / 2 + stubs
        if abs(got - tgt) <= 0.35:
            print('pair %s stretched %.2f -> %.2f (target %.2f)' % (p[:-2], fl, got, tgt))
            return s, got
        bd.unstage(s)
        need += (tgt - got)
    # keep the natural route
    s, l = proute.route_pair(bd, p, n, *ends, lyr, PW, PG, PCLR)
    return (s, sum(l) / 2 + stubs) if s else None


# 1) pairs with the coupled router, fixed from here on
meta = {}
pair_fallback = []
pair_len = {}
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
    if ok:
        stubs = (stub(p, ends[0], U100) + stub(n, ends[1], U100) + stub(p, ends[2], U21) + stub(n, ends[3], U21)) / 2
        fl = sum(l) / 2 + stubs if isinstance(l, tuple) and len(l) == 2 and not isinstance(l[0], str) else None
        tgt = TARGETS.get(PAIR_GROUP[name])
        if fl is not None and tgt and tgt - fl > 0.3:
            got = stretch_pair(p, n, ends, ok[1], fl, tgt, stubs, ok[0])
            if got:
                ok = (got[0], ok[1])
                fl = got[1]
        pair_len[name] = fl
    if not ok:
        bd.unstage(pre)
        # fall back to two matched single-ended legs with the byte (skew is tuned afterwards)
        print('pair failed', name, '-> routed as two single-ended legs')
        pair_fallback.append((name, p, n))
        continue
    bd.commit(pre + ok[0])
    meta[p] = meta[n] = {'group': name, 'layer': ok[1]}
bd.reload()

for name, g in PAIR_GROUP.items():
    if pair_len.get(name) and g in TARGETS:
        TARGETS[g] = pair_len[name]
print('leg targets', {g: round(TARGETS[g], 2) for g in ('LANE0', 'LANE1', 'CMD') if g in TARGETS})

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


def keep_mask(path_cells, ly, box, grp=''):
    # cells another leg's centre may not enter: within w + clr of this centre line
    j0, j1, i0, i1 = box
    sub = np.zeros((j1 - j0, i1 - i0), bool)
    for (j, i) in path_cells:
        sub[j - j0, i - i0] = True
    dist = ndimage.distance_transform_edt(~sub) * G
    w, win = WIDTH[ly]
    ib = inbga[j0:j1, i0:i1]
    r_out = w + CLR + rlib.MARGIN + (SPREAD_CMD if grp in ('CMD', 'CMDP', 'TAIL', 'RESET') else SPREAD)
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
        f = 0.25 if leg['net'] in PRIO else 1.0
        cost = lc * (1.0 + f * H[ly][j0:j1, i0:i1] + f * pres * others(ly, (j0, j1, i0, i1), leg['net']))
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
    km = keep_mask(path, ly, box, leg['group'])
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
_rng = __import__('random').Random(int(SEED)) if SEED else None
order = sorted(legs, key=lambda l: math.hypot(l['a'][0] - l['b'][0], l['a'][1] - l['b'][1]) *
               (1.0 + (0.6 * _rng.random() if _rng else 0.0)))
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
# 3b) lengths. flight = ball stubs + leg. measure writes the group targets (the longest natural member,
#     pairs included); route stretches every short leg to its group target through a waypoint
GROUP_OF = {'LANE0': 'LANE0', 'LANE1': 'LANE1', 'CMD': 'CMD', 'LANE0P': 'LANE0', 'LANE1P': 'LANE1', 'CMDP': 'CMD'}


def raster(pts):
    # polyline -> ordered grid cells (for keep masks)
    cells = []
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(xb - xa, yb - ya) / (G / 2)))
        for k in range(n + 1):
            c = (int(round((ya + (yb - ya) * k / n - y0) / G)), int(round((xa + (xb - xa) * k / n - x0) / G)))
            if not cells or cells[-1] != c:
                cells.append(c)
    return cells


def tight(cells, blocked, a, b_):
    # grid path -> straight segments in clear line of sight (no staircase jabs)
    pts = [(XS[i], YS[j]) for (j, i) in cells]
    pts[0], pts[-1] = a, b_
    bl = blocked.copy()
    for (j, i) in (cell(a), cell(b_)):
        bl[max(0, j - 6):j + 7, max(0, i - 6):i + 7] = False
    return rlib.pull_tight(rlib.simplify(pts), bl, x0, y0)


def leg_pts(leg):
    if leg.get('pts'):
        return leg['pts']
    pts = [(XS[i], YS[j]) for (j, i) in leg['path']]
    pts[0], pts[-1] = leg['a'], leg['b']
    return rlib.simplify(pts)


def set_path(leg, pts):
    path = raster(pts)
    box = (max(0, min(p[0] for p in path) - 30), min(NY, max(p[0] for p in path) + 30),
           max(0, min(p[1] for p in path) - 30), min(NX, max(p[1] for p in path) + 30))
    km = keep_mask(path, leg['layer'], box, leg['group'])
    leg.update({'path': path, 'box': box, 'keep': km, 'pts': pts})
    D[leg['layer']][box[0]:box[1], box[2]:box[3]] += km


def smooth_leg(leg):
    ly, net = leg['layer'], leg['net']
    rip(leg)
    blocked = FIX[ly] | ((CNT[ly] - OWN[(ly, net)]) > 0) | (others(ly, (0, NY, 0, NX), net, skip=leg) > 0.5)
    set_path(leg, tight(leg['path'], blocked, leg['a'], leg['b']))


for leg in legs:
    if 'keep' in leg:
        smooth_leg(leg)
print('smoothed', sum('pts' in l for l in legs), 'legs', flush=True)


def leg_flight(leg):
    return stub(leg['net'], leg['a'], U100) + plen(leg_pts(leg)) + stub(leg['net'], leg['b'], U21)


def stretch_leg(leg, tgt):
    # own layer first, then the other routing layers (a leg mid-bus can only detour on a freer layer)
    home = leg['layer']
    for ly in [home] + [l for l in ALLOWED[leg['group']] if l != home]:
        if stretch_on(leg, tgt, ly):
            return True
    return False


def stretch_on(leg, tgt, ly):
    net = leg['net']
    w, win = WIDTH[ly]
    keep_old = (leg['path'], leg['box'], leg['keep'], leg['layer'])
    rip(leg)
    leg['layer'] = ly
    blocked = FIX[ly] | ((CNT[ly] - OWN[(ly, net)]) > 0) | (others(ly, (0, NY, 0, NX), net) > 0.5)
    want = tgt - stub(net, leg['a'], U100) - stub(net, leg['b'], U21)
    A, B = cell(leg['a']), cell(leg['b'])
    tot, ok, ma, _ = pick(blocked, A, B, want, inbga, w / 2 + 0.35)
    jj, ii = np.ogrid[:NY, :NX]
    search = want
    for attempt in range(5):
        err = np.where(ok, np.abs(tot - search), np.inf)
        k = np.unravel_index(np.argmin(err), err.shape)
        if not np.isfinite(err[k]) or err[k] > 1.0:
            break
        p1 = ma.traceback(k)
        sub = np.zeros((NY, NX), bool)
        for (j, i) in p1:
            sub[j, i] = True
        d1 = ndimage.distance_transform_edt(~sub) * G
        nearw = ((jj - k[0]) ** 2 + (ii - k[1]) ** 2) * G * G < 1.0
        blk2 = blocked | ((d1 < 2 * w + CLR + rlib.MARGIN) & ~nearw)
        c2 = np.where(blk2, np.inf, 1.0)
        c2[max(0, B[0] - 6):B[0] + 7, max(0, B[1] - 6):B[1] + 7] = 1.0
        m2 = MCP_Geometric(c2, fully_connected=True)
        cc, _ = m2.find_costs([k], [B])
        if not np.isfinite(cc[B]):
            ok[max(0, k[0] - 10):k[0] + 11, max(0, k[1] - 10):k[1] + 11] = False
            continue
        wpt = (XS[k[1]], YS[k[0]])
        h1 = tight(list(p1), blocked, leg['a'], wpt)
        h2 = tight(list(m2.traceback(B)), blk2, wpt, leg['b'])
        spts = h1 + h2[1:]
        path = raster(spts)
        got = plen(spts)
        if abs(got - want) <= 0.35:
            box = (max(0, min(p[0] for p in path) - 30), min(NY, max(p[0] for p in path) + 30),
                   max(0, min(p[1] for p in path) - 30), min(NX, max(p[1] for p in path) + 30))
            set_path(leg, spts)
            leg['stretched'] = True
            return True
        search += want - got
    if os.environ.get('SDIAG'):
        e0 = np.where(ok, np.abs(tot - want), np.inf)
        fin = np.isfinite(tot)
        print('nostretch', net, ly, 'want %.2f' % want, 'ok cells', int(ok.sum()), 'finite', int(fin.sum()),
              'min err %.2f' % float(e0.min()), 'max tot %.2f' % float(tot[fin].max() if fin.any() else -1),
              'direct %.2f' % float(tot[B] if np.isfinite(tot[B]) else -1))
    leg['path'], leg['box'], leg['keep'], leg['layer'] = keep_old
    D[leg['layer']][leg['box'][0]:leg['box'][1], leg['box'][2]:leg['box'][3]] += leg['keep']
    return False


flights = {leg['net']: (GROUP_OF[leg['group']], leg_flight(leg)) for leg in legs
           if 'path' in leg and leg['group'] in GROUP_OF}
if PHASE == 'measure':
    tg = {}
    for g in ('LANE0', 'LANE1', 'CMD'):
        vals = sorted(f for (gg, f) in flights.values() if gg == g)
        win = {'LANE0': 1.4, 'LANE1': 1.4, 'CMD': 3.0}[g]
        pn = {v: k for k, v in PAIR_GROUP.items()}[g]
        # the target whose window holds the most members as routed; short ones get stretched up to it,
        # the reference pair is stretched to it, members above the window are re-routed shorter
        best = None
        for t0 in [v - win + 0.2 for v in vals] + [pair_len.get(pn) or 0]:
            cnt = sum(1 for v in vals if t0 - win + 0.2 <= v <= t0 + win - 0.2)
            key = (cnt, -t0)
            if t0 >= (pair_len.get(pn) or 0) - 0.01 and (best is None or key > best[0]):
                best = (key, t0)
        tg[g] = round(best[1], 2)
    tol = {'LANE0': 1.4, 'LANE1': 1.4, 'CMD': 3.0}
    tg['prio'] = sorted(n for n, (g, f) in flights.items() if f > tg[g] + tol[g] - 0.3)
    json.dump(tg, open(TFILE, 'w'))
    print('targets', tg, 'pairs', {k: round(v, 2) for k, v in pair_len.items() if v})
    sys.exit(0)
def shrink_leg(leg):
    # a leg that came out long: shortest path against everything else as it now stands
    ly, net = leg['layer'], leg['net']
    old = (leg['path'], leg['box'], leg['keep'])
    old_pts = leg_pts(leg)
    rip(leg)
    blocked = FIX[ly] | ((CNT[ly] - OWN[(ly, net)]) > 0) | (others(ly, (0, NY, 0, NX), net) > 0.5)
    A, B = cell(leg['a']), cell(leg['b'])
    cost = np.where(blocked, np.inf, 1.0)
    for (j, i) in (A, B):
        cost[max(0, j - 6):j + 7, max(0, i - 6):i + 7] = 1.0
    m = MCP_Geometric(cost, fully_connected=True)
    cc, _ = m.find_costs([A], [B])
    if np.isfinite(cc[B]):
        spts = tight(list(m.traceback(B)), blocked, leg['a'], leg['b'])
        if plen(spts) < plen(old_pts) - 0.3:
            set_path(leg, spts)
            return True
        if False:
            km = keep_mask(path, ly, box, leg['group'])
            leg.update({'path': path, 'box': box, 'keep': km})
            D[ly][box[0]:box[1], box[2]:box[3]] += km
            return True
    leg['path'], leg['box'], leg['keep'] = old
    D[ly][leg['box'][0]:leg['box'][1], leg['box'][2]:leg['box'][3]] += leg['keep']
    return False


TOLG = {'LANE0': 1.4, 'LANE1': 1.4, 'CMD': 3.0}
n_sh = 0
for leg in legs:
    if leg['group'] in GROUP_OF and leg['net'] in flights and 'keep' in leg:
        g, f = flights[leg['net']]
        if TARGETS.get(g) and f > TARGETS[g] + TOLG[g] - 0.3 and shrink_leg(leg):
            n_sh += 1
            flights[leg['net']] = (g, leg_flight(leg))
print('shrunk', n_sh, 'long legs', flush=True)
n_ok = n_bad = 0
for leg in sorted(legs, key=lambda l: flights.get(l['net'], (0, 1e9))[1]):
    if leg['group'] not in GROUP_OF or leg['net'] not in flights or 'keep' not in leg:
        continue
    g, f = flights[leg['net']]
    tgt = TARGETS.get(g)
    if tgt and tgt - f > (0.9 if g.startswith('LANE') else 2.0):
        if stretch_leg(leg, tgt):
            n_ok += 1
        else:
            n_bad += 1
print('stretched', n_ok, 'legs; could not stretch', n_bad, flush=True)


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
    pts = leg_pts(leg)
    if not leg.get('stretched') and detour(leg, pts):
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
json.dump(meta, open(ROUTES, 'w'))
print('committed', done, 'legs; left open:', still)
