#!/usr/bin/env python3
"""Render assets/stats-dark.svg and assets/stats-light.svg from the GitHub API.

Counts every repository the token can see, private ones included, so the
numbers reflect real work rather than the public contribution graph.

    GH_STATS_TOKEN=<token> python3 scripts/generate_stats.py

Only the standard library is used.
"""
import datetime as dt
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

TOKEN = os.environ.get("GH_STATS_TOKEN") or os.environ.get("GITHUB_TOKEN")
API = "https://api.github.com"
ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

LANG_COLORS = {  # GitHub linguist colours
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "CSS": "#663399",
    "SCSS": "#c6538c",
    "Pug": "#a86454",
    "Python": "#3572A5",
}

THEMES = {
    "dark": dict(bg="#0d1117", border="#30363d", text="#e6edf3", muted="#8b949e",
                 tile="#161b22", a1="#7aa2f7", a2="#bb9af7", other="#484f58"),
    "light": dict(bg="#ffffff", border="#d0d7de", text="#1f2328", muted="#656d76",
                  tile="#f6f8fa", a1="#0969da", a2="#8250df", other="#afb8c1"),
}


def get(path, params=None):
    if not TOKEN:
        sys.exit("GH_STATS_TOKEN (or GITHUB_TOKEN) is required")
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-stats",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r), r.headers


def paginate(path, params):
    page, out = 1, []
    while True:
        data, _ = get(path, dict(params, per_page=100, page=page))
        out += data
        if len(data) < 100:
            return out
        page += 1


def count_commits(full_name, since=None, until=None):
    params = {"per_page": 1}
    if since:
        params["since"] = since
    if until:
        params["until"] = until
    try:
        data, headers = get(f"/repos/{full_name}/commits", params)
    except urllib.error.HTTPError as e:
        if e.code in (409, 404):  # empty repository
            return 0
        raise
    m = re.search(r'page=(\d+)>; rel="last"', headers.get("Link", ""))
    return int(m.group(1)) if m else len(data)


def collect():
    me, _ = get("/user")
    repos = [r for r in paginate("/user/repos", {"affiliation": "owner"}) if not r["fork"]]
    since_year = int(me["created_at"][:4])
    this_year = dt.date.today().year
    years = list(range(since_year, this_year + 1))

    total = 0
    by_year = {y: 0 for y in years}
    langs = {}
    deployments = 0
    for r in repos:
        name = r["full_name"]
        total += count_commits(name)
        for y in years:
            by_year[y] += count_commits(name, f"{y}-01-01T00:00:00Z", f"{y}-12-31T23:59:59Z")
        if r.get("homepage"):
            deployments += 1
        data, _ = get(f"/repos/{name}/languages")
        for k, v in data.items():
            langs[k] = langs.get(k, 0) + v

    # Drop leading years with no commits so the chart starts where the work starts.
    while len(by_year) > 1 and by_year[min(by_year)] == 0:
        by_year.pop(min(by_year))

    return {
        "generated": dt.date.today().isoformat(),
        "since": since_year,
        "repos": len(repos),
        "private_repos": sum(1 for r in repos if r["private"]),
        "commits": total,
        "deployments": deployments,
        "commits_by_year": by_year,
        "languages": dict(sorted(langs.items(), key=lambda kv: -kv[1])),
    }


def fmt(n):
    return f"{n:,}"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(stats, theme):
    t = THEMES[theme]
    W, PAD = 900, 28
    lines = []
    add = lines.append

    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="312" viewBox="0 0 {W} 312" role="img" aria-label="GitHub statistics for Jad Ayoubi">')
    add(f'''<style>
  text {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-variant-numeric: tabular-nums; }}
  .title {{ font-size: 12px; font-weight: 700; letter-spacing: 2px; fill: {t["muted"]}; }}
  .meta {{ font-size: 11px; fill: {t["muted"]}; }}
  .num {{ font-size: 36px; font-weight: 800; fill: {t["text"]}; }}
  .lbl {{ font-size: 12px; font-weight: 600; fill: {t["muted"]}; letter-spacing: .3px; }}
  .sec {{ font-size: 12px; font-weight: 700; fill: {t["text"]}; }}
  .leg {{ font-size: 11px; fill: {t["muted"]}; }}
  .yr  {{ font-size: 12px; font-weight: 600; fill: {t["muted"]}; }}
  .val {{ font-size: 12px; font-weight: 700; fill: {t["text"]}; }}
  .grow {{ transform-box: fill-box; transform-origin: left center; animation: grow 900ms cubic-bezier(.2,.8,.2,1) both; }}
  @keyframes grow {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
  @media (prefers-reduced-motion: reduce) {{ .grow {{ animation: none; }} }}
</style>''')
    add(f'''<defs>
  <linearGradient id="acc" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="{t["a1"]}"/><stop offset="1" stop-color="{t["a2"]}"/></linearGradient>
  <clipPath id="bar"><rect x="{PAD}" y="182" width="{W - 2 * PAD}" height="10" rx="5"/></clipPath>
</defs>''')
    add(f'<rect x="0.5" y="0.5" width="{W - 1}" height="311" rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>')
    add(f'<rect x="{PAD}" y="{PAD}" width="42" height="3" rx="1.5" fill="url(#acc)"/>')
    add(f'<text x="{PAD}" y="{PAD + 22}" class="title">BY THE NUMBERS</text>')
    add(f'<text x="{W - PAD}" y="{PAD + 22}" text-anchor="end" class="meta">every repo, private included · updated {esc(stats["generated"])}</text>')

    tiles = [
        (fmt(stats["repos"]), "REPOSITORIES"),
        (fmt(stats["commits"]), "COMMITS"),
        (fmt(stats["deployments"]), "LIVE DEPLOYMENTS"),
        (str(stats["since"]), "ON GITHUB SINCE"),
    ]
    tw = (W - 2 * PAD) / len(tiles)
    for i, (num, lbl) in enumerate(tiles):
        x = PAD + i * tw
        add(f'<text x="{x:.0f}" y="112" class="num">{esc(num)}</text>')
        add(f'<text x="{x:.0f}" y="134" class="lbl">{esc(lbl)}</text>')

    # Language bar
    add(f'<text x="{PAD}" y="170" class="sec">Languages</text>')
    langs = stats["languages"]
    tot = sum(langs.values()) or 1
    top = [(k, v) for k, v in langs.items() if v / tot >= 0.02][:5]
    other = tot - sum(v for _, v in top)
    segs = [(k, v / tot, LANG_COLORS.get(k, t["a1"])) for k, v in top]
    if other > 0:
        segs.append(("Other", other / tot, t["other"]))
    x = PAD
    bw = W - 2 * PAD
    add('<g clip-path="url(#bar)">')
    for i, (name, share, colour) in enumerate(segs):
        w = bw * share
        add(f'<rect class="grow" style="animation-delay:{60 * i + 300}ms" x="{x:.1f}" y="182" width="{w:.1f}" height="10" fill="{colour}"/>')
        x += w
    add('</g>')
    x = PAD
    for name, share, colour in segs:
        add(f'<circle cx="{x + 5}" cy="209" r="5" fill="{colour}"/>')
        label = f"{name} {share * 100:.0f}%"
        add(f'<text x="{x + 15}" y="213" class="leg">{esc(label)}</text>')
        x += 15 + 6.6 * len(label) + 18

    # Commits per year
    add(f'<text x="{PAD}" y="249" class="sec">Commits per year</text>')
    by_year = stats["commits_by_year"]
    ymax = max(by_year.values()) or 1
    n = len(by_year)
    gap = 18
    col_w = (W - 2 * PAD - gap * (n - 1)) / n
    x = PAD
    for i, (year, count) in enumerate(sorted(by_year.items())):
        w = max(6, (col_w - 40 - 48) * count / ymax)
        add(f'<text x="{x:.0f}" y="277" class="yr">{year}</text>')
        add(f'<rect class="grow" style="animation-delay:{100 * i + 500}ms" x="{x + 40:.0f}" y="267" width="{w:.1f}" height="12" rx="6" fill="url(#acc)"/>')
        add(f'<text x="{x + 40 + w + 8:.0f}" y="277" class="val">{fmt(count)}</text>')
        x += col_w + gap

    add('</svg>')
    return "\n".join(lines) + "\n"


def main():
    ASSETS.mkdir(exist_ok=True)
    if "--from-json" in sys.argv:
        stats = json.loads((ASSETS / "stats.json").read_text())
    else:
        stats = collect()
        (ASSETS / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    for theme in THEMES:
        (ASSETS / f"stats-{theme}.svg").write_text(render(stats, theme))
    print(json.dumps({k: v for k, v in stats.items() if k != "languages"}))


if __name__ == "__main__":
    main()
