# APM whole-board field sim (gerber2ems)

full-wave openEMS run driven from the APM gerbers, to get a field heatmap over
the real board. this is the "see the whole board" path.

## what is staged here

fab/               APM gerbers renamed to the gerber2ems convention + drill
fab/stackup.json   real APM 4-layer stack (er 4.5, 0.1 prepreg, 1.24 core)
fab/APM-top-pos.csv  two simulation ports on net FMC_NWAIT (U10 <-> J1 DF40)
simulation.json    frequency 0.1-3 GHz, ports, mesh grid

## run it

runs on system python3 (no venv). commands (gerber2ems, ems2png, ems2paraview)
are on PATH via ~/.local/bin. mesh is coarsened (pixel_size 25, grid 150/1000)
so the grid solver finishes on the full board; go finer later if needed.

    cd sim/g2ems_apm

    # 1. geometry: rasterize gerbers + build mesh. must end with "Saving geometry"
    gerber2ems -g 2>&1 | tee geom.log

    # 2. simulate: the long FDTD, with field export for the heatmap
    gerber2ems -s --export-field cu-outer --oversampling 8 2>&1 | tee sim.log

    # 3. postprocess: S-parameters + impedance plots
    gerber2ems -p 2>&1 | tee post.log

    # (or fold 1-3 into one)
    gerber2ems -a --export-field cu-outer --oversampling 8 2>&1 | tee run.log

monitor in another terminal:

    tail -f sim.log    # watch "Energy: ~... (-NN dB)" fall toward -40..-60 dB = done
    htop               # cpu/ram

## view the whole-board heatmap (python3.13, no blender)

field frames land in ems/simulation/0/et/ near the END of the sim step.

    python3 ../board_heatmap.py --field ems/simulation/0/et \
        --copper ems/geometry/F_Cu.png --out out/apm_heatmap.png
    # animate every frame:  add --anim   then  ffmpeg -i out/heatmap_%04d.png ...
    # interactive 3D:       ems2paraview 1

results also land in ems/results/ (S-parameters).

## two big caveats

1. compute. FMC_NWAIT runs ~87 mm corner-to-corner across a 72x104 mm board,
   so this is essentially a full-board FDTD: tens of minutes to hours (ram is
   not the limit, wall-clock is). the mesh is already coarsened. if the
   geometry step hangs on "generate X axis", coarsen further: pixel_size 40,
   grid max 2000 (that fsolve-based grid solver is the weak point on big boards).

2. port placement. the SP1/SP2 coordinates were derived from the .kicad_pcb
   pad positions (pos frame = pcb x, -pcb y, matched to production/positions.csv).
   this should match the gerber frame, but the robust method is to place two
   "Simulation_Port" footprints in KiCad at the probe points and re-export the
   gerbers + position file, guaranteeing a consistent frame. verify the ports
   land on the trace in the geometry step (`gerber2ems -g`) before the full run.

## the pretty animation (optional, Blender)

ems2paraview gives the quick interactive view. for the polished field-over-PCB
animation like the antmicro demo you additionally need: blender, antmicro's
picknblend + pcbooth, and the EMS_Plane.blend template. ems2png makes the field
PNG sequence that gets textured onto the board model.
