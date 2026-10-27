"""Named disposable browser accounts/library. Never changes an existing account.

Only synthetic fixture identities are deactivated during cleanup. Passwords and
access codes are generated in memory and are never written to reports or files.
"""
import json
from pathlib import Path
import secrets
import sys
from uuid import uuid4
import httpx
from backend.database.mongodb import db
from backend.services import auth_service, institution_service
from backend.schemas.institutions import MembershipChange
from backend.utils.jwt_utils import create_access_token

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT/'reports/search_v2b_browser_fixture.json'
TEST = 'e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'

def account(label):
    email='v2b-'+label.lower()+'-'+uuid4().hex[:12]+'@example.com'
    password=secrets.token_urlsafe(24)
    mail={};send=auth_service.send_otp_email
    try:
        auth_service.send_otp_email=lambda address,name,otp:mail.update({address:otp}) or True
        user=auth_service.register_user('V2B Browser '+label,email,password)
        assert user and auth_service.verify_email_otp(email,mail.pop(email))
    finally:
        auth_service.send_otp_email=send
    return {**user,'password':password}

def create():
    assert not PATH.exists(), 'Review existing fixture evidence before creating more accounts.'
    owner=db.users.find_one({'user_id':4})
    token=create_access_token(4,owner['email'],owner['role'])
    client=httpx.Client(base_url='http://127.0.0.1:8002',headers={'Authorization':'Bearer '+token},timeout=60)
    member,outsider=account('Member'),account('Outsider')
    code=secrets.token_urlsafe(24)
    r=client.post('/libraries/register',json={'name':'V2B Disposable Private Search QA',
        'slug':'v2b-search-qa-'+uuid4().hex[:12], 'library_type':'PRIVATE_INSTITUTION',
        'access_mode':'PRIVATE_CODE','access_code':code})
    assert r.status_code==201,r.text
    lid=r.json()['library']['library_id']
    fixture={'qa_owned':True,'private_library_id':lid,'public_library_id':TEST,
             'member_id':member['user_id'],'outsider_id':outsider['user_id'],'book_ids':[],'status':'ACTIVE_FOR_QA'}
    PATH.write_text(json.dumps(fixture,indent=2),encoding='utf8')
    for title,subjects in [('V2B Archive Networks primer',['Computer networks','Private V2B Orchid']),
                           ('V2B Archive Systems handbook',['Computer networks','Private V2B Orchid','Distributed systems']),
                           ('V2B Archive Literature',['Literature'])]:
        r=client.post(f'/libraries/{lid}/inventory/books',json={'title':title,'subjects':subjects,
            'authors':['Synthetic QA Archivist'],'description':'A beginner introduction to computer networks and archive systems.',
            'create_physical_holding':True,'copies':2,'shelf_location':'V2B-QA-ONLY','idempotency_key':str(uuid4())})
        assert r.status_code==201,r.text
        fixture['book_ids'].append(r.json()['library_book_id'])
        PATH.write_text(json.dumps(fixture,indent=2),encoding='utf8')
    member_token=create_access_token(member['user_id'],member['email'],member['role'])
    for library,body in [(TEST,{}),(lid,{'access_code':code})]:
        r=client.post(f'/libraries/{library}/join',json=body,headers={'Authorization':'Bearer '+member_token})
        assert r.status_code==200,r.text
    from backend.services.reading_list_service import add_to_reading_list
    add_to_reading_list(member['user_id'],f'local:{lid}:{fixture["book_ids"][0]}')
    add_to_reading_list(member['user_id'],'OL19545719W')
    PATH.write_text(json.dumps(fixture,indent=2),encoding='utf8')
    print(json.dumps({'member':{k:member[k] for k in ('user_id','email','password')},
                      'outsider':{k:outsider[k] for k in ('user_id','email','password')},'fixture':fixture}))
    client.close()

def finish(revoke_only=False):
    fixture=json.loads(PATH.read_text())
    assert fixture['qa_owned'] and db.institution_libraries.find_one({'library_id':fixture['private_library_id'],'name':'V2B Disposable Private Search QA'})
    member=fixture['member_id']
    membership=db.institution_memberships.find_one({'library_id':fixture['private_library_id'],'user_id':member})
    if membership['status']=='ACTIVE':
        institution_service.change_membership(fixture['private_library_id'],membership['membership_id'],MembershipChange(status='REMOVED'),{'sub':'4'})
    fixture['membership_revoked']=True
    if not revoke_only:
        for uid in (fixture['member_id'],fixture['outsider_id']):
            user=db.users.find_one({'user_id':uid})
            assert user and user['name'].startswith('V2B Browser ') and user['email'].startswith('v2b-')
            db.users.update_one({'user_id':uid},{'$set':{'is_active':False}})
            db.reading_list.delete_many({'user_id':uid})
            db.search_sessions_v2b.delete_many({'user_id':str(uid)})
        db.institution_memberships.update_many({'user_id':{'$in':[fixture['member_id'],fixture['outsider_id']]}},{'$set':{'status':'REMOVED'}})
        db.institution_libraries.update_one({'library_id':fixture['private_library_id']},{'$set':{'status':'ARCHIVED'}})
        fixture['status']='CLEANED: synthetic accounts disabled, memberships removed, synthetic library archived, synthetic saves and sessions cleared'
    PATH.write_text(json.dumps(fixture,indent=2),encoding='utf8')
    print(json.dumps({'status':fixture['status'],'membership_revoked':True}))

if __name__=='__main__':
    assert db.name=='luminar_library'
    if sys.argv[1]=='create':create()
    elif sys.argv[1]=='revoke':finish(True)
    elif sys.argv[1]=='cleanup':finish()
