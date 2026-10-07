---
name: scout-new-games
description: Process new CFB 26 game recordings for one or all opponents — extract and OCR them, file each under the right opponent by the team on the scoreboard, rebuild that opponent's data and scouting report, update their game plan, then commit and push (which deploys the login-protected pages to allenvestal.com/cf26). Use when the user says they added new videos/games or asks to update the scouting. Optional argument: an opponent (id, player name, or team), e.g. "/scout-new-games jason".
---

# Scout new games

The scouting pipeline lives in `cf26/` inside the allenvestal.com repo. Run every command from the repo root. Read
`cf26/README.md` for the layout and `cf26/SCHEMA.md` for the data fields.

- **Each opponent is isolated** under `cf26/opponents/<id>/`, for example `jason-stanford`.
- **`profile.json`** in each opponent folder holds the player's name, their team(s), and their video folder (absolute path, outside the repo). `video_dir: null` means no usable recordings yet.
- **Never mix opponents.** Every report, plan and tendency is per opponent.
- **The pages go live** at `https://allenvestal.com/cf26/`, behind the same Google login (ADMIN_EMAIL only) as `/admin`. They're served from the committed `cf26/**/*.html` files, so a push to `main` (which auto-deploys) is what updates them.

## Steps

1. **Find new videos.** Run `python3 cf26/scripts/process_new.py --dry-run`. If the user named an opponent, add `--opponent <arg>`.
   - If nothing is new, say so and stop.
   - If an opponent is skipped for having no `video_dir`, mention it once.

2. **Process them.** Run the same command without `--dry-run`, using `run_in_background`. It takes about 10 minutes per hour of video (720p or 1080p).
   - Each video is filed under the opponent whose team appears on the scoreboard, even if it was found in another opponent's folder.
   - Then the script reruns `build_plays.py` and `analyze.py` for every opponent that got a new video, and `render_html.py`.
   - Videos with no matching team go to `cf26/unassigned.json`. Report those; the user may need a new profile (see "New opponent" below).

3. **Sanity-check each new game** in `cf26/opponents/<id>/games/<video>.json`:
   - The opponent should have roughly 25–60 offensive snaps per game (5-minute quarters).
   - The opponent's total TDs should match the score change on the scoreboard.
   - If the counts are far off, or most snaps have `offense` set to the wrong team, check `scout_side` in that opponent's `videos.json`.
   - To view frames, run `KEEP_FRAMES=1 cf26/scripts/extract.sh cf26/work/check "<video>"`.
   - Fix problems in `cf26/scripts/scoreboard.py` / `build_plays.py`, not by hand-editing JSON. Then rebuild with `python3 cf26/scripts/build_plays.py --opponent <id> && python3 cf26/scripts/analyze.py --opponent <id>`.

4. **Update that opponent's plan.** Compare `cf26/opponents/<id>/reports/scouting_report.md` with `git diff` of the same file. Then edit `cf26/opponents/<id>/reports/gameplan.md`:
   - Update the numbers it cites.
   - Add new formation → play links from `formation_plays.json`.
   - Flag tendencies that changed, such as a new favorite play, a coverage that now works or fails, or a new formation.
   - If the opponent has no `gameplan.md` yet, write one using `cf26/opponents/jason-stanford/reports/gameplan.md` as the template. Use only that opponent's data.
   - Be explicit about small sample sizes.
   - Keep the sections in this order: "What the data says", "Pre-snap adjustments", "Coach adjustments", "Pre-snap read → your call", "Calls by down & distance" (plus "Open questions" at the end while the sample is small).
   - Keep the **"Pre-snap read → your call"** table current, with one row per formation from the report's "Pre-snap read" section. Keep the columns in this order: Banner shows | Personnel | **Call** | Backup | He's run from it (confirmed) | How often | His results | Results vs. your calls. Also keep a row for "No banner (hurry-up)" with a default call.
     - Calls must be exact plays from the user's playbook, written `Formation: Play` (e.g. `Nickel 3-3 Over: Cover 2 Man`). Take names from `def_candidates` in that opponent's `games/*.json`; the OCR is messy, so clean the names. Never invent a play the user hasn't had on screen.
   - There is **one cumulative plan per opponent**, covering all their games. Update it; don't start a new plan per video.
   - Write it in the Markdown subset `render_html.py` handles: `#` headings, paragraphs, `-` bullets, pipe tables, `**bold**`, `` `code` ``, `[links](x.md)`.
   - Then run `python3 cf26/scripts/render_html.py` to regenerate `gameplan.html`, `scouting_report.html` and `cf26/index.html`.

5. **Commit and push (this deploys).** This repo commits straight to `main` (no branches or PRs), and its quality bar still applies:
   - Run `npm run lint && npm test` first (100% coverage gate). A content-only change won't affect them, but run them anyway.
   - Then `git add -A && git commit -m "cf26 <opponent>: add <video ids>"` and `git push`. The push auto-deploys to Railway.
   - Videos, `cf26/work/` and `cf26/bin/` are git-ignored.

6. **Report to the user, per opponent.** Cover:
   - The live link `https://allenvestal.com/cf26/opponents/<id>/reports/gameplan.html` (behind the login; live a couple of minutes after the push) and the local file
   - Games added, with snap counts and confirmed plays
   - What changed in their tendencies
   - The top 3 game-plan adjustments
   - Anything that looked wrong

## New opponent

When the user names a new person or team, create `cf26/opponents/<player>-<team>/profile.json` with `player`, `teams` (as shown on the scoreboard, e.g. `"Iowa"`), `video_dir` (absolute path, e.g. `"/Users/allenv/Documents/media/cf26/mike-iowa"`, or `null`), and `my_playbook`. Add an empty `videos.json` (`[]`). If `cf26/unassigned.json` lists games with that team, move their OCR from `cf26/unassigned/` into `cf26/opponents/<id>/ocr/<video_id>/`, add the entries to `videos.json`, and remove them from `unassigned.json`.

The site route only serves opponent ids made of lowercase letters, digits and hyphens.

## Notes

- Only use console screen captures (720p or 1080p game capture). The user does not want GoPro or camera footage of the TV used (e.g. the `GH01*.MP4` files in `nick-michigan/`).
- The user's defensive pick (X/A/Y) is never visible on screen. It's only confirmed when the next play-call screen shows the PREVIOUS PLAY panel. Don't present guesses as confirmed calls.
- The opponent is the offense being scouted. The user plays defense with the playbook in the opponent's profile.
- The repo is public on GitHub. The user is fine with the scouting files being visible there; only the website copy is behind the login.
