import math
import sys

import pcbnew

import proute
import rlib

# in-place move of the ethernet and usb phy groups to the bottom side beside the stm32.
# rips: the groups' old stitching, every route on nets that touch a group (except plane nets), and
# fmc/fpga nets with copper in the target areas (fpga dogbones kept). parts are packed one by one:
# the phy at its anchor, each passive as close as possible to the phy pin it serves, clear of other
# bottom parts, tht parts, vias and remaining b.cu copper. plane pads are stitched afterwards
PCB = sys.argv[1]
MM = 1e6
GROUPS = {
    'U17': dict(anchor=(171.5, 88.0), area=(158.8, 79.8, 184.5, 95.5),
                parts=['C105', 'C106', 'C107', 'C108', 'C109', 'C110', 'C111', 'FB4', 'R50', 'R51', 'R52', 'R53',
                       'R54', 'R55', 'R56', 'R57', 'R58', 'R59', 'Y4']),
    'U13': dict(anchor=(158.0, 120.0), area=(148.0, 114.5, 167.8, 126.2),
                parts=['C90', 'C91', 'C97', 'C98', 'C99', 'C100', 'C101', 'R44', 'R45', 'Y3']),
}
PAD_CLR = 0.2
# fmc copper stays and is packed around unless RIP_FMC=1
import os
RIP_FMC = os.environ.get('RIP_FMC') == '1'

b = pcbnew.LoadBoard(PCB)
fs = b.Footprints()
fps = {fs[i].GetReference(): fs[i] for i in range(len(fs))}
zs = b.Zones()
PLANES = {zs[i].GetNetname() for i in range(len(zs)) if zs[i].GetNetname()} | {'GND'}
key = lambda v: (round(v.x / MM, 3), round(v.y / MM, 3))
moving = [r for g, d in GROUPS.items() for r in [g] + d['parts']]
group_nets = set()
for r in moving:
    f = fps[r]
    group_nets |= {f.Pads()[k].GetNetname() for k in range(len(f.Pads()))}
group_nets -= PLANES | {''}


def inside(p, a, m=1.0):
    return a[0] - m < p[0] < a[2] + m and a[1] - m < p[1] < a[3] + m


u100 = fps['U100']
balls = {key(u100.Pads()[k].GetPosition()): u100.Pads()[k].GetNetname() for k in range(len(u100.Pads()))}
ts = b.Tracks()
items = [ts[i] for i in range(len(ts))]
# fmc/fpga nets with any copper in a target area
fmc_hit = set()
for t in items:
    n = t.GetNetname()
    if not n.startswith(('FMC_', 'FPGA_')):
        continue
    pts = [key(t.GetPosition())] if t.GetClass() == 'PCB_VIA' else [key(t.GetStart()), key(t.GetEnd())]
    if RIP_FMC and any(inside(p, d['area']) for p in pts for d in GROUPS.values()):
        fmc_hit.add(n)
keep, keep_via = set(), set()
for t in items:
    if t.GetClass() == 'PCB_VIA' or t.GetNetname() not in fmc_hit:
        continue
    for e, o in ((key(t.GetStart()), key(t.GetEnd())), (key(t.GetEnd()), key(t.GetStart()))):
        if balls.get(e) == t.GetNetname() and math.hypot(e[0] - o[0], e[1] - o[1]) < 1.2:
            keep.add(id(t))
            keep_via.add((t.GetNetname(), o))
# old stitching of the moving parts
old = set()
for r in moving:
    f = fps[r]
    old |= {key(f.Pads()[k].GetPosition()) for k in range(len(f.Pads()))}
stitch, stitch_via = set(), set()
for t in items:
    if t.GetClass() != 'PCB_VIA' and t.GetNetname() in PLANES:
        s, e = key(t.GetStart()), key(t.GetEnd())
        if s in old or e in old:
            stitch.add(id(t))
            stitch_via.add((t.GetNetname(), e if s in old else s))
rm = collections_count = {'phy nets': 0, 'fmc': 0, 'stitch': 0}
for t in items:
    n = t.GetNetname()
    if t.GetClass() == 'PCB_VIA':
        pos = (n, key(t.GetPosition()))
        if n in group_nets:
            rm['phy nets'] += 1
        elif n in fmc_hit and pos not in keep_via:
            rm['fmc'] += 1
        elif pos in stitch_via:
            rm['stitch'] += 1
        else:
            continue
    else:
        if n in group_nets:
            rm['phy nets'] += 1
        elif n in fmc_hit and id(t) not in keep:
            rm['fmc'] += 1
        elif id(t) in stitch:
            rm['stitch'] += 1
        else:
            continue
    b.Remove(t)
print('ripped', rm, '; fmc nets ripped (dogbones kept):', len(fmc_hit))

# obstacles for bottom placement: remaining vias and b.cu copper
ts = b.Tracks()
vias, bsegs = [], []
for i in range(len(ts)):
    t = ts[i]
    if t.GetClass() == 'PCB_VIA':
        vias.append((t.GetPosition().x / MM, t.GetPosition().y / MM, pcbnew.Cast_to_PCB_VIA(t).GetWidth(pcbnew.F_Cu) / MM / 2))
    elif t.GetLayer() == pcbnew.B_Cu:
        bsegs.append((t.GetStart().x / MM, t.GetStart().y / MM, t.GetEnd().x / MM, t.GetEnd().y / MM, t.GetWidth() / MM / 2))


def crt(f):
    c = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
    return (bb.GetLeft() / MM, bb.GetTop() / MM, bb.GetRight() / MM, bb.GetBottom() / MM)


def tht(f):
    return any(f.Pads()[k].GetAttribute() == pcbnew.PAD_ATTRIB_PTH for k in range(len(f.Pads())))


def hit(a, c, gap=0.35):
    return a[0] - gap < c[2] and a[2] + gap > c[0] and a[1] - gap < c[3] and a[3] + gap > c[1]


def segd(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    u = 0 if L2 == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - x1 - u * dx, py - y1 - u * dy)


placed_bottom = [f for r, f in fps.items() if (f.IsFlipped() or tht(f)) and r not in moving]


RING = 1.2
phy_boxes = []


def ok(f):
    r = crt(f)
    # routing channel around each phy: passives stay RING mm off its courtyard
    if f.GetReference() not in GROUPS and any(hit(r, pb, RING) for pb in phy_boxes):
        return False
    if r[0] < 51 or r[2] > 190 or r[1] < 54 or r[3] > 146:
        return False
    if any(hit(r, crt(o)) for o in placed_bottom if o.GetReference() not in GROUPS):
        return False
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        px, py = p.GetPosition().x / MM, p.GetPosition().y / MM
        pr = max(p.GetBoundingBox().GetWidth(), p.GetBoundingBox().GetHeight()) / MM / 2
        for (vx, vy, vr) in vias:
            if math.hypot(px - vx, py - vy) < pr + vr + PAD_CLR:
                return False
        for (x1, y1, x2, y2, hw) in bsegs:
            if segd(px, py, x1, y1, x2, y2) < pr + hw + PAD_CLR:
                return False
    return True


def place(f, x0, y0, rmax=14.0):
    if not f.IsFlipped():
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    for rad in [0.0] + [0.25 * i for i in range(1, int(rmax / 0.25))]:
        n = 1 if rad == 0 else max(8, int(2 * math.pi * rad / 0.25))
        for k in range(n):
            a = 2 * math.pi * k / n
            for rot in (0, 90, 180, 270):
                f.SetOrientationDegrees(rot)
                f.SetPosition(pcbnew.VECTOR2I(int((x0 + rad * math.cos(a)) * MM), int((y0 + rad * math.sin(a)) * MM)))
                if ok(f):
                    return (round(f.GetPosition().x / MM, 2), round(f.GetPosition().y / MM, 2), rot, rad)
    return None


report = {}
for g, d in GROUPS.items():
    phy = fps[g]
    got = place(phy, *d['anchor'], rmax=10.0)
    if not got:
        raise SystemExit('no room for ' + g)
    placed_bottom.append(phy)
    phy_boxes.append(crt(phy))
    report[g] = got
    pp = {phy.Pads()[k].GetNetname(): phy.Pads()[k].GetPosition() for k in range(len(phy.Pads()))}
    # passives nearest their phy pin; parts tied to more phy pins first
    order = sorted(d['parts'], key=lambda r: -sum(1 for k in range(len(fps[r].Pads())) if fps[r].Pads()[k].GetNetname() in pp))
    for r in order:
        f = fps[r]
        ns = [f.Pads()[k].GetNetname() for k in range(len(f.Pads()))]
        tgt = [pp[n] for n in ns if n in pp and n not in PLANES] or [pp[n] for n in ns if n in pp] or [phy.GetPosition()]
        tx = sum(v.x for v in tgt) / len(tgt) / MM
        ty = sum(v.y for v in tgt) / len(tgt) / MM
        got = place(f, tx, ty)
        if not got:
            raise SystemExit('no room for ' + r)
        placed_bottom.append(f)
        report[r] = got
b.Save(PCB)
far = {r: v for r, v in report.items() if v[3] > 4.0}
print('placed %d parts on the bottom; phys at %s / %s' % (len(report), report['U17'][:2], report['U13'][:2]))
print('passives more than 4 mm from their target:', far)

# stitch plane pads of the moved parts (bottom stub to a via)
bd = rlib.Board(PCB)
okc = fail = 0
for (x, y, hx, hy, n, lays, rnd, p) in list(bd.pads):
    if p.GetParentFootprint().GetReference() not in moving or n not in PLANES:
        continue
    st = []
    if proute.drop_via(bd, (x, y), n, (x, y + 1.0), st, radii=(0.5, 0.6, 0.75, 0.9, 1.1, 1.3, 1.6, 2.0), layer='B.Cu'):
        bd.commit(st)
        okc += 1
    else:
        bd.unstage(st)
        fail += 1
bd.save()
print('stitched %d plane pads, %d without room' % (okc, fail))
