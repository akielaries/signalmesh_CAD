import math
import os
import sys
import time

import numpy as np
from scipy.optimize import linear_sum_assignment

import negroute
import proute
import pslib
import rlib

# STM32 TFBGA265 fanout and routing.
#   fan:   dogbone vias for the balls. outer-ring signal balls escape on F.Cu and get no via; every other
#          ball with a net gets a via at the centre of one of its four neighbouring 2x2 cells (0.4/0.2 mm,
#          0.1 mm stub), assigned all at once so no two balls share a cell, preferring the cell that
#          points away from the package centre. plane balls reach their planes through these vias.
#   route: every open STM32 signal net is joined (ball via, far pads, cut ends left by the swap) with
#          negotiated congestion on all five signal layers, then a plain completion pass.
# usage: bgafan.py <board> fan|route
PCB, STEP = sys.argv[1], sys.argv[2]
PITCH = 0.8
VIA_D = 0.4
LAYERS = ('In2.Cu', 'In7.Cu', 'In5.Cu', 'B.Cu', 'F.Cu')
COST = {'In2.Cu': 1.0, 'In7.Cu': 1.0, 'In5.Cu': 1.05, 'B.Cu': 1.15, 'F.Cu': 1.2}


def planes_of(bd):
    zs = bd.b.Zones()
    return {zs[i].GetNetname() for i in range(len(zs))} | {'GND'}


def balls(bd):
    u = bd.b.FindFootprintByReference('U11')
    out = []
    for k in range(len(u.Pads())):
        p = u.Pads()[k]
        out.append((p.GetNumber(), p.GetNetname(), p.GetPosition().x / 1e6, p.GetPosition().y / 1e6))
    return out


def status(path):
    r = pslib.Router(path, [])
    planes = planes_of(r.bd)
    T = {}
    for (x, y, hx, hy, n, lays, rnd, p) in r.bd.pads:
        if n and n not in planes and not n.startswith('unconnected'):
            T.setdefault(n, []).append((p.GetParentFootprint().GetReference() + ':' + p.GetNumber(), (x, y), lays, (hx, hy)))
    return {n: len(set(r.comp(n, ts))) == 1 for n, ts in T.items() if len(ts) > 1}


ESC = 3.0   # neck-down zone reaches this far past the stm32 courtyard (matches the STM32_ESC rule area)


def router():
    import pcbnew
    rr = pslib.Router(PCB, ['U11', 'U100'])
    rr.clr = 0.127
    c = rr.bd.b.FindFootprintByReference('U11').GetCourtyard(pcbnew.F_CrtYd).BBox()
    rlib.BGA_RECTS.append((c.GetLeft() / 1e6 - ESC, c.GetTop() / 1e6 - ESC, c.GetRight() / 1e6 + ESC,
                           c.GetBottom() / 1e6 + ESC, 0.09))
    proute.ESC[:] = [q[:4] for q in rlib.BGA_RECTS]
    return rr


r = router()
bd = r.bd
planes = planes_of(bd)
B = balls(bd)
xs, ys = [q[2] for q in B], [q[3] for q in B]
cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
X0, Y0 = min(xs), min(ys)
NI = int(round((max(xs) - X0) / PITCH))
gi = lambda x: int(round((x - X0) / PITCH))
gj = lambda y: int(round((y - Y0) / PITCH))
depth = lambda x, y: min(gi(x), NI - gi(x), gj(y), NI - gj(y))
live = lambda n: n and not n.startswith('unconnected')



def spot(x, y, n):
    # exact spot test (proute.via_spot_ok tests a 0.2 mm box round the point, too coarse for 0.8 mm pitch)
    for ly in rlib.LAYERS:
        bl, _, _ = bd.grid(ly, (x - 0.01, y - 0.01, x + 0.01, y + 0.01), VIA_D / 2, {n}, 0.09, pours=False)
        if bl.any():
            return False
    return all(math.hypot(vx - x, vy - y) >= 0.75 for (vx, vy, vr, vn) in bd.vias)


if STEP == 'fan':
    need = [q for q in B if live(q[1]) and (q[1] in planes or depth(q[2], q[3]) > 0 or q[1].startswith('/STM32/VCAP'))]
    # candidate cells: index (ci, cj) is the cell whose centre is at X0 + (ci + 0.5) * PITCH
    cells = sorted({(gi(x) + dx, gj(y) + dy) for (_, _, x, y) in need for dx in (-1, 0) for dy in (-1, 0)})
    cid = {c: k for k, c in enumerate(cells)}
    cost = np.full((len(need), len(cells)), 1e6)
    for a, (num, n, x, y) in enumerate(need):
        ox, oy = x - cx, y - cy
        for dx in (-1, 0):
            for dy in (-1, 0):
                c = (gi(x) + dx, gj(y) + dy)
                vx, vy = X0 + (c[0] + 0.5) * PITCH, Y0 + (c[1] + 0.5) * PITCH
                # outward is cheap; the dot product of the stub with the direction from the centre
                L = math.hypot(ox, oy) or 1.0
                cost[a, cid[c]] = 1.0 - ((vx - x) * ox + (vy - y) * oy) / (L * 0.566)
    ra, ca = linear_sum_assignment(cost)
    st, nvia, nfail = [], 0, []
    for a, k in zip(ra, ca):
        num, n, x, y = need[a]
        if cost[a, k] >= 1e6:
            nfail.append(num)
            continue
        c = cells[k]
        vx, vy = X0 + (c[0] + 0.5) * PITCH, Y0 + (c[1] + 0.5) * PITCH
        if not spot(vx, vy, n):
            nfail.append(num)
            continue
        s = []
        bd.stage_track([(x, y), (vx, vy)], 0.1, n, 'F.Cu', s)
        bd.stage_via(vx, vy, n, s, d=VIA_D)
        bd.commit(s)
        nvia += 1
    bd.save()
    print('balls with a net: %d; vias %d; outer-ring signal balls escaping on F.Cu: %d; no cell: %s'
          % (sum(1 for q in B if live(q[1])), nvia,
             sum(1 for q in B if live(q[1]) and q[1] not in planes and depth(q[2], q[3]) == 0 and not q[1].startswith('/STM32/VCAP')),
             nfail or 'none'))
    sys.exit(0)

# ---- route
before = status(PCB)
if os.environ.get('RIP_OPEN'):
    # partial copper of the open STM32 nets goes (its cut ends sit where the old lqfp pins were); the
    # fanout under the STM32 and the fpga stays: tracks/vias inside either courtyard are kept
    import pcbnew
    boxes = []
    for ref in ('U11', 'U100'):
        c = bd.b.FindFootprintByReference(ref).GetCourtyard(pcbnew.F_CrtYd).BBox()
        boxes.append((c.GetLeft() / 1e6, c.GetTop() / 1e6, c.GetRight() / 1e6, c.GetBottom() / 1e6))
    inb = lambda x, y: any(q[0] <= x <= q[2] and q[1] <= y <= q[3] for q in boxes)
    opn = {q[1] for q in B if live(q[1]) and q[1] not in planes and q[1] in before and not before[q[1]]}
    ts = bd.b.Tracks()
    kill = []
    for i in range(len(ts)):
        it = ts[i]
        if it.GetNetname() not in opn:
            continue
        pts = ([it.GetPosition()] if it.GetClass() == 'PCB_VIA' else [it.GetStart(), it.GetEnd()])
        if not all(inb(p.x / 1e6, p.y / 1e6) for p in pts):
            kill.append(it)
    for it in kill:
        bd.b.Remove(it)
    graveyard = kill
    bd.save()
    print('ripped %d partial-route items of %d open nets' % (len(kill), len(opn)), flush=True)
    r = router()
    bd = r.bd
T = r.terms
targets = sorted({q[1] for q in B if live(q[1]) and q[1] not in planes and q[1] in before and not before[q[1]]})
print('open STM32 signal nets: %d' % len(targets), flush=True)
viapos = {}
for (vx, vy, vr, vn) in bd.vias:
    viapos.setdefault(vn, []).append((vx, vy))
ballpos = {}
for (num, n, x, y) in B:
    ballpos.setdefault(n, []).append((x, y))


def ball_via(n):
    # the dogbone via of n's ball (within a cell diagonal of the ball)
    for (bx, by) in ballpos.get(n, []):
        for (vx, vy) in viapos.get(n, []):
            if abs(math.hypot(vx - bx, vy - by) - 0.566) < 0.02:
                return (vx, vy)
    return None


def cut_points(n):
    ends = {}
    segs = [(xa, ya, xb, yb, hw, ly) for (xa, ya, xb, yb, hw, nn, ly) in bd.tracks if nn == n]
    for (xa, ya, xb, yb, hw, ly) in segs:
        for q in ((xa, ya), (xb, yb)):
            k = (round(q[0], 3), round(q[1], 3), ly)
            ends[k] = ends.get(k, []) + [hw * 2]
    vs = viapos.get(n, [])
    pads = [(x, y, hx, hy) for (x, y, hx, hy, nn, lays, rnd, p) in bd.pads if nn == n]
    out = []
    for (x, y, ly), ws in ends.items():
        if len(ws) > 1 or any(math.hypot(x - vx, y - vy) < 0.05 for vx, vy in vs):
            continue
        if any(abs(x - px) <= hx + 0.02 and abs(y - py) <= hy + 0.02 for px, py, hx, hy in pads):
            continue
        if any(ly == l2 and abs(x - xa) + abs(y - ya) > 0.01 and abs(x - xb) + abs(y - yb) > 0.01 and
               abs((x - xa) * (yb - ya) - (y - ya) * (xb - xa)) / max(1e-9, math.hypot(xb - xa, yb - ya)) < 0.01 and
               min(xa, xb) - 0.01 <= x <= max(xa, xb) + 0.01 and min(ya, yb) - 0.01 <= y <= max(ya, yb) + 0.01
               for (xa, ya, xb, yb, hw, l2) in segs):
            continue
        out.append(('CUT@%.2f,%.2f' % (x, y), (x, y), {ly}, (0.06, 0.06)))
    return out


_u = bd.b.FindFootprintByReference('U100')
fpga_c = (_u.GetPosition().x / 1e6, _u.GetPosition().y / 1e6)


def endpoint_via(n, term):
    name, p, lays = term[0], term[1], term[2]
    if name.startswith('VIA') or set(rlib.LAYERS) <= set(lays):
        return p
    st = []
    if name.startswith('CUT'):
        ly = list(lays)[0]
        if proute.via_spot_ok(bd, p[0], p[1], n, r=VIA_D / 2, clr=0.127):
            bd.stage_via(p[0], p[1], n, st, d=VIA_D)
            bd.commit(st)
            return p
        for rad in (0.4, 0.6, 0.8, 1.1, 1.4):
            for kk in range(8):
                ax, ay = p[0] + rad * math.cos(kk * math.pi / 4), p[1] + rad * math.sin(kk * math.pi / 4)
                if proute.via_spot_ok(bd, ax, ay, n, r=VIA_D / 2, clr=0.127):
                    p2 = bd.path(ly, (ax, ay), p, 0.05, {n}, 0.1, margin=1.5, half_in=0.05)
                    if p2:
                        r.stage(p2, n, 0.127, ly, st)
                        bd.stage_via(ax, ay, n, st, d=VIA_D)
                        bd.commit(st)
                        return (ax, ay)
        return None
    # an outer-ring ball of either bga: via just outside its ball, straight out from the package centre
    if name.startswith(('U11:', 'U100:')):
        fc = fpga_c if name.startswith('U100:') else (cx, cy)
        ox, oy = p[0] - fc[0], p[1] - fc[1]
        d = (1 if ox > 0 else -1, 0) if abs(ox) >= abs(oy) else (0, 1 if oy > 0 else -1)
        # stm32 outer ring: alternate balls start at 1.0 and 1.8 mm out, so the vias do not form a fence
        odd = (gi(p[0]) + gj(p[1])) % 2
        ks = ((1.8, 2.6, 1.0, 1.4, 2.2) if odd else (1.0, 1.4, 1.8, 2.2, 2.6)) if name.startswith('U11:') else (0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
        for k in ks:
            for sh in ((0.0, 0.4, -0.4) if name.startswith('U11:') else (0.5, -0.5, 0.0)):
                ax = p[0] + d[0] * k + (sh if d[0] == 0 else 0)
                ay = p[1] + d[1] * k + (sh if d[1] == 0 else 0)
                if proute.via_spot_ok(bd, ax, ay, n, r=VIA_D / 2, clr=0.127):
                    p2 = bd.path('F.Cu', p, (ax, ay), 0.05, {n}, 0.1, margin=1.0, half_in=0.05)
                    if p2:
                        r.stage(p2, n, 0.1, 'F.Cu', st)
                        bd.stage_via(ax, ay, n, st, d=VIA_D)
                        bd.commit(st)
                        return (ax, ay)
        return None
    v = proute.drop_via(bd, p, n, (cx, cy), st, w=0.15, radii=(0.5, 0.65, 0.8, 1.0, 1.3, 1.6), layer=r.side(lays))
    if v:
        bd.commit(st)
        return v
    bd.unstage(st)
    return None


def mst(tt):
    used, edges = {0}, []
    while len(used) < len(tt):
        best = min(((math.hypot(tt[i][1][0] - tt[j][1][0], tt[i][1][1] - tt[j][1][1]), i, j)
                    for i in used for j in range(len(tt)) if j not in used))
        edges.append(best[1:])
        used.add(best[2])
    return edges


t0 = time.time()
legs, nolink = [], []
for n in targets:
    tt = [q for q in T(n)]
    bv = ball_via(n)
    if bv:
        tt = [q for q in tt if not q[0].startswith('U11:')] + [r.via_term(bv)]
    tt += cut_points(n)
    if len(tt) < 2 or len(set(r.comp(n, [q[:4] for q in tt]))) == 1:
        continue
    ends = []
    for q in tt:
        # a via already joined to this terminal (left by an earlier pass) is reused
        v = None
        if not q[0].startswith('VIA'):
            for (vx, vy) in viapos.get(n, []):
                if math.hypot(vx - q[1][0], vy - q[1][1]) < 3.5 and len(set(r.comp(n, [q[:4], r.via_term((vx, vy))]))) == 1:
                    v = (vx, vy)
                    break
        v = v or endpoint_via(n, q)
        if v is None:
            nolink.append((n, q[0]))
        else:
            ends.append(v)
    if len(ends) < 2:
        continue
    vt = [r.via_term(v) for v in ends]
    for i, j in mst(vt):
        if len(set(r.comp(n, [vt[i], vt[j]]))) > 1:
            legs.append({'net': n, 'a': vt[i][1], 'b': vt[j][1]})
print('legs: %d; connection points without a via spot: %d (%.0fs)' % (len(legs), len(nolink), time.time() - t0), flush=True)
for n, q in nolink[:15]:
    print('  no via spot: %s %s' % (n, q))
left = []
if legs:
    ax = [l['a'][0] for l in legs] + [l['b'][0] for l in legs]
    ay = [l['a'][1] for l in legs] + [l['b'][1] for l in legs]
    win = (max(50.5, min(ax) - 3), max(53.6, min(ay) - 3), min(190.6, max(ax) + 3), min(146.9, max(ay) + 3))
    left = negroute.negotiate(bd, legs, win, {ly: 0.127 for ly in LAYERS}, COST,
                              iters=int(os.environ.get('NEG_ITERS', '15')), log=lambda s: print(s, flush=True))
bd.save()
after = status(PCB)
lost = [n for n in before if before[n] and not after.get(n, False)]
gain = [n for n in before if not before[n] and after.get(n, False)]
print('complete nets: %d -> %d (gained %d, lost %d) in %.0f s' % (sum(before.values()), sum(after.values()),
                                                                    len(gain), len(lost), time.time() - t0))
print('still open STM32 nets: %s' % ' '.join(n for n in targets if not after.get(n, False)))
if lost:
    print('LOST: %s' % ' '.join(lost))
