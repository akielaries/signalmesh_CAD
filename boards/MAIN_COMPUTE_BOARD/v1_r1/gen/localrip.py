import json
import math
import os
import re
import shutil
import subprocess
import sys

import pcbnew

# local rip-up for short missing connections: for each one, the other nets' copper inside a small box around
# the hop is removed (segments and vias only, never whole nets; ddr, vita, transceivers and pairs untouched),
# then localfix.py routes the hop and reconnects what was cut, all inside the box. kept only if kicad drc shows
# fewer unconnected items and no rule errors; otherwise restored. usage: localrip.py <board>
PCB = sys.argv[1]
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
MAXD = float(os.environ.get('MAXD', '20'))
PAD = float(os.environ.get('RIPPAD', '0.8'))
MM = 1e6
PROTECT = re.compile(r'^(DDR_|MEZZ_|GTP|/FPGA_GTP|SFP\d_(TD|RD)|USBH_D|USBHS)|_[PN]$')
GRAVE = []


def drc():
    rpt = PCB + '.lr.json'
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '--refill-zones', '-o', rpt, PCB],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d = json.load(open(rpt))
    errs = sum(1 for v in d.get('violations', []) if not v['type'].startswith(('silk', 'track_dangling', 'via_dangling', 'text_', 'unconnected')))
    return d.get('unconnected_items', []), errs


def short_items(unc):
    out = []
    for v in unc:
        its = v.get('items', [])
        if len(its) != 2 or any(i['description'].startswith('Zone') for i in its):
            continue
        m = re.search(r'\[([^\]]+)\]', its[0]['description'])
        a = (its[0]['pos']['x'], its[0]['pos']['y'])
        b = (its[1]['pos']['x'], its[1]['pos']['y'])
        dd = math.hypot(a[0] - b[0], a[1] - b[1])
        sk = [float(v) for v in os.environ['SKIPBOX'].split(',')] if os.environ.get('SKIPBOX') else None
        if sk and all(sk[0] <= p[0] <= sk[2] and sk[1] <= p[1] <= sk[3] for p in (a, b)):
            continue
        if m and dd <= MAXD and not PROTECT.search(m.group(1)):
            out.append((dd, m.group(1), a, b))
    return sorted(out)


def seg_hits_box(a, z, bx):
    # sampled test: good enough for the short segments near a hop
    n = max(2, int(math.hypot(z[0] - a[0], z[1] - a[1]) / 0.1))
    for i in range(n + 1):
        x = a[0] + (z[0] - a[0]) * i / n
        y = a[1] + (z[1] - a[1]) * i / n
        if bx[0] <= x <= bx[2] and bx[1] <= y <= bx[3]:
            return True
    return False


def rip_box(net, bx):
    b = pcbnew.LoadBoard(PCB)
    ts = b.Tracks()
    kill = []
    keep = []
    for i in range(len(ts)):
        t = ts[i]
        n = t.GetNetname()
        if n == net or PROTECT.search(n) or n == 'GND':
            continue
        if t.GetClass() == 'PCB_VIA':
            p = (t.GetPosition().x / MM, t.GetPosition().y / MM)
            if bx[0] <= p[0] <= bx[2] and bx[1] <= p[1] <= bx[3]:
                kill.append(t)
        else:
            a = (t.GetStart().x / MM, t.GetStart().y / MM)
            z = (t.GetEnd().x / MM, t.GetEnd().y / MM)
            if seg_hits_box(a, z, bx):
                kill.append(t)
                # keep the parts of the segment outside the box so the cut ends stay local
                ln = math.hypot(z[0] - a[0], z[1] - a[1])
                k = max(2, int(ln / 0.02))
                ins = [i for i in range(k + 1) if bx[0] <= a[0] + (z[0] - a[0]) * i / k <= bx[2] and bx[1] <= a[1] + (z[1] - a[1]) * i / k <= bx[3]]
                for (s, e) in ((0, max(0, ins[0] - 1)), (min(k, ins[-1] + 1), k)):
                    if (e - s) * ln / k < 0.05:
                        continue
                    nt = pcbnew.PCB_TRACK(b)
                    p0 = (a[0] + (z[0] - a[0]) * s / k, a[1] + (z[1] - a[1]) * s / k)
                    p1 = (a[0] + (z[0] - a[0]) * e / k, a[1] + (z[1] - a[1]) * e / k)
                    nt.SetStart(pcbnew.VECTOR2I(int(round(p0[0] * MM)), int(round(p0[1] * MM))))
                    nt.SetEnd(pcbnew.VECTOR2I(int(round(p1[0] * MM)), int(round(p1[1] * MM))))
                    nt.SetWidth(t.GetWidth())
                    nt.SetLayer(t.GetLayer())
                    nt.SetNet(t.GetNet())
                    keep.append(nt)
    nets = sorted({t.GetNetname() for t in kill})
    for t in kill:
        b.Remove(t)
    for nt in keep:
        b.Add(nt)
    GRAVE.extend(keep)
    GRAVE.extend(kill)
    GRAVE.append(b)
    b.Save(PCB)
    return nets


unc, e0 = drc()
u0 = len(unc)
print('start: %d unconnected, %d errors' % (u0, e0), flush=True)
tried = set()
kept = 0
while True:
    cand = [c for c in short_items(unc) if (c[1], round(c[2][0], 1), round(c[2][1], 1)) not in tried]
    if not cand:
        break
    dd, net, a, z = cand[0]
    tried.add((net, round(a[0], 1), round(a[1], 1)))
    bx = (min(a[0], z[0]) - PAD, min(a[1], z[1]) - PAD, max(a[0], z[0]) + PAD, max(a[1], z[1]) + PAD)
    snap = PCB + '.lr.snap'
    shutil.copy(PCB, snap)
    ripped = rip_box(net, bx)
    if not ripped:
        print('%-18s %5.1f mm  nothing to rip' % (net, dd), flush=True)
        continue
    wide = (bx[0] - 4, bx[1] - 4, bx[2] + 4, bx[3] + 4)
    env = dict(os.environ, BOX='%.2f,%.2f,%.2f,%.2f' % wide, MAXD='30', FIRST='%s:%.3f,%.3f' % (net, a[0], a[1]))
    subprocess.run([PY, '-u', os.path.join(HERE, 'localfix.py'), PCB], env=env, cwd=HERE,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([PY, os.path.join(HERE, 'viamerge.py'), PCB], cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([PY, os.path.join(HERE, 'cleanup.py'), PCB], cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    unc2, e1 = drc()
    if len(unc2) < u0 and e1 <= e0:
        kept += 1
        print('%-18s %5.1f mm  kept: %d -> %d (ripped %s)' % (net, dd, u0, len(unc2), ' '.join(ripped)), flush=True)
        u0, unc = len(unc2), unc2
    else:
        shutil.copy(snap, PCB)
        print('%-18s %5.1f mm  restored (%d unconnected, %d errors; ripped %s)' % (net, dd, len(unc2), e1, ' '.join(ripped)), flush=True)
print('localrip: %d kept, %d unconnected' % (kept, u0))
