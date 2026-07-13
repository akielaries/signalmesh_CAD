# coupled-line crosstalk model: two parallel microstrips over a ground plane,
# clean openEMS FDTD with proper MSL ports. this is the correct tool for
# trace-to-trace crosstalk -- it uses the real cross-section (width, gap,
# length, stackup) and gives trustworthy NEXT/FEXT plus a clean coupling field,
# without the whole-board port problems of gerber2ems on inner layers.
#
# ports:  P1 aggressor drive (x=-L)   P2 aggressor far (x=+L)
#         P3 victim near/NEXT (x=-L)   P4 victim far/FEXT (x=+L)

import os
import numpy as np
from CSXCAD import ContinuousStructure
from openEMS import openEMS
from openEMS.physical_constants import C0, EPS0


def run(outdir, length_mm, gap_mm, agg_w_mm, vic_w_mm, stackup,
        f_max=3e9, nrts=60000, dump=True, skip_run=False):
    os.makedirs(outdir, exist_ok=True)
    unit = 1e-6
    H = stackup.prepreg_h / unit                 # substrate height to ground
    Wa = agg_w_mm * 1e-3 / unit
    Wv = vic_w_mm * 1e-3 / unit
    sep = gap_mm * 1e-3 / unit                    # center-to-center
    L = length_mm * 1e-3 / unit / 2               # half length; ports at +-L
    er, tan_d = stackup.er, stackup.tan_d
    ya, yv = +sep / 2, -sep / 2                   # aggressor / victim centers

    fdtd = openEMS(NrTS=nrts, EndCriteria=1e-4)
    fdtd.SetGaussExcite(f_max / 2, f_max / 2)
    fdtd.SetBoundaryCond(['PML_8', 'PML_8', 'MUR', 'MUR', 'PEC', 'MUR'])

    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    mesh = csx.GetGrid()
    mesh.SetDeltaUnit(unit)

    res = C0 / (f_max * np.sqrt(er)) / unit / 50
    edge = min(Wa, Wv) / 3
    third = np.array([2 * edge / 3, -edge / 3])

    mesh.AddLine('x', [-L, L])
    mesh.SmoothMeshLines('x', res / 4)
    # y: thirds at all four trace edges, fine across the gap, graded out
    mesh.AddLine('y', [ya, yv])
    for c, W in [(ya, Wa), (yv, Wv)]:
        mesh.AddLine('y', c + W / 2 + third)
        mesh.AddLine('y', c - W / 2 - third)
    span = sep + 2 * max(Wa, Wv)
    mesh.AddLine('y', [-span, span])
    mesh.SmoothMeshLines('y', edge)
    mesh.AddLine('y', [-40 * max(Wa, Wv), 40 * max(Wa, Wv)])
    mesh.SmoothMeshLines('y', res, 1.4)
    mesh.AddLine('z', np.linspace(0, H, 5))
    mesh.AddLine('z', 20 * H)
    mesh.SmoothMeshLines('z', res, 1.4)

    kappa = tan_d * 2 * np.pi * (f_max / 2) * er * EPS0
    sub = csx.AddMaterial('FR4', epsilon=er, kappa=kappa)
    sub.AddBox([-L, -20 * max(Wa, Wv), 0], [L, 20 * max(Wa, Wv), H])

    pec = csx.AddMetal('PEC')
    # aggressor: driven (P1) + far (P2)
    p1 = fdtd.AddMSLPort(1, pec, [-L, ya - Wa / 2, H], [0, ya + Wa / 2, 0], 'x', 'z',
                         excite=-1, FeedShift=10 * res, MeasPlaneShift=L / 3, priority=10)
    p2 = fdtd.AddMSLPort(2, pec, [L, ya - Wa / 2, H], [0, ya + Wa / 2, 0], 'x', 'z',
                         MeasPlaneShift=L / 3, priority=10)
    # victim: near/NEXT (P3, same end as drive) + far/FEXT (P4)
    p3 = fdtd.AddMSLPort(3, pec, [-L, yv - Wv / 2, H], [0, yv + Wv / 2, 0], 'x', 'z',
                         MeasPlaneShift=L / 3, priority=10)
    p4 = fdtd.AddMSLPort(4, pec, [L, yv - Wv / 2, H], [0, yv + Wv / 2, 0], 'x', 'z',
                         MeasPlaneShift=L / 3, priority=10)

    if dump:
        d = csx.AddDump('Et', file_type=0, sub_sampling=[1, 1, 2])
        d.AddBox([-L, -span, 0], [L, span, H])

    if not skip_run:
        fdtd.Run(outdir, cleanup=False)

    f = np.linspace(f_max / 200, f_max, 400)
    for p in (p1, p2, p3, p4):
        p.CalcPort(outdir, f, ref_impedance=50)
    z0 = np.abs(p1.uf_tot / p1.if_tot)
    # incident wave on the driven aggressor. openEMS labels the two travelling
    # waves uf_inc/uf_ref by port orientation; take the larger one on the driven
    # port as the incident so the convention is self-calibrating.
    a_inc = p1.uf_inc if np.abs(p1.uf_inc).mean() > np.abs(p1.uf_ref).mean() else p1.uf_ref

    def coupled_wave(p):
        # the coupled/received wave on a passive port is whichever bin is larger
        return p.uf_ref if np.abs(p.uf_ref).mean() > np.abs(p.uf_inc).mean() else p.uf_inc
    s = {
        "f": f, "z0": z0,
        "s11": (p1.uf_ref if a_inc is p1.uf_inc else p1.uf_inc) / a_inc,
        "s21": coupled_wave(p2) / a_inc,   # aggressor through
        "s31": coupled_wave(p3) / a_inc,   # NEXT (near-end)
        "s41": coupled_wave(p4) / a_inc,   # FEXT (far-end)
        "ports": (p1, p2, p3, p4),
    }
    return s
