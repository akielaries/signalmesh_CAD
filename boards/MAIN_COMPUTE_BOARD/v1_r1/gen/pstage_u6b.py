import sys

import pcbnew

import pslib
from pslib import track, via

# U6 power stage, routing (after pstage_u6.py placed the group): hot loop and switch node by explicit
# geometry, then the 5 V tie-in, output, vos, fb, ss, fsw, enable/power-good chains and stitching
PCB = sys.argv[1]
MM = 1e6
b = pcbnew.LoadBoard(PCB)
F, B = pcbnew.F_Cu, pcbnew.B_Cu
# L5 a touch further east (courtyard margin to U6)
l5 = b.FindFootprintByReference('L5')
l5.SetPosition(pslib.V(103.8, 110.8))
# PG_1V0's old via sits under L5: rip that net and route it again below
ts = b.Tracks()
k = [ts[i] for i in range(len(ts)) if ts[i].GetNetname() == '/POWER/PG_1V0']
for t in k:
    b.Remove(t)
print('PG_1V0 ripped (%d items)' % len(k))

# hot loop: PVIN pins 10-12 (x 97.54) joined, down to a via, C30 +5V pad (bottom, south); C30 GND
# pad to the exposed-pad thermal via
track(b, (97.3, 111.75), (97.3, 112.75), 0.25, '+5V', F)
track(b, (97.3, 112.75), (97.3, 113.6), 0.4, '+5V', F)
via(b, (97.3, 113.6), '+5V')
track(b, (97.3, 113.6), (97.3, 112.9), 0.5, '+5V', B)
track(b, (97.0, 110.65), (97.76, 111.41), 0.5, 'GND', B)
track(b, (97.76, 111.41), (98.41, 111.41), 0.5, 'GND', B)
# 5 V tie-in to the U5 -> L1 feed that passes just south-west
track(b, (97.3, 113.6), (96.37, 114.53), 0.5, '+5V', F)
track(b, (96.37, 114.53), (96.01, 114.53), 0.5, '+5V', F)
# FSW (pin 7, north) to 5 V: a via just north of the pin
track(b, (98.75, 110.54), (98.75, 109.75), 0.15, '+5V', F)
via(b, (98.75, 109.75), '+5V')
# switch node: pins 1-3 (x 100.46) joined, 0.9 mm into L5 pin 1
track(b, (100.75, 111.75), (100.75, 112.75), 0.25, '/POWER/SW_1V8', F)
track(b, (100.75, 112.25), (102.5, 112.25), 0.9, '/POWER/SW_1V8', F)
b.Save(PCB)

r = pslib.Router(PCB, ['U6', 'U5', 'U8'])
r.keepout_courtyards(['L1', 'L4', 'L5', 'L7'])
G = ['U6', 'L5', 'C29', 'C30', 'C31', 'C32', 'C33', 'R17', 'R18']
# output: L5 pin 2 to both output caps, wide; vos, the divider top and the test point thin
r.net('+1V8', r.terms('+1V8', {'L5', 'C32', 'C33'}), 0.8)
r.net('+1V8', r.terms('+1V8', {'L5', 'C32', 'C33', 'U6', 'R17', 'TP6'}), 0.2)
r.net('/POWER/FB_1V8', r.terms('/POWER/FB_1V8'), 0.15)
r.net('/POWER/SS_1V8', r.terms('/POWER/SS_1V8'), 0.15)
# C31 (100 nF) onto the PVIN strip, FSW pin 7 to 5 V
r.net('+5V', r.terms('+5V', {'U6', 'C31'}), 0.3)
# FSW via down to the hot-loop 5 V via, on In2
st = []
pts = r.bd.path('In2.Cu', (98.75, 109.75), (97.3, 113.6), 0.075, {'+5V'}, 0.15, margin=4.0)
if pts:
    r.bd.stage_track(pts, 0.15, '+5V', 'In2.Cu', st)
    r.bd.commit(st)
else:
    r.open.append(('+5V', 'FSW via', 'hot-loop via'))
r.net('/POWER/PG_1V0', r.terms('/POWER/PG_1V0'), 0.15)
r.net('PG_1V8', r.terms('PG_1V8', {'U6', 'U8', 'R19', 'TP17'}), 0.15)
n = r.stitch(G, nets=('GND',))
r.bd.save()
print('stitched %d GND pads' % n)
print('open:', r.open)
