# signalmesh SI suite

Config-driven signal-integrity checks for the APM/ACM boards. One engine, one
per-board config, three tiers of verification. Replaces the earlier one-off
scripts (`hs_audit.py`, `impedance.py`, hand-edited openEMS setups) with a
single package driven entirely by the board's stackup and net classes.

## Layout

```
si/                engine (importable package)
  stackup.py       the 4-layer FR4 stack; everything derives from here
  impedance.py     microstrip/embedded Z0, IPC-2221 current capacity, delay
  netclass.py      trace-class rules; widths derived from the stackup
  kicad.py         dependency-free .kicad_pcb reader (length, width, vias, geometry)
  config.py        loads boards/<name>.yaml
  audit.py         tier-1 audit engine (impedance/length/skew/vias)
  report.py        ascii tables + matplotlib plots
  kicad_export.py  emits KiCad net-class rules
  crosstalk.py     tier-3 openEMS crosstalk: geometry -> ports -> S-params
boards/            per-board config: APM_v5_r2.yaml, ACM_v1_r2.yaml
si-audit           CLI: tier 0/1
si-netclass        CLI: emit KiCad net-class rules for a re-route
si-coupled         CLI: tier 3 crosstalk (coupled-line model) -- the trustworthy one
si-crosstalk       CLI: tier 3 whole-board crosstalk (top-layer nets only)
si-render          CLI: render board field visuals from a gerber2ems run
```

## The method (why this beats per-signal hacks)

1. The **stackup** is the single source of truth. Trace widths for every class
   are computed from it, not hand-picked.
2. **Net classes** encode the design rules per trace type (power by current,
   hs_50 by impedance, slow/audio relaxed, usb_diff). `si-netclass` turns them
   into KiCad rules so the re-route enforces them automatically.
3. **Tiered verification**, cheapest first, re-runnable per revision:
   - tier 0/1 `si-audit`  seconds  impedance + length + skew + via audit
   - tier 3   `si-crosstalk` targeted  full-wave coupling on the worst nets only
   openEMS is reserved for the few nets that earn it; it is never the whole board.

## Usage

```
# tier 0/1: audit a board against its class targets (+ plots)
./si-audit APM_v5_r2 --plot
./si-audit ACM_v1_r2                 # auto-discover mode (no named buses yet)

# emit KiCad net-class rules (stackup-derived widths) for the re-route
./si-netclass APM_v5_r2

# tier 3 crosstalk -- the TRUSTWORTHY path: coupled-line model with your real
# width/gap/length. clean NEXT/FEXT numbers + a clean coupling field, ~1 min.
./si-coupled APM_v5_r2 FMC_NWAIT --auto 1 --field

# tier 3 whole-board crosstalk (gerber2ems). only valid for TOP/BOTTOM outer-
# layer nets -- the port can't launch into an inner-layer trace (that's why
# NWAIT/DA13, which are inner, give boundary-artifact fields; use si-coupled).
./si-crosstalk APM_v5_r2 <TOP_LAYER_NET> --auto 1
./si-render APM_v5_r2 --anim                        # render its board field
```

The crosstalk field movie is rendered from the openEMS dump with:

```
python board_heatmap.py --field 'g2ems_apm/ems/simulation/0/e_field_In1_Cu_*.vtr' \
    --copper g2ems_apm/ems/geometry/In1_Cu.png --agg rms --out out/xtalk.png
```

## Adding constraints to a new revision

Edit `boards/<name>.yaml`: point `kicad_pcb` at the board, list high-speed
`groups` (regex + reference clock) and `class_map` (net regex -> class). The
audit and net-class export both read it. No code changes.

## Caveats

- Impedance uses closed-form microstrip / embedded-microstrip (good to a few
  percent). tier-3 openEMS is the ground truth when it matters.
- `si-crosstalk` needs the board's gerbers staged in `ems_dir/fab/` (as
  `g2ems_apm/` is for the APM). Export them from KiCad for a new board.
- The gerber2ems MSL port models trace-over-plane. It is NOT valid for exciting
  a power-plane pair (that needs a lumped port); use these tools on traces.
