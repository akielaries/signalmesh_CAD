#!/usr/bin/env bash
# full board: placement/planes/fanout -> gtp route+tune -> ddr route+tune -> silk -> drc
set -uo pipefail
S=$(cd "$(dirname "$0")" && pwd)
P=/home/akiel/trunk/pub/signalmesh_CAD/boards/MAIN_COMPUTE_BOARD/v1_r1/MAIN_COMPUTE_BOARD.kicad_pcb
F="assert\|pcb_track.cpp\|swig\|Debug"
cd "$S"
bash pipeline.sh 2>&1 | grep -v "$F\|^front" | tail -6
cp $P board_fanout.kicad_pcb
INNER=In2.Cu,B.Cu PASSES=10 ${PY:-python3} gtp.py $P board_fanout.kicad_pcb 2>&1 | grep -v "$F" | grep "pass"
${PY:-python3} tune.py $P 2>&1 | grep -v "$F" | grep -v "'ok')"
cp $P gtp_tuned.kicad_pcb
ITERS=${DDR_ITERS:-60} ${PY:-python3} ddr2.py $P gtp_tuned.kicad_pcb 2>&1 | grep -v "$F" | grep "iter\|committed\|failed" | tail -4
cp $P ddr_routed.kicad_pcb
${PY:-python3} ddr_tune.py $P 2>&1 | grep -v "$F"
${PY:-python3} resilk.py $P 2>&1 | grep -v "$F"
kicad-cli pcb drc --refill-zones --schematic-parity --severity-all -o $S/drc_chain.rpt $P >/dev/null
grep -E "^\[" $S/drc_chain.rpt | grep -v "unconnected\|via_dangling" | sed 's/(.*//' | sort | uniq -c
grep Found $S/drc_chain.rpt
