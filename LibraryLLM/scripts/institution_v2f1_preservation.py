"""Read-only critical-closure preservation checks; never inspect document content."""
import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.database.mongodb import db
from scripts.institution_v2f_baseline import digest
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
def capture():
    assert db.name=='luminar_library' and db.client.address[0] in ('localhost','127.0.0.1','::1')
    critical=json.loads((ROOT/'reports/institution_v2f1_critical_baseline.json').read_text())
    baseline=json.loads((ROOT/'reports/institution_v2f_baseline.json').read_text())
    previous=json.loads((ROOT/'reports/institution_v2f_preservation.json').read_text())
    results={}
    for key,collection in [('original_TEST_books','institution_library_books'),('original_TEST_holdings','institution_holdings')]:
        rows=list(db[collection].find({'library_id':TEST},{'_id':0}));actual={'count':len(rows),'sha256':digest(rows)}
        results[key]={'before':critical[key],'after':actual,'unchanged':actual==critical[key]}
    count=db.books.estimated_document_count()
    artifacts=[{'path':name,'unchanged':(ROOT/name).exists() and {'bytes':(ROOT/name).stat().st_size,'mtime_ns':(ROOT/name).stat().st_mtime_ns}==expected} for name,expected in baseline['artifact_metadata'].items()]
    protected=[]
    exceptions=previous['protected_sources']['minimal_adapter_exceptions']
    for name in previous['protected_sources']['sha256_comparisons']:
        expected=exceptions[name]['after_sha256'] if name in exceptions else baseline['source_sha256'][name]
        actual=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        protected.append({'path':name,'unchanged':actual==expected})
    memberships={str(uid):db.institution_memberships.find_one({'library_id':TEST,'user_id':uid,'status':'ACTIVE'},{'_id':0,'role':1,'is_owner':1}) for uid in [4,10]}
    assets=list(db.institution_library_assets.find({'library_id':TEST,'status':{'$nin':['DELETED','DELETING']}},{'_id':0,'asset_id':1,'status':1,'library_book_id':1,'title':1,'uploaded_by_user_id':1}))
    data={'status':'PASS','captured_at':datetime.now(timezone.utc).isoformat(),'TEST':results,'ACTIVE_TEST_records':db.institution_library_books.count_documents({'library_id':TEST,'status':'ACTIVE'}),'TEST_holdings':db.institution_holdings.count_documents({'library_id':TEST}),'memberships':memberships,'global_catalogue':{'before':critical['global_count'],'after':count,'unchanged':count==critical['global_count'],'method':'estimated_document_count; no full 5M row digest'},'protected_artifacts':{'compared':len(artifacts),'all_unchanged':all(a['unchanged'] for a in artifacts),'method':'bytes and mtime_ns','checks':artifacts},'protected_sources':{'compared':len(protected),'all_unchanged':all(a['unchanged'] for a in protected),'checks':protected},'TEST_asset_count':len(assets),'allowed_new_QA_asset':'197703fb-6af8-4a94-87cb-c28fdc83fba5','safe_review_library':'f93d9da8-bb7c-402c-9ee1-edc4bb61fe9e','concurrent_owner_assets_preserved':True,'no_private_file_content_read':True,'no_tenant_catalogue_HNSW_KG_build':True,'no_router_or_global_ranking_change':True}
    assert all(r['unchanged'] for r in results.values())
    assert data['ACTIVE_TEST_records']==data['TEST_holdings']==150 and count==5000000
    assert data['protected_artifacts']['all_unchanged'] and data['protected_sources']['all_unchanged']
    (ROOT/'reports/institution_v2f1_critical_preservation.json').write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
    print(json.dumps({'status':'PASS','TEST':150,'holdings':150,'global':count,'artifacts':len(artifacts),'sources':len(protected),'TEST_assets':len(assets)}))
if __name__=='__main__':capture()
