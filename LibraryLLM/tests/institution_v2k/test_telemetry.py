"""Real authenticated Mongo contract tests. Native worker cases are a separate child experiment."""
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
import json,os,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
import pytest
from bson import BSON
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from backend.services.library_operator_access import connect_operator,DiagnosticError
from scratch.institution_v2k_telemetry.telemetry import Actor,Agent,TelemetryError,COLLECTION,SLOT,MAX_BYTES
from scratch.institution_v2k_telemetry.observer import classify,inspect_telemetry

ROOT=Path(__file__).resolve().parents[2]


def record(s):return s.db[COLLECTION].find_one({'_id':SLOT})
def entry(s):return record(s)['current']['progress'][-1]
def job(s,a,**kw):
    row={'job_id':str(uuid4()),'library_id':str(uuid4()),'fence_token':str(uuid4()),'worker_id':a.owner,
         'target':'SEARCH_INDEX','state':'RUNNING','stage':'EMBEDDING','progress_current':0,'progress_total':10,
         'effective_active':True,'lease_expires_at':datetime.now(timezone.utc)+timedelta(seconds=90),
         'artifact_generation_id':str(uuid4()),'requested_generation_id':str(uuid4())}
    row.update(kw);s.db.institution_intelligence_jobs.insert_one(row);return row
def change(s,j,**kw):s.db.institution_intelligence_jobs.update_one({'job_id':j['job_id']},{'$set':kw})
def view(s,lib):
    r=connect_operator(s.reader_uri,s.database)
    try:return inspect_telemetry(r,lib)
    finally:r.close()


def test_worker_instance_unique_per_start(lab,actor):
    b=Actor(lab.telemetry_uri,lab.database,actor.owner)
    try:b.start();assert b.instance_id!=actor.instance_id and record(lab)['epoch']==2
    finally:b.close()

def test_worker_instance_restart_identity(lab,actor):
    actor.pulse('STOPPED');b=Actor(lab.telemetry_uri,lab.database,'tenant-'+str(uuid4()))
    try:
        b.start();r=record(lab);assert r['previous']['instance_id']==actor.instance_id
        assert classify(r,datetime.now(timezone.utc))['restart_observed']
    finally:b.close()

def test_worker_idle_liveness_observation(lab,actor):
    actor.pulse();assert view(lab,str(uuid4()))['worker']['idle'] is True

def test_worker_active_liveness_observation(lab,actor):
    j=job(lab,actor);actor.pulse('ACTIVE',j)
    v=view(lab,j['library_id']);assert v['worker']['active_job_observed'] and not v['worker']['process_independently_verified']

def test_worker_graceful_shutdown_best_effort(lab,actor):
    actor.pulse('STOPPED');r=record(lab);assert classify(r,datetime.now(timezone.utc))['classification']=='STOPPED_REPORTED'

def test_worker_crash_stale_observation(lab,actor):
    r=record(lab);assert classify(r,datetime.now(timezone.utc)+timedelta(seconds=31))['classification']=='STALE'

def test_worker_recent_pulse_not_verified_process(lab,actor):
    v=view(lab,str(uuid4()));assert v['worker']['classification']=='RECENTLY_OBSERVED'
    assert v['worker']['process_independently_verified'] is False and v['worker']['stalled']=='NOT_DETERMINED'

def test_worker_future_heartbeat_clock_skew(lab,actor):
    r=record(lab);r['current']['last_seen_at']=datetime.now(timezone.utc)+timedelta(seconds=1)
    assert classify(r,datetime.now(timezone.utc))['classification']=='UNKNOWN'

def test_server_clock_rollback_sticky(lab,actor):
    lab.db[COLLECTION].update_one({'_id':SLOT},{'$set':{'current.last_seen_at':datetime.now(timezone.utc)+timedelta(days=1)}})
    actor.pulse();assert record(lab)['current']['clock_rollback'] is True
    assert view(lab,str(uuid4()))['worker']['classification']=='UNKNOWN'

def test_worker_missing_telemetry_unknown(lab):
    lab.db[COLLECTION].delete_one({'_id':SLOT});assert view(lab,str(uuid4()))['worker']['classification']=='UNKNOWN'

def test_worker_legacy_job_unknown(lab,actor):
    j=job(lab,actor);assert view(lab,j['library_id'])['progress']==[]

def test_worker_pulse_failure_does_not_corrupt_job(lab,actor):
    j=job(lab,actor);before=lab.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})
    def fail():raise TimeoutError('secret password URI must not escape')
    with pytest.raises(TelemetryError,match='AUXILIARY_UNAVAILABLE'):actor.call('pulse_write',fail)
    assert lab.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})==before

def test_worker_telemetry_authentication(lab):
    for uri in [lab.reader_uri,lab.writer_uri,'mongodb://127.0.0.1:27017/'+lab.database]:
        with pytest.raises(TelemetryError):Actor(uri,lab.database,'tenant-'+str(uuid4()))

def test_operator_read_only_credential_preserved(lab,actor):
    c=MongoClient(lab.reader_uri)
    try:
        with pytest.raises(OperationFailure) as e:c[lab.database][COLLECTION].update_one({'_id':SLOT},{'$set':{'epoch':999}})
        assert e.value.code==13
    finally:c.close()

@pytest.mark.parametrize('role',['OUTSIDER','GENERAL_USER','LIBRARIAN','LIBRARY_ADMIN','PLATFORM_ADMIN'])
def test_operator_unauthorized_telemetry_denied(lab,role):
    with pytest.raises(DiagnosticError):connect_operator('jwt-'+role,lab.database)

@pytest.mark.parametrize('collection',['institution_intelligence_jobs','institution_intelligence_targets','institution_locks','books','institution_libraries'])
def test_writer_cannot_mutate_native_or_global(lab,actor,collection):
    with pytest.raises(OperationFailure) as e:actor.db[collection].update_one({'_id':'fixture'},{'$set':{'state':'SUCCEEDED'}},upsert=True)
    assert e.value.code==13

def test_writer_cannot_insert_delete_or_create(lab,actor):
    for operation in [lambda:actor.collection.insert_one({'_id':'foreign'}),lambda:actor.collection.delete_one({'_id':SLOT}),lambda:actor.db.create_collection('arbitrary')]:
        with pytest.raises(OperationFailure) as e:operation()
        assert e.value.code==13

def test_job_progress_timestamp_on_real_change(lab,actor):
    j=job(lab,actor);actor.observe(j);before=entry(lab);time.sleep(.01)
    change(lab,j,progress_current=3);actor.observe(j);after=entry(lab)
    assert after['last_progress_observed_at']>before['last_progress_observed_at'] and after['progress_current']==3

def test_job_progress_timestamp_not_on_heartbeat(lab,actor):
    j=job(lab,actor);actor.observe(j);before=entry(lab)
    change(lab,j,heartbeat_at=datetime.now(timezone.utc));actor.observe(j);actor.pulse('ACTIVE',j)
    assert entry(lab)==before and record(lab)['current']['pulse_seq']==1

def test_job_progress_timestamp_not_on_same_counter(lab,actor):
    j=job(lab,actor);actor.observe(j);before=entry(lab)
    change(lab,j,progress_current=0,progress_total=10);actor.observe(j)
    assert entry(lab)==before and actor.metrics['progress_write']==1

def test_job_progress_fenced_or_causally_valid(lab,actor):
    j=job(lab,actor);actor.observe(j);before=entry(lab)
    change(lab,j,fence_token=str(uuid4()),progress_current=9)
    assert actor.observe(j) is False and entry(lab)==before
    assert view(lab,j['library_id'])['progress'][0]['recency']=='UNKNOWN'

@pytest.mark.parametrize('state,stage,count,target',[('RUNNING','EMBEDDING',3,'SEARCH_INDEX'),('RUNNING','KG_METADATA',5,'KNOWLEDGE_GRAPH'),('VALIDATING','VALIDATION',10,'SEARCH_INDEX'),('PUBLISHING','PUBLISH',10,'KNOWLEDGE_GRAPH')])
def test_job_progress_native_phase_contract(lab,actor,state,stage,count,target):
    j=job(lab,actor,target=target);actor.observe(j)
    change(lab,j,state=state,stage=stage,progress_current=count);actor.observe(j)
    assert entry(lab)['stage']==stage and entry(lab)['kind']=='PROGRESS'

def test_job_terminal_pointer_verification(lab,actor):
    j=job(lab,actor,state='SUCCEEDED',stage='COMPLETE',effective_active=False,progress_current=10)
    actor.observe(j);assert entry(lab)['publication']=='UNKNOWN' and entry(lab)['last_progress_observed_at'] is None
    lab.db.institution_intelligence_targets.insert_one({'library_id':j['library_id'],'target':j['target'],'published_by_job_id':j['job_id'],
        'active_generation_id':j['artifact_generation_id'],'source_generation_id':j['requested_generation_id']})
    # A repeated terminal tuple is deliberately not upgraded by the writer; a new instance may observe the acknowledged pointer.
    b=Actor(lab.telemetry_uri,lab.database,actor.owner)
    try:
        b.start();b.observe(j);assert entry(lab)['publication']=='ACKNOWLEDGED_POINTER_MATCH'
        assert view(lab,j['library_id'])['progress'][0]['publication']=='ACKNOWLEDGED_POINTER_MATCH'
        lab.db.institution_intelligence_targets.update_one({'library_id':j['library_id']},{'$set':{'active_generation_id':str(uuid4())}})
        assert view(lab,j['library_id'])['progress'][0]['recency']=='UNKNOWN'
    finally:b.close()

def test_progress_recency_unknown_when_missing(lab,actor):
    j=job(lab,actor,state='FAILED',stage='FAILED',effective_active=False);actor.observe(j)
    assert view(lab,j['library_id'])['progress'][0]['recency']=='UNKNOWN'

def test_stalled_warning_not_worker_death(lab,actor):
    j=job(lab,actor);actor.observe(j)
    old=datetime.now(timezone.utc)-timedelta(seconds=60)
    lab.db[COLLECTION].update_one({'_id':SLOT},{'$set':{'current.progress.0.last_progress_observed_at':old}})
    v=view(lab,j['library_id']);assert v['progress'][0]['recency']=='NO_RECENT_PROGRESS_OBSERVED'
    assert v['progress'][0]['stalled']=='NOT_DETERMINED' and v['worker']['classification']=='RECENTLY_OBSERVED'

def test_no_auto_actions_from_stale_telemetry(lab,actor):
    j=job(lab,actor,state='RECOVERY_REQUIRED',stage='RECOVERY_REQUIRED');actor.observe(j)
    before=list(lab.db.institution_intelligence_jobs.find({}))
    for _ in range(3):view(lab,j['library_id'])
    assert list(lab.db.institution_intelligence_jobs.find({}))==before
    assert lab.db.institution_intelligence_targets.count_documents({})==0

def test_old_instance_late_write_rejected(lab,actor):
    b=Actor(lab.telemetry_uri,lab.database,actor.owner)
    try:
        b.start();before=record(lab);assert actor.pulse() is False
        assert record(lab)==before
    finally:b.close()

def test_worker_restart_with_old_lease(lab,actor):
    j=job(lab,actor);actor.observe(j);before=lab.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})
    b=Actor(lab.telemetry_uri,lab.database,'tenant-'+str(uuid4()))
    try:
        b.start();assert view(lab,j['library_id'])['progress']==[]
        assert lab.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})==before
    finally:b.close()

def test_two_worker_instance_race(lab,actor):
    actors=[Actor(lab.telemetry_uri,lab.database,'tenant-'+str(uuid4())) for _ in range(2)]
    try:
        def boot(a):
            try:return a.start()
            except TelemetryError:return False
        with ThreadPoolExecutor(2) as pool:list(pool.map(boot,actors))
        assert sum(a.pulse() for a in actors if a.epoch is not None)==1
    finally:
        for a in actors:a.close()

def test_duplicate_instance_rejected(lab,actor):
    b=Actor(lab.telemetry_uri,lab.database,actor.owner,instance_factory=lambda:actor.instance_id)
    try:
        with pytest.raises(TelemetryError,match='DUPLICATE_INSTANCE_ID'):b.start()
        assert actor.pulse()
    finally:b.close()

def test_telemetry_storage_bounded(lab,actor):
    for _ in range(30):actor.observe(job(lab,actor))
    r=record(lab);assert len(r['current']['progress'])==8 and len(BSON.encode(r))<=MAX_BYTES
    assert lab.db[COLLECTION].count_documents({})==1
    for patch in [{'current.progress':[{}]*9},{'payload':'x'*MAX_BYTES}]:
        with pytest.raises(OperationFailure) as e:actor.collection.update_one({'_id':SLOT},{'$set':patch})
        assert e.value.code==121

def test_telemetry_output_redacts_secrets(lab,actor):
    j=job(lab,actor);actor.observe(j);actor.pulse('ACTIVE',j);data=json.dumps(view(lab,j['library_id']))
    for secret in [lab.password,lab.read_password,lab.telemetry_password,actor.boot_hash,actor.instance_id,actor.owner,j['fence_token']]:assert secret not in data

def test_private_multi_library_telemetry_isolation(lab,actor):
    a=job(lab,actor);b=job(lab,actor,target='KNOWLEDGE_GRAPH');actor.observe(a);actor.observe(b);actor.pulse('ACTIVE',b)
    va,vb=view(lab,a['library_id']),view(lab,b['library_id'])
    assert [p['job_id'] for p in va['progress']]==[a['job_id']]
    assert b['library_id'] not in json.dumps(va) and a['job_id'] not in json.dumps(vb)

def test_operator_cli_bounded_output(lab,actor):
    j=job(lab,actor);actor.observe(j)
    env={**os.environ,'LUMINAR_OPERATOR_MONGO_URI':lab.reader_uri}
    p=subprocess.run([sys.executable,str(ROOT/'scripts/diagnose_institution_v2k_prototype.py'),'--database',lab.database,'--library-id',j['library_id']],env=env,capture_output=True,text=True,timeout=10)
    assert p.returncode==0 and len(p.stdout)<16384 and json.loads(p.stdout)['read_only']

def test_expired_lease_progress_rejected(lab,actor):
    j=job(lab,actor,lease_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1))
    assert actor.observe(j) is False and record(lab)['current']['progress']==[]

def test_agent_failure_isolated_and_shutdown_not_claimed(lab):
    def fail():raise RuntimeError('secret')
    a=Agent(fail,'tenant-'+str(uuid4()),pulse_seconds=.05,poll_seconds=.05)
    a.start();assert a.ready.wait(2);a.close(native_stopped=False)
    assert a.errors['TELEMETRY_UNAVAILABLE']==1 and record(lab)['current'] is None

def test_malformed_and_unexpected_errors_conservative(lab,actor):
    j=job(lab,actor,progress_current=-1)
    with pytest.raises(TelemetryError,match='MALFORMED_NATIVE_PROGRESS'):actor.observe(j)
    for error in [OSError('disk full'),ConnectionError('expired network'),RuntimeError('unexpected')]:
        def fail():raise error
        with pytest.raises(TelemetryError,match='AUXILIARY_UNAVAILABLE'):actor.call('fault',fail)

def test_prototype_rejects_production_namespace(lab):
    with pytest.raises(TelemetryError,match='PROTOTYPE_ONLY'):Actor(lab.telemetry_uri,'luminar_library','tenant-'+str(uuid4()))


def test_actual_server_permission_loss_isolated(lab,actor):
    j=job(lab,actor);before=lab.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})
    roles=[{'role':'fixture_telemetry_writer','db':lab.database}]
    lab.db.command('revokeRolesFromUser','fixture_telemetry',roles=roles)
    try:
        with pytest.raises(TelemetryError,match='PERMISSION_DENIED'):actor.pulse()
        assert lab.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})==before
    finally:lab.db.command('grantRolesToUser','fixture_telemetry',roles=roles)


def test_actual_server_write_timeout_isolated(lab,actor):
    j=job(lab,actor);before=lab.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})
    lab.writer.admin.command('configureFailPoint','failCommand',mode={'times':1},data={
        'failCommands':['update'],'appName':'LuminaR-2K-prototype-telemetry','blockConnection':True,'blockTimeMS':1200})
    try:
        at=time.monotonic()
        with pytest.raises(TelemetryError,match='AUXILIARY_UNAVAILABLE'):actor.pulse()
        assert time.monotonic()-at<1
        assert lab.db.institution_intelligence_jobs.find_one({'job_id':j['job_id']})==before
    finally:lab.writer.admin.command('configureFailPoint','failCommand',mode='off')


def test_actual_network_connection_closed_isolated(lab,actor):
    lab.writer.admin.command('configureFailPoint','failCommand',mode={'times':1},data={
        'failCommands':['update'],'appName':'LuminaR-2K-prototype-telemetry','closeConnection':True})
    try:
        with pytest.raises(TelemetryError,match='AUXILIARY_UNAVAILABLE'):actor.pulse()
    finally:lab.writer.admin.command('configureFailPoint','failCommand',mode='off')


def test_malformed_legacy_telemetry_unknown(lab,actor):
    lab.db[COLLECTION].update_one({'_id':SLOT},{'$set':{'current.instance_id':'malformed','current.last_seen_at':'yesterday'}})
    assert view(lab,str(uuid4()))['worker']['classification']=='UNKNOWN'


def test_cli_read_failure_redacted(lab):
    env={**os.environ,'LUMINAR_OPERATOR_MONGO_URI':lab.reader_uri.replace(lab.read_password,'wrong-secret')}
    p=subprocess.run([sys.executable,str(ROOT/'scripts/diagnose_institution_v2k_prototype.py'),'--database',lab.database,'--library-id',str(uuid4())],env=env,capture_output=True,text=True,timeout=10)
    assert p.returncode==2 and 'wrong-secret' not in p.stderr and lab.reader_uri not in p.stderr


def test_partial_native_shutdown_never_reports_stopped(lab):
    a=Agent(lambda:Actor(lab.telemetry_uri,lab.database,'tenant-'+str(uuid4())),'unused',pulse_seconds=.05,poll_seconds=.05)
    a.start();assert a.ready.wait(2);a.close(native_stopped=False)
    assert record(lab)['current']['lifecycle']!='STOPPED'


def test_retained_previous_and_current_both_at_capacity(lab,actor):
    for _ in range(8):actor.observe(job(lab,actor))
    b=Actor(lab.telemetry_uri,lab.database,actor.owner)
    try:
        b.start()
        for _ in range(12):b.observe(job(lab,b))
        r=record(lab)
        assert len(r['current']['progress'])==len(r['previous']['progress'])==8
        assert len(BSON.encode(r))<=MAX_BYTES
    finally:b.close()
