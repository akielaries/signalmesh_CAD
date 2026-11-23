import heapq
import math
import os
import re
import sys

import proute
import pslib
import rlib

# p/n skew tuning for differential pairs between two parts: the shorter half of each pair is lengthened with
# octilinear bumps (chamfered, 0/45/90 relative to the run) on its longest runs outside the ball fields until
# the two halves match within TOL. lengths are copper flight paths pad to pad.
# usage: skewtune.py <board> <refA> <refB> <regex of pair base names>
PCB, RA, RB, PAT = sys.argv[1:5]
TOL = float(os.environ.get('TOL', '0.25'))
CLR = 0.15
C, F, GAP_B = 0.15, 0.4, 0.3      # chamfer, flat top, spacing between bumps (3w for 0.1 mm tracks)
r = pslib.Router(PCB, ['U100', 'U11', 'U21'])
rlib.BGA_RECTS.append((120.8, 62.35, 179.3, 76.65, 0.10))
bd = r.bd


def tracks_of(net):
    ts = bd.b.Tracks()
    return [ts[i] for i in range(len(ts)) if ts[i].GetNetname() == net and ts[i].GetClass() != 'PCB_VIA']


def pad(net, ref):
    for (x, y, hx, hy, n, l, rr, p) in bd.pads:
        if n == net and p.GetParentFootprint().GetReference() == ref:
            return (x, y)


def flight(net):
    key = lambda x, y: (round(x, 3), round(y, 3))
    g = {}
    for t in tracks_of(net):
        a = key(t.GetStart().x / 1e6, t.GetStart().y / 1e6)
        b_ = key(t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)
        ln = t.GetLength() / 1e6
        g.setdefault(a, []).append((b_, ln))
        g.setdefault(b_, []).append((a, ln))
    pa, pb = pad(net, RA), pad(net, RB)
    if not pa or not pb:
        return None
    s, e = key(*pa), key(*pb)
    if s not in g or e not in g:
        # a pad end may sit inside a track rather than on its vertex: take the nearest vertex
        near = lambda p: min(g, key=lambda v: math.hypot(v[0] - p[0], v[1] - p[1])) if g else None
        s, e = near(pa), near(pb)
    dist = {s: 0.0}
    q = [(0.0, s)]
    while q:
        d, u = heapq.heappop(q)
        if u == e:
            return d
        if d > dist.get(u, 1e9):
            continue
        for v, w in g.get(u, []):
            if d + w < dist.get(v, 1e9):
                dist[v] = d + w
                heapq.heappush(q, (d + w, v))
    return None


def bump_pts(a, b_, nrm, amp, k):
    ux, uy = b_[0] - a[0], b_[1] - a[1]
    ll = math.hypot(ux, uy)
    ux, uy = ux / ll, uy / ll
    pitch = 4 * C + F + GAP_B
    s0 = (ll - (k * pitch - GAP_B)) / 2
    pts = [a]
    for i in range(k):
        s = s0 + i * pitch
        for (t, h) in [(s, 0), (s + C, C), (s + C, amp - C), (s + 2 * C, amp), (s + 2 * C + F, amp),
                       (s + 3 * C + F, amp - C), (s + 3 * C + F, C), (s + 4 * C + F, 0)]:
            pts.append((a[0] + ux * t + nrm[0] * h, a[1] + uy * t + nrm[1] * h))
    pts.append(b_)
    return pts


def added(amp, k):
    return k * (2 * (amp - 2 * C) + 4 * C * math.sqrt(2) - 4 * C)


def lengthen(net, need):
    for t in sorted(tracks_of(net), key=lambda t: -t.GetLength()):
        if need <= TOL / 2:
            break
        w = t.GetWidth() / 1e6
        ll = t.GetLength() / 1e6
        kmax = int((ll - 0.6 + GAP_B) / (4 * C + F + GAP_B))
        if kmax < 1:
            continue
        a = (t.GetStart().x / 1e6, t.GetStart().y / 1e6)
        b_ = (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)
        if rlib.in_esc(*a) or rlib.in_esc(*b_):
            continue
        ly = bd.b.GetLayerName(t.GetLayer())
        ux, uy = (b_[0] - a[0]) / ll, (b_[1] - a[1]) / ll
        done = False
        for amp in (1.0, 0.7, 0.5, 0.4):
            k = min(kmax, max(1, math.ceil(need / added(amp, 1))))
            while k >= 1 and not done:
                amp_k = amp
                if added(amp, k) > need:
                    amp_k = max(2 * C + 0.05, (need / k + 4 * C - 4 * C * math.sqrt(2)) / 2 + 2 * C)
                for nrm in ((-uy, ux), (uy, -ux)):
                    pts = bump_pts(a, b_, nrm, amp_k, k)
                    cached = [q for q in bd.tracks if q[5] == net and q[6] == ly and
                              max(abs(q[0] - a[0]), abs(q[1] - a[1]), abs(q[2] - b_[0]), abs(q[3] - b_[1])) < 1e-6]
                    for q in cached:
                        bd.tracks.remove(q)
                    if proute.segs_clear(bd, ly, pts, w / 2, {net}, CLR):
                        st = []
                        bd.stage_track(pts, w, net, ly, st)
                        bd.commit(st)
                        bd.b.Remove(t)
                        need -= added(amp_k, k)
                        done = True
                        break
                    bd.tracks.extend(cached)
                k -= 1
            if done:
                break
    return need


fps = {}
for (x, y, hx, hy, n, l, rr, p) in bd.pads:
    fps.setdefault(p.GetParentFootprint().GetReference(), set()).add(n)
bases = sorted({n[:-2] for n in fps.get(RA, set()) if n.endswith('_P') and re.search(PAT, n[:-2]) and n in fps.get(RB, set())})
rows = []
for base in bases:
    lp, ln = flight(base + '_P'), flight(base + '_N')
    if lp is None or ln is None:
        continue
    if abs(lp - ln) > TOL:
        short = base + ('_P' if lp < ln else '_N')
        left = lengthen(short, abs(lp - ln))
        lp2, ln2 = flight(base + '_P'), flight(base + '_N')
        rows.append((base, lp, ln, lp2, ln2))
    else:
        rows.append((base, lp, ln, lp, ln))
bd.save()
ok = sum(1 for x in rows if x[3] is not None and x[4] is not None and abs(x[3] - x[4]) <= TOL)
print('pairs measured %d; within %.2f mm after tuning: %d' % (len(rows), TOL, ok))
for base, lp, ln, lp2, ln2 in sorted(rows, key=lambda x: -abs((x[3] or 0) - (x[4] or 0))):
    if abs(lp - ln) > TOL:
        print('  %-16s skew %5.2f -> %5.2f mm' % (base, abs(lp - ln), abs((lp2 or 0) - (ln2 or 0))))
