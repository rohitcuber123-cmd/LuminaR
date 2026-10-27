"""Fresh authorized API, strict predicate, isolation and latency evidence."""
import json,statistics,time
from pathlib import Path
from uuid import uuid4
from dataclasses import asdict
import httpx
from backend.database.mongodb import db
from backend.utils.jwt_utils import create_access_token,decode_access_token
from search.query_plan import parse_query,matches
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
base=json.loads((R/'search_v2c_a_baseline.json').read_text());fixture=json.loads((R/'search_v2c_a_browser_fixture.json').read_text())
assert db.name=='luminar_library'
actors={}
for name,uid in [('owner',4),('member',fixture['member_id']),('outsider',fixture['outsider_id'])]:
 u=db.users.find_one({'user_id':uid});t=create_access_token(uid,u['email'],u['role']);actors[name]=(t,decode_access_token(t))
client=httpx.Client(base_url='http://127.0.0.1:8003',timeout=60)
def call(query,library=None,actor='owner',staff=False,session=None,personalized=False,limit=50):
 params={'search':query,'staff':str(staff).lower(),'limit':limit,'personalized':str(personalized).lower()}
 if session:params['session_id']=session
 headers={'Authorization':'Bearer '+actors[actor][0],'X-Luminar-V2B-QA':'bounded-search-review'}
 start=time.perf_counter()
 r=client.get(f'/libraries/{library}/catalogue/search',params=params,headers=headers) if library else client.post('/search',json={'query':query,'limit':limit,'save_history':False,'personalized':personalized,**({'session_id':session} if session else {})},headers=headers)
 return r,round((time.perf_counter()-start)*1000,3)
queries=[r['query'] for r in base['snapshot_probes']]+['AI excluding deep learning rated above 4','Python 3 for beginners','books published after 2020 about events in 1945','books about history after 1945','available online and physically','online but not physical']
observed={};performance={};parser_times=[]
try:
 for name,lid,actor,staff in [('GLOBAL',None,'owner',False),('TEST_PATRON',fixture['public_library_id'],'member',False),('TEST_STAFF',fixture['public_library_id'],'owner',True),('PRIVATE_PATRON',fixture['private_library_id'],'member',False),('PRIVATE_STAFF',fixture['private_library_id'],'owner',True)]:
  headers={'Authorization':'Bearer '+actors[actor][0]}
  url='http://127.0.0.1:8003/facets' if not lid else f'http://127.0.0.1:8002/libraries/{lid}/catalogue/facets'
  f=client.get(url,params={'staff':str(staff).lower()},headers=headers);f.raise_for_status();facets=[r['subject'] for r in f.json()['results']]
  rows=[]
  for q in queries:
   p=parse_query(q,facets)
   r,elapsed=call(q,lid,actor,staff);r.raise_for_status();body=r.json()
   assert 'diagnostics' not in body
   decision=body['interpretation']['decision']['decision_type']
   if decision not in ('EXECUTABLE','EXECUTABLE_WITH_NOTICE'):assert not body['results']
   else:assert all(matches(p,b) for b in body['results'])
   if lid:assert all(b['library_id']==lid for b in body['results']) and body['source']['catalogue_source']=='LIBRARY_LOCAL'
   assert all(len(b.get('search_reasons',[]))<=2 and not any(k in b for k in ('rerank_score','hnsw_score','_search_relevance','personalization_score')) for b in body['results'])
   rows.append({'query':q,'status':r.status_code,'interpretation':body['interpretation'],'returned':len(body['results']),'elapsed_ms':elapsed,'strict_violations':0,'foreign_rows':0})
  observed[name]=rows
  for _ in range(30):
   for q in queries:
    start=time.perf_counter();parse_query(q,facets);parser_times.append((name,(time.perf_counter()-start)*1000))
 # Baseline-comparable 20-sample resident-model requests. Existing private READY
 # generation and disposable private NOT_BUILT fallback are measured separately.
 for name,lid,actor,staff,topic in [('GLOBAL',None,'owner',False,'books about machine learning'),('TEST',fixture['public_library_id'],'owner',True,'books about computer networks'),('PRIVATE','c5d1f394-e053-426e-a7ff-75d0bb524c12','owner',True,'books about archives'),('PRIVATE_NOT_BUILT',fixture['private_library_id'],'member',False,'books about wizards')]:
  samples=[]
  for _ in range(20):
   r,t=call(topic,lid,actor,staff,limit=10);r.raise_for_status();samples.append(t)
  performance[name]={'samples_ms':samples,'n':len(samples),'p50_ms':statistics.median(samples),'p95_ms':sorted(samples)[18],'query':topic,'limit':10,'session':False,'personalized':False}
  off,_=call(topic,lid,actor,staff);on,_=call(topic,lid,actor,staff,personalized=True)
  key='library_book_id' if lid else 'work_id'
  assert {b[key] for b in off.json()['results']}=={b[key] for b in on.json()['results']}
  performance[name]['personalization_same_eligible_set']=True
 # Unaccepted query must leave last valid actual server session byte-for-byte.
 sid=str(uuid4());actor='member';lid=fixture['private_library_id']
 r,_=call('books about wizards',lid,actor,False,sid);r.raise_for_status()
 before=db.search_sessions_v2b.find_one({'_id':sid})
 for q in ['fiction 4','fiction rating above','books rated above 4 and below 3','books under 250 pages']:
  r,_=call(q,lid,actor,False,sid);r.raise_for_status();assert not r.json()['results']
  assert db.search_sessions_v2b.find_one({'_id':sid})==before
 r,_=call('physical only',lid,actor,False,sid);r.raise_for_status();assert r.json()['interpretation']['session']['refined']
 for staff in (False,True):
  r,_=call('fiction 4',lid,'outsider',staff);assert r.status_code in (403,404)
  observed['OUTSIDER_STAFF' if staff else 'OUTSIDER_PATRON']={'status':r.status_code,'body':r.json()}
 r=client.get(f'/libraries/{lid}/catalogue/search',params={'search':'fiction 4'},headers={'Authorization':'Bearer invalid-jwt'});assert r.status_code==401
 observed['INVALID_JWT']={'status':r.status_code}
 observed['SESSION_REJECTION_PRESERVATION']={'pass':True,'rejected_cases':4,'later_refinement':True}
 for name in ('GLOBAL','TEST_PATRON','TEST_STAFF','PRIVATE_PATRON','PRIVATE_STAFF'):
  values=[t for scope,t in parser_times if scope==name]
  performance[name+':PARSER']={'n':len(values),'p50_ms':statistics.median(values),'p95_ms':sorted(values)[int(.95*len(values))-1]}
 performance['baseline']=base['fresh_v2b_search_ms']
 performance['methodology']='Sequential local resident models; 20 samples/search group, same baseline topics, limit10, session absent and personalization OFF; no throughput or quality gain claim. Entire-pool ON/OFF eligibility checks separately use limit50.'
 (R/'search_v2c_a_live.json').write_text(json.dumps(observed,indent=2,ensure_ascii=False),encoding='utf8')
 (R/'search_v2c_a_performance.json').write_text(json.dumps(performance,indent=2),encoding='utf8')
 print(json.dumps({'contexts':list(observed),'performance':{k:{x:v[x] for x in ('n','p50_ms','p95_ms') if x in v} for k,v in performance.items() if isinstance(v,dict) and 'n'in v}}))
finally:
 for _,actor in actors.values():db.search_sessions_v2b.delete_many({'user_id':str(actor['sub']),'login_session':actor['sid']})
 client.close()
