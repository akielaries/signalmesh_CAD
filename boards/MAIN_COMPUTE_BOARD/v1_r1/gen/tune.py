import math
import sys

import pcbnew

import proute
import rlib

# intra-pair skew tuning: chamfered bumps on the shorter half, away from the partner
PCB = sys.argv[1]
TARGET = 0.15     # mm residual skew
BIG = (0.1, 0.3, 0.35)      # chamfer, flat top, flat between bumps
SMALL = (0.05, 0.2, 0.25)
C, F, GAP_B = BIG
CLR = 0.15
rlib.BGA_RECTS[:] = [(109.5, 79.5, 134.5, 104.5, 0.09), (120.8, 62.35, 179.3, 76.65, 0.10)]

PAIRS = ['GTP0_TX', 'SFP0_TD', 'GTP0_RX', 'SFP0_RD', 'GTP1_TX', 'SFP1_TD', 'GTP1_RX', 'SFP1_RD', 'GTP2_TX',
         'MEZZ_DP0_C2M', 'GTP3_TX', 'MEZZ_DP1_C2M', 'MEZZ_DP0_M2C', 'MEZZ_DP1_M2C', 'GTP_REFCLK1',
         'MEZZ_GBTCLK0_M2C', 'GTP_REFCLK0', '/FPGA_GTP/REFCLK0_OSC']

bd = rlib.Board(PCB)


def tracks_of(net):
    ts = bd.b.Tracks()
    out = []
    for i in range(len(ts)):
        t = ts[i]
        if t.GetClass() != 'PCB_VIA' and t.GetNetname() == net:
            out.append(t)
    return out


def net_len(net):
    return sum(t.GetLength() / 1e6 for t in tracks_of(net))


def bump_pts(a, b_, nrm, amp, k):
    # k bumps centred on segment a-b
    ux, uy = b_[0] - a[0], b_[1] - a[1]
    ll = math.hypot(ux, uy)
    ux, uy = ux / ll, uy / ll
    pitch = 4 * C + F + GAP_B
    span = k * pitch - GAP_B
    s0 = (ll - span) / 2
    pts = [a]
    for i in range(k):
        s = s0 + i * pitch
        prof = [(s, 0), (s + C, C), (s + C, amp - C), (s + 2 * C, amp), (s + 2 * C + F, amp), (s + 3 * C + F, amp - C),
                (s + 3 * C + F, C), (s + 4 * C + F, 0)]
        for (t, h) in prof:
            pts.append((a[0] + ux * t + nrm[0] * h, a[1] + uy * t + nrm[1] * h))
    pts.append(b_)
    return pts


def added(amp, k):
    return k * (2 * (amp - 2 * C) + 4 * C * math.sqrt(2) - 4 * C)


def away_normal(seg, partner_tracks):
    (ax, ay), (bx, by) = seg
    mx, my = (ax + bx) / 2, (ay + by) / 2
    ux, uy = bx - ax, by - ay
    ll = math.hypot(ux, uy)
    nx, ny = -uy / ll, ux / ll
    # side of the closest point on the partner's segments, sampled along this segment
    vote = 0.0
    for f in (0.25, 0.5, 0.75):
        px, py = ax + f * ux, ay + f * uy
        best = None
        for t in partner_tracks:
            sx, sy = t.GetStart().x / 1e6, t.GetStart().y / 1e6
            ex, ey = t.GetEnd().x / 1e6, t.GetEnd().y / 1e6
            dx, dy = ex - sx, ey - sy
            l2 = dx * dx + dy * dy
            k = 0 if l2 == 0 else max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / l2))
            cx, cy = sx + k * dx, sy + k * dy
            dd = math.hypot(cx - px, cy - py)
            if best is None or dd < best[0]:
                best = (dd, cx, cy)
        if best:
            vote += ((best[1] - px) * nx + (best[2] - py) * ny) / max(best[0], 1e-3)
    if vote > 0:
        nx, ny = -nx, -ny
    return nx, ny


def tune_net(short, other, need, end_keep=0.3):
    global C, F, GAP_B
    for geom in (BIG, SMALL):
        C, F, GAP_B = geom
        segs = sorted(tracks_of(short), key=lambda t: -t.GetLength())
        for t in segs:
            if need <= TARGET:
                return need
            ll = t.GetLength() / 1e6
            pitch = 4 * C + F + GAP_B
            kmax = int((ll - 2 * end_keep + GAP_B) / pitch)
            if kmax < 1:
                continue
            a = (t.GetStart().x / 1e6, t.GetStart().y / 1e6)
            b_ = (t.GetEnd().x / 1e6, t.GetEnd().y / 1e6)
            ly = bd.b.GetLayerName(t.GetLayer())
            w = t.GetWidth() / 1e6
            # the existing coupled run sits at the pair gap; allow grid rounding against it
            gmin = (0.17 if ly in ('F.Cu', 'B.Cu') else 0.09) - 0.02
            nrm = away_normal((a, b_), tracks_of(other))
            done = False
            for amp in (0.45, 0.35, 0.25):
                k = min(kmax, max(1, math.ceil(need / added(amp, 1))))
                while k >= 1 and not done:
                    amp_k = amp
                    if added(amp, k) > need:
                        # shrink the amplitude so the total lands on the target
                        amp_k = max(2 * C + 0.02, (need / k + 4 * C - 4 * C * math.sqrt(2)) / 2 + 2 * C)
                    pts = bump_pts(a, b_, nrm, amp_k, k)
                    key = (a[0], a[1], b_[0], b_[1], w / 2, short, ly)
                    cached = [q for q in bd.tracks if q[5] == short and max(abs(q[i] - key[i]) for i in range(4)) < 1e-6]
                    for q in cached:
                        bd.tracks.remove(q)
                    if proute.segs_clear(bd, ly, pts, w / 2, {short}, CLR, partner=(other, gmin)):
                        st = []
                        bd.stage_track(pts, w, short, ly, st)
                        bd.commit(st)
                        bd.b.Remove(t)
                        need -= added(amp_k, k)
                        done = True
                    else:
                        bd.tracks.extend(cached)
                        k -= 1
                if done:
                    break
    return need


report = []
# pass 1: each net pair on its own
for base in PAIRS:
    p, n = base + '_P', base + '_N'
    lp, ln = net_len(p), net_len(n)
    if abs(lp - ln) > TARGET:
        short, other = (p, n) if lp < ln else (n, p)
        tune_net(short, other, abs(lp - ln))
# pass 2: lane totals across the series cap, bumps on whichever leg has room
LANES = [('GTP0_TX', 'SFP0_TD'), ('GTP0_RX', 'SFP0_RD'), ('GTP1_TX', 'SFP1_TD'), ('GTP1_RX', 'SFP1_RD'),
         ('GTP2_TX', 'MEZZ_DP0_C2M'), ('GTP3_TX', 'MEZZ_DP1_C2M'), ('MEZZ_DP0_M2C',), ('MEZZ_DP1_M2C',),
         ('GTP_REFCLK1', 'MEZZ_GBTCLK0_M2C'), ('GTP_REFCLK0', '/FPGA_GTP/REFCLK0_OSC')]
for legs in LANES:
    lp = sum(net_len(b + '_P') for b in legs)
    ln = sum(net_len(b + '_N') for b in legs)
    need = abs(lp - ln)
    sfx = ('_P', '_N') if lp < ln else ('_N', '_P')
    for b in sorted(legs, key=lambda b: -net_len(b + sfx[0])):
        if need <= TARGET:
            break
        need = tune_net(b + sfx[0], b + sfx[1], need)
    lp = sum(net_len(b + '_P') for b in legs)
    ln = sum(net_len(b + '_N') for b in legs)
    report.append((' + '.join(legs), round(lp, 2), round(ln, 2), round(abs(lp - ln), 2),
                   'ok' if abs(lp - ln) <= TARGET + 0.05 else 'short of target'))

bd.save()
for r in report:
    print(r)
