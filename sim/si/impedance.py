# transmission-line impedance + current-capacity math, numpy-free.
# microstrip: hammerstad-jensen with thickness correction.
# embedded/inner: microstrip against the nearest plane (the dominant coupling)
#   with a small er_eff bump for the second dielectric interface. good to a few
#   percent for these stacks; the tier-3 openems run is the ground truth.

import math


def z0_microstrip(w, h, t, er):
    """characteristic impedance (ohm) and er_eff for a microstrip.
    w,h,t in meters. reference plane one dielectric (h) away."""
    if h <= 0 or w <= 0:
        return float("nan"), float("nan")
    if t > 0:
        dw = (t / math.pi) * math.log(
            1 + 4 * math.e / (t / h) / ((1 / math.tanh(math.sqrt(6.517 * (w / h)))) ** 2))
        we = w + dw
    else:
        we = w
    u = we / h
    a = (1 + (1 / 49.0) * math.log((u ** 4 + (u / 52.0) ** 2) / (u ** 4 + 0.432))
         + (1 / 18.7) * math.log(1 + (u / 18.1) ** 3))
    b = 0.564 * ((er - 0.9) / (er + 3.0)) ** 0.053
    ee = (er + 1) / 2 + (er - 1) / 2 * (1 + 10.0 / u) ** (-a * b)
    f = 6 + (2 * math.pi - 6) * math.exp(-(30.666 / u) ** 0.7528)
    z01 = 60 * math.log(f / u + math.sqrt(1 + (2 / u) ** 2))
    return z01 / math.sqrt(ee), ee


def z0_for_layer(w, stackup, layer_kind):
    """z0 for a trace of width w (m) given its layer role.
    layer_kind: 'outer' (microstrip, ref one prepreg away) or
    'inner' (embedded microstrip, ref the near plane one prepreg away, but
    fully embedded in dielectric so er_eff -> er is higher)."""
    if layer_kind == "inner":
        # embedded microstrip: both sides dielectric -> use full er for the
        # upper region too, approximated by referencing the near plane and
        # nudging er_eff toward er
        z, ee = z0_microstrip(w, stackup.prepreg_h, stackup.copper_t, stackup.er)
        ee_emb = ee + 0.45 * (stackup.er - ee)
        return z * math.sqrt(ee / ee_emb), ee_emb
    return z0_microstrip(w, stackup.prepreg_h, stackup.copper_t, stackup.er)


def solve_width(z_target, stackup, layer_kind="outer"):
    """bisection: trace width (m) that hits z_target (ohm) on this stack."""
    lo, hi = 0.02e-3, 6e-3
    for _ in range(90):
        mid = (lo + hi) / 2
        z, _ = z0_for_layer(mid, stackup, layer_kind)
        if z > z_target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def er_eff(stackup, layer_kind="outer"):
    _, ee = z0_for_layer(0.15e-3, stackup, layer_kind)
    return ee


C0_MM_PER_PS = 299792458.0 * 1e3 / 1e12   # speed of light, mm/ps


def delay_ps_per_mm(stackup, layer_kind="outer"):
    """propagation delay along the trace, ps per mm."""
    return math.sqrt(er_eff(stackup, layer_kind)) / C0_MM_PER_PS


def critical_length_mm(rise_ps, stackup, layer_kind="outer", frac=1.0 / 6.0):
    """trace length above which impedance matters, for a given edge rise time.
    default: flight time > rise/6 (conservative)."""
    return frac * rise_ps / delay_ps_per_mm(stackup, layer_kind)


def ampacity_a(w_m, copper_oz=1.0, dT=10.0, external=True):
    """IPC-2221 current capacity (A) for a trace of width w (m).
    I = k * dT^0.44 * A_mils2^0.725, A = width*thickness in mils^2."""
    t_mils = 1.378 * copper_oz            # 1 oz = 1.378 mils
    w_mils = (w_m * 1e3) / 0.0254
    area = w_mils * t_mils
    k = 0.048 if external else 0.024
    return k * dT ** 0.44 * area ** 0.725


def width_for_current(amps, copper_oz=1.0, dT=10.0, external=True):
    """min trace width (m) to carry `amps` within dT rise (IPC-2221)."""
    k = 0.048 if external else 0.024
    t_mils = 1.378 * copper_oz
    area = (amps / (k * dT ** 0.44)) ** (1 / 0.725)   # mils^2
    w_mils = area / t_mils
    return w_mils * 0.0254 * 1e-3
