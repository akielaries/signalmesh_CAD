#!/usr/bin/env python3
# microstrip impedance solver, numpy-only, no external deps.
# uses the hammerstad-jensen closed form with thickness correction.
# purpose: pick a trace width for a target single-ended impedance on the
# APM/ACM stackup, and flag when the target needs an unfab-ably thin trace.

import math
import argparse
from stackup import ER, COPPER_T, PREPREG_H, OUTER_TO_FAR


def z0_microstrip(w, h, t, er):
    # hammerstad-jensen microstrip characteristic impedance
    # effective width with finite thickness correction
    if t > 0:
        dw = (t / math.pi) * math.log(1 + 4 * math.e / (t / h) /
                                      ((1 / math.tanh(math.sqrt(6.517 * (w / h)))) ** 2))
        we = w + dw
    else:
        we = w
    u = we / h
    a = 1 + (1 / 49.0) * math.log((u ** 4 + (u / 52.0) ** 2) / (u ** 4 + 0.432)) \
        + (1 / 18.7) * math.log(1 + (u / 18.1) ** 3)
    b = 0.564 * ((er - 0.9) / (er + 3.0)) ** 0.053
    ee = (er + 1) / 2 + (er - 1) / 2 * (1 + 10.0 / u) ** (-a * b)
    f = 6 + (2 * math.pi - 6) * math.exp(-(30.666 / u) ** 0.7528)
    z01 = 60 * math.log(f / u + math.sqrt(1 + (2 / u) ** 2))
    return z01 / math.sqrt(ee), ee


def solve_width(z_target, h, t, er):
    # bisection on width for the target impedance
    lo, hi = 0.01e-3, 5e-3
    for _ in range(80):
        mid = (lo + hi) / 2
        z, _ = z0_microstrip(mid, h, t, er)
        if z > z_target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main():
    ap = argparse.ArgumentParser(description="microstrip width for a target impedance on the APM/ACM stack")
    ap.add_argument("--z", type=float, default=50.0, help="target single-ended impedance, ohm")
    ap.add_argument("--fab-min", type=float, default=0.1, help="fab minimum trace width, mm")
    args = ap.parse_args()

    print("stackup: FR4 er=%.1f, copper=%.3f mm" % (ER, COPPER_T * 1e3))
    print("target single-ended Z0 = %.1f ohm\n" % args.z)
    for label, h in [("ref = near inner plane (0.1 mm prepreg)", PREPREG_H),
                     ("ref = far inner plane (near layer is signal)", OUTER_TO_FAR)]:
        w = solve_width(args.z, h, COPPER_T, ER)
        z, ee = z0_microstrip(w, h, COPPER_T, ER)
        flag = "  << below fab min %.2f mm" % args.fab_min if w * 1e3 < args.fab_min else ""
        print("%s" % label)
        print("  height h = %.3f mm -> width = %.3f mm  (Z0=%.1f, er_eff=%.2f)%s\n"
              % (h * 1e3, w * 1e3, z, ee, flag))


if __name__ == "__main__":
    main()
