"""Sequential baseline timings on running services, using disposable QA state."""
from pathlib import Path
from uuid import uuid4
import json,time,statistics
import httpx
from jose import jwt
from backend.database.mongodb import db
from backend.utils.jwt_utils import create_access_token,JWT_SECRET_KEY,JWT_ALGORITHM
from search.interaction_api import authorized
from search.query_plan import parse_query
R=Path('reports');f=json.loads((R/'search_v2c_c_resume_fixture.json').read_text());lid=f['library_id'];public=f['public_library_id'];uid=f['member_id']
def token(n):
 u=db.users.find_one({'user_id':n});return create_access_token(n,u['email'],u['role'])
t=token(uid);staff=token(4);actor=jwt.decode(t,JWT_SECRET_KEY,algorithms=[JWT_ALGORITHM]);api=httpx.Client(base_url='http://127.0.0.1:8003',timeout=90)
def request(method,path,staff_scope=False,**kw):return api.request(method,path,headers={'Authorization':'Bearer '+(staff if staff_scope else t)},**kw)
def stats(a):
 s=sorted(a);n=len(a);return {'n':n,'p50_ms':statistics.median(s),'p95_ms':s[max(0,int(.95*n)-1)],'p99_ms':s[max(0,int(.99*n)-1)],'samples_ms':a}
out={'measurement':'Fresh V2C-C resume baseline; sequential samples, not concurrent load testing. Warm/cached paths included; unchanged Search PID3068; parser source unchanged. Private fixture NOT_BUILT so local catalogue fallback is measured, not ready semantic search.','timings':{}}
def measure(name,fn,n=100):
 samples=[]
 for i in range(n):
  start=time.perf_counter();fn(i);samples.append((time.perf_counter()-start)*1000)
 out['timings'][name]=stats(samples)
 (R/'search_v2c_c_resume_performance_baseline.json').write_text(json.dumps(out,indent=2))
 print(name,round(out['timings'][name]['p50_ms'],3),round(out['timings'][name]['p95_ms'],3),flush=True)
scopes=json.loads((R/'search_v2c_c_scope_vocabularies.json').read_text())
measure('parser_global',lambda i:parse_query(['books about stars','fiction rated above 3','books titled "1984"','online and physical'][i%4],scopes['GLOBAL']['subjects']),1000)
measure('authorization',lambda i:authorized_check(),100) if False else None
def auth_check(i):
 with authorized(actor,lid):pass
measure('authorization',auth_check)
def denied(i):assert request('GET','/query/suggestions',params={'q':'neur','library_id':lid,'staff':True}).status_code==403
measure('denial',denied)
for name,library,is_staff in [('GLOBAL',None,False),('PUBLIC_PATRON',public,False),('PUBLIC_STAFF',public,True),('PRIVATE_PATRON',lid,False),('PRIVATE_STAFF',lid,True)]:
 def suggestion(i):
  params={'q':['neur','fict','hist','myst'][i%4]}
  if library:params.update(library_id=library,staff=is_staff)
  request('GET','/query/suggestions',staff_scope=is_staff,params=params).raise_for_status()
 measure('suggestions_'+name,suggestion)
 if not is_staff:
  def search(i):
   q=['books about stars','books about neural networks','books about history','books about mystery'][i%4]
   r=request('GET','/libraries/'+library+'/catalogue/search',params={'search':q,'limit':10}) if library else request('POST','/search',json={'query':q,'save_history':False,'top_k':10})
   r.raise_for_status()
  measure('search_'+name,search)
generations=[];resolutions=[];owned={'user_id':str(uid),'login_session':actor['sid']}
for _ in range(100):
 sid=str(uuid4());q='Fiction rating above'
 try:
  start=time.perf_counter();r=request('GET','/libraries/'+lid+'/catalogue/search',params={'search':q,'session_id':sid});r.raise_for_status();generations.append((time.perf_counter()-start)*1000);ch=r.json()['interpretation']['clarification'];assert ch
  start=time.perf_counter();r=request('POST','/query/resolve',json={'query':q,'session_id':sid,'library_id':lid,'clarification_id':ch['clarification_id'],'choice_id':ch['candidate_choices'][0]['choice_id'],'value':'3'});r.raise_for_status();resolutions.append((time.perf_counter()-start)*1000)
 finally:db.search_sessions_v2b.delete_many({**owned,'$or':[{'_id':sid},{'search_session_id':sid}]})
out['timings']['clarification_generation']=stats(generations);out['timings']['clarification_resolution']=stats(resolutions)
(R/'search_v2c_c_resume_performance_baseline.json').write_text(json.dumps(out,indent=2));print('COMPLETE',flush=True)
