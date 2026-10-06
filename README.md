# cf26-scouting

Scouting an opponent's play calls in **EA SPORTS College Football 26** from recorded games.

The pipeline reads the game recordings and pulls out:

- **Every snap**: quarter, clock, down & distance, field position, who has the ball, and the yards gained, all read off the scoreboard.
- **The opponent's formation and personnel**, from the "DEFENSE, PICK A PLAY!" banner on your play-call screen.
- **The exact offense vs. defense calls** whenever the game shows the **PREVIOUS PLAY** panel (upper right of the play-call screen).
- **Your coverage family** when the panel isn't shown. The three plays on your screen usually come from one concept tab (used only when all three match).
- **A guess at the opponent's play** when the panel isn't shown, based on what he has run from that formation before.

**Analysis is isolated per opponent** (a person plus the team they use). Each opponent has their own folder with their
own games, report and game plan:

| Opponent | Team | Status |
|---|---|---|
| `jason-stanford` | Stanford | 4 games, 181 snaps — see `opponents/jason-stanford/reports/` |
| `mike-iowa` | Iowa | profile only, no usable recordings yet (GoPro footage isn't used) |

## Layout

```
opponents/<player>-<team>/
  profile.json           player name, team(s) as shown on the scoreboard, video folder, your playbook
  videos.json            one entry per recording (id, file, teams, which side of the scoreboard they're on)
  ocr/<video>/*.tsv.gz   raw per-second OCR of each recording; everything else is rebuilt from this
  games/<video>.json     every snap from that recording, both teams (output of build_plays.py)
  plays.csv              their offensive snaps, all games, flat (output of analyze.py)
  formation_plays.json   formation -> plays confirmed from it (the guess model)
  reports/
    scouting_report.md   generated tendencies tables (by down & distance, coverage, play, formation, big plays)
    gameplan.md          hand-written defensive plan built from the report
unassigned.json          processed videos whose scoreboard matched no opponent (OCR kept in unassigned/)
scripts/
  opponents.py           opponent registry helpers
  process_new.py         finds new recordings in every opponent's folder, files them by scoreboard team, rebuilds
  extract.sh             video -> 1 fps frames -> OCR
  ocr.swift              macOS Vision OCR; prints "midX,midY@text" tokens per frame
  scoreboard.py          parses the scoreboard strip
  build_plays.py         OCR -> snaps                                   [--opponent X]
  analyze.py             snaps -> plays.csv, formation_plays.json, report [--opponent X]
SCHEMA.md                field-by-field description of the data files
```

Videos and `work/` (temporary frames) are git-ignored. **The videos aren't needed after processing.** The raw OCR in
`opponents/*/ocr/` is enough to rebuild every output, including after parser improvements. What you lose by deleting a video
is the ability to look at its frames again or extract something new from the picture (for example, routes).

## Adding new games

Drop console screen captures in the opponent's video folder (`video_dir` in their `profile.json`; Jason's is
`../jason-standford`). Each video is filed by the team on the scoreboard, so a game in the wrong folder still lands in
the right place. Then either:

- **In Claude Code**, start it in this repo (`cd cf26-scouting && claude`) and run **`/scout-new-games`**, or
  `/scout-new-games jason` for one opponent. It processes the videos, checks the results, updates that opponent's
  `gameplan.md`, and commits and pushes.
- **Manually:** run `python3 scripts/process_new.py [--opponent jason] [--dry-run]`. That takes about 10 minutes per hour of 1080p video.

**New opponent:** create `opponents/<player>-<team>/profile.json` (copy Jason's and edit it) plus `videos.json` containing `[]`,
or just ask Claude to add them.

To rebuild after changing a parser: `python3 scripts/build_plays.py && python3 scripts/analyze.py` (all opponents).

Requirements: macOS (Vision framework for OCR, `swiftc`), `ffmpeg`, Python 3.9+ (standard library only).

## How it reads the screen

- **Scoreboard.** The ball-spot box sits on the side of the team that has the ball. ▼ means the offense's own half and ▲ means the opponent's half. Yards gained = the change in yards-to-goal between one snap and the next.
- **PREVIOUS PLAY panel.** The left card is the defensive call and the right card is the offensive call. The panel shown during snap *k* describes snap *k − 1*.
- **Picking a defense.** You choose with X / A / Y, so nothing on screen marks which of the three plays was picked. The exact call is only known when the next screen's panel shows it.

## Known limits

- The panel only appears on some play-call screens, so about 20% of snaps have a confirmed play. Everything else is a guess, marked `play_source` empty and listed in `off_play_guess`.
- Text recognition misreads are filtered, but occasionally a yardage is off by a yard or a penalty shows up as `penalty?`.
- `turnover?` means the ball changed hands before 4th down without a score. It's usually an interception or fumble, but not verified.
