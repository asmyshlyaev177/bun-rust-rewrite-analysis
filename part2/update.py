#!/usr/bin/env python3
"""Refresh the post-1.4.0 tracking data and rebuild the chart payload.

    python3 update.py              # fetch from GitHub, then rebuild
    python3 update.py --no-fetch   # rebuild from the cached raw pull

Writes data/issues.jsonl (committed, one slim record per issue),
data/series.js (committed, the chart payload) and data/raw.json
(gitignored cache of the full API response).
"""
import argparse, collections, datetime as dt, json, re, statistics as st, sys, time, urllib.request
from pathlib import Path

MERGE = dt.datetime(2026, 5, 14, 8, 9, 34, tzinfo=dt.timezone.utc)
RELEASE_140 = dt.datetime(2026, 8, 20, 14, 7, 21, tzinfo=dt.timezone.utc)
BASELINE_WEEKS = 26

DATA = Path(__file__).parent / "data"
RAW = DATA / "raw.json"
SLIM = DATA / "issues.jsonl"
SERIES = DATA / "series.js"
RELEASES_CACHE = DATA / "releases.json"
BLOCK = Path(__file__).parent / "block.html"
VENDOR = Path(__file__).parent.parent / "node_modules" / "uplot" / "dist"
PAGE = Path(__file__).parent.parent / "index.html"
START = "<!-- part2:start -->"
END = "<!-- part2:end -->"
FROZEN = Path(__file__).parent.parent / "data"

# Labels that mark an issue as something other than a defect report.
NON_BUG = {"enhancement", "docs", "idea", "question", "chore", "duplicate", "invalid", "wontfix"}

# 1.4.0 was canary-only until it shipped as stable on 2026-08-20; from that date
# the string no longer identifies the channel, so CANARY is only meaningful for
# issues filed before RELEASE_140. Part 1's script has no such date gate.
CANARY = re.compile(r"\b\d+\.\d+\.\d+-canary|\b1\.4\.0[-.\d]*\b")
V14 = re.compile(r"\b1\.4\.\d+")
V13 = re.compile(r"\b1\.3\.\d+(?![-.\w]*canary)")

KEYWORDS = {
    "panic": r"\bpanic",
    "segfault": r"segfault|SIGSEGV|signal 11|access violation",
    "crash": r"\bcrash",
    "memory": r"out of memory|OOM|memory leak|heap",
    "hang": r"\bhang|deadlock|freeze|infinite loop",
    "install": r"bun upgrade|bun install|installation",
}
KEYWORDS = {k: re.compile(v, re.I) for k, v in KEYWORDS.items()}

parse = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None


def fetch(until):
    """Page the search API for every issue filed since the merge.

    Search caps a single query at 1000 results, so the window is split into
    month-sized ranges; unauthenticated search allows 10 requests a minute.
    """
    def get(url):
        for attempt in range(6):
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "bun-rust-rewrite-analysis",
                    "Accept": "application/vnd.github+json"})
                with urllib.request.urlopen(req) as r:
                    return json.load(r)
            except Exception as e:
                print(f"  retry {attempt}: {e}", file=sys.stderr)
                time.sleep(20)
        raise SystemExit(f"gave up on {url}")

    out = {}
    for start, end in month_ranges(MERGE.date(), until):
        for page in range(1, 11):
            url = ("https://api.github.com/search/issues?q=repo:oven-sh/bun+type:issue"
                   f"+created:{start}..{end}&per_page=100&page={page}&sort=created&order=desc")
            payload = get(url)
            items = payload.get("items", [])
            for it in items:
                out[it["number"]] = it
            print(f"  {start}..{end} page {page}: {len(items)} of {payload.get('total_count')}",
                  file=sys.stderr)
            time.sleep(7)
            if len(items) < 100:
                break
    RAW.write_text(json.dumps(list(out.values())))
    return list(out.values())


def month_ranges(start, end):
    cur = start
    while cur <= end:
        last = (cur.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
        yield cur.isoformat(), min(last, end).isoformat()
        cur = last + dt.timedelta(days=1)


def slim(raw):
    rows = []
    for it in raw:
        text = f"{it.get('title') or ''}\n{it.get('body') or ''}"
        labels = sorted(l["name"] for l in it.get("labels", []))
        rows.append({
            "n": it["number"],
            "created": it["created_at"],
            "closed": it.get("closed_at"),
            "fixed": it["state"] == "closed" and it.get("state_reason") == "completed",
            "labels": labels,
            "bug": not (set(labels) & NON_BUG),
            "canary": bool(CANARY.search(text)),
            "v14": bool(V14.search(text)),
            "v13": bool(V13.search(text)),
            "kw": sorted(k for k, pat in KEYWORDS.items() if pat.search(text)),
            "title": it.get("title") or "",
        })
    rows.sort(key=lambda r: r["created"])
    SLIM.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
    return rows


def baseline():
    """Pre-merge comparison rows, read from part 1's frozen pull."""
    bodies = {}
    for line in (FROZEN / "bodies.jsonl").open():
        r = json.loads(line)
        bodies[r["n"]] = r["t"] + "\n" + r["b"]
    start = MERGE - dt.timedelta(weeks=BASELINE_WEEKS)
    rows = []
    for line in (FROZEN / "issues.jsonl").open():
        m = json.loads(line)
        created = parse(m["createdAt"])
        if not (start <= created < MERGE) or m["number"] not in bodies:
            continue
        labels = {x["name"] for x in m["labels"]["nodes"]}
        rows.append({
            "created": m["createdAt"],
            "closed": m["closedAt"],
            "bug": not (labels & NON_BUG),
            "fixed": m["state"] == "CLOSED" and m["stateReason"] == "COMPLETED",
            "canary": bool(CANARY.search(bodies[m["number"]])),
        })
    return rows


def releases():
    """Stable tags from part 1's frozen list, plus everything pulled since."""
    out = []
    for line in (FROZEN / "releases.tsv").open():
        date, tag, prerelease = line.rstrip("\n").split("\t")
        if prerelease == "false" and date >= "2025-11-13":
            out.append([date, tag.replace("bun-v", "")])
    known = {t for _, t in out}
    recent = json.loads(RELEASES_CACHE.read_text()) if RELEASES_CACHE.exists() else []
    out += [r for r in recent if r[1] not in known]
    return sorted(out)


def pull_releases():
    req = urllib.request.Request(
        "https://api.github.com/repos/oven-sh/bun/releases?per_page=40",
        headers={"User-Agent": "bun-rust-rewrite-analysis"})
    with urllib.request.urlopen(req) as r:
        data = json.load(r)
    out = [[x["published_at"][:10], x["tag_name"].replace("bun-v", "")]
           for x in data if not x["prerelease"]]
    RELEASES_CACHE.write_text(json.dumps(sorted(out)))
    return out


def series(rows, now):
    """Everything the chart page draws, derived from the slim records."""
    days = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        d = r["created"][:10]
        days[d]["all"] += 1
        days[d]["v14"] += r["v14"]
        days[d]["bug"] += r["bug"]

    # Backlog is reconstructed from created/closed timestamps, so a single pull
    # yields the whole history rather than only the moment it was taken.
    first = min(days)
    span = [(dt.date.fromisoformat(first) + dt.timedelta(days=i)).isoformat()
            for i in range((now.date() - dt.date.fromisoformat(first)).days + 1)]
    opened = collections.Counter(r["created"][:10] for r in rows)
    closed = collections.Counter(r["closed"][:10] for r in rows if r["closed"])
    backlog, running = [], 0
    for d in span:
        running += opened[d] - closed[d]
        backlog.append({"d": d, "open": running, "in": opened[d], "out": closed[d]})

    months = collections.defaultdict(lambda: {"n": 0, "unlabeled": 0, "bugs": 0, "fixed": 0})
    for r in rows:
        m = months[r["created"][:7]]
        m["n"] += 1
        m["unlabeled"] += not r["labels"]
        if r["bug"]:
            m["bugs"] += 1
            m["fixed"] += r["fixed"]

    since = [r for r in rows if parse(r["created"]) >= RELEASE_140]

    # Crash-class counts run cumulatively by date so the chart shows the rate of
    # arrival, not just the total.
    per_day = collections.defaultdict(collections.Counter)
    for r in since:
        per_day[r["created"][:10]].update(r["kw"])
        per_day[r["created"][:10]]["issues"] += 1
    kw_cum, running = [], collections.Counter()
    for d in sorted(per_day):
        running.update(per_day[d])
        kw_cum.append({"d": d, "issues": running["issues"],
                       **{k: running[k] for k in KEYWORDS}})

    totals = {
        "since_merge": len(rows),
        "bugs_since_merge": sum(r["bug"] for r in rows),
        "since_140": len(since),
        "bugs_since_140": sum(r["bug"] for r in since),
        "kw_since_140": {k: sum(k in r["kw"] for r in since) for k in KEYWORDS},
        "kw_since_merge": {k: sum(k in r["kw"] for r in rows) for k in KEYWORDS},
        "crash_labelled": sum("crash" in r["labels"] for r in since),
        "open_now": sum(1 for r in rows if not r["closed"]),
        "open_since_140": sum(1 for r in since if not r["closed"]),
    }

    pre = baseline()
    cohorts = {
        "pre": summarize([r for r in pre if r["bug"]]),
        "pre_canary": summarize([r for r in pre if r["bug"] and r["canary"]]),
        "post": summarize([r for r in rows if r["bug"]]),
        "post_pre140": summarize([r for r in rows if r["bug"] and parse(r["created"]) < RELEASE_140]),
        "post_140": summarize([r for r in since if r["bug"]]),
    }
    return {
        "generated": now.isoformat(timespec="seconds"),
        "merge": MERGE.isoformat(timespec="seconds"),
        "release140": RELEASE_140.isoformat(timespec="seconds"),
        "daily": [{"d": d, **days[d]} for d in sorted(days)],
        "backlog": backlog,
        "months": [{"m": m, **months[m]} for m in sorted(months)],
        "keywords": kw_cum,
        "keywordNames": list(KEYWORDS),
        "totals": totals,
        "cohorts": cohorts,
        "releases": releases(),
    }


def summarize(group):
    if not group:
        return {"n": 0}
    fixed = sum(r["fixed"] for r in group)
    times = [(parse(r["closed"]) - parse(r["created"])).total_seconds() / 86400
             for r in group if r.get("closed") and r["fixed"]]
    return {"n": len(group), "fixed": fixed, "rate": round(100 * fixed / len(group), 1),
            "median_days": round(st.median(times), 1) if times else None}


def report(payload):
    c = payload["cohorts"]
    print(f"\ngenerated {payload['generated']}")
    for key, label in [("pre", "pre-merge bugs (26 wk)"), ("post", "post-merge bugs"),
                       ("post_pre140", "  before 1.4.0 stable"), ("post_140", "  since 1.4.0 stable")]:
        s = c[key]
        print(f"  {label:<26} n={s['n']:<5} fixed {s['fixed']:<4} {s['rate']:5.1f}%  median {s['median_days']}d")
    print("\n  month     issues  unlabeled   bugs  fixed")
    for m in payload["months"]:
        print(f"  {m['m']}   {m['n']:>5}  {100*m['unlabeled']/m['n']:8.1f}%  {m['bugs']:>5}  "
              f"{100*m['fixed']/m['bugs'] if m['bugs'] else 0:5.1f}%")
    last = payload["backlog"][-1]
    print(f"\n  open backlog (post-merge cohort): {last['open']}")


def inject(payload):
    """Splice the rendered section into the report page, replacing any prior copy."""
    js, css = VENDOR / "uPlot.iife.min.js", VENDOR / "uPlot.min.css"
    if not js.exists():
        raise SystemExit("uplot is missing — run `pnpm install` in the repo root first")
    block = (BLOCK.read_text()
             .replace("__UPLOT_JS__", js.read_text())
             .replace("__UPLOT_CSS__", css.read_text())
             .replace("__DATA__", json.dumps(payload, separators=(",", ":"))))
    section = f"{START}\n{block}{END}\n"
    page = PAGE.read_text()
    if START in page:
        head, rest = page.split(START, 1)
        page = head + section + rest.split(END, 1)[1].lstrip("\n")
    else:
        # Ahead of the method section, so the update reads before the caveats.
        anchor = "<section>\n  <details>"
        assert anchor in page, "method section not found in index.html"
        page = page.replace(anchor, section + "\n" + anchor, 1)
    PAGE.write_text(page)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fetch", action="store_true", help="rebuild from data/raw.json")
    args = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)

    if args.no_fetch:
        raw = json.loads(RAW.read_text())
    else:
        print("fetching issues...", file=sys.stderr)
        raw = fetch(now.date())
        pull_releases()

    rows = slim(raw)
    payload = series(rows, now)
    SERIES.write_text("const S = " + json.dumps(payload, separators=(",", ":")) + ";\n")
    inject(payload)
    report(payload)
    print(f"\nwrote {SLIM.name} ({len(rows)} issues), {SERIES.name}, and the section in {PAGE.name}")


if __name__ == "__main__":
    main()
