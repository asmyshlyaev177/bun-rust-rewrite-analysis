#!/usr/bin/env python3
"""Emit ../data/weekly.csv — the per-week table behind every chart."""
import json, re, csv, collections, datetime as dt
MERGE=dt.datetime(2026,5,14,8,9,34,tzinfo=dt.timezone.utc); NOW=dt.datetime(2026,8,10,12,0,tzinfo=dt.timezone.utc)
START=MERGE-dt.timedelta(weeks=26); P=lambda s: dt.datetime.fromisoformat(s.replace('Z','+00:00'))
FEAT={'enhancement','docs','idea','question','chore','duplicate','invalid','wontfix'}
BUGLAB={'bug','crash','confirmed bug'}
meta={json.loads(l)['number']:json.loads(l) for l in open('../data/issues.jsonl')}
bodies={}
for l in open('../data/bodies.jsonl'):
    r=json.loads(l); bodies[r['n']]=r['t']+'\n'+r['b']
RUST=re.compile(r'\b1\.4\.\d+'); ZIGCAN=re.compile(r'\b1\.3\.\d+-canary'); STA=re.compile(r'\b1\.3\.\d+(?![-.\w]*canary)')
REL=collections.defaultdict(list)
for l in open('../data/releases.tsv'):
    d,tag,_=l.strip().split('\t'); REL[d].append(tag.replace('bun-v',''))
b=collections.defaultdict(collections.Counter)
for n,m in meta.items():
    d=P(m['createdAt'])
    if not (START<=d<NOW): continue
    w=int(((d-MERGE).total_seconds()/86400/7)//1); c=b[w]; lab={x['name'] for x in m['labels']['nodes']}
    fixed = m['state']=='CLOSED' and m['stateReason']=='COMPLETED'
    c['all']+=1
    if (m['author'] or {}).get('login')!='robobun': c['human']+=1
    if not lab: c['unlabelled']+=1
    if lab & BUGLAB: c['labelled_bug']+=1
    if not (lab & FEAT):
        c['bug']+=1; c['bug_fixed']+=fixed
        t=bodies.get(n,'')
        k='canary' if (RUST.search(t) or ZIGCAN.search(t)) else ('stable' if STA.search(t) else 'noversion')
        c[k]+=1; c[k+'_fixed']+=fixed
        if RUST.search(t): c['rust_lineage']+=1
        elif ZIGCAN.search(t): c['zig_canary']+=1
    for sr in ([m['stateReason']] if m['state']=='CLOSED' else ['OPEN']): c['st_'+(sr or 'OPEN')]+=1
COLS=['week','week_start','period','all_issues','human_filed','unlabelled','labelled_bug','bug_reports','bug_fixed',
      'canary','canary_fixed','zig_canary','rust_lineage','stable_only','stable_fixed','no_version','no_version_fixed',
      'closed_completed','closed_duplicate','closed_not_planned','open','releases']
with open('../data/weekly.csv','w',newline='') as f:
    wr=csv.writer(f); wr.writerow(COLS)
    for w in range(-26,13):
        c=b[w]; s=MERGE+dt.timedelta(weeks=w); e=s+dt.timedelta(days=7)
        rel=[t for d,tags in REL.items() if s.strftime('%Y-%m-%d')<=d<e.strftime('%Y-%m-%d') for t in tags]
        wr.writerow([w,s.strftime('%Y-%m-%d'),'partial' if w==12 else ('pre' if w<0 else 'post'),
          c['all'],c['human'],c['unlabelled'],c['labelled_bug'],c['bug'],c['bug_fixed'],
          c['canary'],c['canary_fixed'],c['zig_canary'],c['rust_lineage'],c['stable'],c['stable_fixed'],
          c['noversion'],c['noversion_fixed'],
          c['st_COMPLETED'],c['st_DUPLICATE'],c['st_NOT_PLANNED'],c['st_OPEN'],' '.join(rel)])
print('wrote ../data/weekly.csv')
