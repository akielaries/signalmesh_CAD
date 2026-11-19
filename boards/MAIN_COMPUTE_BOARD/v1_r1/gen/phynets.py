import math
import sys

import pcbnew

import proute
import rlib

# routes every net of the moved phy groups (phymove.py): the mdi and usb hs pairs first, then the
# stm32 <-> phy buses, then the phy-local nets. each net is split into legs by a minimum spanning tree;
# a leg goes direct on a shared outer layer, or through one or two vias (stub on the pad's own layer).
# additive: legs already connected are skipped
PCB = sys.argv[1]
rlib.BGA_RECTS[:] = []
proute.ESC[:] = []
rlib.TIGHT = True
CLR = 0.127
SIG = {'F.Cu': 0.127, 'B.Cu': 0.127, 'In2.Cu': 0.23, 'In5.Cu': 0.23}
PWR = {'F.Cu': 0.3, 'B.Cu': 0.3, 'In2.Cu': 0.3, 'In5.Cu': 0.3}
POWER_NETS = {'ETH_AVDD', 'ETH_VDDCR', '/MCU_IO/ULPI_1V8', '/MCU_IO/ULPI_1V8A', 'VBUS_HS'}
GROUP = ['U17', 'C105', 'C106', 'C107', 'C108', 'C109', 'C110', 'C111', 'FB4', 'R50', 'R51', 'R52', 'R53', 'R54',
         'R55', 'R56', 'R57', 'R58', 'R59', 'Y4', 'U13', 'C90', 'C91', 'C97', 'C98', 'C99', 'C100', 'C101', 'R44',
         'R45', 'Y3']
PAIRS = [('/MCU_IO/ETH_TXP', '/MCU_IO/ETH_TXN', 'U17', 'J10'), ('/MCU_IO/ETH_RXP', '/MCU_IO/ETH_RXN', 'U17', 'J10'),
         ('USBHS_DP', 'USBHS_DM', 'U13', 'U14')]
OUTER = tuple(0.5 + 0.25 * i for i in range(20))

bd = rlib.Board(PCB)


def esc_box(ref, m):
    bb = bd.b.FindFootprintByReference(ref).GetBoundingBox(False)
    return (bb.GetLeft() / 1e6 - m, bb.GetTop() / 1e6 - m, bb.GetRight() / 1e6 + m, bb.GetBottom() / 1e6 + m, 0.09)


# 0.5 mm pitch parts: neck to 0.1 mm / 0.09 mm clearance inside these boxes (as the fpga escape)
rlib.BGA_RECTS[:] = [esc_box('U13', 0.6), esc_box('U17', 0.6), esc_box('U11', 0.3)]
proute.ESC[:] = [r[:4] for r in rlib.BGA_RECTS]
NECK = 0.1
zs = bd.b.Zones()
PLANES = {zs[i].GetNetname() for i in range(len(zs)) if zs[i].GetNetname()} | {'GND'}
term = {}
for (x, y, hx, hy, n, lays, rnd, p) in bd.pads:
    if n:
        term.setdefault(n, []).append((p.GetParentFootprint().GetReference(), (x, y), lays))
nets = sorted({n for n, ts in term.items() if any(r in GROUP for r, _, _ in ts)} - PLANES)


def comp(net):
    # connected groups of terminals via existing copper (ends snapped within 0.06 mm, vias join)
    pts = [t[1] for t in term[net]]
    segs = [(xa, ya, xb, yb, hw) for (xa, ya, xb, yb, hw, n, ly) in bd.tracks if n == net]
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
    for j, s in enumerate(segs):
        par[fd(base + j)] = fd(base + len(segs) + j)
    # pads: anything ending inside the pad joins it
    for i, (r, (x, y), lays) in enumerate(term[net]):
        for j in range(len(pts), len(nodes)):
            if math.hypot(nodes[j][0] - x, nodes[j][1] - y) < 0.3:
                par[fd(i)] = fd(j)
    return [fd(i) for i in range(len(pts))]


def width(net, ly):
    return (PWR if net in POWER_NETS else SIG)[ly]


def side(lays):
    return 'F.Cu' if 'F.Cu' in lays and 'B.Cu' not in lays else ('B.Cu' if 'B.Cu' in lays and 'F.Cu' not in lays else None)


def stage(pts, net, ly, st):
    for seg, inside in rlib.split_neck(pts):
        bd.stage_track(seg, NECK if inside else width(net, ly), net, ly, st)


def path(ly, a, b_, net, margin):
    return bd.path(ly, a, b_, width(net, ly) / 2, {net}, CLR, margin=margin, half_in=NECK / 2)


def leg(net, a, b_):
    (ra, pa, la), (rb, pb, lb) = a, b_
    st = []
    # direct on a shared outer layer
    for ly in ('B.Cu', 'F.Cu'):
        if ly in la and ly in lb:
            pts = path(ly, pa, pb, net, 6.0)
            if pts:
                stage(pts, net, ly, st)
                return st, ly
    sa, sb = side(la) or 'F.Cu', side(lb) or 'F.Cu'
    # one via at the end not on the other's layer
    for (p0, l0, p1, l1) in ((pa, sa, pb, lb), (pb, sb, pa, la)):
        for ly in ('B.Cu', 'F.Cu'):
            if ly in l1 and ly != l0:
                sub = []
                v = proute.drop_via(bd, p0, net, p1, sub, radii=OUTER, layer=l0)
                if v:
                    pts = path(ly, v, p1, net, 8.0)
                    if pts:
                        stage(pts, net, ly, sub)
                        return sub, ly
                bd.unstage(sub)
    # vias at both ends, inner layer (or the far outer layer)
    sub = []
    va = proute.drop_via(bd, pa, net, pb, sub, radii=OUTER, layer=sa)
    vb = proute.drop_via(bd, pb, net, pa, sub, radii=OUTER, layer=sb) if va else None
    if va and vb:
        for ly in ('In5.Cu', 'In2.Cu', 'B.Cu', 'F.Cu'):
            pts = path(ly, va, vb, net, 30.0)
            if pts:
                stage(pts, net, ly, sub)
                return sub, ly
    bd.unstage(sub)
    return None, None


# 2) every net leg by leg (pairs: only their remaining stubs)
report = []


def mst(ts):
    used, edges = {0}, []
    while len(used) < len(ts):
        best = min(((math.hypot(ts[i][1][0] - ts[j][1][0], ts[i][1][1] - ts[j][1][1]), i, j)
                    for i in used for j in range(len(ts)) if j not in used))
        edges.append(best[1:])
        used.add(best[2])
    return edges


def prio(n):
    return 0 if n.startswith(('ETH_', 'ULPI_')) else 1


def route_nets(sel):
    for net in sorted(sel, key=lambda n: len(term[n])):
        ts = term[net]
        for i, j in mst(ts):
            c = comp(net)
            if c[i] == c[j]:
                continue
            s, ly = leg(net, ts[i], ts[j])
            if s:
                bd.commit(s)


# local nets first (crystals, straps, bias, decaps, terminations), then the long pairs, then the buses
local = [n for n in nets if not n.startswith(('ETH_', 'ULPI_')) or n in POWER_NETS]
local = [n for n in local if n not in ('USBHS_DP', 'USBHS_DM', 'VBUS_HS')]
route_nets([n for n in local if not any(n in pr[:2] for pr in PAIRS)])
# 1) pairs: phy -> connector (or esd part), on whatever layer works
pair_nets = set()
for p, n, ra, rb in PAIRS:
    pair_nets |= {p, n}
    tp = {r: (pos, lays) for r, pos, lays in term[p]}
    tn = {r: (pos, lays) for r, pos, lays in term[n]}
    # nearest p/n pad pair on the far part (usb esd part has two of each)
    ep = min([t for t in term[p] if t[0] == rb], key=lambda t: math.hypot(t[1][0] - tp[ra][0][0], t[1][1] - tp[ra][0][1]))
    en = min([t for t in term[n] if t[0] == rb], key=lambda t: math.hypot(t[1][0] - ep[1][0], t[1][1] - ep[1][1]))
    cp, cn = comp(p), comp(n)
    ip = [i for i, t in enumerate(term[p]) if t[0] == ra][0]
    jp = term[p].index(ep)
    if cp[ip] == cp[jp]:
        continue
    s, l = proute.route_pair_any(bd, p, n, tp[ra][0], tn[ra][0], ep[1], en[1], 0.15,
                                 layers=('B.Cu', 'In2.Cu', 'In5.Cu', 'F.Cu'),
                                 s_layers=tuple(sorted(tp[ra][1] & {'F.Cu', 'B.Cu'})) or ('F.Cu',),
                                 e_layers=tuple(sorted(ep[2] & {'F.Cu', 'B.Cu'}, reverse=True)) or ('F.Cu',))
    if s:
        bd.commit(s)
        report.append(('pair', p[-8:] + '/' + n[-3:], l[0]))
    else:
        report.append(('pair', p[-8:] + '/' + n[-3:], 'OPEN'))


route_nets([n for n in nets if n.startswith(('ETH_', 'ULPI_')) and n not in POWER_NETS])
route_nets([n for n in nets if not any(n in pr[:2] for pr in PAIRS)])
open_legs = []
for net in nets:
    ts = term[net]
    c = comp(net)
    for i, j in mst(ts):
        if c[i] != c[j]:
            open_legs.append((net, ts[i][0], ts[j][0]))
bd.save()
for r in report:
    print(r)
done_nets = [n for n in nets if len(set(comp(n))) == 1]
print('phy nets: %d of %d fully connected' % (len(done_nets), len(nets)))
print('open legs:', open_legs)
