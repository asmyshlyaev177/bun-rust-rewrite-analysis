import json, collections, datetime as dt, statistics as st
MERGE=dt.datetime(2026,5,14,8,9,34,tzinfo=dt.timezone.utc); NOW=dt.datetime(2026,8,10,12,0,tzinfo=dt.timezone.utc)
START=MERGE-dt.timedelta(weeks=26); P=lambda s: dt.datetime.fromisoformat(s.replace('Z','+00:00'))
rows=[]
for l in open('../data/issues.jsonl'):
    r=json.loads(l); r['dt']=P(r['createdAt'])
    if not (START<=r['dt']<NOW): continue
    r['cl']=P(r['closedAt']) if r['closedAt'] else None
    r['ttc']=(r['cl']-r['dt']).total_seconds()/86400 if r['cl'] else None
    r['lab']={n['name'] for n in r['labels']['nodes']}; rows.append(r)
print('state x stateReason:',collections.Counter((r['state'],r['stateReason']) for r in rows))
def wk(r): return int(((r['dt']-MERGE).total_seconds()/86400/7)//1)
b=collections.defaultdict(list)
for r in rows: b[wk(r)].append(r)
def mature(w,d): return (MERGE+dt.timedelta(weeks=w+1)+dt.timedelta(days=d))<=NOW
D=30
def rep(name,lo,hi):
    g=[r for w in range(lo,hi+1) for r in b[w]]
    gm=[r for w in range(lo,hi+1) if mature(w,D) for r in b[w]]
    n=len(g); c=collections.Counter(r['stateReason'] or 'OPEN' for r in g)
    fixed30=sum(1 for r in gm if r['stateReason'] in ('COMPLETED','REOPENED') and r['ttc'] is not None and r['ttc']<=D)
    med=st.median([r['ttc'] for r in g if r['stateReason']=='COMPLETED' and r['ttc'] is not None])
    print(f"{name:<32} n={n:<5} open={100*c['OPEN']/n:5.1f}%  fixed={100*(c['COMPLETED']+c['REOPENED'])/n:5.1f}%"
          f"  duplicate={100*c['DUPLICATE']/n:5.1f}%  not-planned={100*c['NOT_PLANNED']/n:5.1f}%"
          + (f" | fixed<={D}d={100*fixed30/len(gm):5.1f}% (n={len(gm)})" if gm else f" | fixed<={D}d=  n/a (censored)")
          + f"  med-to-fix={med:5.1f}d")
print()
for n_,lo,hi in [('Pre-rewrite  wk -26..-1',-26,-1),('  pre last 13wk',-13,-1),('Post-rewrite wk 0..11',0,11),
                 ('  post month 1',0,3),('  post month 2',4,7),('  post month 3',8,11)]: rep(n_,lo,hi)

# ---- releases ----
print("\n=== RELEASE CADENCE ===")
rel=[]
for l in open('../data/releases.tsv'):
    d,tag,pre=l.strip().split('\t'); rel.append((dt.datetime.strptime(d,'%Y-%m-%d').replace(tzinfo=dt.timezone.utc),tag))
rel.sort()
print(f"{len(rel)} releases total, {rel[0][0]:%Y-%m-%d} .. {rel[-1][0]:%Y-%m-%d}; all prerelease=false")
def relstats(name,a,b_):
    w=[r for r in rel if a<=r[0]<b_]; days=(b_-a).days
    gaps=[(w[i+1][0]-w[i][0]).days for i in range(len(w)-1)]
    g=f"median gap {st.median(gaps):.0f}d" if gaps else "n/a"
    print(f"{name:<44} {len(w):>3} releases / {days:>3}d = {len(w)/(days/30.44):.2f}/month, {g}")
    return w
relstats('Pre-rewrite  (13 Nov 25 - 14 May 26)',START,MERGE)
relstats('  same window, 1 yr earlier',START-dt.timedelta(days=365),MERGE-dt.timedelta(days=365))
relstats('Post-rewrite (14 May 26 - 10 Aug 26)',MERGE,NOW)
print(f"\nLast stable release: {rel[-1][1]} on {rel[-1][0]:%Y-%m-%d} "
      f"= {(MERGE-rel[-1][0]).days}d BEFORE the merge; {(NOW-rel[-1][0]).days}d ago, still the newest.")
prev=[ (rel[i+1][0]-rel[i][0]).days for i in range(len(rel)-1) if rel[i+1][0]>dt.datetime(2024,1,1,tzinfo=dt.timezone.utc)]
print(f"Longest gap between releases in all of 2024-2026 before this one: {max(prev)}d (median {st.median(prev):.0f}d)")
print("Releases since 2025-06:"); [print(f"   {d:%Y-%m-%d}  {t}") for d,t in rel if d>=dt.datetime(2025,6,1,tzinfo=dt.timezone.utc)]
