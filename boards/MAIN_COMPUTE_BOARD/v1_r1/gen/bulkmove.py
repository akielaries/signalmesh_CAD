import sys

import pcbnew

import proute
import pslib

# FPGA VCCINT bulk caps C119 (330 uF polymer) and C134 (100 uF): onto the +1V0 pour west of the FPGA
# (C119 sat by the vita connector off any +1V0 copper, C134 4 mm off the pour edge), each pad with a
# 0.5 mm stub and a via to its plane
PCB = sys.argv[1]
SPOTS = {'C119': (105.0, 90.0, 90), 'C134': (100.75, 92.0, 90)}
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
print('ripped %d old stitching items' % P.rip(list(SPOTS)))
for ref, (x, y, rot) in SPOTS.items():
    f = P.fps[ref]
    if f.IsFlipped():
        f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    f.SetOrientationDegrees(rot)
    f.SetPosition(pslib.V(x, y))
    print(ref, 'at', (x, y), 'fits:', P.ok(f), 'pads', P.pads(ref))
b.Save(PCB)
r = pslib.Router(PCB, [])
bd = r.bd
fails = []
for (x, y, hx, hy, n, lays, rnd, p) in list(bd.pads):
    if p.GetParentFootprint().GetReference() not in SPOTS or n not in ('+1V0', 'GND'):
        continue
    st = []
    if proute.drop_via(bd, (x, y), n, (x + (1.5 if n == 'GND' else -1.5), y), st, w=0.5,
                       radii=(0.9, 1.1, 1.3, 1.6, 2.0, 2.4), layer='F.Cu'):
        bd.commit(st)
    else:
        bd.unstage(st)
        fails.append(p.GetParentFootprint().GetReference() + ':' + p.GetNumber())
bd.save()
print('vias placed; no room for:', fails)
