"""Real Mongo indexes/query behavior in a uniquely named disposable database.

Run separately from the legacy staff_auth module which replaces database imports.
No production records or model processes are used.
"""
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.database.mongodb import client as mongo
from backend.dependencies import get_current_user
from backend.main import app
from backend.services import notification_service as ns, admin_operation_service as ops
from backend.services import identity_service, activity_service, issue_service, reservation_service, fine_service

NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


@pytest.fixture
def isolated(monkeypatch):
    name = 'luminar_notification_test_' + uuid4().hex
    db = mongo[name]
    from backend.database import mongodb
    monkeypatch.setattr(mongodb, 'db', db)
    assert name != 'luminar_library' and name.startswith('luminar_notification_test_')
    for module in [ns, ops, identity_service]:
        monkeypatch.setattr(module, 'db', db)
    monkeypatch.setattr(ns, 'notifications', db.notifications)
    for module in [ns, ops, identity_service, activity_service, issue_service, reservation_service, fine_service]:
        for attr, collection in [('users_collection','users'),('activity_collection','activity'),
            ('issues_collection','issues'),('books_collection','books'),('reservations_collection','reservations'),
            ('fines_collection','fines'),('library_inventory_collection','library_inventory'),('borrow_locks_collection','borrow_locks')]:
            if hasattr(module, attr): monkeypatch.setattr(module, attr, db[collection])
    from backend.services import availability_service
    monkeypatch.setattr(availability_service, 'library_inventory_collection', db.library_inventory)
    db.users.insert_many([{'user_id': uid, 'name': name, 'email': email, 'role': role,
                          'is_active': True, 'is_email_verified': True, 'password_hash': 'SECRET'}
        for uid,name,email,role in [(1,'Admin','admin@example.com','ADMIN'),(2,'Alice','alice@example.com','GENERAL_USER'),
                                  (3,'Bob','bob@example.com','GENERAL_USER'),(4,'Staff','staff@example.com','LIBRARIAN')]])
    db.books.insert_many([{'book_id':1,'work_id':'OL1W','title':'Dracula','available_copies':2,'total_copies':2},
                         {'book_id':2,'work_id':'OL2W','title':'Dune','available_copies':2,'total_copies':2}])
    ns.ensure_indexes()
    app.dependency_overrides.clear()
    yield db
    app.dependency_overrides.clear()
    mongo.drop_database(name)


def http(uid=1, claimed='ADMIN'):
    app.dependency_overrides[get_current_user] = lambda: {'sub': str(uid), 'role': claimed}
    return TestClient(app)


def send(uid=1, **fields):
    body = {'recipient_user_ids':[2], 'title':'Notice','message':'Hello','request_id':str(uuid4())}
    body.update(fields)
    return http(uid).post('/admin/notifications', json=body)


def loan(db, delta=2, status='ISSUED', uid=2, loan_id=1):
    db.issues.insert_one({'issue_id':loan_id,'user_id':uid,'work_id':'OL1W','title':'Dracula',
                         'issued_at':NOW-timedelta(days=10),'due_date':NOW+timedelta(days=delta),
                         'returned_at':None,'status':status})


@pytest.mark.parametrize('uid',[2,3,4])
@pytest.mark.parametrize('path',['/admin/operations','/admin/users?q=alice','/admin/users/2/activity','/admin/notifications/sent'])
def test_cross_user_admin_api_forbidden_despite_claimed_role(isolated, uid, path):
    assert http(uid).get(path).status_code == 403


@pytest.mark.parametrize('uid',[2,3,4])
def test_non_admin_cannot_send(isolated,uid):
    assert send(uid).status_code == 403
    assert isolated.notifications.count_documents({}) == 0


def test_admin_send_email_id_multi_persistence_audit_and_current_email(isolated):
    result=send(recipient_user_ids=[3], recipient_emails=['ALICE@example.com'])
    assert result.status_code==201 and result.json()['recipient_count']==2
    rows=list(isolated.notifications.find({})); assert {n['user_id'] for n in rows}=={2,3}
    assert all(n['created_by_user_id']==1 and n['source']=='ADMIN' for n in rows)
    isolated.users.update_one({'user_id':2},{'$set':{'email':'new@example.com'}})
    audit=http().get('/admin/notifications/sent').json()
    assert 'new@example.com' in str(audit) and 'SECRET' not in str(audit)
    assert http(2).get('/notifications').json()['count']==1
    assert http(3).get('/notifications').json()['count']==1


@pytest.mark.parametrize('fields',[{'recipient_emails':['missing@example.com']},{'recipient_user_ids':[999]},
    {'recipient_user_ids':[]},{'title':' '},{'message':'x'*1001},{'user_id':3},{'created_by_user_id':3},
    {'recipient_user_ids':[True]},{'recipient_user_ids':['2']}])
def test_invalid_or_owner_override_rejected_without_delivery(isolated,fields):
    assert send(**fields).status_code in [400,422]
    assert isolated.notifications.count_documents({})==0


def test_idempotent_admin_retry_and_conflicting_payload(isolated):
    rid=str(uuid4());assert send(request_id=rid).status_code==201
    assert send(request_id=rid).status_code==201
    assert isolated.notifications.count_documents({})==1
    assert send(request_id=rid,message='Different').status_code==400


def test_recipient_directory_pagination_complete_private_and_eligible(isolated):
    isolated.users.insert_many([{'user_id': i+10, 'name': f'Reader {i}', 'email': f'reader{i:03}@example.com',
                                'role': 'GENERAL_USER', 'is_active': True, 'is_email_verified': True,
                                'password_hash': 'SECRET'} for i in range(73)])
    isolated.users.insert_many([{'user_id': 1000, 'email': 'inactive@example.com', 'is_active': False, 'is_email_verified': True},
                               {'user_id': 1001, 'email': 'unverified@example.com', 'is_active': True, 'is_email_verified': False}])
    pages=[http().get(f'/admin/users?limit=50&offset={offset}').json() for offset in [0,50]]
    assert [len(p['users']) for p in pages] == [50,27]
    assert all(p['count']==77 for p in pages)
    ids=[u['user_id'] for p in pages for u in p['users']]
    assert len(set(ids))==77 and 1000 not in ids and 1001 not in ids
    assert 'SECRET' not in str(pages)
    filtered=http().get('/admin/users?q=reader&limit=50&offset=50').json()
    assert filtered['count']==73 and len(filtered['users'])==23
    assert http().get('/admin/users?offset=-1').status_code==422
    assert http().get('/admin/users?limit=51').status_code==422
    assert http(2).get('/admin/users?limit=50&offset=50').status_code==403


def test_bulk_selected_recipients_batched_with_same_request_retry_no_duplicates(isolated):
    ids=list(range(10,83))
    isolated.users.insert_many([{'user_id': uid, 'email': f'reader{uid}@example.com',
                                'is_active': True, 'is_email_verified': True} for uid in ids])
    rid=str(uuid4())
    assert send(recipient_user_ids=ids,request_id=rid).status_code==422
    for batch in [ids[:50],ids[50:],ids[50:]]:
        assert send(recipient_user_ids=batch,request_id=rid).status_code==201
    assert isolated.notifications.count_documents({})==73
    assert set(isolated.notifications.distinct('user_id'))==set(ids)


def test_performed_by_current_user_staff_system_and_explicit_legacy_reader(isolated):
    events=[('BOOK_ISSUED',2),('BOOK_RETURNED',1),('RESERVATION_CANCELLED',None),('RESERVATION_READY',None)]
    for kind,actor in events:
        activity_service.create_activity(2,kind,'Test action',actor_user_id=actor,title='Dracula',work_id='OL1W')
    isolated.users.update_one({'user_id':2},{'$set':{'email':'current-alice@example.com'}})
    rows={r['operation_type']:r for r in http().get('/admin/operations').json()['operations']}
    assert rows['BOOK_ISSUED']['performed_by']['account']['email']=='current-alice@example.com'
    assert rows['BOOK_ISSUED']['actor_user_id']==2
    assert rows['BOOK_RETURNED']['performed_by']['account']['email']=='admin@example.com'
    assert rows['RESERVATION_CANCELLED']['performed_by']['kind']=='LEGACY_READER'
    assert rows['RESERVATION_CANCELLED']['performed_by']['account']['email']=='current-alice@example.com'
    assert rows['RESERVATION_CANCELLED']['actor_user_id'] is None
    assert rows['RESERVATION_READY']['performed_by']['kind']=='SYSTEM'
    assert isolated.activity.find_one({'activity_type':'RESERVATION_CANCELLED'})['actor_user_id'] is None


def test_owner_scoped_reads_mark_all_and_private_absence(isolated):
    send();notice=isolated.notifications.find_one({})['notification_id']
    assert http(3).get('/notifications?user_id=2').json()['count']==0
    assert http(3).patch(f'/notifications/{notice}/read').status_code==404
    assert http(3).patch('/notifications/missing/read').status_code==404
    assert http(2).get('/notifications/unread-count').json()['unread_count']==1
    assert http(2).patch(f'/notifications/{notice}/read').status_code==200
    first=isolated.notifications.find_one({})['read_at']
    http(2).patch(f'/notifications/{notice}/read');assert isolated.notifications.find_one({})['read_at']==first
    send(recipient_user_ids=[2,3]);http(2).post('/notifications/read-all')
    assert http(2).get('/notifications/unread-count').json()['unread_count']==0
    assert http(3).get('/notifications/unread-count').json()['unread_count']==1
    public=http(2).get('/notifications').json(); assert 'admin@example.com' not in str(public) and 'dedupe_key' not in str(public)


@pytest.mark.parametrize('delta,kind',[(2,'DUE_SOON'),(0,'DUE_TODAY'),(-3,'OVERDUE'),(1,None),(5,None)])
def test_due_rules_owner_reference_and_repeat_restart(isolated,delta,kind):
    loan(isolated,delta);first=ns.scan_due(NOW);second=ns.scan_due(NOW)
    assert first['created']==(1 if kind else 0) and second['created']==0
    if kind:
        n=isolated.notifications.find_one({});assert n['type']==kind and n['user_id']==2
        assert n['source_ref']['loan_id']==1 and n['source_ref']['work_id']=='OL1W'
        assert n['created_by_user_id'] is None and n['message'].startswith('Dracula is ')
        assert second['duplicates_skipped']==1


@pytest.mark.parametrize('delta',[-3,0,2])
def test_returned_loans_emit_nothing(isolated,delta):
    loan(isolated,delta,'RETURNED');assert ns.scan_due(NOW)['created']==0


def test_worker_current_state_catchup_and_due_change(isolated):
    loan(isolated,-4);assert ns.scan_due(NOW)['created']==1
    assert [n['type'] for n in isolated.notifications.find({})]==['OVERDUE']
    isolated.issues.update_one({'issue_id':1},{'$set':{'due_date':NOW+timedelta(days=5)}})
    assert ns.scan_due(NOW)['created']==0
    isolated.issues.update_one({'issue_id':1},{'$set':{'due_date':NOW+timedelta(days=2)}})
    assert ns.scan_due(NOW)['created']==1
    assert isolated.notifications.count_documents({'type':'OVERDUE'})==1


def test_parallel_worker_unique_dedupe_index(isolated):
    loan(isolated,0)
    with ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(lambda _:ns.scan_due(NOW),range(4)))
    assert sum(r['created'] for r in results)==1 and isolated.notifications.count_documents({})==1


def test_changed_source_between_scan_and_write_skipped(isolated,monkeypatch):
    loan(isolated,-2)
    monkeypatch.setattr(ns.issues_collection,'find_one',lambda *args:None)
    assert ns.scan_due(NOW)['created']==0


def event(uid=2, actor=None, kind='BOOK_ISSUED', title='Dracula', work='OL1W'):
    return activity_service.create_activity(uid,kind,'Source event',work_id=work,actor_user_id=actor,title=title)


def test_operation_current_email_identity_actor_filters_pagination_and_legacy(isolated):
    event(actor=2);event(actor=1,kind='BOOK_RETURNED');event(uid=None,actor=None);event(uid=3,actor=3,title='Dune',work='OL2W')
    isolated.users.update_one({'user_id':2},{'$set':{'email':'changed@example.com'}})
    client=http();data=client.get('/admin/operations?email=changed@&limit=1').json()
    assert data['count']==2 and len(data['operations'])==1
    row=data['operations'][0];assert row['target_user_id']==2 and row['target_user']['email']=='changed@example.com'
    assert row['actor_user_id']==1 and row['actor']['email']=='admin@example.com'
    assert client.get('/admin/operations?user_id=3').json()['count']==1
    assert client.get('/admin/operations?work_id=OL2W').json()['count']==1
    assert client.get('/admin/operations?title=Drac').json()['count']==3
    assert client.get('/admin/operations?operation_type=BOOK_RETURNED').json()['count']==1
    assert client.get('/admin/operations?email=changed@&limit=1&offset=1').json()['operations'][0]['actor_user_id']==2
    unknown=[r for r in client.get('/admin/operations').json()['operations'] if r['target_user_id'] is None][0]
    assert unknown['target_user'] is None and unknown['actor'] is None
    assert client.get('/admin/operations?operation_type=INVENTED').status_code==422
    assert client.get('/admin/operations?limit=51').status_code==422
    assert 'SECRET' not in str(client.get('/admin/users/2/activity').json())


def test_legacy_source_hydration_and_constant_user_queries(isolated):
    loan(isolated);activity_service.create_activity(2,'BOOK_ISSUED','Legacy',issue_id=1,work_id='OL1W')
    with patch.object(ops.users_collection,'find',wraps=ops.users_collection.find) as find:
        row=ops.operations()['operations'][0]
        assert find.call_count==1
    assert row['book']['title']=='Dracula' and row['due_at'] is not None and row['actor_user_id'] is None


def test_real_self_borrow_staff_return_and_failed_action_no_success_event(isolated):
    issue=issue_service.issue_book(2,'OL1W');event_row=isolated.activity.find_one({'activity_type':'BOOK_ISSUED'})
    assert event_row['user_id']==event_row['actor_user_id']==2
    # Borrowing twice fails before audit success.
    before=isolated.activity.count_documents({})
    with pytest.raises(ValueError):issue_service.issue_book(2,'OL1W')
    assert isolated.activity.count_documents({})==before
    result=http().post(f"/admin/operations/return/{issue['issue_id']}");assert result.status_code==200
    row=isolated.activity.find_one({'activity_type':'BOOK_RETURNED'})
    assert row['user_id']==2 and row['actor_user_id']==1
    assert http(4).post(f"/admin/operations/return/{issue['issue_id']}").status_code==403


def test_plain_text_payload_stored_as_text(isolated):
    payload='<img src=x onerror=alert(1)><script>alert(2)</script>'
    assert send(message=payload).status_code==201
    assert http(2).get('/notifications').json()['notifications'][0]['message']==payload


def test_inactive_account_and_deleted_account_fail_closed(isolated):
    isolated.users.update_one({'user_id':1},{'$set':{'is_active':False}})
    assert http().get('/admin/operations').status_code==401
    isolated.users.delete_one({'user_id':2});assert http(2).get('/notifications').status_code==401


@pytest.mark.parametrize('due,kind',[(datetime(2026,10,3,23,59),'DUE_TODAY'),
    (datetime(2026,10,4,1,tzinfo=timezone(timedelta(hours=5,minutes=30))),'DUE_TODAY'),
    (datetime(2026,10,2,23,59,tzinfo=timezone.utc),'OVERDUE')])
def test_utc_calendar_boundaries(due,kind):
    assert ns.due_state(due,NOW)==kind


def test_worker_lifecycle_startup_catchup_and_clean_stop(monkeypatch):
    from threading import Event
    from backend.services import notification_worker as module
    finished=Event();calls=[]
    def scan():
        calls.append(1);finished.set();return {'created':0,'duplicates_skipped':0,'duration_ms':1}
    monkeypatch.setattr(module,'scan_due',scan)
    monkeypatch.setenv('NOTIFICATION_DUE_WORKER_ENABLED','1')
    worker=module.DueWorker();worker.start();assert finished.wait(2)
    worker.stop();assert calls==[1] and not worker.thread.is_alive()


def test_summary_returns_counts_without_loading_history(isolated):
    loan(isolated)
    response=http().get('/admin/summary');assert response.status_code==200
    assert response.json()['active_loans']==1 and response.json()['users']==4
    assert 'issues' not in response.json() and 'email' not in response.json()
