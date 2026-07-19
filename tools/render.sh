#!/usr/bin/env bash
# render design pictures (schematic pdf, pcb layer pdf, 3d front/back png)
# for every kicad board under schematic/, skipping .history and archive copies
#
# usage:
#   tools/render.sh              render all designs
#   tools/render.sh APM_v5_r1    render only matching design(s)
set -euo pipefail

cd "$(dirname "$0")/.."

# layers plotted into the pcb pdf, tweak as needed
PCB_LAYERS="F.Cu,B.Cu,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"

# 3d render resolution; higher is crisper when zooming but slower to render
# override like: RENDER_W=2560 RENDER_H=1440 tools/render.sh
RENDER_W="${RENDER_W:-3840}"
RENDER_H="${RENDER_H:-2160}"

filter="${1:-}"
count=0

while IFS= read -r pcb; do
  case "$pcb" in
    */.history/*|*/archive/*) continue ;;
  esac

  dir="$(dirname "$pcb")"
  base="$(basename "$pcb" .kicad_pcb)"
  sch="$dir/$base.kicad_sch"
  [ -f "$sch" ] || continue

  if [ -n "$filter" ] && [[ "$dir" != *"$filter"* ]]; then
    continue
  fi

  out="$dir/renders"
  mkdir -p "$out"
  echo "=== $dir/$base ==="

  echo "  schematic pdf"
  kicad-cli sch export pdf "$sch" -o "$out/${base}_schematic.pdf" >/dev/null

  echo "  pcb layer pdf"
  kicad-cli pcb export pdf "$pcb" --layers "$PCB_LAYERS" \
    -o "$out/${base}_pcb.pdf" >/dev/null

  echo "  3d top png"
  kicad-cli pcb render "$pcb" --side top --quality high \
    --width "$RENDER_W" --height "$RENDER_H" --floor \
    -o "$out/${base}_3d_top.png" >/dev/null

  echo "  3d bottom png"
  kicad-cli pcb render "$pcb" --side bottom --quality high \
    --width "$RENDER_W" --height "$RENDER_H" --floor \
    -o "$out/${base}_3d_bottom.png" >/dev/null

  count=$((count + 1))
done < <(find schematic -name "*.kicad_pcb" | sort)

echo "done: rendered $count design(s)"
