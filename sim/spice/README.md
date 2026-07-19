# Audio board — analog simulation checks

Behavioral SPICE checks for the analog blocks, so you can validate the **design/topology**
before committing copper (no breadboard). Uses `libngspice.so` (bundled with KiCad) driven
from Python via `ctypes` — **no ngspice binary and no pip packages required**.

## Run it

```sh
cd pub/signalmesh_CAD/sim/spice
make sim          # run all checks
make sim-svf      # just the state-variable filter
make sim-phaser   # just the phaser
make help         # list targets
make clean        # remove scratch files
```

Each check prints its measured numbers and `PASS` / `FAIL`, and exits non-zero on failure
(so `make sim` fails the build if a block regresses).

## What these are (and aren't)

These use an **ideal behavioral OTA** (`Iout = gm·(V+ − V−)`, where `gm ≈ Iabc/2Vt`). They
verify the **topology and control behavior** — the right filter shapes, resonance, and that
cutoff/notches track the bias current. They do **not** model real-device limits (OTA linear
range, noise, offset, slew, the LM13700's linearizing diodes). For those, drop a real LM13700
SPICE subckt into the decks — the harness (`spice.py`) takes any deck string.

They also do **not** check your *schematic wiring* — that's what the KiCad netlist/ERC pass is
for. Design correctness (here) and wiring correctness (ERC) are separate; you want both.

## Targets / thresholds

Edit the constants at the top of each `test_*.py` to match your spec.

### `test_svf.py` — state-variable filter
| check | threshold | meaning |
|---|---|---|
| LP passband | ≤ **+3 dB** at 0.02·f0 | lowpass passes below cutoff |
| LP rolloff | ≤ **−20 dB** at 10·f0 | 2-pole rolloff present (ideal ≈ −40 dB) |
| HP rolloff | ≤ **−20 dB** at f0/10 | highpass rejects below cutoff |
| BP peak | ≥ **+3 dB** | resonance actually peaks |
| BP peak location | **0.6–1.6× f0** | peak lands at the design cutoff |
| cutoff tracking | **6–15×** for 10× Iabc | cutoff is voltage-controlled |

Current result: LP@10f0 = −40 dB, BP peak +16.5 dB @ 1002 Hz, cutoff tracks **10.0×**. ✅

### `test_phaser.py` — phaser
| check | threshold | meaning |
|---|---|---|
| all-pass flatness | spread ≤ **0.5 dB** | each stage is a true all-pass (phase-only) |
| Vlp rolloff | ≤ **−15 dB** at 20·f0 | the LP driving the phase shift actually filters |
| notch depth | dips below **−3 dB** | the 4-stage cascade forms notches |
| notch movement | ≥ **2×** for ~8× Iabc | notches sweep with the LFO/bias (the phaser effect) |

Current result: flatness 0.00 dB, notches move **7.9×**. ✅

## Adding a block

1. Write `test_<block>.py` (copy an existing one): build the deck string, `run()` it, read the
   `wrdata` file with `read_wrdata()`, assert against thresholds, `sys.exit(0/1)`.
2. Add a `sim-<block>` target to the `Makefile` and to the `sim-all` prerequisites.

To simulate the *real* circuit later, export the KiCad schematic to a SPICE netlist and add
device models (LM13700, OPA1678) instead of the behavioral OTA.

## Simulating the ACTUAL schematic (not just hand-decks)

`make sim-real` builds SPICE decks directly from the exported KiCad netlist, so it
tests the *real wiring and component values* in the `.kicad_sch` - catching wiring
or value bugs the hand-written topology decks can't.

Flow (`netsim.py`):
1. `kicad-cli sch export netlist --format kicadsexpr` on a sheet (e.g. MASTER_FILTER)
2. `netsim.build()` turns the pin->net map into a SPICE deck: passives as-is, ICs
   mapped to behavioral subckts in `models/behavioral.lib` (OPA1678, LM13700), muxes
   set to the selected path, DAC CVs -> DC sources, rails -> V sources.
3. run via libngspice, check the response.

Targets: `sim-svf-real` (MASTER_FILTER), `sim-phaser-real` (FX_PHASER).

Limits: behavioral models validate topology/levels-ish, not real LM13700 linear range
/ noise (drop in TI subckts in models/ for that). The BBD chorus can't be SPICE'd
(sampled device) - bench only. To go full-fidelity, assign real .subckt models per
symbol in the KiCad GUI (Simulation Model dialog) and use the built-in simulator.
