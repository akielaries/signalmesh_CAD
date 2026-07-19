#!/usr/bin/env python3
"""SVF (state-variable filter) design check.

Behavioral OTA model (Iout = gm*(V+ - V-)); gm is the OTA transconductance set by
the bias current (gm ~= Iabc/2Vt). Verifies the *topology*: LP/BP/HP shapes,
resonance, and that cutoff tracks the bias current. Values are placeholders - the
point is the shape, not exact Hz.

PASS THRESHOLDS (edit here if your spec differs):
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spice import run, read_wrdata, nearest

# ---- thresholds ----
LP_PASSBAND_MAX_DB   = 3.0     # LP well below cutoff should be ~0 dB (<= this, allowing resonance bump)
LP_ROLLOFF_AT_10F0   = -20.0   # LP a decade above cutoff must be at least this attenuated (2-pole ~ -40 dB)
HP_ROLLOFF_AT_F0_10  = -20.0   # HP a decade below cutoff must be at least this attenuated
BP_PEAK_MIN_DB       = 3.0     # resonance must give a real bandpass peak (>= this)
BP_PEAK_F_TOL        = (0.6, 1.6)   # BP peak must land within 0.6x..1.6x of the design f0
CUTOFF_TRACK_TOL     = (6.0, 15.0)  # 10x bias current must move cutoff into this multiple range

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_svf.txt")

def svf(gm, C):
    return f"""SVF behavioral
Vin in 0 dc 0 ac 1
Bhp hp 0 V = -(V(in) + V(lp) + 0.15*V(bp))
G1 bp1 0 hp 0 {gm}
C1 bp1 0 {C}
Ro1 bp1 0 1e9
Ebp bp 0 bp1 0 1
G2 lp1 0 bp 0 {gm}
C2 lp1 0 {C}
Ro2 lp1 0 1e9
Elp lp 0 lp1 0 1
.control
ac dec 30 20 20k
wrdata {OUT} db(v(lp)) db(v(bp)) db(v(hp))
.endc
.end
"""

def measure(gm, C=1e-9):
    run(svf(gm, C))
    f, (lp, bp, hp) = read_wrdata(OUT)
    f0 = gm / (2 * 3.14159 * C)
    peak_i = max(range(len(f)), key=lambda k: bp[k])
    return dict(f=f, lp=lp, bp=bp, hp=hp, f0=f0, bp_peak_db=bp[peak_i], bp_peak_f=f[peak_i])

def main():
    fails = []
    lo = measure(6.28e-6)   # f0 ~ 1 kHz
    # LP passband
    lp_pb = nearest(lo['f'], 40, lo['lp'])
    if lp_pb > LP_PASSBAND_MAX_DB: fails.append(f"LP passband {lp_pb:+.1f} dB > {LP_PASSBAND_MAX_DB}")
    # LP rolloff a decade up
    lp_ro = nearest(lo['f'], lo['f0'] * 10, lo['lp'])
    if lp_ro > LP_ROLLOFF_AT_10F0: fails.append(f"LP rolloff {lp_ro:+.1f} dB > {LP_ROLLOFF_AT_10F0}")
    # HP rolloff a decade down
    hp_ro = nearest(lo['f'], lo['f0'] / 10, lo['hp'])
    if hp_ro > HP_ROLLOFF_AT_F0_10: fails.append(f"HP rolloff {hp_ro:+.1f} dB > {HP_ROLLOFF_AT_F0_10}")
    # BP peak height + location
    if lo['bp_peak_db'] < BP_PEAK_MIN_DB: fails.append(f"BP peak {lo['bp_peak_db']:+.1f} dB < {BP_PEAK_MIN_DB}")
    r = lo['bp_peak_f'] / lo['f0']
    if not (BP_PEAK_F_TOL[0] <= r <= BP_PEAK_F_TOL[1]): fails.append(f"BP peak at {r:.2f}x f0 (want {BP_PEAK_F_TOL})")
    # cutoff tracks bias current: 10x gm -> ~10x cutoff
    hi = measure(6.28e-5)
    mult = hi['bp_peak_f'] / lo['bp_peak_f']
    if not (CUTOFF_TRACK_TOL[0] <= mult <= CUTOFF_TRACK_TOL[1]): fails.append(f"cutoff moved {mult:.1f}x for 10x Iabc (want {CUTOFF_TRACK_TOL})")

    print(f"SVF @ f0~{lo['f0']:.0f}Hz:  LP_pb={lp_pb:+.1f}  LP@10f0={lp_ro:+.1f}  HP@f0/10={hp_ro:+.1f}  "
          f"BP_peak={lo['bp_peak_db']:+.1f}dB@{lo['bp_peak_f']:.0f}Hz  cutoff_track={mult:.1f}x")
    if fails:
        print("SVF: FAIL"); [print("   -", x) for x in fails]; return 1
    print("SVF: PASS"); return 0

if __name__ == "__main__":
    sys.exit(main())
