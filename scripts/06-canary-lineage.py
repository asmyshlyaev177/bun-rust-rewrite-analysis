import json,re,collections,datetime as dt,statistics as st
MERGE=dt.datetime(2026,5,14,8,9,34,tzinfo=dt.timezone.utc); NOW=dt.datetime(2026,8,10,12,0,tzinfo=dt.timezone.utc)
START=MERGE-dt.timedelta(weeks=26); P=lambda s: dt.datetime.fromisoformat(s.replace('Z','+00:00'))
FEAT={'enhancement','docs','idea','question','chore','duplicate','invalid','wontfix'}
meta={json.loads(l)['number']:json.loads(l) for l in open('../data/issues.jsonl')}
bodies={}
for l in open('../data/bodies.jsonl'):
    r=json.loads(l); bodies[r['n']]=r['t']+'\n'+r['b']
RUST=re.compile(r'\b1\.4\.\d+')                       # 1.4.x — only exists post-rewrite lineage
ZIGCAN=re.compile(r'\b1\.3\.\d+-canary')              # canary on the 1.3 (Zig) line
rows=[]
for n,m in meta.items():
    d=P(m['createdAt'])
    if not (START<=d<NOW) or n not in bodies: continue
    if {x['name'] for x in m['labels']['nodes']}&FEAT: continue
    t=bodies[n]
    rows.append({'n':n,'dt':d,'w':int(((d-MERGE).total_seconds()/86400/7)//1),
      'rust':bool(RUST.search(t)),'zigcan':bool(ZIGCAN.search(t)),
      'fixed':m['state']=='CLOSED' and m['stateReason']=='COMPLETED',
      'ttc':((P(m['closedAt'])-d).total_seconds()/86400) if m['closedAt'] else None})

print("=== when do 1.4.x (Rust-lineage) mentions first appear? ===")
r14=sorted([r for r in rows if r['rust']],key=lambda r:r['dt'])
print(f"{len(r14)} issues mention 1.4.x; earliest {r14[0]['dt']:%Y-%m-%d} (#{r14[0]['n']}), merge was 2026-05-14")
pre=[r for r in r14 if r['w']<0]
print(f"{len(pre)} of them predate the merge; by week: {collections.Counter(r['w'] for r in pre).most_common()}")
print("\n=== weekly canary lineage counts ===")
b=collections.defaultdict(lambda: collections.Counter())
for r in rows:
    k='rust' if r['rust'] else ('zigcan' if r['zigcan'] else None)
    if k: b[r['w']][k]+=1; b[r['w']][k+'F']+=r['fixed']
for w in sorted(b): print(f"  w{w:>4}  zig-canary={b[w]['zigcan']:>3} (fixed {b[w]['zigcanF']:>2})   rust={b[w]['rust']:>3} (fixed {b[w]['rustF']:>2})")

def rep(name,sel,lo,hi):
    g=[r for r in rows if lo<=r['w']<=hi and sel(r)]; nw=hi-lo+1
    if not g: print(f"{name:<40} none"); return
    fx=sum(1 for r in g if r['fixed'])
    gm=[r for r in g if (MERGE+dt.timedelta(weeks=r['w']+1)+dt.timedelta(days=30))<=NOW]
    f30=sum(1 for r in gm if r['fixed'] and r['ttc'] is not None and r['ttc']<=30)
    print(f"{name:<40} n={len(g):<4} {len(g)/nw:5.2f}/wk | fixed {fx:<4}={fx/nw:5.2f}/wk = {100*fx/len(g):5.1f}%"
          + (f" | <=30d={100*f30/len(gm):5.1f}% (n={len(gm)})" if gm else " | <=30d= n/a"))
print("\n=== ZIG CANARY (1.3.x-canary) ===")
rep('Pre-rewrite  -26..-1',lambda r:r['zigcan'],-26,-1); rep('  pre final quarter -13..-1',lambda r:r['zigcan'],-13,-1)
rep('Post-rewrite  0..11',lambda r:r['zigcan'],0,11)
print("\n=== RUST LINEAGE (1.4.x) ===")
rep('Pre-merge  -26..-1',lambda r:r['rust'],-26,-1); rep('Post-merge  0..11',lambda r:r['rust'],0,11)
rep('  post month 1',lambda r:r['rust'],0,3); rep('  post month 2',lambda r:r['rust'],4,7); rep('  post month 3',lambda r:r['rust'],8,11)
print("\n=== ANY CANARY (zig-canary OR rust) — the like-for-like channel ===")
anyc=lambda r: r['zigcan'] or r['rust']
rep('Pre-rewrite  -26..-1',anyc,-26,-1); rep('  pre final quarter -13..-1',anyc,-13,-1); rep('Post-rewrite  0..11',anyc,0,11)
