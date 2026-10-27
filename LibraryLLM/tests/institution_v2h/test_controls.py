import json
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from backend.services import library_intelligence_store as store, library_intelligence_service as service
from search.library_intelligence import TenantIntelligence
from tests.institution_v2g.test_intelligence import book, build, encoder

def member(lib,user,role):
    from uuid import uuid4
    store.collection('memberships').insert_one({'membership_id':str(uuid4()),'library_id':lib,'user_id':user,'role':role,'status':'ACTIVE','is_owner':False})

@pytest.mark.parametrize('role,user,code',[('ADMIN',1,200),('LIBRARIAN',2,200),('GENERAL_USER',3,403),('PLATFORM_ONLY',9,404)])
def test_intelligence_status_authority(client,library,role,user,code):
    lib=library()
    if role in ['LIBRARIAN','GENERAL_USER']:member(lib,user,role)
    if role=='PLATFORM_ONLY':
        from backend.database.mongodb import db
        db.platform_role_assignments.insert_one({'user_id':9,'role':'PLATFORM_ADMIN','status':'ACTIVE','approval_ref':'isolated-fixture','approved_by':'fixture','approved_at':store.now()})
    response=client.get(f'/libraries/{lib}/intelligence',headers={'x-test-user':str(user)})
    assert response.status_code==code
    if code==200:assert response.json()['can_build']==(role=='ADMIN')

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
@pytest.mark.parametrize('user,role,code',[(1,'ADMIN',202),(2,'LIBRARIAN',403),(3,'GENERAL_USER',403),(9,'PLATFORM_ONLY',404)])
def test_build_exact_membership(client,library,target,user,role,code):
    lib=library();book(client,lib)
    if role in ['LIBRARIAN','GENERAL_USER']:member(lib,user,role)
    if role=='PLATFORM_ONLY':
        from backend.database.mongodb import db
        from backend.platform_dependencies import platform_assignments
        db.platform_role_assignments.insert_one({'user_id':user,'role':'PLATFORM_ADMIN','status':'ACTIVE','approval_ref':'isolated-fixture','approved_by':'fixture','approved_at':store.now()})
        assert platform_assignments(user)
    result=client.post(f'/libraries/{lib}/intelligence/builds',headers={'x-test-user':str(user)},json={'target':target})
    assert result.status_code==code
    if code==202:assert store.collection('intelligence_jobs').find_one({'job_id':result.json()['job_id'],'effective_active':True})

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_empty_library_build_blocked(client,library,target):
    lib=library();assert client.post(f'/libraries/{lib}/intelligence/builds',json={'target':target}).status_code==409
    assert store.collection('intelligence_jobs').count_documents({'library_id':lib})==0

def test_cross_library_build_denied(client,library):
    own,foreign=library(),library(owner=2);book(client,own)
    assert client.post(f'/libraries/{foreign}/intelligence/builds',json={'target':'SEARCH_INDEX'}).status_code==404

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_not_built_add_does_not_auto_build(client,library,target):
    lib=library();key='search' if target=='SEARCH_INDEX' else 'kg'
    assert client.get(f'/libraries/{lib}/intelligence').json()[key]['status']=='NOT_BUILT'
    book(client,lib);data=client.get(f'/libraries/{lib}/intelligence').json()
    assert data[key]['status']=='NOT_BUILT' and data['eligible_book_count']==1
    assert store.collection('intelligence_jobs').count_documents({})==0

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_duplicate_build_and_refresh_durable(client,library,target):
    lib=library();book(client,lib)
    def request():
        result=client.post(f'/libraries/{lib}/intelligence/builds',json={'target':target})
        assert result.status_code in [202,503],result.text
        return result
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:request(),range(2)))
    assert any(r.status_code==202 for r in results)
    ids=[]
    for result in results:
        if result.status_code==503:result=client.post(f'/libraries/{lib}/intelligence/builds',json={'target':target})
        assert result.status_code==202,result.text
        ids.append(result.json()['job_id'])
    assert ids[0]==ids[1]
    key='search' if target=='SEARCH_INDEX' else 'kg'
    assert client.get(f'/libraries/{lib}/intelligence').json()[key]['current_job']['job_id']==ids[0]
    assert store.collection('audit').count_documents({'event':('SEARCH_INDEX' if key=='search' else 'KG')+'_BUILD_REQUESTED'})==1

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_ready_generation_stale_and_no_auto_build(client,library,target):
    lib=library();book(client,lib);job,_=build(lib,target)
    key='search' if target=='SEARCH_INDEX' else 'kg'
    value=client.get(f'/libraries/{lib}/intelligence').json()[key]
    assert value['status']=='READY' and value['active_generation_id']==job['artifact_generation_id']
    assert value['built_at'] and value['artifact_verified'] and value['generation_sequence']==1
    assert value['last_build_duration_seconds']>=0
    if key=='kg':assert value['node_count']>0 and value['edge_count']>0
    store.collection('library_books').update_one({'library_id':lib},{'$set':{'title':'Changed catalogue title'}})
    assert client.get(f'/libraries/{lib}/intelligence').json()[key]['status']=='STALE'
    assert store.collection('intelligence_jobs').count_documents({'library_id':lib})==1

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_failed_rebuild_preserves_active_and_retry(client,library,target):
    lib=library();book(client,lib);first,_=build(lib,target)
    request=client.post(f'/libraries/{lib}/intelligence/builds',json={'target':target}).json()
    def fail(stage):
        if stage=='VALIDATION':raise ValueError('/private/path secret-fence traceback')
    assert TenantIntelligence(encoder,model_version='all-MiniLM-L6-v2:unit',fail=fail).run_one()
    key='search' if target=='SEARCH_INDEX' else 'kg';value=client.get(f'/libraries/{lib}/intelligence').json()[key]
    assert value['status']=='FAILED' and value['active_status']=='READY' and value['can_retry']
    assert value['active_generation_id']==first['artifact_generation_id'] and value['latest_job']['state']=='FAILED'
    assert 'private/path' not in json.dumps(value)
    retry=client.post(f'/libraries/{lib}/intelligence/builds',json={'target':target}).json()
    assert retry['job_id']!=request['job_id']

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_building_real_progress(client,library,target):
    lib=library();book(client,lib);store.request_build(lib,{'sub':'1'},target);job=store.claim('hidden-worker')
    store.progress(job,'EMBEDDING' if target=='SEARCH_INDEX' else 'KG_METADATA',1,3)
    key='search' if target=='SEARCH_INDEX' else 'kg';value=client.get(f'/libraries/{lib}/intelligence').json()[key]
    assert value['status']=='BUILDING' and value['current_job']['progress_current']==1 and value['current_job']['progress_total']==3
    assert 'hidden-worker' not in json.dumps(value) and 'fence_token' not in json.dumps(value)

@pytest.mark.parametrize('target',['SEARCH_INDEX','KNOWLEDGE_GRAPH'])
def test_recovery_required_distinct_and_no_blind_retry(client,library,target):
    lib=library();book(client,lib);job=store.request_build(lib,{'sub':'1'},target);claimed=store.claim('worker')
    store.collection('intelligence_jobs').update_one({'job_id':job['job_id']},{'$set':{'lease_expires_at':store.now()-timedelta(seconds=1)}})
    key='search' if target=='SEARCH_INDEX' else 'kg';value=client.get(f'/libraries/{lib}/intelligence').json()[key]
    assert value['status']=='RECOVERY_REQUIRED' and not value['can_retry']
    assert client.post(f'/libraries/{lib}/intelligence/builds',json={'target':target}).json()['job_id']==claimed['job_id']
    assert store.collection('intelligence_jobs').count_documents({})==1

def test_safe_status_whitelist(client,library):
    lib=library();book(client,lib);job=store.request_build(lib,{'sub':'1'},'SEARCH_INDEX')
    store.collection('intelligence_jobs').update_one({'job_id':job['job_id']},{'$set':{'error_code':'C:/secret','error_message':'Traceback secret','worker_id':'hidden','fence_token':'hidden'}})
    payload=client.get(f'/libraries/{lib}/intelligence').text
    assert all(s not in payload for s in ['C:/secret','Traceback','worker_id','fence_token'])

def test_audit_actor_and_idempotency(client,library):
    lib=library();book(client,lib);job,_=build(lib);store.build_audit(job,'SUCCEEDED')
    rows=list(store.collection('audit').find({'library_id':lib,'event':'SEARCH_INDEX_BUILD_SUCCEEDED'}))
    assert len(rows)==1 and rows[0]['actor_user_id']==1

def test_build_activity_hydrates_actor_for_librarian(client,library):
    lib=library();book(client,lib);build(lib);member(lib,2,'LIBRARIAN')
    result=client.get(f'/libraries/{lib}/staff/activity',headers={'x-test-user':'2'})
    assert result.status_code==200
    rows=[r for r in result.json()['results'] if r['event'].startswith('SEARCH_INDEX_BUILD_')]
    assert {r['event'] for r in rows}=={'SEARCH_INDEX_BUILD_REQUESTED','SEARCH_INDEX_BUILD_SUCCEEDED'}
    assert all(r['actor']['email']=='v2f-1@example.com' and r['library_id']==lib for r in rows)

