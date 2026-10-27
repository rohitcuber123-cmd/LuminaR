"""Read-only actual Chromium reproduction and canonical TEST count provenance."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright
from scripts.full_product_browser_session import credentials
from backend.database.mongodb import db
from backend.services import library_book_formats as formats,library_intelligence_service as intelligence,library_intelligence_store as store
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae';BASE='http://127.0.0.1:5173'
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':900})
    page.goto(BASE+'/login');email,password=credentials('staff')
    page.locator('input[type=email]').fill(email);page.locator('input[type=password]').fill(password)
    page.get_by_role('button',name='Sign In',exact=True).click();page.wait_for_url(lambda u:'/login' not in str(u),timeout=60000)
    with page.expect_response(lambda r:f'/libraries/{TEST}/analytics?' in r.url,timeout=60000) as response:
        page.goto(BASE+f'/staff/libraries/{TEST}/analytics')
    r=response.value
    result={'endpoint':r.url.removeprefix(BASE),'method':r.request.method,'library_id':TEST,'status':r.status,'safe_body':r.json()}
    page.get_by_text('Unable to load analytics',exact=True).wait_for(timeout=60000)
    page.screenshot(path=str(ROOT/'reports/post2h_analytics_failure_before.png'),full_page=True)
    (ROOT/'reports/post2h_analytics_failure_before.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    browser.close()
    print({'analytics_http_status_before':r.status,'safe_response':result['safe_body']})
row=db.institution_library_books.find_one({'library_id':TEST,'title':'CN'},{'_id':0})
assert row is not None
bid=row['library_book_id'];holding=db.institution_holdings.find_one({'library_id':TEST,'library_book_id':bid},{'_id':0})
assets=list(db.institution_library_assets.find({'library_id':TEST,'library_book_id':bid},{'_id':0,'asset_id':1,'title':1,'status':1,'visibility':1,'created_by_user_id':1,'created_at':1,'asset_type':1}))
audit=list(db.institution_audit_events.find({'library_id':TEST,'metadata.library_book_id':bid},{'_id':0,'event':1,'actor_user_id':1,'created_at':1,'metadata':1}))
receipt=db.institution_lending_operations.find_one({'library_id':TEST,'library_book_id':bid,'operation_type':'LIBRARY_BOOK_CREATED','state':'COMMITTED'},{'_id':0,'operation_type':1,'state':1,'created_at':1,'actor_user_id':1,'result.has_physical':1,'result.holding':1})
data={'library_id':TEST,'canonical_active_book_count':db.institution_library_books.count_documents({'library_id':TEST,'status':'ACTIVE'}),
 'holding_count':db.institution_holdings.count_documents({'library_id':TEST}),
 'extra_record':{k:row.get(k) for k in ['library_book_id','title','source','created_by_user_id','created_at','status','accession_number','global_work_id']},
 'format':formats.capabilities(TEST,bid,holding),'holding':holding,'assets':assets,'audit':audit,'creation_receipt':receipt,
 'intentional_no_holding':formats.unstocked_origin(TEST,bid),
 'search_status':intelligence.target_status(TEST,'SEARCH_INDEX',observe_stale=False),
 'kg_status':intelligence.target_status(TEST,'KNOWLEDGE_GRAPH',observe_stale=False),
 'eligible_records':len(store.source_records(TEST))}
(ROOT/'reports/post2h_test_count_evidence.json').write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
print({'CN_id':bid,'source':row['source'],'creator':row.get('created_by_user_id'),'format':data['format'],'count':data['canonical_active_book_count'],'intelligence_search':data['search_status']['status']})
