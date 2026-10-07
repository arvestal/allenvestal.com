"""Turn per-second OCR of a CFB 26 game recording into a list of snaps.

Inputs (per video, under opponents/<opp>/ocr/<video_id>/, gzipped, produced by extract.sh):
  sb.tsv     OCR of the scoreboard strip, one line per second
  full.tsv   OCR of the whole frame (960px), one line per second
  panel.tsv  OCR of the "PREVIOUS PLAY" panel crop, one line per second

Output: opponents/<opp>/games/<video_id>.json  (see SCHEMA.md)

    python3 scripts/build_plays.py [--opponent jason]   (default: every opponent)
"""
import gzip, json, os, re, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
import scoreboard
import opponents


DEF_SCREEN = re.compile(r'Stunts|D Audibles|Shell -|offense chooses|DEFENSE, ?PICK|DEFENSE AUTO-FLIPPED|COVERAGE ADJUSTMENTS|ZERO BLITZ|SHOW BLITZ', re.I)
# "Flip Play" also appears in the defensive audible menu, so only count play-art tags and offense-only tabs
OFF_SCREEN = re.compile(r'\bPASS\b|\bRUN\b|Personnel|OFFENSE, ?PICK|HOT ROUTE', re.I)
SPECIAL = re.compile(r'Field Goal|Punt|Kickoff|Kick Return|PAT', re.I)
BANNER = re.compile(r'DEFENSE, ?PICK', re.I)
# "1 RB | 3 TE | 1 WR" — the 1s often OCR as T / I / l and the separators as junk letters
PERSONNEL = re.compile(r'([0-9TIl|])\s*RB\D*?([0-9TIl])\s*TE\D*?([0-9TIl])\s*W', re.I)
_one = lambda c: '1' if c in 'TIl|' else c


def tok(line):
    return scoreboard.tokens(line)


def load(path):
    rows = {}
    if not os.path.exists(path):
        return rows
    for line in gzip.open(path, 'rt'):
        f, _, t = line.rstrip('\n').partition('\t')
        rows[int(f[:5]) - 1] = t
    return rows


def clean_name(s):
    s = re.sub(r'\s+', ' ', s.upper()).strip(' .,|')
    return {'CROSS HDIVIDE': 'CROSS H DIVIDE', 'MTN HSTICK': 'MTN H STICK',
            'NICKEL BLITZ O': 'NICKEL BLITZ 0', 'COVER 3 BUZZ MABLE': 'COVER 3 BUZZ MATCH'}.get(s, s)


def panel(line):
    """PREVIOUS PLAY panel -> (defense, offense) using card position (left = defense)."""
    if 'PREVIOUS PLAY' not in line:
        return None
    left, right = [], []
    for x, y, t in tok(line):
        if 0.12 < y < 0.30 and re.search(r'[A-Z]{2}', t):
            (left if x < 0.5 else right).append(t)
    if left and right:
        return clean_name(' '.join(left)), clean_name(' '.join(right))
    return None


def screen(line):
    """Classify the full frame: which play-call screen (if any) and what it shows."""
    info = {}
    d, o = len(DEF_SCREEN.findall(line)), len(OFF_SCREEN.findall(line))
    if d > o:
        info['screen'] = 'DEF'
    elif o > d:
        info['screen'] = 'OFF'
    toks = tok(line)
    if info.get('screen') == 'DEF' and BANNER.search(line):
        # offense formation + personnel sit just below the banner, left half of the screen
        near = [t for x, y, t in toks if 0.15 < x < 0.40 and 0.52 < y < 0.61 and not BANNER.search(t)]
        txt = ' | '.join(near)
        form = [t for t in near if re.search(r'[A-Za-z]{4}', t) and not PERSONNEL.search(t)]
        if form:
            info['formation'] = re.sub(r'\s*-\s*', ' - ', form[0]).strip()
        if (m := PERSONNEL.search(txt.replace('|', ' ').replace('T', 'T'))):
            info['personnel'] = f"{_one(m[1])}RB {_one(m[2])}TE {_one(m[3])}WR"
    if info.get('screen') == 'DEF':
        # the three play tiles: small formation label above an upper-case play name
        tiles = []
        for col in (0.18, 0.50, 0.82):
            hdr = [(y, t) for x, y, t in toks if abs(x - col) < 0.12 and 0.40 < y < 0.46]
            hdr.sort(reverse=True)
            if len(hdr) >= 2:
                tiles.append(f"{hdr[0][1].upper()}: {clean_name(hdr[1][1])}")
        if tiles:
            info['tiles'] = tiles
    return info


def build(opp, vid, meta):
    ocr = opponents.path(opp, 'ocr', vid)
    sb = load(f"{ocr}/sb.tsv.gz")
    full = load(f"{ocr}/full.tsv.gz")
    pan = load(f"{ocr}/panel.tsv.gz")
    n = max(sb) + 1 if sb else 0

    # 1. per-second state, forward-filling quarter / scores
    secs = []
    last = {}
    for s in range(n):
        r = scoreboard.parse(sb.get(s, ''))
        for k in ('qtr', 'score_l', 'score_r'):
            if k in r:
                last[k] = r[k]
            elif k in last:
                r[k] = last[k]
        if r.get('spot') and r.get('down'):
            r['ytg'] = r['spot'] if r['arrow'] == 'up' else 100 - r['spot']
            if r['dist'] == 'G' and r['ytg'] > 20:
                del r['ytg']
        r.update(screen(full.get(s, '')))
        p = panel(pan.get(s, ''))
        if p:
            r['panel'] = p
        secs.append(r)

    # 2. collapse into snaps = runs of identical (down, dist, ytg) lasting >= 2s
    snaps = []
    cur = None
    for s, r in enumerate(secs):
        if 'ytg' not in r:
            continue
        key = (r['down'], r['dist'], r['ytg'], r['poss_side'])
        if cur and cur['key'] == key:
            cur['end'] = s
            cur['secs'].append(s)
        else:
            cur = {'key': key, 'start': s, 'end': s, 'secs': [s]}
            snaps.append(cur)
    snaps = [c for c in snaps if len(c['secs']) >= 3]
    merged = []
    for c in snaps:  # OCR blips can split one state in two
        if merged and merged[-1]['key'] == c['key']:
            merged[-1]['end'] = c['end']; merged[-1]['secs'] += c['secs']
        else:
            merged.append(c)
    snaps = merged

    # drop misread states: an arrow misread mirrors the spot (ytg + ytg' == 100), and the same
    # down & distance can't move the ball without a penalty changing the distance
    def bogus(a, b):
        da, db = a['key'], b['key']
        if da[3] != db[3]:
            return False
        if abs(da[2] + db[2] - 100) <= 1 and abs(da[2] - db[2]) > 10:
            return True
        return da[0] == db[0] and da[0] > 1 and da[1] == db[1] and da[2] != db[2]
    changed = True
    while changed:
        changed = False
        for i in range(1, len(snaps)):
            if bogus(snaps[i - 1], snaps[i]):
                drop = i if len(snaps[i]['secs']) <= len(snaps[i - 1]['secs']) else i - 1
                snaps.pop(drop); changed = True
                break
        merged = []
        for c in snaps:
            if merged and merged[-1]['key'] == c['key']:
                merged[-1]['end'] = c['end']; merged[-1]['secs'] += c['secs']
            else:
                merged.append(c)
        snaps = merged

    # 3. enrich each snap from the seconds it spans
    out = []
    for i, c in enumerate(snaps):
        lo = c['start']
        hi = snaps[i + 1]['start'] if i + 1 < len(snaps) else n
        rng = [secs[s] for s in range(lo, hi)]
        scr = Counter(r['screen'] for r in rng if 'screen' in r)
        down, dist, ytg, side = c['key']
        st = secs[c['start']]
        snap = {
            'video_id': vid,
            't': lo, 'timestamp': f"{lo // 60}:{lo % 60:02d}",
            'qtr': st.get('qtr'), 'clock': next((secs[s]['clock'] for s in c['secs'] if 'clock' in secs[s]), None),
            'down': down, 'dist': dist, 'ytg': ytg,
            'score': list(Counter((secs[x].get('score_l'), secs[x].get('score_r')) for x in c['secs']).most_common(1)[0][0]),
            'screen': scr.most_common(1)[0][0] if scr else None,
            '_side': side,
        }
        # only look at the first play-call screen in the window; later ones are PAT / kickoff screens
        first = next((k for k, r in enumerate(rng) if r.get('screen') == 'DEF'), None)
        block = []
        if first is not None:
            k = first
            while k < len(rng) and (rng[k].get('screen') == 'DEF' or any(rng[j].get('screen') == 'DEF' for j in range(k + 1, min(k + 4, len(rng))))):
                block.append(rng[k]); k += 1
        forms = Counter(r['formation'] for r in block if 'formation' in r)
        if forms:
            snap['off_formation'] = forms.most_common(1)[0][0]
        pers = Counter(r['personnel'] for r in block if 'personnel' in r)
        if pers:
            snap['off_personnel'] = pers.most_common(1)[0][0]
        tiles = [r['tiles'] for r in block if 'tiles' in r]
        if tiles:
            snap['def_candidates'] = tiles[-1]  # last tiles on screen before the snap
        pans = Counter(r['panel'] for r in rng if 'panel' in r)
        if pans:
            snap['_panel'] = pans.most_common(1)[0][0]
            snap['_panel_t'] = next(s for s in range(lo, hi) if secs[s].get('panel') == snap['_panel'])
        out.append(snap)

    # 4. possession: screen type says who is calling; fill gaps within a drive
    for s in out:
        # possession comes from which side of the scoreboard the ball-spot box is on
        s['offense'] = meta['scout_team'] if s.pop('_side') == meta['scout_side'] else meta['user_team']
    def same_drive(a, b):
        half = lambda q: 1 if q in ('1ST', '2ND') else 2
        return (a['score'] == b['score'] and half(a['qtr']) == half(b['qtr']) and b['t'] - a['t'] < 150
                and -20 < a['ytg'] - b['ytg'] < 60)
    for _ in range(3):
        for i, s in enumerate(out):
            if s['offense']:
                continue
            for j in (i - 1, i + 1):
                if 0 <= j < len(out) and out[j]['offense'] and same_drive(*sorted((s, out[j]), key=lambda z: z['t'])):
                    s['offense'] = out[j]['offense']; break

    # 5. result of each snap from the next snap (same offense)
    for i, s in enumerate(out):
        nxt = out[i + 1] if i + 1 < len(out) else None
        s['result'] = None
        if s.get('off_formation') and SPECIAL.search(s['off_formation']):
            s['special_teams'] = True
        if nxt and nxt['offense'] == s['offense'] and same_drive(s, nxt):
            s['yards'] = s['ytg'] - nxt['ytg']
            if nxt['down'] == s['down'] and nxt['dist'] != 10 and nxt['dist'] != 'G' and s['yards'] != 0:
                s['result'] = 'penalty?'
            elif nxt['down'] == 1:
                s['result'] = 'first_down'
            else:
                s['result'] = 'gain' if s['yards'] > 0 else 'no_gain' if s['yards'] == 0 else 'loss'
        elif nxt and None not in nxt['score'] + s['score'] and nxt['score'] != s['score']:
            side = meta['scout_side'] if s['offense'] == meta['scout_team'] else 1 - meta['scout_side']
            delta = (nxt['score'][side] or 0) - (s['score'][side] or 0)
            if delta >= 6:
                s['result'] = 'touchdown'; s['yards'] = s['ytg']
            elif delta == 3:
                s['result'] = 'field_goal'
            elif delta <= 0:
                s['result'] = 'opponent_score'  # pick-six / safety / fumble return
            else:
                s['result'] = 'score'
        elif nxt and s['qtr'] == '2ND' and nxt['qtr'] == '3RD':
            s['result'] = 'end_of_half'
        elif nxt and s['down'] == 4:
            s['result'] = 'fourth_down_change'
        elif nxt:
            s['result'] = 'turnover?'  # ball changed hands before 4th down without a score

    # 6. the PREVIOUS PLAY panel shown during snap k describes snap k-1
    for i, s in enumerate(out):
        if '_panel' in s:
            d, o = s.pop('_panel')
            pt = s.pop('_panel_t')
            if i > 0:
                prev = out[i - 1]
                prev['off_play'], prev['def_play'] = o, d
                prev['play_source'] = 'panel'
                prev['panel_timestamp'] = f"{pt // 60}:{pt % 60:02d}"
    return out


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--opponent')
    for opp in opponents.resolve(ap.parse_args().opponent):
        os.makedirs(opponents.path(opp, 'games'), exist_ok=True)
        for v in opponents.videos(opp):
            snaps = build(opp, v['id'], v)
            json.dump({'video': v, 'snaps': snaps}, open(opponents.path(opp, 'games', f"{v['id']}.json"), 'w'), indent=1)
            print(opp, v['id'], len(snaps), 'snaps')


if __name__ == '__main__':
    main()
