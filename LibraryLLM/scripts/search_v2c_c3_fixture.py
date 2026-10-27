"""Disposable V2C-C.3 browser fixture through normal account/library/inventory APIs."""
import json
import secrets
import sys
from pathlib import Path
from uuid import uuid4

import httpx

from backend.database.mongodb import db
from backend.schemas.institutions import MembershipChange
from backend.services import auth_service, institution_service
from backend.utils.jwt_utils import create_access_token

PATH = Path(__file__).resolve().parents[1]/'reports/search_v2c_c3_fixture.json'
TEST = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'


def account(label):
    email='v2ccr-'+label.lower()+'-'+uuid4().hex[:10]+'@example.com'
    password=secrets.token_urlsafe(24)
    mail={};send=auth_service.send_otp_email
    try:
        auth_service.send_otp_email=lambda address,name,otp:mail.update({address:otp}) or True
        user=auth_service.register_user('V2CCR Browser '+label,email,password)
        assert user and auth_service.verify_email_otp(email,mail.pop(email))
    finally:
        auth_service.send_otp_email=send
    return {**user,'password':password}


def create():
    assert not PATH.exists()
    owner=db.users.find_one({'user_id':4});token=create_access_token(4,owner['email'],owner['role'])
    client=httpx.Client(base_url='http://127.0.0.1:8002',headers={'Authorization':'Bearer '+token},timeout=60)
    member,outsider=account('Member'),account('Outsider');code=secrets.token_urlsafe(24)
    response=client.post('/libraries/register',json={'name':'V2CCR Clause QA','slug':'v2ccr-qa-'+uuid4().hex[:10],
        'library_type':'PRIVATE_INSTITUTION','access_mode':'PRIVATE_CODE','access_code':code})
    response.raise_for_status();lid=response.json()['library']['library_id']
    f={'qa_owned':True,'library_id':lid,'public_library_id':TEST,'member_id':member['user_id'],
       'outsider_id':outsider['user_id'],'book_ids':[],'status':'ACTIVE'}
    PATH.write_text(json.dumps(f,indent=2),encoding='utf8')
    for title,subjects,work in [('V2CCR Wizards Fiction',['Fiction','Wizards','Neural Networks','V2CCR Private Orchid'],'OL109579W'),
        ('V2CCR Romance',['Romance','V2CCR Private Orchid'],None),
        ('V2CCR Mystery Fiction',['Fiction','Mystery','Detective Fiction','V2CCR Private Orchid'],'OL17918479W')]:
        body={'title':title,'authors':['Synthetic A1 Author'],'subjects':subjects,'description':'Synthetic wizards clause composition QA book.',
              'publication_year':2021,'create_physical_holding':True,'copies':2,'shelf_location':'V2CCR-QA','idempotency_key':str(uuid4())}
        if work:
            assert db.books.find_one({'work_id':work})
            body['global_work_id']=work
        response=client.post(f'/libraries/{lid}/inventory/books',json=body);response.raise_for_status()
        f['book_ids'].append(response.json()['library_book_id']);PATH.write_text(json.dumps(f,indent=2),encoding='utf8')
    mtoken=create_access_token(member['user_id'],member['email'],member['role'])
    for library,body in [(TEST,{}),(lid,{'access_code':code})]:
        response=client.post(f'/libraries/{library}/join',json=body,headers={'Authorization':'Bearer '+mtoken});response.raise_for_status()
    print(json.dumps({'member':{k:member[k] for k in ('user_id','email','password')},
                      'outsider':{k:outsider[k] for k in ('user_id','email','password')},'fixture':f}))


def finish(cleanup=False):
    f=json.loads(PATH.read_text());assert f['qa_owned']
    assert db.institution_libraries.find_one({'library_id':f['library_id'],'name':'V2CCR Clause QA'})
    m=db.institution_memberships.find_one({'library_id':f['library_id'],'user_id':f['member_id']})
    if m['status']=='ACTIVE':
        institution_service.change_membership(f['library_id'],m['membership_id'],MembershipChange(status='REMOVED'),{'sub':'4'})
    f['membership_revoked']=True
    if cleanup:
        for uid in [f['member_id'],f['outsider_id']]:
            user=db.users.find_one({'user_id':uid});assert user['name'].startswith('V2CCR Browser ')
            db.users.update_one({'user_id':uid},{'$set':{'is_active':False}})
            db.search_sessions_v2b.delete_many({'user_id':str(uid)})
        db.institution_memberships.update_many({'user_id':{'$in':[f['member_id'],f['outsider_id']]}},{'$set':{'status':'REMOVED'}})
        db.search_sessions_v2b.delete_many({'library_id':f['library_id']})
        db.institution_libraries.update_one({'library_id':f['library_id']},{'$set':{'status':'ARCHIVED'}})
        f['status']='CLEANED: disposable accounts disabled, memberships removed, QA library archived, QA sessions cleared'
    PATH.write_text(json.dumps(f,indent=2),encoding='utf8');print(json.dumps(f))


if __name__=='__main__':
    assert db.name=='luminar_library'
    if sys.argv[1]=='create':create()
    elif sys.argv[1]=='revoke':finish()
    elif sys.argv[1]=='cleanup':finish(True)

