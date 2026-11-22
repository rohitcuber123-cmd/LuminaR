from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4
import pytest
from backend.services import library_announcement_service as service, notification_service as ns, tenant_notification_service as tn
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

def test_lifecycle_creator_history_and_member_visibility(client,setup,database):
    row=draft(client,setup);url=f'/libraries/{setup}/announcements/{row["announcement_id"]}'
    assert row['status']=='DRAFT' and row['created_by_user_id']==1 and row['published_at'] is None
    assert client.get(url,headers=headers(2)).status_code==404
    assert client.get(f'/libraries/{setup}/announcements',headers=headers(2)).json()['total']==0
    published=action(client,setup,row)
    assert published['delivery']['state']=='PENDING' and published['delivery']['total']==4
    assert client.get(url,headers=headers(2)).json()['body']==row['body']
    assert 'created_by_user_id' not in client.get(url,headers=headers(2)).json()
    repeated=action(client,setup,row)
    assert repeated==published
    withdrawn=action(client,setup,published,'withdraw')
    assert withdrawn['published_at']==published['published_at'] and withdrawn['withdrawn_at']
    assert client.get(url,headers=headers(2)).status_code==404
    assert action(client,setup,published,'withdraw')==withdrawn
    action(client,setup,withdrawn,code=409)

@pytest.mark.parametrize('uid',[2,3,4,5,9,10])
@pytest.mark.parametrize('operation',['create','edit','publish','withdraw','retry','staff_list'])
def test_no_implicit_staff_platform_or_other_tenant_rights(client,setup,libraries,database,uid,operation):
    libraries(owner=5)
    database.platform_role_assignments.insert_one({'user_id':10,'role':'PLATFORM_ADMIN','status':'ACTIVE','approved_by':'fixture','approval_ref':'fixture','approved_at':now()})
    row=draft(client,setup);base=f'/libraries/{setup}'
    if operation=='create':r=client.post(base+'/announcements',headers=headers(uid),json={'title':'Denied','body':'Denied','request_id':str(uuid4())})
    elif operation=='staff_list':r=client.get(base+'/staff/announcements',headers=headers(uid))
    elif operation=='edit':r=client.patch(base+'/announcements/'+row['announcement_id'],headers=headers(uid),json={'title':'Changed','body':'Changed','revision':0})
    else:r=client.post(base+'/announcements/'+row['announcement_id']+'/'+{'retry':'delivery/retry'}.get(operation,operation),headers=headers(uid),json={'revision':0})
    assert r.status_code in [403,404],r.text

@pytest.mark.parametrize('field,value',[
    ('library_id',str(uuid4())),('created_by_user_id',2),('published_at','2026-01-01'),('recipients',[2]),('audience','EVERYONE'),
    ('category','UNSUPPORTED'),('priority','EMERGENCY'),('title','x'*141),('body','x'*5001),('title','  '),('body','  '),
    ('title','<script>alert(1)</script>'),('body','<img src=x onerror=alert(1)>'),('body','hello\x00world'),('body','-----BEGIN RSA PRIVATE KEY----- secret'),('request_id','LIB001')])
def test_input_and_forgery_rejected(client,setup,field,value):
    body={'title':'Safe title','body':'Safe text','request_id':str(uuid4()),field:value}
    assert client.post(f'/libraries/{setup}/announcements',json=body).status_code==422

def test_unauth_expired_and_revoked_session(client,setup):
    from backend.main import app
    from backend.dependencies import get_current_user
    from backend.utils.jwt_utils import create_access_token, decode_access_token, JWT_SECRET_KEY, JWT_ALGORITHM
    from backend.services.login_sessions import revoke
    from jose import jwt
    app.dependency_overrides.pop(get_current_user)
    path=f'/libraries/{setup}/announcements'
    assert client.get(path).status_code in [401,403]
    expired=jwt.encode({'sub':'1','exp':now()-timedelta(seconds=1)},JWT_SECRET_KEY,algorithm=JWT_ALGORITHM)
    assert client.get(path,headers={'Authorization':'Bearer '+expired}).status_code==401
    token=create_access_token(1,'part2p-1@example.com','GENERAL_USER')
    payload=decode_access_token(token)
    revoke(payload)
    assert client.get(path,headers={'Authorization':'Bearer '+token}).status_code==401

def test_canonical_uuid_and_pagination(client,setup):
    for url in ['/libraries/LIB001/announcements',f'/libraries/{setup}/announcements/LIB001',f'/libraries/{setup}/announcements?limit=51',f'/libraries/{setup}/announcements?offset=10001']:
        assert client.get(url).status_code==422
    for _ in range(3):action(client,setup,draft(client,setup))
    first=client.get(f'/libraries/{setup}/announcements?limit=2',headers=headers(2)).json()
    second=client.get(f'/libraries/{setup}/announcements?limit=2&offset=2',headers=headers(2)).json()
    assert first['total']==3 and first['has_more'] and len(second['results'])==1
    assert not ({r['announcement_id'] for r in first['results']} & {r['announcement_id'] for r in second['results']})

def test_draft_edit_optimistic_concurrency_and_immutable_published(client,setup):
    row=draft(client,setup);url=f'/libraries/{setup}/announcements/{row["announcement_id"]}'
    body={'title':'Edited message','body':'Edited body','revision':0}
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:client.patch(url,json=body).status_code,range(2)))
    assert sorted(results)==[200,409]
    action(client,setup,row,code=409)
    row=client.get(f'/libraries/{setup}/staff/announcements/{row["announcement_id"]}').json()
    action(client,setup,row)
    assert client.patch(url,json={**body,'revision':2}).status_code==409

def test_concurrent_publish_and_delivery_deduplicate(client,setup,database):
    member(database,setup,7,role='ADMIN')
    row=draft(client,setup)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda uid:action(client,setup,row,uid=uid),[1,7]))
    assert results[0]==results[1]
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:dispatch(setup,row),range(2)))
    assert database.notifications.count_documents({'type':service.KIND})==5
    assert database.notifications.count_documents({'user_id':2})==1
    assert service.document(setup,row['announcement_id'])['delivery']['cursor']==5

def test_partial_failure_restart_replay_and_worker_integration(client,setup,database,monkeypatch):
    row=draft(client,setup);action(client,setup,row)
    original=ns.insert_notice;calls=[]
    def failure(*args,**kwargs):
        calls.append(args[0])
        if len(calls)==2:raise RuntimeError('secret that must not persist')
        return original(*args,**kwargs)
    monkeypatch.setattr(ns,'insert_notice',failure)
    assert dispatch(setup,row)['failed']==1
    stored=service.document(setup,row['announcement_id'])
    assert stored['delivery']['cursor']==0 and stored['delivery']['last_error_code']=='DELIVERY_FAILED'
    assert 'secret' not in str(stored)
    monkeypatch.setattr(ns,'insert_notice',original)
    result=tn.materialize(stamp=now()+timedelta(minutes=2))
    assert result['failed']==0
    assert database.notifications.count_documents({'type':service.KIND})==4
    assert service.document(setup,row['announcement_id'])['delivery']['state']=='COMPLETE'

def test_failure_after_notice_insert_cursor_write_replays(client,setup,database,monkeypatch):
    row=draft(client,setup);action(client,setup,row)
    import pymongo.synchronous.collection
    original=pymongo.synchronous.collection.Collection.update_one;fail=[True]
    def update(coll,query,values,*a,**k):
        if coll.name=='institution_announcements' and '$inc' in values and 'delivery.delivered' in values['$inc'] and fail[0]:
            fail[0]=False;raise RuntimeError('lost ack')
        return original(coll,query,values,*a,**k)
    monkeypatch.setattr(pymongo.synchronous.collection.Collection,'update_one',update)
    assert dispatch(setup,row)['failed']==1
    assert database.notifications.count_documents({})==4
    assert dispatch(setup,row)['failed']==0
    assert database.notifications.count_documents({})==4
    assert service.document(setup,row['announcement_id'])['delivery']['delivered']==4

@pytest.mark.parametrize('state',['REVOKED','REMOVED','SUSPENDED','DISABLED','UNVERIFIED','BAD_PROOF','SETUP_REQUIRED','LEGACY_SETUP_REQUIRED'])
def test_recipient_canonical_eligibility(client,setup,database,state):
    member(database,setup,6)
    if state=='DISABLED':database.users.update_one({'user_id':6},{'$set':{'is_active':False}})
    elif state=='UNVERIFIED':database.users.update_one({'user_id':6},{'$set':{'is_email_verified':False}})
    elif state in ['SETUP_REQUIRED','LEGACY_SETUP_REQUIRED']:database.users.update_one({'user_id':6},{'$set':{'password_setup_required':True if state=='SETUP_REQUIRED' else 'required'}})
    elif state=='BAD_PROOF':database.institution_memberships.update_one({'user_id':6,'library_id':setup},{'$set':{'grant_invitation_id':str(uuid4())}})
    else:database.institution_memberships.update_one({'user_id':6,'library_id':setup},{'$set':{'status':state}})
    row=draft(client,setup);action(client,setup,row);dispatch(setup,row)
    assert database.notifications.count_documents({'user_id':6})==0

def test_new_joiners_and_mid_delivery_revocation(client,setup,database):
    row=draft(client,setup);published=action(client,setup,row)
    member(database,setup,6)
    database.institution_memberships.update_one({'user_id':2,'library_id':setup},{'$set':{'status':'REVOKED'}})
    result=dispatch(setup,row)
    assert result['suppressed']==1 and result['delivered']==3
    assert inbox(client,2)['count']==0 and inbox(client,6)['count']==0
    path=f'/libraries/{setup}/announcements/{row["announcement_id"]}'
    assert client.get(path,headers=headers(6)).status_code==200
    assert client.get(path,headers=headers(2)).status_code==404
    assert action(client,setup,row)['delivery']['total']==published['delivery']['total']==4

def test_cross_tenant_delivery_inbox_ownership_and_revocation(client,setup,libraries,database):
    other=libraries(owner=5);member(database,other,6)
    row=draft(client,setup);action(client,setup,row);dispatch(setup,row)
    assert inbox(client,6)['count']==0
    notice=inbox(client,2)['notifications'][0]
    url='/notifications/'+notice['notification_id']
    for uid in [4,5,6,10]:
        assert client.get(url,headers=headers(uid)).status_code==404
        assert client.patch(url+'/read',headers=headers(uid)).status_code==404
    assert client.get(f'/libraries/{other}/notifications/{notice["notification_id"]}',headers=headers(2)).status_code==404
    database.institution_memberships.update_one({'user_id':2,'library_id':setup},{'$set':{'status':'REVOKED'}})
    assert inbox(client,2)['count']==0
    assert client.get('/notifications/unread-count',headers=headers(2)).json()['unread_count']==0
    assert client.get(url,headers=headers(2)).status_code==404
    assert client.patch(url+'/read',headers=headers(2)).status_code==404

def test_read_one_all_persistence_and_source_route_spoof(client,setup,database):
    row=draft(client,setup,priority='IMPORTANT');action(client,setup,row);dispatch(setup,row)
    notice=inbox(client,2)['notifications'][0];url='/notifications/'+notice['notification_id']
    assert notice['priority']=='IMPORTANT' and notice['message']!=row['body']
    database.notifications.update_one({'notification_id':notice['notification_id']},{'$set':{'action_route':'https://attacker.example/steal'}})
    assert client.get(url+'/action',headers=headers(2)).json()['action_route']==f'/libraries/{setup}/announcements/{row["announcement_id"]}'
    a=client.patch(url+'/read',headers=headers(2)).json();b=client.patch(url+'/read',headers=headers(2)).json()
    assert a['read_at']==b['read_at'] and inbox(client,2)['unread_count']==0
    assert inbox(client,4)['unread_count']==1
    assert client.post('/notifications/read-all',headers=headers(4)).json()['marked']==1
    assert inbox(client,4)['unread_count']==0

def test_member_multiple_libraries_routes_and_mark_all(client,setup,libraries,database):
    other=libraries(owner=5);member(database,other,2)
    for lib,uid in [(setup,1),(other,5)]:
        row=draft(client,lib,uid);action(client,lib,row,uid=uid);dispatch(lib,row)
    result=inbox(client,2);assert result['unread_count']==2
    assert {n['library_id'] for n in result['notifications']}=={setup,other}
    assert all(n['action_route'].startswith('/libraries/'+n['library_id']+'/') for n in result['notifications'])
    client.post('/notifications/read-all',headers=headers(2))
    assert inbox(client,2)['unread_count']==0

def test_linked_events_foreign_draft_withdrawal_missing_safe(client,setup,libraries,database):
    other=libraries(owner=5)
    event=client.post(f'/libraries/{other}/events',headers=headers(5),json={'title':'Foreign event','category':'LIBRARY_NOTICE','description':'Notice'}).json()
    bad=client.post(f'/libraries/{setup}/announcements',json={'title':'Bad reference','body':'Text','request_id':str(uuid4()),'linked_event_id':event['event_id']})
    assert bad.status_code==404
    event=client.post(f'/libraries/{setup}/events',json={'title':'Linked event','category':'LIBRARY_NOTICE','description':'Notice'}).json()
    row=draft(client,setup,category='EVENT',linked_event_id=event['event_id'])
    action(client,setup,row,code=409)
    client.post(f'/libraries/{setup}/events/{event["event_id"]}/publish')
    published=action(client,setup,row);assert published['linked_event_available']
    dispatch(setup,row)
    database.events.delete_one({'event_id':event['event_id']})
    assert not client.get(f'/libraries/{setup}/announcements/{row["announcement_id"]}',headers=headers(2)).json()['linked_event_available']
    action(client,setup,published,'withdraw')
    notice=inbox(client,2)['notifications'][0]
    assert notice['action_route'] is None and 'no longer' in notice['message']
    assert 'body' not in notice

def test_create_idempotency_limit_and_manual_delivery(client,setup,database,monkeypatch):
    key=str(uuid4());row=draft(client,setup,request_id=key)
    assert draft(client,setup,request_id=key)==row
    assert client.post(f'/libraries/{setup}/announcements',json={'title':'Conflict','body':'Other','request_id':key}).status_code==409
    monkeypatch.setattr(service,'MAX_RECIPIENTS',2)
    action(client,setup,row,code=409)
    assert service.document(setup,row['announcement_id'])['status']=='DRAFT'
    monkeypatch.setattr(service,'MAX_RECIPIENTS',20000)
    action(client,setup,row)
    r=client.post(f'/libraries/{setup}/announcements/{row["announcement_id"]}/delivery/retry')
    assert r.status_code==200 and r.json()['delivery']['state']=='COMPLETE'

def test_filters_private_outsider_and_authority_revocation(client,setup,database):
    row=draft(client,setup)
    assert client.get(f'/libraries/{setup}/announcements',headers=headers(8)).status_code==404
    assert client.get(f'/libraries/{setup}/staff/announcements?status=DRAFT').json()['total']==1
    assert client.get(f'/libraries/{setup}/staff/announcements?status=PUBLISHED').json()['total']==0
    database.institution_memberships.update_one({'library_id':setup,'user_id':1},{'$set':{'status':'REMOVED'}})
    action(client,setup,row,code=404)

def test_delivery_slice_bounded_snapshot_no_private_payload(client,setup,database):
    row=draft(client,setup);action(client,setup,row)
    assert dispatch(setup,row,2)['delivered']==2
    state=service.document(setup,row['announcement_id'])['delivery'];assert state['cursor']==2 and state['state']=='PENDING'
    assert dispatch(setup,row,2)['delivered']==2
    for notice in database.notifications.find({}):
        assert notice['title']=='Library announcement' and 'worker' not in str(notice['source_ref'])
        assert set(notice['source_ref'])=={'announcement_id'}

def test_exhausted_delivery_stops_until_admin_repair(client,setup,database,monkeypatch):
    row=draft(client,setup);action(client,setup,row);original=ns.insert_notice
    monkeypatch.setattr(ns,'insert_notice',lambda *a,**k:(_ for _ in ()).throw(RuntimeError('bounded fault')))
    for _ in range(10):assert dispatch(setup,row)['failed']==1
    assert service.document(setup,row['announcement_id'])['delivery']['state']=='FAILED'
    assert service.deliver_pending(stamp=now()+timedelta(days=2))['scanned']==0
    monkeypatch.setattr(ns,'insert_notice',original)
    r=client.post(f'/libraries/{setup}/announcements/{row["announcement_id"]}/delivery/retry')
    assert r.status_code==200 and r.json()['delivery']['state']=='COMPLETE'

def test_withdraw_cancels_remaining_recipients_and_private_inbox(client,setup,database):
    row=draft(client,setup);published=action(client,setup,row)
    dispatch(setup,row,2);action(client,setup,published,'withdraw')
    assert dispatch(setup,row)['scanned']==0
    assert database.notifications.count_documents({})==2
    assert inbox(client,2)['notifications'][0]['action_route'] is None

def test_accepted_invitation_proof_and_invalidated_proof_inbox(client,setup,database):
    proof=str(uuid4());member(database,setup,6,grant_invitation_id=proof)
    database.institution_invitations.insert_one({'library_id':setup,'invitation_id':proof,'accepted_by_user_id':6,'status':'ACCEPTED'})
    row=draft(client,setup);action(client,setup,row);dispatch(setup,row)
    assert inbox(client,6)['unread_count']==1
    database.institution_invitations.update_one({'invitation_id':proof},{'$set':{'status':'REVOKED'}})
    assert inbox(client,6)['count']==0

def test_read_all_race_and_repeated_read_preserve_other_users(client,setup,database):
    row=draft(client,setup);action(client,setup,row);dispatch(setup,row)
    notice=inbox(client,2)['notifications'][0]
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda op:client.request('POST' if op else 'PATCH','/notifications/read-all' if op else '/notifications/'+notice['notification_id']+'/read',headers=headers(2)),range(2)))
    assert inbox(client,2)['unread_count']==0 and inbox(client,4)['unread_count']==1

def test_suspended_library_blocks_content_and_copies(client,setup,database):
    row=draft(client,setup);action(client,setup,row)
    database.institution_libraries.update_one({'library_id':setup},{'$set':{'status':'SUSPENDED'}})
    assert dispatch(setup,row)['delivered']==0
    assert client.get(f'/libraries/{setup}/announcements',headers=headers(2)).status_code==404

def test_notification_forged_source_id_has_no_navigation(client,setup,database):
    row=draft(client,setup);action(client,setup,row);dispatch(setup,row)
    database.notifications.update_many({'user_id':2},{'$set':{'source_id':'LIB001','action_route':'javascript:alert(1)'}})
    assert inbox(client,2)['notifications'][0]['action_route'] is None

def test_revoked_between_delivery_slices_is_suppressed(client,setup,database):
    row=draft(client,setup);action(client,setup,row)
    assert dispatch(setup,row,2)['delivered']==2
    database.institution_memberships.update_one({'library_id':setup,'user_id':4},{'$set':{'status':'REVOKED'}})
    result=dispatch(setup,row,2)
    assert result['delivered']==1 and result['suppressed']==1
    assert database.notifications.count_documents({'user_id':4})==0

def test_revoked_private_copy_not_marked_by_read_all_and_staff_routes(client,setup,database):
    row=draft(client,setup);action(client,setup,row);dispatch(setup,row)
    for uid in [1,3]:assert inbox(client,uid)['notifications'][0]['action_route']==f'/staff/libraries/{setup}/announcements/{row["announcement_id"]}'
    notice=inbox(client,2)['notifications'][0]
    database.institution_memberships.update_one({'library_id':setup,'user_id':2},{'$set':{'status':'REMOVED'}})
    assert client.post('/notifications/read-all',headers=headers(2)).json()['marked']==0
    assert database.notifications.find_one({'notification_id':notice['notification_id']})['read_at'] is None

def test_fresh_process_resumes_partial_fanout_without_duplicate_copy(client,setup,database,monkeypatch):
    import os,sys,subprocess,json
    from pathlib import Path
    row=draft(client,setup);action(client,setup,row)
    original=ns.insert_notice;calls=[]
    def interrupted(*args,**kwargs):
        calls.append(args[0])
        if len(calls)==2:raise RuntimeError('controlled interrupted fanout')
        return original(*args,**kwargs)
    monkeypatch.setattr(ns,'insert_notice',interrupted)
    assert dispatch(setup,row)['failed']==1
    assert database.notifications.count_documents({})==1
    assert service.document(setup,row['announcement_id'])['delivery']['cursor']==0
    program="""import os,json
from datetime import timedelta
from backend.services.tenant_notification_service import materialize
from backend.services.institution_repository import now
from backend.database.mongodb import db
assert db.name.startswith('luminar_institution_v2p_test_')
print(json.dumps({'pid':os.getpid(),'result':materialize(stamp=now()+timedelta(minutes=5))}))
"""
    run=subprocess.run([sys.executable,'-c',program],cwd=Path(__file__).resolve().parents[2],env=os.environ.copy(),capture_output=True,text=True,timeout=30)
    assert run.returncode==0,run.stderr
    result=json.loads(run.stdout.strip().splitlines()[-1])
    assert result['pid']!=os.getpid() and result['result']['delivered']==4 and result['result']['failed']==0
    assert database.notifications.count_documents({})==4
    assert service.document(setup,row['announcement_id'])['delivery']['state']=='COMPLETE'
