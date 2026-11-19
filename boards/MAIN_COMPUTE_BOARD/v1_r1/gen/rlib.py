import math

import numpy as np
import pcbnew
from scipy import ndimage
from skimage.draw import polygon as fill_poly
from skimage.graph import MCP_Geometric

MM = 1e6
G = 0.025         # grid pitch, mm
MARGIN = 0.02     # extra over the drc clearance to absorb grid quantisation (G*sqrt2/2 ~ 0.018)
LAYERS = {'F.Cu': pcbnew.F_Cu, 'In2.Cu': pcbnew.In2_Cu, 'In5.Cu': pcbnew.In5_Cu, 'B.Cu': pcbnew.B_Cu}
BGA_RECTS = []    # (x0, y0, x1, y1, clr) regions where a reduced escape clearance applies


def L(v):
    if hasattr(v, 'size'):
        return [v[i] for i in range(v.size())]
    if isinstance(v, (list, tuple)):
        return list(v)
    return [v[i] for i in range(len(v))]


def outline_pts(sps):
    pts = []
    o = sps.Outline(0)
    for i in range(o.PointCount()):
        p = o.CPoint(i)
        pts.append((p.x / MM, p.y / MM))
    return pts


class Board:
    def __init__(self, path):
        self.fname = path
        self.b = pcbnew.LoadBoard(path)
        self.reload()

    def reload(self):
        b = self.b
        self.pads = []
        for fp in L(b.Footprints()):
            for p in L(fp.Pads()):
                bb = p.GetBoundingBox()
                lays = {n for n, lid in LAYERS.items() if p.IsOnLayer(lid)}
                if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                    lays = set(LAYERS)
                self.pads.append((p.GetPosition().x / MM, p.GetPosition().y / MM, bb.GetWidth() / 2 / MM,
                                  bb.GetHeight() / 2 / MM, p.GetNetname(), lays,
                                  p.GetShape() == pcbnew.PAD_SHAPE_CIRCLE, p))
        self.vias, self.tracks = [], []
        for t in L(b.Tracks()):
            if t.GetClass() == 'PCB_VIA':
                self.vias.append((t.GetPosition().x / MM, t.GetPosition().y / MM,
                                  t.Cast().GetWidth(pcbnew.F_Cu) / 2 / MM, t.GetNetname()))
            else:
                ln = b.GetLayerName(t.GetLayer())
                if ln in LAYERS:
                    self.tracks.append((t.GetStart().x / MM, t.GetStart().y / MM, t.GetEnd().x / MM,
                                        t.GetEnd().y / MM, t.GetWidth() / 2 / MM, t.GetNetname(), ln))
        # copper pours on routing layers: other nets must not cut through them
        self.pours = []
        for z in L(b.Zones()):
            if z.GetIsRuleArea():
                continue
            ln = b.GetLayerName(z.GetLayer())
            if ln in LAYERS:
                self.pours.append((outline_pts(z.Outline()), ln, z.GetNetname()))
        # track keepouts: board rule areas and rule areas inside footprints
        self.keepouts = []
        zones = list(L(b.Zones()))
        for fp in L(b.Footprints()):
            zones += L(fp.Zones())
        for z in zones:
            if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
                lays = {n for n, lid in LAYERS.items() if z.GetLayerSet().Contains(lid)}
                self.keepouts.append((outline_pts(z.Outline()), lays))

    def net_points(self, net):
        pts = [(x, y, 'pad', lays, p) for (x, y, hx, hy, n, lays, rnd, p) in self.pads if n == net]
        pts += [(x, y, 'via', set(LAYERS), None) for (x, y, r, n) in self.vias if n == net]
        return pts

    # ---------- rasterisation

    def _raster(self, layer, win, reach, own, only=None):
        x0, y0, x1, y1 = win
        nx, ny = int(round((x1 - x0) / G)) + 1, int(round((y1 - y0) / G)) + 1
        blocked = np.zeros((ny, nx), bool)
        xs = x0 + np.arange(nx) * G
        ys = y0 + np.arange(ny) * G

        def box(cx, cy, rx, ry):
            return (max(0, int((cx - rx - x0) / G)), min(nx, int((cx + rx - x0) / G) + 2),
                    max(0, int((cy - ry - y0) / G)), min(ny, int((cy + ry - y0) / G) + 2))

        def mark(b4, fn):
            i0, i1, j0, j1 = b4
            if i0 < i1 and j0 < j1:
                X, Y = np.meshgrid(xs[i0:i1], ys[j0:j1])
                blocked[j0:j1, i0:i1] |= fn(X, Y)

        m = reach
        for (x, y, hx, hy, n, lays, rnd, p) in self.pads:
            if layer not in lays or n in own or (only is not None and n != only):
                continue
            if x + hx + m < x0 or x - hx - m > x1 or y + hy + m < y0 or y - hy - m > y1:
                continue
            if rnd and abs(hx - hy) < 1e-3:
                r = hx + m
                mark(box(x, y, r, r), lambda X, Y, x=x, y=y, r=r: (X - x) ** 2 + (Y - y) ** 2 < r * r)
            else:
                def f(X, Y, x=x, y=y, hx=hx, hy=hy):
                    dx = np.maximum(np.abs(X - x) - hx, 0)
                    dy = np.maximum(np.abs(Y - y) - hy, 0)
                    return dx * dx + dy * dy < m * m
                mark(box(x, y, hx + m, hy + m), f)
        for (x, y, r, n) in self.vias:
            if n in own or (only is not None and n != only):
                continue
            rr = r + m
            if x + rr < x0 or x - rr > x1 or y + rr < y0 or y - rr > y1:
                continue
            mark(box(x, y, rr, rr), lambda X, Y, x=x, y=y, rr=rr: (X - x) ** 2 + (Y - y) ** 2 < rr * rr)
        for (xa, ya, xb, yb, hw, n, ly) in self.tracks:
            if ly != layer or n in own or (only is not None and n != only):
                continue
            rr = hw + m
            if max(xa, xb) + rr < x0 or min(xa, xb) - rr > x1 or max(ya, yb) + rr < y0 or min(ya, yb) - rr > y1:
                continue

            def f(X, Y, xa=xa, ya=ya, xb=xb, yb=yb, rr=rr):
                dx, dy = xb - xa, yb - ya
                ll = dx * dx + dy * dy
                t = 0 if ll == 0 else np.clip(((X - xa) * dx + (Y - ya) * dy) / ll, 0, 1)
                return (X - (xa + t * dx)) ** 2 + (Y - (ya + t * dy)) ** 2 < rr * rr
            mark(box((xa + xb) / 2, (ya + yb) / 2, abs(xb - xa) / 2 + rr, abs(yb - ya) / 2 + rr), f)
        return blocked, xs, ys

    def grid(self, layer, win, half_w, own, clr, free=(), margin=MARGIN, partner=None, half_in=None, pours=True):
        x0, y0, x1, y1 = win
        blocked, xs, ys = self._raster(layer, win, half_w + clr + margin, own)
        for (bx0, by0, bx1, by1, bclr) in BGA_RECTS:
            ii = np.where((xs >= bx0) & (xs <= bx1))[0]
            jj = np.where((ys >= by0) & (ys <= by1))[0]
            if not len(ii) or not len(jj):
                continue
            sub = (xs[ii[0]], ys[jj[0]], xs[ii[-1]], ys[jj[-1]])
            hin = half_w if half_in is None else half_in
            sb, _, _ = self._raster(layer, sub, hin + min(bclr, clr) + margin, own)
            h = min(sb.shape[0], len(jj))
            w = min(sb.shape[1], len(ii))
            blocked[jj[0]:jj[0] + h, ii[0]:ii[0] + w] = sb[:h, :w]
        for pts, lays in self.keepouts:
            if layer not in lays or not pts:
                continue
            px = np.array([(x - x0) / G for x, y in pts])
            py = np.array([(y - y0) / G for x, y in pts])
            if px.max() < 0 or px.min() > blocked.shape[1] or py.max() < 0 or py.min() > blocked.shape[0]:
                continue
            rr, cc = fill_poly(py, px, shape=blocked.shape)
            k = np.zeros_like(blocked)
            k[rr, cc] = True
            k = ndimage.binary_dilation(k, iterations=max(1, int(math.ceil((half_w + 0.05) / G))))
            blocked |= k
        if partner:
            # diff pair partner: kicad checks it against diff_pair_gap, not clearance
            pn, pclr = partner
            pb, _, _ = self._raster(layer, win, half_w + pclr + margin, set(), only=pn)
            blocked |= pb
        for pts, ly, net in (self.pours if pours else ()):
            if ly != layer or net in own or not pts:
                continue
            px = np.array([(x - x0) / G for x, y in pts])
            py = np.array([(y - y0) / G for x, y in pts])
            if px.max() < 0 or px.min() > blocked.shape[1] or py.max() < 0 or py.min() > blocked.shape[0]:
                continue
            rr, cc = fill_poly(py, px, shape=blocked.shape)
            k = np.zeros_like(blocked)
            k[rr, cc] = True
            k = ndimage.binary_dilation(k, iterations=max(1, int(math.ceil((half_w + 0.2) / G))))
            blocked |= k
        e = 0.35 + half_w
        blocked[:, xs < 50 + e] = True
        blocked[:, xs > 210 - e] = True
        blocked[ys < 50 + e, :] = True
        blocked[ys > 150 - e, :] = True
        for (fx, fy, fr) in free:
            i0, i1 = max(0, int((fx - fr - x0) / G)), min(blocked.shape[1], int((fx + fr - x0) / G) + 2)
            j0, j1 = max(0, int((fy - fr - y0) / G)), min(blocked.shape[0], int((fy + fr - y0) / G) + 2)
            if i0 < i1 and j0 < j1:
                X, Y = np.meshgrid(xs[i0:i1], ys[j0:j1])
                blocked[j0:j1, i0:i1] &= ~((X - fx) ** 2 + (Y - fy) ** 2 < fr * fr)
        return blocked, xs, ys

    # ---------- search

    def path(self, layer, a, b_, half_w, own, clr, margin=4.0, free=(), follow=None, follow_d=None,
             wide=0.0, wide_except=(), partner=None, half_in=None):
        x0 = min(a[0], b_[0]) - margin
        x1 = max(a[0], b_[0]) + margin
        y0 = min(a[1], b_[1]) - margin
        y1 = max(a[1], b_[1]) + margin
        own = set(own)
        if partner:
            own.add(partner[0])
        blocked, xs, ys = self.grid(layer, (x0, y0, x1, y1), half_w, own, clr, free, partner=partner, half_in=half_in)
        if wide > 0:
            # keep a wider corridor clear (room for a partner track) except near the given points
            bw, _, _ = self.grid(layer, (x0, y0, x1, y1), half_w + wide, own, clr, free)
            X, Y = np.meshgrid(xs, ys)
            near = np.zeros(blocked.shape, bool)
            for (cx, cy, cr) in wide_except:
                near |= (X - cx) ** 2 + (Y - cy) ** 2 < cr * cr
            blocked = np.where(near, blocked, bw)
        cost = np.ones(blocked.shape)
        if follow is not None:
            ref = np.zeros(blocked.shape, bool)
            for (xa, ya), (xb, yb) in zip(follow, follow[1:]):
                n = max(2, int(math.hypot(xb - xa, yb - ya) / (G / 2)))
                for k in range(n + 1):
                    t = k / n
                    i = int(round((xa + t * (xb - xa) - x0) / G))
                    j = int(round((ya + t * (yb - ya) - y0) / G))
                    if 0 <= j < ref.shape[0] and 0 <= i < ref.shape[1]:
                        ref[j, i] = True
            dist = ndimage.distance_transform_edt(~ref) * G
            cost = 1.0 + np.clip(np.abs(dist - follow_d) / 0.05, 0, 10) * 1.5
            # the partner is excluded from the normal obstacles; keep the pair gap to it explicitly
            blocked = blocked | (dist < follow_d - 0.03)
        cost[blocked] = np.inf
        ia = (int(round((a[1] - y0) / G)), int(round((a[0] - x0) / G)))
        ib = (int(round((b_[1] - y0) / G)), int(round((b_[0] - x0) / G)))
        for (j, i) in (ia, ib):
            cost[max(0, j - 1):j + 2, max(0, i - 1):i + 2] = 1.0
        mcp = MCP_Geometric(cost, fully_connected=True)
        cum, _ = mcp.find_costs([ia], [ib])
        if not np.isfinite(cum[ib]):
            return None
        pts = [(x0 + i * G, y0 + j * G) for (j, i) in mcp.traceback(ib)]
        pts[0] = (a[0], a[1])
        pts[-1] = (b_[0], b_[1])
        # the free squares at the ends let the trace leave a pad/via through blocked cells
        free = np.zeros(blocked.shape, bool)
        for (j, i) in (ia, ib):
            free[max(0, j - 1):j + 2, max(0, i - 1):i + 2] = True
        return pull_tight(simplify(pts), blocked & ~free, x0, y0)

    # ---------- staged edits

    def stage_track(self, pts, w, net, layer, staged):
        for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
            if math.hypot(xb - xa, yb - ya) > 1e-4:
                staged.append(('t', xa, ya, xb, yb, w, net, layer))
                self.tracks.append((xa, ya, xb, yb, w / 2, net, layer))

    def stage_via(self, x, y, net, staged, d=0.45, drill=0.2):
        staged.append(('v', x, y, d, drill, net))
        self.vias.append((x, y, d / 2, net))

    def unstage(self, staged):
        for s in staged:
            if s[0] == 't':
                self.tracks.remove((s[1], s[2], s[3], s[4], s[5] / 2, s[6], s[7]))
            else:
                self.vias.remove((s[1], s[2], s[3] / 2, s[5]))

    def commit(self, staged):
        for s in staged:
            if s[0] == 't':
                _, xa, ya, xb, yb, w, net, layer = s
                t = pcbnew.PCB_TRACK(self.b)
                t.SetStart(pcbnew.VECTOR2I(int(round(xa * MM)), int(round(ya * MM))))
                t.SetEnd(pcbnew.VECTOR2I(int(round(xb * MM)), int(round(yb * MM))))
                t.SetWidth(int(round(w * MM)))
                t.SetLayer(LAYERS[layer])
                t.SetNet(self.b.FindNet(net))
                self.b.Add(t)
            else:
                _, x, y, d, drill, net = s
                v = pcbnew.PCB_VIA(self.b)
                v.SetPosition(pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM))))
                v.SetWidth(int(d * MM))
                v.SetDrill(int(drill * MM))
                v.SetViaType(pcbnew.VIATYPE_THROUGH)
                v.SetNet(self.b.FindNet(net))
                self.b.Add(v)

    def save(self):
        self.b.Save(self.fname)


def simplify(pts):
    res = [pts[0]]
    for i in range(1, len(pts) - 1):
        ax, ay = res[-1]
        bx, by = pts[i]
        cx, cy = pts[i + 1]
        if abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) < 1e-6:
            continue
        res.append(pts[i])
    res.append(pts[-1])
    return res


def length(pts):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def in_esc(x, y):
    return any(r[0] <= x <= r[2] and r[1] <= y <= r[3] for r in BGA_RECTS)


def split_neck(pts, step=0.0125):
    # cut a polyline where it crosses an escape region edge: [(pts, inside), ...]
    out = []
    cur = [pts[0]]
    state = in_esc(*pts[0])
    for (xa, ya), (xb, yb) in zip(pts, pts[1:]):
        n = max(1, int(math.hypot(xb - xa, yb - ya) / step))
        for k in range(1, n + 1):
            t = k / n
            x, y = xa + t * (xb - xa), ya + t * (yb - ya)
            s = in_esc(x, y)
            if s != state:
                cur.append((x, y))
                out.append((simplify(cur) if len(cur) > 2 else cur, state))
                cur = [(x, y)]
                state = s
        if cur[-1] != (xb, yb):
            cur.append((xb, yb))
    if len(cur) > 1:
        out.append((simplify(cur) if len(cur) > 2 else cur, state))
    return out


def seg_clear(blocked, x0, y0, a, b_):
    # every grid cell the straight segment a-b passes over is free
    n = max(2, int(math.hypot(b_[0] - a[0], b_[1] - a[1]) / (G / 2)) + 1)
    t = np.linspace(0.0, 1.0, n)
    ii = np.rint((a[0] + t * (b_[0] - a[0]) - x0) / G).astype(int)
    jj = np.rint((a[1] + t * (b_[1] - a[1]) - y0) / G).astype(int)
    if ii.min() < 0 or jj.min() < 0 or ii.max() >= blocked.shape[1] or jj.max() >= blocked.shape[0]:
        return False
    return not blocked[jj, ii].any()


def pull_tight(pts, blocked, x0, y0):
    # string pulling: from each kept vertex jump to the farthest later vertex in clear line of
    # sight, so grid staircases collapse into a few straight segments
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    i = 0
    n = len(pts)
    while i < n - 1:
        j = n - 1
        while j > i + 1 and not seg_clear(blocked, x0, y0, pts[i], pts[j]):
            j -= 1
        out.append(pts[j])
        i = j
    return out
