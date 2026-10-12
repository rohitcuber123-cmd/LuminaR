from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi import HTTPException
from backend.database.mongodb import db
from scripts import migrate_management_authority as migration


def h(user=1): return {'x-test-user': str(user)}
def cmd(**values): return {'idempotency_key': str(uuid4()), **values}
def grant(user=3, **changes):
    row = {'user_id': user, 'role': 'PLATFORM_ADMIN', 'status': 'ACTIVE', 'approval_ref': 'TEST-REVIEW', 'approved_by': 'test-operator', 'approved_at': datetime.now(timezone.utc)}
    row.update(changes); db.platform_role_assignments.insert_one(row)


@pytest.mark.parametrize('role', ['ADMIN', 'LIBRARIAN', 'GENERAL_USER'])
def test_legacy_role_never_grants_platform_or_library(client, libraries, role):
    db.users.update_one({'user_id': 3}, {'$set': {'role': role}})
    assert client.get('/me/platform-access', headers=h(3)).json() == {'roles': []}
    for url in ['/platform/accounts', '/platform/summary', '/platform/migration-review', '/platform/health', '/platform/events', '/issues/all', '/fines/all']:
        assert client.get(url, headers=h(3)).status_code == 403, url
    assert client.get(libraries[0]['base'] + '/staff/loans', headers=h(3)).status_code == 404


@pytest.mark.parametrize('changes', [{'status': 'REVOKED'}, {'expires_at': datetime.now(timezone.utc)-timedelta(seconds=1)}, {'approval_ref': ''}, {'approved_at': None}, {'approved_by':' '}, {'approval_ref':['unreviewed']}, {'approved_at':datetime.now(timezone.utc)+timedelta(days=1)}])
def test_incomplete_revoked_expired_platform_grant_denies(client, changes):
    grant(**changes)
    assert client.get('/platform/accounts', headers=h(3)).status_code == 403
    assert client.get('/me/platform-access', headers=h(3)).json()['roles'] == []


def test_separate_explicit_authorities_and_fresh_revocation(client, libraries):
    grant()
    assert client.get('/platform/accounts', headers=h(3)).status_code == 200
    assert client.get('/platform/summary', headers=h(3)).status_code == 200
    assert client.get(libraries[0]['base'] + '/staff/loans', headers=h(3)).status_code == 404
    # A GENERAL_USER global identity owns local ADMIN authority solely through membership.
    assert client.get(libraries[1]['base'] + '/staff/loans', headers=h(2)).status_code == 200
    assert client.get('/platform/accounts', headers=h(2)).status_code == 403
    db.platform_role_assignments.update_one({'user_id': 3}, {'$set': {'status': 'REVOKED'}})
    assert client.get('/platform/accounts', headers=h(3)).status_code == 403


def test_identity_status_revokes_platform_access(client):
    grant(); db.users.update_one({'user_id': 3}, {'$set': {'is_active': False}})
    assert client.get('/platform/accounts', headers=h(3)).status_code == 401


def test_no_api_role_or_membership_grant(client):
    grant()
    assert client.post('/platform/accounts', headers=h(3), json={'name': 'Account', 'email': 'test@example.com', 'role': 'PLATFORM_ADMIN'}).status_code == 422
    assert client.patch('/platform/accounts/1', headers=h(3), json={'role': 'ADMIN'}).status_code == 422
    assert db.institution_memberships.count_documents({}) == 0


@pytest.mark.parametrize('url,body', [('/issues/issue', {'work_id': 'W'}), ('/issues/return/1', {}), ('/reservations/', {'work_id': 'W'}), ('/reservations/cancel/1', {}), ('/fines/pay/1', {}), ('/inventory/', {'library_id': 'LIB001', 'work_id': 'W'}), ('/issues/1/renew', {'request_id': str(uuid4()), 'expected_due_date': datetime.now(timezone.utc).isoformat()})])
def test_retired_endpoints_cannot_write(client, url, body):
    before = {name: db[name].count_documents({}) for name in ['issues','reservations','fines','library_inventory','institution_loans']}
    response = client.post(url, headers=h(), json=body)
    assert response.status_code == 410, (url, response.text)
    assert {name: db[name].count_documents({}) for name in before} == before


def test_compatibility_admin_api_redirects_only(client):
    grant()
    response = client.get('/admin/summary', headers=h(3), follow_redirects=False)
    assert response.status_code == 307 and response.headers['location'] == '/platform/summary'


def test_direct_retired_services_have_no_second_writer(client):
    from backend.services import issue_service, reservation_service, fine_service, inventory_service, loan_renewal_service
    for call in [lambda: issue_service.issue_book(1,'W'), lambda: issue_service.return_book(1,1), lambda: reservation_service.create_reservation(1,'W'), lambda: reservation_service.cancel_reservation(1,1), lambda: fine_service.pay_fine(1,1), lambda: inventory_service.add_inventory('LIB001','W'), lambda: loan_renewal_service.renew_loan(1,1,'key',datetime.now(timezone.utc))]:
        with pytest.raises(HTTPException) as raised: call()
        assert raised.value.status_code == 410


def approved(**values):
    return {'user_id': 3, 'role': 'PLATFORM_ADMIN', 'approved': True, 'approved_by': 'test-operator', 'approval_ref': 'TEST-REVIEW', 'reason': 'Explicitly scoped test grant', **values}


def test_migration_dry_run_never_infers_legacy_roles(client):
    result = migration.plan(db, {})
    assert result['grants'] == [] and result['automatic_grants'] == 0
    assert db.platform_role_assignments.count_documents({}) == 0
    assert db.institution_memberships.count_documents({}) == 0


def test_migration_separates_explicit_grants(client, libraries):
    mapping = {'platform_assignments': [approved()], 'library_memberships': [approved(user_id=3, role='LIBRARIAN', library_id=libraries[0]['id'], legacy_library_id='REVIEWED-LEGACY')]}
    proposal = migration.plan(db, mapping)
    assert db.platform_role_assignments.count_documents({}) == 0
    migration.apply(db, proposal)
    assert client.get('/platform/accounts', headers=h(3)).status_code == 200
    assert client.get(libraries[0]['base']+'/staff/loans', headers=h(3)).status_code == 200
    assert client.get(libraries[1]['base']+'/staff/loans', headers=h(3)).status_code == 404
    migration.apply(db, migration.plan(db,mapping))
    assert db.platform_role_assignments.count_documents({'user_id':3}) == 1
    assert db.institution_memberships.count_documents({'user_id':3}) == 1


@pytest.mark.parametrize('change', [{'approved': False}, {'approval_ref': ''}, {'role':'ADMIN'}, {'user_id':0}])
def test_migration_rejects_unapproved_or_ambiguous(client, change):
    with pytest.raises(ValueError): migration.plan(db, {'platform_assignments':[approved(**change)]})
    assert db.platform_role_assignments.count_documents({}) == 0


def loan(client, library):
    base=library['base']
    assert client.post(base+'/join', headers=h(3), json={}).status_code == 200
    request=client.post(base+'/lending/borrow-requests', headers=h(3), json=cmd(library_book_id=library['book']))
    assert request.status_code == 201, request.text
    issued=client.post(base+'/staff/lending/borrow-requests/'+request.json()['lending_request_id']+'/approve', headers=h(library['owner']), json=cmd())
    assert issued.status_code == 200, issued.text
    return issued.json()['loan']


def test_assisted_renewal_and_receipt_use_canonical_journal(client,libraries):
    library=libraries[0]; row=loan(client,library); base=library['base']+'/staff/loans/'+row['loan_id']
    request=cmd(expected_due_at=row['due_at'])
    renewed=client.post(base+'/renew',json=request)
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()['renewal_count'] == 1
    assert client.post(base+'/renew',json=request).json() == renewed.json()
    receive=cmd(); returned=client.post(base+'/receive',json=receive)
    assert returned.status_code == 200, returned.text
    assert returned.json()['loan']['status'] == 'RETURNED'
    assert client.post(base+'/receive',json=receive).json() == returned.json()
    assert db.institution_loans.count_documents({'status':'RETURNED'}) == 1
    assert db.institution_loans.count_documents({'status':'ACTIVE'}) == 0
    assert db.issues.count_documents({}) == 0


def test_platform_alone_and_cross_tenant_cannot_receive_or_renew(client,libraries):
    row=loan(client,libraries[0]); grant(2)
    for action,values in [('renew',{'expected_due_at':row['due_at']}),('receive',{})]:
        url=libraries[0]['base']+'/staff/loans/'+row['loan_id']+'/'+action
        assert client.post(url,headers=h(2),json=cmd(**values)).status_code == 404
        wrong=libraries[1]['base']+'/staff/loans/'+row['loan_id']+'/'+action
        assert client.post(wrong,headers=h(2),json=cmd(**values)).status_code == 404
    assert db.institution_loans.find_one({'loan_id':row['loan_id']})['status']=='ACTIVE'


def test_existing_patron_return_can_be_received_without_duplicate(client,libraries):
    library=libraries[0]; row=loan(client,library); base=library['base']
    assert client.post(base+'/loans/'+row['loan_id']+'/return-request',headers=h(3),json=cmd()).status_code == 201
    result=client.post(base+'/staff/loans/'+row['loan_id']+'/receive',json=cmd())
    assert result.status_code == 200, result.text
    assert db.institution_lending_requests.count_documents({'request_type':'RETURN'}) == 1


def test_platform_provisioning_never_grants_authority(client,monkeypatch):
    from backend.services import platform_account_service as accounts, identity_service
    db.users.create_index('email',unique=True); db.users.create_index('user_id',unique=True)
    identity_service.ensure_identity_indexes(); grant()
    sent=[];monkeypatch.setattr(accounts,'resend_verification_otp',lambda email:sent.append(email))
    response=client.post('/platform/accounts',headers=h(3),json={'name':'New Identity','email':'new-identity@example.com'})
    assert response.status_code==201,response.text
    created=response.json()['user']; uid=created['user_id']
    assert created['role']=='GENERAL_USER' and not created['is_email_verified']
    assert 'password_hash' not in created
    assert db.institution_memberships.count_documents({'user_id':uid})==0
    assert db.platform_role_assignments.count_documents({'user_id':uid})==0
    assert sent==['new-identity@example.com']
    assert client.patch('/platform/accounts/3',headers=h(3),json={'is_active':False}).status_code==400
    assert client.patch('/platform/accounts/'+str(uid),headers=h(3),json={'name':'Renamed'}).status_code==200


def test_assisted_receipt_failure_is_safe_and_resumable(client,libraries,monkeypatch):
    from backend.services import library_lending_service as service
    library=libraries[0];row=loan(client,library);request=cmd()
    url=library['base']+'/staff/loans/'+row['loan_id']+'/receive'
    original=service.review_return
    def fail(*args,**kwargs): raise HTTPException(503,'Temporary receipt failure')
    monkeypatch.setattr(service,'review_return',fail)
    assert client.post(url,json=request).status_code==503
    current=db.institution_loans.find_one({'loan_id':row['loan_id']})
    assert current['status']=='ACTIVE' and current['pending_return_request_id']
    monkeypatch.setattr(service,'review_return',original)
    assert client.post(url,json=request).status_code==200
    assert db.institution_lending_requests.count_documents({'request_type':'RETURN'})==1
    assert db.institution_loans.find_one({'loan_id':row['loan_id']})['status']=='RETURNED'


def test_staff_cannot_use_assisted_path_for_own_personal_loan(client,libraries):
    library=libraries[0];row=loan(client,library)
    member=db.institution_memberships.find_one({'library_id':library['id'],'user_id':3})
    changed=client.patch(library['base']+'/memberships/'+member['membership_id'],json={'role':'LIBRARIAN'})
    assert changed.status_code==200,changed.text
    base=library['base']+'/staff/loans/'+row['loan_id']
    assert client.post(base+'/renew',headers=h(3),json=cmd(expected_due_at=row['due_at'])).status_code==403
    assert client.post(base+'/receive',headers=h(3),json=cmd()).status_code==403


def test_legacy_inventory_reads_require_explicit_alias_and_local_membership(client,libraries):
    library=libraries[0];grant()
    db.library_inventory.insert_one({'library_id':'LEGACY','work_id':'W','total_copies':1,'available_copies':1})
    assert client.get('/inventory/?library_id=LEGACY',headers=h()).status_code==410
    db.institution_library_aliases.insert_one({'legacy_library_id':'LEGACY','canonical_library_id':library['id']})
    assert client.get('/inventory/?library_id=LEGACY',headers=h(3)).status_code==404
    assert client.get('/inventory/?library_id=LEGACY',headers=h()).status_code==200


def test_conflicting_legacy_mapping_rejected_before_any_grant(client,libraries):
    mapping={'platform_assignments':[approved()], 'library_memberships':[
       approved(role='ADMIN',library_id=libraries[0]['id'],legacy_library_id='AMBIGUOUS'),
       approved(role='LIBRARIAN',library_id=libraries[1]['id'],legacy_library_id='AMBIGUOUS')]}
    with pytest.raises(ValueError,match='Conflicting'):migration.plan(db,mapping)
    assert db.platform_role_assignments.count_documents({})==0
    assert db.institution_memberships.count_documents({'user_id':3})==0


def test_migrated_activity_is_canonical_scoped_staff_read_only(client,libraries):
    for library in libraries:
        db.institution_audit.insert_one({'event_id':str(uuid4()),'library_id':library['id'],'event':'LOAN_RENEWED','actor_user_id':library['owner'],'created_at':datetime.now(timezone.utc)})
        db.institution_audit.insert_one({'event_id':str(uuid4()),'library_id':library['id'],'event':'STAFF_INVITED','actor_user_id':library['owner'],'created_at':datetime.now(timezone.utc)})
    # Account1 has ADMIN A / GENERAL_USER B / LIBRARIAN C.
    for index,expected in [(0,200),(1,403),(2,200)]:
        response=client.get(libraries[index]['base']+'/staff/activity')
        assert response.status_code==expected
        if expected==200:
            assert response.json()['total']>=1
            assert all(row['library_id']==libraries[index]['id'] and row['event']!='STAFF_INVITED' for row in response.json()['results'])
    grant()
    assert client.get(libraries[0]['base']+'/staff/activity',headers=h(3)).status_code==404


def test_staff_login_accepts_explicit_authority_on_general_identity(client,monkeypatch):
    from backend.routes import auth
    def identity(email,password):return {'user_id':3,'email':'dashboard-3@example.com','role':'GENERAL_USER','is_active':True,'is_email_verified':True}
    monkeypatch.setattr(auth,'login_user',identity)
    request={'email':'dashboard-3@example.com','password':'Fixture-credentials-only'}
    assert client.post('/auth/staff-login',json=request).status_code==403
    grant()
    assert client.post('/auth/staff-login',json=request).status_code==200
    db.platform_role_assignments.update_one({'user_id':3},{'$set':{'status':'REVOKED'}})
    assert client.post('/auth/staff-login',json=request).status_code==403
