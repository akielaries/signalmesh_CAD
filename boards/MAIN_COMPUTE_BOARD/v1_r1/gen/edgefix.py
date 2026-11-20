import math
import sys
import time

import pslib

# rip-up-and-retry at the STM32 edges: for each open net with an STM32 pin, route it; if that fails,
# rip the few nets whose vias/tracks crowd its pin, route the blocked net first, then route the ripped
# nets back. a step is kept only when the target connects, every ripped net that was complete is
# complete again (incomplete ones no worse), and nothing exceeds 2.5x its span (+10 mm). otherwise
# the board is left as it was. usage: edgefix.py <board>
PCB = sys.argv[1]
SKIP = {'+3V3', 'USBH_DM', 'USBH_DP'}
WIDE = {'/STM32/VCAP': 0.3}
log = open(PCB + '.edgefix.log', 'w')


def say(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    log.write(s + '\n')
    log.flush()


def load():
    return pslib.Router(PCB, ['U11', 'U100'])


def planes_of(r):
    zs = r.bd.b.Zones()
    return {zs[i].GetNetname() for i in range(len(zs))} | {'GND'}


def pieces(r, n):
    ts = r.terms(n)
    return len(set(r.comp(n, ts))) if len(ts) > 1 else 1


def span(r, n):
    ps = [t[1] for t in r.terms(n)]
    return max((math.hypot(a[0] - b[0], a[1] - b[1]) for a in ps for b in ps), default=0.0)


def length(r, n):
    return sum(math.hypot(xb - xa, yb - ya) for (xa, ya, xb, yb, hw, nn, ly) in r.bd.tracks if nn == n)


def sane(r, n):
    s = span(r, n)
    return length(r, n) <= max(2.5 * s, s + 10.0)


def route(r, n):
    r.net(n, r.terms(n), WIDE.get(n, 0.127), inner=('In2.Cu',))


r = load()
planes = planes_of(r)
targets = []
for (x, y, hx, hy, n, lays, rnd, p) in r.bd.pads:
    if p.GetParentFootprint().GetReference() == 'U11' and n and n not in planes and n not in SKIP \
            and not n.startswith('unconnected') and n not in [t[0] for t in targets] and pieces(r, n) > 1:
        targets.append((n, (x, y)))
targets.sort(key=lambda t: span(r, t[0]))
say('targets: %d' % len(targets))
kept, rerouted, failed = [], set(), []
graveyard = []      # removed swig items stay referenced: collecting them corrupts pcbnew's type table
t0 = time.time()
for n, pin in targets:
    r = load()
    if pieces(r, n) == 1:
        continue
    route(r, n)
    if pieces(r, n) == 1 and sane(r, n):
        r.bd.save()
        kept.append(n)
        say('%-18s routed directly (%.1f mm)' % (n, length(r, n)))
        continue
    # rip what crowds the target's pads (any end can be the blocked one)
    r = load()
    blk = set()
    for (tn, pp, lays, hs) in r.terms(n):
        for (vx, vy, vr, vn) in r.bd.vias:
            if vn != n and vn not in planes and math.hypot(vx - pp[0], vy - pp[1]) < 1.5:
                blk.add(vn)
        for (xa, ya, xb, yb, hw, vn, ly) in r.bd.tracks:
            if vn != n and vn not in planes and ly in lays and ly in ('F.Cu', 'B.Cu'):
                dx, dy = xb - xa, yb - ya
                L2 = dx * dx + dy * dy
                u = 0 if L2 == 0 else max(0, min(1, ((pp[0] - xa) * dx + (pp[1] - ya) * dy) / L2))
                if math.hypot(pp[0] - xa - u * dx, pp[1] - ya - u * dy) < 0.8:
                    blk.add(vn)
    blk = sorted(b for b in blk if not b.startswith(('+', 'DDR_', 'MEZZ_', 'GTP')))
    if not blk or len(blk) > 6:
        failed.append((n, 'blockers: %d' % len(blk)))
        say('%-18s skipped (%d blockers)' % (n, len(blk)))
        continue
    before = {b: pieces(r, b) for b in blk}
    b_ = r.bd.b
    ts = b_.Tracks()
    kill = [ts[i] for i in range(len(ts)) if ts[i].GetNetname() in blk]
    for t in kill:
        b_.Remove(t)
    r.bd.reload()
    route(r, n)
    for b in blk:
        route(r, b)
    ok = pieces(r, n) == 1 and sane(r, n) and all(pieces(r, b) <= before[b] for b in blk) \
        and all(sane(r, b) for b in blk if pieces(r, b) == 1)
    if ok:
        r.bd.save()
        kept.append(n)
        rerouted |= set(blk)
        say('%-18s routed after re-routing %s (%.1f mm)' % (n, ', '.join(blk), length(r, n)))
    else:
        failed.append((n, 'rip-up of %s did not work out' % ', '.join(blk)))
        say('%-18s still open (tried re-routing %s)' % (n, ', '.join(blk)))
    graveyard.append(kill)
say('done in %.0f s: %d connected, %d still open' % (time.time() - t0, len(kept), len(failed)))
say('nets re-routed to make room: %s' % ', '.join(sorted(rerouted)))
