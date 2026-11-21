import math
import os
import sys
import time

import pcbnew

import negroute
import proute
import pslib
import rlib

# STM32 <-> FPGA bus router. every net that runs between U11 and U100 is laid on one layer end to end:
#   1. its old copper goes, except the dogbones (ball stub + via) under either chip
#   2. per net, a layer is chosen with a free escape channel out of both chips on it: a 45 degree step
#      from the dogbone via onto a ball line (two slots per line under the 1.0 mm fpga, one under the
#      0.8 mm stm32), then straight to just outside the package. the pair with the least total length
#      (escapes plus the corridor between the two exits) wins. hardest nets (deepest balls) go first
#   3. all corridor legs (exit to exit, pinned to the net's layer) are routed with negotiated congestion
# nets with more terminals than the two chips keep their bus link; the rest of their terminals are left for
# the general pass (bgaesc.py with NO_RIP=1). usage: busroute.py <board>
PCB = sys.argv[1]
LAYERS = ('In2.Cu', 'In7.Cu', 'In5.Cu', 'B.Cu')
PEN = {'In2.Cu': 0.0, 'In7.Cu': 0.0, 'In5.Cu': 0.3, 'B.Cu': 1.0}
W_ESC = 0.1
ESC = 3.0
t0 = time.time()


def router():
    rr = pslib.Router(PCB, ['U11', 'U100'])
    rr.clr = 0.127
    c = rr.bd.b.FindFootprintByReference('U11').GetCourtyard(pcbnew.F_CrtYd).BBox()
    rlib.BGA_RECTS.append((c.GetLeft() / 1e6 - ESC, c.GetTop() / 1e6 - ESC, c.GetRight() / 1e6 + ESC,
                           c.GetBottom() / 1e6 + ESC, 0.09))
    proute.ESC[:] = [q[:4] for q in rlib.BGA_RECTS]
    return rr


def status(path):
    rr = pslib.Router(path, [])
    zs = rr.bd.b.Zones()
    pl = {zs[i].GetNetname() for i in range(len(zs)) if not zs[i].GetIsRuleArea()} | {'GND'}
    T = {}
    for (x, y, hx, hy, n, lays, rnd, p) in rr.bd.pads:
        if n and n not in pl and not n.startswith('unconnected'):
            T.setdefault(n, []).append((p.GetParentFootprint().GetReference() + ':' + p.GetNumber(), (x, y), lays, (hx, hy)))
    return {n: len(set(rr.comp(n, ts))) == 1 for n, ts in T.items() if len(ts) > 1}


before = status(PCB)
r = router()
b = r.bd.b
zs = b.Zones()
planes = {zs[i].GetNetname() for i in range(len(zs)) if not zs[i].GetIsRuleArea()} | {'GND'}


def balls(ref):
    f = b.FindFootprintByReference(ref)
    return [(f.Pads()[k].GetNetname(), f.Pads()[k].GetPosition().x / 1e6, f.Pads()[k].GetPosition().y / 1e6)
            for k in range(len(f.Pads()))]


BS, BF = balls('U11'), balls('U100')
fnets = {n for n, x, y in BF}
bus = sorted({n for n, x, y in BS if n and n not in planes and n in fnets})
stm_sig = sorted({n for n, x, y in BS if n and n not in planes and not n.startswith('unconnected')})
ripnets = set(stm_sig) if os.environ.get('RIP_ALL') else set(bus)
print('bus nets: %d' % len(bus), flush=True)

# 1) rip everything of the bus nets except the dogbones at both chips
ballxy = {}
for n, x, y in BS + BF:
    if n in ripnets:
        ballxy.setdefault(n, []).append((x, y))
ts = b.Tracks()
items = [ts[i] for i in range(len(ts))]
dog_vias = set()
for it in items:
    n = it.GetNetname()
    if n in ripnets and it.GetClass() == 'PCB_VIA':
        v = (it.GetPosition().x / 1e6, it.GetPosition().y / 1e6)
        if any(math.hypot(v[0] - x, v[1] - y) < 0.95 for x, y in ballxy.get(n, [])):
            dog_vias.add((n, round(v[0], 3), round(v[1], 3)))
kill = []
for it in items:
    n = it.GetNetname()
    if n not in ripnets:
        continue
    if it.GetClass() == 'PCB_VIA':
        if (n, round(it.GetPosition().x / 1e6, 3), round(it.GetPosition().y / 1e6, 3)) not in dog_vias:
            kill.append(it)
        continue
    a = (it.GetStart().x / 1e6, it.GetStart().y / 1e6)
    z = (it.GetEnd().x / 1e6, it.GetEnd().y / 1e6)
    on_ball = lambda p: any(math.hypot(p[0] - x, p[1] - y) < 0.02 for x, y in ballxy.get(n, []))
    on_dog = lambda p: (n, round(p[0], 3), round(p[1], 3)) in dog_vias
    if not (it.GetLayer() == pcbnew.F_Cu and ((on_ball(a) and on_dog(z)) or (on_ball(z) and on_dog(a)))):
        kill.append(it)
for it in kill:
    b.Remove(it)
graveyard = kill
r.bd.save()
print('ripped %d items of the bus nets (dogbones kept: %d vias)' % (len(kill), len(dog_vias)), flush=True)
r = router()
bd = r.bd


# 2) escapes
class Chip:
    def __init__(self, ref, pitch, slots, ext):
        bl = balls(ref)
        xs, ys = [q[1] for q in bl], [q[2] for q in bl]
        self.X0, self.Y0, self.XN, self.YN = min(xs), min(ys), max(xs), max(ys)
        self.P, self.slots, self.ext, self.ref = pitch, slots, ext, ref
        self.balls = bl

    def inside(self, x, y):
        return self.X0 - 0.01 < x < self.XN + 0.01 and self.Y0 - 0.01 < y < self.YN + 0.01

    def depth(self, x, y):
        return max(0.0, min(x - self.X0, self.XN - x, y - self.Y0, self.YN - y))

    def bparam(self, side, p):
        # position of an exit along the package boundary facing the corridor: stm32 walked anticlockwise
        # from its north-east corner (north, west, south); fpga clockwise from its north-east corner (east,
        # south). two links on one layer cross unless both chips see them in the same order
        x, y = p
        if self.ref == 'U11':
            if side == 'N':
                return self.Y0 - (x - self.X0)
            if side == 'S':
                return self.YN + (x - self.X0)
            return y
        if side == 'S':
            return self.YN + (self.XN - x)
        return y

    def side_of(self, p):
        x, y = p
        d = {'W': abs(x - self.X0), 'E': abs(x - self.XN), 'N': abs(y - self.Y0), 'S': abs(y - self.YN)}
        return min(d, key=d.get)

    def cands(self, v):
        # (side, path) on any layer; a dogbone outside the ball field needs no escape
        vx, vy = v
        if not self.inside(vx, vy):
            return [(self.side_of(v), [v])]
        P = self.P
        out = []
        j0 = math.floor((vy - self.Y0) / P)
        i0 = math.floor((vx - self.X0) / P)
        for j in (j0, j0 + 1):
            for s in self.slots:
                y = self.Y0 + j * P + s
                d = abs(y - vy)
                out.append(('W', [v, (vx - d, y), (self.X0 - self.ext, y)]))
                out.append(('E', [v, (vx + d, y), (self.XN + self.ext, y)]))
        for i in (i0, i0 + 1):
            for s in self.slots:
                x = self.X0 + i * P + s
                d = abs(x - vx)
                out.append(('N', [v, (x, vy - d), (x, self.Y0 - self.ext)]))
                out.append(('S', [v, (x, vy + d), (x, self.YN + self.ext)]))
        return out


S = Chip('U11', 0.8, (0.0,), 1.2)
F = Chip('U100', 1.0, (0.0, -0.11, 0.11), 1.5)


def free(n, ly, path):
    for (xa, ya), (xb, yb) in zip(path, path[1:]):
        win = (min(xa, xb) - 0.05, min(ya, yb) - 0.05, max(xa, xb) + 0.05, max(ya, yb) + 0.05)
        bl, gx, gy = bd.grid(ly, win, W_ESC / 2, {n}, 0.09, half_in=W_ESC / 2, pours=True)
        k = max(1, int(math.hypot(xb - xa, yb - ya) / 0.02))
        for q in range(k + 1):
            px, py = xa + (xb - xa) * q / k, ya + (yb - ya) * q / k
            jj = min(bl.shape[0] - 1, max(0, int(round((py - gy[0]) / rlib.G))))
            ii = min(bl.shape[1] - 1, max(0, int(round((px - gx[0]) / rlib.G))))
            if bl[jj, ii]:
                return False
    return True


plen = lambda p: sum(math.hypot(q[0] - o[0], q[1] - o[1]) for o, q in zip(p, p[1:]))
vias = {}
for (vx, vy, vr, vn) in bd.vias:
    vias.setdefault(vn, []).append((vx, vy))


def dog(n, chip):
    for (bn, x, y) in chip.balls:
        if bn != n:
            continue
        for v in vias.get(n, []):
            if math.hypot(v[0] - x, v[1] - y) < 0.95:
                return v
    return None


def stm32_outer(n):
    # an stm32 outer-ring ball has no dogbone: a via just outside the package, straight out on F.Cu
    for (bn, x, y) in S.balls:
        if bn != n:
            continue
        ox, oy = x - (S.X0 + S.XN) / 2, y - (S.Y0 + S.YN) / 2
        d = (1 if ox > 0 else -1, 0) if abs(ox) >= abs(oy) else (0, 1 if oy > 0 else -1)
        odd = (round((x - S.X0) / 0.8) + round((y - S.Y0) / 0.8)) % 2
        for k in ((1.8, 2.6, 1.0, 1.4, 2.2) if odd else (1.0, 1.4, 1.8, 2.2, 2.6)):
            ax, ay = x + d[0] * k, y + d[1] * k
            if proute.via_spot_ok(bd, ax, ay, n, r=0.2, clr=0.1):
                p2 = bd.path('F.Cu', (x, y), (ax, ay), 0.05, {n}, 0.09, margin=1.0, half_in=0.05)
                if p2:
                    st = []
                    r.stage(p2, n, 0.1, 'F.Cu', st)
                    bd.stage_via(ax, ay, n, st, d=0.4)
                    bd.commit(st)
                    return (ax, ay)
    return None


def fpga_outer(n):
    # an fpga ball in the outer two rows without a dogbone: F.Cu out past the package edge, then a via
    cx, cy = (F.X0 + F.XN) / 2, (F.Y0 + F.YN) / 2
    for (bn, x, y) in F.balls:
        if bn != n or F.depth(x, y) > 1.01:
            continue
        ox, oy = x - cx, y - cy
        d = (1 if ox > 0 else -1, 0) if abs(ox) >= abs(oy) else (0, 1 if oy > 0 else -1)
        edge = (F.XN if d[0] > 0 else F.X0) if d[0] else (F.YN if d[1] > 0 else F.Y0)
        odd = (round(x - F.X0) + round(y - F.Y0)) % 2
        for k in ((2.3, 1.5, 3.1, 1.9, 2.7) if odd else (1.5, 2.3, 1.9, 2.7, 3.1)):
            for sh in (0.0, 0.25, -0.25):
                ax = edge + d[0] * k if d[0] else x + sh
                ay = edge + d[1] * k if d[1] else y + sh
                if proute.via_spot_ok(bd, ax, ay, n, r=0.2, clr=0.1):
                    p2 = bd.path('F.Cu', (x, y), (ax, ay), 0.05, {n}, 0.09, margin=1.5, half_in=0.05)
                    if p2:
                        st = []
                        r.stage(p2, n, 0.1, 'F.Cu', st)
                        bd.stage_via(ax, ay, n, st, d=0.4)
                        bd.commit(st)
                        return (ax, ay)
    return None


jobs = []
missing = []
for n in bus:
    vs = dog(n, S) or stm32_outer(n)
    vf = dog(n, F) or fpga_outer(n)
    if not vs or not vf:
        missing.append('%s(%s)' % (n, ('S' if not vs else '') + ('F' if not vf else '')))
        continue
    jobs.append((n, vs, vf))
jobs.sort(key=lambda j: -(S.depth(*j[1]) + F.depth(*j[2])))
plan, nofit = {}, []
lanes = {ly: [] for ly in LAYERS}     # (stm32 boundary position, fpga boundary position) per planned link
S_SIDES, F_SIDES = ('W', 'N', 'S'), ('E', 'S')


def crosses(p, q, r_, s):
    o = lambda a, b, c: (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return o(p, q, r_) * o(p, q, s) < 0 and o(r_, s, p) * o(r_, s, q) < 0
for n, vs, vf in jobs:
    cs, cf = S.cands(vs), F.cands(vf)
    best = None
    for ly in LAYERS:
        fs = [(side, p) for side, p in cs if side in S_SIDES and free(n, ly, p)]
        ff = [(side, p) for side, p in cf if side in F_SIDES and free(n, ly, p)]
        for sa, pa in fs:
            for sb, pb in ff:
                ea, eb = pa[-1], pb[-1]
                c = plen(pa) + plen(pb) + abs(ea[0] - eb[0]) + abs(ea[1] - eb[1]) + 3 * PEN[ly]
                # a lane crossing another lane on the same layer cannot be routed: heavy penalty
                ps, pf = S.bparam(sa, ea), F.bparam(sb, eb)
                c += 200 * sum(1 for (u, w) in lanes[ly] if (ps - u) * (pf - w) < 0)
                if best is None or c < best[0]:
                    best = (c, ly, pa, pb, sa, sb)
    if not best:
        # which end had no free escape on any layer
        sok = any(free(n, ly, p) for ly in LAYERS for side, p in cs)
        fok = any(free(n, ly, p) for ly in LAYERS for side, p in cf)
        nofit.append('%s(%s)' % (n, ('S' if not sok else '') + ('F' if not fok else '') or 'layers'))
        continue
    _, ly, pa, pb, _, _ = best
    st = []
    for p in (pa, pb):
        if len(p) > 1:
            bd.stage_track(p, W_ESC, n, ly, st)
    bd.commit(st)
    plan[n] = (ly, pa[-1], pb[-1])
    lanes[ly].append((S.bparam(best[4], pa[-1]), F.bparam(best[5], pb[-1])))
bd.save()
print('escaped both ends on one layer: %d (%s); no common layer: %d %s; no dogbone: %s (%.0fs)' % (
    len(plan), ', '.join('%s %d' % (l, sum(1 for v in plan.values() if v[0] == l)) for l in LAYERS),
    len(nofit), ' '.join(nofit[:20]), ' '.join(missing) or 'none', time.time() - t0), flush=True)

# 3) corridor legs
legs = [{'net': n, 'a': a, 'b': z, 'ly': ly} for n, (ly, a, z) in plan.items()]
if legs:
    ax = [l['a'][0] for l in legs] + [l['b'][0] for l in legs]
    ay = [l['a'][1] for l in legs] + [l['b'][1] for l in legs]
    win = (max(50.5, min(ax) - 6), max(53.6, min(ay) - 6), min(190.6, max(ax) + 6), min(146.9, max(ay) + 6))
    negroute.negotiate(bd, legs, win, {ly: 0.127 for ly in LAYERS}, {ly: 1.0 for ly in LAYERS},
                       iters=int(os.environ.get('NEG_ITERS', '30')), log=lambda s: print(s, flush=True))
bd.save()
after = status(PCB)
lost = [n for n in before if before[n] and not after.get(n, False)]
gain = [n for n in before if not before[n] and after.get(n, False)]
linked = sum(1 for n in bus if len(set(r.comp(n, [t for t in r.terms(n) if t[0].startswith(('U11:', 'U100:'))]))) == 1)
print('bus links joined: %d of %d' % (linked, len(bus)))
print('complete nets: %d -> %d (gained %d, lost %d) in %.0f s' % (sum(before.values()), sum(after.values()),
                                                                    len(gain), len(lost), time.time() - t0))
if lost:
    print('LOST: %s' % ' '.join(lost))
