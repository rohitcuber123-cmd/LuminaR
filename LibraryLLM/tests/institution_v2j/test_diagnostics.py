from datetime import datetime,timedelta,timezone
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
from uuid import uuid4

import pytest
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from backend.services.library_operator_access import connect_operator,DiagnosticError
from backend.services.library_intelligence_diagnostics import inspect,job_view,worker_view

ROOT=Path(__file__).resolve().parents[2]
NOW=datetime.now(timezone.utc)


@pytest.fixture
def reader(auth_server):
    value=connect_operator(auth_server.reader_uri,auth_server.database,seconds=30)
    yield value
    value.close()


def job(server,lib=None,state='QUEUED',target='SEARCH_INDEX',**changes):
    row={'job_id':str(uuid4()),'library_id':lib or str(uuid4()),'target':target,'state':state,'stage':'QUEUED' if state=='QUEUED' else 'EMBEDDING',
         'created_at':NOW-timedelta(seconds=120),'started_at':None if state=='QUEUED' else NOW-timedelta(seconds=60),
         'heartbeat_at':NOW-timedelta(seconds=5),'lease_expires_at':NOW+timedelta(seconds=85),
         'completed_at':NOW if state in ['FAILED','SUCCEEDED'] else None,'effective_active':state in ['QUEUED','RUNNING','VALIDATING','PUBLISHING','RECOVERY_REQUIRED'],
         'progress_current':2,'progress_total':10,'artifact_generation_id':str(uuid4()),'requested_generation_id':str(uuid4()),'attempt':1}
    row.update(changes)
    server.db.institution_intelligence_jobs.insert_one(row)
    return row


def published(server,lib=None,*,temporary=False,state='SUCCEEDED',point=True):
    lib=lib or str(uuid4())
    row=job(server,lib,state,target='KNOWLEDGE_GRAPH')
    gen=row['artifact_generation_id'];source=row['requested_generation_id'];fp='a'*64
    path=server.artifact_root/lib/'kg'/(gen+('.building' if temporary else ''))
    path.mkdir(parents=True)
    (path/'metadata.json').write_text('[]',encoding='utf8')
    (path/'graph.json').write_text('{"nodes":[],"edges":[]}',encoding='utf8')
    manifest={'library_id':lib,'generation_id':gen,'target':'KNOWLEDGE_GRAPH','schema_version':'tenant-catalogue-v1',
              'source_generation_id':source,'source_fingerprint':fp,'book_count':0,'job_id':row['job_id'],
              'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir()}}
    (path/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
    server.db.institution_intelligence_generations.insert_one({'library_id':lib,'generation_id':source,'source_fingerprint':fp,'status':'READY'})
    pointer={'library_id':lib,'target':'KNOWLEDGE_GRAPH','state':'READY' if state=='SUCCEEDED' else state,
             'active_generation_id':gen,'source_generation_id':source,'source_fingerprint':fp,
             'manifest_checksum':hashlib.sha256((path/'manifest.json').read_bytes()).hexdigest(),
             'published_by_job_id':row['job_id'],'record_count':0}
    if point:server.db.institution_intelligence_targets.insert_one(pointer)
    return row,path,pointer


def snapshot(reader,server,lib,**kwargs):
    return inspect(reader,lib,artifact_root=server.artifact_root,now=NOW,**kwargs)


def digest_db(server):
    return {n:hashlib.sha256('\n'.join(sorted(json.dumps(r,sort_keys=True,default=str) for r in server.db[n].find({}))).encode()).hexdigest()
            for n in server.db.list_collection_names() if not n.startswith('system.')}


def files(server):
    return {p.relative_to(server.artifact_root).as_posix():(hashlib.sha256(p.read_bytes()).hexdigest(),p.stat().st_mtime_ns)
            for p in server.artifact_root.rglob('*') if p.is_file()}


def test_operator_diagnostics_authorized(reader,auth_server):
    j=job(auth_server)
    data=snapshot(reader,auth_server,j['library_id'])
    assert data['jobs'][0]['job_id']==j['job_id'] and data['read_only']


@pytest.mark.parametrize('uri',[None,'','application.jwt','mongodb://127.0.0.1:27017/luminar_library','mongodb://name:password@foreign.invalid/luminar_library'])
def test_operator_diagnostics_unauthorized(uri):
    with pytest.raises(DiagnosticError):connect_operator(uri)


def test_wrong_password_denied(auth_server):
    with pytest.raises(DiagnosticError):connect_operator(auth_server.reader_uri.replace(auth_server.read_password,'wrong'),auth_server.database)


def test_platform_only_no_operator_bypass(auth_server):
    auth_server.db.platform_role_assignments.insert_one({'user_id':9,'role':'PLATFORM_ADMIN','status':'ACTIVE'})
    with pytest.raises(DiagnosticError):connect_operator('platform-admin-jwt',auth_server.database)
    # Even the fixture's infrastructure ROOT/write principal is not accepted as
    # the dedicated database-scoped read principal by this diagnostic command.
    with pytest.raises(DiagnosticError):connect_operator(auth_server.writer_uri,auth_server.database)


def test_mongo_reader_server_enforces_no_job_write(auth_server):
    client=MongoClient(auth_server.reader_uri,serverSelectionTimeoutMS=2000)
    try:
        with pytest.raises(OperationFailure) as denied:
            client[auth_server.database].institution_intelligence_jobs.insert_one({'would_be':'unauthorized'})
        assert denied.value.code==13
    finally:client.close()


def test_private_library_diagnostics_denied_to_outsider(auth_server):
    lib=str(uuid4())
    auth_server.db.institution_libraries.insert_one({'library_id':lib,'library_type':'PRIVATE_INSTITUTION','access_mode':'PRIVATE_CODE'})
    j=job(auth_server,lib)
    env=os.environ.copy();env.pop('LUMINAR_OPERATOR_MONGO_URI',None)
    env['LUMINAR_OPERATOR_MONGO_URI']='outsider-application-jwt'
    run=subprocess.run([sys.executable,str(ROOT/'scripts/diagnose_library_intelligence.py'),'--library-id',lib,
                        '--database',auth_server.database,'--format','json'],env=env,cwd=ROOT,capture_output=True,text=True,timeout=10)
    assert run.returncode!=0 and j['job_id'] not in run.stdout+run.stderr


def test_worker_liveness_recent_heartbeat(auth_server):
    j=job(auth_server,state='RUNNING')
    w=worker_view([j],NOW)
    assert w['classification']=='UNKNOWN' and w['process_alive']=='UNKNOWN'
    assert w['current_executing_observations'][0]['heartbeat_evidence']=='RECENT'


def test_worker_liveness_stale_heartbeat(auth_server):
    j=job(auth_server,state='RUNNING',heartbeat_at=NOW-timedelta(seconds=45))
    assert worker_view([j],NOW)['classification']=='STALE_HEARTBEAT'


def test_worker_liveness_unknown():
    assert worker_view([],NOW)['classification']=='UNKNOWN'


def test_clock_skew_is_not_healthy(auth_server):
    j=job(auth_server,state='RUNNING',heartbeat_at=NOW+timedelta(minutes=1))
    assert worker_view([j],NOW)['classification']=='UNKNOWN'
    assert job_view(j,NOW)['heartbeat_evidence']=='CLOCK_SKEW'


@pytest.mark.parametrize('state',['QUEUED','RUNNING','FAILED','RECOVERY_REQUIRED'])
def test_job_state_diagnostic(reader,auth_server,state):
    j=job(auth_server,state=state)
    data=snapshot(reader,auth_server,j['library_id'])
    assert data['jobs'][0]['state']==state
    assert data['jobs'][0]['recovery_required']==(state=='RECOVERY_REQUIRED')


def test_expired_lease_requires_investigation_without_mutation(reader,auth_server):
    j=job(auth_server,state='RUNNING',lease_expires_at=NOW-timedelta(seconds=1))
    before=digest_db(auth_server)
    result=snapshot(reader,auth_server,j['library_id'])
    assert result['jobs'][0]['recovery_required'] and result['jobs'][0]['state']=='RUNNING'
    assert before==digest_db(auth_server)


def test_queue_depth_bounded(reader,auth_server):
    rows=[job(auth_server,created_at=NOW-timedelta(seconds=200-i)) for i in range(30)]
    data=snapshot(reader,auth_server,rows[0]['library_id'],limit=2)
    assert data['queue']['queued_total']==30
    assert len(data['queue']['oldest_observed_jobs'])==3 and len(data['jobs'])<=2


def test_oldest_queued_age(reader,auth_server):
    j=job(auth_server)
    assert snapshot(reader,auth_server,j['library_id'])['queue']['oldest_queued_age_seconds']==pytest.approx(120,abs=.001)


def test_queue_ties_are_ranges(reader,auth_server):
    first,second=job(auth_server),job(auth_server)
    data=snapshot(reader,auth_server,second['library_id'],job_id=second['job_id'])
    p=data['queue']['selected_job_position_range']
    assert p['minimum']==1 and p['maximum']==2


def test_head_of_line_barrier_observed(reader,auth_server):
    j=job(auth_server)
    auth_server.db.institution_locks.insert_one({'_id':j['library_id'],'holder':'NEVER_PRINT','created_at':NOW})
    data=snapshot(reader,auth_server,j['library_id'])
    assert data['queue']['head_of_line']=='POTENTIAL_TENANT_BARRIER_BLOCK'
    assert 'NEVER_PRINT' not in json.dumps(data)


def test_no_invented_eta(reader,auth_server):
    j=job(auth_server)
    data=snapshot(reader,auth_server,j['library_id'])
    assert data['queue']['eta']=='NOT_AVAILABLE'
    assert 'percentage' not in json.dumps(data)


def test_heartbeat_not_equal_progress(auth_server):
    j=job(auth_server,state='RUNNING')
    assert job_view(j,NOW)['progress']['recency']=='UNKNOWN'
    assert job_view(j,NOW)['last_updated_at']=='NOT_AVAILABLE'


def test_last_good_generation_visibility(reader,auth_server):
    row,path,p=published(auth_server)
    old=row['artifact_generation_id']
    job(auth_server,row['library_id'],state='FAILED',error_code='BUILD_FAILED')
    data=snapshot(reader,auth_server,row['library_id'],verify_checksums=True)
    t=next(t for t in data['targets'] if t['target']=='KNOWLEDGE_GRAPH')
    assert t['published_generation_id']==old and t['published_checksum_integrity']=='VERIFIED_WITHIN_BUDGET'
    assert t['runtime_usable'].startswith('NOT_DETERMINED')


def test_unknown_publication_outcome(reader,auth_server):
    row,path,p=published(auth_server,state='RECOVERY_REQUIRED')
    data=snapshot(reader,auth_server,row['library_id'],verify_checksums=True)
    assert data['jobs'][0]['publication_outcome']=='UNKNOWN'
    assert data['targets'][1]['manual_investigation_required']


def test_artifact_manifest_validation(reader,auth_server):
    row,path,p=published(auth_server)
    data=snapshot(reader,auth_server,row['library_id'])
    artifact=data['artifacts']['generations'][0]
    assert artifact['manifest']=='POINTER_ANCHORED_MANIFEST' and artifact['checksums']=='NOT_REQUESTED'
    assert data['artifacts']['checksum_bytes_read']==0


@pytest.mark.parametrize('fault',['missing','invalid','mismatch','foreign','pointer'])
def test_artifact_invalid_conditions(reader,auth_server,fault):
    row,path,p=published(auth_server)
    if fault=='missing':(path/'manifest.json').unlink()
    elif fault=='invalid':(path/'manifest.json').write_text('not JSON')
    elif fault=='mismatch':(path/'metadata.json').write_text('[1]')
    elif fault=='foreign':
        m=json.loads((path/'manifest.json').read_text());m['library_id']=str(uuid4());(path/'manifest.json').write_text(json.dumps(m))
    else:auth_server.db.institution_intelligence_targets.update_one({'library_id':row['library_id']},{'$set':{'source_generation_id':str(uuid4())}})
    data=snapshot(reader,auth_server,row['library_id'],verify_checksums=True)
    artifact=data['artifacts']['generations'][0]
    assert artifact['manifest'] not in ['POINTER_ANCHORED_MANIFEST','IDENTITY_VALID_MANIFEST'] or artifact['checksums']=='MISMATCH'
    assert data['targets'][1]['published_checksum_integrity']=='NOT_VERIFIED'


def test_artifact_tenant_isolation(reader,auth_server):
    a,path,p=published(auth_server)
    b=str(uuid4())
    auth_server.db.institution_intelligence_targets.insert_one({**{k:v for k,v in p.items() if k!='_id'},'library_id':b})
    data=snapshot(reader,auth_server,b,verify_checksums=True)
    assert not data['jobs']
    assert data['artifacts']['generations'][0]['manifest']=='MISSING_GENERATION'
    with pytest.raises(DiagnosticError):snapshot(reader,auth_server,b,job_id=a['job_id'])


def test_failed_artifact_inventory(reader,auth_server):
    row,path,p=published(auth_server,state='FAILED',point=False,temporary=True)
    data=snapshot(reader,auth_server,row['library_id'])
    assert any(a['reconciliation']=='FAILED_RETAINED' and a['directory_present'] for a in data['artifacts']['generations'])


def test_missing_temporary_artifact_reference_is_visible(reader,auth_server):
    row=job(auth_server,state='FAILED')
    result=snapshot(reader,auth_server,row['library_id'])
    assert any(a['generation_id']==row['artifact_generation_id'] and a['temporary'] and not a['directory_present'] for a in result['artifacts']['generations'])
    assert result['artifacts']['observed_generation_count']==0


def test_worker_restart_cannot_be_inferred_from_job_presence(auth_server):
    j=job(auth_server,state='RUNNING')
    assert worker_view([j],NOW)['restart']=='NOT_AVAILABLE'


def test_worker_identity_reference_is_not_process_liveness(auth_server):
    owner='tenant-'+str(uuid4())
    j=job(auth_server,state='RUNNING',worker_id=owner)
    data=job_view(j,NOW)
    assert data['worker_reference'].startswith('worker-')
    assert owner not in json.dumps(data)
    assert worker_view([j],NOW)['process_alive']=='UNKNOWN'


def test_progress_counter_does_not_prove_publication(auth_server):
    row=job(auth_server,state='RUNNING',progress_current=10,progress_total=10)
    assert job_view(row,NOW)['publication_outcome']=='NOT_TERMINAL'


def test_explicit_reader_does_not_accept_write_role(auth_server):
    from urllib.parse import quote
    auth_server.db.command('createUser','not_an_operator',pwd='isolated-not-a-production-secret',roles=[{'role':'readWrite','db':auth_server.database}])
    uri=f'mongodb://not_an_operator:{quote("isolated-not-a-production-secret")}@127.0.0.1:{auth_server.port}/{auth_server.database}'
    with pytest.raises(DiagnosticError):connect_operator(uri,auth_server.database)


def test_deadline_failure_is_bounded(reader,auth_server):
    reader.deadline=time.monotonic()-1
    with pytest.raises(DiagnosticError,match='DIAGNOSTIC_DEADLINE'):
        snapshot(reader,auth_server,str(uuid4()))


def test_large_manifest_is_not_loaded(reader,auth_server):
    row,path,p=published(auth_server)
    (path/'manifest.json').write_bytes(b' '*65537)
    data=snapshot(reader,auth_server,row['library_id'])
    assert data['artifacts']['generations'][0]['manifest']=='ARTIFACT_LIMIT'


def test_pointer_change_during_inspection_not_blessed(reader,auth_server,monkeypatch):
    row,path,p=published(auth_server)
    original=reader.rows
    calls=0
    def concurrent(name,*args,**kwargs):
        nonlocal calls
        if name=='targets':
            calls+=1
            if calls==2:
                auth_server.db.institution_intelligence_targets.update_one({'library_id':row['library_id']},{'$set':{'active_generation_id':str(uuid4())}})
        return original(name,*args,**kwargs)
    monkeypatch.setattr(reader,'rows',concurrent)
    data=snapshot(reader,auth_server,row['library_id'],verify_checksums=True)
    assert data['consistency'].startswith('CONCURRENT_POINTER_CHANGE')
    assert data['targets'][1]['published_checksum_integrity']=='NOT_VERIFIED'


def test_manifest_cannot_select_arbitrary_files(reader,auth_server):
    row,path,p=published(auth_server)
    m=json.loads((path/'manifest.json').read_text())
    m['files']['../credentials']='f'*64
    (path/'manifest.json').write_text(json.dumps(m))
    data=snapshot(reader,auth_server,row['library_id'],verify_checksums=True)
    assert data['artifacts']['generations'][0]['manifest']=='INVALID_OR_UNREADABLE_MANIFEST'


def test_old_jobs_with_missing_timestamps_remain_readable(reader,auth_server):
    row=job(auth_server,state='FAILED')
    auth_server.db.institution_intelligence_jobs.update_one({'job_id':row['job_id']},{'$unset':{'heartbeat_at':'','started_at':'','lease_expires_at':''}})
    data=snapshot(reader,auth_server,row['library_id'])
    assert data['jobs'][0]['heartbeat_evidence']=='NOT_AVAILABLE'
    assert data['jobs'][0]['duration_seconds'] is None


def test_file_growth_never_overreads_shared_checksum_budget(reader,auth_server,monkeypatch):
    from backend.services.library_intelligence_diagnostics import ArtifactInspector
    row,path,p=published(auth_server)
    inspector=ArtifactInspector(auth_server.artifact_root,reader,verify=True,byte_budget=2)
    original=reader.remaining
    calls=0
    def mutation():
        nonlocal calls
        calls+=1
        if calls==2:
            with (path/'metadata.json').open('ab') as stream:stream.write(b'grown')
        return original()
    monkeypatch.setattr(reader,'remaining',mutation)
    with pytest.raises(DiagnosticError,match='ARTIFACT_CHANGED_DURING_READ'):
        inspector.content(path/'metadata.json',256*1024*1024,hashing=True)
    assert inspector.hashed_bytes==2


def test_no_artifact_deletion_or_job_state_mutation(reader,auth_server):
    row,path,p=published(auth_server,state='RECOVERY_REQUIRED')
    before,previous=digest_db(auth_server),files(auth_server)
    data=snapshot(reader,auth_server,row['library_id'],verify_checksums=True)
    assert data['actions_available']==[] and before==digest_db(auth_server) and previous==files(auth_server)


def test_checksum_budget_does_not_claim_verified(reader,auth_server):
    row,path,p=published(auth_server)
    data=snapshot(reader,auth_server,row['library_id'],verify_checksums=True,checksum_budget=0)
    assert data['artifacts']['generations'][0]['checksums']=='CHECKSUM_BUDGET_EXCEEDED'
    assert data['targets'][1]['published_checksum_integrity']=='NOT_VERIFIED'


def test_diagnostics_redact_secrets(reader,auth_server):
    j=job(auth_server,state='FAILED',stage='C:/private/secret',error_code='Traceback PASSWORD',
          error_message='credentials',fence_token='FENCE_SECRET',worker_id='WORKER_SECRET')
    out=json.dumps(snapshot(reader,auth_server,j['library_id']))
    assert all(s not in out for s in ['C:/private','Traceback','PASSWORD','credentials','FENCE_SECRET','WORKER_SECRET'])


def test_diagnostics_bounded_pagination(reader,auth_server):
    lib=str(uuid4())
    rows=[job(auth_server,lib,state='FAILED') for _ in range(7)]
    first=snapshot(reader,auth_server,lib,limit=3)
    second=snapshot(reader,auth_server,lib,limit=3,cursor=first['pagination']['next_cursor'])
    assert len(first['jobs'])==len(second['jobs'])==3
    assert not {j['job_id'] for j in first['jobs']}&{j['job_id'] for j in second['jobs']}
    with pytest.raises(DiagnosticError):snapshot(reader,auth_server,str(uuid4()),cursor=first['pagination']['next_cursor'])


def test_diagnostics_no_catalogue_full_scan(reader,auth_server):
    j=job(auth_server)
    snapshot(reader,auth_server,j['library_id'])
    assert all(o['collection'] in ['jobs','targets','generations','locks'] for o in reader.operations)
    assert len(reader.operations)<=12


def test_no_automatic_rebuild_recovery_cancellation_or_global_controls(reader,auth_server):
    lib=str(uuid4())
    before=digest_db(auth_server)
    result=snapshot(reader,auth_server,lib)
    assert result['actions_available']==[] and before==digest_db(auth_server)
    source=(ROOT/'backend/routes/library_intelligence.py').read_text()
    assert 'diagnostic' not in source and '/cancel' not in source


def test_existing_staff_status_unchanged():
    baseline=json.loads((ROOT/'reports/institution_v2j_baseline.json').read_text())
    for file in ['backend/services/library_intelligence_service.py','backend/services/library_intelligence_store.py',
                 'backend/routes/library_intelligence.py']:
        assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==baseline['source_sha256'][file]
    # Proposed O.3 audited JSX boundary; separate user approval required.
    assert hashlib.sha256((ROOT/'tests/contracts/staff_boundary_v2o3.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest()=='38ce3cc8357dd22b32b55a49c46ef1f615444d9732c314014d1e5dadfb4b5cc7'
    assert hashlib.sha256((ROOT/'tests/contracts/staff_boundary_v2o3.cjs').read_bytes().replace(b'\r\n',b'\n')).hexdigest()=='29fd9343e7808583e2f900cb5dabfe9486c2fb6af7dc9d7f4dc91bd81dbebf28'
    assert hashlib.sha256((ROOT/'tests/contracts/staff_boundary_v2o3.json').read_bytes().replace(b'\r\n',b'\n')).hexdigest()=='45b249cb83389f1b659d5848c126b96f888b637a62c1e124998e46540059baf3'
    from tests.contracts.staff_boundary_v2o3 import assert_staff_contract
    assert_staff_contract(ROOT)
    # Part2L explicitly integrates the native worker. Its original job protocol
    # is pinned/compared by test_native_protocol_matches_original_j_baseline;
    # whole-file identity would also forbid the authorized observer lifecycle.


def test_real_cli_text_json_and_read_only(auth_server):
    row,path,p=published(auth_server)
    before,artifacts=digest_db(auth_server),files(auth_server)
    env=os.environ.copy();env['LUMINAR_OPERATOR_MONGO_URI']=auth_server.reader_uri
    command=[sys.executable,str(ROOT/'scripts/diagnose_library_intelligence.py'),'--library-id',row['library_id'],
             '--database',auth_server.database,'--artifact-root',str(auth_server.artifact_root)]
    for mode in ['json','text']:
        run=subprocess.run([*command,'--format',mode],env=env,cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=15)
        assert run.returncode==0,run.stderr
        assert auth_server.read_password not in run.stdout+run.stderr
        if mode=='json':assert json.loads(run.stdout)['read_only']
        else:assert 'Process liveness: UNKNOWN' in run.stdout
    assert before==digest_db(auth_server) and artifacts==files(auth_server)
