import math
import sys

import pcbnew

import proute
import rlib

# power stage of U6 (TPS62130, 5 V -> +1V8). U6 is turned 180 deg and moved 2 mm east so its switch
# pins face the free space east instead of U5; L5 and the output caps go there. the input cap C30 sits
# on the bottom under the PVIN pins (as C10 under U5), C31 (100 nF) on top in the U5/U6 gap. fb, ss
# and the rest are placed beside their pins, then everything is routed
PCB = sys.argv[1]
MM = 1e6
V = lambda x, y: pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM)))
key = lambda v: (round(v.x / MM, 3), round(v.y / MM, 3))
b = pcbnew.LoadBoard(PCB)
fps = {}
fs = b.Footprints()
for i in range(len(fs)):
    fps[fs[i].GetReference()] = fs[i]
GROUP = ['U6', 'L5', 'C29', 'C30', 'C31', 'C32', 'C33', 'R17', 'R18']
LOCAL = {'/POWER/SW_1V8', '/POWER/FB_1V8', '/POWER/SS_1V8'}

# 1) rip: old stitching of the group, routes of U6's local nets, and the PG_1V0 copper that U6's new
# body would sit on (the via beside the old EN pin)
old = set()
for r in GROUP:
    f = fps[r]
    old |= {key(f.Pads()[k].GetPosition()) for k in range(len(f.Pads()))}
ts = b.Tracks()
items = [ts[i] for i in range(len(ts))]
vias, kill = set(), []
for t in items:
    n = t.GetNetname()
    if n in LOCAL:
        kill.append(t)
        continue
    if t.GetClass() != 'PCB_VIA':
        s, e = key(t.GetStart()), key(t.GetEnd())
        if s in old or e in old:
            kill.append(t)
            vias.add((n, e if s in old else s))
for t in items:
    if t.GetClass() == 'PCB_VIA' and (t.GetNetname(), key(t.GetPosition())) in vias:
        kill.append(t)
# PG_1V0 near the old EN pin: the via at (98.25, 110.54) and copper ending on it
pgv = (98.25, 110.54)
for t in items:
    if t.GetNetname() != '/POWER/PG_1V0':
        continue
    pts = [key(t.GetPosition())] if t.GetClass() == 'PCB_VIA' else [key(t.GetStart()), key(t.GetEnd())]
    if any(math.hypot(p[0] - pgv[0], p[1] - pgv[1]) < 0.6 for p in pts):
        kill.append(t)
seen = set()
for t in kill:
    if id(t) not in seen:
        seen.add(id(t))
        b.Remove(t)
print('ripped %d items' % len(seen))

# 2) fixed placements
u6 = fps['U6']
u6.SetOrientationDegrees(180)
u6.SetPosition(V(99.0, 112.0))
l5 = fps['L5']
l5.SetOrientationDegrees(0)
l5.SetPosition(V(103.6, 110.8))
c30 = fps['C30']
if not c30.IsFlipped():
    c30.Flip(c30.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
for rot in (90, 270):
    c30.SetOrientationDegrees(rot)
    c30.SetPosition(V(97.0, 111.6))
    pp = {c30.Pads()[k].GetNumber(): c30.Pads()[k].GetPosition() for k in range(2)}
    if pp['1'].y > pp['2'].y:      # +5V pad south, next to the PVIN pins' via
        break
c5 = (pp['1'].x / MM, pp['1'].y / MM)
cg = (pp['2'].x / MM, pp['2'].y / MM)
c31 = fps['C31']
c31.SetOrientationDegrees(90)
c31.SetPosition(V(95.5, 111.9))
pin = {u6.Pads()[k].GetNumber(): (u6.Pads()[k].GetPosition().x / MM, u6.Pads()[k].GetPosition().y / MM)
       for k in range(len(u6.Pads())) if u6.Pads()[k].GetNumber()}
lp = {l5.Pads()[k].GetNumber(): (l5.Pads()[k].GetPosition().x / MM, l5.Pads()[k].GetPosition().y / MM) for k in range(2)}
print('U6 pins: SW %s %s %s, PVIN %s %s %s, FB %s, SS %s, VOS %s, EN %s, PG %s, FSW %s' % tuple(
    pin[n] for n in ('1', '2', '3', '10', '11', '12', '5', '9', '14', '13', '4', '7')))
print('L5 pads', lp, '; C30 +5V', c5, 'GND', cg)

# 3) the rest beside their pins: same side courtyards (+ tht), pads clear of other vias/tracks
ts = b.Tracks()
obst_v, obst_t = [], []
for i in range(len(ts)):
    t = ts[i]
    if t.GetClass() == 'PCB_VIA':
        obst_v.append((t.GetPosition().x / MM, t.GetPosition().y / MM, pcbnew.Cast_to_PCB_VIA(t).GetWidth(pcbnew.F_Cu) / MM / 2))
    elif t.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
        obst_t.append((t.GetLayer(), t.GetStart().x / MM, t.GetStart().y / MM, t.GetEnd().x / MM, t.GetEnd().y / MM, t.GetWidth() / MM / 2))


def crt(f):
    c = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
    bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
    return (bb.GetLeft() / MM, bb.GetTop() / MM, bb.GetRight() / MM, bb.GetBottom() / MM)


def tht(f):
    return any(f.Pads()[k].GetAttribute() == pcbnew.PAD_ATTRIB_PTH for k in range(len(f.Pads())))


def hit(a, c, g=0.15):
    return a[0] - g < c[2] and a[2] + g > c[0] and a[1] - g < c[3] and a[3] + g > c[1]


def segd(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    u = 0 if L2 == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - x1 - u * dx, py - y1 - u * dy)


def ok(f):
    r = crt(f)
    for o in fps.values():
        if o.GetReference() != f.GetReference() and (o.IsFlipped() == f.IsFlipped() or tht(o)) and hit(r, crt(o)):
            return False
    lay = pcbnew.B_Cu if f.IsFlipped() else pcbnew.F_Cu
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        px, py = p.GetPosition().x / MM, p.GetPosition().y / MM
        pr = max(p.GetBoundingBox().GetWidth(), p.GetBoundingBox().GetHeight()) / MM / 2
        if any(math.hypot(px - vx, py - vy) < pr + vr + 0.15 for vx, vy, vr in obst_v):
            return False
        if any(l == lay and segd(px, py, x1, y1, x2, y2) < pr + hw + 0.15 for l, x1, y1, x2, y2, hw in obst_t):
            return False
    return True


def place(ref, tx, ty, rmax=6.0):
    f = fps[ref]
    if f.IsFlipped():
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    for rad in [0.25 * i for i in range(0, int(rmax / 0.25))]:
        n = 1 if rad == 0 else max(8, int(2 * math.pi * rad / 0.25))
        for k in range(n):
            a = 2 * math.pi * k / n
            for rot in (0, 90, 180, 270):
                f.SetOrientationDegrees(rot)
                f.SetPosition(V(tx + rad * math.cos(a), ty + rad * math.sin(a)))
                if ok(f):
                    return (round(f.GetPosition().x / MM, 2), round(f.GetPosition().y / MM, 2), rot, rad)
    raise SystemExit('no room for ' + ref)


for r in ('U6', 'L5', 'C30', 'C31'):
    if not ok(fps[r]):
        print('WARNING fixed placement of %s collides' % r)
got = {}
got['C32'] = place('C32', lp['2'][0], lp['2'][1] + 3.6)
got['C33'] = place('C33', lp['2'][0] - 1.5, lp['2'][1] - 3.4)
got['R18'] = place('R18', pin['5'][0] + 0.9, pin['5'][1] - 1.8)
got['R17'] = place('R17', pin['5'][0] + 0.9, pin['5'][1] - 3.0)
got['C29'] = place('C29', pin['9'][0] - 1.6, pin['9'][1] - 1.6)
print('placed', got)
b.Save(PCB)
