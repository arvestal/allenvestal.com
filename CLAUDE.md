# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

# allenvestal.com — Project Context

Allen Vestal's personal site, live at [allenvestal.com](https://allenvestal.com). Node.js +
Express, Handlebars views, no database — softball stats plus a photo gallery (`/gallery`) of the
overlanding-build Tacoma, with more hobbies (CNC, 3D printing, woodworking) and eventually
software/website design planned as the site grows into a portfolio for `vestal.services` LLC
(not registered yet as of 2026-07-26). Deployed on Railway, DNS on Cloudflare.

This repo was refactored (2026-07) from an AngularJS 1.x/ng-grid SPA with a runtime-CSV-parsing
Express API into the current server-rendered form. It's also the source, alongside
[playoff-fantasy](https://github.com/arvestal/playoff-fantasy), for the
[website-starter](https://github.com/arvestal/website-starter) template repo — if a convention
here turns out to be wrong or improves, consider porting the fix there too.

## Commands

```bash
npm run dev          # nodemon, http://localhost:8080
npm run lint
npm test               # jest with coverage (100% lines/branches/functions/statements required
                        # on src/app.js, src/lib/**, src/routes/**, scripts/generate-stats.js)
npm run build:stats    # regenerate data/softball/seasons.js from data/gc_files/*.csv
```

## Architecture map

- `src/app.js` — entry point: Handlebars engine + helpers, static files, `/health`, www→root
  redirect, 404 handler. Exports `app` unconditionally; only calls `.listen()` when run directly
  (`require.main === module`), so `tests/app.test.js` can drive it with `supertest`.
- `src/lib/helpers.js` — Handlebars helpers (`number3`)
- `src/lib/nav.js` — season nav-group / year-tab data (`buildSeasonNavGroups`, `seasonsForLabel`)
- `src/lib/schedule.js` — per-game result (W/L/T/FFT), schedule display fields, championship-banner check
- `src/lib/stats.js` — stat table column config, AVG-desc sort, id-whitelist filter
- `src/routes/index.js` — `/`, `/about`, `/contact`, `/sitemap.xml`
- `src/routes/softball.js` — `/softball` (career), `/softball/postseason`, `/softball/:season`
- `src/routes/gallery.js` — public `/gallery`; reads live photo metadata via
  `src/lib/gallery-store.js` and maps it to view data via `src/lib/gallery.js`'s
  `buildGalleryPhotos`
- `src/routes/admin.js` — Google-OAuth-gated admin at `/admin` (login/callback/logout plus photo
  upload/edit/delete); see **Admin & auth** below
- `src/lib/gallery-store.js` — reads/writes `photos.json` on the Railway volume
  (`GALLERY_DATA_DIR`); the single source of truth for gallery photos at runtime
- `src/lib/gallery-upload.js` — sharp-only resize/WebP-convert for admin-uploaded photos (no
  `sips`/`mdls` — those are macOS-only, this runs on Railway's Linux container)
- `src/lib/admin-auth.js` — signs/verifies the admin session JWT; `safeNextPath` (post-login return path)
- `src/lib/require-admin.js` — the login-gate middleware shared by `/admin` and `/cf26`
- `src/routes/cf26.js` — private CF26 scouting pages at `/cf26` (see **CF26 scouting** below)
- `cf26/` — the CF26 opponent-scouting pipeline (Python) and its generated pages; see `cf26/README.md`
- `views/*.hbs` — Handlebars templates; `views/layouts/main.hbs` is the shared layout;
  `views/admin/*.hbs` is the admin login/dashboard UI
- `data/gc_files/*.csv` — raw GameChanger season exports (source of truth for stats)
- `data/softball/seasons.js` — **generated**, committed. Per-season + career + postseason player
  stats. Produced by `scripts/generate-stats.js`; never hand-edited.
- `data/softball/standings.js` — **hand-authored**, committed. Win/loss/schedule data (not
  derivable from the CSVs) plus the two curated roster-id whitelists (`CAREER_PLAYER_IDS`,
  `POSTSEASON_PLAYER_IDS`) that limit which players show on the career/postseason tables.
- `/data/gallery/photos.json` (on the Railway volume, **not** in git) — `[{slug, source, alt,
  date}]`, the live gallery data. Read/written by `src/lib/gallery-store.js`; managed through
  `/admin`, not by hand-editing.
- `/data/gallery/{full,thumb}/*.webp` (on the Railway volume, **not** in git) — the actual photo
  files. Full images capped at 2000px on the long edge; thumbs at 480px wide.

## Data pipeline

Stats are static and don't change at runtime — no DB, no request-time CSV parsing, no cache
layer. `scripts/generate-stats.js` is a one-off script (`npm run build:stats`) that reads
`data/gc_files/*.csv`, computes per-season and aggregate (career/postseason) stats, and writes
`data/softball/seasons.js` as a plain committed JS module the app just `require()`s. Re-run and
commit the diff if the source CSVs change; the server never touches the CSVs directly.

**Column lookup**: every CSV export shares one 152-column header (offensive stats, then a
pitching/fielding block). Several names repeat in both blocks (`GP`, `H`, `BB`, `SO`, `R`, `HR`,
`TB`, `SB`, `CS`, `SB%`, `PIK`, `BABIP`, `LOB`, `GB%`) — the offensive occurrence always comes
first, so columns are located by name (`header.indexOf(name)`), never by hardcoded position. The
pre-refactor code used a hand-counted positional array with a hole-count mistake starting at the
`XBH` column, which silently shifted every field after it by one for years without anyone
noticing (the resulting numbers still looked plausible). Don't reintroduce a positional array.

**Per-season vs. aggregate rate stats**: per-season `AVG`/`OBP`/`SLG`/`OPS` are taken directly
from GameChanger's own columns (not recomputed), matching what the site has always shown for a
single season. Career/postseason aggregation sums counting stats across seasons and then
recomputes rate stats from those sums (`H/AB`, `(H+BB)/(AB+BB+SAC)`, etc.) — this intentionally
omits HBP, a pre-existing simplification from the original app that's preserved rather than
"fixed," so historical career numbers don't shift.

## Gallery pipeline

Gallery photos are **runtime data on a Railway volume**, not committed to git — this was the
first thing in the app that needed persistent, writable storage, added specifically so `/admin`
can upload/delete photos without a code deploy. `GALLERY_DATA_DIR` (env var, `/data/gallery` in
production) holds `photos.json` (`[{slug, source, alt, date}]`) plus `full/` and `thumb/` WebP
files. `src/lib/gallery-store.js` is the only thing that reads/writes it.

**Why a volume, not git**: Railway does a fresh git checkout on every build regardless of which
files a push touched — committing ~250 photos (108MB+) added that weight to every single build.
A volume is also the only Railway storage that survives a redeploy; anything written to the
regular container filesystem at runtime is gone on the next push. Both problems disappear once
photos live on the volume instead of in the repo.

**All photos go through `/admin`'s upload form** (`src/lib/gallery-upload.js`, sharp-only, no
`sips`/`mdls`) — it works on Railway's Linux container and writes straight to the volume. It
rejects some HEIC variants sharp can't decode (multi-reference "portrait"/burst containers exceed
libvips' HEIF security limit); the admin UI asks for a JPEG re-export in that case rather than
failing silently.

The original 250-photo bulk import (2026-07-26, from a `tacoma/` folder of raw phone photos) used
a since-deleted one-off pipeline: a macOS-only script (`sips`/`mdls` for HEIC normalization and
real EXIF capture dates — file mtimes only reflect when photos were copied onto a machine, not
when they were taken) produced git-committed WebP files + a manifest, and a one-off migration
script merged that onto the volume as the initial `photos.json`, then both were deleted once the
volume-backed version was verified working in production. There's no bulk-import path anymore —
if a large batch of photos needs adding again, that'd be a new feature (e.g. multi-file upload) to
build against the current volume/admin architecture, not a resurrection of that old script.

**Alt text**: writing it requires actually looking at each photo — there's no way to generate it.
The admin dashboard has an inline alt-text field per photo for this. Avoid describing anything
personally identifying visible in a shot (license plates, street addresses/house numbers) even if
legible in the photo.

**Near-duplicate photos**: a straight file-hash dedupe won't catch burst shots (same scene,
slightly different framing/exposure) — this repo's first pass used a perceptual hash (dHash,
8x8 grayscale, Hamming distance ≤8) to cluster near-duplicates before generating anything, then
deleted the lower-quality file from each cluster directly out of `tacoma/`. Only 8 of the original
258 photos turned out to be true near-duplicates; most of a phone camera roll like this is
genuinely distinct shots, not bursts — don't assume heavy duplication without checking.

## Admin & auth

`/admin` (photo upload/edit/delete) is gated by Google login restricted to exactly one email
(`ADMIN_EMAIL`) — no other Google account can log in at all, not even to a lesser-privileged
state. Deliberately **not** Passport/`express-session`, and **not** the same pattern as
`playoff-fantasy`'s admin (which lets any Google account log in, then flags one email as admin via
a `users` table on SQLite): this site has no database, only one possible admin, and no per-user
data to track, so a full session/user-table layer would be pure overhead.

- **Flow**: `google-auth-library`'s `OAuth2Client` directly (`src/routes/admin.js`) —
  `/admin/auth/google` sets a short-lived signed `oauth_state` cookie and redirects to Google;
  `/admin/auth/google/callback` checks that state, exchanges the code, verifies the ID token, and
  rejects outright (403, no cookie issued) unless the verified email matches `ADMIN_EMAIL` exactly.
- **Session is stateless**: on success, `src/lib/admin-auth.js` signs a JWT (email + 30-day
  expiry) into an `httpOnly`/`secure`/`sameSite=lax` cookie. Every request re-verifies that cookie
  — no server-side session store at all. This matters because the deploy trigger means this app's
  process restarts on every push; a session store would need to survive that (playoff-fantasy
  solves this with SQLite-on-a-volume), but a signed cookie doesn't need to survive anything since
  there's no server-side state to lose.
- **Required env vars**: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ADMIN_EMAIL`, `ADMIN_JWT_SECRET`,
  `BASE_URL` (builds the exact callback URL — must match what's registered in Google Cloud
  Console), `NODE_ENV=production` (gates the `secure` cookie flag — without it, cookies aren't
  marked secure and won't be sent correctly over HTTPS in production).
- **Manual step, can't be automated**: creating the OAuth Client ID and registering the callback
  URL (`{BASE_URL}/admin/auth/google/callback`) has to happen in Google Cloud Console by hand —
  no API for this that an agent can drive.
- **Reusable pattern**: this whole login-gate design (not the gallery-specific upload/delete code)
  is meant to be portable to `website-starter` via a configurable `ADMIN_EMAIL`, so any future
  personal site (Mary/Taylor/Logan's included) can gate its own admin behind exactly one Google
  account without needing a database.

## CF26 scouting (`cf26/`, `/cf26`)

Opponent scouting for EA SPORTS College Football 26: game recordings → per-snap play-by-play → per-opponent
scouting report + defensive game plan. Merged in 2026-10-07 from the separate `cf26-scouting` repo (history preserved
via `git subtree add`), so there's one repo. Details in `cf26/README.md` / `cf26/SCHEMA.md`.

- **Pipeline runs on the Mac, not on Railway**: Python 3 stdlib + `ffmpeg` + macOS Vision OCR (`cf26/scripts/ocr.swift`).
  It writes committed files under `cf26/opponents/<player>-<team>/`. The Node app never runs any of it.
- **Processing new games**: `/scout-new-games [opponent]` (`.claude/skills/scout-new-games/`) — extracts new recordings
  from each opponent's `video_dir` (absolute paths outside the repo), rebuilds data + reports, updates the game plan,
  runs lint/tests, commits, pushes (= deploys).
- **Serving**: `src/routes/cf26.js` serves only `cf26/index.html` and `cf26/opponents/<id>/reports/{gameplan,scouting_report}.html`,
  behind `requireAdmin({ returnTo: true })` (same ADMIN_EMAIL Google login as `/admin`; unauthenticated visitors go to
  `/admin/login?next=…` and land back on the page). Responses are `Cache-Control: private, no-store` + `X-Robots-Tag: noindex`;
  `/cf26` is also disallowed in `robots.txt`. The pages are self-contained HTML with relative links, so the URL layout
  mirrors the folder layout and `/cf26` must redirect to `/cf26/`.
- **Public repo**: the owner is fine with the scouting files being readable on GitHub; only the website copy is gated.
- **Game plans stay structurally identical across opponents**: a layout or format change requested for one
  opponent's page is applied to every opponent's page (with their own data), and the `/scout-new-games` skill's
  structure notes are updated to match. Opponent-specific values (calls, settings, numbers) stay per opponent.
- **`?next=` safety**: `safeNextPath` only accepts same-site paths (`/x`, not `//x`, `/\x` or absolute URLs), so the login
  flow can't be used as an open redirect. The value rides in a short-lived `admin_next` cookie across the OAuth round trip.

## Conventions

- **Git workflow: commit straight to `main`, no feature branches or PRs.** The project owner
  explicitly asked for this (2026-07-25) after several PRs — "it's just text content anyways."
  This reverses the branch+PR workflow used earlier in the same refactor; if they ever want it
  back for this repo, that instruction would need to be explicit again. Still run `npm run lint`
  and the full test suite (100% coverage gate) before every commit — only the branch/PR ceremony
  was relaxed, not the quality bar.
- Sortable stats tables (`public/js/sortable-table.js`) are vanilla JS, no build step, no
  framework — consistent with dropping AngularJS/ng-grid entirely rather than reaching for a new
  frontend framework.
- Season pages (`views/softball/season.hbs`) are one shared template for every regular season
  *and* postseason — season-specific data comes from the route, not from 25 near-duplicate
  templates (which is what the pre-refactor `public/partials/*.html` was).

## Known footguns / past bugs (don't reintroduce)

- A tracked `.DS_Store` used to break `git pull`/`git checkout` repeatedly ("local changes would
  be overwritten") because Finder keeps rewriting it. It's untracked now (`**/.DS_Store` in
  `.gitignore`) — if this ever recurs, `git rm --cached` it, don't just retry the pull.
- `railway redeploy` re-deploys whatever commit is *already built* — it does **not** pull a new
  commit after a push. To actually deploy new code: `railway service source connect --repo
  arvestal/allenvestal.com --branch main --service allenvestal-com` (forces a fresh pull + build).
  Always confirm the deployed commit hash via `railway deployment list --json` rather than
  assuming a redeploy picked up the latest push.
  - **As of 2026-07-26 this footgun no longer applies day-to-day**: the service (named `softball`
    until it was renamed to `allenvestal-com` on 2026-07-27 to match the naming convention used by
    the other Vestal family sites — see mary/logan/taylor's `<name>vestal-com` service names) has
    a GitHub push-to-`main` deploy trigger (Railway's `Service.repoTriggers`, added via the
    `deploymentTriggerCreate` GraphQL mutation — there's no CLI/dashboard shortcut for it), so
    ordinary pushes auto-deploy on their own, matching `playoff-rally`. The manual
    `source connect` trick above is now only needed if the trigger itself ever gets removed or
    stops firing. The trigger had been missing since the repo rename (`softball` →
    `allenvestal.com`) because Railway's GitHub App wasn't authorized on the renamed repo —
    `Service.repoTriggers` returned `[]` and `deploymentTriggerCreate` failed with "no one in the
    project has access to it" until repo access was re-granted at
    `github.com/settings/installations`.
- The custom domain's Railway-issued certificate got stuck in
  `CERTIFICATE_STATUS_TYPE_VALIDATING_OWNERSHIP` for an extended period even with verified-correct
  DNS (likely from repeated delete/recreate churn tripping a Let's Encrypt rate limit). Fix used:
  proxy the apex through Cloudflare (matching `www`, which was already proxied) instead of
  waiting on or retrying Railway's cert — Cloudflare's own Universal SSL cert already covers the
  apex (its SAN list includes both the bare domain and `*.domain`), so this sidesteps Railway's
  stuck internal state entirely rather than fixing it. See `www`'s Cloudflare DNS record as the
  reference for how the apex should also be configured if this happens again.
- Railway's free plan allows only one custom domain per service — `www` can't be a second Railway
  custom domain. It's a Cloudflare Page Rule (`www.allenvestal.com/*` → `https://allenvestal.com/$1`,
  301) instead.
- `npm install`/`npm pull` can fail against a stale `package-lock.json` if it was generated on a
  machine with a now-defunct private registry configured (this repo's original lockfile pointed
  at a dead GoDaddy-internal Artifactory instance) — delete the lockfile and reinstall fresh
  rather than debugging registry auth for a registry that shouldn't be in the resolution path
  anymore.
- A CSS change can deploy successfully and still not show up for a returning visitor: Cloudflare
  stamps static assets like `/css/main.css` with a long browser `Cache-Control` (observed:
  `public, max-age=14400`, 4 hours) regardless of what Express sends, so a browser that already
  fetched the old CSS won't even re-check the server for up to 4 hours. Fixed by cache-busting the
  stylesheet URL with Railway's auto-injected `RAILWAY_GIT_COMMIT_SHA` (`src/app.js` sets
  `res.locals.assetVersion`, `views/layouts/main.hbs` appends it as `?v=...`) so every deploy gets
  a new URL. If a CSS/JS change ever looks like it "didn't take" after a successful deploy, hard
  refresh first before assuming the deploy failed.

## Local dev

```bash
npm install
npm run build:stats   # only needed if data/softball/seasons.js is missing/stale
npm run dev
```

No `.env` is required for the softball/gallery-viewing side of local dev — `GALLERY_DATA_DIR`
defaults to a gitignored local folder when unset. `/admin` needs real values to fully exercise
locally (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ADMIN_EMAIL`, `ADMIN_JWT_SECRET`; see
**Admin & auth**). `.env` in this repo (gitignored) also holds GoDaddy/Cloudflare/Railway API
tokens used for *operating* the deployed site (DNS, hosting), not runtime app config.

## Deployment

- Railway project **allen-vestal**, service **allenvestal-com** (renamed from `softball`
  2026-07-27 to match the `<name>vestal-com` convention used by mary/logan/taylor's Railway
  services), connected to `arvestal/allenvestal.com` (repo renamed from `softball` 2026-07-26) on
  `main` (renamed from `master` same day). Builds via Railpack (no Dockerfile — the repo
  intentionally has none; see the redeploy footgun above for how to force a fresh deploy after
  pushing).
- **Persistent volume** `allenvestal-com-volume` (renamed from `softball-volume` in the same
  2026-07-27 pass) mounted at `/data` (added 2026-07-26 for the gallery admin — this app's first
  runtime-writable state). `GALLERY_DATA_DIR=/data/gallery` points the app at it. Created via the
  `volumeCreate` GraphQL mutation — no CLI/dashboard-tool shortcut for it either, same as the
  deploy trigger.
- Custom domain `allenvestal.com` (apex, proxied through Cloudflare — see the stuck-cert footgun
  above for why). `www.allenvestal.com` redirects to the apex via a Cloudflare Page Rule.
- DNS is on Cloudflare (migrated from GoDaddy 2026-07-25); GoDaddy remains the registrar only.
- `/health` returns `200 {"status":"ok"}` for Railway's healthcheck.
