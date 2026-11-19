import json
import math
import os
import random
import shutil
import sys

import proute
import rlib

# ddr3l x16 single device: byte lanes on In2, addr/cmd/ctrl + ck on In5 (fly-by fpga -> dram -> vtt),
# 50 ohm 0.23 mm necking to 0.10 mm inside the ball fields, dqs/ck coupled 100 ohm
PCB = sys.argv[1]
SRC = sys.argv[2] if len(sys.argv) > 2 else PCB
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ddr_routes.json')
FPGA_R = (109.5, 79.5, 134.5, 104.5)
DRAM_R = (105.455, 115.505, 121.545, 125.595)
rlib.BGA_RECTS[:] = [FPGA_R + (0.09,), (120.8, 62.35, 179.3, 76.65, 0.10), DRAM_R + (0.09,)]
proute.ESC[:] = [FPGA_R, DRAM_R]
W_OUT, W_IN, CLR = 0.23, 0.10, 0.15
PW, PG, PCLR = 0.115, 0.10, 0.15

LANES = {0: ['DDR_DQ%d' % i for i in range(8)] + ['DDR_DM0'],
         1: ['DDR_DQ%d' % i for i in range(8, 16)] + ['DDR_DM1']}
CMD = ['DDR_A%d' % i for i in range(15)] + ['DDR_BA0', 'DDR_BA1', 'DDR_BA2', 'DDR_RAS_N', 'DDR_CAS_N', 'DDR_WE_N',
                                            'DDR_CKE', 'DDR_ODT']
PAIRS = [('DQS0', 'DDR_DQS0_P', 'DDR_DQS0_N', 'In2.Cu'), ('DQS1', 'DDR_DQS1_P', 'DDR_DQS1_N', 'In2.Cu'),
         ('CK', 'DDR_CK_P', 'DDR_CK_N', 'In5.Cu')]


def load():
    shutil.copy(SRC, PCB)
    return rlib.Board(PCB)


def pad_xy(bd, net, ref):
    for (x, y, hx, hy, n, lays, rnd, p) in bd.pads:
        if n == net and p.GetParentFootprint().GetReference() == ref:
            return (x, y)
    raise KeyError((net, ref))


def ref_of(bd, value_prefix):
    for (x, y, hx, hy, n, lays, rnd, p) in bd.pads:
        f = p.GetParentFootprint()
        if f.GetValue().startswith(value_prefix):
            return f.GetReference()
    raise KeyError(value_prefix)


def via_of(bd, net, ref):
    # follow the fanout dogbone from the ball to its via
    p = pad_xy(bd, net, ref)
    seen, front = {(round(p[0], 3), round(p[1], 3))}, [p]
    while front:
        x, y = front.pop()
        for (vx, vy, vr, n) in bd.vias:
            if n == net and math.hypot(vx - x, vy - y) < 0.02:
                return (vx, vy)
        for (xa, ya, xb, yb, hw, n, ly) in bd.tracks:
            if n != net:
                continue
            for (sx, sy), (ex, ey) in (((xa, ya), (xb, yb)), ((xb, yb), (xa, ya))):
                k = (round(ex, 3), round(ey, 3))
                if math.hypot(sx - x, sy - y) < 0.02 and k not in seen:
                    seen.add(k)
                    front.append((ex, ey))
    v = proute.existing_via(bd, p, net, 1.0)
    if not v:
        raise KeyError(('no dogbone via', net, ref))
    return v


OUTER = tuple(0.75 + 0.25 * i for i in range(14))


def end_via(bd, net, ref, toward, staged):
    # dogbone via if fanout made one; outer-ring balls get a top stub out to a new via
    try:
        return via_of(bd, net, ref)
    except KeyError:
        return proute.drop_via(bd, pad_xy(bd, net, ref), net, toward, staged, radii=OUTER)


def term_pad(bd, net):
    for (x, y, hx, hy, n, lays, rnd, p) in bd.pads:
        f = p.GetParentFootprint()
        if n == net and f.GetValue().startswith('39.2'):
            return (x, y)
    raise KeyError(('no terminator', net))


def stage_neck(bd, pts, net, ly, staged):
    for seg, inside in rlib.split_neck(pts):
        bd.stage_track(seg, W_IN if inside else W_OUT, net, ly, staged)


def route_se(bd, net, a, b_, layers, staged):
    for ly in layers:
        pts = bd.path(ly, a, b_, W_OUT / 2, {net}, CLR, margin=6.0, half_in=W_IN / 2)
        if pts:
            stage_neck(bd, pts, net, ly, staged)
            return ly, pts
    return None, None


def route_all(order):
    bd = load()
    u100, u21 = 'U100', ref_of(bd, 'MT41K256M16TW')
    meta, fails = {}, []
    for kind, item in order:
        if kind == 'pair':
            name, p, n, ly = item
            pre = []
            dram_mid = proute.mid(pad_xy(bd, p, u21), pad_xy(bd, n, u21))
            fpga_mid = proute.mid(pad_xy(bd, p, u100), pad_xy(bd, n, u100))
            sp, sn = end_via(bd, p, u100, dram_mid, pre), end_via(bd, n, u100, dram_mid, pre)
            ep, en = end_via(bd, p, u21, fpga_mid, pre), end_via(bd, n, u21, fpga_mid, pre)
            ok, l = None, 'no end via'
            if sp and sn and ep and en:
                for lyr in (ly, 'In5.Cu' if ly == 'In2.Cu' else 'In2.Cu'):
                    s, l = proute.route_pair(bd, p, n, sp, sn, ep, en, lyr, PW, PG, PCLR)
                    if s:
                        ok = (s, lyr)
                        break
            if not ok:
                bd.unstage(pre)
                fails.append((name, l))
                continue
            bd.commit(pre + ok[0])
            meta[p] = {'group': name, 'layer': ok[1]}
            meta[n] = {'group': name, 'layer': ok[1]}
            continue
        net, group, layers = item
        staged = []
        b_ = end_via(bd, net, u21, pad_xy(bd, net, u100), staged)
        a = end_via(bd, net, u100, b_ or pad_xy(bd, net, u21), staged) if b_ else None
        if not (a and b_):
            bd.unstage(staged)
            fails.append((net, 'no end via'))
            continue
        ly, pts = route_se(bd, net, a, b_, layers, staged)
        if not ly:
            bd.unstage(staged)
            fails.append((net, 'leg1'))
            continue
        rec = {'group': group, 'layer': ly, 'leg1': pts}
        if group == 'CMD':
            # fly-by tail: dram ball via -> via beside the terminator's signal pad
            tp = term_pad(bd, net)
            tv = proute.drop_via(bd, tp, net, b_, staged)
            ly2 = None
            if tv:
                ly2, pts2 = route_se(bd, net, b_, tv, ('In5.Cu', 'In2.Cu', 'B.Cu'), staged)
            if not ly2:
                bd.unstage(staged)
                fails.append((net, 'termination'))
                continue
            rec['tail_layer'] = ly2
        bd.commit(staged)
        meta[net] = rec
    return bd, meta, fails


def build_order(shuffle=None):
    order = [('pair', p) for p in PAIRS]
    se = []
    for k, nets in LANES.items():
        se += [(n, 'LANE%d' % k, ('In2.Cu', 'B.Cu', 'In5.Cu')) for n in nets]
    se += [(n, 'CMD', ('In5.Cu', 'B.Cu', 'In2.Cu')) for n in CMD]
    se += [('DDR_RESET_N', 'RESET', ('In5.Cu', 'In2.Cu', 'B.Cu'))]
    if shuffle is not None:
        random.Random(shuffle).shuffle(se)
    return order + [('se', s) for s in se]


if __name__ == '__main__':
    best = None
    for it in range(int(os.environ.get('PASSES', '4'))):
        order = build_order(None if it == 0 else it)
        if best and best[2]:
            # failed nets first next time
            failed = {f[0] for f in best[2]}
            pairs = [o for o in order if o[0] == 'pair']
            se = [o for o in order if o[0] == 'se']
            order = sorted(pairs, key=lambda o: o[1][0] not in failed) + sorted(se, key=lambda o: o[1][0] not in failed)
        bd, meta, fails = route_all(order)
        print('pass', it, 'routed', len(meta), 'failed', fails, flush=True)
        if best is None or len(fails) < len(best[2]):
            bd.save()
            shutil.copy(PCB, PCB + '.best')
            best = (it, meta, fails)
        if not fails:
            break
    shutil.copy(PCB + '.best', PCB)
    os.remove(PCB + '.best')
    json.dump(best[1], open(OUT, 'w'))
    print('best pass', best[0], 'failed', best[2])
