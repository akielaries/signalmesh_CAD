import math
import sys

import proute
import rlib

# replace every off-angle track segment with a clear 0/45/90-degree dogleg (same width, layer, net).
# single-ended nets segment by segment; diff pairs get the same dogleg shape on both halves
PCB = sys.argv[1]
PREFIX = tuple(sys.argv[2].split(',')) if len(sys.argv) > 2 else ('DDR_', 'FMC_', 'FPGA_')
rlib.BGA_RECTS[:] = [(109.5, 79.5, 134.5, 104.5, 0.09), (120.8, 62.35, 179.3, 76.65, 0.10),
                     (105.455, 115.505, 121.545, 125.595, 0.09)]
bd = rlib.Board(PCB)


def off_angle(a, b_):
    ang = math.degrees(math.atan2(b_[1] - a[1], b_[0] - a[0])) % 45.0
    return min(ang, 45.0 - ang) > 0.5 and math.hypot(b_[0] - a[0], b_[1] - a[1]) > 0.02


def clr_of(net):
    return 0.15 if net.startswith('DDR_') else 0.127


ts = bd.b.Tracks()
todo = []
for i in range(len(ts)):
    t = ts[i]
    n = t.GetNetname()
    if t.GetClass() == 'PCB_VIA' or not n.startswith(PREFIX) or n.endswith(('_P', '_N')):
        # pairs are octilinear from the pair router (both halves must move together)
        continue
    ly = bd.b.GetLayerName(t.GetLayer())
    if ly not in rlib.LAYERS:
        continue
    a = (t.GetStart().x / 1e6, t.GetStart().y / 1e6)
    b_ = (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)
    if off_angle(a, b_):
        todo.append((t, n, ly, a, b_, t.GetWidth() / 1e6))
fixed = failed = 0
for (t, n, ly, a, b_, w) in todo:
    hw = w / 2
    key = [q for q in bd.tracks if q[5] == n and q[6] == ly and
           max(abs(q[0] - a[0]), abs(q[1] - a[1]), abs(q[2] - b_[0]), abs(q[3] - b_[1])) < 1e-6]
    for q in key:
        bd.tracks.remove(q)
    done = False
    for opt in rlib.octi_options(a, b_):
        if proute.segs_clear(bd, ly, opt, hw, {n}, clr_of(n)):
            st = []
            bd.stage_track(opt, w, n, ly, st)
            bd.commit(st)
            bd.b.Remove(t)
            done = True
            break
    if not done:
        # no single dogleg fits: re-route this stretch with the octilinear grid router, same layer
        rlib.TIGHT = True
        pts = bd.path(ly, a, b_, hw, {n}, clr_of(n), margin=1.5)
        if pts and not any(off_angle(p, q) for p, q in zip(pts, pts[1:])):
            st = []
            bd.stage_track(pts, w, n, ly, st)
            bd.commit(st)
            bd.b.Remove(t)
            done = True
    if done:
        fixed += 1
    else:
        bd.tracks.extend(key)
        failed += 1
bd.save()
print('off-angle segments: %d, made octilinear: %d, left (no clear dogleg): %d' % (len(todo), fixed, failed))
