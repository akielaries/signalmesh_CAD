# MAIN_COMPUTE_BOARD generators

Scripts that build this board: the schematic sheets, placement, planes, BGA fanout, the scripted
routing (GTP pairs, DDR3) and the generated docs. Rerun the whole flow after a schematic or
placement change rather than editing the outputs by hand.

Needs KiCad 10 (`pcbnew` Python module, `kicad-cli`) and numpy, scipy, scikit-image, shapely and
Pillow. Point `PY` at an interpreter that has them, e.g. a venv made with
`--system-site-packages` so it also sees `pcbnew`.

| step | command |
|---|---|
| schematic | `python3 build.py out && cp out/*.kicad_sch out/MAIN_COMPUTE_BOARD.kicad_sym out/sym-lib-table ..` |
| placement, planes, fanout, DRC | `bash pipeline.sh` |
| everything incl. routing and silk | `PY=/path/to/python ./chain.sh` |

- `build.py`, `d*.py`, `sch.py`, `mklib.py`: label-based schematic generator (deterministic uuids)
- `pcbbuild.py`, `planes.py`, `fanout.py`: placement, copper pours, BGA dogbones
- `silkplace.py`, `labels.py`, `resilk.py`: silkscreen refs and labels
- `rlib.py`, `proute.py`: grid router core and coupled-pair router
- `gtp.py`, `tune.py`: transceiver lanes and their skew bumps
- `swap.py`, `ddr_swap.json`: DDR3 pin swap (applied by `dfpga.py`; relative to its pin table)
- `ddr2.py`, `ddr_tune.py`: DDR3 negotiated-congestion router and length matching
- `hwdoc.py`: regenerates `docs/hardware.md` from the board
