# tier-3 crosstalk harness. given a board, an aggressor net, and victim nets,
# auto-place gerber2ems ports at the trace ends and generate the sim config.
# replaces hand-edited port setups: the port coords come from the routed
# geometry, not guesswork.
#
# flow:
#   ports = plan(board, aggressor, victims)          # geometry -> ports
#   write_config(ems_dir, ports, freq, mesh)         # simulation.json + pos csv
#   (user or --run) gerber2ems -g --export-field / -s / -p
#   read_sparams(ems_dir) -> through / NEXT / FEXT in dB
#   render field movie via board_heatmap

import os
import json
import math
import csv
import re

ROUTE_LAYER = "In1.Cu"        # dominant inner routing layer on these boards
LAYER_IDX = 1                 # gerber2ems metal index for In1.Cu
PLANE_IDX = 0                 # F.Cu ground reference
# port width must span >= ~2 mesh cells or openEMS can't form the voltage
# integration line (the "1D/line integration" error). 300 um over a 150 um mesh.
PORT_W = 300
PORT_L = 1000


def _axis_segs(net, layer=ROUTE_LAYER):
    """axis-aligned segments of a net on the routing layer, as
    (kind,'H'/'V', const, lo, hi)."""
    segs = []
    for x1, y1, x2, y2, w, lyr in net.segments:
        if lyr != layer:
            continue
        if abs(y1 - y2) < 0.02 and abs(x1 - x2) > 0.5:
            segs.append(("H", y1, min(x1, x2), max(x1, x2)))
        elif abs(x1 - x2) < 0.02 and abs(y1 - y2) > 0.5:
            segs.append(("V", x1, min(y1, y2), max(y1, y2)))
    return segs


def _endpoints(net, layer=ROUTE_LAYER):
    """the two extreme ends of the routed path on the layer (max separation)."""
    pts = []
    for x1, y1, x2, y2, w, lyr in net.segments:
        if lyr != layer:
            continue
        pts += [(x1, y1), (x2, y2)]
    if not pts:
        for x1, y1, x2, y2, w, lyr in net.segments:
            pts += [(x1, y1), (x2, y2)]
    best = (0, pts[0], pts[0])
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            d = math.hypot(pts[i][0] - pts[j][0], pts[i][1] - pts[j][1])
            if d > best[0]:
                best = (d, pts[i], pts[j])
    return best[1], best[2]


def _port_at(net, near_pt):
    """pick an axis-aligned segment near `near_pt` and return a port
    (x, y, rot) sitting on it, oriented along the trace."""
    segs = _axis_segs(net)
    if not segs:
        return None
    best = None
    for kind, const, lo, hi in segs:
        # the two ends of this segment
        ends = [(const, lo), (const, hi)] if kind == "V" else [(lo, const), (hi, const)]
        for ex, ey in ends:
            d = math.hypot(ex - near_pt[0], ey - near_pt[1])
            if best is None or d < best[0]:
                best = (d, kind, const, lo, hi)
    _, kind, const, lo, hi = best
    mid = (lo + hi) / 2
    # place ~1.5 mm in from the near end, staying on the segment
    if kind == "V":
        y = min(hi - 1.0, max(lo + 1.0, lo + 1.5 if abs(lo - near_pt[1]) < abs(hi - near_pt[1]) else hi - 1.5))
        return (const, y, 0)          # rot 0 -> feed along y
    else:
        x = min(hi - 1.0, max(lo + 1.0, lo + 1.5 if abs(lo - near_pt[0]) < abs(hi - near_pt[0]) else hi - 1.5))
        return (x, const, 90)         # rot 90 -> feed along x


def coupled_length(board, na, nb, layer=ROUTE_LAYER, max_gap=0.6):
    """total parallel co-run length (mm) between two nets on the routing layer."""
    tot = 0.0
    sa = _axis_segs(board.nets[na], layer)
    sb = _axis_segs(board.nets[nb], layer)
    for ka, ca, la, ha in sa:
        for kb, cb, lb, hb in sb:
            if ka != kb:
                continue
            gap = abs(ca - cb)
            if gap > max_gap or gap < 0.03:
                continue
            tot += max(0, min(ha, hb) - max(la, lb))
    return tot


def coupled_geometry(board, na, nb, layer=ROUTE_LAYER, max_gap=0.6):
    """extract the coupled-line cross-section from the routed geometry:
    returns dict(length_mm, gap_mm center-to-center, agg_w_mm, vic_w_mm)."""
    sa = _axis_segs(board.nets[na], layer)
    sb = _axis_segs(board.nets[nb], layer)
    length = 0.0
    gap_weighted = 0.0
    for ka, ca, la, ha in sa:
        for kb, cb, lb, hb in sb:
            if ka != kb:
                continue
            gap = abs(ca - cb)
            if gap > max_gap or gap < 0.03:
                continue
            ov = max(0, min(ha, hb) - max(la, lb))
            length += ov
            gap_weighted += ov * gap
    gap = gap_weighted / length if length else 0.0
    return {"length_mm": length, "gap_mm": gap,
            "agg_w_mm": board.nets[na].dominant_width or 0.1,
            "vic_w_mm": board.nets[nb].dominant_width or 0.1}


def find_victims(board, aggressor, n=1):
    """the n nets with the longest parallel co-run to the aggressor."""
    scored = []
    for name in board.nets:
        if name == aggressor:
            continue
        c = coupled_length(board, aggressor, name)
        if c > 2.0:
            scored.append((c, name))
    scored.sort(reverse=True)
    return scored[:n]


def plan(board, aggressor, victims):
    """return ordered port list of dicts: net, role, x, y, rot.
    order = [aggressor drive, aggressor far, then per victim: near, far]."""
    agg = board.nets[aggressor]
    a_drive_pt, a_far_pt = _endpoints(agg)
    ports = []
    p = _port_at(agg, a_drive_pt)
    ports.append({"net": aggressor, "role": "drive", "x": p[0], "y": p[1], "rot": p[2]})
    p = _port_at(agg, a_far_pt)
    ports.append({"net": aggressor, "role": "agg_far", "x": p[0], "y": p[1], "rot": p[2]})
    for v in victims:
        vn = board.nets[v]
        v1, v2 = _endpoints(vn)
        # near = victim end closest to aggressor drive; far = closest to agg far
        if (math.hypot(v1[0] - a_drive_pt[0], v1[1] - a_drive_pt[1]) >
                math.hypot(v2[0] - a_drive_pt[0], v2[1] - a_drive_pt[1])):
            v1, v2 = v2, v1
        pn = _port_at(vn, v1)
        pf = _port_at(vn, v2)
        ports.append({"net": v, "role": "next", "x": pn[0], "y": pn[1], "rot": pn[2]})
        ports.append({"net": v, "role": "fext", "x": pf[0], "y": pf[1], "rot": pf[2]})
    return ports


def write_config(ems_dir, ports, agg_net, victim_nets, freq=(1e8, 3e9),
                 max_steps=40000, pixel_size=40.0, optimal=150.0):
    """write simulation.json + fab/*-pos.csv for gerber2ems.
    optimal is the fine mesh cell (um) near traces; keep it <= PORT_W/2 so the
    ports resolve. coarsening below that breaks thin-trace ports."""
    sim = {
        "format_version": "1.2",
        "frequency": {"start": freq[0], "stop": freq[1]},
        "max_steps": max_steps,
        "pixel_size": pixel_size,
        "ports": [{"width": PORT_W, "length": PORT_L, "impedance": 50,
                   "layer": LAYER_IDX, "plane": PLANE_IDX,
                   "excite": (i == 0)} for i in range(len(ports))],
        "traces": [{"start": 0, "stop": 1, "nets": [agg_net]}] +
                  [{"start": 2 + 2 * k, "stop": 3 + 2 * k, "nets": [v]}
                   for k, v in enumerate(victim_nets)],
        "grid": {"inter_layers": 4, "optimal": optimal, "diagonal": optimal,
                 "perpendicular": optimal * 2, "max": 2000.0,
                 "margin": {"xy": 2400.0, "z": 5000.0, "from_trace": False},
                 "cell_ratio": {"xy": 1.2, "z": 1.5}},
    }
    with open(os.path.join(ems_dir, "simulation.json"), "w") as f:
        json.dump(sim, f, indent=4)

    fab = os.path.join(ems_dir, "fab")
    os.makedirs(fab, exist_ok=True)
    # pos csv uses pcb-x, -pcb-y (kicad pos convention)
    posfile = None
    for fn in os.listdir(fab):
        if fn.endswith("-pos.csv") or fn.endswith("-top-pos.csv"):
            posfile = os.path.join(fab, fn)
    posfile = posfile or os.path.join(fab, "sim-top-pos.csv")
    with open(posfile, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Ref", "Val", "Package", "PosX", "PosY", "Rot", "Side"])
        for i, p in enumerate(ports):
            w.writerow(["SP%d" % (i + 1), "Simulation_Port", "Simulation_Port",
                        "%.3f" % p["x"], "%.3f" % (-p["y"]), p["rot"], "top"])
    return os.path.join(ems_dir, "simulation.json"), posfile


def read_sparams(ems_dir):
    """parse gerber2ems Port_0_data.csv -> {freq_mhz, through_db, next_db, fext_db}
    for excitation on port 0. columns are |S{i}-0|."""
    path = os.path.join(ems_dir, "ems", "results", "Port_0_data.csv")
    if not os.path.exists(path):
        return None
    import numpy as np
    rows = list(csv.reader(open(path)))
    hdr = rows[0]
    data = np.array([[float(x) for x in r] for r in rows[1:]])
    col = {name.strip(): i for i, name in enumerate(hdr)}

    def mag(i):
        key = "|S%d-0| [-]" % i
        return data[:, col[key]] if key in col else None
    f = data[:, 0]
    out = {"freq_mhz": f.tolist()}
    for i, tag in [(1, "through"), (2, "next"), (3, "fext")]:
        m = mag(i)
        if m is not None:
            db = 20 * np.log10(np.clip(m, 1e-9, None))
            out[tag + "_db"] = db.tolist()
            out[tag + "_worst_db"] = float(np.max(db))
    return out
