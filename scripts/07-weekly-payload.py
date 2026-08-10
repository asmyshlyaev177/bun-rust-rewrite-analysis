import json,re,collections,datetime as dt
MERGE=dt.datetime(2026,5,14,8,9,34,tzinfo=dt.timezone.utc); NOW=dt.datetime(2026,8,10,12,0,tzinfo=dt.timezone.utc)
START=MERGE-dt.timedelta(weeks=26); P=lambda s: dt.datetime.fromisoformat(s.replace('Z','+00:00'))
FEAT={'enhancement','docs','idea','question','chore','duplicate','invalid','wontfix'}
meta={json.loads(l)['number']:json.loads(l) for l in open('../data/issues.jsonl')}
bodies={}
for l in open('../data/bodies.jsonl'):
    r=json.loads(l); bodies[r['n']]=r['t']+'\n'+r['b']
RUST=re.compile(r'\b1\.4\.\d+'); ZIGCAN=re.compile(r'\b1\.3\.\d+-canary'); STA=re.compile(r'\b1\.3\.\d+(?![-.\w]*canary)')
REL={'2025-11-21':'1.3.3','2025-12-07':'1.3.4','2025-12-17':'1.3.5','2026-01-13':'1.3.6','2026-01-27':'1.3.7','2026-01-29':'1.3.8','2026-02-08':'1.3.9','2026-02-26':'1.3.10','2026-03-18':'1.3.11','2026-04-10':'1.3.12','2026-04-20':'1.3.13','2026-05-13':'1.3.14'}
b=collections.defaultdict(lambda: collections.Counter())
for n,m in meta.items():
    d=P(m['createdAt'])
    if not (START<=d<NOW) or n not in bodies: continue
    if {x['name'] for x in m['labels']['nodes']}&FEAT: continue
    w=int(((d-MERGE).total_seconds()/86400/7)//1); t=bodies[n]
    fx=1 if (m['state']=='CLOSED' and m['stateReason']=='COMPLETED') else 0
    c=b[w]; c['bug']+=1; c['bfix']+=fx
    canary = bool(RUST.search(t)) or bool(ZIGCAN.search(t))
    if canary: c['can']+=1; c['canF']+=fx
    elif STA.search(t): c['sta']+=1; c['staF']+=fx
    else: c['unk']+=1; c['unkF']+=fx
out=[]
for w in range(-26,13):
    s=(MERGE+dt.timedelta(weeks=w)); e=s+dt.timedelta(days=7); c=b[w]
    out.append({'w':w,'start':s.strftime('%Y-%m-%d'),'bug':c['bug'],'bfix':c['bfix'],
      'can':c['can'],'canF':c['canF'],'sta':c['sta'],'staF':c['staF'],'unk':c['unk'],
      'rel':[v for k,v in REL.items() if s.strftime('%Y-%m-%d')<=k<e.strftime('%Y-%m-%d')]})
print(json.dumps(out,separators=(',',':')))
