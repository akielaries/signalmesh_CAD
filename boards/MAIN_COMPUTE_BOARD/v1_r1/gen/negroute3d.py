import math
import time

import numpy as np
from scipy import ndimage
from skimage.graph import MCP_Geometric

import rlib

# negotiated-congestion routing with layer changes. like negroute.negotiate, but each leg is searched in
# one 3d cost volume (signal layers interleaved with via planes), so a route may drop a through via
# wherever there is room for one and carry on on another layer. legs: [{'net', 'a', 'b'}] with optional
# 'la' / 'lb' pinning an end to one layer (a track end, not a via). routes that overlap pay rising present
# and history costs until none conflict; conflict-free routes are pulled tight (octilinear) and committed.
G = rlib.G


def negotiate3d(bd, legs, win, width, layer_cost, via_cost=1.2, iters=20, clr=0.127, neck=0.10, via_d=0.4,
                margin=4.0, log=print):
    x0, y0, x1, y1 = win
    NX, NY = int(round((x1 - x0) / G)) + 1, int(round((y1 - y0) / G)) + 1
    XS = x0 + np.arange(NX) * G
    YS = y0 + np.arange(NY) * G
    LY = list(width)
    L = len(LY)
    inesc = np.zeros((NY, NX), bool)
    for r in rlib.BGA_RECTS:
        inesc[np.ix_((YS >= r[1]) & (YS <= r[3]), (XS >= r[0]) & (XS <= r[2]))] = True
    cell = lambda p: (min(NY - 1, max(0, int(round((p[1] - y0) / G)))), min(NX - 1, max(0, int(round((p[0] - x0) / G)))))
    nets = sorted({l['net'] for l in legs})
    t0 = time.time()
    vr = via_d / 2
    FIX, CNT, OWN = {}, {}, {}
    VFIX = np.zeros((NY, NX), bool)
    CNTV = np.zeros((NY, NX), np.int16)
    OWNV = {}

    def crop_store(m):
        js, is_ = np.nonzero(m)
        if not len(js):
            return None
        return (js.min(), js.max() + 1, is_.min(), is_.max() + 1, m[js.min():js.max() + 1, is_.min():is_.max() + 1].copy())

    def uncrop(o, j0, j1, i0, i1):
        out = np.zeros((j1 - j0, i1 - i0), np.int16)
        if o is None:
            return out
        a0, a1, b0, b1, m = o
        c0, c1, d0, d1 = max(a0, j0), min(a1, j1), max(b0, i0), min(b1, i1)
        if c0 < c1 and d0 < d1:
            out[c0 - j0:c1 - j0, d0 - i0:d1 - i0] = m[c0 - a0:c1 - a0, d0 - b0:d1 - b0]
        return out

    for ly, w in width.items():
        FIX[ly], _, _ = bd.grid(ly, win, w / 2, set(nets), clr, half_in=neck / 2)
        vb, _, _ = bd.grid(ly, win, vr, set(nets), clr, half_in=vr, pours=False)
        VFIX |= vb
        CNT[ly] = np.zeros((NY, NX), np.int16)
    for n in nets:
        mv = np.zeros((NY, NX), bool)
        for ly, w in width.items():
            mo, _, _ = bd._raster(ly, win, w / 2 + clr + rlib.MARGIN, set(), only=n)
            mi, _, _ = bd._raster(ly, win, neck / 2 + 0.09 + rlib.MARGIN, set(), only=n)
            m = np.where(inesc, mi, mo)
            CNT[ly] += m
            OWN[(ly, n)] = crop_store(m)
            v, _, _ = bd._raster(ly, win, vr + clr + rlib.MARGIN, set(), only=n)
            mv |= v
        CNTV += mv
        OWNV[n] = crop_store(mv)
    log('negotiate3d: %d legs, %d nets, %d layers, window %.0fx%.0f mm, obstacles %.0fs'
        % (len(legs), len(nets), L, x1 - x0, y1 - y0, time.time() - t0))
    D = {ly: np.zeros((NY, NX), np.float32) for ly in LY}
    H = {ly: np.zeros((NY, NX), np.float32) for ly in LY}
    offs = [(0, dj, di) for dj in (-1, 0, 1) for di in (-1, 0, 1) if (dj, di) != (0, 0)] + [(1, 0, 0), (-1, 0, 0)]
    VC = via_cost / G           # one via costs as much as via_cost mm of track
    vdisk = None

    def disk(rad):
        k = int(math.ceil(rad / G))
        yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
        return (xx * xx + yy * yy) * G * G <= rad * rad, k

    def track_keep(cells, ly):
        j0 = max(0, min(c[0] for c in cells) - 30)
        j1 = min(NY, max(c[0] for c in cells) + 30)
        i0 = max(0, min(c[1] for c in cells) - 30)
        i1 = min(NX, max(c[1] for c in cells) + 30)
        sub = np.zeros((j1 - j0, i1 - i0), bool)
        for (j, i) in cells:
            sub[j - j0, i - i0] = True
        dist = ndimage.distance_transform_edt(~sub) * G
        m = np.where(inesc[j0:j1, i0:i1], dist < neck + 0.09 + rlib.MARGIN, dist < width[ly] + clr + rlib.MARGIN)
        return (ly, (j0, j1, i0, i1), m.astype(np.float32))

    def via_keeps(j, i):
        d, k = disk(vr + max(width.values()) / 2 + clr + rlib.MARGIN)
        j0, j1, i0, i1 = max(0, j - k), min(NY, j + k + 1), max(0, i - k), min(NX, i + k + 1)
        m = d[(j0 - (j - k)):(j0 - (j - k)) + (j1 - j0), (i0 - (i - k)):(i0 - (i - k)) + (i1 - i0)].astype(np.float32)
        return [(ly, (j0, j1, i0, i1), m) for ly in LY]

    def add(leg, s):
        for ly, (j0, j1, i0, i1), m in leg.get('keeps', []):
            D[ly][j0:j1, i0:i1] += s * m

    bynet = {}
    for l in legs:
        bynet.setdefault(l['net'], []).append(l)

    def lift(leg, s):
        # all legs of one net are lifted together: legs of the same net may touch (shared vias)
        for l in bynet[leg['net']]:
            add(l, s)

    def route(leg, pres):
        ja, ia = cell(leg['a'])
        jb, ib = cell(leg['b'])
        m = int(margin / G)
        j0, j1 = max(0, min(ja, jb) - m), min(NY, max(ja, jb) + m)
        i0, i1 = max(0, min(ia, ib) - m), min(NX, max(ia, ib) + m)
        n = leg['net']
        C = np.empty((2 * L - 1, j1 - j0, i1 - i0), np.float32)
        dmax = np.zeros((j1 - j0, i1 - i0), np.float32)
        for k, ly in enumerate(LY):
            blk = FIX[ly][j0:j1, i0:i1] | ((CNT[ly][j0:j1, i0:i1] - uncrop(OWN[(ly, n)], j0, j1, i0, i1)) > 0)
            c = layer_cost[ly] * (1.0 + H[ly][j0:j1, i0:i1] + pres * D[ly][j0:j1, i0:i1])
            C[2 * k] = np.where(blk, np.inf, c)
            dmax = np.maximum(dmax, D[ly][j0:j1, i0:i1] + H[ly][j0:j1, i0:i1])
        vblk = VFIX[j0:j1, i0:i1] | ((CNTV[j0:j1, i0:i1] - uncrop(OWNV[n], j0, j1, i0, i1)) > 0)
        vc = np.where(vblk, np.inf, VC * (1.0 + pres * dmax))
        for k in range(L - 1):
            C[2 * k + 1] = vc
        starts, ends = [], []
        for (j, i), pin, out in (((ja - j0, ia - i0), leg.get('la'), starts), ((jb - j0, ib - i0), leg.get('lb'), ends)):
            sl = (slice(max(0, j - 6), j + 7), slice(max(0, i - 6), i + 7))
            zs = [2 * LY.index(pin)] if pin else list(range(0, 2 * L - 1, 2))
            for z in zs:
                C[z][sl] = np.minimum(C[z][sl], 1.0)
                out.append((z, j, i))
            if not pin:
                for z in range(1, 2 * L - 1, 2):
                    C[z][sl] = np.minimum(C[z][sl], 1.0)
        mcp = MCP_Geometric(C, offsets=offs)
        cum, _ = mcp.find_costs(starts, ends)
        best = min(ends, key=lambda e: cum[e])
        if not np.isfinite(cum[best]):
            return False
        path = [(z, j + j0, i + i0) for (z, j, i) in mcp.traceback(best)]
        runs, vias, cur, curz = [], [], [], None
        for (z, j, i) in path:
            if z % 2 == 0:
                if curz is not None and z != curz:
                    runs.append((LY[curz // 2], cur))
                    cur = []
                curz = z
                cur.append((j, i))
            elif not vias or vias[-1] != (j, i):
                vias.append((j, i))
        runs.append((LY[curz // 2], cur))
        # two layer changes within a via pitch (via, short hop, via) collapse into one via: the hop's run
        # is dropped and the neighbouring runs meet at the first via
        k = 0
        while k + 1 < len(vias) and k + 2 < len(runs):
            if math.hypot(vias[k][0] - vias[k + 1][0], vias[k][1] - vias[k + 1][1]) * G < 0.6:
                del runs[k + 1]
                del vias[k + 1]
                runs[k + 1] = (runs[k + 1][0], [vias[k]] + runs[k + 1][1])
            else:
                k += 1
        # a via where the route changes layer (the endpoints' own vias are not new)
        # a layer change next to an end that is already a via needs no new via; next to a pinned track end it does
        vias = [v for v in vias if (leg.get('la') or math.hypot(v[0] - ja, v[1] - ia) > 6) and
                (leg.get('lb') or math.hypot(v[0] - jb, v[1] - ib) > 6)]
        keeps = [track_keep(c, ly) for ly, c in runs if c]
        for (j, i) in vias:
            keeps += via_keeps(j, i)
        leg.update({'runs': runs, 'vias': vias, 'keeps': keeps})
        add(leg, 1)
        return True

    def conflicted(leg):
        if 'keeps' not in leg:
            return True
        lift(leg, -1)
        bad = any(D[ly][j, i] > 0.5 for ly, cells in leg['runs'] for (j, i) in cells) or \
            any(D[ly][j, i] > 0.5 for (j, i) in leg['vias'] for ly in LY)
        lift(leg, 1)
        return bad

    pres = 0.5
    for it in range(iters):
        t1 = time.time()
        todo = legs if it == 0 else [l for l in legs if conflicted(l)]
        if it and not todo:
            break
        for leg in todo:
            add(leg, -1)
            leg.pop('keeps', None)
            sib = [l for l in bynet[leg['net']] if l is not leg]
            for l in sib:
                add(l, -1)
            route(leg, pres)
            for l in sib:
                add(l, 1)
        bad = [l for l in legs if conflicted(l)]
        log('  iter %d: rerouted %d, conflicts %d, vias %d (%.0fs)' % (it, len(todo), len(bad),
                                                                      sum(len(l.get('vias', [])) for l in legs), time.time() - t1))
        if not bad:
            break
        for ly in LY:
            H[ly] += 0.3 * (D[ly] > 1.5)
        pres *= 1.6

    bad = {id(l) for l in legs if conflicted(l)}
    hot = {}
    for leg in legs:
        if id(leg) in bad and 'runs' in leg:
            add(leg, -1)
            for ly, cells in leg['runs']:
                for (j, i) in cells:
                    if D[ly][j, i] > 0.5:
                        k = (ly, int(XS[i] // 2) * 2, int(YS[j] // 2) * 2)
                        hot[k] = hot.get(k, 0) + 1
            add(leg, 1)
    log('conflict hotspots (layer, x, y: cells): ' + '; '.join('%s %d,%d: %d' % (k[0], k[1], k[2], v)
                                                                for k, v in sorted(hot.items(), key=lambda kv: -kv[1])[:14]))
    done = 0
    for leg in legs:
        if id(leg) in bad or 'runs' not in leg:
            continue
        add(leg, -1)
        n = leg['net']
        st = []
        vpts = [(XS[i], YS[j]) for (j, i) in leg['vias']]
        nr = len(leg['runs'])
        for k, (ly, cells) in enumerate(leg['runs']):
            bl = FIX[ly] | ((CNT[ly] - uncrop(OWN[(ly, n)], 0, NY, 0, NX)) > 0) | (D[ly] > 0.5)
            pts = [(XS[i], YS[j]) for (j, i) in cells]
            # run ends: the leg's endpoints or the via it changes layer at
            # run ends sit on via cells (same grid point as the via) or on the leg's endpoints
            if k == 0:
                pts[0] = leg['a']
            if k == nr - 1:
                pts[-1] = leg['b']
            for (j, i) in (cells[0], cells[-1]):
                bl[max(0, j - 6):j + 7, max(0, i - 6):i + 7] = False
            if len(pts) > 1:
                pts = rlib.pull_tight(rlib.simplify(pts), bl, x0, y0)
                for seg, inside in rlib.split_neck(pts):
                    bd.stage_track(seg, neck if inside else width[ly], n, ly, st)
        for (x, y) in vpts:
            bd.stage_via(x, y, n, st, d=via_d)
        bd.commit(st)
        add(leg, 1)
        done += 1
    log('negotiate3d: %d of %d legs routed, %d new vias' % (done, len(legs), sum(len(l['vias']) for l in legs if id(l) not in bad and 'runs' in l)))
    return [l for l in legs if id(l) in bad or 'runs' not in l]
