"""Actual Mongo authority, restricted reads and shared delivery regressions."""
from uuid import uuid4
import pytest
from backend.services import library_announcement_service as service
from backend.services.institution_repository import now
def headers(uid): return {'x-test-user':str(uid)}
def draft(client,lib,uid=1,**fields):
    body={'title':'Library update','body':'A safe member message.','request_id':str(uuid4()),**fields}
    r=client.post(f'/libraries/{lib}/announcements',headers=headers(uid),json=body)
    assert r.status_code==201,r.text
    return r.json()
def action(client,lib,row,op='publish',uid=1,code=200):
    r=client.post(f'/libraries/{lib}/announcements/{row["announcement_id"]}/{op}',headers=headers(uid),json={'revision':row['revision']})
    assert r.status_code==code,r.text
    return r.json()
def member(database,lib,uid=6,**values):
    database.institution_memberships.insert_one({'library_id':lib,'user_id':uid,'membership_id':str(uuid4()),'status':'ACTIVE','role':'GENERAL_USER',**values})
def inbox(client,uid=2):return client.get('/notifications',headers=headers(uid)).json()
def dispatch(lib,row,limit=100):return service.deliver_one(lib,row['announcement_id'],limit)



def targeted(client,lib,uid=2,**fields):
    return draft(client,lib,audience='SPECIFIC_MEMBER',recipient_user_id=uid,**fields)

def search(client,lib,q='User',uid=1,extra=''):
    return client.get(f'/libraries/{lib}/staff/announcement-recipients',headers=headers(uid),params={'q':q,'limit':10,**extra} if isinstance(extra,dict) else {'q':q,'limit':10})

def test_single_recipient_delivery_visibility_and_read(client,setup,libraries,database):
    other=libraries(owner=5);member(database,other,6)
    row=targeted(client,setup);published=action(client,setup,row)
    assert published['audience']=='SPECIFIC_MEMBER' and published['delivery']['total']==1
    assert published['recipient']['user_id']==2
    assert dispatch(setup,row)['delivered']==1
    assert dispatch(setup,row)['delivered']==0
    assert database.notifications.count_documents({})==1
    assert database.notifications.find_one({})['user_id']==2
    path=f'/libraries/{setup}/announcements/{row["announcement_id"]}'
    for uid in [1,3,4,5,6,9]:
        assert client.get(path,headers=headers(uid)).status_code==404
        if uid in [1,3,4]:assert client.get(f'/libraries/{setup}/announcements',headers=headers(uid)).json()['total']==0
        assert inbox(client,uid)['count']==0
        assert client.get('/notifications/unread-count',headers=headers(uid)).json()['unread_count']==0
    assert client.get(path,headers=headers(2)).status_code==200
    assert client.get(f'/libraries/{setup}/staff/announcements/{row["announcement_id"]}').status_code==200
    notices=inbox(client,2);assert notices['count']==1 and notices['unread_count']==1
    n=notices['notifications'][0];assert n['action_route']==path
    assert client.patch('/notifications/'+n['notification_id']+'/read',headers=headers(2)).status_code==200
    assert inbox(client,2)['unread_count']==0
    assert action(client,setup,row)['delivery']['total']==1
    assert database.notifications.count_documents({})==1

def test_counts_filter_before_pagination_and_all_members_unchanged(client,setup):
    private=targeted(client,setup);action(client,setup,private)
    public=draft(client,setup);assert action(client,setup,public)['delivery']['total']==4
    for uid,count in [(2,2),(3,1),(4,1)]:
        page=client.get(f'/libraries/{setup}/announcements?limit=1',headers=headers(uid)).json()
        assert page['total']==count and len(page['results'])==1 and page['has_more']==(count>1)
    assert client.get(f'/libraries/{setup}/staff/announcements').json()['total']==2

@pytest.mark.parametrize('state',['REVOKED','REMOVED','SUSPENDED','DISABLED','UNVERIFIED','SETUP','LEGACY_SETUP','BAD_PROOF','UNKNOWN','OTHER_LIBRARY'])
@pytest.mark.parametrize('stage',['save','publish','delivery'])
def test_recipient_revalidated_each_stage(client,setup,libraries,database,state,stage):
    row=targeted(client,setup) if stage!='save' else None
    if stage=='delivery':action(client,setup,row)
    if state=='DISABLED':database.users.update_one({'user_id':2},{'$set':{'is_active':False}})
    elif state=='UNVERIFIED':database.users.update_one({'user_id':2},{'$set':{'is_email_verified':False}})
    elif state in ['SETUP','LEGACY_SETUP']:database.users.update_one({'user_id':2},{'$set':{'password_setup_required':True if state=='SETUP' else 'required'}})
    elif state=='UNKNOWN':database.users.delete_one({'user_id':2})
    elif state=='BAD_PROOF':database.institution_memberships.update_one({'user_id':2,'library_id':setup},{'$set':{'grant_invitation_id':str(uuid4())}})
    elif state=='OTHER_LIBRARY':
        database.institution_memberships.delete_one({'user_id':2,'library_id':setup});member(database,libraries(owner=5),2)
    else:database.institution_memberships.update_one({'user_id':2,'library_id':setup},{'$set':{'status':state}})
    if stage=='save':
        response=client.post(f'/libraries/{setup}/announcements',json={'title':'Private message','body':'Only selected member','request_id':str(uuid4()),'audience':'SPECIFIC_MEMBER','recipient_user_id':2})
        assert response.status_code==422,response.text
    elif stage=='publish':action(client,setup,row,code=409)
    else:
        result=dispatch(setup,row);assert result['suppressed']==1 and result['delivered']==0
    assert database.notifications.count_documents({})==0
    assert all(r['user_id']!=2 for r in search(client,setup).json()['results'])

@pytest.mark.parametrize('fields',[
    {'audience':'SPECIFIC_MEMBER'}, {'audience':'SPECIFIC_MEMBER','recipient_user_id':None},
    {'audience':'SPECIFIC_MEMBER','recipient_user_id':True}, {'audience':'SPECIFIC_MEMBER','recipient_user_id':'2'},
    {'audience':'SPECIFIC_MEMBER','recipient_user_id':0}, {'audience':'SPECIFIC_MEMBER','recipient_user_id':-2},
    {'audience':'SPECIFIC_MEMBER','recipient_user_id':2**64}, {'audience':'SPECIFIC_MEMBER','recipient_user_id':99999},
    {'audience':'ALL_ACTIVE_MEMBERS','recipient_user_id':2}, {'audience':'ALL'},
    {'audience':'SPECIFIC_MEMBER','recipient_user_id':2,'recipient_email':'part2p-2@example.com'},
    {'audience':'SPECIFIC_MEMBER','recipient_user_ids':[2,4]}, {'recipient_emails':['part2p-2@example.com']},
])
def test_forged_scope_identity_no_fallback(client,setup,database,fields):
    r=client.post(f'/libraries/{setup}/announcements',json={'title':'Selected member','body':'Private text','request_id':str(uuid4()),**fields})
    assert r.status_code==422,r.text
    assert service.records().count_documents({})==0 and database.notifications.count_documents({})==0

@pytest.mark.parametrize('uid',[2,3,4,5,9,10])
@pytest.mark.parametrize('operation',['search','create','edit','publish'])
def test_no_implicit_admin_or_platform_authority(client,setup,libraries,database,uid,operation):
    libraries(owner=5)
    database.platform_role_assignments.insert_one({'user_id':10,'role':'PLATFORM_ADMIN','status':'ACTIVE'})
    row=targeted(client,setup);base=f'/libraries/{setup}'
    if operation=='search':r=search(client,setup,uid=uid)
    elif operation=='create':r=client.post(base+'/announcements',headers=headers(uid),json={'title':'Denied message','body':'Denied','request_id':str(uuid4()),'audience':'SPECIFIC_MEMBER','recipient_user_id':2})
    elif operation=='edit':r=client.patch(base+'/announcements/'+row['announcement_id'],headers=headers(uid),json={'title':'Denied message','body':'Denied','revision':0,'audience':'SPECIFIC_MEMBER','recipient_user_id':2})
    else:r=client.post(base+'/announcements/'+row['announcement_id']+'/publish',headers=headers(uid),json={'revision':0})
    assert r.status_code in [403,404],r.text

def test_search_names_emails_literal_bounded_and_no_global_directory(client,setup,libraries,database):
    member(database,libraries(owner=5),6)
    database.users.update_one({'user_id':2},{'$set':{'name':'Ada Member','email':'ada.member@example.com'}})
    for q in ['Ada','ADA.MEMBER@EXAMPLE.COM','member@example']:
        result=search(client,setup,q).json();assert result['library_id']==setup
        assert result['results']==[{'user_id':2,'name':'Ada Member','email':'ada.member@example.com'}]
        assert 'total' not in result
    assert search(client,setup,'.*').json()['results']==[]
    assert search(client,setup,'part2p-6').json()['results']==[]
    for extra in [{'limit':21},{'limit':0},{'q':'x'},{'q':'x'*121}]:assert search(client,setup,extra=extra).status_code==422
    page=search(client,setup,'User',extra={'limit':1}).json();assert len(page['results'])==1 and page['has_more']
    assert set(page)=={'library_id','results','has_more'}

def test_invitation_proof_and_duplicate_changed_email_use_stable_account(client,setup,database):
    grant=str(uuid4());database.institution_memberships.update_one({'library_id':setup,'user_id':2},{'$set':{'grant_invitation_id':grant}})
    assert search(client,setup,'User 2').json()['results']==[]
    database.institution_invitations.insert_one({'invitation_id':grant,'library_id':setup,'accepted_by_user_id':2,'status':'ACCEPTED'})
    assert search(client,setup,'User 2').json()['results'][0]['user_id']==2
    row=targeted(client,setup)
    database.users.update_one({'user_id':2},{'$set':{'email':'same@example.com'}})
    database.users.update_one({'user_id':4},{'$set':{'email':'same@example.com'}})
    assert {r['user_id'] for r in search(client,setup,'same@example.com').json()['results']}=={2,4}
    action(client,setup,row);dispatch(setup,row)
    assert database.notifications.distinct('user_id')==[2]

def test_draft_retry_edit_explicit_scope_and_immutable_publish(client,setup,database):
    body={'title':'Selected message','body':'Private body','request_id':str(uuid4()),'audience':'SPECIFIC_MEMBER','recipient_user_id':2}
    a=client.post(f'/libraries/{setup}/announcements',json=body);b=client.post(f'/libraries/{setup}/announcements',json=body)
    assert a.json()==b.json();row=a.json();path=f'/libraries/{setup}/announcements/{row["announcement_id"]}'
    assert client.patch(path,json={'title':'Old client','body':'Must not broadcast','revision':0}).status_code==422
    r=client.patch(path,json={'title':'Selected message','body':'Private body','revision':0,'audience':'SPECIFIC_MEMBER','recipient_user_id':4})
    assert r.status_code==200;r=r.json();assert r['recipient_user_id']==4
    action(client,setup,r)
    assert client.patch(path,json={'title':'Broadcast attempt','body':'No','revision':2,'audience':'ALL_ACTIVE_MEMBERS'}).status_code==409
    dispatch(setup,r);assert database.notifications.distinct('user_id')==[4]

@pytest.mark.parametrize('scope',[None,'UNKNOWN','SPECIFIC_MEMBER'])
def test_unknown_stored_scope_fails_closed(client,setup,database,scope):
    row=draft(client,setup);service.records().update_one({'announcement_id':row['announcement_id']},{'$set':{'audience':scope}})
    action(client,setup,row,code=409)
    service.records().update_one({'announcement_id':row['announcement_id']},{'$set':{'status':'PUBLISHED'}})
    assert client.get(f'/libraries/{setup}/announcements/{row["announcement_id"]}',headers=headers(2)).status_code==404
    assert client.get(f'/libraries/{setup}/announcements',headers=headers(2)).json()['total']==0

def test_legacy_all_scope_and_revocation_search(client,setup,database):
    row=draft(client,setup);service.records().update_one({'announcement_id':row['announcement_id']},{'$unset':{'audience':'','recipient_user_id':''}})
    assert action(client,setup,row)['delivery']['total']==4
    assert client.get(f'/libraries/{setup}/announcements',headers=headers(2)).json()['total']==1
    database.institution_memberships.update_one({'library_id':setup,'user_id':1},{'$set':{'status':'REVOKED'}})
    assert search(client,setup).status_code==404

def test_delivery_rejects_wrong_recipient_even_if_snapshot_is_corrupt(client,setup,database):
    row=targeted(client,setup);action(client,setup,row)
    service.records().update_one({'announcement_id':row['announcement_id']},{'$set':{'delivery.recipients':[2,4],'delivery.total':2}})
    result=dispatch(setup,row)
    assert result['delivered']==1 and result['suppressed']==1
    assert database.notifications.distinct('user_id')==[2]

def test_targeted_withdrawal_keeps_generic_receipt_but_removes_content(client,setup,database):
    row=targeted(client,setup);published=action(client,setup,row);dispatch(setup,row)
    withdrawn=action(client,setup,published,'withdraw')
    assert withdrawn['recipient_user_id']==2
    receipt=inbox(client,2)['notifications'][0]
    assert receipt['action_route'] is None and row['body'] not in str(receipt)
    assert client.get(f'/libraries/{setup}/announcements/{row["announcement_id"]}',headers=headers(2)).status_code==404
    assert inbox(client,4)['count']==0

def test_specific_publish_and_delivery_concurrency(client,setup,database):
    from concurrent.futures import ThreadPoolExecutor
    row=targeted(client,setup)
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts=list(pool.map(lambda _:action(client,setup,row),range(2)))
    assert receipts[0]==receipts[1] and receipts[0]['delivery']['total']==1
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:dispatch(setup,row),range(2)))
    assert database.notifications.count_documents({})==1
    assert database.notifications.distinct('user_id')==[2]

def test_current_admin_role_required_even_with_previously_loaded_picker(client,setup,database):
    assert search(client,setup).status_code==200
    row=targeted(client,setup)
    database.institution_memberships.update_one({'library_id':setup,'user_id':1},{'$set':{'role':'LIBRARIAN'}})
    assert search(client,setup).status_code==403
    action(client,setup,row,code=403)
    assert database.notifications.count_documents({})==0
