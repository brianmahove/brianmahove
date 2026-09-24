"""Generate profile/streak.svg from the GitHub GraphQL contribution calendar.

Usage: GITHUB_TOKEN=... python scripts/streak.py <login> <output.svg>

Standard library only, so the workflow needs no dependency install.
Streaks are counted over the last 12 months, the window GitHub's calendar returns.
"""
import datetime as dt
import json
import os
import sys
import urllib.request

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch_days(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "streak-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload or not payload.get("data", {}).get("user"):
        raise SystemExit(f"GraphQL error: {payload.get('errors') or 'user not found'}")
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [(dt.date.fromisoformat(d["date"]), d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    return sorted(days), cal["totalContributions"]


def streaks(days):
    counts = dict(days)
    today = max(counts)
    # today may not have contributions yet: don't break the streak until the day is over
    cursor = today if counts[today] > 0 else today - dt.timedelta(days=1)
    cur, cur_end = 0, cursor
    while counts.get(cursor, 0) > 0:
        cur += 1
        cursor -= dt.timedelta(days=1)
    cur_start = cur_end - dt.timedelta(days=cur - 1) if cur else None

    best, run, best_range, run_start = 0, 0, None, None
    prev = None
    for day, n in days:
        if n > 0:
            if run and prev == day - dt.timedelta(days=1):
                run += 1
            else:
                run, run_start = 1, day
            if run > best:
                best, best_range = run, (run_start, day)
        else:
            run = 0
        prev = day
    return cur, (cur_start, cur_end if cur else None), best, best_range


def fmt_range(rng):
    if not rng or not rng[0]:
        return "no active streak"
    a, b = rng
    md = lambda d: f"{d.strftime('%b')} {d.day}"
    if a == b:
        return f"{md(a)}, {a.year}"
    if a.year != b.year:
        return f"{md(a)}, {a.year} - {md(b)}, {b.year}"
    return f"{md(a)} - {md(b)}, {b.year}"


def render(total, first, last, cur, cur_rng, best, best_rng):
    green, txt, dim = "#00FFB3", "#e6edf3", "#8b98a9"
    ring = "inline" if cur else "none"
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="495" height="195" viewBox="0 0 495 195" role="img" aria-labelledby="t d">
  <title id="t">GitHub contribution streak</title>
  <desc id="d">{total} contributions in the last year. Current streak {cur} days. Longest streak {best} days.</desc>
  <style>
    text {{ font-family: 'Segoe UI', system-ui, -apple-system, Helvetica, Arial, sans-serif; }}
    .ring {{ stroke-dasharray: 251; stroke-dashoffset: 251; animation: draw 1.4s ease-out forwards; }}
    @keyframes draw {{ to {{ stroke-dashoffset: 0; }} }}
    .flame {{ animation: flick 1.6s ease-in-out infinite; transform-origin: 247px 34px; }}
    @keyframes flick {{ 0%,100% {{ transform: scale(1); }} 50% {{ transform: scale(1.12); }} }}
    @media (prefers-reduced-motion: reduce) {{ .ring {{ animation: none; stroke-dashoffset: 0; }} .flame {{ animation: none; }} }}
  </style>
  <rect x="0.5" y="0.5" width="494" height="194" rx="10" fill="#0D1117" stroke="#26313f"/>
  <line x1="165" y1="30" x2="165" y2="165" stroke="#26313f"/>
  <line x1="330" y1="30" x2="330" y2="165" stroke="#26313f"/>

  <text x="82" y="88" text-anchor="middle" font-size="34" font-weight="800" fill="{txt}">{total}</text>
  <text x="82" y="114" text-anchor="middle" font-size="13" font-weight="600" fill="{green}">Contributions</text>
  <text x="82" y="134" text-anchor="middle" font-size="11" fill="{dim}">{fmt_range((first, last))}</text>

  <circle cx="247" cy="94" r="40" fill="none" stroke="#1f2a37" stroke-width="5"/>
  <circle class="ring" style="display:{ring}" cx="247" cy="94" r="40" fill="none" stroke="{green}" stroke-width="5" stroke-linecap="round" transform="rotate(-90 247 94)"/>
  <path class="flame" d="M247,20 C251,27 258,30 258,39 A11,11 0 0 1 236,39 C236,34 239,32 240,28 C242,31 244,31 245,29 C246,26 246,23 247,20 Z" fill="{green}"/>
  <text x="247" y="104" text-anchor="middle" font-size="30" font-weight="800" fill="{txt}">{cur}</text>
  <text x="247" y="158" text-anchor="middle" font-size="13" font-weight="600" fill="{green}">Current Streak</text>
  <text x="247" y="177" text-anchor="middle" font-size="11" fill="{dim}">{fmt_range(cur_rng)}</text>

  <text x="412" y="88" text-anchor="middle" font-size="34" font-weight="800" fill="{txt}">{best}</text>
  <text x="412" y="114" text-anchor="middle" font-size="13" font-weight="600" fill="{green}">Longest Streak</text>
  <text x="412" y="134" text-anchor="middle" font-size="11" fill="{dim}">{fmt_range(best_rng)}</text>
</svg>
'''


def main():
    login, out = sys.argv[1], sys.argv[2]
    token = os.environ["GITHUB_TOKEN"]
    days, total = fetch_days(login, token)
    cur, cur_rng, best, best_rng = streaks(days)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(total, days[0][0], days[-1][0], cur, cur_rng, best, best_rng))
    print(f"{login}: total={total} current={cur} longest={best} -> {out}")


if __name__ == "__main__":
    main()
