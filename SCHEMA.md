# Data schema

## data/videos.json

| field | example | meaning |
|---|---|---|
| id | `2026-10-04-ou` | short id, used for `work/<id>/` and `data/games/<id>.json` |
| file | `EA SPORTS™ College Football 26 2026-10-04 18-44-14.mp4` | recording file name |
| date | `2026-10-04` | game date |
| user_team | `Oklahoma` | the team you controlled (on defense against the scout) |
| scout_team | `Stanford` | the team being scouted |
| scout_side | `1` | scouted team's side of the scoreboard: 0 = left, 1 = right |
| user_playbook | `3-3-5 Tite` | your defensive playbook |

## data/games/&lt;id&gt;.json

`{"video": <videos.json entry>, "snaps": [ ... ]}`. Each snap is one pre-snap scoreboard state, for both teams:

| field | meaning |
|---|---|
| t, timestamp | seconds / `m:ss` into the recording where the snap's state first appears |
| qtr, clock | quarter (`1ST`…`4TH`, `OT`) and game clock in seconds |
| down, dist | down (1–4) and distance (`"G"` = goal to go) |
| ytg | yards to the goal line (75 = own 25) |
| score | `[left team, right team]` |
| offense | team with the ball |
| screen | play-call screen you were on: `DEF`, `OFF`, or null (hurry-up / skipped) |
| off_formation, off_personnel | raw formation banner text, e.g. `Shotgun - Bunch Spread`, `1RB 1TE 3WR` |
| def_candidates | the three plays on your screen at the last moment before the snap (`FORMATION: PLAY`) |
| off_play, def_play | confirmed calls from the PREVIOUS PLAY panel (only when shown) |
| play_source | `panel` when `off_play`/`def_play` are confirmed |
| panel_timestamp | where in the recording the panel showing this play appears |
| yards | yards gained (null when the ball changed hands or the result is unknown) |
| result | `gain`, `no_gain`, `loss`, `first_down`, `touchdown`, `field_goal`, `penalty?`, `turnover?`, `fourth_down_change`, `end_of_half`, `opponent_score` |
| special_teams | true for FG / punt snaps |

## data/plays.csv

The scouted team's offensive snaps from all games, excluding special teams. It has the columns above, plus:

| column | meaning |
|---|---|
| video_file, opponent | which recording / which of your teams |
| bucket | down & distance group, e.g. `2nd & long (7+)`, `Goal to go / inside 10` |
| formation | normalized formation name (fuzzy-matched from the banner text) |
| off_play_guess | up to 3 likely plays when not confirmed, `;`-separated |
| guess_basis | what the guess is based on (formation history or situation tendency) |
| def_family | your coverage family: Cover 1 / Cover 2 Man / Cover 2 Zone / Cover 3 / Cover 4 / Cover 6/9 / Tampa 2 / Double/Bracket / Blitz/Pressure |
| def_family_source | `panel` (confirmed) or `on-screen options` (all three plays on screen were the same family) |
| success | True if the play gained 40% of the distance on 1st down, 60% on 2nd, or all of it on 3rd/4th |

## data/formation_plays.json

`{ "<formation>": { "<PLAY>": count, ... } }`. These are the plays confirmed by the panel from each formation. They drive the play guesses.
