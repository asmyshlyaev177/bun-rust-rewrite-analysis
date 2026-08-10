import json, re, collections, datetime as dt, statistics as st
MERGE=dt.datetime(2026,5,14,8,9,34,tzinfo=dt.timezone.utc); NOW=dt.datetime(2026,8,10,12,0,tzinfo=dt.timezone.utc)
START=MERGE-dt.timedelta(weeks=26); P=lambda s: dt.datetime.fromisoformat(s.replace('Z','+00:00'))
FEAT={'enhancement','docs','idea','question','chore','duplicate','invalid','wontfix'}

meta={}
for l in open('../data/issues.jsonl'):
    r=json.loads(l); meta[r['number']]=r
bodies={}
for l in open('../data/bodies.jsonl'):
    r=json.loads(l); bodies[r['n']]=r['t']+'\n'+r['b']

CANARY=re.compile(r'\b\d+\.\d+\.\d+-canary|\b1\.4\.0\b|\bcanary\b',re.I)
CANARY_STRICT=re.compile(r'\b\d+\.\d+\.\d+-canary|\b1\.4\.0[-.\d]*\b')
STABLE=re.compile(r'\b1\.3\.\d+(?![-.\w]*canary)')

rows=[]
for n,m in meta.items():
    d=P(m['createdAt'])
    if not (START<=d<NOW) or n not in bodies: continue
    txt=bodies[n]
    lab={x['name'] for x in m['labels']['nodes']}
    rows.append({'n':n,'dt':d,'bug':not(lab&FEAT),
      'fixed':m['state']=='CLOSED' and m['stateReason']=='COMPLETED',
      'ttc':((P(m['closedAt'])-d).total_seconds()/86400) if m['closedAt'] else None,
      'canary':bool(CANARY_STRICT.search(txt)),'stable':bool(STABLE.search(txt))})
print(f"matched bodies for {len(rows)} of the window's issues")

def wk(r): return int(((r['dt']-MERGE).total_seconds()/86400/7)//1)
def rep(name,sel,lo,hi):
    g=[r for r in rows if lo<=wk(r)<=hi and sel(r)]
    nw=hi-lo+1
    if not g: print(f"{name:<34} none"); return
    fx=sum(1 for r in g if r['fixed'])
    gm=[r for r in g if (MERGE+dt.timedelta(weeks=wk(r)+1)+dt.timedelta(days=30))<=NOW]
    f30=sum(1 for r in gm if r['fixed'] and r['ttc'] is not None and r['ttc']<=30)
    med=st.median([r['ttc'] for r in g if r['fixed'] and r['ttc'] is not None]) if fx else float('nan')
    print(f"{name:<34} n={len(g):<5} {len(g)/nw:5.2f}/wk | fixed {fx:<4} = {fx/nw:5.2f}/wk = {100*fx/len(g):5.1f}%"
          + (f" | <=30d={100*f30/len(gm):5.1f}%" if gm else " | <=30d=  n/a") + f" med={med:5.1f}d")

CAN=lambda r: r['canary']
CANBUG=lambda r: r['canary'] and r['bug']
STABUG=lambda r: (not r['canary']) and r['stable'] and r['bug']
print("\n===== CANARY-BUILD ISSUES (any) =====")
rep('Pre-rewrite  -26..-1',CAN,-26,-1); rep('  pre final quarter -13..-1',CAN,-13,-1); rep('Post-rewrite  0..11',CAN,0,11)
print("\n===== CANARY-BUILD BUG ISSUES =====")
rep('Pre-rewrite  -26..-1',CANBUG,-26,-1); rep('  pre final quarter -13..-1',CANBUG,-13,-1)
rep('Post-rewrite  0..11',CANBUG,0,11); rep('  post month 1',CANBUG,0,3); rep('  post month 2',CANBUG,4,7); rep('  post month 3',CANBUG,8,11)
print("\n===== STABLE-ONLY BUG ISSUES (mentions 1.3.x, never canary) =====")
rep('Pre-rewrite  -26..-1',STABUG,-26,-1); rep('Post-rewrite  0..11',STABUG,0,11)

print("\n=== weekly canary bug counts ===")
b=collections.defaultdict(lambda:[0,0])
for r in rows:
    if CANBUG(r): b[wk(r)][0]+=1; b[wk(r)][1]+=r['fixed']
print(json.dumps([{'w':w,'bug':b[w][0],'bfix':b[w][1]} for w in sorted(b)],separators=(',',':')))

print("\n=== censoring-matched speed comparison (canary bugs) ===")
def speed(name,lo,hi):
    g=[r for r in rows if lo<=wk(r)<=hi and CANBUG(r)
       and (MERGE+dt.timedelta(weeks=wk(r)+1)+dt.timedelta(days=30))<=NOW]
    f30=[r['ttc'] for r in g if r['fixed'] and r['ttc'] is not None and r['ttc']<=30]
    ever=[r['ttc'] for r in g if r['fixed'] and r['ttc'] is not None]
    print(f"{name:<30} n={len(g):<4} fixed<=30d={len(f30):<4}({100*len(f30)/len(g):4.1f}%)  "
          f"median of those={st.median(f30):5.1f}d  median of all fixes={st.median(ever):6.1f}d")
speed('Pre-rewrite  -26..-1',-26,-1); speed('  pre final quarter',-13,-1); speed('Post-rewrite  0..7',0,7)

print("\n=== classification coverage ===")
for name,lo,hi in [('pre  -26..-1',-26,-1),('post   0..11',0,11)]:
    g=[r for r in rows if lo<=wk(r)<=hi and r['bug']]
    c=sum(1 for r in g if r['canary']); s=sum(1 for r in g if not r['canary'] and r['stable'])
    print(f"{name:<14} bug issues={len(g):<5} canary={c:<5}({100*c/len(g):4.1f}%)  stable-only={s:<5}({100*s/len(g):4.1f}%)  no version={len(g)-c-s:<5}({100*(len(g)-c-s)/len(g):4.1f}%)")
