import math

import pcbnew

import proute
import rlib

# shared helpers for the power-stage scripts (pstage_*.py): explicit copper, and a leg router that
# joins a net's terminals by a minimum spanning tree, necking to 0.1 mm inside escape boxes
MM = 1e6
V = lambda x, y: pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM)))


def track(b, a, z, w, net, layer):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(V(*a))
    t.SetEnd(V(*z))
    t.SetWidth(int(w * MM))
    t.SetLayer(layer)
    t.SetNet(b.FindNet(net))
    b.Add(t)


def via(b, p, net, d=0.45, drill=0.2):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(V(*p))
    v.SetWidth(int(d * MM))
    v.SetDrill(int(drill * MM))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(b.FindNet(net))
    b.Add(v)


class Router:
    def __init__(self, pcb, esc_refs, clr=0.15, neck=0.1, soft_pours=(('+12V', 'B.Cu'),)):
        self.bd = rlib.Board(pcb)
        # distribution pours that stubs may cross (the pour refills around them)
        self.bd.pours = [p for p in self.bd.pours if (p[2], p[1]) not in set(soft_pours)]
        boxes = []
        for r in esc_refs:
            bb = self.bd.b.FindFootprintByReference(r).GetBoundingBox(False)
            boxes.append((bb.GetLeft() / MM - 0.6, bb.GetTop() / MM - 0.6, bb.GetRight() / MM + 0.6,
                          bb.GetBottom() / MM + 0.6, 0.09))
        # escape strips beyond the packages (the STM32_ESC / FPGA_ESC rule areas): necked tracks may
        # keep 0.09 mm there until they have spread out of the ball field
        if 'U100' in esc_refs:
            boxes += [(134.5, 79.5, 138.0, 108.0, 0.09), (122.0, 104.5, 138.0, 108.0, 0.09)]
        if 'U11' in esc_refs:
            c = self.bd.b.FindFootprintByReference('U11').GetCourtyard(pcbnew.F_CrtYd).BBox()
            boxes.append((c.GetLeft() / MM - 3.0, c.GetTop() / MM - 3.0, c.GetRight() / MM + 3.0, c.GetBottom() / MM + 3.0, 0.09))
        rlib.BGA_RECTS[:] = boxes
        proute.ESC[:] = [r[:4] for r in boxes]
        rlib.TIGHT = True
        self.clr, self.neck = clr, neck
        self.open = []

    def keepout_courtyards(self, refs, layers=('F.Cu',)):
        # no foreign copper under a part's body: the courtyard minus the strips holding its pads
        for ref in refs:
            f = self.bd.b.FindFootprintByReference(ref)
            c = f.GetCourtyard(pcbnew.F_CrtYd).BBox()
            x0, y0, x1, y1 = c.GetLeft() / MM, c.GetTop() / MM, c.GetRight() / MM, c.GetBottom() / MM
            pads = [f.Pads()[k].GetBoundingBox() for k in range(len(f.Pads()))]
            if len(pads) == 2:
                p0, p1 = sorted(pads, key=lambda q: (q.GetCenter().x, q.GetCenter().y))
                if abs(p0.GetCenter().x - p1.GetCenter().x) > abs(p0.GetCenter().y - p1.GetCenter().y):
                    x0, x1 = p0.GetRight() / MM + 0.2, p1.GetLeft() / MM - 0.2
                else:
                    y0, y1 = p0.GetBottom() / MM + 0.2, p1.GetTop() / MM - 0.2
            self.bd.keepouts.append(([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], set(layers)))

    def terms(self, net, refs=None):
        out = []
        for (x, y, hx, hy, n, lays, rnd, p) in self.bd.pads:
            r = p.GetParentFootprint().GetReference()
            if n == net and (refs is None or r in refs):
                out.append((r + ':' + p.GetNumber(), (x, y), lays, (hx, hy)))
        return out

    @staticmethod
    def via_term(p):
        # an existing via as a leg end (all copper layers)
        return ('VIA@%.2f,%.2f' % p, p, set(rlib.LAYERS), (0.225, 0.225))

    def comp(self, net, ts):
        bd = self.bd
        pts = [t[1] for t in ts]
        segs = [(xa, ya, xb, yb) for (xa, ya, xb, yb, hw, n, ly) in bd.tracks if n == net]
        inpad = lambda q, x, y, hx, hy: abs(q[0] - x) <= hx + 0.02 and abs(q[1] - y) <= hy + 0.02
        vs = [(vx, vy) for (vx, vy, vr, n) in bd.vias if n == net]
        nodes = pts + vs + [(s[0], s[1]) for s in segs] + [(s[2], s[3]) for s in segs]
        par = list(range(len(nodes)))

        def fd(a):
            while par[a] != a:
                par[a] = par[par[a]]
                a = par[a]
            return a
        idx = {}
        for i, p in enumerate(nodes):
            k = (round(p[0] / 0.06), round(p[1] / 0.06))
            if k in idx:
                par[fd(i)] = fd(idx[k])
            idx[k] = i
        base = len(pts) + len(vs)
        for j in range(len(segs)):
            par[fd(base + j)] = fd(base + len(segs) + j)
        # a track end inside a pad, or a track passing over a pad centre, joins it
        for i, (r, (x, y), lays, (hx, hy)) in enumerate(ts):
            for j in range(len(pts), len(nodes)):
                if inpad(nodes[j], x, y, hx, hy) or math.hypot(nodes[j][0] - x, nodes[j][1] - y) < 0.35:
                    par[fd(i)] = fd(j)
            for j, (xa, ya, xb, yb) in enumerate(segs):
                dx, dy = xb - xa, yb - ya
                L2 = dx * dx + dy * dy
                u = 0 if L2 == 0 else max(0, min(1, ((x - xa) * dx + (y - ya) * dy) / L2))
                if math.hypot(x - xa - u * dx, y - ya - u * dy) < 0.2:
                    par[fd(i)] = fd(base + j)
        return [fd(i) for i in range(len(pts))]

    def stage(self, pts, net, w, ly, st):
        for seg, inside in rlib.split_neck(pts):
            self.bd.stage_track(seg, min(w, self.neck) if inside else w, net, ly, st)

    @staticmethod
    def side(lays):
        return 'B.Cu' if 'B.Cu' in lays and 'F.Cu' not in lays else 'F.Cu'

    def leg(self, net, a, z, w, inner=('In2.Cu', 'In7.Cu')):
        bd, (ra, pa, la, _), (rz, pz, lz, _) = self.bd, a, z
        for ly in ('F.Cu', 'B.Cu'):
            if ly in la and ly in lz:
                pts = bd.path(ly, pa, pz, w / 2, {net}, self.clr, margin=5.0, half_in=self.neck / 2)
                if pts:
                    st = []
                    self.stage(pts, net, w, ly, st)
                    return st, ly
        R = tuple(0.5 + 0.25 * i for i in range(10))
        sub = []
        sw = min(w, 0.5)
        va = pa if ra.startswith('VIA') else proute.drop_via(bd, pa, net, pz, sub, w=sw, radii=R, layer=self.side(la))
        vz = (pz if rz.startswith('VIA') else
              proute.drop_via(bd, pz, net, pa, sub, w=sw, radii=R, layer=self.side(lz))) if va else None
        if va and vz:
            for ly in ('B.Cu',) + tuple(inner) + ('F.Cu',):
                pts = bd.path(ly, va, vz, w / 2, {net}, self.clr, margin=8.0, half_in=self.neck / 2)
                if pts:
                    self.stage(pts, net, w, ly, sub)
                    return sub, 'vias+' + ly
        bd.unstage(sub)
        return None, None

    def net(self, net, ts, w, inner=('In2.Cu', 'In7.Cu')):
        # join ts (terminals) by a minimum spanning tree, skipping legs copper already joins
        used, edges = {0}, []
        while len(used) < len(ts):
            best = min(((math.hypot(ts[i][1][0] - ts[j][1][0], ts[i][1][1] - ts[j][1][1]), i, j)
                        for i in used for j in range(len(ts)) if j not in used))
            edges.append(best[1:])
            used.add(best[2])
        for i, j in edges:
            c = self.comp(net, ts)
            if c[i] == c[j]:
                continue
            s, how = self.leg(net, ts[i], ts[j], w, inner)
            if s:
                self.bd.commit(s)
            else:
                self.open.append((net, ts[i][0], ts[j][0]))

    def stitch(self, refs, nets=('GND',)):
        # a via beside each plane pad of refs that has no copper yet
        n_ok = 0
        for (x, y, hx, hy, n, lays, rnd, p) in list(self.bd.pads):
            if p.GetParentFootprint().GetReference() not in refs or n not in nets:
                continue
            if any(math.hypot(vx - x, vy - y) < 1.2 for (vx, vy, vr, nn) in self.bd.vias if nn == n):
                continue
            st = []
            if proute.drop_via(self.bd, (x, y), n, (x, y + 1.0), st, radii=(0.5, 0.6, 0.75, 0.9, 1.1, 1.3),
                               layer=self.side(lays)):
                self.bd.commit(st)
                n_ok += 1
            else:
                self.bd.unstage(st)
                self.open.append((n, p.GetParentFootprint().GetReference() + ':' + p.GetNumber(), 'stitch'))
        return n_ok


class Placer:
    # nearest free spot for small parts: same-side courtyards (+ tht parts) clear, pads clear of
    # other nets' vias and of tracks on the part's side
    def __init__(self, b):
        self.b = b
        self.refresh()

    def refresh(self):
        # fresh footprint handles too: removing board items can leave older swig handles untyped
        self._fs = self.b.Footprints()
        self.fps = {self._fs[i].GetReference(): self._fs[i] for i in range(len(self._fs))}
        ts = self.b.Tracks()
        self.vias, self.tracks = [], []
        for i in range(len(ts)):
            t = ts[i]
            if t.GetClass() == 'PCB_VIA':
                self.vias.append((t.GetPosition().x / MM, t.GetPosition().y / MM,
                                  pcbnew.Cast_to_PCB_VIA(t).GetWidth(pcbnew.F_Cu) / MM / 2, t.GetNetname()))
            elif t.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
                self.tracks.append((t.GetLayer(), t.GetStart().x / MM, t.GetStart().y / MM, t.GetEnd().x / MM,
                                    t.GetEnd().y / MM, t.GetWidth() / MM / 2, t.GetNetname()))

    @staticmethod
    def crt(f):
        c = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
        bb = c.BBox() if c.OutlineCount() else f.GetBoundingBox(False)
        return (bb.GetLeft() / MM, bb.GetTop() / MM, bb.GetRight() / MM, bb.GetBottom() / MM)

    @staticmethod
    def tht(f):
        return any(f.Pads()[k].GetAttribute() == pcbnew.PAD_ATTRIB_PTH for k in range(len(f.Pads())))

    def ok(self, f, gap=0.15, ignore=()):
        r = self.crt(f)
        hit = lambda a, c: a[0] - gap < c[2] and a[2] + gap > c[0] and a[1] - gap < c[3] and a[3] + gap > c[1]
        for o in self.fps.values():
            if o.GetReference() in (f.GetReference(),) + tuple(ignore):
                continue
            if (o.IsFlipped() == f.IsFlipped() or (self.tht(o) and not f.IsFlipped())) and hit(r, self.crt(o)):
                return False
            # parts on the other side must still clear tht pads (their copper is on both sides)
            if self.tht(o) and o.IsFlipped() != f.IsFlipped():
                for k in range(len(o.Pads())):
                    p = o.Pads()[k]
                    if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                        pb = p.GetBoundingBox()
                        q = (pb.GetLeft() / MM, pb.GetTop() / MM, pb.GetRight() / MM, pb.GetBottom() / MM)
                        if hit(r, q):
                            return False
        lay = pcbnew.B_Cu if f.IsFlipped() else pcbnew.F_Cu
        for k in range(len(f.Pads())):
            p = f.Pads()[k]
            px, py = p.GetPosition().x / MM, p.GetPosition().y / MM
            n = p.GetNetname()
            bb = p.GetBoundingBox()
            hx, hy = bb.GetWidth() / MM / 2, bb.GetHeight() / MM / 2
            for vx, vy, vr, vn in self.vias:
                if vn != n and abs(px - vx) < hx + vr + gap and abs(py - vy) < hy + vr + gap:
                    return False
            for l, x1, y1, x2, y2, hw, tn in self.tracks:
                if l != lay or tn == n:
                    continue
                dx, dy = x2 - x1, y2 - y1
                L2 = dx * dx + dy * dy
                u = 0 if L2 == 0 else max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / L2))
                if math.hypot(px - x1 - u * dx, py - y1 - u * dy) < max(hx, hy) + hw + gap:
                    return False
        return True

    def place(self, ref, tx, ty, bottom=False, rmax=6.0, rots=(0, 90, 180, 270), ignore=()):
        f = self.fps[ref]
        if f.IsFlipped() != bottom:
            f.Flip(f.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        for rad in [0.25 * i for i in range(0, int(rmax / 0.25))]:
            n = 1 if rad == 0 else max(8, int(2 * math.pi * rad / 0.25))
            for k in range(n):
                a = 2 * math.pi * k / n
                for rot in rots:
                    f.SetOrientationDegrees(rot)
                    f.SetPosition(V(tx + rad * math.cos(a), ty + rad * math.sin(a)))
                    if self.ok(f, ignore=ignore):
                        return (round(f.GetPosition().x / MM, 2), round(f.GetPosition().y / MM, 2), rot, rad)
        raise SystemExit('no room for ' + ref)

    def rip(self, refs, nets=(), near=()):
        # stitching of refs (track from a pad + the via at its far end), all copper of nets, and
        # copper of (net, (x, y), r) within r of a point
        key = lambda v: (round(v.x / MM, 3), round(v.y / MM, 3))
        old = set()
        for r in refs:
            f = self.fps[r]
            old |= {key(f.Pads()[k].GetPosition()) for k in range(len(f.Pads()))}
        ts = self.b.Tracks()
        items = [ts[i] for i in range(len(ts))]
        kill, vias = {}, set()
        for t in items:
            n = t.GetNetname()
            if n in nets:
                kill[id(t)] = t
                continue
            pts = [key(t.GetPosition())] if t.GetClass() == 'PCB_VIA' else [key(t.GetStart()), key(t.GetEnd())]
            for nn, (cx, cy), rr in near:
                if n == nn and any(math.hypot(p[0] - cx, p[1] - cy) < rr for p in pts):
                    kill[id(t)] = t
            if t.GetClass() != 'PCB_VIA':
                s, e = pts
                if s in old or e in old:
                    kill[id(t)] = t
                    vias.add((n, e if s in old else s))
        for t in items:
            if t.GetClass() == 'PCB_VIA' and (t.GetNetname(), key(t.GetPosition())) in vias:
                kill[id(t)] = t
        for t in kill.values():
            self.b.Remove(t)
        # keep the removed items referenced: letting their swig proxies be collected mid-script
        # corrupts pcbnew's type table (later lookups come back as untyped SwigPyObject)
        self._removed = getattr(self, '_removed', []) + list(kill.values())
        self.refresh()
        return len(kill)

    def pads(self, ref):
        f = self.fps[ref]
        return {f.Pads()[k].GetNumber(): (f.Pads()[k].GetPosition().x / MM, f.Pads()[k].GetPosition().y / MM)
                for k in range(len(f.Pads())) if f.Pads()[k].GetNumber()}
