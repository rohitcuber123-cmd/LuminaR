"""Authenticate and bind the disposable DB BEFORE importing any native app module."""
import gc,os
from pathlib import Path
from uuid import uuid4
import pytest
from scripts.institution_v2l_fixture import AuthMongo,provision,seed_database,provision_unauthorized
from backend.services.library_worker_telemetry import COLLECTION,SLOT


@pytest.fixture(scope='module')
def server():
    with AuthMongo() as s:
        seed_database(s);provision(s);provision_unauthorized(s);yield s
        gc.collect()


@pytest.fixture
def lab(server,monkeypatch):
    server.db[COLLECTION].replace_one({'_id':SLOT},{'_id':SLOT,'schema':1,'epoch':0,'current':None,'previous':None},upsert=True)
    for suffix in ['intelligence_jobs','intelligence_targets','intelligence_generations','intelligence_sequences','locks','libraries','memberships','library_books']:
        server.db['institution_'+suffix].delete_many({})
    monkeypatch.setenv('MONGO_URI',server.writer_uri);monkeypatch.setenv('MONGO_DB_NAME',server.database)
    monkeypatch.setenv('LIBRARY_INTELLIGENCE_ROOT',str(server.artifact_root))
    monkeypatch.setenv('NOTIFICATION_DUE_WORKER_ENABLED','0');monkeypatch.setenv('NOTIFICATION_OUTBOX_WORKER_ENABLED','0')
    monkeypatch.delenv('LUMINAR_WORKER_TELEMETRY_ENABLED',raising=False)
    monkeypatch.delenv('LUMINAR_WORKER_TELEMETRY_MONGO_URI',raising=False)
    yield server
    gc.collect()


@pytest.fixture
def writer(lab):
    from backend.services.library_worker_observer import Configuration,RestrictedWriter
    a=RestrictedWriter(Configuration(lab.database,lab.telemetry_uri),'tenant-'+str(uuid4()));a.start()
    yield a
    a.close()


@pytest.fixture
def worker_factory(lab):
    from backend.services import institution_repository as repo,library_catalogue_repository as inventory,library_intelligence_store as store
    from search.library_intelligence import TenantIntelligence
    assert store.collection('intelligence_jobs').database.name==lab.database
    repo.ensure_indexes();inventory.ensure_indexes();store.initialize()
    lab.db.users.update_one({'user_id':1},{'$set':{'email':'v2l@example.com','name':'Fixture owner','role':'GENERAL_USER','is_active':True,'is_email_verified':True}},upsert=True)
    workers=[]
    def create(**kwargs):
        import numpy as np
        def encoder(texts):return np.ones((len(texts),384),dtype=np.float32)
        w=TenantIntelligence(encoder,**kwargs);workers.append(w);return w
    yield create
    for w in workers:
        w.close()
        if w.thread:w.thread.join(timeout=6)
        assert not w.thread or not w.thread.is_alive()
    gc.collect()


@pytest.fixture
def library(lab,worker_factory):
    def seed(private=True):
        lib=str(uuid4())
        lab.db.institution_libraries.insert_one({'library_id':lib,'slug_normalized':lib,'name':'Private observer fixture','status':'ACTIVE',
            'library_type':'PRIVATE_INSTITUTION' if private else 'PUBLIC_LIBRARY','access_mode':'PRIVATE_CODE' if private else 'PUBLIC'})
        lab.db.institution_memberships.insert_one({'library_id':lib,'membership_id':str(uuid4()),'user_id':1,'role':'ADMIN','is_owner':True,'status':'ACTIVE'})
        lab.db.institution_library_books.insert_many([{'library_id':lib,'library_book_id':str(uuid4()),'status':'ACTIVE','accession_number':str(i),
            'accession_sequence':i,'title':'Private synthetic fixture '+str(i),'authors':['Fixture author'],'subjects':['Technology'],'description':'Synthetic only'} for i in range(3)])
        return lib
    return seed
