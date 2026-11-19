import heapq
import json
import math
import os
import sys

import pcbnew

import proute
import rlib

# ddr length matching: dq/dm to their dqs, addr/cmd/ctrl to ck, measured ball to ball through the
# copper (the fly-by tail to the terminator is not counted). meanders go on 0.23 mm runs outside the
# ball fields, on whichever side has room
PCB = sys.argv[1]
META = json.load(open(os.environ.get('ROUTES', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ddr_routes.json'))))
FPGA_R = (109.5, 79.5, 134.5, 104.5)
DRAM_R = (105.455, 115.505, 121.545, 125.595)
rlib.BGA_RECTS[:] = [FPGA_R + (0.09,), (120.8, 62.35, 179.3, 76.65, 0.10), DRAM_R + (0.09,)]
TOL_LANE, TOL_CMD = 1.4, 3.0   # +-10 ps in a byte, +-20 ps addr/cmd to ck (inner ~7 ps/mm)
CLR = 0.15
C, F, GAP_B = 0.15, 0.5, 0.7   # chamfer, flat top, spacing (3w) for 0.23 mm traces

bd = rlib.Board(PCB)
U21 = [p.GetParentFootprint().GetReference() for (x, y, hx, hy, n, l, r, p) in bd.pads
       if p.GetParentFootprint().GetValue().startswith('MT41K')][0]


def tracks_of(net):
    ts = bd.b.Tracks()
    return [ts[i] for i in range(len(ts)) if ts[i].GetNetname() == net and ts[i].GetClass() != 'PCB_VIA']


def ball(net, ref):
    for (x, y, hx, hy, n, l, r, p) in bd.pads:
        if n == net and p.GetParentFootprint().GetReference() == ref:
            return (x, y)


def flight(net):
    # shortest copper path fpga ball -> dram ball; vias join layers at equal xy
    key = lambda x, y: (round(x, 3), round(y, 3))
    g = {}
    for t in tracks_of(net):
        a = key(t.GetStart().x / 1e6, t.GetStart().y / 1e6)
        b_ = key(t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)
        ln = t.GetLength() / 1e6
        g.setdefault(a, []).append((b_, ln))
        g.setdefault(b_, []).append((a, ln))
    s, e = key(*ball(net, 'U100')), key(*ball(net, U21))
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


def lengthen(net, need, partner=None):
    # meander the longest wide runs of the flight path until need is met; returns what is left
    for t in sorted(tracks_of(net), key=lambda t: -t.GetLength()):
        if need <= 0.05:
            break
        w = t.GetWidth() / 1e6
        ll = t.GetLength() / 1e6
        kmax = int((ll - 1.0 + GAP_B) / (4 * C + F + GAP_B))
        if kmax < 1:
            continue
        a = (t.GetStart().x / 1e6, t.GetStart().y / 1e6)
        b_ = (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)
        if rlib.in_esc(*a) or rlib.in_esc(*b_):
            continue
        ly = bd.b.GetLayerName(t.GetLayer())
        ux, uy = (b_[0] - a[0]) / ll, (b_[1] - a[1]) / ll
        done = False
        for amp in (1.2, 0.9, 0.6, 0.4):
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
                    pt = (partner, 0.07 if ly in ('In2.Cu', 'In5.Cu') else 0.15) if partner else None
                    if proute.segs_clear(bd, ly, pts, w / 2, {net}, CLR, partner=pt):
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


groups = {}
for net, m in META.items():
    groups.setdefault(m['group'], []).append(net)
L = {n: flight(n) for n in META}
L = {n: v for n, v in L.items()}
missing = [n for n, v in L.items() if v is None]
if missing:
    print('no flight path for', missing)

# pair skew first (the strobes and clock are the references for everything else)
for pnet in ('DDR_DQS0', 'DDR_DQS1', 'DDR_CK'):
    lp, ln = L.get(pnet + '_P'), L.get(pnet + '_N')
    if lp and ln and abs(lp - ln) > 0.1:
        short, other = (pnet + '_P', pnet + '_N') if lp < ln else (pnet + '_N', pnet + '_P')
        lengthen(short, abs(lp - ln), partner=other)
        L[short] = flight(short)
ref_len = {}
for g, pnet in (('LANE0', 'DDR_DQS0'), ('LANE1', 'DDR_DQS1'), ('CMD', 'DDR_CK')):
    if L.get(pnet + '_P') is None or L.get(pnet + '_N') is None:
        print('reference', pnet, 'not routed; group', g, 'not tuned')
        continue
    ref_len[g] = (L[pnet + '_P'] + L[pnet + '_N']) / 2
    tol = TOL_LANE if g.startswith('LANE') else TOL_CMD
    for net in groups.get(g, []):
        d = ref_len[g] - L[net]
        if d > tol * 0.6:
            # aim for the middle of the window
            lengthen(net, d)

L = {n: flight(n) for n in META}
print('%-14s %8s %8s %8s  %s' % ('net', 'len mm', 'ref mm', 'delta', 'status'))
bad = []
for g, pnet in (('LANE0', 'DDR_DQS0'), ('LANE1', 'DDR_DQS1'), ('CMD', 'DDR_CK')):
    if L.get(pnet + '_P') is None or L.get(pnet + '_N') is None:
        continue
    ref = (L[pnet + '_P'] + L[pnet + '_N']) / 2
    tol = TOL_LANE if g.startswith('LANE') else TOL_CMD
    print('%-14s %8.2f  pair skew %.2f' % (pnet, ref, abs(L[pnet + '_P'] - L[pnet + '_N'])))
    for net in sorted(groups.get(g, []), key=lambda n: L[n]):
        dlt = L[net] - ref
        st = 'ok' if abs(dlt) <= tol else 'OUT'
        if st != 'ok':
            bad.append(net)
        print('%-14s %8.2f %8.2f %+8.2f  %s' % (net, L[net], ref, dlt, st))
ck = (L['DDR_CK_P'] + L['DDR_CK_N']) / 2 if L.get('DDR_CK_P') and L.get('DDR_CK_N') else 0
for k in (0, 1):
    if not (L.get('DDR_DQS%d_P' % k) and L.get('DDR_DQS%d_N' % k)):
        continue
    dq = (L['DDR_DQS%d_P' % k] + L['DDR_DQS%d_N' % k]) / 2
    print('CK - DQS%d = %+.2f mm (%s)' % (k, ck - dq, 'ok, ck longer' if ck >= dq else 'CK SHORTER'))
bd.save()
print('out of window:', bad)
