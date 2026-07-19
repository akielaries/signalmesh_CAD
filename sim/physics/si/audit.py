# tier-1 audit engine. assigns every routed net to a class, computes its Z0
# from the routed width, flags the electrically-long nets that are off target,
# and checks intra-bus skew for the named groups. pure data; report.py renders.

import re
from dataclasses import dataclass, field
from . import impedance

OK, WARN, FAIL = 0, 1, 2

POWER_RE = re.compile(r"(?:^|[/_])(?:\+?5V|3V3|3\.3|1V8|2V5|VDD|VCC|VBUS|PWR|VIN)", re.I)
GND_RE = re.compile(r"^/?GND$|(?:^|[/_])GND", re.I)
AUDIO_RE = re.compile(r"DAC|AUDIO|OUT_[LR]|VOL_", re.I)


@dataclass
class NetResult:
    name: str
    cls: str
    length_mm: float
    width_mm: float
    z0: float
    vias: int
    layers: list
    electrically_long: bool
    z_target: float
    sev: int = OK
    reasons: list = field(default_factory=list)


@dataclass
class GroupResult:
    name: str
    clock_mhz: float
    period_ps: float
    budget_ps: float
    z_target: float
    rows: list = field(default_factory=list)   # (net, length, z0, skew_ps, vias, sev)


@dataclass
class AuditResult:
    board: str
    crit_len_mm: float
    nets: list                       # list[NetResult], all routed nets
    groups: list                     # list[GroupResult]
    class_targets: dict              # class name -> (target_width_mm, z0)


def classify(name, groups, classes_by_name, class_map):
    # explicit per-board mapping wins
    for pattern, cls_name in class_map:
        if re.search(pattern, name):
            if cls_name not in classes_by_name:
                continue
            c = classes_by_name[cls_name]
            return cls_name, (c.z_target if c.kind == "impedance" else None)
    for g in groups:
        if re.search(g.match, name):
            return "hs_50", g.z_target
    if GND_RE.search(name):
        return None, None            # planes: skip
    if POWER_RE.search(name):
        return "power_main", None
    if AUDIO_RE.search(name):
        return "audio_analog", None
    return "default", classes_by_name["default"].z_target


def run(cfg, board):
    st = cfg.stackup
    cbn = cfg.classes_by_name
    crit = impedance.critical_length_mm(cfg.rise_ps, st, "inner")
    pd_inner = impedance.delay_ps_per_mm(st, "inner")

    class_targets = {}
    for c in cfg.classes:
        w = c.target_width_mm(st)
        class_targets[c.name] = (w, c.z0_of(w, st) if w else None)

    results = []
    for name, net in board.nets.items():
        if net.length_mm < 1.0:
            continue
        cls_name, z_target = classify(name, cfg.groups, cbn, cfg.class_map)
        if cls_name is None:
            continue
        cls = cbn[cls_name]
        w = net.dominant_width
        elong = net.length_mm > crit
        z0 = cls.z0_of(w, st) if (w and cls.kind == "impedance") else None
        sev = OK
        reasons = []
        if cls.kind == "impedance":
            zt = z_target if z_target else cls.z_target
            if z0 is not None and elong:
                off = abs(z0 - zt) / zt
                if off > cls.z_tol:
                    sev = max(sev, FAIL if off > 2 * cls.z_tol else WARN)
                    reasons.append("Z0 %.0f vs %.0f ohm (%.0f%% off)" % (z0, zt, off * 100))
        elif cls.kind == "current":
            tw = class_targets[cls.name][0]
            if w is not None and tw and w < tw * 0.95:
                cap = impedance.ampacity_a(w * 1e-3)
                sev = max(sev, WARN)
                reasons.append("w %.2f < %.2f mm target (~%.1f A cap)" % (w, tw, cap))
        if net.vias >= 4:
            sev = max(sev, WARN)
            reasons.append("%d vias" % net.vias)
        results.append(NetResult(name, cls_name, net.length_mm, w or 0.0,
                                  z0 if z0 else 0.0, net.vias, sorted(net.layers),
                                  elong, z_target or (cls.z_target or 0), sev, reasons))
    results.sort(key=lambda r: (-r.sev, -r.length_mm))

    # named-group skew audit
    groups = []
    for g in cfg.groups:
        members = [(n, net) for n, net in board.nets.items()
                   if re.search(g.match, n) and net.length_mm >= 1.0]
        if not members:
            continue
        period = 1e6 / g.clock_mhz
        budget = g.skew_fraction * period
        clk_len = None
        for n, net in members:
            if g.clock and n == g.clock:
                clk_len = net.length_mm
        if clk_len is None:
            clk_len = sorted(net.length_mm for _, net in members)[len(members) // 2]
        clk_delay = clk_len * pd_inner
        rows = []
        for n, net in members:
            skew = net.length_mm * pd_inner - clk_delay
            z0 = cbn["hs_50"].z0_of(net.dominant_width, st) if net.dominant_width else 0
            s = OK
            if abs(skew) > budget:
                s = FAIL
            elif abs(skew) > 0.5 * budget:
                s = WARN
            rows.append((n, net.length_mm, z0, skew, net.vias, s))
        rows.sort(key=lambda r: -abs(r[3]))
        groups.append(GroupResult(g.name, g.clock_mhz, period, budget, g.z_target, rows))

    return AuditResult(cfg.name, crit, results, groups, class_targets)
