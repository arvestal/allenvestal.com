"""Opponent registry: each opponent (a person + the team(s) they use) lives in opponents/<id>/ with a profile.json."""
import glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPP_ROOT = os.path.join(ROOT, 'opponents')


def all_ids():
    return sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(OPP_ROOT, '*', 'profile.json')))


def path(opp, *parts):
    return os.path.join(OPP_ROOT, opp, *parts)


def profile(opp):
    return json.load(open(path(opp, 'profile.json')))


def videos(opp):
    p = path(opp, 'videos.json')
    return json.load(open(p)) if os.path.exists(p) else []


def save_videos(opp, vids):
    json.dump(vids, open(path(opp, 'videos.json'), 'w'), indent=1, ensure_ascii=False)


def video_dir(opp):
    """Folder with this opponent's recordings, or None if not set up yet."""
    d = profile(opp).get('video_dir')
    return os.path.abspath(os.path.join(ROOT, d)) if d else None


def resolve(arg):
    """--opponent value -> list of ids (accepts id, player name, or team; empty = all)."""
    if not arg:
        return all_ids()
    a = arg.lower()
    hits = [o for o in all_ids() if a in (o, profile(o)['player'].lower()) or a in [t.lower() for t in profile(o)['teams']]]
    if not hits:
        raise SystemExit(f"unknown opponent '{arg}'. Known: {', '.join(all_ids())}")
    return hits
