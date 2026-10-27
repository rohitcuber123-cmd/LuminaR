"""Immutable pre-implementation V2C-B measurements and source/artifact inventory."""
import hashlib,json,statistics,time
from datetime import datetime,timezone
from pathlib import Path
import httpx
from backend.database.mongodb import db
from backend.utils.jwt_utils import create_access_token
from search.query_plan import parse_query

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports';OUT=R/'search_v2c_b_baseline.json'
assert not OUT.exists(),'Do not overwrite fresh baseline'
old=json.loads((R/'search_v2c_a1_baseline.json').read_text(encoding='utf8'))
fixture=json.loads((R/'search_v2c_b_fixture.json').read_text())
names=set(old['files'])|{'search/session_store.py','search/query_execution.py','search/api.py','search/library_intelligence_api.py',
    'frontend/src/components/CatalogueSurface.tsx','frontend/src/components/GlobalCatalogue.tsx','frontend/src/components/SearchIntelligence.tsx',
    'frontend/src/pages/LibraryCatalogue.tsx','frontend/src/lib/searchNlu.ts','frontend/src/lib/libraryCatalogue.ts','frontend/src/hooks/useLibraryCatalogue.ts'}
def fp(name):
    p=Path(name);s=p.stat();d={'size':s.st_size,'mtime_ns':s.st_mtime_ns}
    if s.st_size<10_000_000:d['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    return d
user=db.users.find_one({'user_id':4});token=create_access_token(4,user['email'],user['role'])
client=httpx.Client(base_url='http://127.0.0.1:8003',headers={'Authorization':'Bearer '+token},timeout=60)
facets=[r['subject'] for r in client.get('/facets').json()['results']]
times=[]
for _ in range(25):
    for q in old['queries']:
        t=time.perf_counter();parse_query(q,facets);times.append((time.perf_counter()-t)*1000)
groups=[('GLOBAL',None,'books about machine learning'),('TEST',fixture['public_library_id'],'books about computer networks'),
        ('PRIVATE_READY','c5d1f394-e053-426e-a7ff-75d0bb524c12','books about archives'),
        ('PRIVATE_NOT_BUILT',fixture['library_id'],'books about wizards')]
search={}
for name,lid,q in groups:
    values=[]
    for _ in range(20):
        t=time.perf_counter()
        response=client.get(f'/libraries/{lid}/catalogue/search',params={'search':q,'staff':'true','limit':10,'personalized':'false'}) if lid else client.post('/search',json={'query':q,'limit':10,'save_history':False,'personalized':False})
        response.raise_for_status();values.append((time.perf_counter()-t)*1000)
    search[name]={'query':q,'n':20,'samples_ms':values,'p50_ms':statistics.median(values),'p95_ms':sorted(values)[18],
                  'library_id':lid,'staff':bool(lid),'limit':10,'session':False,'personalized':False}
data={'captured_at':datetime.now(timezone.utc).isoformat(),'database':db.name,'global_book_count':db.books.count_documents({}),
      'files':{p:fp(ROOT/p) for p in sorted(names)},'parser':{'queries':old['queries'],'facets':facets,'n':len(times),'samples_ms':times,
      'p50_ms':statistics.median(times),'p95_ms':sorted(times)[int(.95*len(times))-1]},'search':search,
      'health':client.get('/health').json(),'mongo_indexes':{name:db[name].index_information() for name in ['books','institution_library_books']},
      'fresh_gate':{'planner':1307,'session':34,'original_admission':'8/8'},
      'method':'Sequential resident localhost requests;20requests/searchgroup,600parser samples same24A1queries. No throughput/speedup claim.'}
OUT.write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
print(json.dumps({'baseline':str(OUT),'parser':{k:data['parser'][k] for k in ['n','p50_ms','p95_ms']},
                  'search':{k:{x:v[x] for x in ['p50_ms','p95_ms']} for k,v in search.items()}}))
