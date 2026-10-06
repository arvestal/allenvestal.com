"""Parse OCR output of the CFB 26 scoreboard strip (crop 1180x110 @ x370,y915 of a 1080p frame).

Each OCR token is "midX,midY@text" with Vision's normalized coords (origin bottom-left).
"""
import re

DOWN_RE = re.compile(r'\b([1-4])\s*(?:st|nd|rd|th)\s*&\s*(Goal|\d{1,2})', re.I)
CLOCK_RE = re.compile(r'^(\d{1,2})[:.](\d{2})$')
QTR_RE = re.compile(r'^(1st|2nd|3rd|4th|OT\d?)$', re.I)
# ball spot: number plus a triangle. The up-triangle (opponent's half) OCRs reliably as "A";
# the down-triangle (own half) comes out as v / y / · or not at all.
SPOT_RE = re.compile(r'^\s*([A^aVvYy·•.]?)\s*(\d{1,2})\s*([A^aVvYy·•.]?)\s*$')


def tokens(line):
    out = []
    for item in line.split(' | '):
        m = re.match(r'([\d.]+),([\d.]+)@(.*)', item)
        if m:
            out.append((float(m[1]), float(m[2]), m[3].strip()))
    return out


def parse(line):
    """Return dict with qtr, clock (sec), down, dist, spot, arrow, poss_side (0=left team, 1=right), score_l, score_r."""
    r = {}
    for x, y, t in tokens(line):
        if t in ('O', 'o') and 0.30 < x < 0.70:
            t = '0'  # a score of zero OCRs as the letter O
        if 'down' not in r and (m := DOWN_RE.search(t.replace('Ist', '1st').replace('lst', '1st'))):
            r['down'] = int(m[1])
            r['dist'] = 'G' if m[2].lower() == 'goal' else int(m[2])
        elif 0.40 < x < 0.46 and 0.45 < y < 0.65 and QTR_RE.match(t):
            r['qtr'] = t.upper()
        elif 0.46 < x < 0.54 and 0.45 < y < 0.65 and (m := CLOCK_RE.match(t)):
            r['clock'] = int(m[1]) * 60 + int(m[2])
        elif (0.38 < x < 0.47 or 0.53 < x < 0.62) and y > 0.68 and (m := SPOT_RE.match(t)):
            # the spot box sits on the side of the team that has the ball
            arrow = (m[1] or m[3] or '')
            if 1 <= int(m[2]) <= 50:
                r['spot'] = int(m[2])
                r['arrow'] = 'up' if arrow in ('A', '^', 'a') and arrow else 'down'
                r['poss_side'] = 0 if x < 0.5 else 1
        elif 0.30 < x < 0.40 and 0.35 < y < 0.65 and t.isdigit() and int(t) < 100:
            r['score_l'] = int(t)
        elif 0.60 < x < 0.70 and 0.35 < y < 0.65 and t.isdigit() and int(t) < 100:
            r['score_r'] = int(t)
    return r
