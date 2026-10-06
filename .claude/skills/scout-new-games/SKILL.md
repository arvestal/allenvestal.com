---
name: scout-new-games
description: Process new CFB 26 game recordings added to the video folder — extract and OCR them, rebuild the snap data and scouting report, update the defensive game plan, then commit and push. Use when the user says they added new videos/games or asks to update the scouting.
---

# Scout new games

Repo layout and data fields are in `README.md` and `SCHEMA.md`. Settings (scouted team, video folder) are in `data/config.json`.

## Steps

1. **Find new videos.** Run `python3 scripts/process_new.py --dry-run`. If it reports none, tell the user and stop. Check `data/config.json` `video_dir` if they expected some.

2. **Process them.** Run `python3 scripts/process_new.py` with `run_in_background` (about 10 minutes per hour of 1080p video, per video). It extracts frames, runs OCR into `data/ocr/<id>/`, detects the teams from the scoreboard, appends to `data/videos.json`, and reruns `build_plays.py` and `analyze.py`.
   - If it says the scouted team wasn't found on the scoreboard, report the file. It's a game against someone else, and its OCR is left unregistered under `data/ocr/<date-time>/`.

3. **Sanity-check each new game** in `data/games/<id>.json`:
   - The scouted team should have roughly 25–60 snaps per game (5-minute quarters).
   - The scouted team's total TDs should match the score change on the scoreboard.
   - If the snap count is far off, or most snaps have `offense` of the wrong team, check `scout_side` in `data/videos.json`. To view frames, rerun with `KEEP_FRAMES=1 scripts/extract.sh <id> <video>` and look at the scoreboard. Fix the issue in `scripts/scoreboard.py` / `build_plays.py` rather than editing the JSON by hand.

4. **Update the plan.** Read the regenerated `reports/scouting_report.md` and compare it with `git diff reports/scouting_report.md`. Then edit `reports/gameplan.md`:
   - Update the numbers it cites.
   - Add new formation → play links from `data/formation_plays.json`.
   - Flag any tendency that changed, such as a new favorite play, a coverage that now works or fails, or a new formation.
   - Keep the existing structure: "What the data says", the formation table, calls by down & distance, adjustments.
   - Be explicit about small sample sizes.

5. **Report to the user.** Say which games were added, with snap counts and confirmed plays. List what changed in his tendencies, the top 3 adjustments to the game plan, and anything that looked wrong.

6. **Commit and push.** Use `git add -A && git commit -m "Add <ids>: ..."`, then `git push`. Don't commit `work/` or videos; `.gitignore` already covers them.

## Notes

- The user's defensive pick (X/A/Y) is never visible on screen. It's only confirmed when the next play-call screen shows the PREVIOUS PLAY panel. Don't present guesses as confirmed calls.
- The scouted team is the offense. The user plays defense with a 3-3-5 Tite playbook.
- If the user wants to scout a different team, change `scout_team` in `data/config.json`.
