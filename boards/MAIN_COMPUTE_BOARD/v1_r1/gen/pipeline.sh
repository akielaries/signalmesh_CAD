#!/usr/bin/env bash
# full board regeneration: placement -> planes -> fanout -> drc
set -euo pipefail
S=$(cd "$(dirname "$0")" && pwd)
P=/home/akiel/trunk/pub/signalmesh_CAD/boards/MAIN_COMPUTE_BOARD/v1_r1
cd "$S"
kicad-cli sch export netlist -o mcb.net $P/MAIN_COMPUTE_BOARD.kicad_sch >/dev/null
python3 pcbbuild.py $P mcb.net $P/MAIN_COMPUTE_BOARD.kicad_pcb 2>&1 | grep -E "ref labels|could not|no room" || true
python3 planes.py $P/MAIN_COMPUTE_BOARD.kicad_pcb >/dev/null 2>&1
python3 fanout.py $P/MAIN_COMPUTE_BOARD.kicad_pcb 2>&1 | grep -v swig/python || true
kicad-cli pcb drc --refill-zones --schematic-parity --severity-all -o $S/drc_last.rpt $P/MAIN_COMPUTE_BOARD.kicad_pcb >/dev/null
grep -E "^\[" $S/drc_last.rpt | sed 's/(.*//' | sort | uniq -c
grep Found $S/drc_last.rpt
