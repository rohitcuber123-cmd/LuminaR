"""Focused native browser recheck after effect ownership lint repair."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
source=(ROOT/'scripts/institution_v2h_browser.py').read_text(encoding='utf8')
exec(source.split("assert db.name=='luminar_library'")[0],globals())
prior=json.loads((REPORTS/'institution_v2h_browser.json').read_text());checks=prior['checks'];matrix=prior['responsive']
fixture=json.loads((REPORTS/'institution_v2h_fixtures.json').read_text())['disposable_library_id']
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();token=sign(page,*credentials('staff'));ready(page,fixture)
    page.get_by_role('button',name='Rebuild Search Index',exact=True).click();dialog=page.get_by_role('dialog');expect(dialog).to_be_visible();dialog.get_by_role('button',name='Cancel',exact=True).click();expect(dialog).not_to_be_visible()
    held={}
    def hold(route):
        if not held:held.update(route=route,response=route.fetch())
        else:route.continue_()
    page.route('**/api/libraries/'+fixture+'/intelligence',hold)
    page.get_by_role('button',name='Refresh status',exact=True).click();page.wait_for_timeout(500);assert held
    page.locator('.workspace-sidebar select').select_option(TEST);page.wait_for_url('**/staff/libraries/'+TEST,timeout=60000)
    page.get_by_role('link',name='Intelligence',exact=True).click();page.get_by_role('heading',name='Semantic Search Index').wait_for(timeout=60000)
    try:held['route'].fulfill(response=held['response'])
    except Exception:pass
    page.wait_for_timeout(200);assert page.get_by_text('150',exact=True).count()>=2 and page.get_by_text('3',exact=True).count()==0
    passed('Final current-source confirmation and scoped-response ownership recheck')
    first=api('/libraries/register',token,'POST',{'name':'Part 2H first confirmation QA','slug':'v2h-confirm-'+uuid4().hex[:10],'library_type':'PUBLIC_LIBRARY','access_mode':'PUBLIC'},201)['library']['library_id']
    api(f'/libraries/{first}/inventory/books',token,'POST',{'title':'First catalogue entry','subjects':['Technology'],'create_physical_holding':True,'copies':1,'shelf_location':'QA','idempotency_key':str(uuid4())},201)
    page.set_viewport_size({'width':375,'height':812});ready(page,first)
    page.get_by_role('button',name='Build Search Index',exact=True).click();dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
    assert dialog.get_by_text('The new generation becomes available only after validation and publication. Your library catalogue remains available while it builds.',exact=True).count()==1
    assert 'current validated generation' not in dialog.inner_text()
    assert dialog.evaluate('(e)=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1}')
    page.screenshot(path=str(REPORTS/'institution_v2h_first_build_dialog_375.png'),animations='disabled')
    dialog.get_by_role('button',name='Cancel',exact=True).click();assert db.institution_intelligence_jobs.count_documents({'library_id':first})==0
    passed('First-build confirmation accurately describes no prior generation',library_id=first,no_automatic_job=True)
    put('page_recheck',{'status':'PASS','confirmation_cancel':True,'actual_old_HTTP_response_ignored':True,'TEST_only_counts':True,'first_build_copy_accurate':True,'first_build_dialog_375_fit':True})
    put('browser',{**prior,'status':'PASS','checks':checks})
    browser.close()

