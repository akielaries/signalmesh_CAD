import math
import sys

import pcbnew

import proute
import rlib

# power stage of U5 (TPS62130, 5 V -> +1V0). the input cap C10 goes on the bottom right under the
# PVIN pins (top-side space is taken by U6): +5V pad -> via -> PVIN pins 10-12, GND pad -> the
# exposed-pad thermal via, so the hot loop is a few mm. the switch node is a short wide run from
# pins 1-3 to L4. fb, soft-start, power-good, enable and the 5 V feed are routed leg by leg
PCB = sys.argv[1]
MM = 1e6
V = lambda x, y: pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM)))
b = pcbnew.LoadBoard(PCB)
key = lambda v: (round(v.x / MM, 3), round(v.y / MM, 3))


def track(a, z, w, net, layer):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(V(*a))
    t.SetEnd(V(*z))
    t.SetWidth(int(w * MM))
    t.SetLayer(layer)
    t.SetNet(b.FindNet(net))
    b.Add(t)


def via(p, net, d=0.45, drill=0.2):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(V(*p))
    v.SetWidth(int(d * MM))
    v.SetDrill(int(drill * MM))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(b.FindNet(net))
    b.Add(v)


# 1) C10 to the bottom, under the PVIN pins, +5V pad north
c10 = b.FindFootprintByReference('C10')
old = {key(c10.Pads()[k].GetPosition()) for k in range(len(c10.Pads()))}
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
if not c10.IsFlipped():
    c10.Flip(c10.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
CX, CY = 94.15, 111.6
for rot in (90, 270):
    c10.SetOrientationDegrees(rot)
    c10.SetPosition(V(CX, CY))
    pp = {c10.Pads()[k].GetNumber(): c10.Pads()[k].GetPosition() for k in range(2)}
    if pp['1'].y < pp['2'].y:
        break
p5 = (pp['1'].x / MM, pp['1'].y / MM)
pg = (pp['2'].x / MM, pp['2'].y / MM)
print('C10 bottom at (%.2f, %.2f) rot %d: +5V pad %s, GND pad %s' % (CX, CY, rot, p5, pg))

# 2) hot loop: PVIN pins 10-12 joined on top, down a via to C10 +5V; C10 GND to the ep thermal via
track((93.75, 111.25), (93.75, 112.25), 0.25, '+5V', pcbnew.F_Cu)
track((93.75, 111.25), (94.15, 110.85), 0.4, '+5V', pcbnew.F_Cu)
track((94.15, 110.85), (94.15, 109.55), 0.4, '+5V', pcbnew.F_Cu)
via((94.15, 109.55), '+5V')
track((94.15, 109.55), p5, 0.5, '+5V', pcbnew.B_Cu)
track(pg, (92.59, 112.59), 0.5, 'GND', pcbnew.B_Cu)

# 3) switch node: pins 1-3 joined, then a 0.9 mm run to L4 pin 1
track((90.25, 111.25), (90.25, 112.25), 0.25, '/POWER/SW_1V0', pcbnew.F_Cu)
for a, z in (((90.25, 111.75), (89.0, 110.5)), ((89.0, 110.5), (88.25, 109.75)), ((88.25, 109.75), (88.25, 108.6))):
    track(a, z, 0.9, '/POWER/SW_1V0', pcbnew.F_Cu)
b.Save(PCB)

# 4) the small nets, leg by leg, necking to 0.1 mm at U5's 0.5 mm pins
bd = rlib.Board(PCB)
bb = b.FindFootprintByReference('U5').GetBoundingBox(False)
rlib.BGA_RECTS[:] = [(bb.GetLeft() / MM - 0.6, bb.GetTop() / MM - 0.6, bb.GetRight() / MM + 0.6,
                      bb.GetBottom() / MM + 0.6, 0.09)]
proute.ESC[:] = [r[:4] for r in rlib.BGA_RECTS]
rlib.TIGHT = True
CLR = 0.15
NECK = 0.1
W = {'/POWER/FB_1V0': 0.15, '/POWER/SS_1V0': 0.15, '/POWER/PG_1V0': 0.15, '/POWER/PG_5V': 0.15, '+5V': 0.5}
term = {}
for (x, y, hx, hy, n, lays, rnd, p) in bd.pads:
    if n in W:
        term.setdefault(n, []).append((p.GetParentFootprint().GetReference(), (x, y), lays))
# the 5 V feed: only U5's own pins, C10 and the nearby 5 V source caps (U6 is the next chunk)
term['+5V'] = [t for t in term['+5V'] if t[0] in ('U5', 'C10', 'C25', 'L1')]


def comp(net):
    pts = [t[1] for t in term[net]]
    segs = [(xa, ya, xb, yb) for (xa, ya, xb, yb, hw, n, ly) in bd.tracks if n == net]
    vs = [(vx, vy) for (vx, vy, vr, n) in bd.vias if n == net]
    nodes = pts + vs + [(s[0], s[1]) for s in segs] + [(s[2], s[3]) for s in segs]
    par = list(range(len(nodes)))

    def fd(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    idx = {}
    for i, p in enumerate(nodes):
        k = (round(p[0] / 0.06), round(p[1] / 0.06))
        if k in idx:
            par[fd(i)] = fd(idx[k])
        idx[k] = i
    base = len(pts) + len(vs)
    for j in range(len(segs)):
        par[fd(base + j)] = fd(base + len(segs) + j)
    for i, (r, (x, y), lays) in enumerate(term[net]):
        for j in range(len(pts), len(nodes)):
            if math.hypot(nodes[j][0] - x, nodes[j][1] - y) < 0.35:
                par[fd(i)] = fd(j)
    # pins of the same part on the same net are tied inside the part only for the ep; treat
    # pins already joined by copper through comp, nothing else
    return [fd(i) for i in range(len(pts))]


def stage(pts, net, ly, st):
    for seg, inside in rlib.split_neck(pts):
        bd.stage_track(seg, NECK if inside else W[net], net, ly, st)


def side(lays):
    return 'B.Cu' if 'B.Cu' in lays and 'F.Cu' not in lays else 'F.Cu'


def leg(net, a, z):
    (ra, pa, la), (rz, pz, lz) = a, z
    hw = W[net] / 2
    for ly in ('F.Cu', 'B.Cu'):
        if ly in la and ly in lz:
            pts = bd.path(ly, pa, pz, hw, {net}, CLR, margin=5.0, half_in=NECK / 2)
            if pts:
                st = []
                stage(pts, net, ly, st)
                return st
    sub = []
    va = proute.drop_via(bd, pa, net, pz, sub, radii=tuple(0.5 + 0.25 * i for i in range(10)), layer=side(la))
    vz = proute.drop_via(bd, pz, net, pa, sub, radii=tuple(0.5 + 0.25 * i for i in range(10)), layer=side(lz)) if va else None
    if va and vz:
        for ly in ('B.Cu', 'In2.Cu', 'F.Cu'):
            pts = bd.path(ly, va, vz, hw, {net}, CLR, margin=8.0, half_in=NECK / 2)
            if pts:
                stage(pts, net, ly, sub)
                return sub
    bd.unstage(sub)
    return None


def mst(ts):
    used, edges = {0}, []
    while len(used) < len(ts):
        best = min(((math.hypot(ts[i][1][0] - ts[j][1][0], ts[i][1][1] - ts[j][1][1]), i, j)
                    for i in used for j in range(len(ts)) if j not in used))
        edges.append(best[1:])
        used.add(best[2])
    return edges


open_legs = []
for net in ('/POWER/FB_1V0', '/POWER/SS_1V0', '+5V', '/POWER/PG_1V0', '/POWER/PG_5V'):
    ts = term[net]
    for i, j in mst(ts):
        c = comp(net)
        if c[i] == c[j]:
            continue
        s = leg(net, ts[i], ts[j])
        if s:
            bd.commit(s)
        else:
            open_legs.append((net, ts[i][0], ts[j][0]))
bd.save()
print('open legs:', open_legs)
