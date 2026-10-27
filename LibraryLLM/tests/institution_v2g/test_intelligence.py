import hashlib,json
from datetime import timedelta
from uuid import UUID,uuid4
import numpy as np
import pytest
from fastapi import HTTPException
from backend.services import library_intelligence_store as store,library_intelligence_service as service,library_intelligence_artifacts as artifacts
from search.library_intelligence import TenantIntelligence

def encoder(texts):
    output=np.zeros((len(texts),384),dtype=np.float32)
    for i,text in enumerate(texts):
        for term in text.casefold().split():output[i,int(hashlib.sha256(term.encode()).hexdigest()[:8],16)%384]+=1
    return output/np.linalg.norm(output,axis=1,keepdims=True)
def book(client,library_id,title='Local computer networks',linked=False,physical=True):
    payload={'title':title,'subjects':['Computer networks','Technology'],'authors':['Ada Reader'],'description':'Beginner networking guide','create_physical_holding':physical,'copies':2 if physical else 0,'idempotency_key':str(uuid4())}
    if physical:payload.update(shelf_location='QA-1')
    if linked:payload['global_work_id']='OL1W'
    response=client.post(f'/libraries/{library_id}/inventory/books',json=payload)
    assert response.status_code==201,response.text
    return response.json()
def build(library_id,target='SEARCH_INDEX',worker=None):
    job=store.request_build(library_id,{'sub':'1'},target)
    worker=worker or TenantIntelligence(encoder,model_version='all-MiniLM-L6-v2:unit')
    assert worker.run_one()
    done=store.collection('intelligence_jobs').find_one({'job_id':job['job_id']})
    assert done['state']=='SUCCEEDED',done.get('error_code')
    return done,worker

def test_library_dataset_generation_uuid(client,library):
    lib=library();book(client,lib);job,_=build(lib)
    row=store.scoped_generation(lib,job['requested_generation_id'],{'sub':'1'})
    assert str(UUID(row['generation_id']))==row['generation_id'] and row['status']=='READY'
    assert row['book_count']==1
def test_dataset_generation_scope_and_no_foreign_books(client,library):
    a,b=library(),library(name='Other');one=book(client,a);book(client,b,'Foreign title')
    job,_=build(a);rows=json.loads((store.directory(a,'datasets',job['requested_generation_id'])/'records.json').read_text())
    assert [r['library_book_id'] for r in rows]==[one['library_book_id']]
    assert all(r['library_id']==a for r in rows)
def test_dataset_active_books_only(client,library):
    lib=library();active=book(client,lib);inactive=book(client,lib,'Withdrawn book')
    store.collection('library_books').update_one({'library_book_id':inactive['library_book_id']},{'$set':{'status':'WITHDRAWN'}})
    assert [r['library_book_id'] for r in store.source_records(lib)]==[active['library_book_id']]
@pytest.mark.parametrize('linked',[False,True],ids=['local_only','globally_linked'])
def test_dataset_identity_without_global_requirement(client,library,linked):
    lib=library();row=book(client,lib,linked=linked)
    source=store.source_records(lib)[0]
    assert source['library_book_id']==row['library_book_id'] and bool(source['global_work_id'])==linked
def test_dataset_online_only_no_document_chunks(client,library,upload,ready):
    lib=library();row=book(client,lib,physical=False);asset=upload(lib,book_id=row['library_book_id']).json();ready(asset)
    job,_=build(lib);generation=store.scoped_generation(lib,job['requested_generation_id'],{'sub':'1'})
    assert generation['online_count']==1 and generation['physical_count']==0
    assert 'violet lantern' not in artifacts.embedding_text(store.source_records(lib)[0])
def test_dataset_deterministic_fingerprint(client,library):
    lib=library();book(client,lib);first=store.fingerprint(store.source_records(lib))
    assert store.fingerprint(store.source_records(lib))==first
def test_loan_change_does_not_stale_dataset(client,library):
    lib=library();row=book(client,lib);build(lib);fp=store.fingerprint(store.source_records(lib))
    store.collection('loans').insert_one({'library_id':lib,'library_book_id':row['library_book_id'],'status':'ACTIVE','user_id':2})
    store.collection('holdings').update_one({'library_id':lib,'library_book_id':row['library_book_id']},{'$set':{'available_copies':0}})
    assert store.fingerprint(store.source_records(lib))==fp and service.target_status(lib,'SEARCH_INDEX')['status']=='READY'
def test_metadata_change_stales_dataset(client,library):
    lib=library();row=book(client,lib);build(lib)
    store.collection('library_books').update_one({'library_book_id':row['library_book_id']},{'$set':{'description':'changed knowledge'}})
    assert service.target_status(lib,'SEARCH_INDEX')['status']=='STALE'
@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_durable_target_job_and_single_active(client,library,target):
    lib=library();book(client,lib);a=store.request_build(lib,{'sub':'1'},target);b=store.request_build(lib,{'sub':'1'},target)
    assert a['job_id']==b['job_id'] and a['state']=='QUEUED'
    assert a['state']=='QUEUED' and 'fence_token' not in a
def test_search_and_kg_independent_jobs(library):
    lib=library();search=store.request_build(lib,{'sub':'1'},'SEARCH_INDEX');kg=store.request_build(lib,{'sub':'1'},'KNOWLEDGE_GRAPH')
    assert search['job_id']!=kg['job_id']
def test_job_fencing(client,library):
    lib=library();book(client,lib);store.request_build(lib,{'sub':'1'},'SEARCH_INDEX');job=store.claim('one')
    store.collection('intelligence_jobs').update_one({'job_id':job['job_id']},{'$set':{'fence_token':str(uuid4())}})
    with pytest.raises(HTTPException):store.progress(job,'PUBLISH')
def test_stale_worker_cannot_publish_after_recovery(client,library):
    lib=library();book(client,lib);job=store.request_build(lib,{'sub':'1'},'SEARCH_INDEX');claimed=store.claim('one')
    store.collection('intelligence_jobs').update_one({'job_id':job['job_id']},{'$set':{'lease_expires_at':store.now()-timedelta(seconds=1)}})
    service.recover(lib,{'sub':'1'},job['job_id'])
    with pytest.raises(HTTPException):store.check_lease(claimed)
    assert service.target_status(lib,'SEARCH_INDEX')['active_generation_id'] is None

def test_crashed_worker_tagged_barrier_explicit_fenced_recovery(client,library):
    lib=library();book(client,lib);request=store.request_build(lib,{'sub':'1'},'SEARCH_INDEX');job=store.claim('crashed')
    store.collection('intelligence_jobs').update_one({'job_id':job['job_id']},{'$set':{'lease_expires_at':store.now()-timedelta(seconds=1)}})
    store.collection('locks').insert_one({'_id':lib,'holder':'crashed-holder','intelligence_job_id':job['job_id']})
    assert service.recover(lib,{'sub':'1'},request['job_id'])['state']=='FAILED'
    assert not store.collection('locks').find_one({'_id':lib})
    with pytest.raises(HTTPException):store.check_lease(job)
def test_recovery_never_removes_unrelated_tenant_barrier(client,library):
    lib=library();request=store.request_build(lib,{'sub':'1'},'SEARCH_INDEX')
    store.collection('locks').insert_one({'_id':lib,'holder':'domain-mutation'})
    with pytest.raises(HTTPException):service.recover(lib,{'sub':'1'},request['job_id'])
    assert store.collection('locks').find_one({'_id':lib})['holder']=='domain-mutation'
@pytest.mark.parametrize('stage',['DATASET_SNAPSHOT','EMBEDDING_CACHE','EMBEDDING_BATCH','FAISS_BUILD','FAISS_SERIALIZATION','CHECKSUM','MANIFEST_WRITE','VALIDATION','SERIALIZATION_ACK','PUBLISH'])
def test_search_failure_preserves_last_good(client,library,stage):
    lib=library();book(client,lib);first,_=build(lib);old=service.target_status(lib,'SEARCH_INDEX')['active_generation_id']
    # New metadata defeats the embedding cache for a meaningful interrupted rebuild.
    store.collection('library_books').update_one({'library_id':lib},{'$set':{'description':'New revision '+stage}})
    def fail(value):
        if value==stage:raise HTTPException(409,'INJECTED_FAILURE')
    worker=TenantIntelligence(encoder,model_version='all-MiniLM-L6-v2:unit',fail=fail)
    job=store.request_build(lib,{'sub':'1'},'SEARCH_INDEX');worker.run_one()
    assert store.collection('intelligence_jobs').find_one({'job_id':job['job_id']})['state']=='FAILED'
    assert service.target_status(lib,'SEARCH_INDEX')['active_generation_id']==old
    artifacts.validate(lib,'SEARCH_INDEX',old)
@pytest.mark.parametrize('stage',['KG_NODES','KG_EDGES','KG_SERIALIZATION','PUBLISH'])
def test_kg_failure_preserves_last_good(client,library,stage):
    lib=library();book(client,lib);first,_=build(lib,'KNOWLEDGE_GRAPH');old=first['artifact_generation_id']
    def fail(value):
        if value==stage:raise HTTPException(409,'INJECTED_FAILURE')
    store.request_build(lib,{'sub':'1'},'KNOWLEDGE_GRAPH');TenantIntelligence(encoder,fail=fail).run_one()
    assert service.target_status(lib,'KNOWLEDGE_GRAPH')['active_generation_id']==old
    artifacts.validate(lib,'KNOWLEDGE_GRAPH',old)
def test_acknowledgement_loss_requires_recovery(client,library):
    lib=library();book(client,lib)
    def fail(stage):
        if stage=='ACKNOWLEDGEMENT_LOSS':raise RuntimeError('isolated acknowledgement loss')
    job=store.request_build(lib,{'sub':'1'},'SEARCH_INDEX');TenantIntelligence(encoder,fail=fail).run_one()
    assert store.scoped_job(lib,job['job_id'],{'sub':'1'})['state']=='RECOVERY_REQUIRED'
    assert store.request_build(lib,{'sub':'1'},'SEARCH_INDEX')['job_id']==job['job_id']
    assert service.recover(lib,{'sub':'1'},job['job_id'])['state']=='SUCCEEDED'
@pytest.mark.parametrize('user',[2,3,9,10])
def test_only_admin_membership_can_build(client,library,database,user):
    lib=library()
    if user in [2,3]:database.institution_memberships.insert_one({'library_id':lib,'user_id':user,'membership_id':str(uuid4()),'role':'LIBRARIAN' if user==3 else 'GENERAL_USER','status':'ACTIVE'})
    if user==10:database.platform_role_assignments.insert_one({'user_id':10,'role':'PLATFORM_ADMIN','status':'ACTIVE'})
    response=client.post(f'/libraries/{lib}/intelligence/builds',headers={'x-test-user':str(user)},json={'target':'SEARCH_INDEX'})
    assert response.status_code in [403,404]
def test_hnsw_manifest_dimension_normalization_identity(client,library):
    lib=library();row=book(client,lib);job,_=build(lib)
    manifest,metadata,index=artifacts.validate(lib,'SEARCH_INDEX',job['artifact_generation_id'])
    assert manifest['model']==store.MODEL and index.d==384 and index.ntotal==1
    assert manifest['parameters']==artifacts.PARAMETERS and metadata[0]['library_book_id']==row['library_book_id']
def test_ready_query_uses_tenant_index(client,library):
    lib=library();row=book(client,lib);job,worker=build(lib)
    page=worker.semantic(lib,{'sub':'1'},'networks',staff=True)
    assert page['source']['search_source']=='TENANT_SEMANTIC'
    assert [r['library_book_id'] for r in page['results']]==[row['library_book_id']]
@pytest.mark.parametrize('state',['NOT_BUILT','BUILDING','FAILED','STALE'])
def test_safe_local_fallback(client,library,state):
    lib=library();book(client,lib)
    if state!='NOT_BUILT':store.collection('intelligence_targets').insert_one({'library_id':lib,'target':'SEARCH_INDEX','state':state})
    page=TenantIntelligence(encoder).semantic(lib,{'sub':'1'},'computer',staff=True)
    assert page['source']['search_source']=='LOCAL_FALLBACK' and all(r['library_id']==lib for r in page['results'])
def test_archived_book_never_returned_from_stale_index(client,library):
    lib=library();row=book(client,lib);_,worker=build(lib)
    store.collection('library_books').update_one({'library_book_id':row['library_book_id']},{'$set':{'status':'WITHDRAWN'}})
    assert not worker.semantic(lib,{'sub':'1'},'computer',staff=True)['results']
def test_tenant_kg_local_identity_and_no_private_nodes(client,library):
    lib=library();row=book(client,lib);job,_=build(lib,'KNOWLEDGE_GRAPH')
    manifest,records,graph=artifacts.validate(lib,'KNOWLEDGE_GRAPH',job['artifact_generation_id'])
    assert {n['type'] for n in graph['nodes']}=={'Book','Author','Subject'}
    assert next(n for n in graph['nodes'] if n['type']=='Book')['library_book_id']==row['library_book_id']
    assert service.graph(lib,{'sub':'1'},staff=True)['source']=='TENANT_KG'
@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_checksums_missing_corrupt_and_reconciliation(client,library,target):
    lib=library();book(client,lib);job,_=build(lib,target)
    path=store.directory(lib,'search' if target=='SEARCH_INDEX' else 'kg',job['artifact_generation_id'])
    (path/'metadata.json').write_bytes(b'corrupt')
    with pytest.raises(HTTPException):artifacts.validate(lib,target,job['artifact_generation_id'])
    assert service.target_status(lib,target)['status']=='RECOVERY_REQUIRED'
    assert any(p['code']=='ACTIVE_ARTIFACT_INVALID' for p in service.reconcile(lib,{'sub':'1'})['problems'])
def test_foreign_job_generation_graph_query_denied(client,library):
    a,b=library(),library(name='Other',owner=2);book(client,a);job,worker=build(a)
    for path in [f'/libraries/{b}/intelligence/jobs/{job["job_id"]}',f'/libraries/{b}/intelligence/generations/{job["requested_generation_id"]}']:
        assert client.get(path,headers={'x-test-user':'2'}).status_code==404
    with pytest.raises(HTTPException):worker.semantic(b,{'sub':'1'},'computer',staff=True)
    with pytest.raises(HTTPException):service.graph(b,{'sub':'1'},staff=True)
def test_raw_artifacts_and_path_traversal_denied(client,library):
    lib=library()
    for path in [f'/libraries/{lib}/intelligence/index.faiss',f'/libraries/{lib}/intelligence/graph.json','/libraries/..%2Foutside/intelligence']:
        assert client.get(path).status_code in [404,422]
    with pytest.raises(HTTPException):store.directory(lib,'search','../outside')
def test_lazy_cache_namespace_and_eviction(client,library):
    cache=artifacts.ArtifactCache(max_entries=2);assert cache.metrics()['entries']==0
    keys=[]
    for _ in range(3):
        lib=library();book(client,lib);job,_=build(lib);current=service.target_status(lib,'SEARCH_INDEX')
        cache.load(lib,'SEARCH_INDEX',job['artifact_generation_id'],current['manifest_checksum']);keys.append((lib,job['artifact_generation_id'],'SEARCH_INDEX'))
    assert cache.metrics()['entries']==2 and cache.metrics()['evictions']==1
    assert keys[0] not in cache.entries and keys[1] in cache.entries
def test_empty_generation_no_hnsw(client,library):
    lib=library();job,_=build(lib);assert service.target_status(lib,'SEARCH_INDEX')['status']=='EMPTY'
    assert not (store.directory(lib,'search',job['artifact_generation_id'])/'index.faiss').exists()
def test_status_contract_hides_internal_paths_tokens(client,library):
    lib=library();book(client,lib);build(lib)
    data=client.get(f'/libraries/{lib}/intelligence').json()
    assert data['search']['status']=='READY'
    assert not any(s in json.dumps(data).casefold() for s in ['fence_token','worker_id','storage_key','local-data','traceback'])
