"""Real progress and rendered accessibility on a disposable cached rebuild."""
from pathlib import Path
import sys,threading
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
source=(ROOT/'scripts/institution_v2h_failure_browser.py').read_text(encoding='utf8')
exec(source.split('with sync_playwright() as p:')[0],globals())
pause=threading.Event();release=threading.Event();worker_errors=[]
def hold(stage):
    if stage=='VALIDATION':pause.set();assert release.wait(180)
def work():
    try:TenantIntelligence(no_encoder,model_version=manifest['model_version'],fail=hold).run_one()
    except Exception as e:worker_errors.append(type(e).__name__)
thread=threading.Thread(target=work);thread.start();assert pause.wait(30)
rows=[]
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();token=sign(page,*credentials('staff'))
        for width,height in [(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]:
            page.set_viewport_size({'width':width,'height':height});ready(page,fixture)
            progress=page.get_by_role('progressbar',name='Search Index build progress');expect(progress).to_have_attribute('value','3');expect(progress).to_have_attribute('max','3')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            page.add_script_tag(content=(ROOT/'frontend/node_modules/axe-core/axe.min.js').read_text(encoding='utf8'))
            results=page.evaluate("async()=>{const r=await axe.run(document.querySelector('main'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return {violations:r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)})),passes:r.passes.length}}")
            assert not results['violations'],results['violations']
            page.screenshot(path=str(REPORTS/f'institution_v2h_progress_{width}.png'),full_page=True,animations='disabled')
            trigger=page.get_by_role('button',name='Rebuild Knowledge Graph',exact=True);trigger.focus();page.keyboard.press('Enter');dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
            a11y=page.evaluate("async()=>{const r=await axe.run(document.querySelector('dialog'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return r.violations.map(v=>({id:v.id,impact:v.impact}))}")
            assert not a11y,a11y
            assert dialog.evaluate('(e)=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1}')
            page.screenshot(path=str(REPORTS/f'institution_v2h_kg_dialog_{width}.png'),animations='disabled')
            page.keyboard.press('Escape');expect(dialog).not_to_be_visible();assert trigger.evaluate('(e)=>document.activeElement===e')
            rows.append({'viewport':[width,height],'status':'PASS','progress':{'value':3,'max':3,'stage':'VALIDATION','actual_worker':True},'axe':results,'dialog_axe':a11y,'dialog_fit':True,'keyboard_enter_escape':True,'focus_restore':True})
        release.set();thread.join(30);assert not thread.is_alive() and not worker_errors
        state=waitready(page,fixture,token,'search');assert state['search']['active_generation_id']!=before['active_generation_id']
        passed('Known FAILED Retry completes with accepted cached embeddings and atomic publish')
        put('progress',{'status':'PASS','actual_worker_progress':rows,'retry_generation':state['search']['active_generation_id'],'previous_generation':before['active_generation_id']})
        put('accessibility',{'status':'PASS','ready_keyboard':matrix,'active_progress_and_kg_dialog':rows,'violations':[],'rendered_contrast':'axe color-contrast checked at all six viewports'})
        responsive=json.loads((REPORTS/'institution_v2h_responsive.json').read_text());responsive['progress_and_kg_dialog']=rows;put('responsive',responsive)
        put('browser',{'status':'PASS','browser':browser.version,'checks':checks,'responsive':matrix,'active_progress_and_kg_dialog':rows,'errors':errors})
        browser.close()
finally:
    release.set();thread.join(30)
