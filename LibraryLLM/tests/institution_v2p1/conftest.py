"""Real standalone Mongo, uniquely owned database, production authority services."""
import os
from uuid import uuid4
os.environ['MONGO_URI']='mongodb://127.0.0.1:27017'
os.environ['MONGO_DB_NAME']='luminar_institution_v2p1_test_'+uuid4().hex
os.environ['JWT_SECRET_KEY']='part2p-disposable-test-key-not-deployment'
os.environ['NOTIFICATION_DUE_WORKER_ENABLED']='0'
os.environ['NOTIFICATION_OUTBOX_WORKER_ENABLED']='0'
os.environ['ISBN_LOOKUP_DB']='D:/SDC/LibraryLLM/.scratch/institution-v2p1/no-isbn.duckdb'
os.environ['LUMINAR_SESSION_DB']='D:/SDC/LibraryLLM/.scratch/institution-v2p1/sessions-'+uuid4().hex+'.sqlite'
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from backend.main import app
from backend.dependencies import get_current_user
from backend.database.mongodb import db, client as mongo
from backend.services import institution_repository as ir, notification_service as ns, library_announcement_service as service, event_service
from backend.routes.library_announcements import router
if not any(getattr(r,'path','')=='/libraries/{library_id}/announcements' for r in app.routes): app.include_router(router)

@pytest.fixture(scope='session',autouse=True)
def lifecycle():
    mongo.admin.command('ping')
    for m in [ir,ns,service,event_service]: m.ensure_indexes()
    yield
    assert db.name.startswith('luminar_institution_v2p1_test_')
    mongo.drop_database(db.name)
    from pathlib import Path
    Path(os.environ['LUMINAR_SESSION_DB']).unlink(missing_ok=True)

@pytest.fixture(autouse=True)
def isolation():
    for name in db.list_collection_names(): db[name].delete_many({})
    db.users.insert_many([{'user_id':i,'name':f'User {i}','email':f'part2p-{i}@example.com','role':'ADMIN' if i==9 else 'GENERAL_USER','is_active':True,'is_email_verified':True} for i in range(1,16)])
    def identity(request:Request): return {'sub':request.headers.get('x-test-user','1'),'role':request.headers.get('x-test-role','ADMIN')}
    app.dependency_overrides[get_current_user]=identity
    yield
    app.dependency_overrides.clear()

@pytest.fixture
def client(): return TestClient(app)

@pytest.fixture
def database(): return db

@pytest.fixture
def libraries(client):
    def create(owner=1,private=False):
        value={'name':'Part2P fixture','slug':'part2p-'+uuid4().hex[:12],'library_type':'PRIVATE_INSTITUTION' if private else 'PUBLIC_LIBRARY','access_mode':'PRIVATE_CODE' if private else 'PUBLIC'}
        if private:value['access_code']='Disposable private code'
        r=client.post('/libraries/register',headers={'x-test-user':str(owner)},json=value)
        assert r.status_code==201,r.text
        return r.json()['library']['library_id']
    return create

@pytest.fixture
def setup(libraries,database):
    lib=libraries(private=True)
    for uid,role in [(2,'GENERAL_USER'),(3,'LIBRARIAN'),(4,'GENERAL_USER')]:
        database.institution_memberships.insert_one({'membership_id':str(uuid4()),'library_id':lib,'user_id':uid,'role':role,'status':'ACTIVE'})
    return lib
