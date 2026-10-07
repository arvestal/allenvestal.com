"""Find new recordings in every opponent's video folder, extract + OCR them, file each one under the
opponent whose team is on the scoreboard, and rebuild that opponent's data and report.

    python3 scripts/process_new.py [--opponent jason] [--dry-run]

Videos whose scoreboard shows no known opponent team are listed in unassigned.json (so they aren't
re-extracted every run) and their OCR is kept under unassigned/<name>/ in case a profile is added later.
"""
import argparse, difflib, gzip, json, os, re, shutil, subprocess, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import scoreboard
import opponents

ROOT = opponents.ROOT
UNASSIGNED = os.path.join(ROOT, 'unassigned.json')
VIDEO_EXT = ('.mp4', '.mov')


def team_names(sb_gz):
    """Most common team name on the left and right of the scoreboard."""
    left, right = Counter(), Counter()
    for line in gzip.open(sb_gz, 'rt'):
        for x, y, t in scoreboard.tokens(line.partition('\t')[2]):
            name = re.sub(r'^[^A-Za-z]+', '', t).strip()  # drop rank digits / OCR junk in front
            if len(name) >= 4 and name.isupper() and 0.4 < y < 0.65:
                if x < 0.4:
                    left[name] += 1
                elif x > 0.6:
                    right[name] += 1
    return (left.most_common(1)[0][0] if left else None, right.most_common(1)[0][0] if right else None)


def same_team(team, name):
    """Scoreboard name vs profile team. Tolerates a one-letter OCR slip ("TOWA" = IOWA) but not a different
    team that contains the name ("NORTH TEXAS" is not TEXAS)."""
    a, b = team.upper(), (name or '').strip().upper()
    return a == b or (len(a) == len(b) and difflib.SequenceMatcher(None, a, b).ratio() >= 0.75)


def match(left, right, ids, preferred=None):
    """Which opponent profile has a team on this scoreboard? -> (opp, side of the opponent's team)."""
    hits = []
    for opp in ids:
        for team in opponents.profile(opp)['teams']:
            for side, name in ((0, left), (1, right)):
                if same_team(team, name):
                    hits.append((opp, side))
    hits.sort(key=lambda h: h[0] != preferred)  # the folder the video was found in wins ties
    return hits[0] if hits else (None, None)


def register(opp, side, left, right, f, date, ocr_dir):
    """Move a processed recording's OCR under the opponent and add it to their videos.json."""
    prof = opponents.profile(opp)
    vids = opponents.videos(opp)
    my_team = ((right if side == 0 else left) or 'unknown').title()
    vid = f"{date}-{slug(my_team)}"
    while any(v['id'] == vid for v in vids):
        vid += '-2'
    dest = opponents.path(opp, 'ocr', vid)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    os.rename(ocr_dir, dest)
    team = prof['teams'][0] if any(same_team(t, left if side == 0 else right) for t in prof['teams']) else (left if side == 0 else right).title()
    vids.append({'id': vid, 'file': f, 'date': date, 'user_team': my_team, 'scout_team': team,
                 'scout_side': side, 'user_playbook': prof.get('my_playbook', '')})
    opponents.save_videos(opp, vids)
    print(f'   -> {opp}/{vid}: you ({my_team}) vs {prof["player"]} ({team})')


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--opponent', help="only look in this opponent's video folder (id, player, or team)")
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    ids = opponents.all_ids()
    unassigned = json.load(open(UNASSIGNED)) if os.path.exists(UNASSIGNED) else []
    touched = set()

    # earlier recordings that matched nobody: file them now if a profile matches (no re-extraction)
    still = []
    for u in unassigned:
        opp, side = match(*u['teams'], ids)
        if opp and not args.dry_run:
            print(f"== {u['file']} (previously unassigned: {u['teams'][0]} vs {u['teams'][1]})")
            m = re.search(r'(\d{4}-\d{2}-\d{2})', u['file'])
            register(opp, side, *u['teams'], u['file'], m[1] if m else 'unknown-date', os.path.join(ROOT, u['ocr']))
            touched.add(opp)
        else:
            if opp:
                print(f"  [{opp}] {u['file']} (previously unassigned, will be filed)")
            still.append(u)
    if len(still) != len(unassigned):
        unassigned = still
        json.dump(unassigned, open(UNASSIGNED, 'w'), indent=1, ensure_ascii=False)
    known = {v['file'] for o in ids for v in opponents.videos(o)} | {u['file'] for u in unassigned}

    todo, seen = [], set()  # (folder owner, folder, file)
    for opp in opponents.resolve(args.opponent):
        d = opponents.video_dir(opp)
        if not d:
            print(f'{opp}: no video_dir set — skipped')
            continue
        if not os.path.isdir(d):
            print(f'{opp}: video folder {d} does not exist — skipped')
            continue
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(VIDEO_EXT) and f not in known and (d, f) not in seen:
                seen.add((d, f))
                todo.append((opp, d, f))
    if not todo and not touched:
        print('No new videos.')
        return
    print('New videos:')
    for opp, d, f in todo:
        print(f'  [{opp}] {f}')
    if args.dry_run:
        return
    if todo and not shutil.which('ffmpeg'):
        sys.exit('ffmpeg not found: brew install ffmpeg')

    for folder_opp, d, f in todo:
        m = re.search(r'(\d{4}-\d{2}-\d{2}) (\d{2})-(\d{2})', f)
        date = m[1] if m else 'unknown-date'
        tmp = os.path.join(ROOT, 'work', 'ocr-' + (f"{date}-{m[2]}{m[3]}" if m else slug(f)[:40]))
        print(f'\n== {f}\n   extracting (about 10 min per hour of video)')
        subprocess.run([os.path.join(ROOT, 'scripts', 'extract.sh'), tmp, os.path.join(d, f)], check=True)

        left, right = team_names(os.path.join(tmp, 'sb.tsv.gz'))
        print(f'   scoreboard: {left} (left) vs {right} (right)')
        opp, side = match(left, right, ids, folder_opp)
        if not opp:
            keep = os.path.join(ROOT, 'unassigned', os.path.basename(tmp))
            os.makedirs(os.path.dirname(keep), exist_ok=True)
            shutil.rmtree(keep, ignore_errors=True)
            os.rename(tmp, keep)
            unassigned.append({'file': f, 'folder': d, 'teams': [left, right], 'ocr': os.path.relpath(keep, ROOT)})
            json.dump(unassigned, open(UNASSIGNED, 'w'), indent=1, ensure_ascii=False)
            print(f'   !! no opponent profile has {left} or {right} — listed in unassigned.json')
            continue
        if opp != folder_opp:
            print(f"   note: found in {folder_opp}'s folder but the scoreboard says {opp}")
        register(opp, side, left, right, f, date, tmp)
        touched.add(opp)

    for opp in sorted(touched):
        for script in ('build_plays.py', 'analyze.py'):
            subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', script), '--opponent', opp], check=True)
    if touched:
        subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'render_html.py')], check=True)


if __name__ == '__main__':
    main()
