#!/usr/bin/env python3
# high-speed net audit: you declare which nets are high-speed and their clock,
# and this ranks the "worst offenders" against simple signal-integrity rules
# that can be checked without a field solve:
#
#   impedance  - the routed trace width, turned into Z0, vs your 50 ohm target
#   skew       - flight-time difference vs the group's reference clock net
#   vias       - each via is an impedance discontinuity, fewer is better
#
# it prints a ranked table and, with --plot, writes a color-coded png so you
# can see the offenders at a glance. green ok, yellow marginal, red fix it.
#
# edit GROUPS below to say what you consider high-speed. everything else is
# derived from the actual kicad_pcb routing.

import argparse
import math
import re
import sys

from net_lengths import parse, dominant_width, C0_MM_PER_PS
from impedance import z0_microstrip
from stackup import ER, COPPER_T, PREPREG_H

# ---- declare your high-speed intent here -------------------------------------
# clock: the net every other net in the group is length-matched against.
# z_target: intended single-ended impedance, ohm.
# clock_mhz: the STM32H7 max clock for the interface. the skew budget is
#   derived as SKEW_FRACTION of the clock period. FMC 125 MHz = 8000 ps period,
#   QSPI 133 MHz = 7519 ps. this is a rule-of-thumb budget; replace with the
#   real setup+hold window if you run synchronous at full rate.
GROUPS = [
    {"name": "FMC bus", "match": r"FMC_(DA\d+|A\d+|N\w+|CLK)",
     "clock": "/APM_FMC_CLK", "z_target": 50.0, "clock_mhz": 125.0},
    {"name": "QSPI", "match": r"QSPI",
     "clock": "/QSPI_SCK2", "z_target": 50.0, "clock_mhz": 133.0},
]
SKEW_FRACTION = 0.10   # allowed intra-bus skew as a fraction of the clock period
ER_EFF = 3.4            # microstrip on this stack, for delay
Z_TOL = 0.10           # +/-10% off target impedance is a warning, more is a fail
VIA_WARN = 2           # vias above this warn
VIA_FAIL = 4
# -----------------------------------------------------------------------------

PS_PER_MM = math.sqrt(ER_EFF) / (C0_MM_PER_PS / 1000.0)


def z0_for_width(w_mm):
    if w_mm is None:
        return None
    z, _ = z0_microstrip(w_mm * 1e-3, PREPREG_H, COPPER_T, ER)
    return z


def audit_group(g, length, vias, widths):
    pat = re.compile(g["match"])
    nets = [n for n in length if pat.search(n)]
    clk = g["clock"]
    clk_delay = length.get(clk, 0.0) * PS_PER_MM
    period_ps = 1e6 / g["clock_mhz"]        # 1/MHz in ps
    budget = SKEW_FRACTION * period_ps
    g["_budget_ps"] = budget
    g["_period_ps"] = period_ps
    rows = []
    for n in nets:
        ln = length[n]
        w = dominant_width(widths, n)
        z = z0_for_width(w)
        delay = ln * PS_PER_MM
        skew = delay - clk_delay
        v = vias.get(n, 0)

        # per-check status: 0 ok, 1 warn, 2 fail
        z_off = abs(z - g["z_target"]) / g["z_target"] if z else 0
        s_z = 2 if z and z_off > 2 * Z_TOL else (1 if z and z_off > Z_TOL else 0)
        s_skew = 2 if abs(skew) > budget else (
            1 if abs(skew) > 0.5 * budget else 0)
        s_via = 2 if v >= VIA_FAIL else (1 if v > VIA_WARN else 0)
        sev = max(s_z, s_skew, s_via)
        rows.append({"net": n, "len": ln, "w": w, "z": z, "skew": skew,
                     "vias": v, "sev": sev, "s_z": s_z, "s_skew": s_skew,
                     "s_via": s_via})
    # worst offenders first: by severity, then by absolute skew
    rows.sort(key=lambda r: (-r["sev"], -abs(r["skew"])))
    return clk_delay, rows


TAG = {0: "ok ", 1: "WARN", 2: "FAIL"}


def print_group(g, clk_delay, rows):
    print("\n===== %s  (%.0f MHz, period %.0f ps, target %.0f ohm, skew budget %.0f ps) ====="
          % (g["name"], g["clock_mhz"], g["_period_ps"], g["z_target"], g["_budget_ps"]))
    print("%-24s %8s %7s %7s %9s %5s   %s" %
          ("net", "len_mm", "w_mm", "Z0", "skew_ps", "vias", "status"))
    for r in rows:
        z = "%.0f" % r["z"] if r["z"] else "  ?"
        w = "%.3f" % r["w"] if r["w"] else "  ?"
        print("%-24s %8.1f %7s %7s %9.0f %5d   %s [Z:%s skew:%s via:%s]" % (
            r["net"], r["len"], w, z, r["skew"], r["vias"], TAG[r["sev"]],
            TAG[r["s_z"]].strip(), TAG[r["s_skew"]].strip(), TAG[r["s_via"]].strip()))


def plot(all_groups, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    color = {0: "#2ca02c", 1: "#e8a33d", 2: "#d62728"}
    n = len(all_groups)
    fig, axes = plt.subplots(n, 1, figsize=(11, 4 * n), squeeze=False)
    for ax, (g, clk_delay, rows) in zip(axes[:, 0], all_groups):
        names = [r["net"].split("/")[-1] for r in rows]
        skews = [r["skew"] for r in rows]
        cols = [color[r["sev"]] for r in rows]
        ax.barh(range(len(rows)), skews, color=cols)
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels(names, fontsize=7)
        ax.invert_yaxis()
        ax.axvline(g["_budget_ps"], ls="--", c="#d62728", lw=1)
        ax.axvline(-g["_budget_ps"], ls="--", c="#d62728", lw=1)
        ax.axvline(0, c="k", lw=0.8)
        ax.set_xlabel("skew vs %s, ps  (dashed = budget %.0f ps at %.0f MHz)" %
                      (g["clock"].split("/")[-1], g["_budget_ps"], g["clock_mhz"]))
        ax.set_title("%s: flight-time skew, worst offenders" % g["name"])
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    print("\nwrote %s" % out)


def main():
    ap = argparse.ArgumentParser(description="rank high-speed net SI offenders from a kicad_pcb")
    ap.add_argument("pcb")
    ap.add_argument("--plot", metavar="PNG", help="also write a color-coded png")
    args = ap.parse_args()
    length, vias, widths = parse(args.pcb)
    results = []
    worst = 0
    for g in GROUPS:
        clk_delay, rows = audit_group(g, length, vias, widths)
        if not rows:
            print("\n%s: no nets matched %r" % (g["name"], g["match"]))
            continue
        print_group(g, clk_delay, rows)
        results.append((g, clk_delay, rows))
        worst = max(worst, max((r["sev"] for r in rows), default=0))
    if args.plot and results:
        plot(results, args.plot)
    print("\noverall: %s" % {0: "all ok", 1: "warnings", 2: "FAILURES present"}[worst])
    return 1 if worst == 2 else 0


if __name__ == "__main__":
    sys.exit(main())
