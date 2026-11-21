import math
import time

import numpy as np
from scipy import ndimage
from skimage.graph import MCP_Geometric

import rlib

# negotiated-congestion (pathfinder) routing of via-to-via legs, lifted from fmc2.py so other scripts can
# use it. legs: [{'net': n, 'a': (x, y), 'b': (x, y)}], both ends vias. every leg is routed on whichever
# layer is cheapest; legs that overlap pay a rising present cost and history cost until no two conflict.
# conflict-free legs are pulled tight (octilinear) and committed; leftovers get one plain completion try.
G = rlib.G


def negotiate(bd, legs, win, width, layer_cost, iters=30, clr=0.127, neck=0.10, log=print):
    x0, y0, x1, y1 = win
    NX, NY = int(round((x1 - x0) / G)) + 1, int(round((y1 - y0) / G)) + 1
    XS = x0 + np.arange(NX) * G
    YS = y0 + np.arange(NY) * G
    inesc = np.zeros((NY, NX), bool)
    for r in rlib.BGA_RECTS:
        inesc[np.ix_((YS >= r[1]) & (YS <= r[3]), (XS >= r[0]) & (XS <= r[2]))] = True
    cell = lambda p: (int(round((p[1] - y0) / G)), int(round((p[0] - x0) / G)))
    nets = sorted({l['net'] for l in legs})
    t0 = time.time()
    FIX, OWN, CNT = {}, {}, {}
    for ly, w in width.items():
        FIX[ly], _, _ = bd.grid(ly, win, w / 2, set(nets), clr, half_in=neck / 2)
        CNT[ly] = np.zeros((NY, NX), np.int16)
        for n in nets:
            mo, _, _ = bd._raster(ly, win, w / 2 + clr + rlib.MARGIN, set(), only=n)
            mi, _, _ = bd._raster(ly, win, neck / 2 + 0.09 + rlib.MARGIN, set(), only=n)
            m = np.where(inesc, mi, mo)
            CNT[ly] += m
            js, is_ = np.nonzero(m)
            # stored cropped to the net's own copper: full-window masks for every net would not fit in memory
            OWN[(ly, n)] = (js.min(), js.max() + 1, is_.min(), is_.max() + 1, m[js.min():js.max() + 1, is_.min():is_.max() + 1].copy()) if len(js) else None
            del m, mo, mi

    def own(ly, n, j0, j1, i0, i1):
        out = np.zeros((j1 - j0, i1 - i0), np.int16)
        o = OWN.get((ly, n))
        if o is None:
            return out
        a0, a1, b0, b1, m = o
        c0, c1, d0, d1 = max(a0, j0), min(a1, j1), max(b0, i0), min(b1, i1)
        if c0 < c1 and d0 < d1:
            out[c0 - j0:c1 - j0, d0 - i0:d1 - i0] = m[c0 - a0:c1 - a0, d0 - b0:d1 - b0]
        return out
    log('negotiate: %d legs, %d nets, window %.0fx%.0f mm, obstacles %.0fs' % (len(legs), len(nets), x1 - x0, y1 - y0, time.time() - t0))
    D = {ly: np.zeros((NY, NX), np.float32) for ly in width}
    H = {ly: np.zeros((NY, NX), np.float32) for ly in width}

    def keep_mask(path, ly, box):
        j0, j1, i0, i1 = box
        sub = np.zeros((j1 - j0, i1 - i0), bool)
        for (j, i) in path:
            sub[j - j0, i - i0] = True
        dist = ndimage.distance_transform_edt(~sub) * G
        return np.where(inesc[j0:j1, i0:i1], dist < neck + 0.09 + rlib.MARGIN, dist < width[ly] + clr + rlib.MARGIN)

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
        for ly in ([leg['ly']] if 'ly' in leg else width):
            blocked = FIX[ly][j0:j1, i0:i1] | ((CNT[ly][j0:j1, i0:i1] - own(ly, leg['net'], j0, j1, i0, i1)) > 0)
            cost = layer_cost[ly] * (1.0 + H[ly][j0:j1, i0:i1] + pres * D[ly][j0:j1, i0:i1])
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
    for it in range(iters):
        t0 = time.time()
        todo = legs if it == 0 else [l for l in legs if conflicted(l)]
        if it and not todo:
            break
        for leg in todo:
            rip(leg)
            route_leg(leg, pres)
        bad = [l for l in legs if conflicted(l)]
        log('  iter %d: rerouted %d, conflicts %d (%.0fs)' % (it, len(todo), len(bad), time.time() - t0))
        if not bad:
            break
        for ly in D:
            H[ly] += 0.3 * (D[ly] > 1.5)
        pres *= 1.6

    def tight(leg):
        ly, net = leg['layer'], leg['net']
        rip(leg)
        bl = FIX[ly] | ((CNT[ly] - own(ly, net, 0, NY, 0, NX)) > 0) | (D[ly] > 0.5)
        for (j, i) in (cell(leg['a']), cell(leg['b'])):
            bl[max(0, j - 6):j + 7, max(0, i - 6):i + 7] = False
        pts = [(XS[i], YS[j]) for (j, i) in leg['path']]
        pts[0], pts[-1] = leg['a'], leg['b']
        pts = rlib.pull_tight(rlib.simplify(pts), bl, x0, y0)
        cells = []
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            k = max(1, int(math.hypot(xb - xa, yb - ya) / (G / 2)))
            for q in range(k + 1):
                c = cell((xa + (xb - xa) * q / k, ya + (yb - ya) * q / k))
                if not cells or cells[-1] != c:
                    cells.append(c)
        box = box_of(cells)
        km = keep_mask(cells, ly, box)
        leg.update({'path': cells, 'box': box, 'keep': km, 'pts': pts})
        D[ly][box[0]:box[1], box[2]:box[3]] += km

    bad = {id(l) for l in legs if conflicted(l)}
    # where the stuck legs collide: 2 mm bins of their overlapping cells, per layer
    hot = {}
    for leg in legs:
        if id(leg) in bad and 'keep' in leg:
            j0, j1, i0, i1 = leg['box']
            od = D[leg['layer']][j0:j1, i0:i1] - leg['keep']
            for (j, i) in leg['path']:
                if od[j - j0, i - i0] > 0.5:
                    k = (leg['layer'], int(XS[i] // 2) * 2, int(YS[j] // 2) * 2)
                    hot[k] = hot.get(k, 0) + 1
    top = sorted(hot.items(), key=lambda kv: -kv[1])[:12]
    log('conflict hotspots (layer, x, y: cells): ' + '; '.join('%s %d,%d: %d' % (k[0], k[1], k[2], v) for k, v in top))
    for leg in legs:
        if id(leg) not in bad:
            tight(leg)
    done, left = 0, []
    for leg in legs:
        if id(leg) in bad or 'pts' not in leg:
            left.append(leg)
            continue
        st = []
        for seg, inside in rlib.split_neck(leg['pts']):
            bd.stage_track(seg, neck if inside else width[leg['layer']], leg['net'], leg['layer'], st)
        bd.commit(st)
        done += 1
    still = []
    for leg in left:
        got = None
        for ly in ([leg['ly']] if 'ly' in leg else sorted(width, key=lambda l: layer_cost[l])):
            pts = bd.path(ly, leg['a'], leg['b'], width[ly] / 2, {leg['net']}, clr, margin=10.0, half_in=neck / 2)
            if pts:
                got = (ly, pts)
                break
        if not got:
            still.append(leg)
            continue
        ly, pts = got
        st = []
        for seg, inside in rlib.split_neck(pts):
            bd.stage_track(seg, neck if inside else width[ly], leg['net'], ly, st)
        bd.commit(st)
        done += 1
    log('negotiate: %d of %d legs routed' % (done, len(legs)))
    return still
