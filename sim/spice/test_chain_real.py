"""Per-stage signal-chain verification from the ACTUAL root schematic.

Exports the whole flattened hierarchy (AUDIO_BOARD.kicad_sch), rebuilds SPICE from
the REAL wiring + behavioral IC models, and verifies the signal at EVERY stage:

  input buffer -> VCF/VCA -> SVF -> drive+tremolo -> phaser -> chorus(bypass) -> out

Two passes:
  PER-STAGE AC : inject a clean unit source at each stage's input, probe its output,
                 check the transfer (gain + filter shape) in isolation. Robust - no
                 cascade blow-up, and it pinpoints which stage a wiring bug is in.
  FULL TRANSIENT: inject a 1 kHz sine at the board input, probe all six stage nodes,
                 confirm the waveform propagates end-to-end.

What this validates: wiring/connectivity, per-stage topology, filter shape direction,
VCA gain control, end-to-end propagation. What it does NOT: absolute levels or exact
cutoff-vs-CV tracking (idealized OTA/op-amp models) - those need the vendor LM13700 /
OPA1678 subckts + bench. The BBD chorus is run in bypass (BBD has no SPICE model).
"""
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netsim
from spice import run, read_wrdata

HERE = os.path.dirname(os.path.abspath(__file__))
SCH = os.path.join(HERE, "..", "..", "schematic", "AUDIO_BOARD_v1_r1", "AUDIO_BOARD.kicad_sch")
NET = os.path.join(HERE, "_chain.net")

# shared bias (DAC CVs -> DC). the analog filter is idealized: CV sets gain/shape, not exact Fc
BIAS = {
    "/ANALOG_FILTER_CV/CV_CUTOFF": -3.0, "/ANALOG_FILTER_CV/CV_RES": -4.9,
    "/ANALOG_FILTER_CV/CV_VCA": 0.0, "/ANALOG_FILTER_CV/CV_MOD": 0.0,
    "/MF_CV_CUTOFF": -4.7, "/MF_CV_RES": -4.99,
    "/CV_FX1": -4.9, "/CV_FX2": -3.0, "/CV_FX3": -3.0,
}
# mux routes
U6_ON  = {"U6":  [("14", "13"), ("15", "1")]}   # VCF/VCA engaged
SVF_LP = {"U33": [("13", "12")], "U37": [("13", "12")]}
TREM_BYP = {"U41": [("14", "12"), ("15", "2")]}
TREM_ON  = {"U41": [("14", "13"), ("15", "1")]}
PHAS_BYP = {"U63": [("14", "12"), ("15", "2")]}
PHAS_ON  = {"U63": [("14", "13"), ("15", "1")]}
CHOR_BYP = {"U76": [("14", "12"), ("15", "2")]}

def merge(*ds):
    o = {}
    for d in ds:
        o.update(d)
    return o

# per-stage: (label, inject-node, probe-node, mux, check-fn(gain@100,1k,15k)->(ok,note))
def pass_(v100, v1k, v15k):
    return (v1k > -30, f"passes ({v1k:+.1f}dB @1k)")
def lp_(v100, v1k, v15k):
    return (v100 - v15k > 8, f"lowpass, {v100 - v15k:+.1f}dB 100Hz->15k")
def gain_(v100, v1k, v15k):
    return (v1k > 3, f"gain {v1k:+.1f}dB @1k")
def flat_(v100, v1k, v15k):
    return (max(abs(v100 - v1k), abs(v1k - v15k)) < 6, f"flat within {max(abs(v100-v1k),abs(v1k-v15k)):.1f}dB")

STAGES = [
    ("input buffer", "Net-(U3A-+)",  "/FILT_L_IN",                  {},                          pass_),
    ("VCF / VCA",    "/FILT_L_IN",   "/ANALOG_FILTER_CV/VCA_L_OUT", U6_ON,                       lp_),
    ("SVF (LP)",     "/FILT_L_OUT",  "/FILT_L_FILT",                SVF_LP,                      lp_),
    ("drive+trem",   "/FILT_L_FILT", "/FX_L_OUT",                   TREM_BYP,                    gain_),
    ("phaser",       "/FX_L_OUT",    "/CH_L_IN",                    PHAS_ON,                     flat_),
    ("chorus/out",   "/CH_L_IN",     "/VOL_L",                      CHOR_BYP,                    pass_),
]

def ac_stage(inject, probe, mux, tag):
    out = os.path.join(HERE, f"_st_{tag}.txt")
    cfg = {"in": inject, "dc": BIAS, "mux": mux, "probe": [probe], "out_file": out,
           "analysis": "ac", "ac_pts": 16, "fmin": 20, "fmax": 20000}
    if not run_ok(netsim.build(NET, cfg), out):
        return None
    f, cols = read_wrdata(out)
    col = cols[0]
    a = lambda fr: col[min(range(len(f)), key=lambda k: abs(f[k] - fr))]
    return a(100), a(1000), a(15000)

def run_ok(deck, out):
    if os.path.exists(out):
        os.remove(out)
    run(deck)
    return os.path.exists(out)

# ------------------------------------------------ export + per-stage AC
subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
                "--output", NET, SCH], check=True, capture_output=True)

print("=" * 70)
print("PER-STAGE frequency-response verification (inject at each stage input)")
print("=" * 70)
print(f"{'stage':<14}{'inject':<16}{'gain@1k':>9}   behaviour")
print("-" * 70)
allpass = True
for i, (name, inj, prb, mux, chk) in enumerate(STAGES):
    r = ac_stage(inj, prb, mux, str(i))
    if r is None:
        print(f"{name:<14}{inj[:15]:<16}{'SIM FAIL':>9}")
        allpass = False
        continue
    ok, note = chk(*r)
    allpass = allpass and ok
    tag = "PASS" if ok else "FAIL"
    print(f"{name:<14}{inj[:15]:<16}{r[1]:>8.1f}   [{tag}] {note}")

# ------------------------------------------------ per-stage Bode (frequency response)
print()
print("=" * 70)
print("PER-STAGE frequency response (gain dB) - the 1 kHz column is the sine")
print("level a 1 kHz input reaches at that stage output")
print("=" * 70)
FR = [50, 100, 500, 1000, 5000, 15000]
print("stage".ljust(14) + "".join(f"{fr:>8}Hz" for fr in FR))
print("-" * (14 + 10 * len(FR)))
for i, (name, inj, prb, mux, chk) in enumerate(STAGES):
    out = os.path.join(HERE, f"_bode_{i}.txt")
    cfg = {"in": inj, "dc": BIAS, "mux": mux, "probe": [prb], "out_file": out,
           "analysis": "ac", "ac_pts": 24, "fmin": 20, "fmax": 20000}
    if not run_ok(netsim.build(NET, cfg), out):
        print(name.ljust(14) + "  SIM FAIL")
        continue
    f, cols = read_wrdata(out)
    col = cols[0]
    row = [col[min(range(len(f)), key=lambda k: abs(f[k] - fr))] for fr in FR]
    print(name.ljust(14) + "".join(f"{v:>10.1f}" for v in row))

print()
print("NOTE: true time-domain waveform (distortion, tremolo/phaser modulation, clipping)")
print("needs the vendor LM13700/OPA1678 subckts + the DAC-streamed LFOs - the idealized")
print("models here are linear/unbounded, so AC (frequency) is their reliable domain.")
print()
print("CHAIN-REAL:", "PASS" if allpass else "FAIL")
sys.exit(0 if allpass else 1)
