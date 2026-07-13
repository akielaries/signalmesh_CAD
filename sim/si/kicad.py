# minimal, dependency-free kicad_pcb reader for SI work.
# extracts per-net routed geometry (length, dominant width, vias, layers,
# axis-aligned segments) plus the board outline. tuned for kicad 8/9/10 where
# tracks reference nets by name string.

import re
import math
from dataclasses import dataclass, field


@dataclass
class Net:
    name: str
    length_mm: float = 0.0
    vias: int = 0
    widths: dict = field(default_factory=dict)   # width_mm -> length_mm
    segments: list = field(default_factory=list)  # (x1,y1,x2,y2,width,layer)
    layers: set = field(default_factory=set)

    @property
    def dominant_width(self):
        if not self.widths:
            return None
        return max(self.widths.items(), key=lambda kv: kv[1])[0]


@dataclass
class Board:
    path: str
    nets: dict                       # name -> Net
    outline: tuple                   # (xmin,xmax,ymin,ymax) mm, pcb frame
    footprints: dict                 # ref -> {"at":(x,y,rot), "pads":[(name,net,x,y)]}


def _seg_re():
    return re.compile(
        r'\(segment\s*\(start ([\-\d.]+) ([\-\d.]+)\)\s*\(end ([\-\d.]+) ([\-\d.]+)\)'
        r'\s*\(width ([\d.]+)\)\s*\(layer "([^"]+)"\).*?\(net "([^"]*)"\)', re.S)


def _arc_len(x1, y1, xm, ym, x2, y2):
    ax, ay, bx, by, cx, cy = x1, y1, xm, ym, x2, y2
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return math.hypot(x2 - x1, y2 - y1)
    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a1 = math.atan2(ay - uy, ax - ux)
    a2 = math.atan2(cy - uy, cx - ux)
    da = abs(a2 - a1)
    if da > math.pi:
        da = 2 * math.pi - da
    return r * da


def _blocks(s, tag):
    out = []
    i = 0
    while True:
        i = s.find('(' + tag, i)
        if i < 0:
            break
        d = 0
        j = i
        while j < len(s):
            c = s[j]
            if c == '(':
                d += 1
            elif c == ')':
                d -= 1
                if d == 0:
                    break
            j += 1
        out.append(s[i:j + 1])
        i = j + 1
    return out


def load(path):
    s = open(path).read()
    nets = {}

    def net(n):
        return nets.setdefault(n, Net(n))

    # straight track segments
    for m in _seg_re().finditer(s):
        x1, y1, x2, y2, w, layer, n = (float(m.group(1)), float(m.group(2)),
                                       float(m.group(3)), float(m.group(4)),
                                       float(m.group(5)), m.group(6), m.group(7))
        ln = math.hypot(x2 - x1, y2 - y1)
        e = net(n)
        e.length_mm += ln
        e.widths[w] = e.widths.get(w, 0.0) + ln
        e.segments.append((x1, y1, x2, y2, w, layer))
        e.layers.add(layer)
    # arcs
    for m in re.finditer(
            r'\(arc\s*\(start ([\-\d.]+) ([\-\d.]+)\)\s*\(mid ([\-\d.]+) ([\-\d.]+)\)'
            r'\s*\(end ([\-\d.]+) ([\-\d.]+)\)\s*\(width ([\d.]+)\)\s*\(layer "([^"]+)"\).*?\(net "([^"]*)"\)', s, re.S):
        x1, y1, xm, ym, x2, y2, w, layer, n = (float(m.group(1)), float(m.group(2)),
                                               float(m.group(3)), float(m.group(4)),
                                               float(m.group(5)), float(m.group(6)),
                                               float(m.group(7)), m.group(8), m.group(9))
        ln = _arc_len(x1, y1, xm, ym, x2, y2)
        e = net(n)
        e.length_mm += ln
        e.widths[w] = e.widths.get(w, 0.0) + ln
        e.layers.add(layer)
    # vias
    for m in re.finditer(r'\(via\s*\(at [\-\d.]+ [\-\d.]+\).*?\(net "([^"]*)"\)', s, re.S):
        net(m.group(1)).vias += 1

    # board outline from Edge.Cuts gr_line
    xs, ys = [], []
    for b in _blocks(s, 'gr_line'):
        if '"Edge.Cuts"' not in b:
            continue
        st = re.search(r'\(start ([\-\d.]+) ([\-\d.]+)\)', b)
        en = re.search(r'\(end ([\-\d.]+) ([\-\d.]+)\)', b)
        if st and en:
            xs += [float(st.group(1)), float(en.group(1))]
            ys += [float(st.group(2)), float(en.group(2))]
    outline = (min(xs), max(xs), min(ys), max(ys)) if xs else (0, 0, 0, 0)

    # footprints + pads (absolute pcb coords) for port placement
    fps = {}
    for b in _blocks(s, 'footprint'):
        ref = re.search(r'\(property "Reference" "([^"]+)"', b)
        at = re.search(r'\(at ([\-\d.]+) ([\-\d.]+)(?: ([\-\d.]+))?\)', b)
        if not ref or not at:
            continue
        fx, fy = float(at.group(1)), float(at.group(2))
        frot = math.radians(float(at.group(3)) if at.group(3) else 0.0)
        pads = []
        for pb in _blocks(b, 'pad'):
            pn = re.search(r'\(pad "([^"]+)"', pb)
            pat = re.search(r'\(at ([\-\d.]+) ([\-\d.]+)', pb)
            pnet = re.search(r'\(net \d+ "([^"]+)"\)', pb) or re.search(r'\(net "([^"]+)"\)', pb)
            if not pat:
                continue
            px, py = float(pat.group(1)), float(pat.group(2))
            ax = fx + px * math.cos(frot) - py * math.sin(frot)
            ay = fy + px * math.sin(frot) + py * math.cos(frot)
            pads.append((pn.group(1) if pn else "?", pnet.group(1) if pnet else "", ax, ay))
        fps[ref.group(1)] = {"at": (fx, fy, frot), "pads": pads}

    return Board(path=path, nets=nets, outline=outline, footprints=fps)
