import json
import math
import os
import re
import subprocess
import sys

import negroute3d
import pslib
import rlib

# short missing connections one at a time: every drc unconnected item whose two ends are close (MAXD) is
# routed alone in a small window, trying the widest track first and narrowing down to 0.127 mm (power hops
# between regulator pins rarely fit 0.25). clearance follows the net class (0.15 for power, 0.1 otherwise).
# FIRST=net:x,y routes that hop before the rest. BOX=x0,y0,x1,y1 limits it to items with both ends inside. usage: localfix.py <board>
PCB = sys.argv[1]
MAXD = float(os.environ.get('MAXD', '20'))
RPT = PCB + '.local.json'
subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--refill-zones', '-o', RPT, PCB],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
d = json.load(open(RPT))
os.remove(RPT)
PWR = re.compile(r'^(\+|-|VTT|GND$|VADJ$|ETH_AVDD|/MCU_IO/ULPI_1V8)')
LAYERS = ('F.Cu', 'B.Cu', 'In2.Cu', 'In7.Cu', 'In5.Cu')
items = []
for v in d.get('unconnected_items', []):
    its = v.get('items', [])
    if len(its) != 2:
        continue
    m = re.search(r'\[([^\]]+)\]', its[0]['description'])
    if not m or its[0]['description'].startswith('Zone') or its[1]['description'].startswith('Zone'):
        continue
    ends = []
    for it in its:
        p = (it['pos']['x'], it['pos']['y'])
        desc = it['description']
        lm = re.search(r' on ([FB]\.Cu|In\d\.Cu)\b', desc)
        ends.append((p, None if (desc.startswith('Via') or 'F.Cu - B.Cu' in desc or not lm) else lm.group(1)))
    dist = math.hypot(ends[0][0][0] - ends[1][0][0], ends[0][0][1] - ends[1][0][1])
    box = [float(x) for x in os.environ['BOX'].split(',')] if os.environ.get('BOX') else None
    inbox = lambda p: box is None or (box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3])
    if dist <= MAXD and inbox(ends[0][0]) and inbox(ends[1][0]):
        items.append((dist, m.group(1), ends))
items.sort()
# FIRST=net:x,y puts the item of that net nearest to (x, y) at the front (the hop a rip-up was made for)
if os.environ.get('FIRST'):
    fn, fxy = os.environ['FIRST'].rsplit(':', 1)
    fx, fy = (float(v) for v in fxy.split(','))
    mine = [it for it in items if it[1] == fn]
    if mine:
        top = min(mine, key=lambda it: min(math.hypot(e[0][0] - fx, e[0][1] - fy) for e in it[2]))
        items.remove(top)
        items.insert(0, top)
print('short missing connections: %d' % len(items), flush=True)
done = 0
for dist, net, ends in items:
    pw = bool(PWR.search(net))
    clr = 0.15 if pw else 0.1
    widths = (0.3, 0.25, 0.2, 0.15, 0.127) if pw else (0.127,)
    ok = None
    for wd in widths:
        r = pslib.Router(PCB, ['U11', 'U100', 'U21'])
        r.clr = clr
        bd = r.bd
        leg = {'net': net, 'a': ends[0][0], 'b': ends[1][0]}
        if ends[0][1] in rlib.LAYERS:
            leg['la'] = ends[0][1]
        if ends[1][1] in rlib.LAYERS:
            leg['lb'] = ends[1][1]
        xs, ys = (ends[0][0][0], ends[1][0][0]), (ends[0][0][1], ends[1][0][1])
        for pad in (3.0, 6.0):
            win = (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
            left = negroute3d.negotiate3d(bd, [leg], win, {ly: wd for ly in LAYERS}, {ly: 1.0 for ly in LAYERS},
                                          via_cost=1.5, iters=8, clr=clr, margin=pad, log=lambda s: None)
            if not left:
                bd.save()
                ok = (wd, pad)
                break
        if ok:
            break
    if ok:
        done += 1
    print('%-22s %5.1f mm  %s' % (net, dist, 'routed at %.3f mm' % ok[0] if ok else 'no route'), flush=True)
print('localfix: %d of %d routed' % (done, len(items)))
