"""Read-only PRE-V2C-A evidence; run before editing accepted parser sources."""
import json,hashlib,statistics,time
from pathlib import Path
from dataclasses import asdict
from datetime import datetime,timezone
import httpx
from backend.database.mongodb import db
from backend.utils.jwt_utils import create_access_token
from search.query_plan import parse_query
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/search_v2c_a_baseline.json'
assert not OUT.exists(),'Never overwrite the pre-change baseline'
old=json.loads((ROOT/'reports/search_v2b_baseline.json').read_text())
def fp(p):
 p=Path(p);s=p.stat();d={'size':s.st_size,'mtime_ns':s.st_mtime_ns}
 if s.st_size<10_000_000:d['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
 return d
paths=set(old['files'])|{'search/query_session.py','search/session_store.py','search/personalization.py','frontend/src/lib/searchNlu.ts','frontend/src/components/SearchIntelligence.tsx'}
result={'captured_at':datetime.now(timezone.utc).isoformat(),'database':db.name,'global_count':db.books.count_documents({}),
 'files':{p:fp(ROOT/p) for p in sorted(paths)},'tenant_artifacts':{p:fp(p) for p in old['tenant_artifacts']},
 'command':'.venv\\Scripts\\python.exe -m scripts.search_v2c_a_baseline','scopes':{},'fresh_v2b_search_ms':{}}
assert db.name=='luminar_library'
user=db.users.find_one({'user_id':4});token=create_access_token(4,user['email'],user['role'])
client=httpx.Client(base_url='http://127.0.0.1:8003',headers={'Authorization':'Bearer '+token},timeout=60)
queries=[r['query'] for r in json.loads((ROOT/'reports/search_v2c_b_precondition.json').read_text())['query_probes']]
snapshot=[v['subject'] for v in json.loads((ROOT/'reports/search_v2a_facet_vocabulary.json').read_text())['results']]
result['snapshot_probes']=[{'query':q,'plan':asdict(parse_query(q,snapshot)),'public':parse_query(q,snapshot).public()} for q in queries]
pt=[]
for _ in range(40):
 for q in queries:
  started=time.perf_counter();parse_query(q,snapshot);pt.append((time.perf_counter()-started)*1000)
result['parser_ms']={'p50':statistics.median(pt),'p95':sorted(pt)[int(.95*len(pt))-1],'n':len(pt)}
for name,lid,topic in [('GLOBAL',None,'books about machine learning'),('TEST','e6d1e5b4-c48f-4b47-b96a-656a676fb8ae','books about computer networks'),('PRIVATE','c5d1f394-e053-426e-a7ff-75d0bb524c12','books about archives')]:
 r=client.get('/facets' if not lid else f'http://127.0.0.1:8002/libraries/{lid}/catalogue/facets',params={'staff':'true'} if lid else {})
 r.raise_for_status();facets=[v['subject'] for v in r.json()['results']]
 probes=[]
 for q in queries:
  p=parse_query(q,facets);probes.append({'query':q,'plan':asdict(p),'public':p.public()})
 timings=[]
 for _ in range(20):
  start=time.perf_counter()
  r=client.post('/search',json={'query':topic,'limit':10,'save_history':False,'personalized':False}) if not lid else client.get(f'/libraries/{lid}/catalogue/search',params={'search':topic,'staff':'true','limit':10})
  r.raise_for_status();timings.append(round((time.perf_counter()-start)*1000,3))
 result['scopes'][name]={'library_id':lid,'staff':bool(lid),'facet_source':'fresh authorized facet API','facets':facets,'probes':probes}
 result['fresh_v2b_search_ms'][name]={'samples':timings,'p50':statistics.median(timings),'p95':sorted(timings)[18],'n':20,'query':topic,'session':False,'personalized':False}
result['search_health']=client.get('/health').json()
OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps({'baseline':str(OUT),'global_count':result['global_count'],'scopes':{k:len(v['facets']) for k,v in result['scopes'].items()},'performance':result['fresh_v2b_search_ms']}))
