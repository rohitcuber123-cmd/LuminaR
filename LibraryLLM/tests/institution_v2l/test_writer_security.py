"""Actual auth-enabled Mongo permissions; no native app imports in this module."""
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
import json,os,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
import pytest
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from bson import BSON
from backend.services.library_worker_telemetry import COLLECTION,SLOT,TelemetryError
from backend.services.library_worker_observer import Configuration,RestrictedWriter,configured_factory,ENABLE_ENV,URI_ENV
from backend.services.library_worker_diagnostics import inspect_telemetry
from backend.services.library_operator_access import connect_operator,DiagnosticError
ROOT=Path(__file__).resolve().parents[2]


def record(s):return s.db[COLLECTION].find_one({'_id':SLOT})
def job(s,w,**changes):
    j={'job_id':str(uuid4()),'library_id':str(uuid4()),'worker_id':w.owner,'fence_token':str(uuid4()),'target':'SEARCH_INDEX',
        'state':'RUNNING','stage':'EMBEDDING','progress_current':0,'progress_total':10,'effective_active':True,
        'heartbeat_at':datetime.now(timezone.utc),'lease_expires_at':datetime.now(timezone.utc)+timedelta(seconds=90),
        'artifact_generation_id':str(uuid4()),'requested_generation_id':str(uuid4())}
    j.update(changes);s.db.institution_intelligence_jobs.insert_one(j);return j


def test_telemetry_disabled_by_default(lab):
    for env in [{},{URI_ENV:lab.telemetry_uri},{ENABLE_ENV:'true',URI_ENV:lab.telemetry_uri},{ENABLE_ENV:'0',URI_ENV:lab.telemetry_uri}]:
        assert configured_factory(lab.database,environ=env) is None
    assert record(lab)['epoch']==0

def test_telemetry_explicit_opt_in(lab):
    f=configured_factory(lab.database,environ={ENABLE_ENV:'1',URI_ENV:lab.telemetry_uri});a=f('tenant-'+str(uuid4()))
    try:a.started();assert a.ready.wait(3) and a.state=='OBSERVING' and record(lab)['epoch']==1
    finally:a.stopped()
    assert not a.thread.is_alive()

def test_missing_writer_credential_no_fallback(lab,caplog):
    env={ENABLE_ENV:'1','MONGO_URI':lab.writer_uri,'LUMINAR_OPERATOR_MONGO_URI':lab.reader_uri}
    assert configured_factory(lab.database,environ=env) is None and record(lab)['epoch']==0
    assert 'MISSING_WRITER_CREDENTIAL' in caplog.text and lab.writer_uri not in caplog.text

@pytest.mark.parametrize('kind',['wrong_password','read_operator','root','anonymous','other_database'])
def test_invalid_writer_credential_no_fallback(lab,kind,caplog):
    uri={'wrong_password':lab.telemetry_uri.replace(lab.telemetry_password,'invalid-private-secret'),'read_operator':lab.reader_uri,
         'root':lab.writer_uri,'anonymous':f'mongodb://127.0.0.1:{lab.port}/{lab.database}',
         'other_database':lab.telemetry_uri.replace('/'+lab.database+'?','/foreign?')}[kind]
    f=configured_factory(lab.database,environ={ENABLE_ENV:'1',URI_ENV:uri,'MONGO_URI':lab.writer_uri})
    a=f('tenant-'+str(uuid4()))
    try:a.started();assert a.ready.wait(3) and a.state=='UNAVAILABLE' and record(lab)['epoch']==0
    finally:a.stopped()
    assert uri not in caplog.text and 'invalid-private-secret' not in caplog.text

def test_telemetry_writer_restricted_role(lab,writer):
    assert writer.pulse();info=writer.db.command('connectionStatus',showPrivileges=True)['authInfo']
    assert len(info['authenticatedUsers'])==1 and info['authenticatedUsers'][0]['db']==lab.database

def test_uri_cannot_weaken_primary_acknowledged_writer(lab):
    from pymongo.read_preferences import ReadPreference
    a=RestrictedWriter(Configuration(lab.database,lab.telemetry_uri+'&w=0&readPreference=secondaryPreferred&maxPoolSize=1000'),'tenant-'+str(uuid4()))
    try:
        assert a.db.read_preference==ReadPreference.PRIMARY and a.db.write_concern.document=={'j':True,'w':1}
        assert a.client.options.pool_options.max_pool_size==2
        a.start();assert a.pulse()
    finally:a.close()

def test_operator_secondary_read_rejected(lab):
    r=connect_operator(lab.reader_uri+'&readPreference=secondaryPreferred',lab.database)
    try:
        with pytest.raises(DiagnosticError,match='PRIMARY_READ_REQUIRED'):inspect_telemetry(r,str(uuid4()))
    finally:r.close()

@pytest.mark.parametrize('name',['institution_intelligence_jobs','institution_intelligence_targets','institution_intelligence_generations',
    'institution_locks','institution_library_books','institution_memberships','users','institution_library_assets','institution_library_asset_jobs','personal_rag_records','books'])
def test_telemetry_writer_cannot_modify_authoritative_data(lab,writer,name):
    with pytest.raises(OperationFailure) as e:writer.db[name].update_one({'_id':'fixture'},{'$set':{'state':'SUCCEEDED'}},upsert=True)
    assert e.value.code==13

def test_writer_no_insert_delete_schema_grant(lab,writer):
    for f in [lambda:writer.collection.insert_one({'_id':'extra'}),lambda:writer.collection.delete_one({'_id':SLOT}),lambda:writer.collection.create_index('epoch')]:
        with pytest.raises(OperationFailure) as e:f()
        assert e.value.code==13

def test_operator_read_only_preserved(lab,writer):
    r=connect_operator(lab.reader_uri,lab.database)
    try:
        assert inspect_telemetry(r,str(uuid4()))['read_only']
        for coll in [COLLECTION,'institution_intelligence_jobs']:
            with pytest.raises(OperationFailure) as e:r.database[coll].update_one({'_id':SLOT},{'$set':{'epoch':9}})
            assert e.value.code==13
    finally:r.close()

def test_unauthorized_read_and_writer_denied(lab):
    with pytest.raises(DiagnosticError):connect_operator(lab.unauthorized_uri,lab.database)
    c=MongoClient(lab.unauthorized_uri)
    try:
        with pytest.raises(OperationFailure) as e:c[lab.database][COLLECTION].find_one({'_id':SLOT})
        assert e.value.code==13
        with pytest.raises(OperationFailure) as e:c[lab.database][COLLECTION].update_one({'_id':SLOT},{'$set':{'epoch':99}})
        assert e.value.code==13
    finally:c.close()

@pytest.mark.parametrize('role',['GENERAL_USER','LIBRARIAN','LIBRARY_ADMIN','PLATFORM_ADMIN','OUTSIDER'])
def test_application_role_not_operator_or_writer(lab,role):
    with pytest.raises(DiagnosticError):connect_operator('JWT-'+role,lab.database)
    with pytest.raises(TelemetryError):RestrictedWriter(Configuration(lab.database,'JWT-'+role),'tenant-'+str(uuid4()))

def test_progress_observed_after_durable_change(lab,writer):
    j=job(lab,writer);writer.observe(j);before=record(lab)['current']['progress'][0]
    assert before['progress_current']==0
    lab.db.institution_intelligence_jobs.update_one({'job_id':j['job_id']},{'$set':{'progress_current':4}});time.sleep(.01);writer.observe(j)
    after=record(lab)['current']['progress'][0]
    assert after['progress_current']==4 and after['last_progress_observed_at']>before['last_progress_observed_at']

def test_progress_identical_tuple_and_lease_heartbeat_no_new_event(lab,writer):
    j=job(lab,writer);writer.observe(j);before=record(lab)['current']['progress'][0]
    for _ in range(3):
        lab.db.institution_intelligence_jobs.update_one({'job_id':j['job_id']},{'$set':{'heartbeat_at':datetime.now(timezone.utc)}});writer.observe(j)
    assert record(lab)['current']['progress'][0]==before and writer.metrics['progress_write']==1

def test_terminal_counter_not_publication(lab,writer):
    j=job(lab,writer,state='SUCCEEDED',stage='COMPLETE',progress_current=10,effective_active=False);writer.observe(j)
    e=record(lab)['current']['progress'][0]
    assert e['publication']=='UNKNOWN' and e['last_progress_observed_at'] is None

@pytest.mark.parametrize('changes',[{'fence_token':str(uuid4())},{'worker_id':'tenant-'+str(uuid4())},{'lease_expires_at':datetime.now(timezone.utc)-timedelta(seconds=1)}])
def test_fence_claim_mismatch_and_expired_lease_rejected(lab,writer,changes):
    j=job(lab,writer);before=lab.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})
    lab.db.institution_intelligence_jobs.update_one({'job_id':j['job_id']},{'$set':changes})
    assert writer.observe(j) is False and record(lab)['current']['progress']==[]

def test_old_observer_late_write_and_epoch_cas(lab,writer):
    b=RestrictedWriter(Configuration(lab.database,lab.telemetry_uri),writer.owner)
    try:b.start();before=record(lab);assert not writer.pulse() and writer.ownership_lost;assert record(lab)==before
    finally:b.close()

def test_concurrent_instance_startup(lab,writer):
    actors=[RestrictedWriter(Configuration(lab.database,lab.telemetry_uri),'tenant-'+str(uuid4())) for _ in range(2)]
    def boot(a):
        try:return a.start()
        except TelemetryError:return False
    try:
        with ThreadPoolExecutor(2) as p:list(p.map(boot,actors))
        assert sum(a.pulse() for a in actors if a.epoch is not None)==1
    finally:
        for a in actors:a.close()

def test_telemetry_storage_cap(lab,writer):
    for _ in range(12):writer.observe(job(lab,writer))
    b=RestrictedWriter(Configuration(lab.database,lab.telemetry_uri),writer.owner)
    try:
        b.start()
        for _ in range(12):b.observe(job(lab,b))
        d=record(lab);assert len(d['current']['progress'])==len(d['previous']['progress'])==8
        assert len(BSON.encode(d))<=16384 and lab.db[COLLECTION].count_documents({})==1
        for v in [{'current.progress':[{}]*9},{'payload':'x'*16384}]:
            with pytest.raises(OperationFailure) as e:b.collection.update_one({'_id':SLOT},{'$set':v})
            assert e.value.code==121
    finally:b.close()

def test_operator_cli_bounded_output_and_secret_redaction(lab,writer):
    j=job(lab,writer);writer.observe(j);writer.pulse('ACTIVE',j)
    p=subprocess.run([sys.executable,str(ROOT/'scripts/diagnose_worker_telemetry.py'),'--database',lab.database,'--library-id',j['library_id'],'--format','json'],
        env={**os.environ,'LUMINAR_OPERATOR_MONGO_URI':lab.reader_uri},capture_output=True,text=True,timeout=10)
    assert p.returncode==0 and len(p.stdout)<16384
    for secret in [writer.instance_id,writer.boot_hash,writer.owner,j['fence_token'],lab.telemetry_password,lab.read_password]:assert secret not in p.stdout
    d=json.loads(p.stdout);assert not d['worker']['process_independently_verified'] and d['associated_job']['job_id']==j['job_id']

def test_private_multi_tenant_job_correlation(lab,writer):
    a=job(lab,writer);b=job(lab,writer,target='KNOWLEDGE_GRAPH');writer.observe(a);writer.observe(b);writer.pulse('ACTIVE',b)
    r=connect_operator(lab.reader_uri,lab.database)
    try:
        va,vb=inspect_telemetry(r,a['library_id']),inspect_telemetry(r,b['library_id'])
        assert b['library_id'] not in json.dumps(va) and b['job_id'] not in json.dumps(va)
        assert va['associated_job'] is None and vb['associated_job']['job_id']==b['job_id']
    finally:r.close()

def test_legacy_job_without_telemetry(lab):
    r=connect_operator(lab.reader_uri,lab.database)
    try:
        v=inspect_telemetry(r,str(uuid4()));assert v['worker']['classification']=='UNKNOWN' and v['progress']==[]
    finally:r.close()
