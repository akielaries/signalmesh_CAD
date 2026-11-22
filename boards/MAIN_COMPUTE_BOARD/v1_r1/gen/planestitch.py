import math
import sys

import pcbnew

import proute
import pslib

# plane hookups: smd pads on plane nets with no copper of their own (no track end or via on the pad,
# not sitting in a same-net pour on their layer) get a short stub and a via down to the plane. fine-pitch
# parts and the areas the user routes by hand (ddr, fpga, stm32 edges, vita) are left alone.
# usage: planestitch.py <board> [--dry]
PCB = sys.argv[1]
DRY = '--dry' in sys.argv
MM = 1e6
ALL = '--all' in sys.argv     # include the dense areas (bga fields, ddr, la gap), with necked stubs there
r = pslib.Router(PCB, ['U100', 'U11', 'U21'] if ALL else [])
bd = r.bd
b = bd.b
zs = b.Zones()
planes = ({zs[i].GetNetname() for i in range(len(zs)) if zs[i].GetNetname()} | {'GND'}) - {'+12V', '+12V_JACK'}
# where each plane net actually has copper on an inner layer: a via must land inside one of these
inner = {}
for i in range(len(zs)):
    z = zs[i]
    if any(l not in (pcbnew.F_Cu, pcbnew.B_Cu) for l in z.GetLayerSet().Seq()):
        inner.setdefault(z.GetNetname(), []).append(z)
# a via must land on filled copper of its plane (inside the outline is not enough: voids and other rails)
pcbnew.ZONE_FILLER(b).Fill([zs[i] for i in range(len(zs))])
zs = b.Zones()
inner = {}
for i in range(len(zs)):
    z = zs[i]
    if any(l not in (pcbnew.F_Cu, pcbnew.B_Cu) for l in z.GetLayerSet().Seq()):
        inner.setdefault(z.GetNetname(), []).append(z)
reaches = lambda n, x, y: any(z.HitTestFilledArea(l, pcbnew.VECTOR2I(int(x * MM), int(y * MM)), int(0.1 * MM))
                              for z in inner.get(n, []) for l in z.GetLayerSet().Seq() if l not in (pcbnew.F_Cu, pcbnew.B_Cu))
skip_refs = [] if ALL else ['U100', 'U11', 'J20', 'U17', 'U13'] + [f.GetReference() for f in b.Footprints() if f.GetValue().startswith('MT41K')]
dense = []
for ref in skip_refs:
    bb = b.FindFootprintByReference(ref).GetBoundingBox(False)
    dense.append((bb.GetLeft() / MM - 1.0, bb.GetTop() / MM - 1.0, bb.GetRight() / MM + 1.0, bb.GetBottom() / MM + 1.0))
if not ALL:
    dense.append((95.0, 94.0, 125.0, 135.5))      # ddr escape and fly-by area
    dense.append((109.0, 74.0, 181.0, 80.0))      # la gap between the vita connector and the fpga
in_dense = lambda x, y: any(x0 < x < x1 and y0 < y < y1 for x0, y0, x1, y1 in dense)
# same-net copper per net
ends = {}
for (xa, ya, xb, yb, hw, n, ly) in bd.tracks:
    ends.setdefault(n, []).extend([(xa, ya, ly), (xb, yb, ly)])
vias = {}
for (vx, vy, vr, n) in bd.vias:
    vias.setdefault(n, []).append((vx, vy))
pour = {}
for i in range(len(zs)):
    z = zs[i]
    for l in z.GetLayerSet().Seq():
        if l in (pcbnew.F_Cu, pcbnew.B_Cu):
            pour.setdefault((z.GetNetname(), b.GetLayerName(l)), []).append(z)
cands = []
for (x, y, hx, hy, n, lays, rnd, p) in bd.pads:
    if n not in planes or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
        continue
    ly = 'B.Cu' if 'B.Cu' in lays else 'F.Cu'
    ref = p.GetParentFootprint().GetReference()
    if ref in skip_refs or in_dense(x, y):
        continue
    # ground pins of parts whose exposed pad already reaches the plane through its own thermal vias
    fpp = p.GetParentFootprint()
    if any(fpp.Pads()[k].GetNetname() == n and fpp.Pads()[k].GetAttribute() == pcbnew.PAD_ATTRIB_PTH
           for k in range(len(fpp.Pads()))):
        continue
    onpad = lambda q: abs(q[0] - x) <= hx + 0.05 and abs(q[1] - y) <= hy + 0.05
    if any(onpad(e) and e[2] == ly for e in ends.get(n, [])) or any(onpad(v) for v in vias.get(n, [])):
        continue
    if any(z.HitTestFilledArea(b.GetLayerID(ly), pcbnew.VECTOR2I(int(x * MM), int(y * MM))) for z in pour.get((n, ly), [])):
        continue
    cands.append((ref, p.GetNumber(), n, x, y, ly))
by = {}
for c in cands:
    by[c[2]] = by.get(c[2], 0) + 1
print('orphan plane pads outside the hand-routed areas: %d %s' % (len(cands), dict(sorted(by.items(), key=lambda kv: -kv[1]))))
if DRY:
    sys.exit(0)
ok, fail = 0, []
for ref, num, n, x, y, ly in cands:
    st = []
    v = proute.drop_via(bd, (x, y), n, (x, y + 1.0), st, w=0.3, radii=(0.55, 0.65, 0.8, 0.95, 1.1, 1.3, 1.6), layer=ly)
    if not v and ALL:
        # fine search: any exact via spot within 3 mm the pad reaches on its own layer with a necked stub
        bd.unstage(st)
        st = []
        spots = sorted(((x + dx * 0.25, y + dy * 0.25) for dx in range(-12, 13) for dy in range(-12, 13) if 0.4 < math.hypot(dx * 0.25, dy * 0.25) <= 3.0),
                       key=lambda q: math.hypot(q[0] - x, q[1] - y))
        for q in spots:
            if reaches(n, q[0], q[1]) and proute.via_spot_exact(bd, q[0], q[1], n, r=0.2, clr=0.127):
                pts = bd.path(ly, (x, y), q, 0.075, {n}, 0.15, margin=1.0, half_in=0.05)
                if pts:
                    r.stage(pts, n, 0.15, ly, st)
                    bd.stage_via(q[0], q[1], n, st, d=0.4)
                    v = q
                    break
    if v and reaches(n, v[0], v[1]):
        bd.commit(st)
        ok += 1
    elif v:
        bd.unstage(st)
        fail.append('%s:%s(outside %s pour)' % (ref, num, n))
    else:
        bd.unstage(st)
        fail.append('%s:%s' % (ref, num))
bd.save()
print('stitched %d, no room for %d: %s' % (ok, len(fail), ' '.join(fail[:40])))
