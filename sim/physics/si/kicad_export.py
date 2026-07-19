# emit KiCad net-class definitions (with stackup-derived widths) plus the
# net->class pattern assignments, so the re-route enforces the SI rules.
# output is the "net_settings" object you merge into the .kicad_pro, and a
# human-readable summary.

import json


def build_net_settings(cfg):
    st = cfg.stackup
    classes_json = []
    summary = []
    for c in cfg.classes:
        w = c.target_width_mm(st)
        # sensible fallbacks for classes with no impedance/current width
        if w is None:
            w = 0.20 if c.kind == "relaxed" else 0.25
        entry = {
            "name": c.name,
            "clearance": round(c.clearance_mm, 3),
            "track_width": round(w, 3),
            "via_diameter": 0.6,
            "via_drill": 0.3,
            "diff_pair_width": round(w, 3),
            "diff_pair_gap": round(max(0.12, c.clearance_mm), 3),
        }
        z = c.z0_of(w, st) if c.kind == "impedance" else None
        classes_json.append(entry)
        summary.append((c.name, w, z, c.kind, c.note))

    # net -> class patterns: explicit class_map first, then the hs groups.
    # KiCad uses shell-style patterns; we translate the common regex forms.
    patterns = []
    for regex, cls in cfg.class_map:
        patterns.append({"pattern": _to_kicad_pattern(regex), "netclass": cls})
    for g in cfg.groups:
        patterns.append({"pattern": _to_kicad_pattern(g.match), "netclass": "hs_50"})

    net_settings = {"classes": classes_json, "net_class_patterns": patterns}
    return net_settings, summary


def _to_kicad_pattern(regex):
    # KiCad net-class patterns support regex when wrapped, but plain substrings
    # are simplest and most robust. keep the raw regex as a wildcard match.
    return "/.*(%s).*/" % regex if any(ch in regex for ch in "\\[](|") else "*%s*" % regex


def write(cfg, out_path):
    ns, summary = build_net_settings(cfg)
    with open(out_path, "w") as f:
        json.dump({"net_settings": ns}, f, indent=2)
    return ns, summary, out_path
