#!/usr/bin/env python3
"""Robustness check for the canary classifier.

The published (loose) rule counts a bug report as canary if its text matches
1.3.x-canary or any 1.4.x token. That can be fooled by library versions
(elysia 1.4.x, libavif 1.4.2, WCAG 1.4.3). The strict rule below only accepts
a 1.4.x token that carries canary/debug/a build hash, or sits within 80 chars
of bun/version/revision context. This script prints both classifications side
by side and lists every issue the strict rule drops, for manual inspection."""
import json, re, datetime as dt

MERGE = dt.datetime(2026, 5, 14, 8, 9, 34, tzinfo=dt.timezone.utc)
NOW   = dt.datetime(2026, 8, 10, 12, 0, tzinfo=dt.timezone.utc)
START = MERGE - dt.timedelta(weeks=26)
FEAT  = {'enhancement','docs','idea','question','chore','duplicate','invalid','wontfix'}
P     = lambda s: dt.datetime.fromisoformat(s.replace('Z','+00:00'))

issues = {json.loads(l)['number']: json.loads(l) for l in open('../data/issues.jsonl')}
bodies = {}
for l in open('../data/bodies.jsonl'):
    r = json.loads(l); bodies[r['n']] = r['t'] + '\n' + r['b']

RUST, ZIGCAN = re.compile(r'\b1\.4\.\d+'), re.compile(r'\b1\.3\.\d+-canary')

def strict_rust(t):
    for m in re.finditer(r'\b1\.4\.\d+[-+A-Za-z0-9.]*', t):
        if re.search(r'canary|debug|\+[0-9a-f]{7,}', m.group(0)): return True
        ctx = t[max(0, m.start()-80):m.end()+40].lower()
        if re.search(r'\bbun\b|version|revision|canary|nightly|main\b', ctx): return True
    return False

rows = []
for n, m in issues.items():
    d = P(m['createdAt'])
    if not (START <= d < NOW): continue
    if {x['name'] for x in m['labels']['nodes']} & FEAT: continue
    t = bodies.get(n, '')
    rows.append(dict(n=n, w=int(((d-MERGE).total_seconds()/86400/7)//1),
        fixed=m['state']=='CLOSED' and m['stateReason']=='COMPLETED',
        loose=bool(RUST.search(t) or ZIGCAN.search(t)),
        strict=bool(strict_rust(t) or ZIGCAN.search(t)), t=t))

for name, key in [('loose (published)', 'loose'), ('strict', 'strict')]:
    pre  = [r for r in rows if -26 <= r['w'] <= -1 and r[key]]
    post = [r for r in rows if   0 <= r['w'] <= 11 and r[key]]
    print(f"{name:<18} pre n={len(pre):<4} {len(pre)/26:5.2f}/wk fix={100*sum(r['fixed'] for r in pre)/len(pre):5.1f}%"
          f" | post n={len(post):<4} {len(post)/12:5.2f}/wk fix={100*sum(r['fixed'] for r in post)/len(post):5.1f}%"
          f" | ratio {(len(post)/12)/(len(pre)/26):4.2f}x")

print("\nissues the strict rule drops (inspect the match context):")
for r in rows:
    if r['loose'] and not r['strict']:
        m = RUST.search(r['t']); i = m.start() if m else 0
        ctx = re.sub(r'\s+', ' ', r['t'][max(0, i-60):i+40])
        print(f"  #{r['n']} week {r['w']:>3}: ...{ctx}...")
