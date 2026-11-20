import math
import sys

import pcbnew

import pslib

# STM32 32 kHz crystal: Y2 sat 10 mm from the LSE pins (11/12, left edge of the STM32); its load caps C85/C86
# are already beside the pins on the bottom. Y2 moves next to the pins and LSE is re-routed
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
print('ripped %d' % P.rip(['Y2'], nets={'/STM32/LSE_IN', '/STM32/LSE_OUT'}))
u = P.pads('U11')
pin = ((u['11'][0] + u['12'][0]) / 2, (u['11'][1] + u['12'][1]) / 2)
P.fps['Y2'].SetPosition(pslib.V(60.0, 60.0))
got = P.place('Y2', pin[0] + 1.0, pin[1] + 2.6, bottom=False, rmax=8.0)
y1 = P.pads('Y2')
print('Y2 at', got, 'pads', y1, 'LSE pins', u['11'], u['12'])
b.Save(PCB)
r = pslib.Router(PCB, ['U11'])
T = r.terms
r.net('/STM32/LSE_IN', T('/STM32/LSE_IN'), 0.15)
r.net('/STM32/LSE_OUT', T('/STM32/LSE_OUT'), 0.15)
k = r.stitch(['Y2'], nets=('GND',))
r.bd.save()
L = {}
for (xa, ya, xb, yb, hw, n, ly) in r.bd.tracks:
    if n in ('/STM32/LSE_IN', '/STM32/LSE_OUT'):
        L[n] = L.get(n, 0) + math.hypot(xb - xa, yb - ya)
print('stitched %d, lengths %s' % (k, {n: round(v, 1) for n, v in L.items()}))
print('open:', r.open)
