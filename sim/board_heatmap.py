#!/usr/bin/env python3
# composite an openEMS |E| field dump over the board copper to get the
# crosstalk / EMI heatmap-over-layout look, on plain system python3.
# no blender, no bpy, no python3.11 - just vtk + numpy + matplotlib.
#
# inputs:
#   --field   a gerber2ems E-field dump dir (ems/simulation/0/et) or a single
#             .vtr file, or any openEMS Et_*.vtr dump
#   --copper  a grayscale copper-layer PNG (gerber2ems writes these to
#             ems/geometry/F_Cu.png etc.) to draw the board under the field
#   --frame   'peak' (default, the strongest frame) or an integer index
#   --anim    write every frame as heatmap_####.png for a movie
#
# usage:
#   python3 board_heatmap.py \
#     --field ~/trunk/OSS/gerber2ems/examples/filter/ems/simulation/0/et \
#     --copper ~/trunk/OSS/gerber2ems/examples/filter/ems/geometry/F_Cu.png \
#     --out out/board_heatmap.png

import argparse
import glob
import os
import sys
import numpy as np
import vtk
from vtk.util.numpy_support import vtk_to_numpy
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize


def read_vtr(path):
    r = vtk.vtkXMLRectilinearGridReader()
    r.SetFileName(path)
    r.Update()
    d = r.GetOutput()
    nx, ny, nz = d.GetDimensions()
    xc = vtk_to_numpy(d.GetXCoordinates())
    yc = vtk_to_numpy(d.GetYCoordinates())
    arr = d.GetPointData().GetArray(0)
    if arr is None:
        return None
    E = vtk_to_numpy(arr)
    if E.ndim == 2 and E.shape[1] == 3:
        E = E.reshape(nz, ny, nx, 3)
        mag = np.linalg.norm(E, axis=-1)
    else:
        mag = E.reshape(nz, ny, nx)
    # top copper slice (near the highest z with signal), collapse z by max
    top = mag.max(axis=0)                       # (ny, nx)
    extent = [xc.min(), xc.max(), yc.min(), yc.max()]
    return top, extent


def frames_from(field):
    if os.path.isfile(field):
        return [field]
    fr = sorted(glob.glob(os.path.join(field, "*.vtr")))
    return fr


def render(top, extent, copper_png, out, title):
    fig, ax = plt.subplots(figsize=(11, 8))
    if copper_png and os.path.exists(copper_png):
        cu = plt.imread(copper_png)
        if cu.ndim == 3:
            cu = cu[..., :3].mean(axis=-1)
        # copper as a dark board base, stretched to the field extent
        ax.imshow(cu, cmap="gray", extent=extent, origin="upper",
                  aspect="equal", vmin=0, vmax=1, alpha=0.9)
    # field heatmap on top, transparent where weak so the board shows through
    norm = Normalize(vmin=np.percentile(top, 50), vmax=np.percentile(top, 99.5))
    a = np.clip(norm(top), 0, 1) ** 0.6            # alpha ramps with strength
    ax.imshow(top, cmap="turbo", extent=extent, origin="lower",
              aspect="equal", norm=norm, alpha=a)
    ax.set_title(title)
    ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)")
    sm = plt.cm.ScalarMappable(cmap="turbo", norm=norm)
    fig.colorbar(sm, ax=ax, label="|E| field strength (arb)")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="field-over-board EMI heatmap (python3.13, no blender)")
    ap.add_argument("--field", required=True, help="E-field .vtr file or dump dir")
    ap.add_argument("--copper", default="", help="grayscale copper PNG to draw under the field")
    ap.add_argument("--frame", default="peak", help="'peak' or an integer frame index")
    ap.add_argument("--out", default="out/board_heatmap.png")
    ap.add_argument("--anim", action="store_true", help="render every frame as heatmap_####.png")
    args = ap.parse_args()

    frames = frames_from(args.field)
    if not frames:
        sys.exit("no .vtr frames found at %s" % args.field)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    if args.anim:
        for i, f in enumerate(frames):
            res = read_vtr(f)
            if res is None:
                continue
            top, extent = res
            render(top, extent, args.copper, "out/heatmap_%04d.png" % i,
                   "|E| over board, frame %d" % i)
        print("wrote out/heatmap_####.png (%d frames)" % len(frames))
        print("make a movie:  ffmpeg -i out/heatmap_%04d.png out/board_field.mp4")
        return

    if args.frame == "peak":
        # pick the frame with the strongest field
        best = None
        for f in frames:
            res = read_vtr(f)
            if res is None:
                continue
            s = res[0].sum()
            if best is None or s > best[0]:
                best = (s, res, f)
        if best is None:
            sys.exit("no readable field data in frames")
        _, (top, extent), f = best
    else:
        top, extent = read_vtr(frames[int(args.frame)])
        f = frames[int(args.frame)]

    render(top, extent, args.copper, args.out, "|E| field over board copper")
    print("wrote %s (from %s)" % (args.out, os.path.basename(f)))


if __name__ == "__main__":
    main()
