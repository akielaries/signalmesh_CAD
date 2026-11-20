import sys

import pcbnew

import pslib
from pslib import via

# B.Cu reclaim: the full-board +12V pour on B.Cu becomes one narrower pour (top strip, left strip down
# the front side, bottom-left power box), and the input shunt R2 moves next to Q1 / the INA219 so
# +12V starts at the input. every +12V pad is then stitched into the pour
PCB = sys.argv[1]
MM = 1e6
b = pcbnew.LoadBoard(PCB)
P = pslib.Placer(b)
# 1) R2 below the INA219: force pad 1 (12V_PROT) west toward Q1, force pad 4 (+12V) east
P.rip(['R2'])
r2 = P.fps['R2']
r2.SetPosition(pslib.V(60.0, 60.0))
# bottom side under Q1 / the INA219 (the sfp cage J18 keeps the top side full): rot 0 puts force pad 1
# (12V_PROT) under Q1's source pins, force pad 4 (+12V) on B.Cu inside the new pour
got = P.place('R2', 76.0, 61.5, bottom=True, rmax=1.0, rots=(0,))
pp = P.pads('R2')
print('R2 at', got, 'pads', pp)
f = P.fps['R2']
for k in range(len(f.Pads())):
    if f.Pads()[k].GetNumber() == '4':
        f.Pads()[k].SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
# 2) the pour: one outline instead of the whole board
zs = b.Zones()
old = [zs[i] for i in range(len(zs)) if zs[i].GetNetname() == '+12V' and zs[i].GetLayer() == pcbnew.B_Cu][0]
pts = [(76.0, 53.6), (190.6, 53.6), (190.6, 64.5), (180.0, 64.5), (180.0, 60.5), (90.0, 60.5), (90.0, 66.5),
       (82.0, 66.5), (82.0, 112.0), (90.0, 112.0), (90.0, 146.0), (75.0, 146.0), (75.0, 112.0), (76.0, 112.0)]
new = old.Duplicate(False).Cast()
sps = pcbnew.SHAPE_POLY_SET()
sps.NewOutline()
for x, y in pts:
    sps.Append(int(x * MM), int(y * MM))
new.SetOutline(sps)
b.Add(new)
b.Remove(old)
P._removed = [old]
# 3) 12V_PROT: Q1's source pins (top) and D2 down three vias onto R2's force pad 1 (bottom)
F, B = pcbnew.F_Cu, pcbnew.B_Cu
q1 = P.pads('Q1')
d2 = P.pads('D2')['1']
p1 = pp['1']
pslib.track(b, (q1['1'][0], q1['1'][1]), (q1['3'][0], q1['3'][1]), 0.6, '/POWER/12V_PROT', F)
# straight down from Q1 past D2's 12V_PROT pin to a via row below R2's force pad (pad 2, the sense pad
# of the same end, sits north of it and must stay a separate net)
yv = p1[1] + 1.75
pslib.track(b, q1['3'], (q1['3'][0], yv), 1.5, '/POWER/12V_PROT', F)
pslib.track(b, (q1['3'][0], yv), (p1[0] + 0.8, yv), 1.5, '/POWER/12V_PROT', F)
for x in (p1[0] - 0.8, p1[0], p1[0] + 0.8):
    via(b, (x, yv), '/POWER/12V_PROT')
pslib.track(b, (p1[0] - 0.8, yv), (p1[0] + 0.8, yv), 0.8, '/POWER/12V_PROT', B)
pslib.track(b, (p1[0], yv), p1, 1.5, '/POWER/12V_PROT', B)
filler = pcbnew.ZONE_FILLER(b)
zs = b.Zones()
filler.Fill([zs[i] for i in range(len(zs))])
b.Save(PCB)
print('pour replaced; filled area now %.0f mm2' % (new.GetFilledArea() / MM / MM))

# 4) input path and sense lines, then every +12V pad into the pour
r = pslib.Router(PCB, [])
T = r.terms
r.net('/POWER/ISNS_P', T('/POWER/ISNS_P'), 0.2)
r.net('/POWER/ISNS_N', T('/POWER/ISNS_N'), 0.2)
loads = [f.GetReference() for f in r.bd.b.Footprints()
         if any(f.Pads()[k].GetNetname() == '+12V' for k in range(len(f.Pads()))) and f.GetReference() != 'R2']
k = r.stitch(loads, nets=('+12V',))
r.bd.save()
print('stitched %d +12V pads' % k)
print('open:', r.open)
