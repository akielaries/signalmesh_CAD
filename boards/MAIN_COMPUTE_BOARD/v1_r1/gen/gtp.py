import os
import random
import shutil
import sys

import rlib
import proute

PCB = sys.argv[1]
SRC = sys.argv[2] if len(sys.argv) > 2 else PCB
# always load from the project path; saving a board loaded elsewhere rewrites the .kicad_pro with defaults
shutil.copy(SRC, PCB)
bd = rlib.Board(PCB)
W, GAP = 0.10, 0.18  # outer 100 ohm
CLR = 0.15  # DIFF100 netclass clearance
rlib.BGA_RECTS[:] = [(109.5, 79.5, 134.5, 104.5, 0.09), (120.8, 62.35, 179.3, 76.65, 0.10)]


def pads_of(net, ref=None):
    out = []
    for (x, y, hx, hy, n, lays, rnd, p) in bd.pads:
        if n == net and (ref is None or p.GetParentFootprint().GetReference() == ref):
            out.append((x, y, p.GetParentFootprint().GetReference()))
    return out


def cap_between(na, nb):
    for fp in rlib.L(bd.b.Footprints()):
        nets = {p.GetNetname() for p in rlib.L(fp.Pads())} - {''}
        if nets == {na, nb}:
            return fp.GetReference()
    raise SystemExit('no cap between %s %s' % (na, nb))


def ep(net, ref):
    p = pads_of(net, ref)
    assert p, (net, ref)
    return (p[0][0], p[0][1])


# (name, fpga p/n, far p/n, far ref, caps (fpga-side nets -> far-side nets) or None, caps near 'far' or 'fpga')
LANES = [
    ('SFP0 TX', ('GTP0_TX_P', 'GTP0_TX_N'), ('SFP0_TD_P', 'SFP0_TD_N'), None, 'far'),
    ('SFP0 RX', ('GTP0_RX_P', 'GTP0_RX_N'), ('SFP0_RD_P', 'SFP0_RD_N'), None, 'fpga'),
    ('SFP1 TX', ('GTP1_TX_P', 'GTP1_TX_N'), ('SFP1_TD_P', 'SFP1_TD_N'), None, 'far'),
    ('SFP1 RX', ('GTP1_RX_P', 'GTP1_RX_N'), ('SFP1_RD_P', 'SFP1_RD_N'), None, 'fpga'),
    ('VITA DP0 C2M', ('GTP2_TX_P', 'GTP2_TX_N'), ('MEZZ_DP0_C2M_P', 'MEZZ_DP0_C2M_N'), None, 'far'),
    ('VITA DP1 C2M', ('GTP3_TX_P', 'GTP3_TX_N'), ('MEZZ_DP1_C2M_P', 'MEZZ_DP1_C2M_N'), None, 'far'),
    ('REFCLK1 (VITA)', ('GTP_REFCLK1_P', 'GTP_REFCLK1_N'), ('MEZZ_GBTCLK0_M2C_P', 'MEZZ_GBTCLK0_M2C_N'), None, 'fpga'),
    ('REFCLK0 (125M)', ('GTP_REFCLK0_P', 'GTP_REFCLK0_N'), ('/FPGA_GTP/REFCLK0_OSC_P', '/FPGA_GTP/REFCLK0_OSC_N'), None, 'fpga'),
]
DIRECT = [('VITA DP0 M2C', ('MEZZ_DP0_M2C_P', 'MEZZ_DP0_M2C_N')), ('VITA DP1 M2C', ('MEZZ_DP1_M2C_P', 'MEZZ_DP1_M2C_N'))]



INNER_ONLY = tuple(os.environ.get('INNER', 'In2.Cu,In5.Cu').split(','))


def reserve_conn_vias(bd):
    # drop the vita-side vias for every lane first so no lane routes over another's via spots
    fm = proute.mid(ep('GTP2_TX_P', 'U100'), ep('GTP3_TX_P', 'U100'))
    staged = []
    for lane in ALL:
        nets = lane[2] if lane[-1] == 'cap' else lane[1]
        for net in nets:
            if not pads_of(net, 'J20'):
                continue
            if not proute.drop_via(bd, ep(net, 'J20'), net, fm, staged):
                print('no via spot for', net)
    bd.commit(staged)


def route_lane(bd, lane):
    name, kind = lane[0], lane[-1]
    if kind == 'direct':
        np_, nn = lane[1]
        far = [q for q in pads_of(np_) if q[2] != 'U100'][0][2]
        s, l = proute.route_pair_any(bd, np_, nn, ep(np_, 'U100'), ep(nn, 'U100'), ep(np_, far), ep(nn, far), CLR,
                                     layers=INNER_ONLY if far == 'J20' else ('F.Cu',) + INNER_ONLY)
        if s:
            bd.commit(s)
            return (name, 'ok', l)
        return (name, 'fail', l)
    _, (fp_, fn), (xp, xn), _, near, _ = lane
    cp, cn = cap_between(fp_, xp), cap_between(fn, xn)
    fpga_mid = proute.mid(ep(fp_, 'U100'), ep(fn, 'U100'))
    far_ref = [q for q in pads_of(xp) if q[2] not in (cp, cn)][0][2]
    far_mid = proute.mid(ep(xp, far_ref), ep(xn, far_ref))
    tried = []
    for order in ((cp, cn), (cn, cp)):
        if near == 'far':
            ok = proute.place_pair_caps(bd, order, fpga_mid, far_mid, dist_list=tuple(x * 0.5 for x in range(4, 56)),
                                        toward_nets=(fp_, fn))
        else:
            ok = proute.place_pair_caps(bd, order, far_mid, fpga_mid, dist_list=tuple(x * 0.5 for x in range(8, 36)),
                                        toward_nets=(xp, xn))
        if not ok:
            tried.append('placement')
            continue
        s1, l1 = proute.route_pair_any(bd, fp_, fn, ep(fp_, 'U100'), ep(fn, 'U100'), ep(fp_, cp), ep(fn, cn), CLR)
        s2, l2 = (None, 'skipped') if not s1 else proute.route_pair_any(
            bd, xp, xn, ep(xp, cp), ep(xn, cn), ep(xp, far_ref), ep(xn, far_ref), CLR,
            layers=INNER_ONLY if far_ref == 'J20' else ('F.Cu',) + INNER_ONLY)
        if s1 and s2:
            bd.commit(s1 + s2)
            return (name, 'ok', 'fpga leg', l1, 'far leg', l2)
        if s1:
            bd.unstage(s1)
        tried.append((l1 if not s1 else 'leg1 ok', l2 if not s2 else 'leg2 ok'))
    return (name, 'fail', tried)


ALL = [l + ('cap',) for l in LANES] + [d + ('direct',) for d in DIRECT]
ONLY = os.environ.get('ONLY')
if ONLY:
    ALL = [l for l in ALL if any(k in l[0] for k in ONLY.split(','))]
order = list(range(len(ALL)))
best = None
rng = random.Random(1)
for it in range(int(os.environ.get("PASSES", "3"))):
    shutil.copy(SRC, PCB)
    bd = rlib.Board(PCB)
    reserve_conn_vias(bd)
    bd.reload()
    rep = [route_lane(bd, ALL[i]) for i in order]
    nok = sum(r[1] == 'ok' for r in rep)
    print('pass', it, nok, '/', len(ALL), [ALL[i][0] for i in order if rep[order.index(i)][1] != 'ok'], flush=True)
    if best is None or nok > best[0]:
        best = (nok, list(order), rep)
        bd.save()
        shutil.copy(PCB, PCB + '.best')
    if nok == len(ALL):
        break
    failed = [i for i, r in zip(order, rep) if r[1] != 'ok']
    rest = [i for i in order if i not in failed]
    if it and nok <= best[0]:
        rng.shuffle(rest)
    order = failed + rest
shutil.copy(PCB + '.best', PCB)
os.remove(PCB + '.best')
for r in best[2]:
    print(r)
