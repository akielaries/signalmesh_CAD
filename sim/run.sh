#!/usr/bin/env bash
# one command to run the whole signal-integrity pass and drop the visuals.
# usage: ./run.sh
set -e
cd "$(dirname "$0")"

APM=../schematic/APM_v5_r1/APM.kicad_pcb
OUT=out
mkdir -p "$OUT"

echo "############ controlled-impedance reference ############"
python3 impedance.py --z 50

echo
echo "############ high-speed audit: APM (STM32H7 driver) ############"
python3 hs_audit.py "$APM" --plot "$OUT/apm_hs_audit.png" || true

# optional field solve: ./run.sh field   (needs openEMS, ~1 min)
if [ "$1" = "field" ]; then
  echo
  echo "############ openEMS field solve: 50 ohm microstrip ############"
  python3 openems_microstrip.py --len 30 --width 0.15 --dump --plot "$OUT/openems_msl.png"
  echo "field animation: paraview $OUT/openems/Et_..vtr"
fi

echo
echo "visuals in $OUT/"
ls -1 "$OUT"
