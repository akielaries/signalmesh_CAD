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
    L.append(f"Vin {san(cfg['in'])} 0 dc 0 ac 1")
    # emit devices
    for ref, val in comps.items():
        if ref.startswith("R") and not ref.startswith("RV"):
            L.append(f"{ref} {n(ref,'1')} {n(ref,'2')} {val.replace('R','').replace('k','e3').replace('M','e6') or '1k'}")
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
    L.append(f".control")
    L.append(f"ac dec 30 20 20k")
    L.append(f"wrdata {cfg['out_file']} " + " ".join(f"db(v({san(o)}))" for o in cfg['probe']))
    L.append(".endc")
    L.append(".end")
    return "\n".join(L)
