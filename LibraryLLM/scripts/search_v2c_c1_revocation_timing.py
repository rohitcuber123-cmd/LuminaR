"""Measure fresh canonical revocation cleanup using only disposable QA membership."""
import json,time,statistics
from pathlib import Path
from uuid import uuid4
import httpx
from jose import jwt
from backend.database.mongodb import db
from backend.schemas.institutions import MembershipChange
from backend.services.institution_service import change_membership
from backend.utils.jwt_utils import create_access_token,JWT_SECRET_KEY,JWT_ALGORITHM
from search.scope_authorization import invalidate_if_access_lost
R=Path('reports');f=json.loads((R/'search_v2c_c1_fixture.json').read_text());assert f['qa_owned'] and f['member_id']==494
lid=f['library_id'];u=db.users.find_one({'user_id':494});token=create_access_token(494,u['email'],u['role']);actor=jwt.decode(token,JWT_SECRET_KEY,algorithms=[JWT_ALGORITHM]);c=db.search_sessions_v2b
api=httpx.Client(base_url='http://127.0.0.1:8003',headers={'Authorization':'Bearer '+token},timeout=30)
membership=db.institution_memberships.find_one({'library_id':lid,'user_id':494});assert membership['status']=='ACTIVE'
samples=[];evidence=[]
try:
 for _ in range(30):
  sid=str(uuid4());params={'session_id':sid,'search':'books about neural networks'};api.get('/libraries/'+lid+'/catalogue/search',params=params).raise_for_status()
  api.get('/libraries/'+lid+'/catalogue/search',params={**params,'search':'include Romance but exclude Romance'}).raise_for_status()
  owned={'user_id':'494','login_session':actor['sid'],'library_id':lid,'workspace':'PATRON'};before=list(c.find(owned));assert len(before)==2
  change_membership(lid,membership['membership_id'],MembershipChange(status='REMOVED'),{'sub':'4'})
  start=time.perf_counter();assert invalidate_if_access_lost(actor,lid);elapsed=(time.perf_counter()-start)*1000
  assert not c.find_one(owned);samples.append(elapsed);evidence.append({'before_ids':[r['_id'] for r in before],'after_count':0,'elapsed_ms':elapsed})
  change_membership(lid,membership['membership_id'],MembershipChange(status='ACTIVE'),{'sub':'4'})
finally:
 change_membership(lid,membership['membership_id'],MembershipChange(status='ACTIVE'),{'sub':'4'})
 c.delete_many({'user_id':'494','login_session':actor['sid']})
d={'n':len(samples),'p50_ms':statistics.median(samples),'p95_ms':sorted(samples)[int(.95*len(samples))-1],'samples_ms':samples,'evidence':evidence,'method':'Direct exact-scope helper including existing library lock, fresh canonical guards and Mongo deletion. Each iteration starts with real API-created accepted and pending rows, then normal membership removal. Only disposable QA494 membership toggled; restored ACTIVE. No prepatch revocation timing captured.'}
(R/'search_v2c_c1_revocation_measurements.json').write_text(json.dumps(d,indent=2));print(json.dumps({k:d[k] for k in ['n','p50_ms','p95_ms']}))
