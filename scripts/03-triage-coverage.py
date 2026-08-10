import json, collections, datetime as dt
MERGE=dt.datetime(2026,5,14,8,9,34,tzinfo=dt.timezone.utc)
NOW=dt.datetime(2026,8,10,12,0,tzinfo=dt.timezone.utc)
START=MERGE-dt.timedelta(weeks=26)
rows=[json.loads(l) for l in open('../data/issues.jsonl')]
for r in rows:
    r['dt']=dt.datetime.fromisoformat(r['createdAt'].replace('Z','+00:00'))
    r['lab']={n['name'] for n in r['labels']['nodes']}
rows=[r for r in rows if START<=r['dt']<NOW]
def wk(r): return int(((r['dt']-MERGE).total_seconds()/86400/7)//1)

b=collections.defaultdict(lambda: collections.Counter())
for r in rows:
    w=wk(r); c=b[w]; c['all']+=1
    if not r['lab']: c['nolabel']+=1
    if 'needs triage' in r['lab']: c['triage']+=1
    if r['lab'] & {'bug','crash','confirmed bug'}: c['bug']+=1
    if 'enhancement' in r['lab']: c['enh']+=1
    if r['closedAt']: c['closed']+=1
    if (r['author'] or {}).get('login')=='robobun': c['bot']+=1
    if 'regression' in r['lab']: c['regr']+=1

print(f"{'wk':>4} {'start':<11}{'all':>5}{'bug%':>7}{'unlab%':>8}{'triage%':>8}{'enh':>5}{'bot':>5}{'closed%':>8}")
for w in sorted(b):
    c=b[w]; a=c['all']
    print(f"{w:>4} {MERGE+dt.timedelta(weeks=w):%Y-%m-%d} {a:>5}{100*c['bug']/a:>6.0f}%{100*c['nolabel']/a:>7.0f}%{100*c['triage']/a:>7.0f}%{c['enh']:>5}{c['bot']:>5}{100*c['closed']/a:>7.0f}%")

def agg(lo,hi):
    t=collections.Counter()
    for w in range(lo,hi+1): t.update(b[w])
    return t
print("\n=== coverage check ===")
for name,lo,hi in [('pre  -26..-1',-26,-1),('pre  -13..-1 (last 3mo)',-13,-1),('post   0..11',0,11),('post   8..11',8,11)]:
    t=agg(lo,hi); a=t['all']
    print(f"{name:<26} n={a:<5} bug={100*t['bug']/a:5.1f}%  unlabeled={100*t['nolabel']/a:5.1f}%  needs-triage={100*t['triage']/a:5.1f}%  closed={100*t['closed']/a:5.1f}%  bot={t['bot']}")
