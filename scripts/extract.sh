#!/usr/bin/env bash
# Extract 1 fps frames from a CFB 26 recording and OCR them.
#   usage: scripts/extract.sh <output dir> "<path to video.mp4>"
# Writes <output dir>/{sb,full,panel}.tsv.gz for build_plays.py (normally opponents/<opp>/ocr/<video_id>).
# Frames go to work/<name of output dir>/ and are deleted afterwards unless KEEP_FRAMES=1.
# Needs ffmpeg (brew install ffmpeg) and macOS (Vision OCR via swiftc).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$1"; VIDEO="$2"
W="$ROOT/work/$(basename "$OUT")"
mkdir -p "$W"/{sb,full,panel} "$OUT" "$ROOT/bin"

[ -x "$ROOT/bin/ocr" ] || swiftc -O "$ROOT/scripts/ocr.swift" -o "$ROOT/bin/ocr"

# scoreboard strip (full res), whole frame (960px), PREVIOUS PLAY panel (upper right) — 1080p source assumed
ffmpeg -loglevel error -hwaccel videotoolbox -i "$VIDEO" -filter_complex \
  "[0:v]fps=1,split=3[a][b][c];[a]crop=1180:110:370:915[sb];[b]scale=960:-1[full];[c]crop=820:400:1020:40[panel]" \
  -map "[sb]" -q:v 2 "$W/sb/%05d.jpg" \
  -map "[full]" -q:v 4 "$W/full/%05d.jpg" \
  -map "[panel]" -q:v 3 "$W/panel/%05d.jpg"

for part in sb full panel; do
  ( "$ROOT/bin/ocr" "$W/$part" | gzip > "$OUT/$part.tsv.gz" ) &
done
wait

[ "${KEEP_FRAMES:-0}" = "1" ] || rm -rf "$W"
echo "done: $OUT"
