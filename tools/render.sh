#!/usr/bin/env bash
# render design pictures (schematic pdf, pcb layer pdf, 3d front/back png)
# for the allowlisted boards below, skipping .history and _archive copies
#
# usage:
#   tools/render.sh               render all allowlisted designs
#   tools/render.sh APM/v5_r2     render only matching allowlisted design(s)
#   tools/render.sh --list        print the allowlist (one board/rev per line)
#   tools/render.sh --list-json   print the allowlist as a json array (ci matrix)
set -euo pipefail

cd "$(dirname "$0")/.."

# layers plotted into the pcb pdf, tweak as needed
PCB_LAYERS="F.Cu,B.Cu,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"

# 3d render resolution; higher is crisper when zooming but slower to render
# override like: RENDER_W=2560 RENDER_H=1440 tools/render.sh
RENDER_W="${RENDER_W:-3840}"
RENDER_H="${RENDER_H:-2160}"

# only the newest revision of each active board is rendered; update the entry
# when you spin a new revision so old revs stop consuming render time.
# this list is also the ci render matrix (see tools/render.sh --list-json)
RENDER_BOARDS=(
  APM/v5_r2
  ACM/v1_r3
  OSC_CTRL/v1_r1
  AUDIO_BOARD/v1_r1
)

case "${1:-}" in
  --list)
    printf '%s\n' "${RENDER_BOARDS[@]}"
    exit 0
    ;;
  --list-json)
    out=""
    for b in "${RENDER_BOARDS[@]}"; do
      out="$out,\"$b\""
    done
    echo "[${out#,}]"
    exit 0
    ;;
esac

filter="${1:-}"
count=0

while IFS= read -r pcb; do
  case "$pcb" in
    */.history/*|boards/_archive/*) continue ;;
  esac

  dir="$(dirname "$pcb")"
  base="$(basename "$pcb" .kicad_pcb)"
  sch="$dir/$base.kicad_sch"
  [ -f "$sch" ] || continue

  # skip anything not in the render allowlist
  keep=0
  for b in "${RENDER_BOARDS[@]}"; do
    [ "$dir" = "boards/$b" ] && keep=1 && break
  done
  [ "$keep" = 1 ] || continue

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
done < <(find boards -name "*.kicad_pcb" | sort)

echo "done: rendered $count design(s)"
