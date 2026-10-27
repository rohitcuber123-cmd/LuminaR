"""Disposable real-service workspace security evidence; no production catalogue edits."""
from pathlib import Path
from uuid import uuid4
from copy import deepcopy
from datetime import datetime,timezone
import json,sys,httpx,time,statistics
from backend.database.mongodb import db
from backend.utils.jwt_utils import create_access_token,JWT_SECRET_KEY,JWT_ALGORITHM
from jose import jwt
R=Path('reports');f=json.loads((R/'search_v2c_c1_fixture.json').read_text());c=db.search_sessions_v2b
uid=f['member_id'];u=db.users.find_one({'user_id':uid});token=create_access_token(uid,u['email'],u['role']);actor=jwt.decode(token,JWT_SECRET_KEY,algorithms=[JWT_ALGORITHM]);auth={'Authorization':'Bearer '+token};lid=f['library_id'];api=httpx.Client(base_url='http://127.0.0.1:8003',headers=auth,timeout=60)
phase=sys.argv[1]
if phase in ('prepatch','postpatch'):
 ids={scope:str(uuid4()) for scope in ['GLOBAL','PUBLIC','PRIVATE']}
 api.post('/search',json={'query':'books about stars','session_id':ids['GLOBAL'],'save_history':False}).raise_for_status()
 for scope,library in [('PUBLIC',f['public_library_id']),('PRIVATE',lid)]:
  api.get('/libraries/'+library+'/catalogue/search',params={'search':'books about neural networks','session_id':ids[scope]}).raise_for_status()
 q='include Romance but exclude Romance';r=api.get('/libraries/'+lid+'/catalogue/search',params={'search':q,'session_id':ids['PRIVATE']});r.raise_for_status();choice=r.json()['interpretation']['clarification']
 before=list(c.find({'user_id':str(uid),'login_session':actor['sid']}));start=time.perf_counter();r=api.get('/query/suggestions',params={'q':'neur','library_id':lid,'staff':'true'});elapsed=(time.perf_counter()-start)*1000
 after=list(c.find({'user_id':str(uid),'login_session':actor['sid']}));bm={d['_id']:d for d in before};am={d['_id']:d for d in after}
 membership=db.institution_memberships.find_one({'user_id':uid,'library_id':lid},{'_id':0,'role':1,'status':1})
 result={'phase':phase,'database':db.name,'actor':actor['sub'],'sid':actor['sid'],'library_id':lid,'request_scope':'STAFF','existing_scope':'PATRON','status':r.status_code,'body':r.json(),'elapsed_ms':elapsed,'membership':membership,'before':before,'after':after,
 'accepted_unchanged':bm[ids['PRIVATE']]==am.get(ids['PRIVATE']),'pending_unchanged':bm['clarification:'+choice['clarification_id']]==am.get('clarification:'+choice['clarification_id']),
 'global_unchanged':bm[ids['GLOBAL']]==am.get(ids['GLOBAL']),'other_library_unchanged':bm[ids['PUBLIC']]==am.get(ids['PUBLIC'])}
 assert r.status_code==403 and membership=={'role':'GENERAL_USER','status':'ACTIVE'}
 if phase=='postpatch':
  assert before==after
  res=api.post('/query/resolve',json={'clarification_id':choice['clarification_id'],'choice_id':choice['candidate_choices'][0]['choice_id'],'query':q,'session_id':ids['PRIVATE'],'library_id':lid});assert res.status_code==200,res.text
  latest=c.find_one({'_id':ids['PRIVATE']});assert latest['version']==bm[ids['PRIVATE']]['version']+1 and latest['current_plan']['subjects']==['Romance']
  result['valid_resolution']={'status':res.status_code,'after':latest,'exactly_one_commit':True}
 else:assert not result['accepted_unchanged'] and not result['pending_unchanged']
 (R/('search_v2c_c1_'+('prepatch_reproducer' if phase=='prepatch' else 'live_postpatch')+'.json')).write_text(json.dumps(result,indent=2,default=str))
 print(json.dumps({k:v for k,v in result.items() if k not in ['before','after','valid_resolution']},indent=2))
elif phase in ('before','after'):
 from search.interaction_api import authorized
 def stats(a):return {'n':len(a),'p50_ms':statistics.median(a),'p95_ms':sorted(a)[int(.95*len(a))-1],'samples_ms':a}
 timings={}
 for name,fn in [('authorization',None),('denied_workspace',None),('valid_search',None)]:
  values=[]
  for _ in range(50):
   start=time.perf_counter()
   if name=='authorization':
    with authorized(actor,lid):pass
   elif name=='denied_workspace':assert api.get('/query/suggestions',params={'q':'neur','library_id':lid,'staff':'true'}).status_code==403
   else:api.get('/libraries/'+lid+'/catalogue/search',params={'search':'books about neural networks','limit':10}).raise_for_status()
   values.append((time.perf_counter()-start)*1000)
  timings[name]=stats(values)
 generations=[];resolutions=[];contexts=[]
 try:
  for _ in range(50):
   sid=str(uuid4());contexts.append(sid);q='Fiction rating above';start=time.perf_counter();r=api.get('/libraries/'+lid+'/catalogue/search',params={'search':q,'session_id':sid,'limit':10});r.raise_for_status();generations.append((time.perf_counter()-start)*1000);ch=r.json()['interpretation']['clarification'];start=time.perf_counter();r=api.post('/query/resolve',json={'clarification_id':ch['clarification_id'],'choice_id':ch['candidate_choices'][0]['choice_id'],'query':q,'library_id':lid,'session_id':sid,'value':'3'});r.raise_for_status();resolutions.append((time.perf_counter()-start)*1000)
   # Avoid the account's normal 32-context capacity policy evicting other QA flows.
   c.delete_many({'user_id':str(uid),'login_session':actor['sid'],'$or':[{'_id':sid},{'search_session_id':sid}]})
 finally:c.delete_many({'user_id':str(uid),'login_session':actor['sid'],'$or':[{'_id':{'$in':contexts}},{'search_session_id':{'$in':contexts}}]})
 timings['clarification_generation']=stats(generations);timings['clarification_resolution']=stats(resolutions)
 (R/('search_v2c_c1_'+phase+'_measurements.json')).write_text(json.dumps(timings,indent=2));print(json.dumps({k:{i:v[i] for i in ['n','p50_ms','p95_ms']} for k,v in timings.items()},indent=2))
