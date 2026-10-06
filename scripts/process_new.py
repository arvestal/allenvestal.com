"""Find recordings not yet in data/videos.json, extract + OCR them, register them, and rebuild everything.

    python3 scripts/process_new.py [--video-dir DIR] [--dry-run]

Settings live in data/config.json:
    scout_team    team being scouted (must appear on the scoreboard)
    video_dir     folder with the .mp4 recordings (relative to the repo root)
    user_playbook your defensive playbook, recorded with each game
"""
import argparse, gzip, json, os, re, shutil, subprocess, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import scoreboard

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEOS = os.path.join(ROOT, 'data', 'videos.json')


def team_names(sb_gz):
    """Most common team name on the left and right of the scoreboard."""
    left, right = Counter(), Counter()
    for line in gzip.open(sb_gz, 'rt'):
        for x, y, t in scoreboard.tokens(line.partition('\t')[2]):
            name = re.sub(r'^[^A-Za-z]+', '', t).strip()  # drop rank digits / OCR junk in front
            if len(name) >= 4 and name.isupper() and 0.4 < y < 0.65:
                (left if x < 0.4 else right if x > 0.6 else Counter())[name] += 1
    return (left.most_common(1)[0][0] if left else None, right.most_common(1)[0][0] if right else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--video-dir')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    cfg = json.load(open(os.path.join(ROOT, 'data', 'config.json')))
    vdir = os.path.abspath(os.path.join(ROOT, args.video_dir or cfg['video_dir']))
    videos = json.load(open(VIDEOS))
    known = {v['file'] for v in videos}
    new = sorted(f for f in os.listdir(vdir) if f.lower().endswith(('.mp4', '.mov')) and f not in known)
    if not new:
        print(f'No new videos in {vdir}')
        return
    print('New videos:', *new, sep='\n  ')
    if args.dry_run:
        return
    if not shutil.which('ffmpeg'):
        sys.exit('ffmpeg not found: brew install ffmpeg')

    scout = cfg['scout_team'].upper()
    for f in new:
        m = re.search(r'(\d{4}-\d{2}-\d{2}) (\d{2})-(\d{2})', f)
        date = m[1] if m else 'unknown-date'
        tmp = f"{date}-{m[2]}{m[3]}" if m else re.sub(r'\W+', '-', f)[:40]
        print(f'\n== {f}\n   extracting as {tmp} (about 10 min per hour of video)')
        subprocess.run([os.path.join(ROOT, 'scripts', 'extract.sh'), tmp, os.path.join(vdir, f)], check=True)

        left, right = team_names(os.path.join(ROOT, 'data', 'ocr', tmp, 'sb.tsv.gz'))
        print(f'   scoreboard: {left} (left) vs {right} (right)')
        if not left or not right or scout not in (left + right):
            print(f'   !! {cfg["scout_team"]} not found on the scoreboard — kept OCR under data/ocr/{tmp}, not registered')
            continue
        side = 0 if scout in left else 1
        user = (right if side == 0 else left).title()
        vid = f"{date}-{re.sub(r'[^a-z0-9]+', '-', user.lower()).strip('-')}"
        while any(v['id'] == vid for v in videos):
            vid += '-2'
        os.rename(os.path.join(ROOT, 'data', 'ocr', tmp), os.path.join(ROOT, 'data', 'ocr', vid))
        videos.append({'id': vid, 'file': f, 'date': date, 'user_team': user, 'scout_team': cfg['scout_team'],
                       'scout_side': side, 'user_playbook': cfg.get('user_playbook', '')})
        json.dump(videos, open(VIDEOS, 'w'), indent=1, ensure_ascii=False)
        print(f'   registered as {vid}: {user} vs {cfg["scout_team"]} (scout on the {"left" if side == 0 else "right"})')

    for script in ('build_plays.py', 'analyze.py'):
        subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', script)], check=True)


if __name__ == '__main__':
    main()
