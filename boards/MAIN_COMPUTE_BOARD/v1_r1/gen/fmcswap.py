import json
import os
import sys

import numpy as np
import pcbnew
from scipy.optimize import linear_sum_assignment

# fmc pin swap on the fpga side: within each swappable set, give each stm32 pin the fpga ball that
# minimises total straight-line length (hungarian, crossing-free). d0-d15 (selectmap data), fmc_clk
# (clock-capable pin) and the config pins stay fixed. output: {net now on an fpga ball: net it carries}
b = pcbnew.LoadBoard(sys.argv[1])
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), sys.argv[2] if len(sys.argv) > 2 else 'fmc_swap.json')
SETS = [['FMC_D%d' % i for i in range(16, 32)], ['FMC_A%d' % i for i in range(19)],
        ['FMC_NOE', 'FMC_NWE', 'FMC_NE1', 'FMC_NWAIT', 'FMC_NBL0', 'FMC_NBL1', 'FMC_NBL2', 'FMC_NBL3']]
fp, sp = {}, {}
fs = b.Footprints()
for i in range(len(fs)):
    f = fs[i]
    tgt = fp if f.GetReference() == 'U100' else sp if f.GetValue().startswith('STM32H755') else None
    if tgt is None:
        continue
    for k in range(len(f.Pads())):
        p = f.Pads()[k]
        tgt[p.GetNetname()] = (p.GetPosition().x / 1e6, p.GetPosition().y / 1e6)
m = {}
for s in SETS:
    # euclidean: the minimum-total assignment of straight connections has no crossings
    cost = np.array([[np.hypot(fp[a][0] - sp[c][0], fp[a][1] - sp[c][1]) for c in s] for a in s])
    r, c = linear_sum_assignment(cost)
    before = sum(cost[i, i] for i in range(len(s)))
    after = cost[r, c].sum()
    print('%s..: total %.0f -> %.0f mm' % (s[0], before, after))
    m.update({s[i]: s[j] for i, j in zip(r, c) if i != j})
json.dump(m, open(OUT, 'w'), indent=1, sort_keys=True)
print(len(m), 'nets move')
