#!/usr/bin/env bash
# ci only: renders one board inside the kicad/kicad:10.0-full container.
# the workflow runs this through docker only when the board's render cache
# misses, so unchanged boards never pull the kicad image
#
# usage (from the repo root, inside the container): tools/ci_render.sh BOARD/vX_rY
set -euo pipefail
board="$1"
git config --global --add safe.directory '*'

# point all three model vars at the image's real stock dir, else stock ics and
# passives render as flat outlines
sample=$(find /usr -type f -name 'R_0402_1005Metric.step' \
  -path '*Resistor_SMD.3dshapes*' 2>/dev/null | head -1)
if [ -z "$sample" ]; then
  echo "::error::stock 3d models not found in image"
  exit 1
fi
stock=$(dirname "$(dirname "$sample")")
echo "stock 3d model dir: $stock"
export KICAD10_3DMODEL_DIR="$stock" KICAD9_3DMODEL_DIR="$stock" KISYS3DMOD="$stock"

# boards reference custom models by absolute path; clone the public lib there
git clone --depth 1 https://github.com/akielaries/my_pcb_lib /home/akiel/trunk/pub/my_footprints

# the 3d render needs a display
apt-get update
apt-get install -y --no-install-recommends xvfb
xvfb-run -a bash tools/render.sh "$board"
