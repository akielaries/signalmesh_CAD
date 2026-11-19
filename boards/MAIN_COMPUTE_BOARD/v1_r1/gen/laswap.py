import json
import os
import sys

import numpy as np
import pcbnew
from scipy.optimize import linear_sum_assignment

# vita la pair swap on the fpga side: within each bank's la set, whole pairs (p and n together)
# re-paired with the connector pins by minimum total straight-line length (crossing-free).
# clock-capable la00/01/17/18 and clk0/1_m2c stay fixed. output: {net now on a ball: net it carries}
b = pcbnew.LoadBoard(sys.argv[1])
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'la_swap.json')
SETS = [['MEZZ_LA%02d' % i for i in range(2, 17)], ['MEZZ_LA%02d' % i for i in range(19, 34)]]
fp, jp = {}, {}
fs = b.Footprints()
for i in range(len(fs)):
    f = fs[i]
    tgt = fp if f.GetReference() == 'U100' else jp if f.GetReference() == 'J20' else None
    if tgt is None:
        continue
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        tgt[p.GetNetname()] = (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)


def mid(d, base):
    return ((d[base + '_P'][0] + d[base + '_N'][0]) / 2, (d[base + '_P'][1] + d[base + '_N'][1]) / 2)


m = {}
for s in SETS:
    cost = np.array([[np.hypot(mid(fp, a)[0] - mid(jp, c)[0], mid(fp, a)[1] - mid(jp, c)[1]) for c in s] for a in s])
    r, c = linear_sum_assignment(cost)
    print('%s..: total %.0f -> %.0f mm' % (s[0], sum(cost[i, i] for i in range(len(s))), cost[r, c].sum()))
    for i, j in zip(r, c):
        if i != j:
            m[s[i] + '_P'] = s[j] + '_P'
            m[s[i] + '_N'] = s[j] + '_N'
json.dump(m, open(OUT, 'w'), indent=1, sort_keys=True)
print(len(m) // 2, 'pairs move')
