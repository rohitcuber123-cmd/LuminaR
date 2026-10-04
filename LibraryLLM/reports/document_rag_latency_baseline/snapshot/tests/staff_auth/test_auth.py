"""Run separately: python -m pytest tests/staff_auth -q.

The database module is replaced BEFORE app import; no live MongoDB or email.
"""
import sys
import types
from datetime import datetime, timezone
from unittest.mock import MagicMock
import bcrypt
import pytest
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

database = types.ModuleType('backend.database.mongodb')
database.db = MagicMock()
for name in ['users','email_verifications','books','issues','borrow_locks','reservations','fines','activity','recommendation_feedbacks','library_inventory','inventory_preview','book_categories','reading_list']:
    setattr(database, name+'_collection', MagicMock())
sys.modules['backend.database.mongodb'] = database
from backend.main import app
from backend.services import auth_service
from backend.utils import jwt_utils
from fastapi.testclient import TestClient

client = TestClient(app)
PASSWORD = 'Test account password 123!'
HASH = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()

@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    app.dependency_overrides.clear()
    for value in vars(database).values():
        if isinstance(value, MagicMock): value.reset_mock(return_value=True, side_effect=True)
    monkeypatch.setattr(jwt_utils, 'JWT_SECRET_KEY', 'test-signing-key-not-a-real-secret')
    monkeypatch.setattr(auth_service, 'send_otp_email', lambda *args: True)
    from backend.utils.auth_rate_limit import limiter
    limiter.entries.clear()
    database.users_collection.find_one.return_value = None
    database.users_collection.find.return_value.limit.return_value = []
    database.users_collection.list_indexes.return_value = [
        {'key':{'email':1},'unique':True}, {'key':{'user_id':1},'unique':True}]
    yield

def account(role='GENERAL_USER', **fields):
    user={'user_id':1,'name':'Test user','email':'reader@example.com','password_hash':HASH,'role':role,'is_email_verified':True,'created_at':datetime.now(timezone.utc)}
    user.update(fields)
    database.users_collection.find_one.return_value = user
    database.users_collection.find.return_value.limit.return_value = [user]
    return user

def headers(role='GENERAL_USER'):
    return {'Authorization':'Bearer '+jwt_utils.create_access_token(1,'reader@example.com',role)}

@pytest.mark.parametrize('role',['GENERAL_USER','ADMIN','LIBRARIAN'])
def test_existing_normal_login(role):
    account(role)
    response=client.post('/auth/login',json={'email':'reader@example.com','password':PASSWORD})
    assert response.status_code == 200
    assert response.json()['user']['role'] == role
    assert set(response.json()) == {'message','access_token','token_type','user'}
    assert 'password_hash' not in response.json()['user']

def test_existing_invalid_credentials():
    account()
    response=client.post('/auth/login',json={'email':'reader@example.com','password':'wrong'})
    assert response.status_code == 401
    assert response.json()['detail'] == 'Invalid email or password'

def test_existing_unverified_login():
    account(is_email_verified=False)
    response=client.post('/auth/login',json={'email':'reader@example.com','password':PASSWORD})
    assert response.status_code == 403

@pytest.mark.parametrize('requested_role',['ADMIN','LIBRARIAN'])
def test_public_signup_never_elevates(requested_role):
    response=client.post('/auth/register',json={'name':'Reader','email':'new@example.com','password':PASSWORD,'role':requested_role})
    assert response.status_code in (200,422)
    if response.status_code == 200:
        assert response.json()['user']['role'] == 'GENERAL_USER'
        assert database.users_collection.insert_one.call_args.args[0]['role'] == 'GENERAL_USER'
    else:
        database.users_collection.insert_one.assert_not_called()

def test_existing_malformed_token_rejected():
    assert client.get('/issues/all',headers={'Authorization':'Bearer invalid'}).status_code == 401

@pytest.mark.parametrize('role',['ADMIN','LIBRARIAN'])
def test_staff_login(role, caplog):
    account(role)
    response=client.post('/auth/staff-login',json={'email':'reader@example.com','password':PASSWORD})
    assert response.status_code == 200
    assert response.json()['user']['role'] == role
    token=response.json()['access_token']
    assert PASSWORD not in caplog.text and HASH not in caplog.text and token not in caplog.text
    assert 'staff_login_success' in caplog.text

def test_reader_denied_staff_login():
    account()
    response=client.post('/auth/staff-login',json={'email':'reader@example.com','password':PASSWORD})
    assert response.status_code == 403
    assert response.json()['detail'] == 'This account is not authorized for staff access.'

@pytest.mark.parametrize('kind',['missing','wrong','too_long'])
def test_staff_invalid_credentials_generic(kind):
    if kind != 'missing': account('ADMIN')
    password='x'*73 if kind == 'too_long' else 'wrong'
    response=client.post('/auth/staff-login',json={'email':'reader@example.com','password':password})
    assert response.status_code == 401
    assert response.json()['detail'] == 'Invalid email or password'

@pytest.mark.parametrize('fields',[{'is_active':False},{'is_email_verified':False},{'password_setup_required':True}])
@pytest.mark.parametrize('path',['/auth/login','/auth/staff-login'])
def test_account_status_blocks_both_flows(fields,path):
    account('LIBRARIAN',**fields)
    assert client.post(path,json={'email':'reader@example.com','password':PASSWORD}).status_code == 403

@pytest.mark.parametrize('role',['GENERAL_USER','LIBRARIAN'])
def test_non_admin_rejected_from_every_staff_api(role):
    account(role)
    for method,path,body in [('GET','/staff/',None),('POST','/staff/librarians',{'name':'New','email':'new@example.com'}),('PATCH','/staff/2',{'is_active':False}),('POST','/staff/2/resend-verification',None)]:
        result=client.request(method,path,headers=headers(role),**({'json':body} if body else {}))
        assert result.status_code == 403
    database.users_collection.insert_one.assert_not_called()
    database.users_collection.update_one.assert_not_called()

def test_reader_denied_existing_staff_apis():
    account()
    for path in ['/issues/all','/reservations/all','/fines/all','/activity/all']:
        assert client.get(path,headers=headers()).status_code == 403
    assert client.post('/inventory/',headers=headers(),json={'library_id':'TEST','work_id':'OL1W'}).status_code == 403

def test_stored_role_overrides_signed_stale_or_forged_role():
    account('GENERAL_USER')
    assert client.get('/staff/',headers=headers('ADMIN')).status_code == 403
    assert client.delete('/books/OL1W',headers=headers('ADMIN')).status_code == 403

def test_disabled_existing_token_rejected():
    account('ADMIN')
    token=headers('ADMIN')
    account('ADMIN',is_active=False)
    assert client.get('/staff/',headers=token).status_code == 401

@pytest.mark.parametrize('extra',[{'role':'ADMIN'},{'role':'LIBRARIAN'},{'is_admin':True},{'is_librarian':True},{'permissions':['admin']},{'staff':True},{'user_type':'ADMIN'}])
def test_public_signup_rejects_all_privilege_fields(extra):
    result=client.post('/auth/register',json={'name':'Reader','email':'new@example.com','password':PASSWORD,**extra})
    assert result.status_code == 422
    database.users_collection.insert_one.assert_not_called()

@pytest.mark.parametrize('extra',[{'role':'ADMIN'},{'is_admin':True},{'password':'client supplied'},{'is_email_verified':True}])
def test_staff_creation_rejects_hidden_privilege_fields(extra):
    account('ADMIN')
    result=client.post('/staff/librarians',headers=headers('ADMIN'),json={'name':'New','email':'new@example.com',**extra})
    assert result.status_code == 422
    database.users_collection.insert_one.assert_not_called()

def test_staff_login_role_field_rejected():
    account('ADMIN')
    assert client.post('/auth/staff-login',json={'email':'reader@example.com','password':PASSWORD,'role':'ADMIN'}).status_code == 422

def test_admin_staff_directory_whitelists_fields():
    user=account('ADMIN')
    database.users_collection.find.return_value.sort.return_value.skip.return_value.limit.return_value=[{**user,'otp':'not-for-output','token':'not-for-output'}]
    database.users_collection.count_documents.return_value=1
    result=client.get('/staff/',headers=headers('ADMIN'))
    assert result.status_code == 200
    row=result.json()['users'][0]
    assert set(row) == {'user_id','name','email','role','is_email_verified','is_active','created_at'}
    assert row['is_active'] is True

class AtomicCounter:
    def __init__(self): self.seq=0; self.lock=Lock()
    def update_one(self,query,update,**kwargs):
        with self.lock: self.seq=max(self.seq,update['$max']['seq'])
    def find_one_and_update(self,query,update,**kwargs):
        with self.lock:
            self.seq+=update['$inc']['seq']
            return {'seq':self.seq}

def test_numeric_ids_are_atomic_and_respect_existing_floor():
    from backend.services.identity_service import next_user_id
    account(user_id=50)
    database.db.__getitem__.return_value=AtomicCounter()
    with ThreadPoolExecutor(max_workers=12) as pool:
        ids=list(pool.map(lambda _:next_user_id(),range(120)))
    assert sorted(ids) == list(range(51,171))

def test_bootstrap_duplicate_email_refused():
    from backend.scripts.bootstrap_admin import bootstrap_first_admin
    account()
    with pytest.raises(ValueError,match='Email already registered'):
        bootstrap_first_admin('Admin','reader@example.com',PASSWORD)
    database.users_collection.insert_one.assert_not_called()

def test_bootstrap_existing_admin_refused():
    from backend.scripts.bootstrap_admin import bootstrap_first_admin
    database.users_collection.find_one.side_effect=lambda query,*a,**k: {'user_id':1} if query == {'role':'ADMIN'} else None
    with pytest.raises(ValueError,match='already exists'):
        bootstrap_first_admin('Admin','new@example.com',PASSWORD)
    database.users_collection.insert_one.assert_not_called()

def test_bootstrap_atomic_single_winner_lock():
    from backend.scripts.bootstrap_admin import bootstrap_first_admin
    from pymongo.errors import DuplicateKeyError
    database.db.__getitem__.return_value.insert_one.side_effect=DuplicateKeyError('locked')
    with pytest.raises(ValueError,match='in progress'):
        bootstrap_first_admin('Admin','new@example.com',PASSWORD)
    database.users_collection.insert_one.assert_not_called()

def test_bootstrap_creates_only_admin_with_hashed_password(monkeypatch):
    from backend.scripts import bootstrap_admin
    monkeypatch.setattr(bootstrap_admin,'next_user_id',lambda:10)
    result=bootstrap_admin.bootstrap_first_admin('Admin','NEW@example.com',PASSWORD)
    document=database.users_collection.insert_one.call_args.args[0]
    assert document['role'] == 'ADMIN' and document['is_email_verified'] and document['is_active']
    assert bcrypt.checkpw(PASSWORD.encode(),document['password_hash'].encode())
    assert set(result)=={'email','role'} and result['email']=='new@example.com'
    database.db.__getitem__.return_value.delete_one.assert_not_called()

def test_missing_identity_indexes_fail_without_creating_indexes():
    from backend.services.identity_service import next_user_id
    database.users_collection.list_indexes.return_value=[]
    with pytest.raises(RuntimeError,match='indexes are missing'): next_user_id()
    database.users_collection.create_index.assert_not_called()

def test_admin_creates_librarian_invitation(monkeypatch):
    from backend.services import staff_service
    account('ADMIN')
    monkeypatch.setattr(staff_service,'email_exists',lambda email:False)
    monkeypatch.setattr(staff_service,'next_user_id',lambda:12)
    sent=[]
    monkeypatch.setattr(staff_service,'resend_verification_otp',lambda email:sent.append(email))
    result=client.post('/staff/librarians',headers=headers('ADMIN'),json={'name':'Librarian','email':'NEW@example.com'})
    assert result.status_code == 201
    document=database.users_collection.insert_one.call_args.args[0]
    assert document['role']=='LIBRARIAN' and not document['is_email_verified']
    assert document['password_setup_required'] is True and sent==['new@example.com']
    assert 'password_hash' not in result.json()['user']

def test_email_failure_leaves_honest_pending_invitation(monkeypatch):
    from backend.services import staff_service
    account('ADMIN')
    monkeypatch.setattr(staff_service,'email_exists',lambda email:False)
    monkeypatch.setattr(staff_service,'next_user_id',lambda:12)
    def failed(email): raise RuntimeError('delivery unavailable')
    monkeypatch.setattr(staff_service,'resend_verification_otp',failed)
    result=client.post('/staff/librarians',headers=headers('ADMIN'),json={'name':'Librarian','email':'new@example.com'})
    assert result.status_code == 201 and result.json()['verification_sent'] is False
    assert result.json()['user']['is_email_verified'] is False

def test_admin_can_update_librarian_but_not_admin(monkeypatch):
    account('ADMIN')
    admin=database.users_collection.find_one.return_value
    database.users_collection.find_one.side_effect=lambda query,*a,**k: (None if query.get('role')=='LIBRARIAN' and query.get('user_id')==1 else {**admin,'user_id':2,'role':'LIBRARIAN'}) if 'role' in query else admin
    response=client.patch('/staff/2',headers=headers('ADMIN'),json={'name':'Renamed','is_active':False})
    assert response.status_code == 200
    assert database.users_collection.update_one.call_args.args[0]=={'user_id':2,'role':'LIBRARIAN'}
    assert client.patch('/staff/1',headers=headers('ADMIN'),json={'is_active':False}).status_code==404
    assert client.patch('/staff/2',headers=headers('ADMIN'),json={'role':'ADMIN'}).status_code==422

def test_staff_setup_consumes_otp_and_sets_own_password():
    account('LIBRARIAN',is_email_verified=False,password_setup_required=True)
    code='123456'
    database.email_verifications_collection.find_one_and_update.return_value={'_id':'test-code','otp_hash':bcrypt.hashpw(code.encode(),bcrypt.gensalt(rounds=4)).decode()}
    database.email_verifications_collection.delete_one.return_value.deleted_count=1
    database.users_collection.update_one.return_value.modified_count=1
    result=client.post('/auth/staff-setup',json={'email':'reader@example.com','otp':code,'password':PASSWORD})
    assert result.status_code==200
    update=database.users_collection.update_one.call_args.args[1]['$set']
    assert update['is_email_verified'] is True and update['password_setup_required'] is False
    assert bcrypt.checkpw(PASSWORD.encode(),update['password_hash'].encode())
    assert set(result.json())=={'message'}

@pytest.mark.parametrize('state',['no_invitation','expired','used','wrong','disabled'])
def test_staff_setup_cannot_create_or_escalate_accounts(state):
    account('LIBRARIAN' if state!='no_invitation' else 'GENERAL_USER',is_email_verified=False,password_setup_required=True,is_active=state!='disabled')
    database.email_verifications_collection.find_one_and_update.return_value=None
    if state in ('used','wrong'):
        database.email_verifications_collection.find_one_and_update.return_value={'_id':'x','otp_hash':bcrypt.hashpw(b'123456',bcrypt.gensalt(rounds=4)).decode()}
        database.email_verifications_collection.delete_one.return_value.deleted_count=0
    response=client.post('/auth/staff-setup',json={'email':'reader@example.com','otp':'999999' if state=='wrong' else '123456','password':PASSWORD})
    assert response.status_code==400
    database.users_collection.insert_one.assert_not_called()
    database.users_collection.update_one.assert_not_called()

def test_ordinary_otp_cannot_activate_invited_staff():
    account('LIBRARIAN',is_email_verified=False,password_setup_required=True)
    assert client.post('/auth/verify-email',json={'email':'reader@example.com','otp':'123456'}).status_code==400
    database.users_collection.update_one.assert_not_called()

def test_existing_reader_otp_still_works():
    account(is_email_verified=False)
    database.email_verifications_collection.find_one_and_update.return_value={'_id':'x','otp_hash':bcrypt.hashpw(b'123456',bcrypt.gensalt(rounds=4)).decode()}
    database.email_verifications_collection.delete_one.return_value.deleted_count=1
    result=client.post('/auth/verify-email',json={'email':'reader@example.com','otp':'123456'})
    assert result.status_code==200 and result.json()['user']['is_email_verified'] is True

def test_email_lookup_normalizes_without_changing_existing_records():
    account()
    result=client.post('/auth/login',json={'email':'  READER@example.com  ','password':PASSWORD})
    assert result.status_code==200
    query=database.users_collection.find.call_args.args[0]
    assert query['email']['$options']=='i'
    database.users_collection.update_one.assert_not_called()

def test_auth_rate_limit_is_bounded():
    from backend.utils.auth_rate_limit import AuthRateLimiter
    from fastapi import HTTPException
    limiter=AuthRateLimiter(limit=2)
    limiter.check('test-client');limiter.check('test-client')
    with pytest.raises(HTTPException) as error: limiter.check('test-client')
    assert error.value.status_code==429

@pytest.mark.parametrize('kind',['expired','no_exp','wrong_signature'])
def test_invalid_jwt_variants(kind):
    from jose import jwt
    account('ADMIN')
    payload={'sub':'1','email':'reader@example.com','role':'ADMIN'}
    if kind!='no_exp': payload['exp']=1 if kind=='expired' else int(datetime.now(timezone.utc).timestamp())+600
    token=jwt.encode(payload,'another-test-key' if kind=='wrong_signature' else jwt_utils.JWT_SECRET_KEY,algorithm='HS256')
    assert client.get('/staff/',headers={'Authorization':'Bearer '+token}).status_code==401

def test_staff_token_lifetime_uses_same_signer_with_shorter_expiry():
    from jose import jwt
    reader=jwt.get_unverified_claims(jwt_utils.create_access_token(1,'reader@example.com','GENERAL_USER'))
    staff=jwt.get_unverified_claims(jwt_utils.create_access_token(1,'reader@example.com','ADMIN'))
    assert 1799<=reader['exp']-staff['exp']<=1801

def test_normal_registration_still_creates_reader_with_verification():
    database.db.__getitem__.return_value=AtomicCounter()
    response=client.post('/auth/register',json={'name':'Reader','email':'NEW@example.com','password':PASSWORD})
    assert response.status_code==200
    row=database.users_collection.insert_one.call_args.args[0]
    assert row['role']=='GENERAL_USER' and row['email']=='new@example.com' and row['is_email_verified'] is False
    assert bcrypt.checkpw(PASSWORD.encode(),row['password_hash'].encode())
    assert database.email_verifications_collection.insert_one.call_count==1

def test_public_otp_responses_do_not_expose_staff_identity(monkeypatch):
    account('LIBRARIAN',is_email_verified=True)
    result=client.post('/auth/verify-email',json={'email':'reader@example.com','otp':'123456'})
    assert result.status_code==200 and set(result.json()['user'])=={'is_email_verified'}
    monkeypatch.setattr(auth_service,'send_otp_email',lambda *args:True)
    account('LIBRARIAN',is_email_verified=False)
    database.email_verifications_collection.find_one.return_value=None
    result=client.post('/auth/resend-verification',json={'email':'reader@example.com'})
    assert result.status_code==200 and set(result.json()['user'])=={'is_email_verified'}

def test_counter_first_use_race_retries_without_resetting_sequence():
    from backend.services.identity_service import next_user_id
    from pymongo.errors import DuplicateKeyError
    counter=database.db.__getitem__.return_value
    counter.update_one.side_effect=[DuplicateKeyError('concurrent initializer'),None]
    counter.find_one_and_update.return_value={'seq':100}
    assert next_user_id()==100
    assert counter.update_one.call_count==2
    assert counter.find_one_and_update.call_args.args[1]=={'$inc':{'seq':1}}


def admin_reset_accounts(*users):
    database.users_collection.find.return_value = list(users)


def test_admin_password_reset_no_admin(capsys):
    from backend.scripts import reset_admin_password
    admin_reset_accounts()
    assert reset_admin_password.main() == 0
    assert capsys.readouterr().out.strip() == 'No administrator account exists.'
    database.users_collection.update_one.assert_not_called()


def test_admin_password_reset_one_admin_shows_only_safe_identity(monkeypatch, capsys):
    from backend.scripts import reset_admin_password
    admin = account('ADMIN', name='Existing Admin', email='admin@example.com', secret='hidden')
    admin_reset_accounts(admin)
    monkeypatch.setattr('builtins.input', lambda prompt: 'n')
    assert reset_admin_password.main() == 0
    output = capsys.readouterr().out
    assert all(value in output for value in ('Existing Admin', 'admin@example.com', 'user_id: 1', 'role: ADMIN'))
    assert 'hidden' not in output and HASH not in output
    database.users_collection.update_one.assert_not_called()


@pytest.mark.parametrize('selector', ['second@example.com', '2'])
def test_admin_password_reset_multiple_requires_explicit_selection(monkeypatch, selector):
    from backend.scripts import reset_admin_password
    admins = [
        {'user_id': 1, 'name': 'First', 'email': 'first@example.com', 'role': 'ADMIN'},
        {'user_id': 2, 'name': 'Second', 'email': 'second@example.com', 'role': 'ADMIN'},
    ]
    admin_reset_accounts(*admins)
    answers = iter([selector, 'y'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(answers))
    monkeypatch.setattr(reset_admin_password.getpass, 'getpass', lambda prompt: PASSWORD)
    database.users_collection.update_one.return_value.matched_count = 1
    assert reset_admin_password.main() == 0
    assert database.users_collection.update_one.call_args.args[0] == {'user_id': 2, 'role': 'ADMIN'}


def test_admin_password_reset_wrong_confirmation_changes_nothing(monkeypatch):
    from backend.scripts import reset_admin_password
    admin_reset_accounts({'user_id': 1, 'name': 'Admin', 'email': 'admin@example.com', 'role': 'ADMIN'})
    monkeypatch.setattr('builtins.input', lambda prompt: 'no')
    assert reset_admin_password.main() == 0
    database.users_collection.update_one.assert_not_called()


def test_admin_password_reset_mismatching_passwords(monkeypatch):
    from backend.scripts import reset_admin_password
    admin_reset_accounts({'user_id': 1, 'name': 'Admin', 'email': 'admin@example.com', 'role': 'ADMIN'})
    monkeypatch.setattr('builtins.input', lambda prompt: 'y')
    passwords = iter([PASSWORD, PASSWORD + 'different'])
    monkeypatch.setattr(reset_admin_password.getpass, 'getpass', lambda prompt: next(passwords))
    assert reset_admin_password.main() == 1
    database.users_collection.update_one.assert_not_called()


@pytest.mark.parametrize('password', ['short', 'é' * 37])
def test_admin_password_reset_rejects_invalid_password_length(password):
    from backend.scripts.reset_admin_password import update_admin_password
    with pytest.raises(ValueError, match='Password'):
        update_admin_password(1, password)
    database.users_collection.update_one.assert_not_called()


def test_admin_password_reset_reuses_hashing_and_changes_only_password_hash():
    from backend.scripts.reset_admin_password import update_admin_password
    database.users_collection.update_one.return_value.matched_count = 1
    update_admin_password(7, PASSWORD)
    query, update = database.users_collection.update_one.call_args.args
    assert query == {'user_id': 7, 'role': 'ADMIN'}
    assert set(update) == {'$set'} and set(update['$set']) == {'password_hash'}
    assert bcrypt.checkpw(PASSWORD.encode(), update['$set']['password_hash'].encode())


def test_admin_password_reset_cannot_reset_non_admin():
    from backend.scripts.reset_admin_password import update_admin_password
    database.users_collection.update_one.return_value.matched_count = 0
    with pytest.raises(ValueError, match='not an Admin'):
        update_admin_password(9, PASSWORD)
    assert database.users_collection.update_one.call_args.args[0] == {'user_id': 9, 'role': 'ADMIN'}
