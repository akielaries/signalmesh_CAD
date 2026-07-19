#!/usr/bin/env python3
# routed copper length per net, straight from a kicad_pcb, numpy-only.
# purpose: check length match on the FMC bus (data vs FMC_CLK) and see how
# far the fast nets run. via count is reported as a discontinuity proxy.

import re
import sys
import math
import argparse

# effective permittivity of a ~50 ohm microstrip on this stack (from
# impedance.py, er_eff ~ 3.4). signal velocity v = c / sqrt(er_eff).
# delay per mm = 1 / v. override with --er-eff for stripline (~4.5) etc.
C0_MM_PER_PS = 299.792458  # speed of light, mm/ns == mm per ps*1000


def parse(path):
    # kicad 10 references nets by name string inside each track/via
    s = open(path).read()
    length = {}
    vias = {}
    widths = {}   # net -> {trace_width_mm: length_mm} for the dominant-width calc
    # straight segments
    for m in re.finditer(
            r'\(segment\s*\(start ([\-\d.]+) ([\-\d.]+)\)\s*\(end ([\-\d.]+) ([\-\d.]+)\)'
            r'\s*\(width ([\d.]+)\).*?\(net "([^"]*)"\)', s, re.S):
        x1, y1, x2, y2, w, n = m.groups()
        d = math.hypot(float(x2) - float(x1), float(y2) - float(y1))
        length[n] = length.get(n, 0.0) + d
        widths.setdefault(n, {})
        widths[n][w] = widths[n].get(w, 0.0) + d
    # arc tracks (approximate by circular arc through mid)
    for m in re.finditer(
            r'\(arc\s*\(start ([\-\d.]+) ([\-\d.]+)\)\s*\(mid ([\-\d.]+) ([\-\d.]+)\)'
            r'\s*\(end ([\-\d.]+) ([\-\d.]+)\).*?\(net "([^"]*)"\)', s, re.S):
        x1, y1, xm, ym, x2, y2 = (float(m.group(i)) for i in range(1, 7))
        n = m.group(7)
        length[n] = length.get(n, 0.0) + _arc_len(x1, y1, xm, ym, x2, y2)
    for m in re.finditer(r'\(via.*?\(net "([^"]*)"\)', s, re.S):
        n = m.group(1)
        vias[n] = vias.get(n, 0) + 1
    return length, vias, widths


def dominant_width(widths, net):
    # trace width carrying the most routed length on this net, in mm
    w = widths.get(net)
    if not w:
        return None
    return float(max(w.items(), key=lambda kv: kv[1])[0])


def _arc_len(x1, y1, xm, ym, x2, y2):
    # circumradius from three points, then arc length; fall back to chord
    ax, ay, bx, by, cx, cy = x1, y1, xm, ym, x2, y2
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return math.hypot(x2 - x1, y2 - y1)
    ux = ((ax**2 + ay**2) * (by - cy) + (bx**2 + by**2) * (cy - ay) + (cx**2 + cy**2) * (ay - by)) / d
    uy = ((ax**2 + ay**2) * (cx - bx) + (bx**2 + by**2) * (ax - cx) + (cx**2 + cy**2) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    a1 = math.atan2(y1 - uy, x1 - ux)
    a2 = math.atan2(y2 - uy, x2 - ux)
    da = abs(a2 - a1)
    if da > math.pi:
        da = 2 * math.pi - da
    return r * da


def main():
    ap = argparse.ArgumentParser(description="routed length per net from a kicad_pcb")
    ap.add_argument("pcb")
    ap.add_argument("--filter", default="", help="only nets whose name matches this regex")
    ap.add_argument("--er-eff", type=float, default=3.4,
                    help="effective permittivity for delay (microstrip ~3.4, stripline ~4.5)")
    args = ap.parse_args()
    # picoseconds per mm = sqrt(er_eff) / c[mm/ps]
    ps_per_mm = math.sqrt(args.er_eff) / (C0_MM_PER_PS / 1000.0)
    length, vias, _ = parse(args.pcb)
    pat = re.compile(args.filter) if args.filter else None
    rows = []
    for nm, ln in length.items():
        if pat and not pat.search(nm):
            continue
        rows.append((nm, ln, vias.get(nm, 0), ln * ps_per_mm))
    rows.sort(key=lambda r: -r[1])
    print("%-28s %10s %6s %10s" % ("net", "len_mm", "vias", "delay_ps"))
    for nm, ln, v, d in rows:
        print("%-28s %10.2f %6d %10.1f" % (nm, ln, v, d))
    if rows:
        mx = max(r[1] for r in rows)
        mn = min(r[1] for r in rows)
        print("\nskew across shown nets: %.2f mm = %.1f ps (max %.2f, min %.2f mm)"
              % (mx - mn, (mx - mn) * ps_per_mm, mx, mn))


if __name__ == "__main__":
    main()
