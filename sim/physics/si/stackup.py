# board stackup model. one place that owns the layer physics; everything
# (impedance targets, net-class widths, the openems sim) derives from here.

from dataclasses import dataclass


@dataclass(frozen=True)
class Stackup:
    """a 4-layer FR4 stack, dimensions in meters."""
    name: str
    er: float               # relative permittivity of the dielectric
    tan_d: float            # loss tangent
    copper_t: float         # copper thickness (1 oz = 35 um)
    prepreg_h: float        # outer copper <-> nearest inner layer
    core_h: float           # inner layer <-> inner layer
    # layer roles top->bottom; "signal" or "plane"
    layers: tuple = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")

    @property
    def outer_to_far(self):
        # an inner signal referenced to the far plane across prepreg+copper+core
        return self.prepreg_h + self.copper_t + self.core_h


# the APM and ACM boards share this stack (read from the kicad_pcb stackup block)
DEFAULT = Stackup(
    name="apm_acm_4layer_fr4",
    er=4.5,
    tan_d=0.02,
    copper_t=0.035e-3,
    prepreg_h=0.10e-3,
    core_h=1.24e-3,
)

PRESETS = {"default": DEFAULT}


def get(name):
    if name in PRESETS:
        return PRESETS[name]
    raise KeyError("unknown stackup preset %r (have %s)" % (name, list(PRESETS)))
