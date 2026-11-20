import math
import shutil
import sys

import pcbnew

import proute
import pslib

# STM32 (U11) re-fanout. the edges were fenced by a single row of vias placed in routing order. this
# rips each STM32 signal net's copper inside a 4 mm band round the pin field (plane nets and their
# stitching stay), gives the pins that need one a via in a two-row staggered dogbone pattern, reconnects
# every net to where its route was cut (same layer and width), routes the nets that were open, and keeps
# the result only if more nets are complete and no complete net is lost. usage: fanout_u11.py <board>
PCB = sys.argv[1]
SNAP = PCB + '.prefanout'
MM = 1e6
BAND = 4.0
ROWS = (0.9, 1.5, 2.1, 2.7, 3.3, 3.9)  # via distance outward from the pin tip; alternate pins use rows 0 / 1
VIA_D = 0.4                  # fanout vias 0.4/0.2 mm (0.1 mm annular ring)
shutil.copy(PCB, SNAP)


def status(path):
    r = pslib.Router(path, [])
    zs = r.bd.b.Zones()
    planes = {zs[i].GetNetname() for i in range(len(zs))} | {'GND'}
    T = {}
    for (x, y, hx, hy, n, lays, rnd, p) in r.bd.pads:
        if n and n not in planes and not n.startswith('unconnected'):
            T.setdefault(n, []).append((p.GetParentFootprint().GetReference() + ':' + p.GetNumber(), (x, y), lays, (hx, hy)))
    return {n: len(set(r.comp(n, ts))) == 1 for n, ts in T.items() if len(ts) > 1}, planes


before, planes = status(PCB)
b = pcbnew.LoadBoard(PCB)
u = b.FindFootprintByReference('U11')
pins = []
for k in range(len(u.Pads())):
    p = u.Pads()[k]
    if not p.GetNumber():
        continue
    bb = p.GetBoundingBox()
    pins.append((p.GetNumber(), p.GetNetname(), p.GetPosition().x / MM, p.GetPosition().y / MM,
                 (bb.GetLeft() / MM, bb.GetTop() / MM, bb.GetRight() / MM, bb.GetBottom() / MM)))
xs = [p[2] for p in pins]
ys = [p[3] for p in pins]
X0, X1, Y0, Y1 = min(xs), max(xs), min(ys), max(ys)


def side(x, y):
    return 'L' if abs(x - X0) < 0.05 else 'R' if abs(x - X1) < 0.05 else 'T' if abs(y - Y0) < 0.05 else 'B'


tipx0 = min(p[4][0] for p in pins)
tipx1 = max(p[4][2] for p in pins)
tipy0 = min(p[4][1] for p in pins)
tipy1 = max(p[4][3] for p in pins)
R = (tipx0 - BAND, tipy0 - BAND, tipx1 + BAND, tipy1 + BAND)
inR = lambda x, y: R[0] < x < R[2] and R[1] < y < R[3]
# rip only a ring: the band outside the pins plus ~3 mm inside the pads' inner ends (inward vias). copper
# deeper under the body (routes crossing under the package) stays, so cuts land next to their vias
from shapely.geometry import LineString, Point, box as sbox
lin = [p for p in pins if side(p[2], p[3]) == 'L']
rin = [p for p in pins if side(p[2], p[3]) == 'R']
tin = [p for p in pins if side(p[2], p[3]) == 'T']
bin_ = [p for p in pins if side(p[2], p[3]) == 'B']
I = (max(p[4][2] for p in lin) + 3.0, max(p[4][3] for p in tin) + 3.0,
     min(p[4][0] for p in rin) - 3.0, min(p[4][1] for p in bin_) - 3.0)
RING = sbox(*R).difference(sbox(*I))
inRing = lambda x, y: RING.contains(Point(x, y))
targets = sorted({p[1] for p in pins if p[1] and p[1] not in planes and p[1] in before})
print('STM32 signal nets: %d (%d complete now)' % (len(targets), sum(before[n] for n in targets)))
# 1) rip inside the band
ts = b.Tracks()
kill = []
for i in range(len(ts)):
    t = ts[i]
    if t.GetNetname() not in targets:
        continue
    if t.GetClass() == 'PCB_VIA':
        if inRing(t.GetPosition().x / MM, t.GetPosition().y / MM):
            kill.append(t)
    else:
        a, z = (t.GetStart().x / MM, t.GetStart().y / MM), (t.GetEnd().x / MM, t.GetEnd().y / MM)
        g = LineString([a, z]) if a != z else Point(a)
        if g.intersects(RING):
            kill.append(t)
# the STM32's own plane pins (VDD/VSS...) join the pattern too: their stubs from a U11 pad and the via at
# the stub's far end go
key = lambda v: (round(v.x / MM, 3), round(v.y / MM, 3))
ppads = {(round(p[2], 3), round(p[3], 3)) for p in pins if p[1] in planes}
pv = set()
for i in range(len(ts)):
    t = ts[i]
    if t.GetClass() == 'PCB_TRACK' and t.GetNetname() in planes:
        s, e = key(t.GetStart()), key(t.GetEnd())
        if s in ppads or e in ppads:
            kill.append(t)
            pv.add((t.GetNetname(), e if s in ppads else s))
for i in range(len(ts)):
    t = ts[i]
    if t.GetClass() == 'PCB_VIA' and (t.GetNetname(), key(t.GetPosition())) in pv:
        kill.append(t)
for t in kill:
    b.Remove(t)
b.Save(PCB)
print('ripped %d items inside the band (incl. STM32 plane-pin stitching)' % len(kill))
graveyard = [kill]
# 2) fanout
r = pslib.Router(PCB, ['U11'])
r.clr = 0.127
# the whole band is a neck-down zone (0.1 mm / 0.09 mm, as under the fpga): reconnects have to thread the
# staggered via rows
import rlib
rlib.BGA_RECTS.append(R + (0.09,))
proute.ESC[:] = [q[:4] for q in rlib.BGA_RECTS]
bd = r.bd
T = r.terms


def cut_points(n):
    # free track ends of n (left by the rip): end not on another track end, a via or a pad of n
    ends = {}
    segs = [(xa, ya, xb, yb, hw, ly) for (xa, ya, xb, yb, hw, nn, ly) in bd.tracks if nn == n]
    for (xa, ya, xb, yb, hw, ly) in segs:
        for q in ((xa, ya), (xb, yb)):
            k = (round(q[0], 3), round(q[1], 3), ly)
            ends[k] = ends.get(k, []) + [hw * 2]
    vs = [(vx, vy) for (vx, vy, vr, nn) in bd.vias if nn == n]
    pads = [(x, y, hx, hy) for (x, y, hx, hy, nn, lays, rnd, p) in bd.pads if nn == n]
    out = []
    for (x, y, ly), ws in ends.items():
        if len(ws) > 1:
            continue
        if any(math.hypot(x - vx, y - vy) < 0.05 for vx, vy in vs):
            continue
        if any(abs(x - px) <= hx + 0.02 and abs(y - py) <= hy + 0.02 for px, py, hx, hy in pads):
            continue
        # a free end lying on another segment's middle is a t-junction, not a cut
        if any(ly == l2 and (abs(x - xa) + abs(y - ya) > 0.01 and abs(x - xb) + abs(y - yb) > 0.01) and
               abs((x - xa) * (yb - ya) - (y - ya) * (xb - xa)) / max(1e-9, math.hypot(xb - xa, yb - ya)) < 0.01 and
               min(xa, xb) - 0.01 <= x <= max(xa, xb) + 0.01 and min(ya, yb) - 0.01 <= y <= max(ya, yb) + 0.01
               for (xa, ya, xb, yb, hw, l2) in segs):
            continue
        out.append(('CUT@%.2f,%.2f' % (x, y), (x, y), {ly}, (0.06, 0.06), ws[0]))
    return out


cuts = {n: cut_points(n) for n in targets}
need = {}
for n in targets:
    others = [t for t in T(n) if not t[0].startswith('U11:')]
    # full fanout: in a staggered pattern every gap between first-row vias carries a neighbour's stub,
    # so a pin left without a via has no exit
    need[n] = True
order = {'L': lambda p: p[3], 'R': lambda p: p[3], 'T': lambda p: p[2], 'B': lambda p: p[2]}
fan = {}
nvia = nskip = 0
for sd in 'LRTB':
    row = sorted([p for p in pins if side(p[2], p[3]) == sd], key=order[sd])
    for i, (num, n, x, y, bb_) in enumerate(row):
        is_plane = n in planes and n
        if not is_plane and (n not in targets or not need[n]):
            continue
        out = {'L': (-1, 0), 'R': (1, 0), 'T': (0, -1), 'B': (0, 1)}[sd]
        tip = {'L': bb_[0], 'R': bb_[2], 'T': bb_[1], 'B': bb_[3]}[sd]
        placed = None
        for d in (ROWS[i % 2], ROWS[2], ROWS[(i + 1) % 2], ROWS[3], ROWS[4], ROWS[5]):
            for sh in (0.0, 0.25, -0.25, 0.5, -0.5):
                vx = tip + out[0] * d if out[0] else x + sh
                vy = tip + out[1] * d if out[1] else y + sh
                if out[0]:
                    vy = y + sh
                else:
                    vx = x + sh
                if proute.via_spot_ok(bd, vx, vy, n, r=VIA_D / 2, clr=0.127):
                    placed = (vx, vy)
                    break
            if placed:
                break
        if not placed:
            # inward, under the package body (no pads there on top)
            inner = {'L': bb_[2], 'R': bb_[0], 'T': bb_[3], 'B': bb_[1]}[sd]
            for d in (0.6, 1.2, 1.8, 2.4):
                for sh in (0.0, 0.25, -0.25):
                    vx = inner - out[0] * d if out[0] else x + sh
                    vy = inner - out[1] * d if out[1] else y + sh
                    if out[0]:
                        vy = y + sh
                    else:
                        vx = x + sh
                    if proute.via_spot_ok(bd, vx, vy, n, r=VIA_D / 2, clr=0.127):
                        placed = (vx, vy)
                        break
                if placed:
                    break
        if not placed:
            nskip += 1
            continue
        st = []
        r.stage([(x, y), placed], n, 0.15, 'F.Cu', st)
        bd.stage_via(placed[0], placed[1], n, st, d=VIA_D)
        bd.commit(st)
        if not is_plane:
            fan[n] = placed
        nvia += 1
print('fanout vias %d, pins without a via spot %d' % (nvia, nskip))


# 3) reconnect each net to its cut points, then finish the open ones
def leg(n, a, z, w):
    for c, o in ((a, z), (z, a)):
        if c[0].startswith('CUT'):
            ly = list(c[2])[0]
            ww = c[4]
            st = []
            if o[0].startswith('VIA') or ly in o[2]:
                pts = bd.path(ly, o[1], c[1], ww / 2, {n}, r.clr, margin=6.0, half_in=0.05)
                if pts:
                    r.stage(pts, n, ww, ly, st)
                    return st
            if ly in ('F.Cu', 'B.Cu') and ly in o[2]:
                return None
            vo = o[1] if o[0].startswith('VIA') else proute.drop_via(bd, o[1], n, c[1], st, w=0.15, radii=(0.6, 0.8, 1.0, 1.3, 1.6),
                                                                    layer=r.side(o[2]))
            if vo:
                pts = bd.path(ly, vo, c[1], ww / 2, {n}, r.clr, margin=6.0, half_in=0.05)
                if pts:
                    r.stage(pts, n, ww, ly, st)
                    return st
                # change layer: any routable layer to a via dropped beside the cut, then onto the cut layer
                for ly2 in ('In2.Cu', 'B.Cu', 'F.Cu', 'In5.Cu'):
                    if ly2 == ly:
                        continue
                    sub = []
                    vc = proute.drop_via(bd, c[1], n, vo, sub, w=min(ww, 0.15), radii=(0.5, 0.7, 0.9, 1.2, 1.5),
                                         layer=ly) if ly in ('F.Cu', 'B.Cu') else None
                    if vc is None and ly not in ('F.Cu', 'B.Cu'):
                        for rad in (0.5, 0.7, 0.9, 1.2):
                            for kk in range(8):
                                ax = c[1][0] + rad * math.cos(kk * math.pi / 4)
                                ay = c[1][1] + rad * math.sin(kk * math.pi / 4)
                                if proute.via_spot_ok(bd, ax, ay, n, r=VIA_D / 2, clr=0.127):
                                    p2 = bd.path(ly, (ax, ay), c[1], ww / 2, {n}, r.clr, margin=1.5, half_in=0.05)
                                    if p2:
                                        r.stage(p2, n, ww, ly, sub)
                                        bd.stage_via(ax, ay, n, sub, d=VIA_D)
                                        vc = (ax, ay)
                                        break
                            if vc:
                                break
                    if vc:
                        p3 = bd.path(ly2, vo, vc, 0.0635, {n}, r.clr, margin=6.0, half_in=0.05)
                        if p3:
                            r.stage(p3, n, 0.127, ly2, sub)
                            st += sub
                            return st
                    bd.unstage(sub)
            bd.unstage(st)
            return None
    s, how = r.leg(n, a[:4], z[:4], w, inner=('In2.Cu',))
    return s


def mst(tt):
    used, edges = {0}, []
    while len(used) < len(tt):
        best = min(((math.hypot(tt[i][1][0] - tt[j][1][0], tt[i][1][1] - tt[j][1][1]), i, j)
                    for i in used for j in range(len(tt)) if j not in used))
        edges.append(best[1:])
        used.add(best[2])
    return edges


import os
DBG = os.environ.get('DEBUG_NET')
if DBG:
    import numpy as np
    for c in cuts.get(DBG, []):
        ly = list(c[2])[0]
        v = fan.get(DBG)
        print('debug', DBG, 'via', v, 'cut', c[1], ly, 'width', c[4])
        for (a, nm) in ((v, 'via'), (c[1], 'cut')):
            if not a:
                continue
            win = (a[0] - 0.6, a[1] - 0.6, a[0] + 0.6, a[1] + 0.6)
            bl, gx, gy = bd.grid(ly, win, c[4] / 2, {DBG}, r.clr, half_in=0.05)
            j, i = int(round((a[1] - gy[0]) / (gy[1] - gy[0]))), int(round((a[0] - gx[0]) / (gx[1] - gx[0])))
            print('   %s cell blocked: %s; blocked fraction around: %.2f' % (nm, bool(bl[j, i]), bl.mean()))
            near = [(round(x2, 2), round(y2, 2), nn) for (x2, y2, hx, hy, nn, lays, rnd, p) in bd.pads if abs(x2 - a[0]) < 0.8 and abs(y2 - a[1]) < 0.8 and nn != DBG]
            nv = [(round(vx, 2), round(vy, 2), nn) for (vx, vy, vr, nn) in bd.vias if math.hypot(vx - a[0], vy - a[1]) < 0.8 and nn != DBG]
            nt = [(nn, ll) for (xa, ya, xb, yb, hw, nn, ll) in bd.tracks if nn != DBG and ll == ly and min(xa, xb) - 0.6 < a[0] < max(xa, xb) + 0.6 and min(ya, yb) - 0.6 < a[1] < max(ya, yb) + 0.6]
            print('   near: pads', near[:4], 'vias', nv[:4], 'tracks', nt[:4])
        pts = bd.path(ly, v, c[1], c[4] / 2, {DBG}, r.clr, margin=6.0, half_in=0.05) if v else None
        print('   path found:', bool(pts))
    shutil.copy(SNAP, PCB)
    sys.exit(0)
why = {}
# every leg of every net in one queue, shortest first: the short escapes out of the via rows go in before
# the long connections that would otherwise fill the gaps; then one retry pass for what failed
TT = {}
legs = []
for n in targets:
    tt = [q + (0.127,) for q in T(n) if not (n in fan and q[0].startswith('U11:'))]
    if n in fan:
        tt = [r.via_term(fan[n]) + (0.127,)] + tt
    tt += cuts[n]
    if len(tt) < 2:
        continue
    TT[n] = tt
    for i, j in mst(tt):
        legs.append((math.hypot(tt[i][1][0] - tt[j][1][0], tt[i][1][1] - tt[j][1][1]), n, i, j))
legs.sort()
for attempt in range(2):
    failed = []
    for d, n, i, j in legs:
        tt = TT[n]
        c = r.comp(n, [q[:4] for q in tt])
        if c[i] == c[j]:
            continue
        s = leg(n, tt[i], tt[j], 0.127)
        if s:
            bd.commit(s)
        else:
            failed.append((d, n, i, j))
    print('reconnect pass %d: %d legs failed' % (attempt + 1, len(failed)))
    legs = failed
for d, n, i, j in legs:
    tt = TT[n]
    why.setdefault(n, []).append('%s(%s) -> %s(%s)' % (tt[i][0], ','.join(sorted(tt[i][2]))[:12], tt[j][0], ','.join(sorted(tt[j][2]))[:12]))
bd.save()
after, _ = status(PCB)
lost = [n for n in before if before[n] and not after.get(n, False)]
gain = [n for n in before if not before[n] and after.get(n, False)]
print('complete nets: %d -> %d (gained %d, lost %d)' % (sum(before.values()), sum(after.values()), len(gain), len(lost)))
print('lost nets whose pin got no fanout via: %d of %d' % (sum(1 for x in lost if x not in fan), len(lost)))
for n in lost[:12]:
    print('  lost %-14s via %s, %d cuts, failed legs: %s' % (n, 'yes' if n in fan else 'NO', len(cuts[n]), '; '.join(why.get(n, ['(none failed: comp?)'])[:3])))
if lost or len(gain) == 0:
    shutil.copy(SNAP, PCB)
    print('NOT kept: board restored. lost: %s' % ' '.join(lost[:40]))
else:
    print('kept. gained: %s' % ' '.join(gain))
