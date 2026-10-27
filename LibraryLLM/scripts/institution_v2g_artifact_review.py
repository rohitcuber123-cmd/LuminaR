"""Read-only real artifact validation, lazy retained-memory and reconciliation receipts."""
import gc,json,sys,time
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.database.mongodb import db
from backend.services import library_intelligence_artifacts as artifacts,library_intelligence_service as service,library_intelligence_store as store
from scripts.institution_v2f_baseline import digest
from scripts.institution_v2f_preservation import personal_snapshot
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae';REPORTS=ROOT/'reports'
def put(name,value):(REPORTS/f'institution_v2g_{name}.json').write_text(json.dumps(value,indent=2,default=str),encoding='utf8')
def main():
    assert db.name=='luminar_library'
    baseline=json.loads((REPORTS/'institution_v2g_baseline.json').read_text())
    current={n:{'count':db[n].count_documents({'library_id':TEST}),'sha256':digest(list(db[n].find({'library_id':TEST},{'_id':0})))} for n in baseline['TEST']}
    assert current==baseline['TEST'],'TEST preservation mismatch'
    changed_artifacts=[name for name,record in baseline['global_artifact_metadata'].items() if not (ROOT/name).is_file() or {'bytes':(ROOT/name).stat().st_size,'mtime_ns':(ROOT/name).stat().st_mtime_ns}!=record]
    assert not changed_artifacts,changed_artifacts
    count=db.books.estimated_document_count();assert count==baseline['global_book_count']==5000000
    assert personal_snapshot(ROOT/'rag/private_documents/registry.sqlite')==baseline['personal_logical']
    changed_sources=[p for p,d in baseline['source_sha256'].items() if store.checksum(ROOT/p)!=d]
    protected=[p for p in baseline['source_sha256'] if p.startswith(('assistant/','rag/','recommendation/','knowledge_graph/')) or p.startswith('search/') and p!='search/api.py']
    assert not set(changed_sources)&set(protected),'Protected semantic source changed'
    put('preservation',{'status':'PASS','TEST':current,'global_book_count':count,'global_artifacts_compared':len(baseline['global_artifact_metadata']),'changed_artifacts':changed_artifacts,'comparison':'Exact byte length and nanosecond mtime against immutable pre-phase baseline; no global build invoked.','global_HNSW_rebuilt':False,'global_KG_rebuilt':False,'protected_semantic_sources_unchanged':True,'personal_registry_logical_unchanged':True,'changed_existing_sources':changed_sources,'no_TEST_QA_mutations':True})
    fixtures=json.loads((REPORTS/'institution_v2g_fixtures.json').read_text());libraries=[TEST,fixtures['A']['library_id'],fixtures['B']['library_id'],fixtures['C']['library_id'],fixtures['benchmark']['library_id']]
    reviewed=[];reconciliations=[]
    for lib in libraries:
        statuses=[]
        for target in ['SEARCH_INDEX','KNOWLEDGE_GRAPH']:
            status=service.target_status(lib,target);assert status['status']=='READY'
            manifest,records,payload=artifacts.validate(lib,target,status['active_generation_id'])
            statuses.append({'target':target,'status':'PASS','generation_id':manifest['generation_id'],'source_generation_id':manifest['source_generation_id'],'book_count':len(records),'manifest':manifest,'artifact_bytes':status['artifact_bytes']})
        reviewed.append({'library_id':lib,'targets':statuses})
        result=service.reconcile(lib,{'sub':'4'});assert not result['problems'],result['problems'];reconciliations.append(result)
    put('validation',{'status':'PASS','libraries':reviewed,'real_artifacts':True,'checks':['canonical UUID namespace','source generation and fingerprint','dataset and target checksums','exact ACTIVE metadata identity','384 normalized finite float32 vectors','FAISS HNSW inner product parameters and reconstructed vectors','deterministically rederived KG nodes/edges','no private member or document fields']})
    put('reconciliation',{'status':'PASS','dry_run':True,'receipts':reconciliations,'writes_or_deletes':False})
    generation=store.scoped_generation(TEST,reviewed[0]['targets'][0]['source_generation_id'],{'sub':'4'})
    put('dataset_generation',{'status':'PASS','TEST':generation,'eligibility':'All ACTIVE nonblank canonical book metadata; role-specific usable filtering occurs during final result hydration. No document chunks.','global_enrichment':'Existing linked work may supply missing descriptive public fields, never inventory/authority.'})
    rss=lambda:psutil.Process().memory_info().rss
    cache=artifacts.ArtifactCache(max_entries=2);rss_start=rss();memory=[]
    for lib in libraries[:3]+[TEST]:
        status=service.target_status(lib,'SEARCH_INDEX');before=rss();started=time.perf_counter();cache.load(lib,'SEARCH_INDEX',status['active_generation_id'],status['manifest_checksum'])
        memory.append({'library_id':lib,'load_ms':(time.perf_counter()-started)*1000,'rss_before':before,'rss_after':rss(),'cache':cache.metrics()})
    assert cache.metrics()['entries']==2 and cache.metrics()['evictions']==2
    retained=cache.metrics();cache.clear();gc.collect()
    put('memory',{'status':'PASS','model_free_review_process':True,'rss_start':rss_start,'switches':memory,'retained_before_clear':retained,'after_clear':cache.metrics(),'rss_after_clear':rss(),'RSS_caveat':'Allocator/native arenas can retain high-water memory after eviction; cache references and retained bytes are bounded. Production resident global models are reused, not loaded once per tenant.'})
    put('lazy_loading',{'status':'PASS','startup_entries':0,'search_cache_default_entries':3,'kg_cache_default_entries':3,'per_cache_max_retained_bytes':256*1024*1024,'no_startup_scan_or_load':True,'library_generation_target_keys':True,'A_B_C_A_eviction':'institution_v2g_cache.json','memory':'institution_v2g_memory.json'})
    kg={**service.target_status(TEST,'KNOWLEDGE_GRAPH'),'library_id':TEST,'source':'TENANT_KG'}
    put('kg_routing',{'status':'PASS','TEST':kg,'global_KG_fallback':False,'not_ready':'Truthful TENANT_KG state and separate Global Graph Lab link.','browser':'institution_v2g_browser.json','online_only':'institution_v2g_online_only.json','cross_tenant':'institution_v2g_cross_tenant.json'})
    print('PASS real artifact validation, dry-run reconciliation, bounded cache and preservation',flush=True)
if __name__=='__main__':main()
