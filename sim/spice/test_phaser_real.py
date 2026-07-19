# Simulate the ACTUAL phaser schematic (FX_PHASER): all-pass stages should keep the
# wet output magnitude roughly flat (all-pass) - a broken stage would tilt/kill it.
import sys, os, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import netsim
from spice import run, read_wrdata
HERE = os.path.dirname(os.path.abspath(__file__))
SCH = os.path.join(HERE, "..", "..", "schematic", "AUDIO_BOARD_v1_r1", "FX_PHASER.kicad_sch")
NET = os.path.join(HERE, "_ph_real.net"); OUT = os.path.join(HERE, "_ph_real.txt")
subprocess.run(["kicad-cli","sch","export","netlist","--format","kicadsexpr","--output",NET,SCH],check=True,capture_output=True)
# U63 = bypass CD4053: X sec com=14, wet(phased) in1=13 -> select wet
cfg = {"in": "/PH_L_IN",
       "dc": {"/CV_FX2": -4.6, "/PH_R_IN": 0.0},
       "mux": {"U63": [("14", "13")]},        # L common(14) -> wet(13)
       "probe": ["/PH_L_OUT"], "out_file": OUT}
run(netsim.build(NET, cfg))
f, cols = read_wrdata(OUT); m = cols[0]
lo, mid, hi = m[2], m[len(m)//2], m[-3]
spread = max(m) - min(m)
print(f"phaser from REAL schematic: |H| lo={lo:.1f} mid={mid:.1f} hi={hi:.1f} dB, spread={spread:.1f}dB")
PASS = spread < 25 and max(m) > -40   # roughly all-pass-ish, signal present (not dead)
print("PHASER-REAL:", "PASS" if PASS else "FAIL")
sys.exit(0 if PASS else 1)
