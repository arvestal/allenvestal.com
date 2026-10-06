"""Enrich snaps (formation names, coverage family, play guesses) and write the scouting outputs.

Per opponent, under opponents/<opp>/:
Reads  games/*.json                 (from build_plays.py)
Writes plays.csv                    one row per scouted-team snap, all games
       formation_plays.json         formation -> plays seen from it (the guess model)
       reports/scouting_report.md   tendencies by down & distance, coverage, play, formation

    python3 scripts/analyze.py [--opponent jason]   (default: every opponent)
"""
import argparse, csv, difflib, glob, json, os, re, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
import opponents

FORMATIONS = [
    'Shotgun - Normal Y Off Close', 'Shotgun - Flex Y Off Close', 'Shotgun - Bunch Spread',
    'Shotgun - Bunch Str Offset', 'Shotgun - Bunch Open Offset', 'Shotgun - Bunch TE',
    'Shotgun - Spread Dbl Flex', 'Shotgun - Spread Y-Flex', 'Shotgun - Spread Y Slot Wk',
    'Shotgun - Trips Offset', 'Shotgun - Trips Y Slot Wk', 'Shotgun - Trips TE', 'Shotgun - Y Off Trips Wk',
    'Shotgun - Trio Rt Open', 'Shotgun - Ace Offset', 'Shotgun - Doubles', 'Shotgun - Doubles HB Wk',
    'Shotgun - 5WR', 'Shotgun - 5WR Flex Trey', 'Shotgun - Box', 'Pistol - Trips',
    'I Form - Close', 'I Form - Pro', 'Goal Line Offense - Normal', 'Field Goal', 'Punt',
]
_norm = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
_FN = {_norm(f): f for f in FORMATIONS}


def canon_formation(raw):
    if not raw:
        return None
    tail = raw.split('-', 1)[-1] if '-' in raw else raw
    if len(re.sub(r'[^A-Za-z]', '', tail)) < 3:
        return None
    n = _norm(raw)
    best = max(_FN, key=lambda k: difflib.SequenceMatcher(None, n, k).ratio())
    if difflib.SequenceMatcher(None, n, best).ratio() >= 0.6:
        return _FN[best]
    # truncated prefix, e.g. "Form - Clos" -> "I Form - Close"
    hits = [k for k in _FN if n and n[:6] in k]
    return _FN[hits[0]] if len(hits) == 1 else None


def coverage_family(name):
    n = (name or '').upper()
    if re.search(r'BLITZ|FIRE|PINCH|\bSTING\b|OVERLOAD|SS 2 TRAP|CROSS 0|\b0\b', n):
        return 'Blitz/Pressure'
    for pat, fam in [(r'COVER 2 MAN|2 MAN', 'Cover 2 Man'), (r'COVER 1|ROBBER|1 HOLE', 'Cover 1'),
                     (r'COVER 3|3 SKY|3 BUZZ|3 MATCH|3 CLOUD|3 LOCK', 'Cover 3'),
                     (r'COVER 4|QUARTERS|PALMS|4 DROP', 'Cover 4'), (r'COVER 6|COVER 9', 'Cover 6/9'),
                     (r'TAMPA 2', 'Tampa 2'), (r'COVER 2|INVERT', 'Cover 2 Zone'),
                     (r'DOUBLE BRACKET|DOUBLE WR1|DOUBLE MAN', 'Double/Bracket')]:
        if re.search(pat, n):
            return fam
    return None


def bucket(s):
    d, dist, ytg = s['down'], s['dist'], s['ytg']
    if dist == 'G' or ytg <= 10:
        return 'Goal to go / inside 10'
    dd = ytg if dist == 'G' else dist
    if d == 1:
        return '1st & 10+' if dd >= 10 else '1st & short'
    rng = 'short (1-3)' if dd <= 3 else 'medium (4-6)' if dd <= 6 else 'long (7+)'
    return f"{['', '1st', '2nd', '3rd', '4th'][d]} & {rng}"


def success(s):
    """Standard success rate: 40% of distance on 1st, 60% on 2nd, all of it on 3rd/4th."""
    if s.get('yards') is None:
        return None
    if s['result'] in ('touchdown', 'first_down'):
        return True
    dist = s['ytg'] if s['dist'] == 'G' else s['dist']
    need = {1: 0.4, 2: 0.6}.get(s['down'], 1.0) * dist
    return s['yards'] >= need


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--opponent')
    for opp in opponents.resolve(ap.parse_args().opponent):
        analyze(opp)


def analyze(opp):
    prof = opponents.profile(opp)
    games = [json.load(open(f)) for f in sorted(glob.glob(opponents.path(opp, 'games', '*.json')))]
    if not games:
        print(f"{opp}: no games yet")
        return
    rows = []
    for g in games:
        v = g['video']
        for s in g['snaps']:
            if s['offense'] != v['scout_team'] or s.get('special_teams'):
                continue
            s = dict(s)
            s['video_file'] = v['file']
            s['opponent'] = v['user_team']
            s['formation'] = canon_formation(s.get('off_formation'))
            if s['formation'] in ('Field Goal', 'Punt'):
                continue
            s['def_family'] = coverage_family(s.get('def_play'))
            if not s['def_family'] and s.get('def_candidates'):
                fams = {coverage_family(t.split(':', 1)[-1]) for t in s['def_candidates']}
                if len(fams) == 1 and None not in fams:
                    s['def_family'] = fams.pop()
                    s['def_family_source'] = 'on-screen options'
            elif s['def_family']:
                s['def_family_source'] = 'panel'
            s['bucket'] = bucket(s)
            s['success'] = success(s)
            rows.append(s)

    # formation -> plays seen from it (panel-confirmed only)
    form_plays = defaultdict(Counter)
    situ_plays = defaultdict(Counter)
    for s in rows:
        if s.get('off_play'):
            situ_plays[s['bucket']][s['off_play']] += 1
            if s['formation']:
                form_plays[s['formation']][s['off_play']] += 1
    overall = Counter(s['off_play'] for s in rows if s.get('off_play'))

    for s in rows:
        if s.get('off_play'):
            continue
        if s['formation'] and form_plays.get(s['formation']):
            c = form_plays[s['formation']]
            s['off_play_guess'] = [p for p, _ in c.most_common(3)]
            s['guess_basis'] = f"seen from {s['formation']} ({sum(c.values())} confirmed)"
        else:
            c = situ_plays.get(s['bucket']) or overall
            s['off_play_guess'] = [p for p, _ in c.most_common(3)]
            s['guess_basis'] = f"his most-called plays on {s['bucket']}" if situ_plays.get(s['bucket']) else 'his most-called plays overall'

    # ---- outputs
    json.dump({f: dict(c.most_common()) for f, c in sorted(form_plays.items())},
              open(opponents.path(opp, 'formation_plays.json'), 'w'), indent=1)
    cols = ['video_id', 'video_file', 'timestamp', 'opponent', 'qtr', 'clock', 'down', 'dist', 'ytg', 'bucket',
            'formation', 'off_personnel', 'off_play', 'play_source', 'off_play_guess', 'guess_basis',
            'def_play', 'def_family', 'def_family_source', 'def_candidates', 'yards', 'result', 'success', 'panel_timestamp']
    with open(opponents.path(opp, 'plays.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols)
        for s in rows:
            w.writerow(['; '.join(s[c]) if isinstance(s.get(c), list) else ('' if s.get(c) is None else s[c]) for c in cols])
    write_report(opp, prof, rows, form_plays)
    print(f"{opp}: {len(rows)} snaps -> opponents/{opp}/plays.csv, formation_plays.json, reports/scouting_report.md")


def stats(ss):
    ys = [s['yards'] for s in ss if s.get('yards') is not None]
    sc = [s['success'] for s in ss if s.get('success') is not None]
    return {
        'n': len(ss), 'avg': sum(ys) / len(ys) if ys else None,
        'succ': sum(sc) / len(sc) if sc else None,
        'expl': sum(y >= 15 for y in ys) / len(ys) if ys else None,
        'td': sum(s['result'] == 'touchdown' for s in ss),
    }


def fmt(st):
    a = f"{st['avg']:.1f}" if st['avg'] is not None else '–'
    s = f"{st['succ']:.0%}" if st['succ'] is not None else '–'
    e = f"{st['expl']:.0%}" if st['expl'] is not None else '–'
    return f"{st['n']} | {a} | {s} | {e} | {st['td']}"


BUCKET_ORDER = ['1st & 10+', '1st & short', '2nd & short (1-3)', '2nd & medium (4-6)', '2nd & long (7+)',
                '3rd & short (1-3)', '3rd & medium (4-6)', '3rd & long (7+)', '4th & short (1-3)',
                '4th & medium (4-6)', '4th & long (7+)', 'Goal to go / inside 10']


def write_report(opp, prof, rows, form_plays):
    L = []
    o = stats(rows)
    L += [f"# {prof['player']} ({' / '.join(prof['teams'])}) — offense scouting report", '',
          f"Source: {len({s['video_id'] for s in rows})} games, {o['n']} offensive snaps "
          f"({sum(1 for s in rows if s.get('off_play'))} with the play confirmed by the PREVIOUS PLAY panel).", '',
          'Columns: **n** snaps | **avg** yards per play | **succ** success rate (40% of the distance on 1st down, 60% on 2nd, '
          'all of it on 3rd/4th) | **expl** share of plays gaining 15+ | **TD** touchdowns.', '',
          f"**Overall:** n {o['n']} · {o['avg']:.1f} yds/play · {o['succ']:.0%} success · {o['expl']:.0%} explosive · {o['td']} TD", '']

    L += ['## By down & distance', '', '| Situation | n | avg | succ | expl | TD | His top calls (confirmed) | His top formations |',
          '|---|---|---|---|---|---|---|---|']
    for b in BUCKET_ORDER:
        ss = [s for s in rows if s['bucket'] == b]
        if not ss:
            continue
        plays = Counter(s['off_play'] for s in ss if s.get('off_play')).most_common(3)
        forms = Counter(s['formation'] for s in ss if s.get('formation')).most_common(3)
        top_p = ', '.join(f'{p.title()} ({n})' for p, n in plays) or '–'
        top_f = ', '.join(f"{f.replace('Shotgun - ', '')} ({n})" for f, n in forms) or '–'
        L.append(f"| {b} | {fmt(stats(ss))} | {top_p} | {top_f} |")

    L += ['', '## Your coverage vs. his offense', '',
          'Coverage family comes from the panel when shown; otherwise from the three plays you had on screen '
          '(used only when all three are the same family).', '',
          '| Your coverage | n | avg allowed | his success | explosive | TD |', '|---|---|---|---|---|---|']
    fam = defaultdict(list)
    for s in rows:
        if s.get('def_family'):
            fam[s['def_family']].append(s)
    for f, ss in sorted(fam.items(), key=lambda kv: -len(kv[1])):
        L.append(f"| {f} | {fmt(stats(ss))} |")

    L += ['', '### Coverage by situation', '', '| Situation | Coverage | n | avg | succ | expl | TD |', '|---|---|---|---|---|---|---|']
    for b in BUCKET_ORDER:
        bf = defaultdict(list)
        for s in rows:
            if s['bucket'] == b and s.get('def_family'):
                bf[s['def_family']].append(s)
        for f, ss in sorted(bf.items(), key=lambda kv: -len(kv[1])):
            L.append(f"| {b} | {f} | {fmt(stats(ss))} |")

    L += ['', '## His plays (confirmed)', '', '| Play | n | avg | succ | expl | TD | Formations seen |', '|---|---|---|---|---|---|---|']
    by_play = defaultdict(list)
    for s in rows:
        if s.get('off_play'):
            by_play[s['off_play']].append(s)
    for p, ss in sorted(by_play.items(), key=lambda kv: -len(kv[1])):
        forms = sorted({s['formation'] for s in ss if s.get('formation')})
        L.append(f"| {p.title()} | {fmt(stats(ss))} | {', '.join(forms) or '–'} |")

    L += ['', '## His formations', '', '| Formation | n | avg | succ | expl | TD | Plays confirmed from it |', '|---|---|---|---|---|---|---|']
    by_form = defaultdict(list)
    for s in rows:
        if s.get('formation'):
            by_form[s['formation']].append(s)
    for f, ss in sorted(by_form.items(), key=lambda kv: -len(kv[1])):
        L.append(f"| {f} | {fmt(stats(ss))} | {', '.join(p.title() for p in form_plays.get(f, {})) or '–'} |")

    L += ['', '## Biggest plays allowed (15+ yards)', '', '| Game | Time | Situation | Formation | Play | Your call | Yards | Result |',
          '|---|---|---|---|---|---|---|---|']
    for s in sorted((s for s in rows if (s.get('yards') or 0) >= 15), key=lambda s: -s['yards']):
        play = s.get('off_play') or ('guess: ' + ' / '.join(s.get('off_play_guess') or []))
        dc = s.get('def_play') or s.get('def_family') or '–'
        L.append(f"| {s['video_id']} | {s['timestamp']} | {s['down']} & {s['dist']} at {s['ytg']} | {s.get('formation') or '–'} | "
                 f"{play.title()} | {dc.title()} | {s['yards']} | {s['result']} |")
    os.makedirs(opponents.path(opp, 'reports'), exist_ok=True)
    open(opponents.path(opp, 'reports', 'scouting_report.md'), 'w').write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
