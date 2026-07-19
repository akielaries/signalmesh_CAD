# behavioral BBD chorus check: a short delay (BBD) mixed with dry = comb filter;
# the delay is clock-controlled, so the comb notches SWEEP with delay time (the chorus/vibrato).
# we validate: (a) comb notches exist at f=(2k+1)/(2*TD), (b) they MOVE when the delay changes.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spice import run, read_wrdata, nearest

def comb_deck(td, out):
    # lossless T-line = pure delay TD; comb = dry + delayed
    return f"""chorus comb (delay={td})
V1 in 0 dc 0 ac 1
Rs in ina 50
T1 ina 0 outa 0 Z0=600 TD={td}
Rt outa 0 600
Bcomb comb 0 V = 0.5*V(ina) + 0.5*V(outa)
.control
ac dec 60 20 4000
wrdata {out} db(v(comb))
.endc
.end
"""

def notches(freqs, mags, thresh=-8.0):
    out = []
    for i in range(2, len(freqs) - 2):
        if mags[i] < mags[i-1] and mags[i] < mags[i+1] and mags[i] < thresh:
            out.append(freqs[i])
    return out

O = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_ch.txt")
res = {}
for td in ("5m", "10m"):
    run(comb_deck(td, O))
    f, cols = read_wrdata(O)
    n = notches(f, cols[0])
    res[td] = n
    print(f"chorus delay={td}: first comb notches (Hz) = {[f'{x:.0f}' for x in n[:4]]}  (expect ~(2k+1)/(2*TD))")

# checks
n5 = res["5m"]; n10 = res["10m"]
# expected first notch: 1/(2*TD): 5ms->100Hz, 10ms->50Hz
ok_exist = len(n5) >= 2 and len(n10) >= 2
first5 = n5[0] if n5 else 0; first10 = n10[0] if n10 else 0
ok_5 = 60 < first5 < 160          # ~100 Hz
ok_10 = 30 < first10 < 90         # ~50 Hz
ok_move = first5 > first10 * 1.5  # notches move up as delay shortens
print(f"\nfirst notch: 5ms={first5:.0f}Hz (want ~100)  10ms={first10:.0f}Hz (want ~50)  moved={ok_move}")
PASS = ok_exist and ok_5 and ok_10 and ok_move
print("CHORUS:", "PASS" if PASS else "FAIL")
sys.exit(0 if PASS else 1)
