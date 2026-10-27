"""Authenticated read-only product QA; no user/library/index mutations."""
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter
import requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.database.mongodb import db
from backend.services.institution_repository import collection
from backend.utils.jwt_utils import create_access_token
assert db.name=='luminar_library'
def headers(user):return {'Authorization':'Bearer '+create_access_token(user['user_id'],user['email'],user['role']),'X-Luminar-NLU-QA':'query-understanding-v2a'}
user=db.users.find_one({'user_id':4});auth=headers(user)
rows=[]
queries=['fiction','detectve','books about wizards','fiction books about wizards rated above 4',
 'fiction about detectives but not romance','online books about computer networks',
 'I want an easy introduction to computer networks','reference book for database normalization',
 'research material about neural networks','books about neural networks','books about machine learning','OL19545719W']
for query in queries:
    started=perf_counter();r=requests.post('http://127.0.0.1:8003/search',headers=auth,json={'query':query,'limit':10,'save_history':False},timeout=90)
    rows.append({'scope':'GLOBAL','query':query,'status':r.status_code,'elapsed_ms':round((perf_counter()-started)*1000,2),'response':r.json()})
    print(query,r.status_code,len(r.json().get('results',[])),flush=True)
for name in ['TEST','Private Archive QA A']:
    lib=collection('libraries').find_one({'name':name});lid=lib['library_id']
    for query in ['fiction','books about computer networks','books about neural networks','online books about computer networks']:
        started=perf_counter();r=requests.get(f'http://127.0.0.1:8003/libraries/{lid}/catalogue/search',params={'search':query,'staff':True},headers=auth,timeout=90)
        rows.append({'scope':name,'library_id':lid,'query':query,'status':r.status_code,'elapsed_ms':round((perf_counter()-started)*1000,2),'response':r.json()})
    if lib['library_type']=='PRIVATE_INSTITUTION':
        outsider=next(u for u in db.users.find({'is_active':True}) if not collection('memberships').find_one({'library_id':lid,'user_id':u['user_id'],'status':'ACTIVE'}))
        for port,route in [(8003,'search'),(8002,'facets')]:
            r=requests.get(f'http://127.0.0.1:{port}/libraries/{lid}/catalogue/{route}',params={'search':'books about neural networks'},headers=headers(outsider),timeout=45)
            rows.append({'scope':'PRIVATE_OUTSIDER','endpoint':route,'status':r.status_code,'response':r.json()})
Path(ROOT/'.local/search_v2a_live.json').write_text(json.dumps(rows,indent=2,default=str),encoding='utf-8')
performance=[]
for query,enabled in [('OL19545719W',False),('fiction',False),('books about wizards',False),('fiction books about wizards rated above 4',False),('books about machine learning',True),('books about neural networks rated above 4',True),('books about machine learning',False)]:
    samples=[];responses=[]
    for _ in range(5):
        h={**auth,'X-Luminar-V2A-KG':'on' if enabled else 'off'};started=perf_counter()
        r=requests.post('http://127.0.0.1:8003/search',headers=h,json={'query':query,'limit':10,'save_history':False},timeout=90)
        assert r.status_code==200,r.text;samples.append(round((perf_counter()-started)*1000,2));responses.append(r.json())
    performance.append({'query':query,'kg_enabled':enabled,'samples_ms':samples,'p50_ms':statistics.median(samples),'p95_ms':max(samples),'last_results':[b['work_id'] for b in responses[-1]['results']]})
events=[json.loads(line) for line in (ROOT/'.local/search_v2a_events.jsonl').read_text(encoding='utf-8').splitlines()]
for case in performance:
    traces=[e for e in events if e['scope']=='GLOBAL' and e['query']==case['query'] and e['kg_enabled']==case['kg_enabled']][-5:]
    case.update(candidate_counts=[e['diagnostics']['candidate_count'] for e in traces],kg_expansion_ms=[e['diagnostics']['kg'].get('elapsed_ms',0) for e in traces],expansion_added_candidates=[e['diagnostics']['expansion_added_candidates'] for e in traces],kg_concepts=[e['diagnostics']['kg']['concepts'] for e in traces])
(ROOT/'reports/search_v2a_performance.json').write_text(json.dumps({'source':'Live loopback HTTP, accepted resident models; five samples per case; nearest-rank p95, not a concurrency benchmark','cases':performance},indent=2),encoding='utf-8')
(ROOT/'reports/search_v2a_kg_runtime.json').write_text(json.dumps({'events':events},indent=2),encoding='utf-8')
print('Live V2A and performance evidence saved.',flush=True)
