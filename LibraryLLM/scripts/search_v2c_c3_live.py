"""Fresh live security preflight; no benchmark evaluation or parser mutation."""
import json,hashlib
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone
import httpx
from jose import jwt
from backend.database.mongodb import db
from backend.schemas.institutions import MembershipChange
from backend.services.institution_service import change_membership
from backend.utils.jwt_utils import create_access_token,JWT_SECRET_KEY,JWT_ALGORITHM
R=Path('reports');f=json.loads((R/'search_v2c_c3_fixture.json').read_text());lid=f['library_id'];uid=f['member_id'];c=db.search_sessions_v2b
u=db.users.find_one({'user_id':uid});t=create_access_token(uid,u['email'],u['role']);actor=jwt.decode(t,JWT_SECRET_KEY,algorithms=[JWT_ALGORITHM]);owner={'user_id':str(uid),'login_session':actor['sid']}
api=httpx.Client(base_url='http://127.0.0.1:8003',headers={'Authorization':'Bearer '+t},timeout=60)
ids={scope:str(uuid4()) for scope in ['GLOBAL','PUBLIC','PRIVATE']}
api.post('/search',json={'query':'books about stars','session_id':ids['GLOBAL'],'save_history':False}).raise_for_status()
for scope,library in [('PUBLIC',f['public_library_id']),('PRIVATE',lid)]:api.get('/libraries/'+library+'/catalogue/search',params={'search':'books about neural networks','session_id':ids[scope]}).raise_for_status()
q='include Romance but exclude Romance';res=api.get('/libraries/'+lid+'/catalogue/search',params={'search':q,'session_id':ids['PRIVATE']});res.raise_for_status();ch=res.json()['interpretation']['clarification'];body={'query':q,'session_id':ids['PRIVATE'],'library_id':lid,'clarification_id':ch['clarification_id'],'choice_id':ch['candidate_choices'][0]['choice_id']}
before=list(c.find(owner).sort('_id'));denial=api.get('/query/suggestions',params={'q':'neur','library_id':lid,'staff':True});after=list(c.find(owner).sort('_id'));assert denial.status_code==403 and before==after
forged=api.post('/query/resolve',json={**body,'choice_id':str(uuid4())});after_forged=list(c.find(owner).sort('_id'));assert forged.status_code==404 and after_forged==before
valid=api.post('/query/resolve',json=body);valid.raise_for_status();accepted=c.find_one({'_id':ids['PRIVATE']});prior=next(r for r in before if r['_id']==ids['PRIVATE']);assert accepted['version']==prior['version']+1
before_revocation=list(c.find(owner).sort('_id'));m=db.institution_memberships.find_one({'library_id':lid,'user_id':uid});change_membership(lid,m['membership_id'],MembershipChange(status='REMOVED'),{'sub':'4'})
try:
 revoked=api.get('/query/suggestions',params={'q':'neur','library_id':lid});after_revocation=list(c.find(owner).sort('_id'));assert revoked.status_code==404
 assert not any(r.get('library_id')==lid for r in after_revocation)
 assert after_revocation==[r for r in before_revocation if r.get('library_id')!=lid]
finally:change_membership(lid,m['membership_id'],MembershipChange(status='ACTIVE'),{'sub':'4'})
o=db.users.find_one({'user_id':f['outsider_id']});ot=create_access_token(o['user_id'],o['email'],o['role']);outsider=[]
for path,params in [('/query/suggestions',{'q':'neur','library_id':lid}),('/libraries/'+lid+'/catalogue/search',{'search':q}),('/libraries/'+lid+'/catalogue/search',{'search':'V2CCR Private Orchid','staff':True})]:
 r=httpx.get('http://127.0.0.1:8003'+path,params=params,headers={'Authorization':'Bearer '+ot},timeout=30);assert r.status_code==404 and r.json()=={'detail':'Library resource not found.'};outsider.append({'path':path,'status':r.status_code,'body':r.json()})
health=api.get('/health');health.raise_for_status();count=db.books.count_documents({});assert count==5000000
d={'result':'PASS','observed_at':datetime.now(timezone.utc).isoformat(),'database':db.name,'count':count,'health':health.json(),'owner':owner,'library_id':lid,'before':before,'after_denial':after,'denial_status':denial.status_code,'after_forged':after_forged,'forged_status':forged.status_code,'valid_after_forged_status':valid.status_code,'valid_accepted':accepted,'before_revocation':before_revocation,'after_revocation':after_revocation,'revocation_status':revoked.status_code,'outsider_requests':outsider,'observed_private_leaks':0,'source_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in map(Path,['search/scope_authorization.py','search/session_store.py','search/interaction_api.py','search/query_execution.py','search/personalization.py'])},'fixture_membership_restored_for_authorized_continuation':True}
(R/'search_v2c_c3_preflight_live.json').write_text(json.dumps(d,indent=2,default=str));print(json.dumps({'result':'PASS','denial':403,'forged':404,'valid':200,'revoked':404,'private_leaks':0,'count':count}))
