import math
import sys

import pcbnew

import proute
import pslib

# B.Cu reclaim, second pass: the +12V pads that only the old full-board pour reached. pads near a
# regulator join its 12 V copper; off-strip loads get a via inside the pour and a trace to it
PCB = sys.argv[1]
r = pslib.Router(PCB, ['U4', 'U7'])
bd = r.bd
T = r.terms
zs = bd.b.Zones()
z = [zs[i] for i in range(len(zs)) if zs[i].GetNetname() == '+12V' and zs[i].GetLayer() == pcbnew.B_Cu][0]
outline = z.Outline()


def in_pour(x, y, m=0.6):
    # inside the zone outline with margin to its edge
    return all(outline.Contains(pcbnew.VECTOR2I(int((x + dx) * 1e6), int((y + dy) * 1e6)))
               for dx, dy in ((m, 0), (-m, 0), (0, m), (0, -m)))


def pour_via_near(p):
    for rad in [0.5 * i for i in range(1, 60)]:
        m = max(8, int(2 * math.pi * rad / 0.5))
        best = None
        for k in range(m):
            x, y = p[0] + rad * math.cos(2 * math.pi * k / m), p[1] + rad * math.sin(2 * math.pi * k / m)
            if in_pour(x, y) and proute.via_spot_ok(bd, x, y, '+12V'):
                best = (x, y)
                break
        if best:
            st = []
            bd.stage_via(best[0], best[1], '+12V', st)
            bd.commit(st)
            return best
    return None


# near a regulator: to that regulator's 12 V copper
r.net('+12V', T('+12V', {'U4', 'C20', 'C21', 'R3'}), 0.3)
r.net('+12V', T('+12V', {'U7', 'C35', 'C36'}), 0.3)
# off-strip loads: a via inside the pour, then a trace
for ref, w in (('F2', 0.8), ('R35', 0.25), ('TP2', 0.3)):
    pad = T('+12V', {ref})[0]
    v = pour_via_near(pad[1])
    if not v:
        r.open.append(('+12V', ref, 'no pour via'))
        continue
    r.net('+12V', [pad, r.via_term(v)], w, inner=('In2.Cu', 'In5.Cu'))
    print('%s: pour via at (%.2f, %.2f), %.1f mm away' % (ref, v[0], v[1], math.hypot(v[0] - pad[1][0], v[1] - pad[1][1])))
bd.save()
print('open:', r.open)
