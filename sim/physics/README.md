# sim toolkit

signal-integrity helpers for the APM and ACM boards. built around the shared
4-layer FR4 stack (0.035 copper, 0.1 mm prepreg to inner plane, 1.24 mm core,
er 4.5, tan 0.02) read from the kicad_pcb stackup.

## runs today (numpy only)

impedance.py
  microstrip width for a target single-ended impedance on this stack.
  `python3 impedance.py --z 50`
  result: 50 ohm over the 0.1 mm sublayer needs a 0.150 mm trace (fabbable).

net_lengths.py
  routed copper length and via count per net, straight from a kicad_pcb.
  `python3 net_lengths.py ../../boards/APM/v5_r1/APM.kicad_pcb --filter 'FMC_DA|FMC_CLK'`
  use it to check length match against FMC_CLK and to spot outlier nets.

## field solve (openEMS)

setup_env.sh
  links the openEMS bindings (built at ~/opt/openEMS) into the user site so
  plain system python3 can import them, no venv activation. also installs h5py.

openems_microstrip.py
  full-wave FDTD of a controlled-impedance microstrip on this stack. the
  "Sonnet analog": a field solve of the real geometry, not a closed form.
  `python3 openems_microstrip.py --len 30 --width 0.15 --dump --plot out/openems_msl.png`
  result on this stack: a 0.15 mm trace measures Z0 = 54.8 ohm (S11 -26.8 dB
  vs a 50 ohm reference). writes out/openems_msl.png (Z0 + S-params) and, with
  --dump, ~1000 E-field frames in out/openems/ for ParaView.
  notes: the run is capped at --nrts 50000 timesteps to stop before a residual
  Mur late-time instability; --post-only re-does only the plotting from cached
  field data (seconds, no re-solve).

  see the field animation:  paraview out/openems/Et_..vtr

## suggested workflow

1. impedance.py to fix your controlled-impedance trace width.
2. net_lengths.py to find skew on the FMC bus and QSPI, then length-tune the
   worst offenders in kicad against FMC_CLK.
3. openems_microstrip.py to confirm Z0 and see FR4 loss at your net lengths.
4. for the DF40 connector transition specifically, either pull a Touchstone
   model from Hirose or extend the openEMS script to model the via+launch,
   then cascade with scikit-rf.
