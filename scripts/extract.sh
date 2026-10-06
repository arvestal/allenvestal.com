#!/usr/bin/env bash
# Extract 1 fps frames from a CFB 26 recording and OCR them.
#   usage: scripts/extract.sh <video_id> "<path to video.mp4>"
# Produces work/<video_id>/{sb,full,panel}.tsv for build_plays.py. Needs ffmpeg (brew install ffmpeg) and macOS (Vision OCR).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ID="$1"; VIDEO="$2"
W="${WORK:-$ROOT/work}/$ID"
mkdir -p "$W"/frames/{sb,full,panel} "$ROOT/bin"

[ -x "$ROOT/bin/ocr" ] || swiftc -O "$ROOT/scripts/ocr.swift" -o "$ROOT/bin/ocr"

# scoreboard strip (full res), whole frame (960px), PREVIOUS PLAY panel (upper right) — 1080p source assumed
ffmpeg -loglevel error -hwaccel videotoolbox -i "$VIDEO" -filter_complex \
  "[0:v]fps=1,split=3[a][b][c];[a]crop=1180:110:370:915[sb];[b]scale=960:-1[full];[c]crop=820:400:1020:40[panel]" \
  -map "[sb]" -q:v 2 "$W/frames/sb/%05d.jpg" \
  -map "[full]" -q:v 4 "$W/frames/full/%05d.jpg" \
  -map "[panel]" -q:v 3 "$W/frames/panel/%05d.jpg"

"$ROOT/bin/ocr" "$W/frames/sb" > "$W/sb.tsv" &
"$ROOT/bin/ocr" "$W/frames/full" > "$W/full.tsv" &
"$ROOT/bin/ocr" "$W/frames/panel" > "$W/panel.tsv" &
wait
echo "done: $W"
