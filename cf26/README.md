# cf26 — CFB 26 opponent scouting

Lives in `cf26/` inside the allenvestal.com repo (it was a separate `cf26-scouting` repo until 2026-10-07; its history
was merged in). Scouting the people I play in **EA SPORTS College Football 26**, from recordings of our games.

For each opponent (a person plus the team they use), the recordings are turned into a play-by-play of their offense:
every snap's down, distance, field position and yards gained, their formation, their play call when the game shows it,
and my coverage. That feeds a scouting report and a defensive game plan for the next game against them.

## Deliverables — what to read before a game

**Live (behind my Google login, same as `/admin`): https://allenvestal.com/cf26/**. It links every opponent's pages:

| Opponent | Game plan | Scouting report |
|---|---|---|
| Jason (Stanford) | https://allenvestal.com/cf26/opponents/jason-stanford/reports/gameplan.html | https://allenvestal.com/cf26/opponents/jason-stanford/reports/scouting_report.html |
| Mike (Iowa) | https://allenvestal.com/cf26/opponents/mike-iowa/reports/gameplan.html | https://allenvestal.com/cf26/opponents/mike-iowa/reports/scouting_report.html |

Locally, open `cf26/index.html` in a browser. Each opponent's pages are in `cf26/opponents/<player>-<team>/reports/`:

| Page | What it is | Made by |
|---|---|---|
| **`gameplan.html`** | **The deliverable.** A pre-snap table (the formation on the "DEFENSE, PICK A PLAY!" banner → what they run from it → the exact play to call from my playbook), what to call by down & distance, formation tells (formation → their likely play → my answer), coverages that work and fail, pre-snap and coach adjustments. | Claude, during `/scout-new-games` |
| `scouting_report.html` | The evidence behind the plan: tables by down & distance, my coverage vs. their offense, their plays, their formations, and every 15+ yard play allowed with timestamps. | `analyze.py` (automatic) |

Tables are sortable: click a column header. Red shading means the number is good for the offense. The `.md` files next to
the pages are their source; edit those, not the HTML. The site (`src/routes/cf26.js`) serves only the two `.html` pages per
opponent and `index.html`, never the data files. The repo is public, so everything here is also readable on GitHub;
only the website copy is behind the login.

To check a specific play, `plays.csv` in the opponent folder has every snap with its video file and timestamp. It opens in Excel or Numbers.

## Opponents

| Opponent | Team | Data |
|---|---|---|
| [`jason-stanford`](opponents/jason-stanford/reports/) | Stanford | 4 games, 181 offensive snaps |
| [`mike-iowa`](opponents/mike-iowa/reports/) | Iowa | 1 game, 60 offensive snaps |

Each opponent is fully isolated. Their games, tendencies, report and plan are built only from games against them.

## Adding games

1. **Save the console recording** (screen capture, 720p or 1080p) in the opponent's video folder, set in their
   `profile.json`. Jason's games go in `/Users/allenv/Documents/media/cf26/jason-standford` and Mike's in
   `/Users/allenv/Documents/media/cf26/mike-iowa`. Videos stay outside the repo.
   - Don't use GoPro or phone footage of the TV.
   - A video in the wrong folder still gets filed correctly, because the opponent is identified by the team on the scoreboard.
2. **Process it.** Start Claude Code in this repo and run the command:
   ```
   cd /Users/allenv/Documents/dev/allenvestal.com
   claude
   /scout-new-games            # every opponent
   /scout-new-games mike       # one opponent (id, player, or team)
   ```
   It extracts and reads the video (about 10 minutes per hour of footage), rebuilds that opponent's data and
   `scouting_report.md`, sanity-checks the numbers, updates their `gameplan.md`, runs the site's lint and tests, and commits
   and pushes to `main`. The push auto-deploys, so the live pages update a couple of minutes later.
3. **Open the game plan** at https://allenvestal.com/cf26/ (or the local `gameplan.html`). There's one plan per opponent, covering all their games, and each new game updates it.

Without Claude, `python3 cf26/scripts/process_new.py [--opponent mike] [--dry-run]` does everything except update the game plan.

**New opponent:** ask Claude to add them, or create `opponents/<player>-<team>/profile.json` (copy an existing one)
and a `videos.json` containing `[]`.

**Deleting videos:** once a game is processed, its recording isn't needed. The raw text read from every frame is kept in
the repo (`ocr/`), and every output can be rebuilt from it. Deleting means you can't re-watch the game or extract
something new from the picture later, such as routes.

## What gets built, per opponent

```
opponents/<player>-<team>/
  profile.json           player, team(s) as shown on the scoreboard, video folder, my playbook   (you write)
  videos.json            one entry per processed recording                                        (process_new.py)
  ocr/<video>/*.tsv.gz   raw per-second OCR of the scoreboard, full frame, and PREVIOUS PLAY panel (extract.sh)
  games/<video>.json     every snap of that game, both teams                                      (build_plays.py)
  plays.csv              their offensive snaps from all games, one row each                       (analyze.py)
  formation_plays.json   formation -> plays confirmed from it (used to guess unconfirmed plays)   (analyze.py)
  reports/
    scouting_report.md   generated tables                                                         (analyze.py)
    gameplan.md          the plan, cumulative over all games                                      (Claude)
    *.html               the two pages above, styled, sortable tables                             (render_html.py)
```

Shared files:

```
scripts/
  process_new.py   finds new recordings in every opponent's folder, files them by scoreboard team, runs the rest
  extract.sh       video -> 1 frame per second -> OCR
  ocr.swift        macOS Vision OCR (compiled to bin/ on first run)
  scoreboard.py    reads the scoreboard strip
  build_plays.py   OCR -> snaps                                       [--opponent X]
  analyze.py       snaps -> plays.csv, formation_plays.json, report   [--opponent X]
  render_html.py   reports/*.md -> .html for every opponent, plus index.html
  opponents.py     opponent registry helpers
unassigned.json    processed recordings whose scoreboard matched no opponent (OCR kept in unassigned/)
../.claude/skills/scout-new-games/   the /scout-new-games command (at the allenvestal.com repo root)
SCHEMA.md          every field in every data file
```

To rebuild everything after changing a parser: `python3 cf26/scripts/build_plays.py && python3 cf26/scripts/analyze.py && python3 cf26/scripts/render_html.py`.

Requirements: macOS (Vision framework for OCR, `swiftc`), `ffmpeg` (`brew install ffmpeg`), Python 3.9+ (standard library only).

## How it reads the screen

- **Scoreboard.** The ball-spot box sits on the side of the team with the ball. ▼ means the offense's own half and ▲ means the opponent's half. Yards gained = the change in yards-to-goal between snaps.
- **Their formation** comes from the "DEFENSE, PICK A PLAY!" banner on my play-call screen.
- **PREVIOUS PLAY panel** (upper right of the play-call screen): the left card is the defense and the right card is the offense. The panel during snap *k* describes snap *k − 1*.
- **My call.** I pick with X / A / Y, so nothing on screen marks which of the three plays I chose. It's confirmed only when the next screen's panel shows it. Otherwise only the coverage family is recorded, and only when all three on-screen options share one.

## Known limits

- The panel shows on only some play-call screens, so roughly 20% of plays are confirmed. The rest are guesses, flagged in `off_play_guess` with the reason in `guess_basis`.
- Yardage can be off by a yard because the scoreboard rounds the ball spot. `penalty?` and `turnover?` results are inferred, not verified.
- Sample sizes per situation are small until there are several games against an opponent.
