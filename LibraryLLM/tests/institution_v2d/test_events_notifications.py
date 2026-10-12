from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4
import pytest
from pydantic import ValidationError
from backend.schemas.notifications import NotificationScope
from backend.services import notification_service as ns, tenant_notification_service as tn
from backend.services.institution_repository import now


def headers(uid):return {'x-test-user':str(uid)}
def command(**fields):return {'idempotency_key':str(uuid4()),**fields}
def post(client,lib,path,uid=1,body=None,status=200):
    r=client.post(f'/libraries/{lib}/{path}',headers=headers(uid),json=command() if body is None else body)
    assert r.status_code==status,r.text
    return r.json()
def event(client,lib,uid=1,**fields):return post(client,lib,'events',uid,{'title':'Shared event title','category':'OTHER','description':'An actual library event.','start_at':(now()+timedelta(days=3)).isoformat(),**fields},201)
def publish(client,lib,uid=1,**fields):
    row=event(client,lib,uid,**fields)
    return post(client,lib,f'events/{row["event_id"]}/publish',uid,{})
def request(client,setup,uid=2):
    lib,book=setup;return post(client,lib,'lending/borrow-requests',uid,command(library_book_id=book),201)
def issue(client,setup,uid=2):
    lib,_=setup;row=request(client,setup,uid)
    return post(client,lib,f'staff/lending/borrow-requests/{row["lending_request_id"]}/approve')['loan']
def return_request(client,lib,loan,uid=2):return post(client,lib,f'loans/{loan["loan_id"]}/return-request',uid,command(),201)
def receive(client,lib,loan,uid=2):
    row=return_request(client,lib,loan,uid)
    return post(client,lib,f'staff/lending/return-requests/{row["lending_request_id"]}/confirm')
def notices(database,kind,uid=None):
    query={'type':kind}
    if uid is not None:query['user_id']=uid
    return list(database.notifications.find(query))
def dispatch():
    result=tn.materialize(500);assert result['failed']==0,result
    return result


def test_event_requires_library_uuid(client):
    assert client.post('/libraries/LIB001/events',json={'title':'Hello','category':'OTHER'}).status_code==422


@pytest.mark.parametrize('uid',[1,3])
def test_admin_and_librarian_create_library_event(client,setup,uid):
    row=event(client,setup[0],uid)
    assert row['library_id']==setup[0] and row['scope']=='LIBRARY' and row['visibility']=='LIBRARY_MEMBERS' and UUID(row['event_id'])


@pytest.mark.parametrize('uid',[2,9,10])
def test_general_user_legacy_admin_platform_cannot_create_event(client,setup,database,uid):
    if uid==10:database.platform_role_assignments.insert_one({'user_id':10,'role':'PLATFORM_ADMIN','status':'ACTIVE','approved_by':'fixture','approval_ref':'fixture','approved_at':now()})
    assert client.post(f'/libraries/{setup[0]}/events',headers=headers(uid),json={'title':'Denied','category':'OTHER'}).status_code in [403,404]


def test_event_cross_library_denied(client,setup,libraries):
    row=publish(client,setup[0]);other=libraries(owner=5)
    assert client.get(f'/libraries/{other}/events/{row["event_id"]}').status_code==404
    assert client.patch(f'/libraries/{other}/events/{row["event_id"]}',headers=headers(5),json={'title':'Cross tenant'}).status_code==404
    assert client.get('/events/'+row['event_id']).status_code==404
    assert client.get('/platform/events/'+row['event_id']).status_code==403


def test_private_event_outsider_denied(client,libraries,database):
    lib=libraries(private=True);row=publish(client,lib)
    assert client.get(f'/libraries/{lib}/events/{row["event_id"]}',headers=headers(2)).status_code==404
    assert client.get(f'/libraries/{lib}/events',headers=headers(2)).status_code==404
    database.institution_memberships.insert_one({'membership_id':str(uuid4()),'library_id':lib,'user_id':2,'role':'GENERAL_USER','status':'ACTIVE'})
    assert client.get(f'/libraries/{lib}/events/{row["event_id"]}',headers=headers(2)).status_code==200
    assert client.post(f'/libraries/{lib}/events',json={'title':'Public leak','category':'OTHER','visibility':'PUBLIC'}).status_code==422


def test_member_reads_published_not_draft(client,setup):
    row=event(client,setup[0]);url=f'/libraries/{setup[0]}/events/{row["event_id"]}'
    assert client.get(url,headers=headers(2)).status_code==404
    post(client,setup[0],f'events/{row["event_id"]}/publish',body={})
    assert client.get(url,headers=headers(2)).status_code==200


def test_publish_cancel_reason_cancelled_detail(client,setup):
    lib=setup[0];row=publish(client,lib,3);url=f'/libraries/{lib}/events/{row["event_id"]}/cancel'
    for body in [{},{'reason':''},{'reason':'  '}]:assert client.post(url,headers=headers(3),json=body).status_code==422
    assert client.post(url,headers=headers(3),json={'reason':'Venue closed.'}).status_code==200
    detail=client.get(url.removesuffix('/cancel'),headers=headers(2)).json()
    assert detail['status']=='CANCELLED' and detail['cancellation_reason']=='Venue closed.'
    assert client.get(f'/libraries/{lib}/events?view=cancelled',headers=headers(2)).json()['count']==1


def test_same_title_two_libraries(client,setup,libraries):
    a=publish(client,setup[0]);lib=libraries(owner=5);b=publish(client,lib,5)
    assert a['event_id']!=b['event_id'] and a['library_id']!=b['library_id']


@pytest.mark.parametrize('state',['SUSPENDED','REMOVED'])
def test_lifecycle_event_mutation_denied(client,setup,database,state):
    row=event(client,setup[0]);database.institution_libraries.update_one({'library_id':setup[0]},{'$set':{'status':state}})
    assert client.post(f'/libraries/{setup[0]}/events/{row["event_id"]}/publish').status_code==404
    assert client.post(f'/libraries/{setup[0]}/events',json={'title':'Denied','category':'OTHER'}).status_code==404


def test_event_public_visibility_and_draft_filters(client,setup):
    private=publish(client,setup[0]);public=publish(client,setup[0],visibility='PUBLIC')
    rows=client.get(f'/libraries/{setup[0]}/events',headers=headers(8)).json()['events']
    assert [r['event_id'] for r in rows]==[public['event_id']]
    assert private['event_id'] not in [r['event_id'] for r in rows]
    event(client,setup[0]);assert client.get(f'/libraries/{setup[0]}/staff/events?status=DRAFT').json()['count']==1
    assert client.get(f'/libraries/{setup[0]}/staff/events?view=past').json()['count']==0


def test_global_events_explicit_and_tenant_excluded(client,setup,database):
    publish(client,setup[0]);database.platform_role_assignments.insert_one({'user_id':1,'role':'PLATFORM_ADMIN','status':'ACTIVE','approved_by':'fixture','approval_ref':'fixture','approved_at':now()})
    row=client.post('/platform/events',json={'title':'Global announcement','category':'OTHER'}).json()
    assert row['scope']=='GLOBAL' and row['library_id'] is None
    assert client.get('/platform/events').json()['count']==1
    database.events.insert_one({'event_id':str(uuid4()),'library_id':'LIB001','status':'PUBLISHED'})
    assert client.get('/platform/events').json()['count']==1
    assert client.get('/platform/summary').json()['events']==1


def test_notification_library_scope_requires_uuid():
    for value in [None,'LIB001','TEST']:
        with pytest.raises(ValidationError):NotificationScope(user_id=1,scope='LIBRARY',library_id=value)


def test_global_notification_has_no_library_uuid():
    for scope in ['GLOBAL','PLATFORM']:
        assert NotificationScope(user_id=1,scope=scope).library_id is None
        with pytest.raises(ValidationError):NotificationScope(user_id=1,scope=scope,library_id=uuid4())


def test_borrow_request_staff_notification(client,setup,database,libraries):
    other=libraries(owner=6);request(client,setup);dispatch()
    rows=notices(database,'BORROW_REQUEST_CREATED')
    assert {r['user_id'] for r in rows}=={1,3}
    assert all(r['library_id']==setup[0] and r['library_id']!=other for r in rows)
    assert all('/staff/libraries/'+setup[0]+'/circulation'==r['action_route'] for r in rows)


@pytest.mark.parametrize('action,kind',[('approve','BORROW_REQUEST_APPROVED'),('reject','BORROW_REQUEST_REJECTED')])
def test_borrow_review_patron_notification(client,setup,database,action,kind):
    row=request(client,setup);payload=command(reason='QA review')
    path=f'staff/lending/borrow-requests/{row["lending_request_id"]}/{action}'
    post(client,setup[0],path,body=payload);post(client,setup[0],path,body=payload);dispatch();dispatch()
    rows=notices(database,kind,2);assert len(rows)==1 and rows[0]['library_id']==setup[0]


def test_return_request_confirmed_notification_dedupe(client,setup,database):
    loan=issue(client,setup);row=return_request(client,setup[0],loan);payload=command()
    path=f'staff/lending/return-requests/{row["lending_request_id"]}/confirm'
    post(client,setup[0],path,body=payload);post(client,setup[0],path,body=payload);dispatch();dispatch()
    assert {r['user_id'] for r in notices(database,'RETURN_REQUEST_CREATED')}=={1,3}
    assert len(notices(database,'RETURN_CONFIRMED',2))==1


def test_reservation_ready_notification_dedupe(client,setup,database):
    loan=issue(client,setup);lib,book=setup
    row=post(client,lib,'reservations',4,command(library_book_id=book),201)
    receive(client,lib,loan);dispatch();dispatch()
    ready=notices(database,'RESERVATION_READY',4)
    assert len(ready)==1 and ready[0]['source_id']==row['reservation_id'] and ready[0]['action_route'].endswith('/reservations')


@pytest.mark.parametrize('action,kind,body',[('waive','FEE_WAIVED',{'reason':'QA waiver'}),('payments','PAYMENT_RECORDED',{'amount_minor':500,'method':'CASH'})])
def test_fee_notifications_where_supported(client,setup,database,action,kind,body):
    loan=issue(client,setup);database.institution_loans.update_one({'loan_id':loan['loan_id']},{'$set':{'due_at':now()-timedelta(days=2)}})
    receive(client,setup[0],loan)
    fee=database.institution_fees.find_one({'loan_id':loan['loan_id']});assert fee
    payload=command(**body);path=f'staff/fees/{fee["fee_id"]}/{action}'
    post(client,setup[0],path,body=payload);post(client,setup[0],path,body=payload);dispatch()
    assert len(notices(database,'FEE_ASSESSED',2))==1 and len(notices(database,kind,2))==1


def test_notification_other_user_and_cross_library_denied(client,setup,database,libraries):
    issue(client,setup);dispatch();row=notices(database,'BORROW_REQUEST_APPROVED',2)[0]
    assert client.get('/notifications/'+row['notification_id'],headers=headers(4)).status_code==404
    assert client.patch('/notifications/'+row['notification_id']+'/read',headers=headers(4)).status_code==404
    other=libraries(owner=6)
    assert client.get(f'/libraries/{other}/notifications/{row["notification_id"]}',headers=headers(2)).status_code==404


def test_mark_read_all_unread_account_scoped(client,setup,database):
    issue(client,setup);dispatch();row=notices(database,'BORROW_REQUEST_APPROVED',2)[0]
    assert client.get('/notifications/unread-count',headers=headers(2)).json()['unread_count']==1
    assert client.patch('/notifications/'+row['notification_id']+'/read',headers=headers(2)).status_code==200
    assert client.get('/notifications/unread-count',headers=headers(2)).json()['unread_count']==0
    client.post('/notifications/read-all',headers=headers(1))
    assert ns.unread(3)==1 and ns.unread(1)==0


@pytest.mark.parametrize('state',['REMOVED','SUSPENDED','REVOKED','MEMBERSHIP_REMOVED','ROLE_CHANGED'])
def test_notification_action_unavailable_after_authority_change(client,setup,database,state):
    issue(client,setup);dispatch();row=notices(database,'BORROW_REQUEST_APPROVED',2)[0]
    if state in ['REMOVED','SUSPENDED']:database.institution_libraries.update_one({'library_id':setup[0]},{'$set':{'status':state}})
    elif state=='ROLE_CHANGED':database.institution_memberships.update_one({'library_id':setup[0],'user_id':2},{'$set':{'role':'ADMIN'}})
    else:database.institution_memberships.update_one({'library_id':setup[0],'user_id':2},{'$set':{'status':'REMOVED' if state=='MEMBERSHIP_REMOVED' else state}})
    response=client.get('/notifications/'+row['notification_id']+'/action',headers=headers(2)).json()
    assert response['action_route'] is None and response['action_unavailable']=='Library unavailable'
    assert client.get('/notifications',headers=headers(2)).json()['count']==1


def test_multi_library_notification_routes(client,setup,database,libraries):
    issue(client,setup);other=libraries(owner=2);book=client.post(f'/libraries/{other}/inventory/books',headers=headers(2),json={'title':'Other library book','subjects':['Systems'],'idempotency_key':str(uuid4())}).json()['library_book_id']
    database.institution_memberships.insert_one({'membership_id':str(uuid4()),'library_id':other,'user_id':4,'status':'ACTIVE','role':'GENERAL_USER'})
    post(client,other,'lending/borrow-requests',4,command(library_book_id=book),201);dispatch()
    rows=client.get('/notifications',headers=headers(2)).json()['notifications']
    assert {r['library_id'] for r in rows}=={setup[0],other}
    assert {r['action_route'] for r in rows}=={f'/libraries/{setup[0]}/my-library',f'/staff/libraries/{other}/circulation'}


def test_outbox_failure_cannot_rollback_domain_and_retry_dedupes(client,setup,database,monkeypatch):
    loan=issue(client,setup);original=ns.insert_notice
    monkeypatch.setattr(ns,'insert_notice',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('deliberate safe fault')))
    result=tn.materialize();assert result['failed']==3
    assert database.institution_loans.find_one({'loan_id':loan['loan_id']})['status']=='ACTIVE'
    assert database.institution_lending_operations.count_documents({'state':{'$ne':'COMMITTED'}})==0
    monkeypatch.setattr(ns,'insert_notice',original)
    assert tn.materialize(stamp=now()+timedelta(hours=1))['delivered']==3
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:tn.materialize(),range(2)))
    assert database.notifications.count_documents({})==3


def test_prepared_outbox_never_dispatches(client,setup,database):
    row=request(client,setup);database.institution_lending_operations.update_one({'operation_id':row['operation_id']},{'$set':{'state':'PREPARED'}})
    result=tn.materialize();assert result['uncommitted']==2 and database.notifications.count_documents({})==0


def test_revoked_staff_and_platform_not_recipients(client,setup,database):
    database.institution_memberships.update_one({'library_id':setup[0],'user_id':3},{'$set':{'status':'REVOKED'}})
    database.platform_role_assignments.insert_one({'user_id':10,'role':'PLATFORM_ADMIN','status':'ACTIVE','approved_by':'fixture','approval_ref':'fixture','approved_at':now()})
    request(client,setup);dispatch();assert {r['user_id'] for r in notices(database,'BORROW_REQUEST_CREATED')}=={1}


def test_revoked_after_commit_suppresses_pending_delivery(client,setup,database):
    request(client,setup);database.institution_memberships.update_one({'library_id':setup[0],'user_id':3},{'$set':{'status':'REVOKED'}})
    dispatch();assert {r['user_id'] for r in notices(database,'BORROW_REQUEST_CREATED')}=={1}


def test_platform_activity_excludes_tenant_notifications(client,setup,database):
    issue(client,setup);dispatch();database.platform_role_assignments.insert_one({'user_id':10,'role':'PLATFORM_ADMIN','status':'ACTIVE','approved_by':'fixture','approval_ref':'fixture','approved_at':now()})
    result=client.get('/platform/users/2/activity',headers=headers(10)).json()
    assert result['notifications']['count']==0 and not result['notifications']['records']
