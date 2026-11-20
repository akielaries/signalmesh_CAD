import sys

import pcbnew

import pslib
from pslib import track

# U2 boot loop fix: switch node straight east into L1's tall pad, C4 stood on end in the gap between
# U2's pin ends and L1, SW pad on the switch trace, BOOT pad next to pin 7
PCB = sys.argv[1]
MM = 1e6
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
ts = b.Tracks()
kill = []
for i in range(len(ts)):
    t = ts[i]
    n = t.GetNetname()
    if n == '/POWER/BOOT_5V':
        kill.append(t)
    elif n == '/POWER/SW_5V' and t.GetClass() == 'PCB_TRACK':
        # keep only the pin-8 stub; the diagonal and C4's old leg go
        sx, ex = t.GetStart().x / MM, t.GetEnd().x / MM
        if not (abs(t.GetStart().y / MM - 116.59) < 0.02 and abs(t.GetEnd().y / MM - 116.59) < 0.02 and max(sx, ex) < 92.6):
            kill.append(t)
for t in kill:
    b.Remove(t)
P._removed = kill
c4 = P.fps['C4']
for rot in (90, 270):
    c4.SetOrientationDegrees(rot)
    c4.SetPosition(pslib.V(93.0, 117.1))
    pp = P.pads('C4')
    if pp['1'][1] > pp['2'][1]:          # BOOT pad (1) south, next to pin 7
        break
print('C4 pads', pp)
F = pcbnew.F_Cu
track(b, (92.57, 116.59), (94.0, 116.59), 1.0, '/POWER/SW_5V', F)
track(b, (91.7, 117.865), (92.75, 117.865), 0.3, '/POWER/BOOT_5V', F)
track(b, (92.75, 117.865), pp['1'], 0.3, '/POWER/BOOT_5V', F)
b.Save(PCB)
print('removed %d, boot loop rebuilt' % len(kill))
