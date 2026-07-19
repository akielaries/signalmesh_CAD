# Simulate the ACTUAL SVF schematic (MASTER_FILTER.kicad_sch): export its netlist,
# rebuild SPICE from the real wiring + behavioral models, check the LP response.
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netsim
from spice import run, read_wrdata

HERE = os.path.dirname(os.path.abspath(__file__))
SCH = os.path.join(HERE, "..", "..", "schematic", "AUDIO_BOARD_v1_r1", "MASTER_FILTER.kicad_sch")
NET = os.path.join(HERE, "_svf_real.net")
OUT = os.path.join(HERE, "_svf_real.txt")

# 1. export the actual schematic's netlist (real wiring)
subprocess.run(["kicad-cli", "sch", "export", "netlist", "--format", "kicadsexpr",
                "--output", NET, SCH], check=True, capture_output=True)

# 2. build SPICE from that netlist; mux in LP mode; CVs set cutoff/resonance
cfg = {"in": "/AUDIO_L_IN",
       "dc": {"/CV_CUTOFF": -4.7, "/CV_RES": -4.99, "/AUDIO_R_IN": 0.0},
       "mux": {"U33": [("13", "12")], "U37": [("13", "12")]},   # common(13) -> LP channel(12)
       "probe": ["/AUDIO_L_OUT"],
       "out_file": OUT}
deck = netsim.build(NET, cfg)
run(deck)
f, cols = read_wrdata(OUT)
lp = cols[0]
def at(freq):
    i = min(range(len(f)), key=lambda k: abs(f[k] - freq)); return lp[i]
pb, hi = at(50), at(18000)
print(f"SVF from the REAL schematic (LP mode): |H|@50Hz={pb:.1f}dB  @18kHz={hi:.1f}dB  rolloff={pb-hi:.1f}dB")
PASS = (pb - hi) > 10   # a lowpass must roll off toward HF
print("SVF-REAL:", "PASS" if PASS else "FAIL")
sys.exit(0 if PASS else 1)
