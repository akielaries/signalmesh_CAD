import math
import os
import re
import shutil
import subprocess
import sys
import time

import pslib

# rip-up and retry around blocked pins. for each open target net: the nets whose copper crowds its pins
# (tracks on the pad's layer or vias within REACH of a pad; planes, ddr, vita la, transceivers and pairs are
# never ripped) are ripped with it; the target is routed first, then the ripped nets (3d negotiated router,
# reroute.py). the attempt is kept only if the board's total of complete nets went up, else restored.
# usage: pinfree.py <board> NET [NET ...]
PCB, TARGETS = sys.argv[1], sys.argv[2:]
HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
REACH = float(os.environ.get("REACH", "0.7"))
PROTECT = re.compile(r'^(DDR_|MEZZ_|GTP|/FPGA_GTP|SFP\d_(TD|RD)|USBH_D|USBHS)|_[PN]$|^GND$')
LOG = open(PCB + '.pinfree.log', 'a')


def say(s):
    print(s, flush=True)
    LOG.write(s + '\n')
    LOG.flush()


def state():
    r = pslib.Router(PCB, [])
    zs = r.bd.b.Zones()
    planes = {zs[i].GetNetname() for i in range(len(zs)) if not zs[i].GetIsRuleArea()} | {'GND'}
    T = {}
    for (x, y, hx, hy, n, lays, rnd, p) in r.bd.pads:
        if n and not n.startswith('unconnected'):
            T.setdefault(n, []).append((p.GetParentFootprint().GetReference() + ':' + p.GetNumber(), (x, y), lays, (hx, hy)))
    done = {n for n, ts in T.items() if n not in planes and len(ts) > 1 and len(set(r.comp(n, ts))) == 1}
    return r, planes, T, done


def run(env, *args):
    e = dict(os.environ, R3D='1', FLAT_COST='1', VIA_COST='2', NEG_ITERS='20', MARGIN='8', **env)
    subprocess.run([PY, '-u', os.path.join(HERE, 'reroute.py'), PCB] + list(args), env=e, cwd=HERE,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def width_of(n):
    return '0.2' if re.match(r'^(\+|-|/POWER/|ETH_AVDD|ETH_VDDCR|VCCADC|VREF)', n) else ('0.1' if re.search(r'ETH_(TX|RX)[PN]$', n) else '0.127')


kept = 0
for tgt in TARGETS:
    r, planes, T, done = state()
    if tgt in done or tgt not in T:
        continue
    blk = set()
    for (name, (px, py), lays, (hx, hy)) in T[tgt]:
        for (xa, ya, xb, yb, hw, n, ly) in r.bd.tracks:
            if n == tgt or ly not in lays:
                continue
            dx, dy = xb - xa, yb - ya
            L2 = dx * dx + dy * dy
            u = 0 if L2 == 0 else max(0, min(1, ((px - xa) * dx + (py - ya) * dy) / L2))
            if math.hypot(px - xa - u * dx, py - ya - u * dy) < max(hx, hy) + REACH:
                blk.add(n)
        for (vx, vy, vr, n) in r.bd.vias:
            if n != tgt and math.hypot(vx - px, vy - py) < max(hx, hy) + REACH:
                blk.add(n)
    blk = sorted(b for b in blk if b not in planes and not PROTECT.search(b))[:int(os.environ.get("MAXBLK", "6"))]
    if not blk:
        say('%-18s no rippable blockers' % tgt)
        continue
    before = len(done)
    snap = PCB + '.pinfree.snap'
    shutil.copy(PCB, snap)
    t0 = time.time()
    run({}, 'rip', tgt, *blk)
    run({'WIDTH': width_of(tgt), 'CLR': '0.15' if width_of(tgt) != '0.127' else '0.127'}, 'route', tgt)
    for wdt in sorted({width_of(b) for b in blk}):
        group = [b for b in blk if width_of(b) == wdt]
        run({'WIDTH': wdt, 'CLR': '0.15' if wdt != '0.127' else '0.127'}, 'route', *group)
    _, _, _, done2 = state()
    if len(done2) > before:
        kept += 1
        say('%-18s kept: complete %d -> %d (ripped %s) %.0fs' % (tgt, before, len(done2), ' '.join(blk), time.time() - t0))
    else:
        shutil.copy(snap, PCB)
        say('%-18s reverted: complete %d -> %d (tried %s) %.0fs' % (tgt, before, len(done2), ' '.join(blk), time.time() - t0))
say('pinfree: %d of %d targets improved the board' % (kept, len(TARGETS)))
