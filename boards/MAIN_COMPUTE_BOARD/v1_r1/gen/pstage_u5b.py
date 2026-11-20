import sys

import proute
import rlib

# U5 power stage, second pass: the 5 V feed (C10/PVIN via -> L1, the 5 V buck output), FSW pin 7,
# and PG_5V (U5 enable) between R7, TP15's via and U2. vias at known spots, In2 between them
PCB = sys.argv[1]
rlib.BGA_RECTS[:] = []
proute.ESC[:] = []
rlib.TIGHT = True
bd = rlib.Board(PCB)
R = tuple(0.5 + 0.25 * i for i in range(12))


def pad(ref, num):
    for (x, y, hx, hy, n, lays, rnd, p) in bd.pads:
        if p.GetParentFootprint().GetReference() == ref and p.GetNumber() == num:
            return (x, y), n


def run(name, a, z, net, w, ly='In2.Cu', a_pad=False, z_pad=False):
    st = []
    if a_pad:
        a = proute.drop_via(bd, a, net, z, st, radii=R)
    if a and z_pad:
        z = proute.drop_via(bd, z, net, a, st, radii=R)
    pts = bd.path(ly, a, z, w / 2, {net}, 0.15, margin=10.0) if a and z else None
    if pts:
        bd.stage_track(pts, w, net, ly, st)
        bd.commit(st)
        print('%-18s ok (%.1f mm on %s)' % (name, sum(((q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2) ** 0.5 for p, q in zip(pts, pts[1:])), ly))
    else:
        bd.unstage(st)
        print('%-18s OPEN' % name)


l1, _ = pad('L1', '2')
run('5V feed -> L1', (94.15, 109.55), l1, '+5V', 0.5, z_pad=True)
p7, _ = pad('U5', '7')
run('FSW pin 7', p7, (94.15, 109.55), '+5V', 0.15, a_pad=True)
r7, _ = pad('R7', '1')
run('PG_5V R7 -> TP15', r7, (87.55, 112.25), '/POWER/PG_5V', 0.15, a_pad=True)
u2, _ = pad('U2', '4')
run('PG_5V U2 -> R7', u2, r7, '/POWER/PG_5V', 0.15, a_pad=True, z_pad=True)
bd.save()
