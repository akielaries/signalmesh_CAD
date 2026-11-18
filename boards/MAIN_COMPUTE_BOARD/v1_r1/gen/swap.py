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


def mh(a, b):
    # escape routes run along the ball grids, so manhattan distance tracks routed length better
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def balance(fnets, dnets, ref, tol):
    # bottleneck matching: no member longer than ref + tol, the shortest as long as possible, so
    # the length tuner has the least to add
    L = [[mh(fpga[a], dram[c]) for c in dnets] for a in fnets]
    n = len(fnets)

    def match(lo, hi):
        own = {}

        def aug(i, seen):
            for j in range(n):
                if lo <= L[i][j] <= hi and j not in seen:
                    seen.add(j)
                    if j not in own or aug(own[j], seen):
                        own[j] = i
                        return True
            return False
        for i in range(n):
            if not aug(i, set()):
                return None
        return {fnets[i]: dnets[j] for j, i in own.items()}
    hi = ref + tol
    for lo in sorted({v for r in L for v in r if v <= hi}, reverse=True):
        got = match(lo, hi)
        if got:
            print('  balanced: %.1f..%.1f mm (ref %.1f)' % (lo, max(L[fnets.index(a)][dnets.index(c)] for a, c in got.items()), ref))
            return got
    print('  balance failed, keeping crossing-free order')
    return pair_up(fnets, dnets)


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
    ref = (mh(fpga['DDR_DQS%d_P' % k], dram['DDR_DQS%d_P' % kk]) + mh(fpga['DDR_DQS%d_N' % k], dram['DDR_DQS%d_N' % kk])) / 2
    m.update(balance(byte[k], byte[kk], ref, 1.4))
cmd = ['DDR_A%d' % i for i in range(15)] + ['DDR_BA0', 'DDR_BA1', 'DDR_BA2', 'DDR_RAS_N', 'DDR_CAS_N', 'DDR_WE_N',
                                            'DDR_CKE']
ck = (mh(fpga['DDR_CK_P'], dram['DDR_CK_P']) + mh(fpga['DDR_CK_N'], dram['DDR_CK_N'])) / 2
m.update(balance(cmd, cmd, ck, 3.0))
assert sorted(m.values()) == sorted(m.keys())
changed = {a: c for a, c in m.items() if a != c}
json.dump(changed, open(OUT, 'w'), indent=1, sort_keys=True)
print(len(changed), 'nets move; written', OUT)
