import re
import subprocess
import sys

import pcbnew

# remove dangling track stubs a power-stage chunk left behind: tracks with a free end that is not in
# the baseline drc report (the 9 dangling ends that predate these chunks are never touched)
PCB, BASE = sys.argv[1], sys.argv[2]
MM = 1e6


def dangling(rpt):
    out = set()
    lines = open(rpt).read().split('\n')
    for i, ln in enumerate(lines):
        if ln.startswith('[track_dangling]'):
            m = re.search(r'@\(([-\d.]+) mm, ([-\d.]+) mm\): Track \[([^\]]*)\]', lines[i + 2])
            if m:
                out.add((round(float(m.group(1)), 2), round(float(m.group(2)), 2), m.group(3)))
    return out


base = dangling(BASE)
removed = 0
for it in range(4):
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--schematic-parity', '-o', '/tmp/_prune.rpt' if False else PCB + '.prune.rpt', PCB],
                   capture_output=True)
    new = dangling(PCB + '.prune.rpt') - base
    if not new:
        break
    b = pcbnew.LoadBoard(PCB)
    ts = b.Tracks()
    kill = []
    for i in range(len(ts)):
        t = ts[i]
        if t.GetClass() != 'PCB_TRACK' or t.GetLength() / MM > 8.0:
            continue
        for p in (t.GetStart(), t.GetEnd()):
            if (round(p.x / MM, 2), round(p.y / MM, 2), t.GetNetname()) in new:
                kill.append(t)
                break
    if not kill:
        break
    for t in kill:
        b.Remove(t)
    b.Save(PCB)
    removed += len(kill)
print('pruned %d dangling stub segments' % removed)
