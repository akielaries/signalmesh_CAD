#!/usr/bin/env python3
"""Phaser design check (behavioral OTA all-pass stages).

Each stage: Vlp = 1st-order low-pass of Vin (OTA-C); all-pass = 2*Vlp - Vin.
Verifies: (1) a single stage is a true all-pass (flat magnitude), (2) its Vlp
rolls off at the design corner, (3) the 4-stage cascade produces notches that
MOVE with the bias current (the phaser sweep).

PASS THRESHOLDS:
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spice import run, read_wrdata, nearest

ALLPASS_FLATNESS_DB = 0.5     # single all-pass magnitude spread over the band must be <= this
VLP_ROLLOFF_AT_20F0 = -15.0   # Vlp two decades above corner must be <= this (it must actually filter)
NOTCH_DEPTH_DB      = -3.0    # a phaser notch counts if it dips below this
NOTCH_MOVE_MIN      = 2.0     # lowest notch must move at least this ratio when bias current changes ~8x

HERE = os.path.dirname(os.path.abspath(__file__))

def allpass_deck(gm, C, out):
    return f"""allpass
Vin in 0 dc 0 ac 1
G1 0 lpn in lp {gm}
C1 lpn 0 {C}
Ro1 lpn 0 1e9
Elp lp 0 lpn 0 1
Bap ap 0 V = 2*V(lp) - V(in)
.control
ac dec 30 20 20k
wrdata {out} db(v(lp)) db(v(ap))
.endc
.end
"""

def stage(n, inn, gm, C):
    return (f"G{n} 0 l{n} {inn} b{n} {gm}\nC{n} l{n} 0 {C}\nRo{n} l{n} 0 1e9\n"
            f"Eb{n} b{n} 0 l{n} 0 1\nBap{n} ap{n} 0 V = 2*V(b{n}) - V({inn})\n")

def phaser_deck(gm, C, out):
    d = "phaser 4-stage\nVin in 0 dc 0 ac 1\nBfin fin 0 V = V(in) + 0.5*V(ap4)\n"
    d += stage(1, "fin", gm, C) + stage(2, "ap1", gm, C) + stage(3, "ap2", gm, C) + stage(4, "ap3", gm, C)
    d += "Bout out 0 V = 0.5*V(in) + 0.5*V(ap4)\n"
    d += f".control\nac dec 40 20 20k\nwrdata {out} db(v(out))\n.endc\n.end\n"
    return d

def notches(f, mag):
    return [f[i] for i in range(2, len(f) - 2)
            if mag[i] < mag[i-1] and mag[i] < mag[i+1] and mag[i] < NOTCH_DEPTH_DB]

def main():
    fails = []
    ap_out = os.path.join(HERE, "_ap.txt")
    run(allpass_deck(6.28e-6, "1n", ap_out))
    f, (vlp, apmag) = read_wrdata(ap_out)
    flat = max(apmag) - min(apmag)
    if flat > ALLPASS_FLATNESS_DB: fails.append(f"all-pass magnitude spread {flat:.2f} dB > {ALLPASS_FLATNESS_DB}")
    vlp_ro = nearest(f, 1000 * 20, vlp)
    if vlp_ro > VLP_ROLLOFF_AT_20F0: fails.append(f"Vlp@20*f0 = {vlp_ro:+.1f} dB > {VLP_ROLLOFF_AT_20F0} (LP not filtering)")

    p_out = os.path.join(HERE, "_ph.txt")
    run(phaser_deck(6.28e-6, "1n", p_out))
    f1, (m1,) = read_wrdata(p_out)
    n1 = notches(f1, m1)
    run(phaser_deck(5.0e-5, "1n", p_out))
    f2, (m2,) = read_wrdata(p_out)
    n2 = notches(f2, m2)
    if not n1 or not n2: fails.append(f"no notches found (low={len(n1)}, high={len(n2)})")
    move = (n2[0] / n1[0]) if (n1 and n2) else 0
    if move < NOTCH_MOVE_MIN: fails.append(f"lowest notch moved {move:.1f}x for ~8x Iabc (want >= {NOTCH_MOVE_MIN})")

    print(f"PHASER:  allpass_flatness={flat:.2f}dB  Vlp@20f0={vlp_ro:+.1f}dB  "
          f"notches_low={[f'{x:.0f}' for x in n1[:4]]}  notches_high={[f'{x:.0f}' for x in n2[:4]]}  move={move:.1f}x")
    if fails:
        print("PHASER: FAIL"); [print("   -", x) for x in fails]; return 1
    print("PHASER: PASS"); return 0

if __name__ == "__main__":
    sys.exit(main())
