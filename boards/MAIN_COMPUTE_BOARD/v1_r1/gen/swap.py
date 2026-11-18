import json
import os
import sys

import pcbnew

# ddr3 pin swap: re-pair fpga balls with dram nets so the bus runs without crossings.
# lanes swap as whole bytes, dq bits swap inside a byte, addr/cmd nets swap among the addr/cmd balls.
# dqs, ck, dm, odt, reset stay put. output: {net now on an fpga ball: net it should carry}
b = pcbnew.LoadBoard(sys.argv[1])
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ddr_swap.json')
fpga, dram = {}, {}
fs = b.Footprints()
for i in range(len(fs)):
    f = fs[i]
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        n = p.GetNetname()
        if n.startswith('DDR_'):
            xy = (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)
            if f.GetReference() == 'U100':
                fpga[n] = xy
            elif f.GetValue().startswith('MT41K'):
                dram[n] = xy


def cen(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def across(src, dst):
    # unit vector perpendicular to the flow from src centroid to dst centroid
    (ax, ay), (bx, by) = cen(src), cen(dst)
    dx, dy = bx - ax, by - ay
    ln = (dx * dx + dy * dy) ** 0.5
    return (-dy / ln, dx / ln)


def pair_up(fnets, dnets):
    # fnets: nets now on the fpga balls of a group; dnets: dram nets the group must carry
    u = across([fpga[n] for n in fnets], [dram[n] for n in dnets])
    fo = sorted(fnets, key=lambda n: u[0] * fpga[n][0] + u[1] * fpga[n][1])
    do = sorted(dnets, key=lambda n: u[0] * dram[n][0] + u[1] * dram[n][1])
    return dict(zip(fo, do))


m = {}
byte = {k: ['DDR_DQ%d' % (8 * k + i) for i in range(8)] for k in (0, 1)}
extra = {k: ['DDR_DM%d' % k, 'DDR_DQS%d_P' % k, 'DDR_DQS%d_N' % k] for k in (0, 1)}
# which fpga byte group should carry which dram byte
fc = {k: cen([fpga[n] for n in byte[k] + extra[k]]) for k in (0, 1)}
dc = {k: cen([dram[n] for n in byte[k] + extra[k]]) for k in (0, 1)}
u = across([fc[0], fc[1]], [dc[0], dc[1]])
fo = sorted((0, 1), key=lambda k: u[0] * fc[k][0] + u[1] * fc[k][1])
do = sorted((0, 1), key=lambda k: u[0] * dc[k][0] + u[1] * dc[k][1])
lane = dict(zip(fo, do))
print('fpga byte group -> dram byte:', lane)
for k, kk in lane.items():
    for a, c in zip(extra[k], extra[kk]):
        m[a] = c
    m.update(pair_up(byte[k], byte[kk]))
cmd = ['DDR_A%d' % i for i in range(15)] + ['DDR_BA0', 'DDR_BA1', 'DDR_BA2', 'DDR_RAS_N', 'DDR_CAS_N', 'DDR_WE_N',
                                            'DDR_CKE']
m.update(pair_up(cmd, cmd))
assert sorted(m.values()) == sorted(m.keys())
changed = {a: c for a, c in m.items() if a != c}
json.dump(changed, open(OUT, 'w'), indent=1, sort_keys=True)
print(len(changed), 'nets move; written', OUT)
