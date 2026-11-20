import math
import sys

import pcbnew

import pslib

# STM32 crystal: Y1 sat 23 mm from the HSE pins (35/36, left edge of the STM32); its load caps C83/C84
# are already beside the pins on the bottom. Y1 moves onto the bottom next to them and HSE is re-routed
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
print('ripped %d' % P.rip(['Y1'], nets={'/STM32/HSE_IN', '/STM32/HSE_OUT'}))
u = P.pads('U11')
pin = ((u['35'][0] + u['36'][0]) / 2, (u['35'][1] + u['36'][1]) / 2)
P.fps['Y1'].SetPosition(pslib.V(60.0, 60.0))
got = P.place('Y1', pin[0] + 1.0, pin[1] + 2.6, bottom=False, rmax=8.0)
y1 = P.pads('Y1')
print('Y1 at', got, 'pads', y1, 'HSE pins', u['35'], u['36'])
b.Save(PCB)
r = pslib.Router(PCB, ['U11'])
T = r.terms
r.net('/STM32/HSE_IN', T('/STM32/HSE_IN'), 0.15)
r.net('/STM32/HSE_OUT', T('/STM32/HSE_OUT'), 0.15)
k = r.stitch(['Y1'], nets=('GND',))
r.bd.save()
L = {}
for (xa, ya, xb, yb, hw, n, ly) in r.bd.tracks:
    if n in ('/STM32/HSE_IN', '/STM32/HSE_OUT'):
        L[n] = L.get(n, 0) + math.hypot(xb - xa, yb - ya)
print('stitched %d, lengths %s' % (k, {n: round(v, 1) for n, v in L.items()}))
print('open:', r.open)
