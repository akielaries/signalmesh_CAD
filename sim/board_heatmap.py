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
    # a glob pattern (e.g. ".../e_field_In1_Cu_*.vtr") to pick one layer out of
    # a run dir that holds several layers' dumps
    if any(c in field for c in "*?["):
        return sorted(glob.glob(field))
    fr = sorted(glob.glob(os.path.join(field, "*.vtr")))
    return fr


def mask_border(top, extent, board_mm, inset_mm=1.5):
    """NaN-out the margin outside the board and a thin inset ring, so domain-edge
    field spikes don't dominate the color scale. board_mm=(w,h) in mm."""
    ny, nx = top.shape
    xs = np.linspace(extent[0], extent[1], nx) * 1000.0   # mm
    ys = np.linspace(extent[2], extent[3], ny) * 1000.0
    bw, bh = board_mm
    mx = (xs >= inset_mm) & (xs <= bw - inset_mm)
    my = (ys >= inset_mm) & (ys <= bh - inset_mm)
    m = np.outer(my, mx)
    out = top.copy()
    out[~m] = np.nan
    return out


def render(top, extent, copper_png, out, title, lognorm=True, vmax=None, marks=None):
    from matplotlib.colors import LogNorm
    fig, ax = plt.subplots(figsize=(11, 8))
    fig.patch.set_facecolor("black"); ax.set_facecolor("black")
    if copper_png and os.path.exists(copper_png):
        cu = plt.imread(copper_png)
        if cu.ndim == 3:
            cu = cu[..., :3].mean(axis=-1)
        # dark PCB base: copper a dim gray, clearances/gaps near black, so the
        # board reads like a real board and the field glows on top.
        # origin="lower" to match the field: gerbv writes the PNG pcb-y-min-up,
        # same sense as the field's ascending y -> the two align.
        board = 0.10 + 0.28 * cu
        ax.imshow(board, cmap="gray", extent=extent, origin="lower",
                  aspect="equal", vmin=0, vmax=1)
    # field heatmap on top, transparent where weak so the board shows through
    pos = top[np.isfinite(top) & (top > 0)]
    if vmax is None:
        vmax = np.nanpercentile(top, 99.5)
    # degenerate frame (all ~zero, e.g. early in a movie): draw board only
    if not (np.isfinite(vmax) and vmax > 0 and pos.size):
        norm = Normalize(vmin=0, vmax=1)
    elif lognorm:
        vmin = max(np.percentile(pos, 60), vmax * 1e-2)
        if not (vmin < vmax):
            vmin = vmax * 1e-2
        norm = LogNorm(vmin=vmin, vmax=vmax)
    else:
        norm = Normalize(vmin=np.nanpercentile(top, 50), vmax=vmax)
    fld = np.nan_to_num(top, nan=0.0)
    a = np.clip(norm(np.clip(fld, 1e-30, None)), 0, 1) ** 0.7   # alpha ramps with strength
    a[~np.isfinite(top)] = 0.0                                  # fully transparent in masked margin
    ax.imshow(fld, cmap="turbo", extent=extent, origin="lower",
              aspect="equal", norm=norm, alpha=a)
    # position markers (list of (x_mm, y_mm, label, color)), board-relative mm
    for (xmm, ymm, lbl, col) in (marks or []):
        ax.plot(xmm / 1000.0, ymm / 1000.0, "o", mfc="none", mec=col, mew=2, ms=14)
        ax.annotate(lbl, (xmm / 1000.0, ymm / 1000.0), color=col, fontsize=9,
                    xytext=(8, 8), textcoords="offset points", weight="bold")
    ax.set_title(title, color="white")
    ax.set_xlabel("x (m)", color="white"); ax.set_ylabel("y (m)", color="white")
    ax.tick_params(colors="white")
    sm = plt.cm.ScalarMappable(cmap="turbo", norm=norm)
    cb = fig.colorbar(sm, ax=ax, label="|E| field magnitude (arb.)")
    cb.ax.yaxis.label.set_color("white"); cb.ax.tick_params(colors="white")
    fig.tight_layout()
    fig.savefig(out, dpi=120, facecolor="black")
    plt.close(fig)


def aggregate(frames, mode):
    """time-collapse a stack of frames: 'rms', 'mean', or 'peak' (single strongest)."""
    acc = None; n = 0; extent = None
    best = None
    for f in frames:
        res = read_vtr(f)
        if res is None:
            continue
        top, extent = res
        if mode == "peak":
            s = top.sum()
            if best is None or s > best[0]:
                best = (s, top)
            continue
        acc = (top ** 2 if mode == "rms" else top) if acc is None else acc + (top ** 2 if mode == "rms" else top)
        n += 1
    if mode == "peak":
        return (None if best is None else best[1]), extent
    if acc is None:
        return None, extent
    field = np.sqrt(acc / n) if mode == "rms" else acc / n
    return field, extent


def main():
    ap = argparse.ArgumentParser(description="field-over-board EMI heatmap (python3.13, no blender)")
    ap.add_argument("--field", required=True, help="E-field .vtr file or dump dir")
    ap.add_argument("--copper", default="", help="grayscale copper PNG to draw under the field")
    ap.add_argument("--frame", default=None, help="an integer frame index (overrides --agg)")
    ap.add_argument("--agg", default="rms", choices=["rms", "mean", "peak"],
                    help="time-collapse across frames: rms (PDN field map), mean, or peak")
    ap.add_argument("--out", default="out/board_heatmap.png")
    ap.add_argument("--anim", action="store_true", help="render every frame as heatmap_####.png")
    args = ap.parse_args()

    frames = frames_from(args.field)
    if not frames:
        sys.exit("no .vtr frames found at %s" % args.field)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    if args.anim:
        # fixed global scale so colors are comparable across the movie
        gmax = 0.0
        stack = []
        for f in frames:
            res = read_vtr(f)
            if res is None:
                continue
            stack.append(res)
            gmax = max(gmax, np.percentile(res[0], 99.9))
        for i, (top, extent) in enumerate(stack):
            render(top, extent, args.copper, "out/heatmap_%04d.png" % i,
                   "|E| over board, frame %d" % i, vmax=gmax)
        print("wrote out/heatmap_####.png (%d frames)" % len(stack))
        print("make a movie:  ffmpeg -i out/heatmap_%04d.png out/board_field.mp4")
        return

    if args.frame is not None:
        top, extent = read_vtr(frames[int(args.frame)])
        title = "|E| over board, frame %s" % args.frame
    else:
        top, extent = aggregate(frames, args.agg)
        title = "|E| over board (%s over %d frames)" % (args.agg, len(frames))
    if top is None:
        sys.exit("no readable field data in frames")

    render(top, extent, args.copper, args.out, title)
    print("wrote %s" % args.out)


if __name__ == "__main__":
    main()
