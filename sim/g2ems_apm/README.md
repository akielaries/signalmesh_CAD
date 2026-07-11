# APM whole-board field sim (gerber2ems)

full-wave openEMS run driven from the APM gerbers, to get a field heatmap over
the real board. this is the "see the whole board" path.

## what is staged here

fab/               APM gerbers renamed to the gerber2ems convention + drill
fab/stackup.json   real APM 4-layer stack (er 4.5, 0.1 prepreg, 1.24 core)
fab/APM-top-pos.csv  two simulation ports on net FMC_NWAIT (U10 <-> J1 DF40)
simulation.json    frequency 0.1-3 GHz, ports, mesh grid

## run it (after `sudo apt install gerbv`)

    cd sim/g2ems_apm
    gerber2ems -a --export-field outer cu-outer --oversampling 16
    ems2png 1                 # field snapshot PNGs
    ems2paraview 1            # interactive 3D field view (ParaView installed)

results land in ems/results/ (S-parameters) and the field dumps for viewing.

## two big caveats

1. compute. FMC_NWAIT runs ~87 mm corner-to-corner across a 72x104 mm board,
   so this is essentially a full-board FDTD: millions of cells, likely GB of
   RAM and a long run. for a fast first result prefer a short, localized net,
   or crop the gerbers to the region of interest.

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
