# part2 — tracking the stable release

Part 1 froze its data on 2026-08-10, while the Rust build still shipped to canary
only. Bun 1.4.0 reached stable users on **2026-08-20**, 98 days after the merge.
This folder re-pulls the tracker on demand and renders a section into the report
page, so the numbers can be refreshed without touching part 1's frozen snapshot.

## Running it

```bash
pnpm run refresh   # fetch, re-derive, re-render — the whole thing (~2 min)
```

That is the only command. It is named `refresh` rather than `update` because
`pnpm update` is a built-in and would shadow a script of that name.

`python3 part2/update.py --no-fetch` re-derives from the cached pull without
touching the network — useful while editing a classifier or the chart code, and
the reason `data/raw.json` is kept.

Both write the `7 — After the stable release` section into `../index.html`,
replacing any previous copy between the `<!-- part2:start -->` and
`<!-- part2:end -->` markers. Re-running is idempotent.

The fetch is unauthenticated, so it is paced at one request every 7 seconds
against the Search API's 10-per-minute limit for anonymous callers. The window is
split into month-sized ranges because a single search query caps at 1,000
results.

## Files

| | |
| --- | --- |
| `update.py` | fetch, classify, derive, inject |
| `block.html` | the section's markup and chart code; `__DATA__`, `__ECHARTS_JS__`, `__UPLOT_JS__` and `__UPLOT_CSS__` are the injection points |
| `echarts.js` | the ECharts components the volume chart uses, bundled by esbuild at injection time |
| `data/issues.jsonl` | one slim record per issue since the merge — committed |
| `data/series.js` | the derived chart payload, also inlined into the page — committed |
| `data/releases.json` | stable tags seen on the Releases API — committed |
| `data/raw.json` | full API response, gitignored cache so `--no-fetch` can re-derive |

Editing a regex in `update.py` and re-running with `--no-fetch` re-derives every
flag from the cached bodies, so a classifier change costs no API calls.

## Charts

Both libraries are inlined into the page at injection time, so `index.html` stays a single file that opens over `file://` with nothing to fetch.

**Volume chart: [ECharts](https://echarts.apache.org/).** `update.py` bundles `echarts.js` with esbuild on every run, about 570 KB against 1.1 MB for the full `echarts.min.js`. The slider under the plot picks a range over a day-level overview. Scrolling over the plot zooms and dragging pans.

**Buckets are calendar units that follow the zoom.** The finest unit with at most 60 buckets in view wins (`MAX_BUCKETS`), counted in calendar buckets, so the full range opens on weeks (22 of them) and zooming steps down to days. Each bucket is a custom-series rect across its own `[start, end)`, because a bar series gives every bar one width. Months run 28 to 31 days, and the first and last buckets are clipped to the data, so a partial bucket is drawn narrower and its tooltip gives the day count. The data encodes x over both ends with `filterMode: 'weakFilter'`, so a bucket that only partly overlaps the view stays in and the y-axis re-fits to what is visible.

**Crash chart: [uPlot](https://github.com/leeoniya/uPlot)** (~50 KB minified). Hovering a line thickens it and dims the rest, while the legend tracks the cursor's date. uPlot has no per-series width on focus, so the thickening is a `setSeries` hook (see `emphasise`). Drag across the plot to zoom, scroll to scale and double-click to reset; the wheel is a small plugin, clamped to the data's extent. The cumulative series is sampled every nth point past 130 days. `setData(rows, false)` keeps the x range but also pins y to the previous sample's magnitude, so the re-sample resets the scales and puts x back by hand.

**Release markers.** On the volume chart they are a `markLine`. ECharts' `hideOverlap` does not reach markLine labels, so a release within 13 px of the last labelled one keeps its rule and loses its tag until a zoom gives it room. On the crash chart they are absolutely-positioned labels over the canvas rather than a plot series, so they stay readable at any width. Close tags stagger across three rows; a release that fits in none goes unlabelled rather than stacking a staircase down over the plot, and zooming in gives it room. Their line-height is pinned to 11px against the 12px row pitch — on the inherited 1.5 line-height the rows overlapped by 2px and the labels smeared together.

Each of those was found by replaying the charts against a synthetic extra year
of data; all of them looked fine on the short window the charts ship with. Worth
re-checking a long range by hand before trusting a change here.

## What differs from part 1

**The canary classifier has a date gate.** Part 1 reads `1.4.0` in an issue body
as "this reporter is on canary", which held while 1.4.0 existed nowhere else.
From 2026-08-20 that string is the stable release, so
`scripts/05-canary-vs-stable.py` re-run over post-August data files stable
reports into the canary bucket. `CANARY` here is only consulted for issues filed
before `RELEASE_140`.

**Crash-class counts are keyword matches, not labels.** The `crash` label is
applied to a small fraction of the issues that describe one, because triage
coverage kept falling — unlabelled share of new issues went from 42.6% in May to
59.7% in August. A label count would measure triage capacity. The keyword proxy
over-counts issues that merely mention the word and under-counts crashes
described without it; both charts caption the limitation.

**Backlog is reconstructed, not sampled.** `created_at` and `closed_at` are in
every record, so open-issue counts for any past date are derived from a single
pull rather than needing a snapshot taken that day.

## Baseline

Pre-merge comparison rows are read from part 1's frozen `../data/*.jsonl`, so the
Zig baseline never moves as this folder is re-run. Release history likewise comes
from `../data/releases.tsv`, extended with whatever the Releases API has added
since.
