#!/usr/bin/env python3
# render a colored |E| field heatmap from an openEMS Et_*.vtr frame.
# this is the "shaded" visual: it shows where the electric field is strong
# around the trace, the same physics an EMI heatmap shows, for the geometry
# that was actually simulated (here, one microstrip line).

import glob
import os
import sys
import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_vtr(path):
    r = vtk.vtkXMLRectilinearGridReader()
    r.SetFileName(path)
    r.Update()
    d = r.GetOutput()
    nx, ny, nz = d.GetDimensions()
    xc = vtk_to_numpy(d.GetXCoordinates())
    yc = vtk_to_numpy(d.GetYCoordinates())
    zc = vtk_to_numpy(d.GetZCoordinates())
    E = vtk_to_numpy(d.GetPointData().GetArray(0))    # (npts, 3), x fastest
    E = E.reshape(nz, ny, nx, 3)
    mag = np.linalg.norm(E, axis=-1)                  # (nz, ny, nx)
    return xc, yc, zc, mag


def main():
    frames = sorted(glob.glob("out/openems/Et_*.vtr"))
    if not frames:
        sys.exit("no field frames in out/openems/ - run openems_microstrip.py --dump first")
    # default: a frame partway through, where the field is strong
    path = sys.argv[1] if len(sys.argv) > 1 else frames[len(frames) // 3]
    xc, yc, zc, mag = read_vtr(path)

    ix0 = len(zc) // 2
    yc_mm, xc_mm, zc_mm = yc * 1e3, xc * 1e3, zc * 1e3
    # top-down slice at the strip layer (lowest z with field), and a vertical
    # cross-section through the strip centre
    ztop = 1                     # just above the substrate/strip
    ymid = len(yc) // 2
    top = mag[ztop, :, :]        # (ny, nx)
    side = mag[:, ymid, :]       # (nz, nx)

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11, 7))
    im1 = a1.pcolormesh(xc_mm, yc_mm, top, shading="auto", cmap="turbo")
    a1.set_title("|E| top view at the trace layer  (frame %s)" % os.path.basename(path))
    a1.set_xlabel("x along trace, mm"); a1.set_ylabel("y, mm")
    fig.colorbar(im1, ax=a1, label="|E| (V/m, arb)")
    im2 = a2.pcolormesh(xc_mm, zc_mm, side, shading="auto", cmap="turbo")
    a2.set_title("|E| cross-section through trace centre (field concentrates in the dielectric)")
    a2.set_xlabel("x along trace, mm"); a2.set_ylabel("z height, mm")
    a2.set_ylim(0, zc_mm[min(len(zc) - 1, 6)])
    fig.colorbar(im2, ax=a2, label="|E| (V/m, arb)")
    fig.tight_layout()
    out = "out/field_slice.png"
    fig.savefig(out, dpi=110)
    print("wrote %s from %s" % (out, path))


if __name__ == "__main__":
    main()
