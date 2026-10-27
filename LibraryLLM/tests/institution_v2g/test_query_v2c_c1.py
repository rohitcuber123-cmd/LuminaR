"""C.1 ownership matrix over isolated real Mongo and workspace-bound profiles."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
from time import monotonic
from threading import Event
from concurrent.futures import ThreadPoolExecutor
import json,os
import pytest
from fastapi import HTTPException
from search.session_store import collection,resolve as resolve_plan,invalidate
from search import personalization as profiles
from search.query_execution import tenant_search
from test_query_v2a import query_library
from test_query_v2c_b import ACTOR,interaction_client
from backend.schemas.institutions import MembershipChange
from backend.services.institution_service import change_membership

R=Path(os.getenv('LUMINAR_SECURITY_REPORT_DIR',str(Path(__file__).resolve().parents[2]/'reports')))

def actor(sid='v2cb-login',uid=2):return {'sub':str(uid),'sid':sid}

def context(worker,lid,who,staff=False):
 sid=str(uuid4());q='books rated above 4 and below 3'
 if lid:
  tenant_search(worker,lid,who,'books about neural networks',session_id=sid,staff=staff)
  response=tenant_search(worker,lid,who,q,session_id=sid,staff=staff)
 else:
  from search.query_interaction import offer
  from search.query_plan import parse_query
  _,session=resolve_plan('books about stars',who,[],session_id=sid)
  response={'interpretation':{'clarification':offer(parse_query(q),session,who,query=q,mode='SMART',filters={},omit=[],session_id=sid,capabilities={'rating':True})}}
 ch=response['interpretation']['clarification'];assert ch
 key=(who['sub'],who['sid'],lid,bool(staff),'saved-canonical-v1');profiles._cache[key]=(monotonic()+60,profiles.empty())
 return {'sid':sid,'cid':'clarification:'+ch['clarification_id'],'owner':who,'library_id':lid,'staff':staff,
         'body':{'query':q,'session_id':sid,'library_id':lid,'staff':staff,'clarification_id':ch['clarification_id'],'choice_id':ch['candidate_choices'][0]['choice_id']}}

def capture():
 return {'accepted':list(collection().find({'current_plan':{'$exists':True}}).sort('_id')),
         'pending':list(collection().find({'record_type':'CLARIFICATION'}).sort('_id')),
         'profiles':{repr(k):deepcopy(v) for k,v in profiles._cache.items()}}

def record(name,before,after,status,request,reason):
 def changes(kind):
  b={r['_id']:r for r in before[kind]};a={r['_id']:r for r in after[kind]}
  return {'invalidated':sorted(b.keys()-a.keys()),'preserved':sorted(k for k in b.keys()&a.keys() if b[k]==a[k]),'updated':sorted(k for k in b.keys()&a.keys() if b[k]!=a[k])}
 row={'case':name,'request_scope':request,'request_result':status,'authorization_reason':reason,'before':before,'after':after,
      'accepted_changes':changes('accepted'),'pending_changes':changes('pending'),
      'personalization_invalidated':sorted(before['profiles'].keys()-after['profiles'].keys()),
      'personalization_preserved':sorted(k for k in before['profiles'].keys()&after['profiles'].keys() if before['profiles'][k]==after['profiles'][k]),
      'destructive_action_permitted_because':reason if any(changes(k)['invalidated'] for k in ['accepted','pending']) else 'No destructive action occurred.'}
 p=R/'search_v2c_c1_matrix_observed.json';data=json.loads(p.read_text()) if p.exists() else {};data[name]=row;p.write_text(json.dumps(data,indent=2,default=str))

def unchanged_scope(item,before,after):
 for kind,key in [('accepted','sid'),('pending','cid')]:
  b=next(r for r in before[kind] if r['_id']==item[key]);assert next((r for r in after[kind] if r['_id']==item[key]),None)==b

def absent(item,after):
 assert not any(r['_id']==item['sid'] for r in after['accepted'])
 assert not any(r['_id']==item['cid'] for r in after['pending'])

def set_role(lid,role):
 from backend.database.mongodb import db
 m=db.institution_memberships.find_one({'library_id':lid,'user_id':2})
 return change_membership(lid,m['membership_id'],MembershipChange(role=role),{'sub':'1'})

def revoke(lid):
 from backend.database.mongodb import db
 m=db.institution_memberships.find_one({'library_id':lid,'user_id':2})
 return change_membership(lid,m['membership_id'],MembershipChange(status='REMOVED'),{'sub':'1'})

@pytest.fixture
def scopes(query_library,database,client,library):
 profiles._cache.clear();lid=query_library[0];worker=query_library[3]
 other=library(private=False);assert client.post(f'/libraries/{other}/join',headers={'x-test-user':'2'},json={}).status_code==200
 owner=actor();other_login=actor('other-login');another=actor(uid=4)
 assert client.post(f'/libraries/{lid}/join',headers={'x-test-user':'4'},json={'access_code':'Isolated fixture access code'}).status_code==200
 ctx={'A':context(worker,lid,owner),'B':context(worker,other,owner),'GLOBAL':context(worker,None,owner),
      'S2':context(worker,lid,other_login),'OTHER_USER':context(worker,lid,another)}
 return lid,other,worker,ctx,interaction_client(database,worker)

@pytest.mark.parametrize('case',['patron_staff','staff_patron','library_denied','global_malformed','sid_denied','foreign_choice','role_upgrade','role_downgrade','revocation','account_disabled','logout','workspace_switch','missing_library','foreign_user_denied','recovery_not_revocation'])
def test_authorization_invalidation_matrix(scopes,database,case):
 lid,other,worker,ctx,api=scopes;who=actor();reason='Requested operation denied; other owned scopes remain authorized.'
 if case in ['staff_patron','role_downgrade']:
  set_role(lid,'LIBRARIAN');ctx['STAFF']=context(worker,lid,who,True)
  # Remove historically invalid patron A before this independent staff setup.
  collection().delete_many({'_id':{'$in':[ctx['A']['sid'],ctx['A']['cid']]}})
  profiles._cache.pop((who['sub'],who['sid'],lid,False,'saved-canonical-v1'),None)
  ctx.pop('A')
 if case=='role_upgrade':
  set_role(lid,'LIBRARIAN');ctx['STAFF']=context(worker,lid,who,True)
 if case=='role_downgrade':
  set_role(lid,'GENERAL_USER');ctx['A']=context(worker,lid,who)
 if case=='revocation':revoke(lid)
 if case=='account_disabled':database.users.update_one({'user_id':2},{'$set':{'is_active':False}})
 if case=='recovery_not_revocation':database.institution_lending_config.update_one({'library_id':lid},{'$set':{'state':'RECOVERY_REQUIRED'}},upsert=True)
 before=capture();params={'q':'neur','library_id':lid,'staff':'true'};headers={};request=dict(params)
 if case=='staff_patron' or case=='role_upgrade':params['staff']='false'
 elif case=='library_denied':params['library_id']=str(uuid4())
 elif case=='missing_library':params['library_id']='not-a-uuid'
 elif case=='sid_denied':headers={'x-sid':'other-login'}
 elif case=='foreign_user_denied':headers={'x-user':'3'}
 elif case in ['account_disabled','recovery_not_revocation']:params['staff']='false'
 if case=='global_malformed':
  response=api.post('/query/resolve',json={'clarification_id':'invalid'});status=response.status_code;request={'scope':'GLOBAL','operation':'malformed choice'}
 elif case=='foreign_choice':
  response=api.post('/query/resolve',json={**ctx['A']['body'],'staff':True});status=response.status_code
 elif case=='logout':
  invalidate(who);profiles.invalidate(who);status=200;request={'operation':'existing explicit account-wide logout cleanup'};reason='Accepted explicit logout policy removes all scopes/sids for this account only.'
 elif case=='workspace_switch':
  response=api.get('/query/suggestions',params={'q':'neur','library_id':other},headers=headers);status=response.status_code;request={'library_id':other,'workspace':'PATRON'}
 else:
  response=api.get('/query/suggestions',params=params,headers=headers);status=response.status_code;request=dict(params)
 after=capture()
 if case in ['patron_staff','staff_patron','foreign_choice','sid_denied','library_denied','foreign_user_denied','global_malformed','workspace_switch','missing_library','recovery_not_revocation']:
  assert before==after
  assert status in ([200] if case=='workspace_switch' else [422] if case in ['global_malformed','missing_library'] else [503] if case=='recovery_not_revocation' else [403,404])
 elif case in ['role_upgrade','role_downgrade']:
  lost='A' if case=='role_upgrade' else 'STAFF';kept='STAFF' if case=='role_upgrade' else 'A'
  assert status==403;absent(ctx[lost],after);unchanged_scope(ctx[kept],before,after)
  reason='Fresh canonical role check denies only the former workspace for this exact login.'
 elif case in ['revocation','account_disabled']:
  assert status==(404 if case=='revocation' else 401);absent(ctx['A'],after)
  reason='Fresh canonical membership removed/account disabled; only this login and affected library ownership tuples cleared.'
 elif case=='logout':
  for key in ['A','B','GLOBAL','S2']:absent(ctx[key],after)
  unchanged_scope(ctx['OTHER_USER'],before,after)
 if case not in ['logout']:
  for key in ['B','GLOBAL','OTHER_USER']:unchanged_scope(ctx[key],before,after)
 if case not in ['logout','sid_denied']:unchanged_scope(ctx['S2'],before,after)
 removed=set()
 if case in ['role_upgrade','revocation','account_disabled']:
  removed={repr((who['sub'],who['sid'],lid,False,'saved-canonical-v1'))}
 elif case=='role_downgrade':removed={repr((who['sub'],who['sid'],lid,True,'saved-canonical-v1'))}
 elif case=='logout':removed={k for k in before['profiles'] if k.startswith("('2',")}
 assert after['profiles']=={k:v for k,v in before['profiles'].items() if k not in removed}
 record(case,before,after,status,request,reason)

@pytest.mark.parametrize('during',['search','resolution','revocation','role_change','logout'])
def test_denial_interleaving_never_erases_newer_authorized_state(scopes,monkeypatch,during):
 lid,other,worker,ctx,api=scopes;entered=Event();release=Event()
 import search.scope_authorization as scope_auth
 original=scope_auth.invalidate_if_access_lost
 def paused(*args,**kwargs):
  entered.set();assert release.wait(15),'Interleaving timed out';return original(*args,**kwargs)
 monkeypatch.setattr(scope_auth,'invalidate_if_access_lost',paused)
 before=capture()
 with ThreadPoolExecutor(max_workers=1) as pool:
  future=pool.submit(api.get,'/query/suggestions',params={'q':'neur','library_id':lid,'staff':'true'})
  assert entered.wait(10)
  try:
   if during=='search':tenant_search(worker,lid,actor(),'rating above 3',session_id=ctx['A']['sid'])
   elif during=='resolution':assert api.post('/query/resolve',json=ctx['A']['body']).status_code==200
   elif during=='revocation':revoke(lid)
   elif during=='role_change':set_role(lid,'LIBRARIAN');ctx['STAFF']=context(worker,lid,actor(),True)
   else:invalidate(actor());profiles.invalidate(actor())
   committed=capture()
  finally:release.set()
  response=future.result(timeout=20);assert response.status_code==403
 after=capture()
 if during in ['search','resolution','role_change','logout']:assert after==committed
 else:absent(ctx['A'],after)
 if during!='logout':
  for key in ['B','GLOBAL','S2','OTHER_USER']:unchanged_scope(ctx[key],before,after)
 else:assert not any(r['user_id']=='2' for r in after['accepted']+after['pending'])
 record('interleaved_'+during,before,after,response.status_code,{'library_id':lid,'workspace':'STAFF'},'Fresh authority after deterministic interleaving; only inaccessible exact ownership tuple may be deleted.')
