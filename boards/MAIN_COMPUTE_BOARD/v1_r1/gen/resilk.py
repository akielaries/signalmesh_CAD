import json
import os
import sys

import pcbnew

import labels
import silkplace

# redo silk labels and refs on a board whose footprints moved after pcbbuild (router cap moves)
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
fs = b.Footprints()
fps = {fs[i].GetReference(): fs[i] for i in range(len(fs))}
ds = b.Drawings()
old = [ds[i] for i in range(len(ds)) if ds[i].GetClass() == 'PCB_TEXT' and ds[i].GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)]
for d in old:
    b.Remove(d)
amap = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out', 'audio_refmap.json')))
byvalue = {}
for r, f in sorted(fps.items()):
    byvalue.setdefault(f.GetValue(), r)
named = labels.build(byvalue, [(amap['J13'], 'L'), (amap['J9'], 'R'), (amap['J11'], 'DAC1')])
named += [(r, 'GND') for r, f in fps.items() if f.GetValue() == 'TP GND']
print('removed', len(old), 'labels', silkplace.place_refs(b, 50, 50, 210, 150, labels=named))
b.Save(PCB)
