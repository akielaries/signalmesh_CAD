import math
import re
import sys

import pcbnew

MM = 1e6
PCB = sys.argv[1]
b = pcbnew.LoadBoard(PCB)
F, B = pcbnew.F_Cu, pcbnew.B_Cu
CLR = 0.1


def L(v):
    if hasattr(v, 'size'):
        return [v[i] for i in range(v.size())]
    return [v[i] for i in range(len(v))]


def P(x, y):
    return pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM)))


# copper obstacles: (kind, layerset 'F'/'B'/'*', x, y, r) circles, and segments
circles = []   # (x, y, r, net, layers)
segs = []      # (x1, y1, x2, y2, half_w, net, layer)


def pad_obstacles():
    for fp in L(b.Footprints()):
        for p in L(fp.Pads()):
            pos = p.GetPosition()
            bb = p.GetBoundingBox()
            r = max(bb.GetWidth(), bb.GetHeight()) / 2 / MM
            rr = min(bb.GetWidth(), bb.GetHeight()) / 2 / MM
            thr = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            lay = '*' if thr else ('B' if p.IsOnLayer(B) else 'F')
            if bb.GetWidth() > 1.6 * bb.GetHeight() or bb.GetHeight() > 1.6 * bb.GetWidth():
                # elongated pad as a fat segment
                if bb.GetWidth() > bb.GetHeight():
                    segs.append((bb.GetX() / MM + rr, pos.y / MM, bb.GetRight() / MM - rr, pos.y / MM, rr,
                                 p.GetNetname(), lay))
                else:
                    segs.append((pos.x / MM, bb.GetY() / MM + rr, pos.x / MM, bb.GetBottom() / MM - rr, rr,
                                 p.GetNetname(), lay))
            else:
                circles.append((pos.x / MM, pos.y / MM, r, p.GetNetname(), lay))


def dseg(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def layers_hit(a, b_):
    return a == '*' or b_ == '*' or a == b_


VIAS = []  # (x, y) of every drilled via, any net


def via_ok(x, y, r, net, clr=CLR):
    # drill to drill spacing applies regardless of net (0.25 mm wall between 0.2 mm drills)
    for (vx, vy) in VIAS:
        if math.hypot(x - vx, y - vy) < 0.2 + 0.25:
            return False
    for (cx, cy, cr, cn, cl) in circles:
        if cn == net and cn:
            continue
        if math.hypot(x - cx, y - cy) < r + cr + clr:
            return False
    for (x1, y1, x2, y2, hw, sn, sl) in segs:
        if sn == net and sn:
            continue
        if dseg(x, y, x1, y1, x2, y2) < r + hw + clr:
            return False
    # board edge, and the card-guide strips (keepouts up to y 53 and from y 147) by the via's edge
    if x - r < 50.5 or x + r > 209.5 or y - r < 53.05 or y + r > 146.95:
        return False
    return True


def seg_ok(x1, y1, x2, y2, hw, net, layer, clr=CLR):
    steps = max(2, int(math.hypot(x2 - x1, y2 - y1) / 0.05))
    for (cx, cy, cr, cn, cl) in circles:
        if (cn == net and cn) or not layers_hit(cl, layer):
            continue
        if dseg(cx, cy, x1, y1, x2, y2) < cr + hw + clr:
            return False
    for (a1, b1, a2, b2, w2, sn, sl) in segs:
        if (sn == net and sn) or not layers_hit(sl, layer):
            continue
        for i in range(steps + 1):
            t = i / steps
            if dseg(x1 + t * (x2 - x1), y1 + t * (y2 - y1), a1, b1, a2, b2) < hw + w2 + clr:
                return False
    return True


def add_via(x, y, net, d=0.45, drill=0.2):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(P(x, y))
    v.SetWidth(int(d * MM))
    v.SetDrill(int(drill * MM))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetNet(b.FindNet(net))
    b.Add(v)
    circles.append((x, y, d / 2, net, '*'))
    VIAS.append((x, y))
    return v


def add_track(x1, y1, x2, y2, w, net, layer):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(P(x1, y1))
    t.SetEnd(P(x2, y2))
    t.SetWidth(int(w * MM))
    t.SetLayer(layer)
    t.SetNet(b.FindNet(net))
    b.Add(t)
    segs.append((x1, y1, x2, y2, w / 2, net, 'F' if layer == F else 'B'))


# fanout expects a freshly placed board (pcbbuild.py, then planes.py)
if len(L(b.Tracks())):
    raise SystemExit('board already has tracks/vias; rebuild with pcbbuild.py + planes.py first')
pad_obstacles()

POWER = re.compile(r'^(GND|GNDADC|\+.*|VADJ|VTT_DDR|VREF_DDR|VCCADC)$')
stats = {}


def bga_fanout(ref, pitch, via_d, ring_skip, sig_w):
    fp = b.FindFootprintByReference(ref)
    cx, cy = fp.GetPosition().x / MM, fp.GetPosition().y / MM
    pads = [p for p in L(fp.Pads()) if p.GetNetname() and not p.GetNetname().startswith('unconnected-')]
    xs = sorted({round(p.GetPosition().x / MM, 3) for p in L(fp.Pads())})
    ys = sorted({round(p.GetPosition().y / MM, 3) for p in L(fp.Pads())})
    h = pitch / 2
    balls = {}
    for p in pads:
        px, py = round(p.GetPosition().x / MM, 3), round(p.GetPosition().y / MM, 3)
        ci, ri = xs.index(px), ys.index(py)
        ring = min(ci, len(xs) - 1 - ci, ri, len(ys) - 1 - ri)
        balls[(px, py)] = (p.GetNetname(), ring)

    def slots_of(px, py):
        sx = 1 if px >= cx else -1
        sy = 1 if py >= cy else -1
        out = []
        for dx, dy in ((sx, sy), (sx, -sy), (-sx, sy), (-sx, -sy)):
            k = (round(px + dx * h, 3), round(py + dy * h, 3))
            if via_ok(k[0], k[1], via_d / 2, '', 0.09) or True:
                out.append(k)
        return out

    # ddr balls always get a via: their routes go to inner layers, not out over the top
    sig = [k for k, (n, r) in balls.items() if not POWER.match(n) and (r >= ring_skip or n.startswith('DDR_'))]
    pwr = [k for k, (n, r) in balls.items() if POWER.match(n)]
    n_skip = sum(1 for k, (n, r) in balls.items() if not POWER.match(n) and r < ring_skip and not n.startswith('DDR_'))

    # 1) maximum bipartite matching: each signal ball gets its own slot (kuhn's algorithm)
    adj = {k: slots_of(*k) for k in sig}
    owner = {}

    def try_assign(k, seen):
        for s in adj[k]:
            if s in seen:
                continue
            seen.add(s)
            if s not in owner or try_assign(owner[s], seen):
                owner[s] = k
                return True
        return False

    # outer rings first gives shorter escapes priority on the outward diagonal
    for k in sorted(sig, key=lambda k: balls[k][1]):
        try_assign(k, set())
    sig_slot = {v: s for s, v in owner.items()}
    used = set(owner)

    n_ok = n_fail = 0
    for k in sig:
        if k not in sig_slot:
            n_fail += 1
            continue
        vx, vy = sig_slot[k]
        net = balls[k][0]
        add_via(vx, vy, net, via_d, 0.2)
        add_track(k[0], k[1], vx, vy, sig_w, net, F)
        n_ok += 1

    # 2) supply balls share free slots; 3) otherwise hop to an adjacent same-net ball
    pvia = {}
    pending = []
    for k in sorted(pwr, key=lambda k: -sum(1 for s in slots_of(*k) if s not in used)):
        net = balls[k][0]
        got = None
        for s in slots_of(*k):
            if pvia.get(s) == net:
                got = s
                break
        if not got:
            best, bestn = None, -1
            for s in slots_of(*k):
                if s in used:
                    continue
                n_same = sum(1 for ex in (-h, h) for ey in (-h, h)
                             if balls.get((round(s[0] + ex, 3), round(s[1] + ey, 3)), ('',))[0] == net)
                if n_same > bestn:
                    best, bestn = s, n_same
            if best:
                add_via(best[0], best[1], net, via_d, 0.2)
                used.add(best)
                pvia[best] = net
                got = best
        if got:
            add_track(k[0], k[1], got[0], got[1], 0.2, net, F)
            n_ok += 1
        else:
            pending.append(k)
    linked = {k for k in pwr if k not in pending}
    for k in pending:
        net = balls[k][0]
        for ex, ey in ((pitch, 0), (-pitch, 0), (0, pitch), (0, -pitch)):
            nb = (round(k[0] + ex, 3), round(k[1] + ey, 3))
            if nb in linked and balls[nb][0] == net:
                add_track(k[0], k[1], nb[0], nb[1], 0.2, net, F)
                n_ok += 1
                break
        else:
            n_fail += 1
    stats[ref] = (n_ok, n_skip, n_fail)


bga_fanout('U100', 1.0, 0.45, 2, 0.1)
def ref_by_value(prefix):
    fs = b.Footprints()
    return [fs[i].GetReference() for i in range(len(fs)) if fs[i].GetValue().startswith(prefix)][0]


bga_fanout(ref_by_value('MT41K256M16TW'), 0.8, 0.4, 0, 0.1)

# stm32 supply/ground pins: via just past the pad tip
fp = b.FindFootprintByReference(ref_by_value('STM32H755'))
cx, cy = fp.GetPosition().x / MM, fp.GetPosition().y / MM
n = 0
for p in L(fp.Pads()):
    net = p.GetNetname()
    if not net or not (POWER.match(net) or net == '/STM32/VCAP'):
        continue
    px, py = p.GetPosition().x / MM, p.GetPosition().y / MM
    if abs(px - cx) > abs(py - cy):
        ux, uy = (1 if px > cx else -1), 0
    else:
        ux, uy = 0, (1 if py > cy else -1)
    for off in (1.25, 1.6, 2.0):
        for lat in (0.0, 0.5, -0.5):
            vx, vy = px + ux * off + uy * lat, py + uy * off + ux * lat
            if via_ok(vx, vy, 0.225, net) and seg_ok(px, py, vx, vy, 0.125, net, 'F'):
                add_via(vx, vy, net)
                add_track(px, py, vx, vy, 0.25, net, F)
                n += 1
                break
        else:
            continue
        break
stats['U11 pins'] = n

# bottom-side passives (decoupling): reuse a nearby same-net via or drop a new one
vias_by_net = {}
for (x, y, r, net, lay) in circles:
    if lay == '*' and r < 0.3:
        vias_by_net.setdefault(net, []).append((x, y))
n_reuse = n_new = n_fail = 0
for fp in L(b.Footprints()):
    if not fp.IsFlipped() or fp.GetPadCount() > 3:
        continue
    for p in L(fp.Pads()):
        net = p.GetNetname()
        if not net:
            continue
        px, py = p.GetPosition().x / MM, p.GetPosition().y / MM
        best = None
        for (vx, vy) in sorted(vias_by_net.get(net, []), key=lambda v: math.hypot(v[0] - px, v[1] - py))[:6]:
            dd = math.hypot(vx - px, vy - py)
            if dd > 1.8:
                break
            if seg_ok(px, py, vx, vy, 0.1, net, 'B'):
                best = (vx, vy)
                break
        if best:
            add_track(px, py, best[0], best[1], 0.2, net, B)
            n_reuse += 1
            continue
        # new via along the pad's long axis, away from the other pad
        other = [q for q in L(fp.Pads()) if q.GetNumber() != p.GetNumber()]
        ox, oy = (other[0].GetPosition().x / MM, other[0].GetPosition().y / MM) if other else (px - 1, py)
        ax, ay = px - ox, py - oy
        al = math.hypot(ax, ay) or 1.0
        ax, ay = ax / al, ay / al
        done = False
        for off in (0.55, 0.75, 1.0, 1.3):
            for lat in (0.0, 0.45, -0.45, 0.8, -0.8):
                vx, vy = px + ax * off - ay * lat, py + ay * off + ax * lat
                if via_ok(vx, vy, 0.225, net) and seg_ok(px, py, vx, vy, 0.1, net, 'B'):
                    add_via(vx, vy, net)
                    add_track(px, py, vx, vy, 0.2, net, B)
                    vias_by_net.setdefault(net, []).append((vx, vy))
                    done = True
                    break
            if done:
                break
        if done:
            n_new += 1
        else:
            n_fail += 1
stats['bottom passives'] = (n_reuse, n_new, n_fail)

# top-side smd pads on gnd or a plane-backed rail: stitch to the plane with a short via
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
plane_layer = {}
for z in L(b.Zones()):
    if z.GetIsRuleArea():
        continue
    plane_layer.setdefault(z.GetNetname(), []).append(z)


def plane_at(net, x, y):
    for z in plane_layer.get(net, []):
        if z.HitTestFilledArea(z.GetLayer(), P(x, y), 0):
            return True
    return False


n_top = n_topfail = 0
SKIP = {'U100', 'U21', 'U11'}
for fp in L(b.Footprints()):
    if fp.GetReference() in SKIP or (fp.IsFlipped() and fp.GetPadCount() <= 3):
        continue
    lay_s, lay_l = ('B', B) if fp.IsFlipped() else ('F', F)
    fcx, fcy = fp.GetPosition().x / MM, fp.GetPosition().y / MM
    for p in L(fp.Pads()):
        net = p.GetNetname()
        if not net or net not in plane_layer:
            continue
        if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
            continue
        px, py = p.GetPosition().x / MM, p.GetPosition().y / MM
        # reuse a same-net via already close by
        near = [(vx, vy) for (vx, vy) in vias_by_net.get(net, []) if math.hypot(vx - px, vy - py) < 1.2]
        if near and seg_ok(px, py, near[0][0], near[0][1], 0.125, net, lay_s):
            add_track(px, py, near[0][0], near[0][1], 0.25, net, lay_l)
            n_top += 1
            continue
        ax, ay = px - fcx, py - fcy
        al = math.hypot(ax, ay)
        if al < 0.05:
            ax, ay, al = 1.0, 0.0, 1.0
        ax, ay = ax / al, ay / al
        sz = max(p.GetSize().x, p.GetSize().y) / MM / 2
        done = False
        for off in (sz + 0.4, sz + 0.65, sz + 0.95, sz + 1.3):
            for ang in (0, 35, -35, 70, -70, 110, -110, 180):
                ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                dx, dy = ax * ca - ay * sa, ax * sa + ay * ca
                vx, vy = px + dx * off, py + dy * off
                if not plane_at(net, vx, vy):
                    continue
                if via_ok(vx, vy, 0.225, net) and seg_ok(px, py, vx, vy, 0.125, net, lay_s):
                    add_via(vx, vy, net)
                    add_track(px, py, vx, vy, 0.25, net, lay_l)
                    vias_by_net.setdefault(net, []).append((vx, vy))
                    done = True
                    break
            if done:
                break
        if done:
            n_top += 1
        else:
            n_topfail += 1
stats['ic/connector pads to planes'] = (n_top, n_topfail)

filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
b.Save(PCB)
for k, v in stats.items():
    print(k, v)
