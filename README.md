# cf26-scouting

Scouting an opponent's play calls in **EA SPORTS College Football 26** from recorded games.

The pipeline reads the game recordings and pulls out:

- **Every snap**: quarter, clock, down & distance, field position, who has the ball, and the yards gained, all read off the scoreboard.
- **The opponent's formation and personnel**, from the "DEFENSE, PICK A PLAY!" banner on your play-call screen.
- **The exact offense vs. defense calls** whenever the game shows the **PREVIOUS PLAY** panel (upper right of the play-call screen).
- **Your coverage family** when the panel isn't shown. The three plays on your screen usually come from one concept tab (used only when all three match).
- **A guess at the opponent's play** when the panel isn't shown, based on what he has run from that formation before.

Current scout: **Stanford** (opponent), seen from the user's North Texas / Oklahoma games running a **3-3-5 Tite** defense.

## Layout

```
data/
  videos.json            one entry per recording (id, file, teams, which side of the scoreboard the scouted team is on)
  games/<id>.json        every snap from that recording, both teams (output of build_plays.py)
  plays.csv              scouted team's offensive snaps, all games, flat (output of analyze.py)
  formation_plays.json   formation -> plays confirmed from it (the guess model)
reports/
  scouting_report.md     generated tendencies tables (by down & distance, coverage, play, formation, big plays)
  gameplan.md            hand-written defensive plan built from the report
scripts/
  extract.sh             video -> 1 fps frames -> OCR (.tsv)
  ocr.swift              macOS Vision OCR; prints "midX,midY@text" tokens per frame
  scoreboard.py          parses the scoreboard strip
  build_plays.py         OCR -> snaps (data/games/*.json)
  analyze.py             snaps -> plays.csv, formation_plays.json, scouting_report.md
SCHEMA.md                field-by-field description of the data files
```

`work/` (frames and raw OCR, several GB) and the videos themselves are git-ignored.

## Adding a new game

```bash
# 1. add an entry to data/videos.json (scout_side: 0 if the scouted team is on the LEFT of the scoreboard, 1 if RIGHT)
# 2. extract + OCR (about 10 minutes per hour of 1080p video)
scripts/extract.sh 2026-10-10-ou "/path/to/EA SPORTS College Football 26 2026-10-10 ....mp4"
# 3. rebuild everything
python3 scripts/build_plays.py && python3 scripts/analyze.py
```

Requirements: macOS (Vision framework for OCR, `swiftc`), `ffmpeg`, Python 3.9+ (standard library only).

## How it reads the screen

- **Scoreboard.** The ball-spot box sits on the side of the team that has the ball. ▼ means the offense's own half and ▲ means the opponent's half. Yards gained = the change in yards-to-goal between one snap and the next.
- **PREVIOUS PLAY panel.** The left card is the defensive call and the right card is the offensive call. The panel shown during snap *k* describes snap *k − 1*.
- **Picking a defense.** You choose with X / A / Y, so nothing on screen marks which of the three plays was picked. The exact call is only known when the next screen's panel shows it.

## Known limits

- The panel only appears on some play-call screens, so about 20% of snaps have a confirmed play. Everything else is a guess, marked `play_source` empty and listed in `off_play_guess`.
- Text recognition misreads are filtered, but occasionally a yardage is off by a yard or a penalty shows up as `penalty?`.
- `turnover?` means the ball changed hands before 4th down without a score. It's usually an interception or fumble, but not verified.
