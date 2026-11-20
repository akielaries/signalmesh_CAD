import sys

import pcbnew

import pslib

# U2 power stage routing (after pstage_u2.py), plus U5's parts that moved under U5
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
# PG_1V8's vias sit under U2's BOOT pad: rip the net, route it again below (U3's enable is on it too)
print('PG_1V8 ripped (%d items)' % P.rip([], nets={'PG_1V8'}))
b.Save(PCB)

r = pslib.Router(PCB, ['U5', 'U6'])
r.keepout_courtyards(['L1', 'L2', 'L4', 'L5', 'L7'])
T = r.terms
# switch node first, wide; then boot, vcc, feedback
r.net('/POWER/SW_5V', T('/POWER/SW_5V', {'U2', 'L1'}), 1.0)
r.net('/POWER/SW_5V', T('/POWER/SW_5V', {'U2', 'L1', 'C4'}), 0.3)
r.net('/POWER/BOOT_5V', T('/POWER/BOOT_5V'), 0.3)
r.net('/POWER/VCC_5V', T('/POWER/VCC_5V'), 0.3)
r.net('/POWER/FB_5V', T('/POWER/FB_5V'), 0.15)
r.net('+5V', T('+5V', {'R5', 'L1'}), 0.2)
# input: VIN and the three caps, then the ground side
r.net('+12V', T('+12V', {'U2', 'C5', 'C6', 'C7'}), 0.6)
r.net('GND', [t for t in T('GND', {'U2', 'C5', 'C6', 'C7'}) if t[0] in ('U2:1', 'C5:2', 'C6:2', 'C7:2')], 0.6)
# U5's moved parts
r.net('/POWER/FB_1V0', T('/POWER/FB_1V0'), 0.15)
r.net('/POWER/SS_1V0', T('/POWER/SS_1V0'), 0.15)
r.net('+5V', T('+5V', {'C25', 'C26', 'U5'}), 0.4)
# enable / power-good chains
r.net('/POWER/PG_5V', T('/POWER/PG_5V'), 0.15)
r.net('PG_1V8', T('PG_1V8'), 0.15)
n = r.stitch(['U2', 'C3', 'C5', 'C6', 'C7', 'R6', 'R14', 'R15', 'C24', 'C25', 'C26'], nets=('GND', '+12V', '+1V0'))
r.bd.save()
print('stitched %d plane pads' % n)
print('open:', r.open)
