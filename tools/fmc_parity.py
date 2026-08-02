#!/usr/bin/env python3
# fmc parity checker for the signalmesh DF40 board-to-board interface
#
# source of truth: the APM project (STM32H7 FMC bus -> DF40 connectors)
# downstream:      the ACM project (DF40 connectors -> GW5A-25 FPGA)
#
# the two projects do NOT share net names across the connector. APM names
# nets by FMC signal (FMC_DA0, FMC_A20), ACM names them by FPGA pin
# (H5_IOT61A, L7_IOT19A). the only shared coordinate is the DF40 pin number,
# and the connectors mate pin-N to pin-N (verified by identical GND fingerprint).
#
# so parity is checked two ways:
#   1. structural  - per mated pin, both sides must agree on pin CLASS
#                    (gnd / power / signal / no-connect). a gnd or power pin
#                    facing a signal pin is a hard error.
#   2. contract    - the locked apm_net <-> acm_net identity for every pin.
#                    'update' writes the contract from the current design
#                    (APM is authoritative). 'check' flags any drift from it.
#                    this is how the downstream connector "knows the source":
#                    the contract is generated from APM and ACM is held to it.

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # tools/.. -> signalmesh_CAD
BOARDS = os.path.join(ROOT, "boards")

# top-level schematic of each project (kicad-cli reads the full hierarchy)
APM_SCH = os.path.join(BOARDS, "APM", "v5_r1", "APM.kicad_sch")
ACM_SCH = os.path.join(BOARDS, "ACM", "v1_r1", "ACM_v1_r1.kicad_sch")

# the mated DF40 pairs that carry the FMC interface.
# each entry: (apm_connector_ref, acm_connector_ref)
PAIRS = [
    ("J1", "J5"),
    ("J3", "J6"),
]

PIN_COUNT = 60
CONTRACT = os.path.join(HERE, "fmc_contract.json")


def export_netlist(sch_path):
    # ask kicad-cli to resolve full connectivity, then parse the sexpr netlist.
    # we rely on kicad rather than re-tracing wires by geometry.
    fd, tmp = tempfile.mkstemp(suffix=".net")
    os.close(fd)
    try:
        r = subprocess.run(
            ["kicad-cli", "sch", "export", "netlist",
             "--format", "kicadsexpr", "-o", tmp, sch_path],
            capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("kicad-cli failed for %s:\n%s" % (sch_path, r.stderr))
        return open(tmp).read()
    finally:
        os.unlink(tmp)


def parse_connectors(netlist_text):
    # return {connector_ref: {pin_int: raw_net_name}} for DF40 connectors
    comps = re.findall(
        r'\(comp\s*\(ref "([^"]+)"\)\s*\(value "([^"]+)"\)', netlist_text)
    df40 = set(r for r, v in comps if "DF40" in v)
    conn = {}
    for nm in re.finditer(
            r'\(net\s*\(code "[^"]*"\)\s*\(name "([^"]+)"\)(.*?)(?=\(net\s|\Z)',
            netlist_text, re.S):
        net = nm.group(1)
        body = nm.group(2)
        for node in re.finditer(
                r'\(node\s*\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', body):
            ref, pin = node.group(1), node.group(2)
            if ref in df40:
                conn.setdefault(ref, {})[int(pin)] = net
    return conn


def norm(name):
    # strip hierarchy path, project prefix, and kicad escapes
    if name is None:
        return None
    n = name.rsplit("/", 1)[-1]
    n = n.replace("{slash}", "/")
    n = re.sub(r"^(APM_|ACM_)", "", n)
    return n


VOLT = re.compile(r"(\d+V\d+|\dV\d|\+?\d+V|1V8|2V5|3V3|5V)", re.I)


def classify(raw):
    # bucket a net into gnd / pwr / nc / sig and pull a rail token for pwr
    if raw is None:
        return ("missing", None)
    n = norm(raw)
    if raw.startswith("unconnected-"):
        return ("nc", None)
    u = n.upper()
    if u in ("GND", "GNDA", "AGND", "DGND"):
        return ("gnd", None)
    if (u.startswith("+") or u.startswith("VDD") or u.startswith("VCC")
            or u.startswith("VBUS") or "_3V3" in u or "_5V" in u
            or u in ("FPGA_3V3", "FPGA_5V") or VOLT.fullmatch(u)
            or u.startswith("VDDA")):
        m = VOLT.search(u.replace("+", ""))
        rail = m.group(1).upper().lstrip("0") if m else None
        return ("pwr", rail)
    return ("sig", None)


def build_rows():
    # returns list of dicts, one per mated pin, with both sides resolved
    apm = parse_connectors(export_netlist(APM_SCH))
    acm = parse_connectors(export_netlist(ACM_SCH))
    rows = []
    for apm_ref, acm_ref in PAIRS:
        if apm_ref not in apm:
            sys.exit("APM connector %s not found in netlist" % apm_ref)
        if acm_ref not in acm:
            sys.exit("ACM connector %s not found in netlist" % acm_ref)
        for pin in range(1, PIN_COUNT + 1):
            a_raw = apm[apm_ref].get(pin)
            b_raw = acm[acm_ref].get(pin)
            a_cls, a_rail = classify(a_raw)
            b_cls, b_rail = classify(b_raw)
            rows.append({
                "pair": "%s<->%s" % (apm_ref, acm_ref),
                "apm_ref": apm_ref, "acm_ref": acm_ref, "pin": pin,
                "apm_net": norm(a_raw), "acm_net": norm(b_raw),
                "apm_class": a_cls, "acm_class": b_cls,
                "apm_rail": a_rail, "acm_rail": b_rail,
            })
    return rows


def structural_issues(rows):
    # live apm-vs-acm class agreement, no contract needed
    issues = []
    for r in rows:
        a, b = r["apm_class"], r["acm_class"]
        key = "%s pin %d" % (r["pair"], r["pin"])
        desc = "APM %s [%s] | ACM %s [%s]" % (
            r["apm_net"], a, r["acm_net"], b)
        if a == b:
            if a == "pwr" and r["apm_rail"] != r["acm_rail"]:
                issues.append(("ERROR", key,
                               "power rail mismatch: %s vs %s" % (
                                   r["apm_rail"], r["acm_rail"]), desc))
            continue
        # classes differ
        hard = {"gnd", "pwr"}
        if (a in hard and b == "sig") or (b in hard and a == "sig"):
            issues.append(("ERROR", key, "class conflict %s vs %s" % (a, b), desc))
        elif "nc" in (a, b):
            # one side floats the other drives it - usually a locally
            # regulated rail (e.g. ACM VDD_1V8) or a forgotten connection
            issues.append(("WARN", key, "one side no-connect (%s vs %s)" % (a, b), desc))
        else:
            issues.append(("WARN", key, "class differs %s vs %s" % (a, b), desc))
    return issues


def load_contract():
    if not os.path.exists(CONTRACT):
        return None
    return json.load(open(CONTRACT))


def contract_key(r):
    return "%s|%d" % (r["pair"], r["pin"])


def cmd_update(rows):
    data = {"pairs": ["%s<->%s" % p for p in PAIRS], "pins": {}}
    for r in rows:
        data["pins"][contract_key(r)] = {
            "apm_net": r["apm_net"], "acm_net": r["acm_net"],
            "apm_class": r["apm_class"], "acm_class": r["acm_class"],
        }
    json.dump(data, open(CONTRACT, "w"), indent=2, sort_keys=True)
    print("wrote contract: %s (%d pins, source of truth = APM)" % (
        CONTRACT, len(data["pins"])))


def cmd_check(rows, strict_nc):
    structural = structural_issues(rows)
    drift = []
    contract = load_contract()
    if contract is None:
        print("no contract yet - run 'fmc_parity.py update' to lock the "
              "current pinout as source of truth")
    else:
        cur = {contract_key(r): r for r in rows}
        old = contract["pins"]
        for k in sorted(set(cur) | set(old)):
            if k not in cur:
                drift.append(("ERROR", k, "pin in contract but gone from design", ""))
                continue
            if k not in old:
                drift.append(("WARN", k, "new pin not in contract", ""))
                continue
            c, o = cur[k], old[k]
            if c["apm_net"] != o["apm_net"]:
                drift.append(("ERROR", k,
                              "APM net drifted: contract %s -> now %s" % (
                                  o["apm_net"], c["apm_net"]), ""))
            if c["acm_net"] != o["acm_net"]:
                drift.append(("ERROR", k,
                              "ACM net drifted: contract %s -> now %s" % (
                                  o["acm_net"], c["acm_net"]), ""))

    errs = warns = 0
    print("\n== structural parity (live APM vs ACM) ==")
    if not structural:
        print("  ok - all mated pins agree on class")
    for sev, key, msg, desc in structural:
        if sev == "WARN" and not strict_nc:
            warns += 1
        elif sev == "ERROR":
            errs += 1
        else:
            warns += 1
        print("  %-5s %-14s %s" % (sev, key, msg))
        if desc:
            print("            %s" % desc)

    print("\n== contract drift (vs locked source of truth) ==")
    if contract is None:
        print("  skipped - no contract")
    elif not drift:
        print("  ok - design matches contract")
    for sev, key, msg, _ in drift:
        if sev == "ERROR":
            errs += 1
        else:
            warns += 1
        print("  %-5s %-14s %s" % (sev, key, msg))

    print("\n%d error(s), %d warning(s)" % (errs, warns))
    return 1 if errs else 0


def cmd_table(rows):
    cur_pair = None
    for r in rows:
        if r["pair"] != cur_pair:
            cur_pair = r["pair"]
            print("\n== %s ==" % cur_pair)
            print("pin  | APM (source: FMC)        | ACM (FPGA pin / net)     | class")
            print("-" * 72)
        flag = "" if r["apm_class"] == r["acm_class"] else "  <-- class differs"
        print("%3d  | %-24s | %-24s | %s/%s%s" % (
            r["pin"], r["apm_net"] or "-", r["acm_net"] or "-",
            r["apm_class"], r["acm_class"], flag))


def main():
    ap = argparse.ArgumentParser(
        description="check FMC DF40 pinout parity between APM (source) and ACM")
    ap.add_argument("command", choices=["check", "update", "table"],
                    nargs="?", default="check",
                    help="check (default) | update contract | table")
    ap.add_argument("--strict-nc", action="store_true",
                    help="treat no-connect mismatches as errors")
    args = ap.parse_args()

    rows = build_rows()
    if args.command == "update":
        cmd_update(rows)
        return 0
    if args.command == "table":
        cmd_table(rows)
        return 0
    return cmd_check(rows, args.strict_nc)


if __name__ == "__main__":
    sys.exit(main())
