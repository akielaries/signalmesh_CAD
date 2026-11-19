import math
import sys

import pcbnew

import ddr
import proute
import rlib

# quadspi: stm32 (top) to the two w25q01 (bottom, dual-flash mode). a via beside each stm32 pin,
# then b.cu (inner layers as fallback) to the flash pads, clk/ncs daisy-chained u18 -> u19.
# first moves the ncs pull-up next to u18 on the bottom. additive, skips connected nets
PCB = sys.argv[1]
MM = 1e6
rlib.BGA_RECTS[:] = []
proute.ESC[:] = []
rlib.TIGHT = True
W = {'B.Cu': 0.127, 'In5.Cu': 0.23, 'In2.Cu': 0.23}
CLR = 0.127
OUTER = tuple(0.75 + 0.25 * i for i in range(38))

# 1) pull-up beside u18 pin 1, bottom side
b = pcbnew.LoadBoard(PCB)
fs = b.Footprints()
fps = [fs[i] for i in range(len(fs))]
r61 = b.FindFootprintByReference('R61')
u18 = b.FindFootprintByReference('U18')
pin1 = [u18.Pads()[k] for k in range(len(u18.Pads())) if u18.Pads()[k].GetNumber() == '1'][0].GetPosition()


def crt(f):
    c = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
    return (bb.GetLeft() / MM, bb.GetTop() / MM, bb.GetRight() / MM, bb.GetBottom() / MM)


def tht(f):
    return any(f.Pads()[k].GetAttribute() == pcbnew.PAD_ATTRIB_PTH for k in range(len(f.Pads())))


def hit(a, c, gap=0.2):
    return a[0] - gap < c[2] and a[2] + gap > c[0] and a[1] - gap < c[3] and a[3] + gap > c[1]


def free(f):
    r = crt(f)
    return not any(o.GetReference() != f.GetReference() and (o.IsFlipped() or tht(o)) and hit(r, crt(o)) for o in fps)


key = lambda v: (round(v.x / MM, 3), round(v.y / MM, 3))
moved = None
if not r61.IsFlipped():
    old = {key(r61.Pads()[k].GetPosition()) for k in range(len(r61.Pads()))}
    ts = b.Tracks()
    items = [ts[i] for i in range(len(ts))]
    vias, kill = set(), []
    for t in items:
        if t.GetClass() != 'PCB_VIA':
            s, e = key(t.GetStart()), key(t.GetEnd())
            if s in old or e in old:
                kill.append(t)
                vias.add((t.GetNetname(), e if s in old else s))
    kill += [t for t in items if t.GetClass() == 'PCB_VIA' and (t.GetNetname(), key(t.GetPosition())) in vias]
    for t in kill:
        b.Remove(t)
    r61.Flip(r61.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    x0, y0 = pin1.x / MM, pin1.y / MM
    for rad in [1.5 + 0.25 * i for i in range(40)]:
        n = max(8, int(2 * math.pi * rad / 0.25))
        for k in range(n):
            a = 2 * math.pi * k / n
            for rot in (0, 90):
                r61.SetOrientationDegrees(rot)
                r61.SetPosition(pcbnew.VECTOR2I(int((x0 + rad * math.cos(a)) * MM), int((y0 + rad * math.sin(a)) * MM)))
                if free(r61):
                    moved = (round(r61.GetPosition().x / MM, 2), round(r61.GetPosition().y / MM, 2), rot)
                    break
            if moved:
                break
        if moved:
            break
    if not moved:
        raise SystemExit('no spot for R61')
    b.Save(PCB)
print('R61 moved to bottom at', moved)

# 2) route
bd = rlib.Board(PCB)
STM = ddr.ref_of(bd, 'STM32H755')
ends = {}
for (x, y, hx, hy, n, lays, rnd, p) in bd.pads:
    if n.startswith('QSPI_'):
        ends.setdefault(n, []).append((p.GetParentFootprint().GetReference(), (x, y)))


def connected(net, a, b_):
    k = lambda x, y: (round(x, 3), round(y, 3))
    g = {}
    for (xa, ya, xb, yb, hw, n, ly) in bd.tracks:
        if n == net:
            g.setdefault(k(xa, ya), set()).add(k(xb, yb))
            g.setdefault(k(xb, yb), set()).add(k(xa, ya))
    seen, todo = {k(*a)}, [k(*a)]
    while todo:
        x = todo.pop()
        if x == k(*b_):
            return True
        for y in g.get(x, ()):
            if y not in seen:
                seen.add(y)
                todo.append(y)
    return False


def leg(net, a, c, st):
    # b.cu first; inner layer with a via at the bottom pad as fallback
    pts = bd.path('B.Cu', a, c, W['B.Cu'] / 2, {net}, CLR, margin=15.0)
    if pts:
        bd.stage_track(pts, W['B.Cu'], net, 'B.Cu', st)
        return 'B.Cu'
    sub = []
    vb = proute.drop_via(bd, c, net, a, sub, radii=OUTER[:12], layer='B.Cu')
    if not vb:
        return None
    for ly in ('In5.Cu', 'In2.Cu'):
        pts = bd.path(ly, a, vb, W[ly] / 2, {net}, CLR, margin=15.0)
        if pts:
            st += sub
            bd.stage_track(pts, W[ly], net, ly, st)
            return ly
    bd.unstage(sub)
    return None


done, fail = [], []
nets = sorted(ends, key=lambda n: len(ends[n]))
for net in nets:
    s = [p for r, p in ends[net] if r == STM][0]
    rest = [p for r, p in ends[net] if r != STM]
    if all(connected(net, s, p) for p in rest):
        continue
    st = []
    va = proute.drop_via(bd, s, net, rest[0], st, radii=OUTER)
    ok = va is not None
    cur, todo, used = va, list(rest), []
    while ok and todo:
        nxt = min(todo, key=lambda p: math.hypot(p[0] - cur[0], p[1] - cur[1]))
        ly = leg(net, cur, nxt, st)
        if not ly:
            ok = False
            break
        used.append(ly)
        todo.remove(nxt)
        cur = nxt
    if ok:
        bd.commit(st)
        done.append((net, used))
    else:
        bd.unstage(st)
        fail.append(net)
bd.save()
print('qspi: routed %d of %d' % (len(done), len(nets)))
for d in done:
    print('  ', d)
print('open:', fail)
