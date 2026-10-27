"""Disposable normal-service browser fixtures; credentials stay in memory/output."""
import json,secrets,sys
from pathlib import Path
from uuid import uuid4
import httpx
from backend.database.mongodb import db
from backend.services import auth_service,institution_service
from backend.schemas.institutions import MembershipChange
from backend.utils.jwt_utils import create_access_token
ROOT=Path(__file__).resolve().parents[1];PATH=ROOT/'reports/search_v2c_a_browser_fixture.json'
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
def account(label):
 email='v2ca-'+label.lower()+'-'+uuid4().hex[:10]+'@example.com';password=secrets.token_urlsafe(24)
 mail={};send=auth_service.send_otp_email
 try:
  auth_service.send_otp_email=lambda address,name,otp:mail.update({address:otp}) or True
  user=auth_service.register_user('V2CA Browser '+label,email,password)
  assert user and auth_service.verify_email_otp(email,mail.pop(email))
 finally:auth_service.send_otp_email=send
 return {**user,'password':password}
def create():
 assert not PATH.exists(),'Do not duplicate fixtures'
 owner=db.users.find_one({'user_id':4});token=create_access_token(4,owner['email'],owner['role'])
 client=httpx.Client(base_url='http://127.0.0.1:8002',headers={'Authorization':'Bearer '+token},timeout=60)
 candidates=httpx.post('http://127.0.0.1:8003/search',headers={'Authorization':'Bearer '+token},json={'query':'fiction rated above 3','limit':2,'save_history':False},timeout=60)
 candidates.raise_for_status();works=[r['work_id'] for r in candidates.json()['results']];assert len(works)==2
 member,outsider=account('Member'),account('Outsider');code=secrets.token_urlsafe(24)
 r=client.post('/libraries/register',json={'name':'V2CA Compositional Search QA','slug':'v2ca-qa-'+uuid4().hex[:10],'library_type':'PRIVATE_INSTITUTION','access_mode':'PRIVATE_CODE','access_code':code});r.raise_for_status();lid=r.json()['library']['library_id']
 fixture={'qa_owned':True,'private_library_id':lid,'member_id':member['user_id'],'outsider_id':outsider['user_id'],'public_library_id':TEST,'book_ids':[],'status':'ACTIVE'}
 PATH.write_text(json.dumps(fixture,indent=2),encoding='utf8')
 for i,title in enumerate(['V2CA Fiction Wizards primer','V2CA Fiction Dragons guide','V2CA Python 3 for beginners']):
  body={'title':title,'authors':['Synthetic QA Author'],'subjects':['Fiction','Wizards','V2CA Private Orchid'] if i<2 else ['Computer science'],
        'description':'A synthetic beginner guide to wizards, dragons and artificial intelligence for private catalogue QA.',
        'publication_year':2021,'create_physical_holding':True,'copies':2,'shelf_location':'V2CA-QA-ONLY','idempotency_key':str(uuid4())}
  if i<2:body['global_work_id']=works[i]
  r=client.post(f'/libraries/{lid}/inventory/books',json=body);r.raise_for_status();fixture['book_ids'].append(r.json()['library_book_id'])
  PATH.write_text(json.dumps(fixture,indent=2),encoding='utf8')
 mtoken=create_access_token(member['user_id'],member['email'],member['role'])
 for library,body in [(TEST,{}),(lid,{'access_code':code})]:
  r=client.post(f'/libraries/{library}/join',json=body,headers={'Authorization':'Bearer '+mtoken});r.raise_for_status()
 from backend.services.reading_list_service import add_to_reading_list
 add_to_reading_list(member['user_id'],works[0]);add_to_reading_list(member['user_id'],f'local:{lid}:{fixture["book_ids"][2]}')
 print(json.dumps({'member':{k:member[k] for k in ('user_id','email','password')},'outsider':{k:outsider[k] for k in ('user_id','email','password')},'fixture':fixture}))
def finish(revoke_only=False):
 f=json.loads(PATH.read_text());assert f['qa_owned'] and db.institution_libraries.find_one({'library_id':f['private_library_id'],'name':'V2CA Compositional Search QA'})
 m=db.institution_memberships.find_one({'library_id':f['private_library_id'],'user_id':f['member_id']})
 if m['status']=='ACTIVE':institution_service.change_membership(f['private_library_id'],m['membership_id'],MembershipChange(status='REMOVED'),{'sub':'4'})
 f['membership_revoked']=True
 if not revoke_only:
  for uid in (f['member_id'],f['outsider_id']):
   user=db.users.find_one({'user_id':uid});assert user['name'].startswith('V2CA Browser ') and user['email'].startswith('v2ca-')
   db.users.update_one({'user_id':uid},{'$set':{'is_active':False}});db.reading_list.delete_many({'user_id':uid});db.search_sessions_v2b.delete_many({'user_id':str(uid)})
  db.institution_memberships.update_many({'user_id':{'$in':[f['member_id'],f['outsider_id']]}},{'$set':{'status':'REMOVED'}})
  db.institution_libraries.update_one({'library_id':f['private_library_id']},{'$set':{'status':'ARCHIVED'}})
  f['status']='CLEANED: QA users disabled, memberships removed, private QA library archived, QA saves/sessions cleared'
 PATH.write_text(json.dumps(f,indent=2),encoding='utf8');print(json.dumps({'status':f['status'],'revoked':True}))
if __name__=='__main__':
 assert db.name=='luminar_library'
 if sys.argv[1]=='create':create()
 elif sys.argv[1]=='revoke':finish(True)
 elif sys.argv[1]=='cleanup':finish()
