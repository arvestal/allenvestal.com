"""Render each opponent's reports/*.md to styled HTML pages, plus a root index.html.

    python3 scripts/render_html.py

The Markdown files stay the source (easy to edit and diff); the HTML is what you open. Handles the Markdown subset
the reports use: headings, paragraphs, bullet and numbered lists, tables, **bold**, *italic*, `code`, [links](url).
Tables are sortable (click a header). Percent / yards columns get a red tint: redder = better for the offense.
"""
import glob, html, os, re, sys

sys.path.insert(0, os.path.dirname(__file__))
import opponents

ROOT = opponents.ROOT

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2330;--muted:#5d6676;--line:#e2e5ea;--accent:#8c1515;--head:#f0f2f5;--heat:200,40,40}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--card:#1c2027;--ink:#e6e8eb;--muted:#9aa3b2;--line:#2c323c;--accent:#e0656a;--head:#232831;--heat:230,80,80}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 20px 64px}
nav{font-size:13px;color:var(--muted);margin-bottom:8px}
nav a{color:var(--muted)}
h1{font-size:26px;margin:4px 0 16px;letter-spacing:-.01em}
h2{font-size:19px;margin:36px 0 10px;padding-bottom:6px;border-bottom:2px solid var(--accent)}
h3{font-size:16px;margin:24px 0 8px}
p,li{max-width:80ch}
a{color:var(--accent)}
code{background:var(--head);padding:1px 5px;border-radius:4px;font-size:.9em}
.tbl{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px;margin:12px 0 20px}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:7px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--head);position:sticky;top:0;cursor:pointer;user-select:none;white-space:nowrap;font-weight:600}
th:hover{color:var(--accent)}
th.asc::after{content:" ▲";font-size:10px}th.desc::after{content:" ▼";font-size:10px}
tr:last-child td{border-bottom:none}
tbody tr:hover td{background:rgba(127,127,127,.06)}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.nowrap{white-space:nowrap}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;margin-top:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
.card h3{margin:0 0 4px}.card p{margin:4px 0;color:var(--muted);font-size:13.5px}
.card a.btn{display:inline-block;margin:10px 10px 0 0;font-weight:600}
"""

JS = """
document.querySelectorAll('table').forEach(t=>{
  t.querySelectorAll('th').forEach((th,i)=>th.addEventListener('click',()=>{
    const asc=!th.classList.contains('asc');
    t.querySelectorAll('th').forEach(h=>h.classList.remove('asc','desc'));
    th.classList.add(asc?'asc':'desc');
    const key=td=>{const s=td.textContent.trim().replace('%','').replace('–','');const n=parseFloat(s);return isNaN(n)?s.toLowerCase():n};
    const rows=[...t.tBodies[0].rows];
    rows.sort((a,b)=>{const x=key(a.cells[i]),y=key(b.cells[i]);return (x>y?1:x<y?-1:0)*(asc?1:-1)});
    rows.forEach(r=>t.tBodies[0].appendChild(r));
  }));
});
"""

# columns whose cells should never wrap
NOWRAP = re.compile(r'^\**(personnel)\**$', re.I)
# columns that stay left-aligned even when a cell is just a number (mixed "11%" / "19% (his #1)" cells)
LEFT = re.compile(r'^\**(how often)\**$', re.I)

# columns where a higher number is better for the offense (worse for me) -> tint
HEAT = re.compile(r'^(avg|avg allowed|succ|his success|expl|explosive|yards)$', re.I)


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<![*\w])\*([^*]+)\*(?!\*)', r'<em>\1</em>', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: f'<a href="{m[2].replace(".md", ".html")}">{m[1]}</a>', s)
    return s


def heat(col, text):
    t = text.strip()
    m = re.match(r'^(-?\d+(?:\.\d+)?)(%?)$', t)
    if not m or not HEAT.match(col.strip()):
        return ''
    v = float(m[1])
    frac = v / 100 if m[2] else max(0.0, min(1.0, v / 20))  # yards: 20+ = full tint
    return f' style="background:rgba(var(--heat),{0.04 + 0.30 * max(0.0, min(1.0, frac)):.2f})"'


def table(lines):
    rows = [[c.strip() for c in l.strip().strip('|').split('|')] for l in lines]
    head, body = rows[0], [r for r in rows[2:]]
    out = ['<div class="tbl"><table><thead><tr>' + ''.join(f'<th>{inline(h)}</th>' for h in head) + '</tr></thead><tbody>']
    for r in body:
        cells = []
        for i, c in enumerate(r):
            col = head[i] if i < len(head) else ''
            num = re.match(r'^-?[\d.]+%?$|^–$', c.strip()) and not LEFT.match(col.strip())
            cls = ' class="num"' if num else ' class="nowrap"' if NOWRAP.match(col.strip()) else ''
            cells.append(f'<td{cls}{heat(head[i] if i < len(head) else "", c)}>{inline(c)}</td>')
        out.append('<tr>' + ''.join(cells) + '</tr>')
    out.append('</tbody></table></div>')
    return '\n'.join(out)


def md_to_html(md):
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        l = lines[i]
        if l.startswith('|'):
            block = []
            while i < len(lines) and lines[i].startswith('|'):
                block.append(lines[i]); i += 1
            out.append(table(block)); continue
        if m := re.match(r'^(#{1,3}) (.*)', l):
            n = len(m[1]); out.append(f'<h{n}>{inline(m[2])}</h{n}>')
        elif re.match(r'^\s*[-*] ', l):
            items = []  # (level, text); a bullet indented 2+ spaces is a sub-item
            while i < len(lines) and re.match(r'^\s*[-*] |^\s{2,}\S', lines[i]):
                if m2 := re.match(r'^(\s*)[-*] (.*)', lines[i]):
                    items.append([1 if len(m2[1]) >= 2 else 0, m2[2]])
                else:
                    items[-1][1] += ' ' + lines[i].strip()
                i += 1
            h, open_sub = ['<ul>'], False
            for lvl, txt in items:
                if lvl and not open_sub:
                    h[-1] = h[-1][:-5] if h[-1].endswith('</li>') else h[-1]
                    h.append('<ul>'); open_sub = True
                elif not lvl and open_sub:
                    h.append('</ul></li>'); open_sub = False
                h.append(f'<li>{inline(txt)}</li>' if lvl else f'<li>{inline(txt)}</li>')
            if open_sub:
                h.append('</ul></li>')
            h.append('</ul>')
            out.append(''.join(h)); continue
        elif re.match(r'^\d+\. ', l):
            items = []
            while i < len(lines) and re.match(r'^\d+\. ', lines[i]):
                items.append(re.sub(r'^\d+\. ', '', lines[i])); i += 1
            out.append('<ol>' + ''.join(f'<li>{inline(x)}</li>' for x in items) + '</ol>'); continue
        elif l.strip():
            para = [l]
            while i + 1 < len(lines) and lines[i + 1].strip() and not re.match(r'^(#|\||\s*[-*] |\d+\. )', lines[i + 1]):
                i += 1; para.append(lines[i])
            out.append(f'<p>{inline(" ".join(para))}</p>')
        i += 1
    return '\n'.join(out)


def page(title, body, crumbs):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{CSS}</style></head><body><main><nav>{crumbs}</nav>{body}</main>'
            f'<script>{JS}</script></body></html>')


def main():
    cards = []
    for opp in opponents.all_ids():
        prof = opponents.profile(opp)
        who = f"{prof['player']} ({' / '.join(prof['teams'])})"
        rep = opponents.path(opp, 'reports')
        pages = []
        for md in sorted(glob.glob(os.path.join(rep, '*.md'))):
            name = os.path.splitext(os.path.basename(md))[0]
            body = md_to_html(open(md).read())
            title = re.search(r'<h1>(.*?)</h1>', body)
            other = ' · '.join(f'<a href="{n}.html">{n.replace("_", " ")}</a>'
                               for n in ('gameplan', 'scouting_report') if n != name and os.path.exists(os.path.join(rep, n + '.md')))
            crumbs = f'<a href="../../../index.html">All opponents</a> › {html.escape(who)}' + (f' › {other}' if other else '')
            open(os.path.join(rep, name + '.html'), 'w').write(page(re.sub('<[^>]+>', '', title[1]) if title else name, body, crumbs))
            pages.append(name)
        vids = opponents.videos(opp)
        links = ''.join(f'<a class="btn" href="opponents/{opp}/reports/{n}.html">{"Game plan" if n == "gameplan" else "Scouting report"}</a>'
                        for n in ('gameplan', 'scouting_report') if n in pages)
        cards.append(f'<div class="card"><h3>{html.escape(who)}</h3><p>{len(vids)} game{"s" if len(vids) != 1 else ""} scouted'
                     f'{" · last " + max(v["date"] for v in vids) if vids else ""}</p>{links or "<p>No reports yet</p>"}</div>')
    idx = page('CF26 scouting', '<h1>CF26 scouting</h1><p>Open an opponent\'s <strong>game plan</strong> before you play them; '
               'the scouting report has the numbers behind it.</p><div class="cards">' + ''.join(cards) + '</div>', 'cf26-scouting')
    open(os.path.join(ROOT, 'index.html'), 'w').write(idx)
    print('wrote index.html and', ', '.join(f'opponents/{o}/reports/*.html' for o in opponents.all_ids()))


if __name__ == '__main__':
    main()
