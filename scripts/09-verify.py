#!/usr/bin/env python3
"""Independent re-derivation of every headline figure, written separately from
scripts 03-08. Asserts against the published numbers; exits non-zero on drift."""
import json, re, sys, collections, datetime as dt

MERGE = dt.datetime(2026, 5, 14, 8, 9, 34, tzinfo=dt.timezone.utc)
NOW   = dt.datetime(2026, 8, 10, 12, 0, tzinfo=dt.timezone.utc)
START = MERGE - dt.timedelta(weeks=26)
FEAT  = {'enhancement','docs','idea','question','chore','duplicate','invalid','wontfix'}
P     = lambda s: dt.datetime.fromisoformat(s.replace('Z','+00:00'))

issues = {}
for line in open('../data/issues.jsonl'):
    r = json.loads(line); issues[r['number']] = r
bodies = {}
for line in open('../data/bodies.jsonl'):
    r = json.loads(line); bodies[r['n']] = r['t'] + '\n' + r['b']

RUST, ZIGCAN = re.compile(r'\b1\.4\.\d+'), re.compile(r'\b1\.3\.\d+-canary')
STA = re.compile(r'\b1\.3\.\d+(?![-.\w]*canary)')

rows = []
for n, m in issues.items():
    d = P(m['createdAt'])
    if not (START <= d < NOW): continue
    lab = {x['name'] for x in m['labels']['nodes']}
    fixed = m['state'] == 'CLOSED' and m['stateReason'] == 'COMPLETED'
    ttc = (P(m['closedAt']) - d).total_seconds()/86400 if m['closedAt'] else None
    t = bodies.get(n, '')
    rows.append(dict(n=n, d=d, w=int(((d-MERGE).total_seconds()/86400/7)//1),
        bug=not (lab & FEAT), fixed=fixed, ttc=ttc,
        bot=(m['author'] or {}).get('login')=='robobun', unlab=not lab,
        can=bool(RUST.search(t) or ZIGCAN.search(t)),
        sta=bool(STA.search(t)), reopened=m['stateReason']=='REOPENED'))

PRE  = [r for r in rows if -26 <= r['w'] <= -1]
POST = [r for r in rows if   0 <= r['w'] <= 11]
def wk(g, n): return len(g)/n
def med(xs):
    xs = sorted(xs); k = len(xs)
    return (xs[k//2] if k % 2 else (xs[k//2-1]+xs[k//2])/2) if xs else float('nan')

checks, fail = [], 0
def ck(name, got, want, tol=0.051):
    global fail
    ok = abs(got - want) <= tol
    checks.append((name, got, want, ok)); fail += (not ok)

ck('issues in window',            len(rows), 2981, 0)
ck('all issues/wk pre',           wk(PRE,26), 79.1)
ck('all issues/wk post',          wk(POST,12), 74.0)
preB  = [r for r in PRE  if r['bug']]; postB = [r for r in POST if r['bug']]
ck('bug reports pre (n)',         len(preB), 1802, 0)
ck('bug reports post (n)',        len(postB), 827, 0)
ck('bug/wk pre',                  wk(preB,26), 69.31)
ck('bug/wk post',                 wk(postB,12), 68.92)
ck('bug fix rate pre %',          100*sum(r['fixed'] for r in preB)/len(preB), 40.8)
ck('bug fix rate post %',         100*sum(r['fixed'] for r in postB)/len(postB), 39.7)
ck('bug fixed/wk pre',            sum(r['fixed'] for r in preB)/26, 28.3)
ck('bug fixed/wk post',           sum(r['fixed'] for r in postB)/12, 27.3)
ck('median ttfix pre (d)',        med([r['ttc'] for r in preB  if r['fixed']]), 2.7, 0.25)
ck('median ttfix post (d)',       med([r['ttc'] for r in postB if r['fixed']]), 3.2, 0.25)
preC  = [r for r in preB  if r['can']]; postC = [r for r in postB if r['can']]
ck('canary pre (n)',              len(preC), 154, 0)
ck('canary post (n)',             len(postC), 248, 0)
ck('canary/wk pre',               wk(preC,26), 5.92)
ck('canary/wk post',              wk(postC,12), 20.67)
ck('canary fix rate pre %',       100*sum(r['fixed'] for r in preC)/len(preC), 43.5)
ck('canary fix rate post %',      100*sum(r['fixed'] for r in postC)/len(postC), 41.9)
mat = lambda g, dd: [r for r in g if MERGE+dt.timedelta(weeks=r['w']+1, days=dd) <= NOW]
f30 = lambda g: 100*sum(1 for r in g if r['fixed'] and r['ttc'] is not None and r['ttc']<=30)/len(g)
ck('canary <=30d pre %',          f30(mat(preC,30)), 18.8)
ck('canary <=30d post %',         f30(mat(postC,30)), 30.4)
preS  = [r for r in preB  if not r['can'] and r['sta']]
postS = [r for r in postB if not r['can'] and r['sta']]
ck('stable/wk pre',               wk(preS,26), 45.77)
ck('stable/wk post',              wk(postS,12), 31.50)
ck('stable change %',             100*(wk(postS,12)/wk(preS,26)-1), -31.2, 0.1)
ck('unlabelled pre %',            100*sum(r['unlab'] for r in PRE)/len(PRE), 20.7)
ck('unlabelled post %',           100*sum(r['unlab'] for r in POST)/len(POST), 49.8)
ck('reopened counted open (n)',   sum(r['reopened'] for r in rows), 19, 0)
ck('robobun post (n)',            sum(r['bot'] for r in POST), 84, 0)

rel = sorted(dt.datetime.strptime(l.split('\t')[0], '%Y-%m-%d').replace(tzinfo=dt.timezone.utc)
             for l in open('../data/releases.tsv'))
inwin = [d for d in rel if START <= d < MERGE]
ck('releases pre-window (n)',     len(inwin), 12, 0)
gaps24 = [ (rel[i+1]-rel[i]).days for i in range(len(rel)-1)
           if rel[i+1] >= dt.datetime(2024,1,1,tzinfo=dt.timezone.utc) ]
ck('longest 2024+ gap pre (d)',   max(gaps24), 27, 0)
ck('drought (d)',                 (NOW-max(rel)).days, 89, 0)

wide = max(len(c[0]) for c in checks)
for name, got, want, ok in checks:
    print(f"{'OK ' if ok else 'FAIL'} {name:<{wide}}  got {got:>8.2f}  want {want:>8.2f}")
print(f"\n{len(checks)-fail}/{len(checks)} checks passed")
sys.exit(1 if fail else 0)
