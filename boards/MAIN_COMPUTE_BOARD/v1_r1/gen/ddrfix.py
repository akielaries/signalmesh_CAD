import heapq
import json
import math
import os
import shutil
import sys

import negroute3d
import proute
import pslib
import rlib

# ddr length fixes by re-routing: for every net outside its matching window (dq/dm to their dqs, addr/cmd to
# ck), the fpga-to-dram part of its route is replaced (dogbones and the fly-by tail to the terminator stay).
# too long: re-routed on the tightest window that still routes. too short: routed through a detour point
# placed to add the missing length. a net is kept only if it ends closer to its window and stays connected;
# otherwise the board is restored. usage: ddrfix.py <board>
PCB = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
META = json.load(open(os.path.join(HERE, 'ddr_routes.json')))
TOL = {'LANE0': 1.4, 'LANE1': 1.4, 'CMD': 3.0}
REF = {'LANE0': 'DDR_DQS0', 'LANE1': 'DDR_DQS1', 'CMD': 'DDR_CK'}
LAYERS = ('In5.Cu', 'In2.Cu', 'In7.Cu', 'B.Cu', 'F.Cu')
CLR, W = 0.15, 0.127
LOG = open(PCB + '.ddrfix.log', 'a')
GRAVE = []     # removed swig items stay referenced (collecting them corrupts pcbnew's type table)
BOARDS = []


def say(s):
    print(s, flush=True)
    LOG.write(s + '\n')
    LOG.flush()


def load():
    r = pslib.Router(PCB, ['U100', 'U21'])
    BOARDS.append(r)
    r.clr = CLR
    return r


def ball(bd, net, ref):
    for (x, y, hx, hy, n, l, rr, p) in bd.pads:
        if n == net and p.GetParentFootprint().GetReference() == ref:
            return (x, y)


def dram_ref(bd):
    for (x, y, hx, hy, n, l, rr, p) in bd.pads:
        if p.GetParentFootprint().GetValue().startswith('MT41K'):
            return p.GetParentFootprint().GetReference()


def flight(bd, net, dr):
    # shortest copper path fpga ball -> dram ball (xy graph, vias join layers); returns (length, edges)
    key = lambda x, y: (round(x, 3), round(y, 3))
    g = {}
    for t in bd.tracks:
        if t[5] != net:
            continue
        a, b_ = key(t[0], t[1]), key(t[2], t[3])
        ln = math.hypot(t[2] - t[0], t[3] - t[1])
        g.setdefault(a, []).append((b_, ln, t))
        g.setdefault(b_, []).append((a, ln, t))
    pa, pb = ball(bd, net, 'U100'), ball(bd, net, dr)
    if not pa or not pb:
        return None, []
    s, e = key(*pa), key(*pb)
    if s not in g or e not in g:
        return None, []
    dist, prev = {s: 0.0}, {}
    q = [(0.0, s)]
    while q:
        d, u = heapq.heappop(q)
        if u == e:
            path = []
            while u != s:
                pu, t = prev[u]
                path.append(t)
                u = pu
            return d, path
        if d > dist.get(u, 1e9):
            continue
        for v, w, t in g.get(u, []):
            if d + w < dist.get(v, 1e9):
                dist[v] = d + w
                prev[v] = (u, t)
                heapq.heappush(q, (d + w, v))
    return None, []


def lengths(r, dr):
    return {n: flight(r.bd, n, dr)[0] for n in META}


def windows(L):
    out = {}
    for n, m in META.items():
        g = m['group']
        if g not in REF or L.get(n) is None:
            continue
        lp, ln = L.get(REF[g] + '_P'), L.get(REF[g] + '_N')
        if lp is None or ln is None:
            continue
        out[n] = (L[n] - (lp + ln) / 2, TOL[g])
    return out


def replace(n, mode, need, only=None):
    # rip the flight part of n and route it again; returns True if a route was committed
    r = load()
    bd = r.bd
    dr = dram_ref(bd)
    L0, path = flight(bd, n, dr)
    pa, pb = ball(bd, n, 'U100'), ball(bd, n, dr)
    near = lambda p, q: math.hypot(p[0] - q[0], p[1] - q[1]) < 0.95
    keep_seg = lambda t: near((t[0], t[1]), pa) and near((t[2], t[3]), pa) or near((t[0], t[1]), pb) and near((t[2], t[3]), pb)
    gone = [t for t in path if not keep_seg(t)]
    if not gone:
        return False
    # the new leg runs between the dogbone ends of the removed part
    ends = {}
    for t in gone:
        for p in ((t[0], t[1]), (t[2], t[3])):
            k = (round(p[0], 3), round(p[1], 3))
            ends[k] = ends.get(k, 0) + 1
    tips = [k for k, c in ends.items() if c == 1]
    if len(tips) != 2:
        return False
    a, z = sorted(tips, key=lambda p: math.hypot(p[0] - pa[0], p[1] - pa[1]))
    b = bd.b
    ts = b.Tracks()
    gk = {(round(t[0], 3), round(t[1], 3), round(t[2], 3), round(t[3], 3), t[6]) for t in gone}
    kill = []
    for i in range(len(ts)):
        t = ts[i]
        if t.GetNetname() != n or t.GetClass() == 'PCB_VIA':
            continue
        k = (round(t.GetStart().x / 1e6, 3), round(t.GetStart().y / 1e6, 3), round(t.GetEnd().x / 1e6, 3), round(t.GetEnd().y / 1e6, 3), b.GetLayerName(t.GetLayer()))
        if k in gk:
            kill.append(t)
    # vias along the removed part that nothing else uses any more
    inner = {k for k, c in ends.items() if c >= 2}
    for i in range(len(ts)):
        t = ts[i]
        if t.GetNetname() == n and t.GetClass() == 'PCB_VIA':
            k = (round(t.GetPosition().x / 1e6, 3), round(t.GetPosition().y / 1e6, 3))
            if k in inner:
                kill.append(t)
    for t in kill:
        b.Remove(t)
    GRAVE.extend(kill)
    bd.save()
    r = load()
    bd = r.bd
    viaat = lambda p: any(math.hypot(v[0] - p[0], v[1] - p[1]) < 0.02 for v in bd.vias if v[3] == n)
    lay_of = lambda p: next((t[6] for t in bd.tracks if t[5] == n and (math.hypot(t[0] - p[0], t[1] - p[1]) < 0.02 or math.hypot(t[2] - p[0], t[3] - p[1]) < 0.02)), 'F.Cu')
    win = (min(a[0], z[0]) - 12, min(a[1], z[1]) - 12, max(a[0], z[0]) + 12, max(a[1], z[1]) + 12)
    legs = []
    if mode == 'short':
        D = math.hypot(z[0] - a[0], z[1] - a[1])
        h = math.sqrt(max(0.0, ((D + need) / 2) ** 2 - (D / 2) ** 2))
        ux, uy = (z[0] - a[0]) / D, (z[1] - a[1]) / D
        for side in (1, -1):
            for scale in (only,) if only else (1.0,):
                wpt = ((a[0] + z[0]) / 2 - uy * h * side * scale, (a[1] + z[1]) / 2 + ux * h * side * scale)
                for ly in ('In5.Cu', 'In2.Cu', 'In7.Cu'):
                    legs.append([{'net': n, 'a': a, 'b': wpt, 'lb': ly}, {'net': n, 'a': wpt, 'b': z, 'la': ly}])
    else:
        legs = [[{'net': n, 'a': a, 'b': z}]]
    margins = (1.0, 2.0, 3.0, 5.0) if mode == 'long' else (4.0,)
    for cand in legs:
        for m in margins:
            for l in cand:
                for k_, p in (('a', l['a']), ('b', l['b'])):
                    pin = 'la' if k_ == 'a' else 'lb'
                    if pin not in l and p in (a, z) and not viaat(p):
                        l[pin] = lay_of(p)
            left = negroute3d.negotiate3d(bd, [dict(l) for l in cand], win, {ly: W for ly in LAYERS}, {ly: 1.0 for ly in LAYERS},
                                          via_cost=3.0, iters=12, clr=CLR, margin=m, log=lambda s: None)
            if not left:
                bd.save()
                return True
            # a partial commit must not stay: reload from disk (nothing saved yet)
            r = load()
            bd = r.bd
    return False


r = load()
dr = dram_ref(r.bd)
L = lengths(r, dr)
wn = windows(L)
bad = sorted(((abs(d) - t, n, d, t) for n, (d, t) in wn.items() if abs(d) > t and not n.startswith(('DDR_DQS', 'DDR_CK'))), reverse=True)
say('ddr nets out of window: %d: %s' % (len(bad), ' '.join('%s(%+.1f)' % (n, d) for _, n, d, t in bad)))
fixed = 0
def attempt(n, d, t, scale=None):
    ok = replace(n, 'long' if d > 0 else 'short', -d, only=scale)
    r = load()
    L2 = lengths(r, dr)
    return ok, r, L2, windows(L2).get(n, (None, t))[0]


for _, n, d, t in bad:
    snap = PCB + '.ddrfix.snap'
    shutil.copy(PCB, snap)
    if d > 0:
        ok, r, L2, d2 = attempt(n, d, t)
    else:
        # short: several detour sizes, each from the snapshot; the one landing nearest the window wins
        best = None
        for scale in (0.25, 0.4, 0.55, 0.7, 0.85, 1.0):
            shutil.copy(snap, PCB)
            ok, r, L2, d2 = attempt(n, d, t, scale)
            if ok and d2 is not None and len(set(r.comp(n, r.terms(n)))) == 1 and (best is None or abs(d2) < abs(best[0])):
                best = (d2, scale)
                shutil.copy(PCB, PCB + '.ddrfix.best')
            if best and abs(best[0]) <= t * 0.6:
                break
        if best:
            shutil.copy(PCB + '.ddrfix.best', PCB)
            ok, r, L2, d2 = True, load(), None, None
            L2 = lengths(r, dr)
            d2 = windows(L2).get(n, (None, t))[0]
        else:
            ok, d2 = False, None
    connected = len(set(r.comp(n, r.terms(n)))) == 1
    others_ok = all(abs(windows(L2).get(m, (0, 99))[0]) <= abs(wn[m][0]) + 0.05 or abs(windows(L2).get(m, (0, 99))[0]) <= wn[m][1]
                    for m in wn if m != n)
    if ok and d2 is not None and connected and others_ok and abs(d2) < abs(d) - 0.3:
        fixed += 1
        wn = windows(L2)
        say('%-12s %+.2f -> %+.2f mm (window +-%.1f) kept' % (n, d, d2, t))
    else:
        shutil.copy(snap, PCB)
        say('%-12s %+.2f -> %s, restored' % (n, d, ('%+.2f' % d2) if d2 is not None else 'open'))
say('ddrfix: %d of %d improved' % (fixed, len(bad)))
