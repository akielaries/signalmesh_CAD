#!/usr/bin/env python3
# full-wave microstrip line on the APM/ACM stackup using openEMS (FDTD).
# extracts characteristic impedance and S-parameters vs frequency so you can
# validate the 50-ohm target from impedance.py and see FR4 loss over length,
# and (with --dump) writes a time-domain E-field animation for ParaView.
#
# run inside the openEMS venv:
#   ~/opt/openEMS/venv/bin/python3 openems_microstrip.py --len 30 --dump
#
# ground is the zmin PEC boundary (standard microstrip setup); the port adds
# the strip conductor. mesh is coarse along the line and fine across it.

import argparse
import os
import sys
import tempfile

try:
    import numpy as np
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS
    from openEMS.physical_constants import C0, EPS0
except Exception:
    sys.exit("openEMS python bindings not found. run inside the openEMS venv.")

from stackup import ER, TAN_D, COPPER_T, PREPREG_H


def run(length_mm, width_mm, f_max, do_dump, outdir, nrts, skip_run=False):
    # everything in micrometers, mirroring the openEMS MSL tutorial
    unit = 1e-6
    H = PREPREG_H / unit          # substrate height to reference plane, um
    W = width_mm * 1e-3 / unit
    L = length_mm * 1e-3 / unit / 2   # half length; ports meet at x=0

    # cap timesteps: the pulse is fully recorded and decays to ~-59 dB well
    # before the residual Mur late-time instability grows, so stop in between.
    fdtd = openEMS(NrTS=nrts, EndCriteria=1e-4)
    fdtd.SetGaussExcite(f_max / 2, f_max / 2)
    # PML in the propagation direction (x) is the stable choice; MUR on the
    # open sides. all-MUR causes a late-time instability. PML needs enough
    # x cells, so x is meshed finer below.
    fdtd.SetBoundaryCond(['PML_8', 'PML_8', 'MUR', 'MUR', 'PEC', 'MUR'])

    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    mesh = csx.GetGrid()
    mesh.SetDeltaUnit(unit)

    res = C0 / (f_max * np.sqrt(ER)) / unit / 50   # coarse, lambda/50
    # fine mesh near the strip must scale to the strip WIDTH, not the
    # wavelength: for a narrow 150 um strip the wavelength-scaled thirds
    # lines would cross each other and make degenerate (unstable) cells.
    edge = W / 3
    third = np.array([2 * edge / 3, -edge / 3])

    # x: fine enough that PML_8 has cells to spare along the propagation run
    mesh.AddLine('x', [-L, L])
    mesh.SmoothMeshLines('x', res / 4)
    # y: thirds rule at the two strip edges, fine within ~2 widths, open out
    mesh.AddLine('y', 0)
    mesh.AddLine('y', W / 2 + third)
    mesh.AddLine('y', -W / 2 - third)
    mesh.AddLine('y', [-2 * W, 2 * W])
    mesh.SmoothMeshLines('y', edge)
    mesh.AddLine('y', [-40 * W, 40 * W])
    mesh.SmoothMeshLines('y', res, 1.4)   # graded out to the sides
    # z: fine through the thin substrate, graded up into the air
    mesh.AddLine('z', np.linspace(0, H, 5))
    mesh.AddLine('z', 20 * H)
    mesh.SmoothMeshLines('z', res, 1.4)

    # lossy FR4 substrate (kappa from loss tangent at f_max/2)
    kappa = TAN_D * 2 * np.pi * (f_max / 2) * ER * EPS0
    sub = csx.AddMaterial('FR4', epsilon=ER, kappa=kappa)
    sub.AddBox([-L, -15 * W, 0], [L, 15 * W, H])

    # two MSL ports tile the whole line; together they form the strip end to
    # end. z spans substrate top (H) down to ground (0); exc_dir 'z'.
    pec = csx.AddMetal('PEC')
    p1 = fdtd.AddMSLPort(1, pec, [-L, -W / 2, H], [0, W / 2, 0], 'x', 'z',
                         excite=-1, FeedShift=10 * res, MeasPlaneShift=L / 3,
                         priority=10)
    p2 = fdtd.AddMSLPort(2, pec, [L, -W / 2, H], [0, W / 2, 0], 'x', 'z',
                         MeasPlaneShift=L / 3, priority=10)

    if do_dump:
        # time-domain E-field volume -> ParaView (writes Et_..vtr files)
        dump = csx.AddDump('Et', file_type=0, sub_sampling=[2, 2, 2])
        dump.AddBox([-L, -15 * W, 0], [L, 15 * W, 15 * H])

    if not skip_run:
        fdtd.Run(outdir, cleanup=False)

    f = np.linspace(f_max / 200, f_max, 400)
    p1.CalcPort(outdir, f, ref_impedance=50)
    p2.CalcPort(outdir, f, ref_impedance=50)
    z0 = np.abs(p1.uf_tot / p1.if_tot)
    # both ports face inward (toward x=0), so openEMS lands the injected
    # (incident) wave in the uf_ref bin and the reflected wave in uf_inc.
    # verified against the analytic S11 = (Z0-50)/(Z0+50) = -26.8 dB for
    # Z0=54.8 ohm. S11 = reflected/incident, S21 = transmitted/incident.
    s11 = p1.uf_inc / p1.uf_ref
    s21 = p2.uf_ref / p1.uf_ref
    return f, z0, s11, s21


def main():
    ap = argparse.ArgumentParser(description="openEMS microstrip Z0 / S-params on the APM/ACM stack")
    ap.add_argument("--len", type=float, default=30.0, help="line length, mm")
    ap.add_argument("--width", type=float, default=0.15, help="trace width, mm (0.15 ~ 50 ohm)")
    ap.add_argument("--fmax", type=float, default=2e9, help="max analysis frequency, Hz")
    ap.add_argument("--dump", action="store_true", help="also write E-field animation for ParaView")
    ap.add_argument("--plot", metavar="PNG", help="write Z0 and S-param plot")
    ap.add_argument("--nrts", type=int, default=50000,
                    help="max timesteps; capped to avoid late-time instability")
    ap.add_argument("--post-only", action="store_true",
                    help="reuse existing sim data, only redo post-processing")
    args = ap.parse_args()

    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "openems")
    os.makedirs(outdir, exist_ok=True)
    # openEMS chdir's into the sim dir during Run, so resolve plot path now
    plot_path = os.path.abspath(args.plot) if args.plot else None
    f, z0, s11, s21 = run(args.len, args.width, args.fmax, args.dump, outdir, args.nrts,
                          skip_run=args.post_only)

    print("width=%.3f mm  length=%.1f mm" % (args.width, args.len))
    print("%8s %8s %9s %9s" % ("f_GHz", "Z0_ohm", "S11_dB", "S21_dB"))
    for i in range(0, len(f), 40):
        print("%8.2f %8.1f %9.2f %9.2f" % (
            f[i] / 1e9, z0[i],
            20 * np.log10(abs(s11[i])), 20 * np.log10(abs(s21[i]))))
    print("\nZ0 at low freq: %.1f ohm   (raw dumps + fields in %s)" % (z0[1], outdir))

    if plot_path:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 7))
        a1.plot(f / 1e9, z0)
        a1.axhline(50, ls="--", c="r")
        a1.set_ylabel("Z0, ohm"); a1.set_xlabel("f, GHz")
        a1.set_title("characteristic impedance, w=%.3f mm on APM/ACM stack" % args.width)
        a2.plot(f / 1e9, 20 * np.log10(np.abs(s11)), label="S11 return loss")
        a2.plot(f / 1e9, 20 * np.log10(np.abs(s21)), label="S21 insertion loss")
        a2.set_ylabel("dB"); a2.set_xlabel("f, GHz"); a2.legend()
        a2.set_title("S-parameters, %.0f mm line" % args.len)
        fig.tight_layout(); fig.savefig(plot_path, dpi=110)
        print("wrote %s" % plot_path)


if __name__ == "__main__":
    main()
