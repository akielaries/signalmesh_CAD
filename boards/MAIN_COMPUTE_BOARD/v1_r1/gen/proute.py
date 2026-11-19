import os
import math

import numpy as np
import pcbnew

import rlib
from rlib import MM


def mid(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def pad_free(bd, fp, layer='F.Cu', clr=0.15, skip=()):
    own = {p.GetNetname() for p in rlib.L(fp.Pads())}
    for p in rlib.L(fp.Pads()):
        px, py = p.GetPosition().x / MM, p.GetPosition().y / MM
        hx = p.GetBoundingBox().GetWidth() / 2 / MM
        hy = p.GetBoundingBox().GetHeight() / 2 / MM
        blocked, xs, ys = bd.grid(layer, (px - hx - 0.4, py - hy - 0.4, px + hx + 0.4, py + hy + 0.4), 0.0, own,
                                  clr, margin=0.0)
        X, Y = np.meshgrid(xs, ys)
        if (blocked & (abs(X - px) <= hx) & (abs(Y - py) <= hy)).any():
            return False
    cy = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
    for o in rlib.L(bd.b.Footprints()):
        if o.GetReference() == fp.GetReference() or o.IsFlipped() or o.GetReference() in skip:
            continue
        oc = o.GetCourtyard(pcbnew.F_CrtYd)
        if oc.OutlineCount() and cy.Intersects(oc.BBox()):
            return False
    return True


def place_pair_caps(bd, refs, toward, away, dist_list=tuple(x * 0.5 for x in range(4, 30)), pitch=0.75,
                    toward_nets=()):
    fps = [bd.b.FindFootprintByReference(r) for r in refs]
    orig = [(fp.GetPosition(), fp.GetOrientationDegrees()) for fp in fps]
    ux, uy = toward[0] - away[0], toward[1] - away[1]
    ul = math.hypot(ux, uy) or 1.0
    ux, uy = ux / ul, uy / ul
    ang = round(math.degrees(math.atan2(-uy, ux)) / 90.0) * 90.0
    # side-by-side offset perpendicular to the cap axis
    ca, sa = math.cos(math.radians(ang)), -math.sin(math.radians(ang))
    px, py = -sa, ca
    for d in dist_list:
        for lat in (0.0, 0.4, -0.4, 0.8, -0.8, 1.2, -1.2, 1.8, -1.8, 2.5, -2.5, 3.5, -3.5, 4.5, -4.5):
            cx, cy = away[0] + ux * d + px * lat, away[1] + uy * d + py * lat
            for k, fp in enumerate(fps):
                s = (k - 0.5) * pitch
                fp.SetOrientationDegrees(ang)
                fp.SetPosition(pcbnew.VECTOR2I(int((cx + px * s) * MM), int((cy + py * s) * MM)))
                # the pad on the `toward` side net must face `toward`
                pads = [p for p in rlib.L(fp.Pads()) if p.GetNetname()]
                near = [p for p in pads if p.GetNetname() in toward_nets]
                far = [p for p in pads if p.GetNetname() not in toward_nets]
                if near and far:
                    dn = math.hypot(near[0].GetPosition().x / MM - toward[0], near[0].GetPosition().y / MM - toward[1])
                    df = math.hypot(far[0].GetPosition().x / MM - toward[0], far[0].GetPosition().y / MM - toward[1])
                    if dn > df:
                        fp.SetOrientationDegrees(ang + 180)
            if all(pad_free(bd, fp, skip=refs) for fp in fps):
                bd.reload()
                return True
    for fp, (pos, ang0) in zip(fps, orig):
        fp.SetOrientationDegrees(ang0)
        fp.SetPosition(pos)
    return False


BGA = (109.5, 79.5, 134.5, 104.5)


def in_bga(p):
    x0, y0, x1, y1 = BGA
    return x0 < p[0] < x1 and y0 < p[1] < y1


CONN = (120.8, 62.35, 179.3, 76.65)  # vita pin field


ESC = [BGA]


def free_r_of(p, layer='F.Cu'):
    for x0, y0, x1, y1 in ESC:
        if x0 < p[0] < x1 and y0 < p[1] < y1:
            return min(p[0] - x0, x1 - p[0], p[1] - y0, y1 - p[1]) + 0.8
    x0, y0, x1, y1 = CONN
    if layer != 'F.Cu' and x0 < p[0] < x1 and y0 < p[1] < y1:
        return 2.5
    return 1.2


def route_pair(bd, netp, netn, sp, sn, ep, en, layer, w, gap, clr):
    r = route_pair_c(bd, netp, netn, sp, sn, ep, en, layer, w, gap, clr)
    if r[0]:
        return r
    f = route_pair_f(bd, netp, netn, sp, sn, ep, en, layer, w, gap, clr)
    if f[0]:
        return f
    if r[1] == 'too short to couple':
        u = route_uncoupled(bd, netp, netn, sp, sn, ep, en, layer, w, clr)
        if u[0]:
            return u
    return None, (r[1], f[1])


def route_uncoupled(bd, netp, netn, sp, sn, ep, en, layer, w, clr):
    # short escape legs: each half on its own
    staged = []
    a = bd.path(layer, sp, ep, w / 2, {netp}, clr, margin=2.0)
    if not a:
        return None, 'uncoupled p failed'
    bd.stage_track(a, w, netp, layer, staged)
    b_ = bd.path(layer, sn, en, w / 2, {netn}, clr, margin=2.0)
    if not b_:
        bd.unstage(staged)
        return None, 'uncoupled n failed'
    bd.stage_track(b_, w, netn, layer, staged)
    return staged, (rlib.length(a), rlib.length(b_))


def route_pair_f(bd, netp, netn, sp, sn, ep, en, layer, w, gap, clr):
    # route p, then n following p at the coupled pitch; all or nothing
    staged = []
    margin = 4.0
    # p reserves room for n alongside it, except where the ends cannot couple (bga, connector pins)
    ex = [(sp[0], sp[1], free_r_of(sp)), (sn[0], sn[1], free_r_of(sn)), (ep[0], ep[1], free_r_of(ep)),
          (en[0], en[1], free_r_of(en))]
    a = None
    for wide in (w + gap, (w + gap) * 0.6, 0.0):
        a = bd.path(layer, sp, ep, w / 2, {netp}, clr, margin=margin, wide=wide, wide_except=ex)
        if a:
            break
    if not a:
        return None, 'p path failed'
    bd.stage_track(a, w, netp, layer, staged)
    b_ = offset_n(bd, a, sp, sn, ep, en, layer, w, gap, clr, netn, netp)
    if not b_:
        # fallback: grid search that follows p at the pair pitch
        b_ = bd.path(layer, sn, en, w / 2, {netn, netp}, clr, margin=margin, follow=a, follow_d=w + gap)
    if b_:
        # make sure n does not crowd p closer than the pair gap
        if min_dist(a, b_) < w + gap - 0.009:
            b_ = None
    if not b_:
        bd.unstage(staged)
        return None, 'n path failed'
    bd.stage_track(b_, w, netn, layer, staged)
    return staged, (rlib.length(a), rlib.length(b_))


def min_dist(pa, pb):
    def dseg(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ll = dx * dx + dy * dy
        t = 0 if ll == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ll))
        return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)
    best = 1e9
    # skip the very ends (they sit on pads that may be closer by design)
    for seg_a in zip(pa, pa[1:]):
        for p in pb[1:-1]:
            best = min(best, dseg(p, *seg_a))
    for seg_b in zip(pb, pb[1:]):
        for p in pa[1:-1]:
            best = min(best, dseg(p, *seg_b))
    return best


def dump(bd, layer, a, b_, half_w, own, clr, path_png, follow=None, follow_d=None, margin=4.0, scale=3):
    # debug image of the obstacle map (grey), partner keep-off (pink), partner (red), ends (blue/green)
    from PIL import Image, ImageDraw
    from scipy import ndimage
    x0, y0 = min(a[0], b_[0]) - margin, min(a[1], b_[1]) - margin
    x1, y1 = max(a[0], b_[0]) + margin, max(a[1], b_[1]) + margin
    bl, xs, ys = bd.grid(layer, (x0, y0, x1, y1), half_w, own, clr)
    img = np.full(bl.shape + (3,), 235, np.uint8)
    img[bl] = (70, 70, 70)
    if follow:
        ref = np.zeros(bl.shape, bool)
        for (xa, ya), (xb, yb) in zip(follow, follow[1:]):
            n = max(2, int(math.hypot(xb - xa, yb - ya) / (rlib.G / 2)))
            for k in range(n + 1):
                t = k / n
                i = int(round((xa + t * (xb - xa) - x0) / rlib.G))
                j = int(round((ya + t * (yb - ya) - y0) / rlib.G))
                if 0 <= j < ref.shape[0] and 0 <= i < ref.shape[1]:
                    ref[j, i] = True
        dist = ndimage.distance_transform_edt(~ref) * rlib.G
        img[(dist < follow_d - 0.03) & ~bl] = (230, 150, 150)
        img[ref] = (200, 0, 0)
    im = Image.fromarray(img).resize((bl.shape[1] * scale, bl.shape[0] * scale), Image.NEAREST)
    d = ImageDraw.Draw(im)
    for p, c in ((a, 'blue'), (b_, 'green')):
        i, j = (p[0] - x0) / rlib.G * scale, (p[1] - y0) / rlib.G * scale
        d.ellipse([i - 8, j - 8, i + 8, j + 8], outline=c, width=3)
    im.save(path_png)


INNER = {'In2.Cu': (0.115, 0.10), 'In5.Cu': (0.115, 0.10), 'B.Cu': (0.10, 0.18)}


def via_spot_ok(bd, x, y, net, staged_own=(), r=0.225, clr=0.12):
    for ly in rlib.LAYERS:
        # a via may sit inside another net's pour (the pour clears around it)
        bl, xs, ys = bd.grid(ly, (x - 0.1, y - 0.1, x + 0.1, y + 0.1), r, {net} | set(staged_own), clr, pours=False)
        if bl.any():
            return False
    for (vx, vy, vr, n) in bd.vias:
        if math.hypot(vx - x, vy - y) < 0.2 + 0.26:
            return False
    return True


def existing_via(bd, p, net, maxd=0.9):
    best = None
    for (vx, vy, vr, n) in bd.vias:
        d = math.hypot(vx - p[0], vy - p[1])
        if n == net and d < maxd and (best is None or d < best[0]):
            best = (d, (vx, vy))
    return best[1] if best else None


def drop_via(bd, p, net, toward, staged, w=0.1, radii=(0.75, 0.9, 1.05, 1.25, 1.5, 1.8, 2.2), layer='F.Cu'):
    # via near a pad on layer (reuse the dogbone if there is one), with a short stub on that layer
    v = existing_via(bd, p, net)
    if v:
        return v
    ang0 = round(math.atan2(toward[1] - p[1], toward[0] - p[0]) / (math.pi / 4)) * (math.pi / 4)
    for rad in radii:
        for k in range(8):
            da = (k + 1) // 2 * (1 if k % 2 else -1) * (math.pi / 4)
            a = ang0 + da
            x, y = p[0] + rad * math.cos(a), p[1] + rad * math.sin(a)
            if not via_spot_ok(bd, x, y, net):
                continue
            st = bd.path(layer, p, (x, y), w / 2, {net}, 0.12, margin=1.0)
            if not st:
                continue
            bd.stage_track(st, w, net, layer, staged)
            bd.stage_via(x, y, net, staged)
            return (x, y)
    return None


def route_pair_any(bd, netp, netn, sp, sn, ep, en, clr, layers=None, s_layers=('F.Cu',), e_layers=('F.Cu',)):
    if layers is None:
        layers = ('F.Cu',) + tuple(os.environ.get('INNER', 'In2.Cu,In5.Cu').split(','))
    # direct on an outer layer both ends' pads are on, else vias dropped beside the pads (stub on
    # the pad's own layer) and the pair on the given layer
    why = []
    for ly in layers:
        if ly in ('F.Cu', 'B.Cu') and ly in s_layers and ly in e_layers:
            w, gap = (0.10, 0.18)
            s, l = route_pair(bd, netp, netn, sp, sn, ep, en, ly, w, gap, clr)
            if s:
                return s, (ly, l)
            why.append((ly, l))
            continue
        if ly == 'F.Cu':
            why.append((ly, 'pads not on F.Cu'))
            continue
        w, gap = INNER[ly]
        staged = []
        mids = mid(sp, sn), mid(ep, en)
        vsp = drop_via(bd, sp, netp, mids[1], staged, layer=s_layers[0])
        vsn = drop_via(bd, sn, netn, mids[1], staged, layer=s_layers[0]) if vsp else None
        vep = drop_via(bd, ep, netp, mids[0], staged, layer=e_layers[0]) if vsn else None
        ven = drop_via(bd, en, netn, mids[0], staged, layer=e_layers[0]) if vep else None
        if not ven:
            bd.unstage(staged)
            why.append((ly, 'via drop failed %s' % [bool(q) for q in (vsp, vsn, vep, ven)]))
            continue
        s, l = route_pair(bd, netp, netn, vsp, vsn, vep, ven, ly, w, gap, clr)
        if s:
            return staged + s, (ly, l)
        why.append((ly, l))
        bd.unstage(staged)
    return None, why


def offset_n(bd, a, sp, sn, ep, en, layer, w, gap, clr, netn, netp):
    # n = exact parallel offset of p's coupled middle, joined to its pads by short searched stubs
    from shapely.geometry import LineString, Point
    from shapely.ops import substring
    pl = LineString(a)
    rs, re_ = free_r_of(sp), free_r_of(ep)
    if pl.length < rs + re_ + 0.5:
        return None
    mid_l = substring(pl, rs, pl.length - re_)
    if mid_l.length < 0.3:
        return None
    # n sits on the side of p where its start pad is
    (x0, y0), (x1, y1) = a[0], a[1] if len(a) > 1 else a[0]
    best = None
    for side in (1, -1):
        off = mid_l.offset_curve(side * (w + gap), join_style=2, mitre_limit=2.0)
        if off.is_empty or off.geom_type != 'LineString':
            continue
        d = Point(sn).distance(Point(off.coords[0])) + Point(en).distance(Point(off.coords[-1]))
        if best is None or d < best[0]:
            best = (d, off)
    if not best:
        return None
    oc = [tuple(c) for c in best[1].coords]
    # offset section must clear everything except the pair itself
    staged_n = []
    if not segs_clear(bd, layer, oc, w / 2, {netn, netp}, clr):
        return None
    s1 = bd.path(layer, sn, oc[0], w / 2, {netn}, clr, margin=1.5)
    if not s1:
        return None
    bd.stage_track(s1, w, netn, layer, staged_n)
    s2 = bd.path(layer, oc[-1], en, w / 2, {netn}, clr, margin=1.5)
    bd.unstage(staged_n)
    if not s2:
        return None
    return rlib.simplify(list(s1) + oc[1:-1] + list(s2))


def segs_clear(bd, layer, pts, half_w, own, clr, partner=None):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    win = (min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1)
    own = set(own) | ({partner[0]} if partner else set())
    bl, gx, gy = bd.grid(layer, win, half_w, own, clr, margin=0.0, partner=partner)
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        n = max(2, int(math.hypot(xb - xa, yb - ya) / (rlib.G / 2)))
        for k in range(n + 1):
            t = k / n
            i = int(round((xa + t * (xb - xa) - win[0]) / rlib.G))
            j = int(round((ya + t * (yb - ya) - win[1]) / rlib.G))
            if bl[j, i]:
                return False
    return True


def pair_frame(sp, sn, ep, en, layer, w, gap):
    cs, ce = mid(sp, sn), mid(ep, en)
    rs = max(free_r_of(sp, layer), free_r_of(sn, layer))
    re_ = max(free_r_of(ep, layer), free_r_of(en, layer))
    return cs, ce, rs, re_, w + gap / 2


def route_pair_c(bd, netp, netn, sp, sn, ep, en, layer, w, gap, clr, waypoint=None):
    # centreline method: plan one track of the pair's full width, offset both halves exactly.
    # with a waypoint the centreline goes out to it and back (length matching), the return half
    # kept a pair width plus clearance away from the outbound half
    from shapely.geometry import LineString, Point
    from shapely.ops import substring
    cs, ce, rs, re_, half = pair_frame(sp, sn, ep, en, layer, w, gap)
    if waypoint is None:
        c = bd.path(layer, cs, ce, half, {netp, netn}, clr, free=((cs[0], cs[1], rs), (ce[0], ce[1], re_)))
    else:
        c1 = bd.path(layer, cs, waypoint, half, {netp, netn}, clr, free=((cs[0], cs[1], rs),), margin=10.0)
        c = None
        if c1:
            l1 = LineString(c1)
            st = []
            if l1.length > 1.2:
                body = [tuple(q) for q in substring(l1, 0, l1.length - 1.0).coords]
                bd.stage_track(body, 2 * half, '__pair_out', layer, st)
            c2 = bd.path(layer, waypoint, ce, half, {netp, netn}, clr, free=((ce[0], ce[1], re_),), margin=10.0)
            bd.unstage(st)
            if c2:
                c = rlib.simplify(list(c1) + list(c2[1:]))
    if not c:
        return None, 'centreline failed'
    cl = LineString(c)
    if cl.length < rs + re_ + 0.3:
        return None, 'too short to couple'
    # trim where the centreline last leaves each free circle (geometric, not arc length)
    ts = [k * 0.05 for k in range(int(cl.length / 0.05) + 1)]
    pin = [cl.interpolate(s) for s in ts]
    t0 = max([s for s, q in zip(ts, pin) if q.distance(Point(cs)) <= rs + 0.05] or [0.0])
    t1 = min([s for s, q in zip(ts, pin) if q.distance(Point(ce)) <= re_ + 0.05] or [cl.length])
    if t1 - t0 < 0.3:
        return None, 'too short to couple'
    # octilinear centreline: pull the grid staircase tight with 0/45/90 doglegs only, against the
    # obstacles for the full pair width; mitred offsets then keep both halves at 45-degree corners
    cpts = [tuple(q) for q in substring(cl, t0, t1).coords]
    xs_ = [p[0] for p in cpts]
    ys_ = [p[1] for p in cpts]
    win = (min(xs_) - 1.0, min(ys_) - 1.0, max(xs_) + 1.0, max(ys_) + 1.0)
    bl, _, _ = bd.grid(layer, win, half, {netp, netn}, clr, margin=0.0)
    core = LineString(rlib.pull_tight(rlib.simplify(cpts), bl, win[0], win[1]))
    offs = {}
    for side in (1, -1):
        o = core.offset_curve(side * (w + gap) / 2, join_style=2, mitre_limit=2.5)
        if o.is_empty or o.geom_type != 'LineString':
            return None, 'offset failed'
        offs[side] = [tuple(q) for q in o.coords]
    # p takes the side whose start is nearer its pad
    dp = {s: Point(sp).distance(Point(offs[s][0])) + Point(ep).distance(Point(offs[s][-1])) for s in offs}
    sp_side = 1 if dp[1] <= dp[-1] else -1
    po, no = offs[sp_side], offs[-sp_side]
    if not segs_clear(bd, layer, po, w / 2, {netp, netn}, clr) or not segs_clear(bd, layer, no, w / 2, {netp, netn}, clr):
        return None, 'offset blocked'
    staged = []
    bd.stage_track(po, w, netp, layer, staged)
    bd.stage_track(no, w, netn, layer, staged)
    legs = {}
    gmin = gap - 0.01
    for net, a, b_, key in ((netp, sp, po[0], 'ps'), (netn, sn, no[0], 'ns'), (netp, po[-1], ep, 'pe'),
                            (netn, no[-1], en, 'ne')):
        other = netn if net == netp else netp
        s = bd.path(layer, a, b_, w / 2, {net}, clr, margin=3.0, partner=(other, gmin))
        if not s:
            bd.unstage(staged)
            return None, 'stub %s failed' % key
        bd.stage_track(s, w, net, layer, staged)
        legs[key] = s
    pp = rlib.simplify(list(legs['ps']) + po[1:-1] + list(legs['pe']))
    nn = rlib.simplify(list(legs['ns']) + no[1:-1] + list(legs['ne']))
    return staged, (rlib.length(pp), rlib.length(nn))
