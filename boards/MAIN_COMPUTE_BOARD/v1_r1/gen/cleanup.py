import json
import os
import subprocess
import sys

import pcbnew

# remove routing debris: every track with a free end and every via connected on one layer or none, as
# reported by kicad's drc, repeatedly until none are left (removing a stub can expose the next one).
# the board must live in its project folder (drc needs the rules). usage: cleanup.py <board>
PCB = sys.argv[1]
MM = 1e6
RPT = PCB + '.cleanup.json'
graveyard = []
total = 0
for rnd in range(12):
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--refill-zones', '-o', RPT, PCB],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d = json.load(open(RPT))
    ids = set()
    for v in d.get('violations', []):
        if v['type'] in ('track_dangling', 'via_dangling'):
            ids |= {it['uuid'] for it in v.get('items', []) if it.get('uuid')}
    if not ids:
        break
    b = pcbnew.LoadBoard(PCB)
    # dogbones of bga balls (stub + via next to a ball of the same net) are kept even when their net is
    # still open: they are the escape the router starts from
    balls = {}
    for ref in ('U11', 'U100', 'U21'):
        f = b.FindFootprintByReference(ref)
        if f:
            for k in range(len(f.Pads())):
                p = f.Pads()[k]
                balls.setdefault(p.GetNetname(), []).append((p.GetPosition().x / MM, p.GetPosition().y / MM))
    near_ball = lambda n, x, y: any((x - bx) ** 2 + (y - by) ** 2 < 0.95 ** 2 for bx, by in balls.get(n, []))
    ts = b.Tracks()
    kill = []
    for i in range(len(ts)):
        t = ts[i]
        if t.m_Uuid.AsString() not in ids:
            continue
        n = t.GetNetname()
        if t.GetClass() == 'PCB_VIA':
            if near_ball(n, t.GetPosition().x / MM, t.GetPosition().y / MM):
                continue
        elif any(near_ball(n, e.x / MM, e.y / MM) for e in (t.GetStart(), t.GetEnd())) and t.GetLength() / MM < 0.95:
            continue
        kill.append(t)
    for t in kill:
        b.Remove(t)
    graveyard.append(kill)
    b.Save(PCB)
    total += len(kill)
    print('round %d: removed %d of %d flagged' % (rnd, len(kill), len(ids)), flush=True)
    if not kill:
        break
os.remove(RPT)
print('cleanup: removed %d items' % total)
