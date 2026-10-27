"""Tamper, eviction and recovery checks against isolated canonical fixtures."""
import json
from datetime import timedelta
from pathlib import Path
import pytest
from fastapi import HTTPException
from backend.services import library_intelligence_store as store,library_intelligence_service as service,library_intelligence_artifacts as artifacts
from search.library_intelligence import TenantIntelligence
from test_intelligence import book,build,encoder

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_missing_artifact_detected(client,library,target):
    lib=library();book(client,lib);job,_=build(lib,target)
    (store.directory(lib,'search' if target=='SEARCH_INDEX' else 'kg',job['artifact_generation_id'])/'metadata.json').unlink()
    assert service.target_status(lib,target)['status']=='RECOVERY_REQUIRED'

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_broken_publish_detected(client,library,target):
    lib=library();book(client,lib);build(lib,target)
    store.collection('intelligence_targets').update_one({'library_id':lib,'target':target},{'$unset':{'active_generation_id':''}})
    assert any(p['code']=='PUBLISH_POINTER_MISSING' for p in service.reconcile(lib,{'sub':'1'})['problems'])

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_foreign_library_manifest_detected(client,library,target):
    lib=library();other=library();book(client,lib);job,_=build(lib,target)
    path=store.directory(lib,'search' if target=='SEARCH_INDEX' else 'kg',job['artifact_generation_id'])/'manifest.json'
    manifest=json.loads(path.read_text());manifest['library_id']=other;path.write_text(json.dumps(manifest))
    with pytest.raises(HTTPException):artifacts.validate(lib,target,job['artifact_generation_id'])

def test_source_fingerprint_mismatch_and_stale_timestamp(client,library):
    lib=library();book(client,lib);build(lib)
    store.collection('library_books').update_one({'library_id':lib},{'$set':{'description':'Different source'}})
    first=service.target_status(lib,'SEARCH_INDEX');second=service.target_status(lib,'SEARCH_INDEX')
    assert first['status']=='STALE' and first['stale_since']==second['stale_since'] and first['stale_since']>first['built_at']
    assert any(p['code']=='SOURCE_FINGERPRINT_CHANGED' for p in service.reconcile(lib,{'sub':'1'})['problems'])

def test_reconciliation_dry_run_never_writes(client,library):
    lib=library();book(client,lib);build(lib)
    store.collection('library_books').update_one({'library_id':lib},{'$set':{'description':'Stale source'}})
    before=list(store.collection('intelligence_targets').find())
    assert service.reconcile(lib,{'sub':'1'})['dry_run']
    assert list(store.collection('intelligence_targets').find())==before

def test_orphan_generation_detected(client,library):
    lib=library();path=store.root()/lib/'search'/'11111111-1111-4111-8111-111111111111';path.mkdir(parents=True)
    assert any(p['code']=='ORPHAN_FINAL_GENERATION' for p in service.reconcile(lib,{'sub':'1'})['problems'])

@pytest.mark.parametrize('kind',['search','kg'])
def test_temporary_generation_detected(client,library,kind):
    lib=library();path=store.root()/lib/kind/'11111111-1111-4111-8111-111111111111.building';path.mkdir(parents=True)
    assert any(p['code']=='TEMPORARY_GENERATION' for p in service.reconcile(lib,{'sub':'1'})['problems'])

def test_dataset_artifact_corruption_detected(client,library):
    lib=library();book(client,lib);job,_=build(lib)
    (store.directory(lib,'datasets',job['requested_generation_id'])/'records.json').write_bytes(b'changed')
    with pytest.raises(HTTPException):artifacts.validate(lib,'SEARCH_INDEX',job['artifact_generation_id'])

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_cache_lazy_load_namespace_and_generation_keys(client,library,target):
    lib=library();book(client,lib);cache=artifacts.ArtifactCache();assert cache.metrics()['entries']==0
    first,_=build(lib,target);pointer=service.target_status(lib,target)
    cache.load(lib,target,first['artifact_generation_id'],pointer['manifest_checksum'])
    cache.load(lib,target,first['artifact_generation_id'],pointer['manifest_checksum']);assert cache.metrics()['loads']==1
    second,_=build(lib,target);pointer=service.target_status(lib,target);cache.load(lib,target,second['artifact_generation_id'],pointer['manifest_checksum'])
    assert (lib,first['artifact_generation_id'],target) in cache.entries
    assert (lib,second['artifact_generation_id'],target) in cache.entries

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_old_generation_eviction(client,library,target):
    lib=library();book(client,lib);cache=artifacts.ArtifactCache(max_entries=1);old,_=build(lib,target);pointer=service.target_status(lib,target)
    cache.load(lib,target,old['artifact_generation_id'],pointer['manifest_checksum'])
    new,_=build(lib,target);pointer=service.target_status(lib,target);cache.load(lib,target,new['artifact_generation_id'],pointer['manifest_checksum'])
    assert (lib,old['artifact_generation_id'],target) not in cache.entries and cache.metrics()['evictions']==1

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_heartbeat_loss_requires_recovery(client,library,target):
    lib=library();book(client,lib)
    def fail(stage):
        if stage=='HEARTBEAT':raise HTTPException(409,'HEARTBEAT_LOSS')
    job=store.request_build(lib,{'sub':'1'},target);TenantIntelligence(encoder,fail=fail).run_one()
    assert store.scoped_job(lib,job['job_id'],{'sub':'1'})['state']=='RECOVERY_REQUIRED'
    assert service.recover(lib,{'sub':'1'},job['job_id'])['state']=='FAILED'

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_cache_memory_limit(client,library,target):
    lib=library();book(client,lib);job,_=build(lib,target);pointer=service.target_status(lib,target)
    cache=artifacts.ArtifactCache(max_bytes=1)
    with pytest.raises(HTTPException):cache.load(lib,target,job['artifact_generation_id'],pointer['manifest_checksum'])
    assert cache.metrics()['entries']==0

def test_cache_detects_corruption_after_load(client,library):
    lib=library();book(client,lib);job,_=build(lib);pointer=service.target_status(lib,'SEARCH_INDEX');cache=artifacts.ArtifactCache()
    cache.load(lib,'SEARCH_INDEX',job['artifact_generation_id'],pointer['manifest_checksum'])
    (store.directory(lib,'search',job['artifact_generation_id'])/'index.faiss').write_bytes(b'bad')
    with pytest.raises(HTTPException):cache.load(lib,'SEARCH_INDEX',job['artifact_generation_id'],pointer['manifest_checksum'])
    assert cache.metrics()['entries']==0

def test_same_global_work_keeps_distinct_local_ids(client,library):
    a,b=library(),library();one=book(client,a,linked=True);two=book(client,b,linked=True)
    _,worker=build(a);build(b,worker=worker)
    assert one['global_work_id']==two['global_work_id'] and one['library_book_id']!=two['library_book_id']
    for lib,row in [(a,one),(b,two),(a,one)]:
        assert {r['library_book_id'] for r in worker.semantic(lib,{'sub':'1'},'networks',staff=True)['results']}=={row['library_book_id']}

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_worker_crash_marks_recovery_required(client,library,target):
    lib=library();book(client,lib)
    def fail(stage):
        if stage=='PUBLISH':raise RuntimeError('isolated crash')
    job=store.request_build(lib,{'sub':'1'},target);TenantIntelligence(encoder,fail=fail).run_one()
    assert store.scoped_job(lib,job['job_id'],{'sub':'1'})['state']=='RECOVERY_REQUIRED'
    assert service.recover(lib,{'sub':'1'},job['job_id'])['state']=='FAILED'

def test_expired_worker_not_automatically_restarted(client,library):
    lib=library();job=store.request_build(lib,{'sub':'1'},'SEARCH_INDEX');claimed=store.claim('old')
    store.collection('intelligence_jobs').update_one({'job_id':job['job_id']},{'$set':{'lease_expires_at':store.now()-timedelta(seconds=1)}})
    assert service.target_status(lib,'SEARCH_INDEX')['status']=='RECOVERY_REQUIRED'
    assert store.claim('new') is None
    with pytest.raises(HTTPException):store.progress(claimed,'PUBLISH')

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_online_only_includes_graph_and_index_metadata(client,library,upload,ready,target):
    lib=library();row=book(client,lib,physical=False);asset=upload(lib,book_id=row['library_book_id']).json();ready(asset)
    job,_=build(lib,target);manifest,records,payload=artifacts.validate(lib,target,job['artifact_generation_id'])
    assert records[0]['library_book_id']==row['library_book_id'] and manifest['book_count']==1
    assert 'violet lantern' not in json.dumps(records)

def test_platform_only_build_denied_with_valid_explicit_grant(client,library,database):
    from backend.platform_dependencies import platform_assignments
    lib=library();database.platform_role_assignments.insert_one({'user_id':10,'role':'PLATFORM_ADMIN','status':'ACTIVE','approved_at':store.now(),'approved_by':'isolated-review','approval_ref':'PART2G-TEST'})
    assert platform_assignments(10)
    assert client.post(f'/libraries/{lib}/intelligence/builds',headers={'x-test-user':'10'},json={'target':'SEARCH_INDEX'}).status_code==404

@pytest.mark.parametrize('forbidden',['knowledge_graph/data','search','rag/private_documents','indexes'])
def test_global_artifact_root_rejected(monkeypatch,forbidden):
    monkeypatch.setenv('LIBRARY_INTELLIGENCE_ROOT',str(Path(__file__).resolve().parents[2]/forbidden))
    with pytest.raises(HTTPException):store.root()
