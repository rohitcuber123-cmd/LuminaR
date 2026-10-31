import pytest
from scripts.institution_v2k_fixture import AuthMongo,provision,seed_database
from scratch.institution_v2k_telemetry.telemetry import COLLECTION,SLOT,Actor
from uuid import uuid4


@pytest.fixture(scope='module')
def server():
    with AuthMongo() as s:
        seed_database(s);provision(s);yield s


@pytest.fixture
def lab(server):
    server.db[COLLECTION].replace_one({'_id':SLOT},{'_id':SLOT,'schema':1,'epoch':0,'current':None,'previous':None},upsert=True)
    server.db.institution_intelligence_jobs.delete_many({})
    server.db.institution_intelligence_targets.delete_many({})
    yield server


@pytest.fixture
def actor(lab):
    a=Actor(lab.telemetry_uri,lab.database,'tenant-'+str(uuid4()));a.start()
    yield a
    a.close()
