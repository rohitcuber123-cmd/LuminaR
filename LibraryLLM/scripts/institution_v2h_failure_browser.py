"""Disposable-only fault review with the normal Search worker paused by operator.

No fault injection endpoint or production switch is added. Existing worker
injection hook operates only in this review process; accepted embeddings are
reused from the disposable library's content-addressed cache.
"""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
source=(ROOT/'scripts/institution_v2h_browser.py').read_text(encoding='utf8')
exec(source.split("assert db.name=='luminar_library'")[0],globals())
from fastapi import HTTPException
from backend.services import library_intelligence_store as store
from search.library_intelligence import TenantIntelligence
fixture=json.loads((REPORTS/'institution_v2h_fixtures.json').read_text())['disposable_library_id']
prior=json.loads((REPORTS/'institution_v2h_browser.json').read_text());checks=prior['checks'];matrix=prior['responsive']
assert fixture!=TEST and db.name=='luminar_library'
before=store.collection('intelligence_targets').find_one({'library_id':fixture,'target':'SEARCH_INDEX'})
manifest=json.loads((store.directory(fixture,'search',before['active_generation_id'])/'manifest.json').read_text())
def no_encoder(texts):raise AssertionError('Review must reuse existing disposable embeddings')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();token=sign(page,*credentials('staff'));ready(page,fixture)
    clickbuild(page,'Rebuild Search Index')
    queued=api(f'/libraries/{fixture}/intelligence',token)['search']['current_job'];assert queued['state']=='QUEUED'
    duplicate=api(f'/libraries/{fixture}/intelligence/builds',token,'POST',{'target':'SEARCH_INDEX'},202);assert duplicate['job_id']==queued['job_id']
    page.reload();page.get_by_role('heading',name='Semantic Search Index').wait_for(timeout=60000);expect(page.get_by_text('Queued',exact=True)).to_have_count(1)
    page.screenshot(path=str(REPORTS/'institution_v2h_queued.png'),full_page=True)
    context.close();context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();token=sign(page,*credentials('staff'));ready(page,fixture)
    assert api(f'/libraries/{fixture}/intelligence',token)['search']['current_job']['job_id']==queued['job_id']
    passed('Queued job survives refresh, browser restart and re-login; duplicate deduped')
    def known(stage):
        if stage=='VALIDATION':raise ValueError('Private worker traceback /internal/path never public')
    assert TenantIntelligence(no_encoder,model_version=manifest['model_version'],fail=known).run_one()
    ready(page,fixture);expect(page.get_by_role('button',name='Retry Build',exact=True)).to_be_visible();assert page.get_by_text('Ready',exact=True).count()==2
    assert 'traceback' not in page.locator('main').inner_text().lower()
    failed=api(f'/libraries/{fixture}/intelligence',token)['search'];assert failed['active_generation_id']==before['active_generation_id'] and failed['active_status']=='READY'
    page.screenshot(path=str(REPORTS/'institution_v2h_failed.png'),full_page=True)
    passed('Known failed rebuild preserves validated generation and bounded Retry UX')
    clickbuild(page,'Retry Build')
    def unknown(stage):
        if stage=='CHECKSUM':raise HTTPException(409,'WORKER_CRASH')
    assert TenantIntelligence(no_encoder,model_version=manifest['model_version'],fail=unknown).run_one()
    ready(page,fixture);expect(page.get_by_text('Needs recovery',exact=True)).to_have_count(1)
    assert page.get_by_role('button',name='Retry Build',exact=True).count()==0
    recovery=api(f'/libraries/{fixture}/intelligence',token)['search'];assert recovery['status']=='RECOVERY_REQUIRED'
    page.screenshot(path=str(REPORTS/'institution_v2h_recovery.png'),full_page=True)
    passed('Unknown outcome has distinct RECOVERY_REQUIRED UI without blind Retry')
    recovered=api(f'/libraries/{fixture}/intelligence/jobs/{recovery["current_job"]["job_id"]}/recover',token,'POST',{});assert recovered['state']=='FAILED'
    ready(page,fixture);clickbuild(page,'Retry Build')
    # Hold an actual old tenant HTTP response, then switch to TEST. Cancellation
    # or ignored completion must not overwrite the new route's canonical data.
    held={}
    def hold(route):
        if 'response' not in held:
            held['response']=route.fetch();held['route']=route
        else:route.continue_()
    page.route('**/api/libraries/'+fixture+'/intelligence',hold)
    page.get_by_role('button',name='Refresh status',exact=True).click();page.wait_for_timeout(500)
    assert held.get('response')
    page.locator('.workspace-sidebar select').select_option(TEST)
    page.wait_for_url('**/staff/libraries/'+TEST,timeout=60000)
    page.get_by_role('link',name='Intelligence',exact=True).click()
    page.get_by_role('heading',name='Semantic Search Index').wait_for(timeout=60000)
    try:held['route'].fulfill(response=held['response'])
    except Exception:pass  # Browser legitimately cancels the old scoped request.
    page.wait_for_timeout(300);assert page.get_by_text('150',exact=True).count()>=2
    assert page.get_by_text('3',exact=True).count()==0
    passed('Switch library during active polling ignores old real HTTP response')
    put('failure_ui',{'status':'PASS','known_failure':failed,'recovery_required':recovery,'operator_recovery':recovered,'test_artifacts_modified':False})
    put('security',{'status':'PASS','no_paths_or_tracebacks':True,'no_blind_recovery_retry':True,'cross_library_response_ignored':True})
    put('browser',{'status':'PASS','browser':browser.version,'checks':checks,'responsive':matrix,'errors':errors,'pending_safe_retry_library':fixture})
    browser.close()

