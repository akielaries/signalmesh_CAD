# net-class rules: the design constraints per trace type. each class knows how
# to turn the stackup into a target trace width, and how to judge a routed net.
# this is the single source of truth the audit and the kicad export both read.

from dataclasses import dataclass
from . import impedance


@dataclass
class NetClass:
    name: str
    kind: str                 # "impedance" | "current" | "relaxed"
    layer_kind: str = "outer"  # outer microstrip or inner embedded
    z_target: float = None     # ohm, for kind=="impedance"
    z_tol: float = 0.10        # +/- fraction warn threshold
    current_a: float = None    # A, for kind=="current"
    clearance_mm: float = 0.15
    note: str = ""

    def target_width_mm(self, stackup):
        if self.kind == "impedance":
            return impedance.solve_width(self.z_target, stackup, self.layer_kind) * 1e3
        if self.kind == "current":
            return impedance.width_for_current(self.current_a) * 1e3
        return None   # relaxed: no width target

    def z0_of(self, width_mm, stackup):
        if width_mm is None:
            return None
        z, _ = impedance.z0_for_layer(width_mm * 1e-3, stackup, self.layer_kind)
        return z


# the standard classes for the ACM synth boards. widths are DERIVED from the
# stackup at runtime, not hard-coded, so they stay correct if the stack changes.
DEFAULT_CLASSES = [
    NetClass("power_main", "current", current_a=1.5, clearance_mm=0.25,
             note="main rails: size by current (LDO/supply amps)"),
    NetClass("power_local", "current", current_a=0.5, clearance_mm=0.2,
             note="decoupling / short local power"),
    NetClass("hs_50", "impedance", layer_kind="inner", z_target=50.0, clearance_mm=0.2,
             note="controlled 50 ohm SE: FMC/QSPI runs > critical length"),
    NetClass("audio_analog", "relaxed", clearance_mm=0.3,
             note="DAC/analog: low-R + isolation, impedance not critical"),
    NetClass("usb_diff", "impedance", layer_kind="inner", z_target=45.0, z_tol=0.15,
             clearance_mm=0.2, note="USB D+/D-: 90 ohm differential ~ 45 ohm each SE"),
    NetClass("slow", "relaxed", clearance_mm=0.15,
             note="slow buses (I2C/UART/GPIO): impedance not critical"),
    NetClass("default", "impedance", layer_kind="inner", z_target=50.0, z_tol=0.20,
             clearance_mm=0.15, note="everything else; loose 50 ohm"),
]


def by_name(classes):
    return {c.name: c for c in classes}


def load_classes(spec):
    """spec is 'default' or a list of dicts from a board yaml."""
    if spec in (None, "default"):
        return list(DEFAULT_CLASSES)
    out = []
    for d in spec:
        out.append(NetClass(**d))
    return out
