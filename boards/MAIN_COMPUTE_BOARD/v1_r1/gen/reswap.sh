#!/usr/bin/env bash
# recompute the ddr pin swap after a floorplan change: build with the original pin table,
# place, derive the swap from the geometry, rebuild with it
set -euo pipefail
S=$(cd "$(dirname "$0")" && pwd)
P=$(dirname "$S")
cd "$S"
[ -f ddr_swap.json ] && mv ddr_swap.json ddr_swap.prev.json
python3 build.py out | grep -E "expected|SPLIT|MERGED"
cp out/*.kicad_sch out/MAIN_COMPUTE_BOARD.kicad_sym out/sym-lib-table "$P"/
bash pipeline.sh | tail -3
${PY:-python3} swap.py "$P"/MAIN_COMPUTE_BOARD.kicad_pcb 2>&1 | grep -v "Debug\|swig"
python3 build.py out | grep -E "expected|SPLIT|MERGED"
cp out/*.kicad_sch out/MAIN_COMPUTE_BOARD.kicad_sym out/sym-lib-table "$P"/
