"""Real Mongo and production guards, isolated disposable canonical libraries."""
import os
from uuid import uuid4
os.environ['MONGO_URI']='mongodb://127.0.0.1:27017'
os.environ['MONGO_DB_NAME']='luminar_institution_v2d_test_'+uuid4().hex
os.environ['JWT_SECRET_KEY']='institution-v2d-disposable-key'
os.environ['ISBN_LOOKUP_DB']='D:/SDC/LibraryLLM/.scratch/institution-v2d/no-isbn-lookup.duckdb'
os.environ['NOTIFICATION_DUE_WORKER_ENABLED']='0'
os.environ['NOTIFICATION_OUTBOX_WORKER_ENABLED']='0'
import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from backend.main import app
from backend.dependencies import get_current_user
from backend.database.mongodb import db, client as mongo
from backend.services import institution_repository, library_catalogue_repository, library_lending_journal, library_reservation_service, event_service, notification_service, tenant_notification_service, library_event_service


@pytest.fixture(scope='session',autouse=True)
def database_lifecycle():
    mongo.admin.command('ping')
    for module in [institution_repository,library_catalogue_repository,library_lending_journal,library_reservation_service,event_service,notification_service,tenant_notification_service,library_event_service]:module.ensure_indexes()
    yield
    assert db.name.startswith('luminar_institution_v2d_test_')
    mongo.drop_database(db.name)


@pytest.fixture(autouse=True)
def isolate():
    for name in db.list_collection_names():db[name].delete_many({})
    db.users.insert_many([{'user_id':i,'name':f'User {i}','email':f'v2d-{i}@example.com','role':'ADMIN' if i==9 else 'GENERAL_USER','is_active':True,'is_email_verified':True} for i in range(1,15)])
    db.books.insert_one({'work_id':'OL1W','title':'Networks','authors':['Author']})
    def identity(request:Request):return {'sub':request.headers.get('x-test-user','1'),'role':request.headers.get('x-test-role','GENERAL_USER')}
    app.dependency_overrides[get_current_user]=identity
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():return TestClient(app)


@pytest.fixture
def database():return db


@pytest.fixture
def libraries(client):
    def create(owner=1,private=False,name='V2D Library'):
        value={'name':name,'slug':'v2d-'+uuid4().hex[:12],'library_type':'PRIVATE_INSTITUTION' if private else 'PUBLIC_LIBRARY','access_mode':'PRIVATE_CODE' if private else 'PUBLIC'}
        if private:value['access_code']='Disposable library fixture code'
        response=client.post('/libraries/register',headers={'x-test-user':str(owner)},json=value)
        assert response.status_code==201,response.text
        return response.json()['library']['library_id']
    return create


@pytest.fixture
def setup(client,libraries,database):
    library=libraries()
    for uid,role in [(2,'GENERAL_USER'),(3,'LIBRARIAN'),(4,'GENERAL_USER')]:
        database.institution_memberships.insert_one({'library_id':library,'user_id':uid,'membership_id':str(uuid4()),'role':role,'status':'ACTIVE'})
    response=client.post(f'/libraries/{library}/inventory/books',json={'title':'V2D Canonical Book','subjects':['Systems'],'idempotency_key':str(uuid4())})
    assert response.status_code==201,response.text
    return library,response.json()['library_book_id']
