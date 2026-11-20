import sys

import pcbnew

import pslib
from pslib import track

# power stage of U3 (LMR33630, 12 V -> +3V3). U3 and L2 stay. input caps C13/C14/C15 come down from
# the top right to the VIN/PGND side, output caps C16-C18 from the top left to L2's output; the switch
# node runs straight east into L2's tall pad and the boot cap C12 stands in the gap beside pins 7-8
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
G = ['U3', 'C11', 'C12', 'C13', 'C14', 'C15', 'C16', 'C17', 'C18']
n = P.rip(G, nets={'/POWER/SW_3V3', '/POWER/BOOT_3V3', '/POWER/VCC_3V3', '/POWER/FB_3V3'})
print('ripped %d items' % n)
for r in ('C13', 'C14', 'C15', 'C16', 'C17', 'C18', 'C11', 'C12'):
    P.fps[r].SetPosition(pslib.V(60.0, 60.0))      # parked off the work area
u = P.pads('U3')
l2 = P.pads('L2')
print('U3 pins', {k: u[k] for k in '12345678'}, 'L2', l2)
# boot cap on end between the pin ends and L2's pad, BOOT pad (1) south beside pin 7
c12 = P.fps['C12']
gx = (u['8'][0] + 0.775 + (l2['1'][0] - 0.775)) / 2
for rot in (90, 270):
    c12.SetOrientationDegrees(rot)
    c12.SetPosition(pslib.V(gx, (u['8'][1] + u['7'][1]) / 2 + 0.03))
    pp = P.pads('C12')
    if pp['1'][1] > pp['2'][1]:
        break
print('C12 pads', pp)


def place_any(ref, x, y, rmax=7.0):
    try:
        return P.place(ref, x, y, rmax=rmax, ignore=('C12',))
    except SystemExit:
        return P.place(ref, x, y, bottom=True, rmax=rmax, ignore=('C12',))


got = {}
got['C15'] = place_any('C15', u['2'][0] - 1.5, (u['1'][1] + u['2'][1]) / 2)
got['C13'] = place_any('C13', u['2'][0] - 3.2, u['2'][1] - 0.6)
got['C14'] = place_any('C14', u['2'][0] - 3.2, u['2'][1] + 1.6)
got['C11'] = place_any('C11', u['6'][0] + 1.4, u['6'][1] + 0.6)
got['C16'] = place_any('C16', l2['2'][0] + 2.6, l2['2'][1] - 1.5)
got['C17'] = place_any('C17', l2['2'][0] + 2.6, l2['2'][1] + 1.0)
got['C18'] = place_any('C18', l2['2'][0] + 2.6, l2['2'][1] + 3.3)
for k, v in got.items():
    print('  %-4s at (%.2f, %.2f) rot %d, %.2f mm from target%s' % ((k,) + v[:3] + (v[3], ' (bottom)' if P.fps[k].IsFlipped() else '')))
F = pcbnew.F_Cu
sw_y = u['8'][1]
track(b, u['8'], (l2['1'][0] - 0.2, sw_y), 1.0, '/POWER/SW_3V3', F)
track(b, u['7'], (u['7'][0] + 1.05, u['7'][1]), 0.3, '/POWER/BOOT_3V3', F)
track(b, (u['7'][0] + 1.05, u['7'][1]), pp['1'], 0.3, '/POWER/BOOT_3V3', F)
b.Save(PCB)

r = pslib.Router(PCB, [])
r.keepout_courtyards(['L1', 'L2'])
T = r.terms
r.net('/POWER/VCC_3V3', T('/POWER/VCC_3V3'), 0.3)
r.net('/POWER/FB_3V3', T('/POWER/FB_3V3'), 0.15)
r.net('+3V3', T('+3V3', {'L2', 'C16', 'C17', 'C18'}), 0.8)
r.net('+3V3', T('+3V3', {'L2', 'R8'}), 0.2)
r.net('+12V', T('+12V', {'U3', 'C13', 'C14', 'C15'}), 0.6)
r.net('GND', [t for t in T('GND', {'U3', 'C13', 'C14', 'C15'}) if t[0] in ('U3:1', 'C13:2', 'C14:2', 'C15:2')], 0.6)
r.net('/POWER/PG_3V3', T('/POWER/PG_3V3'), 0.15)
k = r.stitch(G + ['R9'], nets=('GND', '+12V', '+3V3'))
r.bd.save()
print('stitched %d plane pads' % k)
print('open:', r.open)
