"""Reconstruct a runnable SPICE deck from a KiCad schematic netlist (kicadsexpr).
Uses the ACTUAL wiring from the schematic + behavioral IC models. This is the
"simulate the real schematic" path: catches wiring/value bugs the hand decks can't.
Unsimulatable parts (DAC/MCP/connectors/BBD) are substituted (DAC CVs -> DC sources)."""
import re, os

def parse(path):
    t = open(path).read()
    comps = {}
    for m in re.finditer(r'\(comp\s*\(ref "([^"]+)"\)\s*\(value "([^"]*)"', t):
        comps[m.group(1)] = m.group(2)
    pinnet = {}   # (ref,pin) -> net
    nets_sec = t[t.find("(nets"):]
    for chunk in re.split(r'\n\t\t\(net\n', nets_sec)[1:]:
        nm = re.search(r'\(name "([^"]+)"\)', chunk)
        if not nm:
            continue
        name = nm.group(1)
        for nd in re.finditer(r'\(node\s*\(ref "([^"]+)"\)\s*\(pin "([^"]+)"', chunk):
            pinnet[(nd.group(1), nd.group(2))] = name
    return comps, pinnet

def san(net):
    return re.sub(r'[^A-Za-z0-9_]', '_', net)

def parse_res(v):
    """resistor value -> ohms string, handling european notation (4k7=4700, 220R=220)"""
    v = (v or "").strip()
    m = re.match(r'^([\d.]*)\s*([RrkKMG]?)\s*([\d.]*)$', v)
    if not m or not (m.group(1) or m.group(3)):
        return "1k"
    a, mult, b = m.group(1), m.group(2), m.group(3)
    scale = {"": 1, "R": 1, "r": 1, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}[mult]
    num = float(f"{a or 0}.{b}") if b else float(a or 0)
    return repr(num * scale)

def N(pinnet, ref, pin):
    return san(pinnet.get((ref, pin), f"nc_{ref}_{pin}"))

def build(netlist, cfg):
    comps, pinnet = parse(netlist)
    L = [f"* auto-built from {os.path.basename(netlist)} (real schematic wiring)"]
    L.append(f'.include "{os.path.join(os.path.dirname(os.path.abspath(__file__)),"models","behavioral.lib")}"')
    L.append(".options rshunt=1e12 gmin=1e-9 reltol=1e-3")
    # supply rails + CV DC sources + AC stimulus
    L.append("V5 P5V 0 5")            # +5V  -> net name +5V maps to P5V
    L.append("VN5 N5V 0 -5")
    def n(ref, pin):
        raw = pinnet.get((ref, pin), f"nc_{ref}_{pin}")
        if raw in ("+5V", "-5V", "GND"):
            return {"+5V": "P5V", "-5V": "N5V", "GND": "0"}[raw]
        return san(raw)
    for net, v in cfg.get("dc", {}).items():
        L.append(f"V_{san(net)} {san(net)} 0 {v}")
    analysis = cfg.get("analysis", "ac")
    if analysis == "ac":
        L.append(f"Vin {san(cfg['in'])} 0 dc 0 ac 1")
    else:
        amp = cfg.get("amp", 0.5); freq = cfg.get("freq", 1000.0)
        L.append(f"Vin {san(cfg['in'])} 0 dc 0 sin(0 {amp} {freq})")
    # emit devices
    for ref, val in comps.items():
        if ref.startswith("R") and not ref.startswith("RV"):
            L.append(f"{ref} {n(ref,'1')} {n(ref,'2')} {parse_res(val)}")
        elif ref.startswith("C"):
            v = val.replace("nF","n").replace("uF","u").replace("pF","p").replace("F","")
            L.append(f"{ref} {n(ref,'1')} {n(ref,'2')} {v}")
        elif val == "OPA1678":
            L.append(f"X{ref} {n(ref,'1')} {n(ref,'2')} {n(ref,'3')} {n(ref,'7')} {n(ref,'6')} {n(ref,'5')} {n(ref,'8')} {n(ref,'4')} OPA1678")
        elif val == "LM13700":
            # OTA A (1 Iabc,3 +,4 -,5 out,7 bin,8 bout) ; OTA B (16,14,13,12,10,9) ; 11 V+ 6 V-
            L.append(f"X{ref}A {n(ref,'1')} {n(ref,'3')} {n(ref,'4')} {n(ref,'5')} {n(ref,'7')} {n(ref,'8')} {n(ref,'11')} {n(ref,'6')} LM13700_HALF")
            L.append(f"X{ref}B {n(ref,'16')} {n(ref,'14')} {n(ref,'13')} {n(ref,'12')} {n(ref,'10')} {n(ref,'9')} {n(ref,'11')} {n(ref,'6')} LM13700_HALF")
        elif val in ("4052", "4053"):
            # mux: connect the selected channel to the common (per cfg[mux])
            for com, ch in cfg.get("mux", {}).get(ref, []):
                L.append(f"Rmux_{ref}_{com} {n(ref,com)} {n(ref,ch)} 1")
        elif val == "MN3207" and cfg.get("bbd"):
            # BBD approximated as a lossless-line delay (delay only; no companding/noise -> bench)
            td = cfg["bbd"]; bin_ = n(ref, "3"); o1 = n(ref, "7"); o2 = n(ref, "8")
            L.append(f"R{ref}s {bin_} {ref}_bi 1k")
            L.append(f"T{ref} {ref}_bi 0 {ref}_bo 0 Z0=1k TD={td}")
            L.append(f"R{ref}t {ref}_bo 0 1k")
            L.append(f"E{ref}1 {o1} 0 {ref}_bo 0 1")
            L.append(f"E{ref}2 {o2} 0 {ref}_bo 0 1")
    L.append(".control")
    probes = " ".join((f"db(v({san(o)}))" if analysis == "ac" else f"v({san(o)})") for o in cfg["probe"])
    if analysis == "ac":
        L.append(f"ac dec {cfg.get('ac_pts',30)} {cfg.get('fmin',20)} {cfg.get('fmax',20000)}")
    else:
        f0 = cfg.get("freq", 1000.0); cyc = cfg.get("cycles", 8)
        tstop = cyc / f0; tstep = tstop / cfg.get("tpts", 2000)
        L.append(f"tran {tstep:.3e} {tstop:.6e} 0 {tstep:.3e}")
    L.append(f"wrdata {cfg['out_file']} {probes}")
    L.append(".endc")
    L.append(".end")
    return "\n".join(L)
