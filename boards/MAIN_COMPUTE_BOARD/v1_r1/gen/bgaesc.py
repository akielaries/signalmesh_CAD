import math
import os
import sys
import time

import pcbnew

import negroute
import proute
import pslib
import rlib

# planned STM32 TFBGA265 escape plus routing. run on the fanout board (bgafan.py fan).
#   1. partial copper of open STM32 nets outside the two BGA courtyards is ripped
#   2. escape: each signal via under the package gets a channel of its own out to the package edge: a half
#      cell diagonal onto a ball line, then straight along that line (inner layers have no ball pads, so
#      ball lines are the channels between vias). one net per (side, layer, line); innermost vias are
#      planned first because they have the fewest options. outer-ring signal balls run straight out on F.Cu
#   3. every net is routed from its escape end (pinned to the escape's layer) to its other terminals with
#      negotiated congestion
# usage: bgaesc.py <board>
PCB = sys.argv[1]
P = 0.8
EXT = 1.2           # escape ends this far outside the outermost ball line
VIA_D = 0.4
W_ESC = 0.1
LAYERS = ('In2.Cu', 'In7.Cu', 'In5.Cu', 'B.Cu', 'F.Cu')
COST = {'In2.Cu': 1.0, 'In7.Cu': 1.0, 'In5.Cu': 1.05, 'B.Cu': 1.15, 'F.Cu': 1.2}
ESC_LAYER_PEN = {'In2.Cu': 0.0, 'In7.Cu': 0.0, 'In5.Cu': 0.5, 'B.Cu': 1.5}
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


def planes_of(bd):
    zs = bd.b.Zones()
    return {zs[i].GetNetname() for i in range(len(zs)) if not zs[i].GetIsRuleArea()} | {'GND'}


def status(path):
    rr = pslib.Router(path, [])
    pl = planes_of(rr.bd)
    T = {}
    for (x, y, hx, hy, n, lays, rnd, p) in rr.bd.pads:
        if n and n not in pl and not n.startswith('unconnected'):
            T.setdefault(n, []).append((p.GetParentFootprint().GetReference() + ':' + p.GetNumber(), (x, y), lays, (hx, hy)))
    return {n: len(set(rr.comp(n, ts))) == 1 for n, ts in T.items() if len(ts) > 1}


live = lambda n: n and not n.startswith('unconnected')
before = status(PCB)
r = router()
bd = r.bd
planes = planes_of(bd)
u11 = bd.b.FindFootprintByReference('U11')
B = [(u11.Pads()[k].GetNumber(), u11.Pads()[k].GetNetname(), u11.Pads()[k].GetPosition().x / 1e6,
      u11.Pads()[k].GetPosition().y / 1e6) for k in range(len(u11.Pads()))]
sig = {q[1] for q in B if live(q[1]) and q[1] not in planes}
opn = {n for n in sig if n in before and not before[n]}

# 1) rip partial copper of the open nets outside both courtyards (skipped with NO_RIP=1)
if os.environ.get('NO_RIP'):
    opn_rip = set()
else:
    opn_rip = opn
boxes = []
for ref in ('U11', 'U100'):
    c = bd.b.FindFootprintByReference(ref).GetCourtyard(pcbnew.F_CrtYd).BBox()
    boxes.append((c.GetLeft() / 1e6, c.GetTop() / 1e6, c.GetRight() / 1e6, c.GetBottom() / 1e6))
inb = lambda x, y: any(q[0] <= x <= q[2] and q[1] <= y <= q[3] for q in boxes)
ts = bd.b.Tracks()
kill = []
for i in range(len(ts)):
    it = ts[i]
    if it.GetNetname() in opn_rip:
        pts = [it.GetPosition()] if it.GetClass() == 'PCB_VIA' else [it.GetStart(), it.GetEnd()]
        if not all(inb(p.x / 1e6, p.y / 1e6) for p in pts):
            kill.append(it)
for it in kill:
    bd.b.Remove(it)
graveyard = kill
bd.save()
print('open STM32 nets: %d of %d; ripped %d partial-route items' % (len(opn), len(sig), len(kill)), flush=True)
r = router()
bd = r.bd

# 2) escape planning
xs, ys = [q[2] for q in B], [q[3] for q in B]
X0, Y0, XN, YN = min(xs), min(ys), max(xs), max(ys)
NI = int(round((XN - X0) / P))
gi = lambda x: int(round((x - X0) / P))
gj = lambda y: int(round((y - Y0) / P))
T = r.terms
dest = {}
for n in opn:
    pts = [t[1] for t in T(n) if not t[0].startswith('U11:')]
    if pts:
        dest[n] = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
vias = {}
for (vx, vy, vr, vn) in bd.vias:
    vias.setdefault(vn, []).append((vx, vy))
items = []      # (net, kind, data)
for (num, n, x, y) in B:
    if n not in opn or n not in dest:
        continue
    dv = [v for v in vias.get(n, []) if abs(math.hypot(v[0] - x, v[1] - y) - 0.566) < 0.02]
    if dv:
        vx, vy = dv[0]
        items.append((n, 'via', (vx, vy, int(math.floor((vx - X0) / P)), int(math.floor((vy - Y0) / P)))))
    elif min(gi(x), NI - gi(x), gj(y), NI - gj(y)) == 0:
        items.append((n, 'ball', (x, y)))


def candidates(kind, d):
    # (side, layer, line, path) for one escape
    out = []
    if kind == 'ball':
        x, y = d
        i, j = gi(x), gj(y)
        for side, ok, path in (('W', i == 0, [(x, y), (X0 - EXT, y)]), ('E', i == NI, [(x, y), (XN + EXT, y)]),
                               ('N', j == 0, [(x, y), (x, Y0 - EXT)]), ('S', j == NI, [(x, y), (x, YN + EXT)])):
            if ok:
                out.append((side, 'F.Cu', path))
        return out
    vx, vy, ci, cj = d
    for ly in ESC_LAYER_PEN:
        for j in (cj, cj + 1):
            out.append(('W', ly, [(vx, vy), (X0 + ci * P, Y0 + j * P), (X0 - EXT, Y0 + j * P)]))
            out.append(('E', ly, [(vx, vy), (X0 + (ci + 1) * P, Y0 + j * P), (XN + EXT, Y0 + j * P)]))
        for i in (ci, ci + 1):
            out.append(('N', ly, [(vx, vy), (X0 + i * P, Y0 + cj * P), (X0 + i * P, Y0 - EXT)]))
            out.append(('S', ly, [(vx, vy), (X0 + i * P, Y0 + (cj + 1) * P), (X0 + i * P, YN + EXT)]))
    return out


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


ring = lambda it: (min(it[2][2] + 1, NI - it[2][2], it[2][3] + 1, NI - it[2][3]) if it[1] == 'via' else -1)
esc = {}
nofit = []
for it in sorted(items, key=lambda it: -ring(it)):
    n, kind, d = it
    best = []
    for side, ly, path in candidates(kind, d):
        ex = path[-1]
        L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))
        c = L + abs(ex[0] - dest[n][0]) + abs(ex[1] - dest[n][1]) + ESC_LAYER_PEN.get(ly, 0.0) * 3
        best.append((c, side, ly, path))
    best.sort(key=lambda q: q[0])
    got = None
    for c, side, ly, path in best:
        if free(n, ly, path):
            got = (side, ly, path)
            break
    if not got:
        nofit.append(n)
        continue
    st = []
    bd.stage_track(got[2], W_ESC, n, got[1], st)
    bd.commit(st)
    esc[n] = (got[2][-1], got[1])
print('escapes: %d planned (%s); no channel: %d %s (%.0fs)' % (
    len(esc), ', '.join('%s %d' % (ly, sum(1 for v in esc.values() if v[1] == ly)) for ly in LAYERS),
    len(nofit), ' '.join(nofit[:20]), time.time() - t0), flush=True)
bd.save()

# 3) legs from each escape end (pinned to its layer) to the net's other terminals
_u = bd.b.FindFootprintByReference('U100')
fpga_c = (_u.GetPosition().x / 1e6, _u.GetPosition().y / 1e6)


def endpoint_via(n, term):
    name, p, lays = term[0], term[1], term[2]
    if name.startswith('VIA') or set(rlib.LAYERS) <= set(lays):
        return p
    st = []
    if name.startswith('U100:'):
        ox, oy = p[0] - fpga_c[0], p[1] - fpga_c[1]
        d = (1 if ox > 0 else -1, 0) if abs(ox) >= abs(oy) else (0, 1 if oy > 0 else -1)
        for k in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
            for sh in (0.5, -0.5, 0.0):
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
    v = proute.drop_via(bd, p, n, (X0, Y0), st, w=0.15, radii=(0.5, 0.65, 0.8, 1.0, 1.3, 1.6), layer=r.side(lays))
    if v:
        bd.commit(st)
        return v
    bd.unstage(st)
    return None


vias = {}
for (vx, vy, vr, vn) in bd.vias:
    vias.setdefault(vn, []).append((vx, vy))
legs, nolink = [], []
for n in sorted(opn):
    if n not in dest:
        continue
    ends = []       # (point, layer or None)
    if n in esc:
        ends.append(esc[n])
    else:
        dv = [v for (num, nn, x, y) in B if nn == n for v in vias.get(n, []) if abs(math.hypot(v[0] - x, v[1] - y) - 0.566) < 0.02]
        if dv:
            ends.append((dv[0], None))
    for q in T(n):
        if q[0].startswith('U11:'):
            continue
        v = None
        for (vx, vy) in vias.get(n, []):
            if math.hypot(vx - q[1][0], vy - q[1][1]) < 3.5 and len(set(r.comp(n, [q[:4], r.via_term((vx, vy))]))) == 1:
                v = (vx, vy)
                break
        v = v or endpoint_via(n, q)
        if v is None:
            nolink.append((n, q[0]))
        else:
            ends.append((v, None))
    if len(ends) < 2:
        continue
    used, edges = {0}, []
    while len(used) < len(ends):
        bst = min(((math.hypot(ends[i][0][0] - ends[j][0][0], ends[i][0][1] - ends[j][0][1]), i, j)
                   for i in used for j in range(len(ends)) if j not in used))
        edges.append(bst[1:])
        used.add(bst[2])
    for i, j in edges:
        a, b = ends[i], ends[j]
        if b[1] and not a[1]:
            a, b = b, a
        leg = {'net': n, 'a': a[0], 'b': b[0]}
        if a[1]:
            leg['ly'] = a[1]
        legs.append(leg)
print('legs: %d (%d pinned to an escape layer); terminals without a via spot: %d (%.0fs)'
      % (len(legs), sum(1 for l in legs if 'ly' in l), len(nolink), time.time() - t0), flush=True)
if legs:
    ax = [l['a'][0] for l in legs] + [l['b'][0] for l in legs]
    ay = [l['a'][1] for l in legs] + [l['b'][1] for l in legs]
    win = (max(50.5, min(ax) - 3), max(53.6, min(ay) - 3), min(190.6, max(ax) + 3), min(146.9, max(ay) + 3))
    negroute.negotiate(bd, legs, win, {ly: 0.127 for ly in LAYERS}, COST,
                       iters=int(os.environ.get('NEG_ITERS', '25')), log=lambda s: print(s, flush=True))
bd.save()
after = status(PCB)
lost = [n for n in before if before[n] and not after.get(n, False)]
gain = [n for n in before if not before[n] and after.get(n, False)]
print('complete nets: %d -> %d (gained %d, lost %d) in %.0f s' % (sum(before.values()), sum(after.values()),
                                                                    len(gain), len(lost), time.time() - t0))
print('still open STM32 nets (%d): %s' % (sum(1 for n in sig if not after.get(n, True)), ' '.join(sorted(n for n in sig if not after.get(n, True)))))
if lost:
    print('LOST: %s' % ' '.join(lost))
