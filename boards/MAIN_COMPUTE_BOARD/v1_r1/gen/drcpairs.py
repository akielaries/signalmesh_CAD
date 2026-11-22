import json
import os
import re
import subprocess
import sys
import time

import pcbnew

import negroute3d
import proute
import pslib
import rlib

# route exactly the connections kicad's drc reports as missing: each unconnected_items entry names the two
# nearest copper pieces of one net that should join. both ends become a leg of the 3d negotiated router:
# a via end may change layer, a pad or track end is pinned to its layer. power and plane nets get wide
# tracks, everything else 0.127 mm. usage: drcpairs.py <board> [regex of nets to include]
PCB = sys.argv[1]
PAT = re.compile(sys.argv[2]) if len(sys.argv) > 2 else re.compile('.')
RPT = PCB + '.pairs.json'
t0 = time.time()
subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--refill-zones', '-o', RPT, PCB],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
d = json.load(open(RPT))
os.remove(RPT)
r = pslib.Router(PCB, ['U11', 'U100', 'U21'])
r.clr = 0.127
bd = r.bd
POWER = re.compile(r'^(\+|-|/POWER/|ETH_AVDD|ETH_VDDCR|VCCADC|GNDADC|VREF|VBUS|VTT|GND$|VADJ$|/MCU_IO/ULPI_1V8)')
legs = []
for v in d.get('unconnected_items', []) + [x for x in d.get('violations', []) if x.get('type') == 'unconnected_items']:
    its = v.get('items', [])
    if len(its) != 2:
        continue
    m = re.search(r'\[([^\]]+)\]', its[0]['description'])
    if not m or not PAT.search(m.group(1)):
        continue
    net = m.group(1)
    ends = []
    for it in its:
        p = (it['pos']['x'], it['pos']['y'])
        desc = it['description']
        lm = re.search(r' on ([FB]\.Cu|In\d\.Cu)\b', desc)
        if desc.startswith('Via') or desc.startswith('PTH') or 'F.Cu - B.Cu' in desc or not lm:
            ends.append((p, None))
        else:
            ends.append((p, lm.group(1)))
    leg = {'net': net, 'a': ends[0][0], 'b': ends[1][0]}
    if ends[0][1] in rlib.LAYERS:
        leg['la'] = ends[0][1]
    if ends[1][1] in rlib.LAYERS:
        leg['lb'] = ends[1][1]
    legs.append(leg)
print('missing connections from drc: %d (%.0fs)' % (len(legs), time.time() - t0), flush=True)
LAYERS = ('In2.Cu', 'In7.Cu', 'In5.Cu', 'B.Cu', 'F.Cu')
for group, wd, clr in (('power', 0.25, 0.15), ('signal', 0.127, 0.127)):
    gl = [l for l in legs if bool(POWER.search(l['net'])) == (group == 'power')]
    if not gl:
        continue
    ax = [l['a'][0] for l in gl] + [l['b'][0] for l in gl]
    ay = [l['a'][1] for l in gl] + [l['b'][1] for l in gl]
    win = (max(50.5, min(ax) - 6), max(53.6, min(ay) - 6), min(190.6, max(ax) + 6), min(146.9, max(ay) + 6))
    left = negroute3d.negotiate3d(bd, gl, win, {ly: wd for ly in LAYERS}, {ly: 1.0 for ly in LAYERS}, via_cost=2.0,
                                  iters=int(os.environ.get('NEG_ITERS', '20')), clr=clr, margin=float(os.environ.get('MARGIN', '6')),
                                  log=lambda s: print(s, flush=True))
    print('%s: %d of %d connections routed' % (group, len(gl) - len(left), len(gl)), flush=True)
bd.save()
