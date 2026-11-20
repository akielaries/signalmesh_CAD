import sys

import pcbnew

import pslib

# U23 (LM2662 charge pump, +5V_AUD -> -5V): input caps C47/C48 in to pins 1/8, flying cap C259 across
# CAP+/CAP-, output cap C267 at pin 5; then route
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
G = ['U23', 'C47', 'C48', 'C259', 'C267']
caps = {}
u = P.pads('U23')
nets = {}
f = P.fps['U23']
for k in range(len(f.Pads())):
    nets[f.Pads()[k].GetNumber()] = f.Pads()[k].GetNetname()
flying = [nets['2'], nets['4']]
print('ripped %d' % P.rip(G, nets=set(flying)))
for r in G[1:]:
    P.fps[r].SetPosition(pslib.V(60.0, 60.0))


def place_any(ref, x, y, rmax=6.0):
    try:
        return P.place(ref, x, y, rmax=rmax)
    except SystemExit:
        return P.place(ref, x, y, bottom=True, rmax=rmax)


got = {}
got['C48'] = place_any('C48', u['8'][0] + 1.2, u['8'][1])
got['C47'] = place_any('C47', u['1'][0] - 1.4, u['1'][1])
got['C259'] = place_any('C259', (u['2'][0] + u['4'][0]) / 2 - 1.6, (u['2'][1] + u['4'][1]) / 2)
got['C267'] = place_any('C267', u['5'][0] + 2.0, u['5'][1] + 1.0)
for k, v in got.items():
    print('  %-4s at (%.2f, %.2f) rot %d, %.2f mm from target%s' % ((k,) + v[:3] + (v[3], ' (bottom)' if P.fps[k].IsFlipped() else '')))
b.Save(PCB)
r = pslib.Router(PCB, [])
T = r.terms
for net, refs, w in (('+5V_AUD', {'U23', 'C47', 'C48'}, 0.4), (flying[0], None, 0.4), (flying[1], None, 0.4),
                     ('-5V', {'U23', 'C267'}, 0.4)):
    r.net(net, T(net, refs), w)
k = r.stitch(G, nets=('GND',))
r.bd.save()
print('stitched %d GND pads' % k)
print('open:', r.open)
