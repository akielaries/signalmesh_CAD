import math
import os
import re
import sys
import time

import negroute
import proute
import pslib
import rlib

# negotiated differential-pair router. each open pair between two parts is routed as one wide track
# (2w + gap) along its centreline with negotiated congestion, so all pairs compete for room together;
# the centreline is then split into P and N at +-(w + gap)/2 (mitred, so 0/45/90 stays 0/45/90) and
# each half is joined to its via at both ends. pairs whose halves would have to cross over are left open.
# usage: pairroute.py <board> <refA> <refB> <regex of pair base names>
PCB, RA, RB, PAT = sys.argv[1:5]
LAYERS = tuple(os.environ.get('LAYERS', 'In2.Cu,In7.Cu,In5.Cu,B.Cu').split(','))
COST = {'In2.Cu': 1.0, 'In7.Cu': 1.0, 'In5.Cu': 1.05, 'B.Cu': 1.2, 'F.Cu': 1.3}
WG = {'In2.Cu': (0.09, 0.125), 'In7.Cu': (0.09, 0.125), 'In5.Cu': (0.09, 0.125), 'B.Cu': (0.10, 0.18), 'F.Cu': (0.10, 0.18)}
CLR = 0.15
t0 = time.time()
r = pslib.Router(PCB, os.environ.get('ESC_REFS', 'U100').split(','))
r.clr = CLR
bd = r.bd
for q in os.environ.get('EXTRA_ESC', '').split(';'):
    if q:
        rlib.BGA_RECTS.append(tuple(float(v) for v in q.split(',')) + (0.10,))
proute.ESC[:] = [q[:4] for q in rlib.BGA_RECTS]


def pads(ref):
    return {n: ((x, y), lays) for (x, y, hx, hy, n, lays, rnd, p) in bd.pads if p.GetParentFootprint().GetReference() == ref and n}


pa, pb = pads(RA), pads(RB)
bases = sorted({n[:-2] for n in pa if n.endswith('_P') and n in pb and n[:-2] + '_N' in pa and n[:-2] + '_N' in pb
                and re.search(PAT, n[:-2])})


def done_net(n):
    ts = r.terms(n)
    return len(ts) > 1 and len(set(r.comp(n, ts))) == 1


todo = [b for b in bases if not (done_net(b + '_P') and done_net(b + '_N'))]
print('pairs %s<->%s matching %s: %d, open %d' % (RA, RB, PAT, len(bases), len(todo)), flush=True)


PITCH = {'U100': 1.0, 'J20': 1.27, 'U11': 0.8, 'U21': 0.8}


def via_for(net, pad, toward, ref=None):
    (p, lays) = pad
    v = proute.existing_via(bd, p, net, maxd=1.2)
    if v:
        return v
    st = []
    # a dogbone at one of the four diagonal cell centres of the part's ball/pin grid, nearest the target first
    h = PITCH.get(ref, 0) / 2
    if h:
        cands = sorted(((p[0] + sx * h, p[1] + sy * h) for sx in (-1, 1) for sy in (-1, 1)),
                       key=lambda q: math.hypot(q[0] - toward[0], q[1] - toward[1]))
        for q in cands:
            if proute.via_spot_exact(bd, q[0], q[1], net):
                ly = r.side(lays)
                if bd.path(ly, p, q, 0.05, {net}, 0.09, margin=0.6, half_in=0.05):
                    bd.stage_track([p, q], 0.1, net, ly, st)
                    bd.stage_via(q[0], q[1], net, st, d=0.4)
                    bd.commit(st)
                    return q
        st = []
    v = proute.drop_via(bd, p, net, toward, st, w=0.1, radii=(0.6, 0.75, 0.9, 1.1, 1.3, 1.6), layer=r.side(lays))
    if v:
        bd.commit(st)
        return v
    bd.unstage(st)
    return None


mid = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
legs, novia = [], []
info = {}
def pair_vias(P, N, pp, pn, toward, ref):
    # both halves of a pair take the same diagonal dogbone direction, so their vias sit side by side and
    # the pair's centre lands in a channel; existing vias of either half are reused
    ep, en = proute.existing_via(bd, pp[0], P, maxd=1.2), proute.existing_via(bd, pn[0], N, maxd=1.2)
    h = PITCH.get(ref, 0) / 2
    if (ep and en) or not h:
        return ep or via_for(P, pp, toward, ref), en or via_for(N, pn, toward, ref)
    c = mid(pp[0], pn[0])
    for sx, sy in sorted(((sx, sy) for sx in (-1, 1) for sy in (-1, 1)),
                         key=lambda s: math.hypot(c[0] + s[0] * h - toward[0], c[1] + s[1] * h - toward[1])):
        st, got = [], []
        for net, (p, lays), e in ((P, pp, ep), (N, pn, en)):
            if e:
                got.append(e)
                continue
            q = (p[0] + sx * h, p[1] + sy * h)
            ly = r.side(lays)
            if proute.via_spot_exact(bd, q[0], q[1], net) and bd.path(ly, p, q, 0.05, {net}, 0.09, margin=0.6, half_in=0.05):
                bd.stage_track([p, q], 0.1, net, ly, st)
                bd.stage_via(q[0], q[1], net, st, d=0.4)
                got.append(q)
            else:
                break
        if len(got) == 2:
            bd.commit(st)
            return tuple(got)
        bd.unstage(st)
    return via_for(P, pp, toward, ref), via_for(N, pn, toward, ref)


for base in todo:
    P, N = base + '_P', base + '_N'
    ca, cb = mid(pa[P][0], pa[N][0]), mid(pb[P][0], pb[N][0])
    vpa, vna = pair_vias(P, N, pa[P], pa[N], cb, RA)
    vpb, vnb = pair_vias(P, N, pb[P], pb[N], ca, RB)
    pin = None
    # an end without vias uses its pads; both pads on F.Cu then pins the pair to F.Cu
    if not (vpa and vna):
        if 'F.Cu' in pa[P][1] and 'F.Cu' in pa[N][1]:
            vpa, vna, pin = pa[P][0], pa[N][0], 'F.Cu'
    if not (vpb and vnb):
        if 'F.Cu' in pb[P][1] and 'F.Cu' in pb[N][1]:
            vpb, vnb, pin = pb[P][0], pb[N][0], 'F.Cu'
    if not all((vpa, vna, vpb, vnb)):
        novia.append(base)
        continue
    info[base] = (vpa, vna, vpb, vnb)
    leg = {'net': P, 'nets': [P, N], 'a': mid(vpa, vna), 'b': mid(vpb, vnb), 'base': base}
    if pin:
        leg['ly'] = pin
    legs.append(leg)
print('pair legs %d; no via room: %s (%.0fs)' % (len(legs), novia or 'none', time.time() - t0), flush=True)


def offset(pts, d):
    # offset an octilinear polyline by d to its left (y down): mitred joins keep the angles
    segs = []
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        L = math.hypot(xb - xa, yb - ya)
        if L < 1e-6:
            continue
        nx, ny = (yb - ya) / L, -(xb - xa) / L
        segs.append(((xa + nx * d, ya + ny * d), (xb + nx * d, yb + ny * d)))
    if not segs:
        return None
    out = [segs[0][0]]
    for (a1, b1), (a2, b2) in zip(segs, segs[1:]):
        d1 = (b1[0] - a1[0], b1[1] - a1[1])
        d2 = (b2[0] - a2[0], b2[1] - a2[1])
        den = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(den) < 1e-9:
            out.append(b1)
            continue
        t = ((a2[0] - a1[0]) * d2[1] - (a2[1] - a1[1]) * d2[0]) / den
        out.append((a1[0] + d1[0] * t, a1[1] + d1[1] * t))
    out.append(segs[-1][1])
    return out


def dogleg(a, b):
    # 0/45/90 join from a to b: diagonal first, then straight
    dx, dy = b[0] - a[0], b[1] - a[1]
    k = min(abs(dx), abs(dy))
    m = (a[0] + math.copysign(k, dx), a[1] + math.copysign(k, dy))
    return [a, m, b] if math.hypot(m[0] - b[0], m[1] - b[1]) > 1e-4 and math.hypot(m[0] - a[0], m[1] - a[1]) > 1e-4 else [a, b]


def commit_pair(leg, pts, ly):
    base = leg['base']
    vpa, vna, vpb, vnb = info[base]
    w, gap = WG[ly]
    d = (w + gap) / 2
    left, right = offset(pts, d), offset(pts, -d)
    if not left or not right:
        return False
    # which side P runs on, from the start; the far end must agree or the halves would cross
    dl = math.hypot(left[0][0] - vpa[0], left[0][1] - vpa[1]) + math.hypot(left[-1][0] - vpb[0], left[-1][1] - vpb[1])
    dr = math.hypot(right[0][0] - vpa[0], right[0][1] - vpa[1]) + math.hypot(right[-1][0] - vpb[0], right[-1][1] - vpb[1])
    pp, nn = (left, right) if dl < dr else (right, left)
    if math.hypot(pp[-1][0] - vpb[0], pp[-1][1] - vpb[1]) > math.hypot(pp[-1][0] - vnb[0], pp[-1][1] - vnb[1]):
        return False
    st = []
    for net, path, va, vb in ((leg['base'] + '_P', pp, vpa, vpb), (leg['base'] + '_N', nn, vna, vnb)):
        full = dogleg(va, path[0])[:-1] + path + dogleg(path[-1], vb)[1:]
        bd.stage_track(full, w, net, ly, st)
    bd.commit(st)
    return True


left = []
if legs:
    ax = [l['a'][0] for l in legs] + [l['b'][0] for l in legs]
    ay = [l['a'][1] for l in legs] + [l['b'][1] for l in legs]
    win = (max(50.5, min(ax) - 6), max(53.6, min(ay) - 6), min(190.6, max(ax) + 6), min(146.9, max(ay) + 6))
    wid = {ly: 2 * WG[ly][0] + WG[ly][1] for ly in LAYERS + (('F.Cu',) if 'F.Cu' not in LAYERS else ())}
    left = negroute.negotiate(bd, legs, win, wid, {ly: COST[ly] for ly in wid}, iters=int(os.environ.get('NEG_ITERS', '25')),
                              clr=CLR, neck=2 * 0.09 + 0.125, log=lambda s: print(s, flush=True), commit_fn=commit_pair)
bd.save()
r2 = pslib.Router(PCB, [])
ok = [b for b in todo if all(len(set(r2.comp(b + s, r2.terms(b + s)))) == 1 for s in ('_P', '_N'))]
print('pairs complete now: %d of %d open; still open: %s (%.0f s)' % (len(ok), len(todo), ' '.join(sorted(set(todo) - set(ok))), time.time() - t0))
