from datetime import datetime, timedelta, timezone
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import pytest
from conftest import NOW, http
from backend.services import notification_service as ns, issue_service as loans, loan_renewal_service as renewals
from backend.services.loan_notification_service import reconcile_loan_notifications


def loan(db, delta=2, uid=2, iid=1, **extra):
    doc={'issue_id':iid,'user_id':uid,'work_id':'OL1W','book_id':1,'title':'Dracula',
         'issued_at':NOW-timedelta(days=12),'due_date':NOW+timedelta(days=delta),
         'status':'ISSUED','returned_at':None,'fine_amount':0,**extra}
    db.issues.insert_one(doc);doc.pop('_id',None);return doc


def body(doc, rid=None):return {'request_id':str(rid or uuid4()),'expected_due_date':ns.utc(doc['due_date']).isoformat()}
def post(doc, uid=2, payload=None):return http(uid).post(f"/issues/{doc['issue_id']}/renew",json=payload or body(doc))


def test_owner_renews_legacy_active_loan_atomically_with_dates_count_audit_and_no_inventory_change(isolated):
    doc=loan(isolated);inventory=isolated.books.find_one({'work_id':'OL1W'})['available_copies']
    response=post(doc);assert response.status_code==200;out=response.json()
    assert ns.utc(out['new_due_date'])==ns.utc(doc['due_date'])+timedelta(days=14)
    assert out['renewal_count']==1 and out['remaining_renewals']==0
    stored=isolated.issues.find_one({'issue_id':1});assert stored['original_due_date']==doc['due_date'].replace(tzinfo=None)
    assert stored['last_renewed_at'] and len(stored['renewal_receipts'])==1
    event=isolated.activity.find_one({'activity_type':'BOOK_RENEWED'})
    assert event['user_id']==event['actor_user_id']==2 and event['old_due_date']==doc['due_date'].replace(tzinfo=None)
    assert event['new_due_date']==stored['due_date'] and event['issue_id']==1
    assert isolated.books.find_one({'work_id':'OL1W'})['available_copies']==inventory
    out=http().get('/admin/operations?operation_type=BOOK_RENEWED&email=alice@').json()
    assert out['count']==1 and out['operations'][0]['target_user']['email']=='alice@example.com'
    assert out['operations'][0]['old_due_date'] and out['operations'][0]['new_due_date']


@pytest.mark.parametrize('uid',[1,3,4])
def test_other_accounts_cannot_self_renew(isolated,uid):
    doc=loan(isolated);assert post(doc,uid).status_code==403
    assert isolated.activity.count_documents({})==0


def test_returned_loan_and_missing_loan_rejected(isolated):
    doc=loan(isolated,status='RETURNED');assert post(doc).json()['detail']['code']=='RENEWAL_NOT_ACTIVE'
    assert http(2).post('/issues/999/renew',json=body(doc)).status_code==404


@pytest.mark.parametrize('status',['ACTIVE','READY_FOR_PICKUP'])
def test_other_reader_reservation_blocks_renewal_even_with_spare_copy(isolated,status):
    doc=loan(isolated);isolated.reservations.insert_one({'reservation_id':1,'work_id':'OL1W','user_id':3,'status':status})
    response=post(doc);assert response.status_code==409 and response.json()['detail']['code']=='RENEWAL_BLOCKED_BY_RESERVATION'
    assert isolated.activity.count_documents({})==0 and isolated.issues.find_one({'issue_id':1})['due_date']==doc['due_date'].replace(tzinfo=None)


@pytest.mark.parametrize('uid,status',[(2,'ACTIVE'),(3,'CANCELLED'),(3,'FULFILLED')])
def test_own_or_inactive_reservation_does_not_block(isolated,uid,status):
    doc=loan(isolated);isolated.reservations.insert_one({'work_id':'OL1W','user_id':uid,'status':status});assert post(doc).status_code==200


def test_overdue_renewal_rejected_and_existing_fee_unchanged(isolated):
    doc=loan(isolated,-3,fine_amount=15);isolated.fines.insert_one({'fine_id':1,'issue_id':1,'user_id':2,'amount':15,'status':'UNPAID'})
    assert post(doc).json()['detail']['code']=='RENEWAL_OVERDUE'
    assert isolated.fines.find_one({})['amount']==15 and isolated.issues.find_one({})['fine_amount']==15
    assert isolated.activity.count_documents({})==0


def test_non_overdue_renewal_does_not_reset_existing_fine_fields(isolated):
    doc=loan(isolated,fine_amount=10);isolated.fines.insert_one({'fine_id':1,'user_id':2,'amount':10,'status':'UNPAID'})
    assert post(doc).status_code==200;assert isolated.fines.find_one({})['amount']==10
    assert isolated.issues.find_one({})['fine_amount']==10


def test_configuration_and_count_limit(isolated,monkeypatch):
    monkeypatch.setenv('LOAN_RENEWAL_DAYS','7');monkeypatch.setenv('LOAN_MAX_RENEWALS','2')
    doc=loan(isolated);one=post(doc).json();assert ns.utc(one['new_due_date'])==ns.utc(doc['due_date'])+timedelta(days=7)
    assert post(doc).json()['detail']['code']=='RENEWAL_STATE_CHANGED'
    current=isolated.issues.find_one({'issue_id':1});two=post(current).json();assert two['renewal_count']==2
    assert post(isolated.issues.find_one({'issue_id':1})).json()['detail']['code']=='RENEWAL_LIMIT_REACHED'
    assert isolated.activity.count_documents({'activity_type':'BOOK_RENEWED'})==2


@pytest.mark.parametrize('setting,value,code',[('LOAN_RENEWAL_ENABLED','0','RENEWAL_DISABLED'),('LOAN_MAX_RENEWALS','0','RENEWAL_LIMIT_REACHED'),('LOAN_RENEWAL_DAYS','bad','RENEWAL_POLICY_INVALID')])
def test_disabled_or_invalid_policy_fails_closed(isolated,monkeypatch,setting,value,code):
    monkeypatch.setenv(setting,value);doc=loan(isolated);assert post(doc).json()['detail']['code']==code


def test_retry_uuid_only_one_extension_and_one_audit(isolated):
    doc=loan(isolated);payload=body(doc);assert post(doc,payload=payload).status_code==200
    assert post(doc,payload=payload).json()['idempotent_replay']
    assert isolated.issues.find_one({})['renewal_count']==1 and isolated.activity.count_documents({})==1
    payload['expected_due_date']=ns.utc(doc['due_date']+timedelta(days=1)).isoformat()
    assert post(doc,payload=payload).json()['detail']['code']=='RENEWAL_REQUEST_CONFLICT'


@pytest.mark.parametrize('same_uuid',[False,True])
def test_concurrent_renewal_safely_extends_once_even_when_maximum_two(isolated,monkeypatch,same_uuid):
    monkeypatch.setenv('LOAN_MAX_RENEWALS','2');doc=loan(isolated);rid=str(uuid4())
    def run(i):
        try:return renewals.renew_loan(1,2,rid if same_uuid else str(uuid4()),doc['due_date'])
        except renewals.RenewalError as e:return e.code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert isolated.issues.find_one({})['renewal_count']==1 and isolated.activity.count_documents({})==1
    assert sum(isinstance(r,dict) for r in results)==(2 if same_uuid else 1)


def test_admin_assisted_actor_target_and_librarian_not_granted_cross_user_permission(isolated):
    doc=loan(isolated);payload=body(doc)
    assert http(4).post('/admin/operations/renew/1',json=payload).status_code==403
    assert http(3).post('/admin/operations/renew/1',json=payload).status_code==403
    assert http().post('/admin/operations/renew/1',json=payload).status_code==200
    row=isolated.activity.find_one({});assert row['actor_user_id']==1 and row['user_id']==2


def test_forged_role_inactive_account_and_owner_body_not_accepted(isolated):
    doc=loan(isolated);payload={**body(doc),'user_id':2}
    assert http(3).post('/admin/operations/renew/1',json=body(doc)).status_code==403
    assert post(doc,payload=payload).status_code==422
    isolated.users.update_one({'user_id':2},{'$set':{'is_active':False}});assert post(doc).status_code==401


def test_user_loan_api_eligibility_and_current_dates(isolated):
    loan(isolated);out=http(2).get('/issues/my').json()['issues'][0]
    assert out['renewal']['eligible'] and out['renewal']['max_renewals']==1 and ns.utc(out['due_date']).utcoffset()==timedelta(0)
    assert http(3).get('/issues/1/renewal').status_code==403


def due_notice(doc,kind='DUE_SOON'):
    return ns.insert_notice(doc['user_id'],kind,'Book reminder','A historical warning',f"{kind}:{doc['issue_id']}:{ns.utc(doc['due_date']).isoformat()}",source_ref={'loan_id':doc['issue_id'],'work_id':doc['work_id'],'due_date':ns.utc(doc['due_date']).isoformat()})[0]


@pytest.mark.parametrize('kind',['DUE_SOON','DUE_TODAY','OVERDUE'])
def test_renewal_resolves_each_old_system_type_without_deleting_or_overloading_read(isolated,kind):
    doc=loan(isolated);n=due_notice(doc,kind);assert post(doc).status_code==200
    saved=isolated.notifications.find_one({'notification_id':n['notification_id']})
    assert saved['resolved_at'] and saved['resolution_reason']=='LOAN_RENEWED' and saved['read_at'] is None
    assert ns.unread(2)==0 and ns.list_own(2)['count']==1


@pytest.mark.parametrize('kind',['DUE_SOON','DUE_TODAY','OVERDUE'])
def test_return_resolves_each_system_type_and_worker_cannot_recreate(isolated,kind):
    doc=loan(isolated,-3);due_notice(doc,kind);loans.return_book(1,2)
    saved=isolated.notifications.find_one({});assert saved['resolution_reason']=='LOAN_RETURNED'
    assert ns.scan_due(NOW)['created']==0 and ns.unread(2)==0
    assert isolated.fines.find_one({})['amount']==15


def test_new_due_version_later_notifies_and_old_version_never_alarms(isolated):
    doc=loan(isolated);ns.scan_due(NOW);assert post(doc).status_code==200
    assert ns.scan_due(NOW+timedelta(days=3))['created']==0
    assert ns.scan_due(NOW+timedelta(days=14))['created']==1
    active=list(isolated.notifications.find({'resolved_at':None}));assert len(active)==1 and active[0]['type']=='DUE_SOON'
    assert ns.utc(active[0]['source_ref']['due_date'])==ns.utc(doc['due_date'])+timedelta(days=14)


def test_reconciliation_idempotent_admin_other_loan_and_other_user_untouched(isolated):
    doc=loan(isolated);due_notice(doc);other=loan(isolated,uid=3,iid=2);due_notice(other)
    admin=ns.insert_notice(2,'ADMIN_MESSAGE','Reminder','Admin text','admin',source='ADMIN',source_ref={'loan_id':1})[0]
    assert reconcile_loan_notifications(1,doc['due_date'],'LOAN_RENEWED')==1
    assert reconcile_loan_notifications(1,doc['due_date'],'LOAN_RENEWED')==0
    assert isolated.notifications.find_one({'notification_id':admin['notification_id']})['resolved_at'] is None
    assert ns.unread(2)==1 and ns.unread(3)==1
    assert ns.list_own(2)['notifications'][0]['type']=='ADMIN_MESSAGE'


@pytest.mark.parametrize('action',['return','renew'])
def test_worker_insert_after_mutation_reconciliation_is_resolved_by_postcheck(isolated,monkeypatch,action):
    doc=loan(isolated,-3 if action=='return' else 2);original=ns.insert_notice
    def insert_after_change(*args,**kwargs):
        if action=='return':loans.return_book(1,2)
        else:renewals.renew_loan(1,2,str(uuid4()),doc['due_date'])
        return original(*args,**kwargs)
    monkeypatch.setattr(ns,'insert_notice',insert_after_change)
    result=ns.scan_due(NOW);assert result['created']==1 and result['resolved_stale']==1
    assert isolated.notifications.count_documents({'resolved_at':None,'type':{'$in':['DUE_SOON','DUE_TODAY','OVERDUE']}})==0


@pytest.mark.parametrize('action',['return','renew'])
def test_mutation_after_worker_insert_resolves_existing_notice(isolated,action):
    doc=loan(isolated,-3 if action=='return' else 2);ns.scan_due(NOW)
    if action=='return':loans.return_book(1,2)
    else:renewals.renew_loan(1,2,str(uuid4()),doc['due_date'])
    assert isolated.notifications.count_documents({'resolved_at':None})==0


def test_startup_recovers_interrupted_return_and_manual_due_change(isolated):
    doc=loan(isolated);due_notice(doc);isolated.issues.update_one({'issue_id':1},{'$set':{'due_date':NOW+timedelta(days=20)}})
    assert ns.scan_due(NOW)['resolved_stale']==1
    assert isolated.notifications.find_one({})['resolution_reason']=='DUE_DATE_CHANGED'
    other=loan(isolated,-3,uid=3,iid=2);due_notice(other,'OVERDUE')
    isolated.issues.update_one({'issue_id':2},{'$set':{'status':'RETURNED'}})
    assert ns.scan_due(NOW)['resolved_stale']==1 and ns.unread(3)==0


def test_authoritative_ready_transition_emits_once_no_invented_expiry(isolated):
    doc=loan(isolated);isolated.reservations.insert_one({'reservation_id':1,'user_id':3,'work_id':'OL1W','title':'Dracula','status':'ACTIVE','reserved_at':NOW})
    loans.return_book(1,2)
    notice=isolated.notifications.find_one({'type':'RESERVATION_AVAILABLE'})
    assert notice['user_id']==3 and notice['source_ref']['reservation_id']==1
    assert isolated.reservations.find_one({})['status']=='READY_FOR_PICKUP'
    from backend.services.reservation_service import mark_next_reservation_ready
    assert mark_next_reservation_ready('OL1W') is None
    assert isolated.notifications.count_documents({'type':'RESERVATION_AVAILABLE'})==1


@pytest.mark.parametrize('action',['return','renew'])
@pytest.mark.parametrize('insert_first',[False,True])
def test_real_parallel_worker_and_mutation_no_active_stale_notice(isolated,monkeypatch,action,insert_first):
    from threading import Event
    doc=loan(isolated,-3 if action=='return' else 2)
    entered,changed=Event(),Event();original=ns.insert_notice
    def paused(*args,**kwargs):
        stored=original(*args,**kwargs) if insert_first else None
        entered.set();assert changed.wait(5)
        return stored if insert_first else original(*args,**kwargs)
    monkeypatch.setattr(ns,'insert_notice',paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending=pool.submit(ns.scan_due,NOW)
        assert entered.wait(5)
        try:
            if action=='return':loans.return_book(1,2)
            else:renewals.renew_loan(1,2,str(uuid4()),doc['due_date'])
        finally:changed.set()
        pending.result(timeout=5)
    assert isolated.notifications.count_documents({'resolved_at':None,'type':{'$in':['DUE_SOON','DUE_TODAY','OVERDUE']}})==0
