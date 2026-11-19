import heapq
import os
import sys

import pcbnew

# writes docs/ddr_routing.md: every ddr3 net, where it goes, its matching group and its state on the board
PCB, OUT = sys.argv[1], sys.argv[2]
b = pcbnew.LoadBoard(PCB)
fs = b.Footprints()
fp = {fs[i].GetReference(): fs[i] for i in range(len(fs))}
U21 = [r for r, f in fp.items() if f.GetValue().startswith('MT41K')][0]
TOL = {'LANE0': 1.4, 'LANE1': 1.4, 'CMD': 3.0}
REF = {'LANE0': 'DDR_DQS0', 'LANE1': 'DDR_DQS1', 'CMD': 'DDR_CK'}
LANES = {0: ['DDR_DQ%d' % i for i in range(8)] + ['DDR_DM0'], 1: ['DDR_DQ%d' % i for i in range(8, 16)] + ['DDR_DM1']}
CMD = ['DDR_A%d' % i for i in range(15)] + ['DDR_BA0', 'DDR_BA1', 'DDR_BA2', 'DDR_RAS_N', 'DDR_CAS_N', 'DDR_WE_N',
                                            'DDR_CKE', 'DDR_ODT']


def ball(net, ref):
    f = fp[ref]
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        if p.GetNetname() == net:
            return p.GetNumber(), (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)
    return None, None


def term(net):
    for r, f in fp.items():
        if f.GetValue().startswith('39.2'):
            for k in range(len(f.Pads())):
                if f.Pads()[k].GetNetname() == net:
                    return r
    return ''


ts = b.Tracks()
tracks = {}
vias = {}
for i in range(len(ts)):
    t = ts[i]
    n = t.GetNetname()
    if not n.startswith('DDR_'):
        continue
    if t.GetClass() == 'PCB_VIA':
        vias.setdefault(n, set()).add((round(t.GetPosition().x / 1e6, 3), round(t.GetPosition().y / 1e6, 3)))
    else:
        tracks.setdefault(n, []).append((round(t.GetStart().x / 1e6, 3), round(t.GetStart().y / 1e6, 3),
                                         round(t.GetEnd().x / 1e6, 3), round(t.GetEnd().y / 1e6, 3),
                                         t.GetLength() / 1e6, b.GetLayerName(t.GetLayer())))


def term_xy(net):
    r = term(net)
    if not r:
        return None
    f = fp[r]
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        if p.GetNetname() == net:
            return (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)


def flight(net, s=None, e=None):
    # copper path (default fpga ball -> dram ball): length, vias passed, layers used (None if not connected)
    g = {}
    for (xa, ya, xb, yb, ln, ly) in tracks.get(net, []):
        g.setdefault((xa, ya), []).append(((xb, yb), ln, ly))
        g.setdefault((xb, yb), []).append(((xa, ya), ln, ly))
    if s is None:
        _, s = ball(net, 'U100')
    if e is None:
        _, e = ball(net, U21)
    s, e = (round(s[0], 3), round(s[1], 3)), (round(e[0], 3), round(e[1], 3))
    dist, prev = {s: 0.0}, {}
    q = [(0.0, s)]
    while q:
        d, u = heapq.heappop(q)
        if u == e:
            break
        if d > dist.get(u, 1e9):
            continue
        for v, w, ly in g.get(u, []):
            if d + w < dist.get(v, 1e9):
                dist[v], prev[v] = d + w, (u, ly)
                heapq.heappush(q, (d + w, v))
    if e not in dist:
        return None, 0, set()
    nv, lys, u = 0, set(), e
    while u in prev:
        u, ly = prev[u]
        lys.add(ly.replace('.Cu', ''))
        if u in vias.get(net, set()):
            nv += 1
    return dist[e], nv, lys


L = {}
for n in CMD + sum(LANES.values(), []) + ['DDR_RESET_N'] + [p + s for p in REF.values() for s in ('_P', '_N')]:
    L[n] = flight(n)
ref_len = {}
for g, r in REF.items():
    a, c = L[r + '_P'][0], L[r + '_N'][0]
    ref_len[g] = (a + c) / 2 if a and c else None


def rows(nets, g):
    out = []
    for n in nets:
        fb, _ = ball(n, 'U100')
        db, _ = ball(n, U21)
        ln, nv, lys = L[n]
        tr = term(n) if g == 'CMD' else ''
        if tr:
            tl = flight(n, ball(n, U21)[1], term_xy(n))[0]
            tr += ' (tail %s)' % ('%.1f mm' % tl if tl else '**open**')
        if ln is None:
            state, dl = '**open**', ''
        else:
            r = ref_len.get(g)
            dl = '%+.2f' % (ln - r) if r else ''
            if g not in TOL:
                state = 'routed'
            else:
                state = 'ok' if r is not None and abs(ln - r) <= TOL[g] else '**tune**'
        out.append('| %s | %s | %s | %s | %s | %s | %s | %s |' % (
            n, fb, db, tr, '%.2f' % ln if ln else '', dl, '%d / %s' % (nv, ','.join(sorted(lys))) if ln else '',
            state))
    return '\n'.join(out)


def pair_rows():
    out = []
    for g, r in REF.items():
        for s in ('_P', '_N'):
            n = r + s
            fb, _ = ball(n, 'U100')
            db, _ = ball(n, U21)
            ln, nv, lys = L[n]
            out.append('| %s | %s | %s | %s | %s |' % (n, fb, db, '%.2f' % ln if ln else '**open**',
                                                     '%d / %s' % (nv, ','.join(sorted(lys))) if ln else ''))
    return '\n'.join(out)


H = '| net | FPGA ball | DRAM ball | terminator | length mm | vs ref | vias / layers | state |\n|---|---|---|---|---|---|---|---|\n'
doc = '''# DDR3 routing: status and finishing guide

Generated from the board by `gen/ddrdoc.py`. Lengths are copper from the FPGA ball to the DRAM ball,
including both dogbones; the fly-by tail to each command terminator is not counted.

## rules

| item | rule |
|---|---|
| byte lane 0 | DQ0-7 and DM0 matched to the DQS0 pair, +/-1.4 mm (+/-10 ps) |
| byte lane 1 | DQ8-15 and DM1 matched to the DQS1 pair, +/-1.4 mm |
| address/command | A0-14, BA0-2, RAS_N, CAS_N, WE_N, CKE, ODT matched to the CK pair, +/-3 mm (+/-20 ps) |
| pairs | DQS0, DQS1, CK: P to N within 0.15 mm, coupled outside the ball fields (DIFF100). CK is currently 1.8 mm apart (21.73 / 23.52): add a skew bump on CK_P |
| not matched | RESET_N; the tails from DRAM ball to the 39.2 R terminators; lane-to-lane; CK to DQS (write leveling absorbs it, keep CK equal or longer if you can) |
| topology | command nets are fly-by: FPGA, then the DRAM ball, then the terminator. Take the tail from the DRAM ball via, never stub off the main run. Tail length is not matched; under about 20 mm is fine since the terminator ends the line |
| vias | 2 per net: the FPGA dogbone and the DRAM dogbone (3 at most, if a net has to change layer once). The command tail adds one more at the terminator. Keep the via count equal within a byte lane; a pair's two halves always get the same vias |
| layers | In2 (between GND planes) is preferred for data, In5 (between the 1V35 plane and GND) for command. B.Cu and F.Cu are allowed. Keep a byte lane on one layer where possible: outer-layer microstrip is about 15 percent faster per mm than stripline, so a mixed lane needs matching in ps, not mm |
| widths | In2/In5: 0.23 mm (50 ohm). F.Cu/B.Cu: 0.127 mm. Pairs inner: 0.115 mm with a 0.10 mm gap; outer: 0.10 / 0.18. Neck to 0.10 mm only inside the FPGA and DRAM ball fields (DRC rule "BGA escape") |
| spacing | 0.15 mm DDR class clearance minimum; 3x the trace width (about 0.7 mm inner) between different nets on long parallel runs and between serpentine loops |
| tuning | KiCad length tuner (single track: 7, diff pair: 8). Amplitude up to about 1 mm, spacing 3w, put meanders outside the ball fields. For ps accuracy, add the FPGA package delays (xc7a100tfgg484 package file) when available |
| don't cut | the In5 +1V0 feed pour (left of and above the DDR escape) and the VTT strip/pour around the terminators |

## references

| pair | length mm |
|---|---|
''' + '\n'.join('| %s | %s |' % (r, '%.2f' % ref_len[g] if ref_len[g] else 'open') for g, r in REF.items()) + '''

## pairs

| net | FPGA ball | DRAM ball | length mm | vias / layers |
|---|---|---|---|---|
''' + pair_rows() + '''

## byte lane 0 (to DQS0)

''' + H + rows(LANES[0], 'LANE0') + '''

## byte lane 1 (to DQS1)

''' + H + rows(LANES[1], 'LANE1') + '''

## address / command (to CK)

''' + H + rows(CMD, 'CMD') + '''

## reset (not matched)

''' + H + rows(['DDR_RESET_N'], 'RESET') + '''

`open` = no copper path between the two balls yet (end vias and dogbones are in place). `tune` =
routed, but outside its window: positive is too long (re-route shorter), negative is too short (add
a serpentine). Command nets also need their tail from the DRAM ball via to the listed terminator.
'''
open(os.path.join(OUT, 'ddr_routing.md'), 'w').write(doc)
print('ddr_routing.md written')
