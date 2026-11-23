import math
import sys

import pcbnew

import proute
import pslib

# give dogbone-less bga balls of open nets a cell by shifting a neighbour: when a diagonal cell of the ball
# holds another net's dogbone via whose own ball has a different free diagonal cell, that dogbone moves
# there (its stub and the tracks on the old via go; the net is re-routed afterwards) and the blocked ball
# takes the vacated cell. usage: shiftbones.py <board>
PCB = sys.argv[1]
MM = 1e6
r = pslib.Router(PCB, ['U11', 'U100'])
bd = r.bd
b = bd.b
zs = b.Zones()
planes = {zs[i].GetNetname() for i in range(len(zs)) if not zs[i].GetIsRuleArea()} | {'GND'}
moved, gave, graveyard = [], 0, []


def has_bone(n, x, y):
    return any(abs(t[0] - x) < 0.01 and abs(t[1] - y) < 0.01 or abs(t[2] - x) < 0.01 and abs(t[3] - y) < 0.01
               for t in bd.tracks if t[5] == n) or proute.existing_via(bd, (x, y), n, maxd=0.95)


def remove_at(n, q):
    # the via of n at q and every track of n ending on it
    ts = b.Tracks()
    kill = []
    for i in range(len(ts)):
        t = ts[i]
        if t.GetNetname() != n:
            continue
        pts = [t.GetPosition()] if t.GetClass() == 'PCB_VIA' else [t.GetStart(), t.GetEnd()]
        if any(abs(p.x / MM - q[0]) < 0.02 and abs(p.y / MM - q[1]) < 0.02 for p in pts):
            kill.append(t)
    for t in kill:
        b.Remove(t)
    graveyard.extend(kill)
    bd.reload()


def bone(n, ball, q):
    st = []
    bd.stage_track([ball, q], 0.1, n, 'F.Cu', st)
    bd.stage_via(q[0], q[1], n, st, d=0.4)
    bd.commit(st)


for ref, h in (('U11', 0.4), ('U100', 0.5)):
    f = b.FindFootprintByReference(ref)
    balls = {}
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        balls.setdefault(p.GetNetname(), []).append((p.GetPosition().x / MM, p.GetPosition().y / MM))
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        n = p.GetNetname()
        if not n or n.startswith('unconnected') or n in planes:
            continue
        x, y = p.GetPosition().x / MM, p.GetPosition().y / MM
        if has_bone(n, x, y):
            continue
        ts = r.terms(n)
        if len(ts) < 2 or len(set(r.comp(n, ts))) == 1:
            continue
        done = False
        for sx in (-1, 1):
            for sy in (-1, 1):
                c = (x + sx * h, y + sy * h)
                occ = [(vx, vy, vn) for (vx, vy, vr, vn) in bd.vias if vn != n and math.hypot(vx - c[0], vy - c[1]) < 0.05]
                if len(occ) != 1 or occ[0][2] in planes:
                    continue
                m = occ[0][2]
                # the neighbour's ball this via serves, and its other cells
                mb = [q for q in balls.get(m, []) if abs(math.hypot(q[0] - c[0], q[1] - c[1]) - h * math.sqrt(2)) < 0.02]
                if not mb:
                    continue
                mx, my = mb[0]
                alt = [(mx + ax * h, my + ay * h) for ax in (-1, 1) for ay in (-1, 1)]
                alt = [q for q in alt if math.hypot(q[0] - c[0], q[1] - c[1]) > 0.05 and proute.via_spot_exact(bd, q[0], q[1], m)]
                if not alt:
                    continue
                remove_at(m, c)
                if not proute.via_spot_exact(bd, c[0], c[1], n) or not proute.via_spot_exact(bd, alt[0][0], alt[0][1], m):
                    continue
                bone(m, (mx, my), alt[0])
                bone(n, (x, y), c)
                moved.append(m)
                gave += 1
                done = True
                break
            if done:
                break
bd.save()
print('balls given a dogbone: %d; neighbours shifted: %s' % (gave, ' '.join(sorted(set(moved)))))
