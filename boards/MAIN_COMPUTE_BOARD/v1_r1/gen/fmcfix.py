import json
import math
import os
import sys

import pcbnew

# bring an existing board in line with fmc_swap.json without regenerating it: relabel the swapped
# fpga balls and their fanout dogbones, and remove only those nets' old routes
PCB = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
swap = json.load(open(os.path.join(HERE, sys.argv[2] if len(sys.argv) > 2 else 'fmc_swap.json')))
b = pcbnew.LoadBoard(PCB)
u = b.FindFootprintByReference('U100')
ball_new = {}
for k in range(len(u.Pads())):
    p = u.Pads()[k]
    n = p.GetNetname()
    if n in swap:
        ball_new[(round(p.GetPosition().x / 1e6, 3), round(p.GetPosition().y / 1e6, 3))] = (p, swap[n])
ts = b.Tracks()
items = [ts[i] for i in range(len(ts))]
key = lambda v: (round(v.x / 1e6, 3), round(v.y / 1e6, 3))
keep = {}
for t in items:
    if t.GetClass() == 'PCB_VIA' or t.GetLayer() != pcbnew.F_Cu or t.GetNetname() not in swap:
        continue
    for end, other in ((key(t.GetStart()), key(t.GetEnd())), (key(t.GetEnd()), key(t.GetStart()))):
        if end in ball_new and math.hypot(end[0] - other[0], end[1] - other[1]) < 1.2:
            keep[id(t)] = ball_new[end][1]
            keep[('via', other)] = ball_new[end][1]
relabel = remove = 0
for t in items:
    n = t.GetNetname()
    if n not in swap:
        continue
    if id(t) in keep:
        t.SetNet(b.FindNet(keep[id(t)]))
        relabel += 1
    elif t.GetClass() == 'PCB_VIA' and ('via', key(t.GetPosition())) in keep:
        t.SetNet(b.FindNet(keep[('via', key(t.GetPosition()))]))
        relabel += 1
    else:
        b.Remove(t)
        remove += 1
for (p, new) in ball_new.values():
    p.SetNet(b.FindNet(new))
b.Save(PCB)
print('balls relabelled %d, dogbone items relabelled %d, old route items removed %d' % (len(ball_new), relabel, remove))
