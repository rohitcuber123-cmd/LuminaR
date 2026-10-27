"""Normal local QA authority, canonical disposable imports and real resident models."""
import csv,io,json,sys,time,statistics
from pathlib import Path
from uuid import uuid4
import requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.full_product_browser_session import credentials
from backend.database.mongodb import db
from backend.services import library_intelligence_artifacts as artifacts,library_intelligence_service as service,library_intelligence_store as store
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae';REPORTS=ROOT/'reports';CORE='http://127.0.0.1:8002';SEARCH='http://127.0.0.1:8003'
def put(name,value):(REPORTS/f'institution_v2g_{name}.json').write_text(json.dumps(value,indent=2,default=str),encoding='utf8')
def login(kind):
    email,password=credentials(kind);r=requests.post(CORE+'/auth/login',json={'email':email,'password':password},timeout=30);assert r.ok
    return {'Authorization':'Bearer '+r.json()['access_token']}
def call(path,*,method='GET',body=None,headers=None,server=CORE,expected=200,**kw):
    for attempt in range(50):
        r=requests.request(method,server+path,headers=headers,json=body,timeout=180,**kw)
        if r.status_code!=503:break
        time.sleep(.2)
    assert r.status_code==expected,(path,r.status_code,r.text[:250]);return r.json()
def query(lib,headers,q='computer networks',staff=False):
    start=time.perf_counter();result=call(f'/libraries/{lib}/catalogue/search',headers=headers,server=SEARCH,params={'search':q,'staff':str(staff).lower(),'limit':20})
    assert all(row['library_id']==lib and row['source']=='LIBRARY' for row in result['results'])
    return result,(time.perf_counter()-start)*1000
def builds(lib,headers):
    started=time.perf_counter();jobs=[call(f'/libraries/{lib}/intelligence/builds',method='POST',body={'target':t},headers=headers,expected=202) for t in ['SEARCH_INDEX','KNOWLEDGE_GRAPH']]
    deadline=time.monotonic()+1200
    while time.monotonic()<deadline:
        jobs=[call(f'/libraries/{lib}/intelligence/jobs/{j["job_id"]}',headers=headers) for j in jobs]
        if all(j['state'] in ['SUCCEEDED','FAILED','RECOVERY_REQUIRED'] for j in jobs):break
        time.sleep(.5)
    assert all(j['state']=='SUCCEEDED' for j in jobs),[(j['target'],j['state'],j['error_code']) for j in jobs]
    return {'library_id':lib,'jobs':jobs,'elapsed_seconds':time.perf_counter()-started,'status':call(f'/libraries/{lib}/intelligence',headers=headers)}
def create(name,headers,patron):
    lib=call('/libraries/register',method='POST',body={'name':name,'slug':'v2g-'+uuid4().hex[:14],'library_type':'PUBLIC_LIBRARY','access_mode':'PUBLIC'},headers=headers,expected=201)['library']['library_id']
    call(f'/libraries/{lib}/join',method='POST',body={},headers=patron)
    return lib
def add(lib,headers,title,work=None):
    body={'title':title,'subjects':['Computer networks','Technology'],'authors':['Part 2G QA'],'description':'Canonical metadata about computer networks and reliable internet protocols.','create_physical_holding':True,'copies':1,'shelf_location':'QA','idempotency_key':str(uuid4())}
    if work:body['global_work_id']=work
    return call(f'/libraries/{lib}/inventory/books',method='POST',body=body,headers=headers,expected=201)
def main():
    assert db.name=='luminar_library' and db.client.address[0] in ['localhost','127.0.0.1','::1']
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        try:
            if requests.get(SEARCH+'/health',timeout=3).ok and requests.get(CORE+'/health',timeout=3).ok:break
        except requests.RequestException:pass
        time.sleep(1)
    owner,patron=login('staff'),login('patron');checks=[]
    for role,headers,staff in [('ADMIN',owner,True),('GENERAL_USER',patron,False)]:
        for q in ['computer networks','linguistics','history of Glasgow']:
            result,latency=query(TEST,headers,q,staff);assert result['source']['search_source']=='TENANT_SEMANTIC' and result['results']
            checks.append({'role':role,'query':q,'source':result['source'],'book_ids':[r['library_book_id'] for r in result['results']],'latency_ms':latency,'status':'PASS'})
    put('search_routing',{'status':'PASS','checks':checks,'resident_models':True,'global_filler':False})
    target=REPORTS/'institution_v2g_fixtures.json'
    fixtures=json.loads(target.read_text()) if target.exists() else {}
    work=db.institution_library_books.find_one({'library_id':TEST,'global_work_id':{'$type':'string'}},{'global_work_id':1})['global_work_id']
    for name in ['A','B','C']:
        if name not in fixtures:
            lib=create('Part 2G isolation '+name,owner,patron);fixtures[name]={'library_id':lib,'books':[]};put('fixtures',fixtures)
            for i in range(24):fixtures[name]['books'].append(add(lib,owner,f'Part 2G {name} computer networks {i:02d}',work if i==0 else None)['library_book_id'])
            put('fixtures',fixtures)
        lib=fixtures[name]['library_id']
        if service.target_status(lib,'SEARCH_INDEX')['status']!='READY' or service.target_status(lib,'KNOWLEDGE_GRAPH')['status']!='READY':fixtures[name]['build']=builds(lib,owner);put('fixtures',fixtures)
        print('PASS real isolation build',name,flush=True)
    online=json.loads((REPORTS/'institution_v2f1_consolidated_fixtures.json').read_text())['format_library']
    if service.target_status(online,'SEARCH_INDEX')['status']!='READY' or service.target_status(online,'KNOWLEDGE_GRAPH')['status']!='READY':receipt=builds(online,owner)
    else:receipt={'status':call(f'/libraries/{online}/intelligence',headers=owner)}
    records=store.source_records(online);assert not any('09:00' in str(r) or 'Cedar Reading Room opens' in str(r) for r in records)
    page,_=query(online,patron,'Consolidated Online');assert page['source']['search_source']=='TENANT_SEMANTIC'
    graph=call(f'/libraries/{online}/intelligence/graph',headers=patron)
    online_ids={r['library_book_id'] for r in db.institution_library_books.find({'library_id':online,'status':'ACTIVE'}) if not db.institution_holdings.find_one({'library_id':online,'library_book_id':r['library_book_id']})}
    assert online_ids and online_ids <= {n['library_book_id'] for n in graph['nodes'] if n['type']=='Book'}
    put('online_only',{'status':'PASS','library_id':online,'online_book_ids':sorted(online_ids),'search_source':page['source']['search_source'],'graph_source':graph['source'],'no_document_chunks':True,'build':receipt})
    cache=artifacts.ArtifactCache(max_entries=2);switches=[]
    assert cache.metrics()['entries']==0
    for name in ['A','B','C','A']:
        lib=fixtures[name]['library_id'];status=service.target_status(lib,'SEARCH_INDEX');_,rows,_=cache.load(lib,'SEARCH_INDEX',status['active_generation_id'],status['manifest_checksum'])
        result,latency=query(lib,patron);assert {r['library_book_id'] for r in result['results']} <= set(fixtures[name]['books'])
        assert all(r['library_id']==lib for r in rows)
        graph=call(f'/libraries/{lib}/intelligence/graph',headers=patron);assert graph['source']=='TENANT_KG'
        assert {n['library_book_id'] for n in graph['nodes'] if n['type']=='Book'} <= set(fixtures[name]['books'])
        switches.append({'library':name,'library_id':lib,'cache':cache.metrics(),'query_ms':latency,'status':'PASS'})
    assert cache.metrics()['entries']==2 and cache.metrics()['evictions']==2
    assert fixtures['A']['books'][0]!=fixtures['B']['books'][0]
    put('cache',{'status':'PASS','startup_entries':0,'namespace_key':['library_id','generation_id','target'],'switches':switches,'bounded':True,'same_global_work_local_id_distinct':True})
    put('cross_tenant',{'status':'PASS','libraries':fixtures,'switch_order':['A','B','C','A'],'same_global_work_id':work,'canonical_local_id_distinct':True,'foreign_results':0})
    if 'benchmark' not in fixtures:
        lib=create('Part 2G 1000 book benchmark',owner,patron);fixtures['benchmark']={'library_id':lib};put('fixtures',fixtures)
    lib=fixtures['benchmark']['library_id']
    if not db.institution_library_books.count_documents({'library_id':lib}):
        data=io.StringIO();writer=csv.writer(data);writer.writerow(['title','subjects','authors','description','copies','shelf_location'])
        for i in range(1000):writer.writerow([f'Part 2G benchmark networking volume {i:04d}','Computer networks;Technology','Benchmark Reader',f'Computer networks, protocol routing and internet reliability volume {i}',1,'QA'])
        preview=call(f'/libraries/{lib}/inventory/imports/preview',method='POST',headers=owner,expected=201,files={'file':('benchmark.csv',data.getvalue().encode(),'text/csv')})
        assert preview['rows_valid']==1000
        result=call(f'/libraries/{lib}/inventory/imports/{preview["import_id"]}/apply',method='POST',body={'existing_policy':'skip'},headers=owner)
        assert result['created_records']==1000,result
    receipt=builds(lib,owner) if service.target_status(lib,'SEARCH_INDEX')['status']!='READY' else {'status':call(f'/libraries/{lib}/intelligence',headers=owner)}
    times=[query(lib,patron)[1] for _ in range(5)]
    put('benchmark',{'status':'PASS','profile':artifacts.PARAMETERS,'TEST_150':{'build':'institution_v2g_build_jobs.json','latencies_ms':[r['latency_ms'] for r in checks]},'library_1000':{'library_id':lib,'books':1000,'build':receipt,'query_ms':times,'median_ms':statistics.median(times)},'limit_books':store.MAX_BOOKS,'hundred_thousand_build':False,'scope':'Local canonical disposable library; real resident embedding/reranker, no global writes.'})
    print('PASS TEST semantic, online-only, A/B/C/A and 1000 benchmark',flush=True)
if __name__=='__main__':main()
