#!/usr/bin/env bash
# run ddr route + tune variants in parallel (seed x spacing), score each: 3 x open legs + nets out of window
S=$(cd "$(dirname "$0")" && pwd)
cd "$S"; mkdir -p var
PY=${PY:-python3}
F="assert\|pcb_track.cpp\|swig\|Debug"
run() {
    tag=$1; seed=$2; sp=$3; spc=$4
    b=var/$tag.kicad_pcb
    export SEED=$seed SPREAD=$sp SPREAD_CMD=$spc TFILE=var/$tag.targets.json ROUTES=var/$tag.routes.json ITERS=60
    { PHASE=measure $PY ddr2.py $b gtp_tuned.kicad_pcb 2>&1 | grep -v "$F" | grep "targets"
      PHASE=route $PY ddr2.py $b gtp_tuned.kicad_pcb 2>&1 | grep -v "$F" | grep "committed"
      $PY ddr_tune.py $b 2>&1 | grep -v "$F"; } > var/$tag.log 2>&1
    open=$(grep -o "left open: \[.*\]" var/$tag.log | grep -o "('DDR" | wc -l)
    out=$(grep -c " OUT$" var/$tag.log)
    echo "$tag seed=$seed spread=$sp/$spc open=$open out=$out score=$((3 * open + out))"
}
i=0
for seed in 1 2 3 4; do
  for sp in "0.4 0.4" "0.4 0.3"; do
    set -- $sp
    run s${seed}_${1}_${2} $seed $1 $2 &
    i=$((i + 1))
  done
done
wait
