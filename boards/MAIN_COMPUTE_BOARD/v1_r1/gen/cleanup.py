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
    ts = b.Tracks()
    kill = []
    for i in range(len(ts)):
        t = ts[i]
        if t.m_Uuid.AsString() in ids:
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
