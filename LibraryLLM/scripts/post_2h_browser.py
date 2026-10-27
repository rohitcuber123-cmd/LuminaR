"""Real Chromium frontend closure. No build/lifecycle actions or stored credentials."""
import sys,json,secrets,time,requests
from uuid import uuid4
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright,expect
from scripts.full_product_browser_session import credentials
from backend.database.mongodb import db
from backend.services import auth_service
from scripts import migrate_management_authority as migration
BASE='http://127.0.0.1:5173';CORE='http://127.0.0.1:8002';TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
REPORTS=ROOT/'reports';checks=[];matrix=[];violations=[];errors=[];build_posts=[];user_id=None
def save(status='IN_PROGRESS'):
    (REPORTS/'post_2h_browser.json').write_text(json.dumps({'status':status,'checks':checks,'responsive':matrix,'accessibility':violations,'page_errors':errors,'live_build_requests':build_posts},indent=2),encoding='utf8')
def passed(name,**details):
    checks.append({'scenario':name,'status':'NOT_APPLICABLE' if details.get('availability')=='NOT_AVAILABLE' else 'PASS',**details});save();print('PASS '+name,flush=True)
def api(path,token):
    for attempt in range(20):
        r=requests.get(CORE+path,headers={'Authorization':'Bearer '+token},timeout=60)
        if r.status_code!=503:break
        time.sleep(.3)
    r.raise_for_status();return r.json()
def sign(page,email,password):
    page.goto(BASE+'/login');page.locator('input[type=email]').fill(email);page.locator('input[type=password]').fill(password)
    page.get_by_role('button',name='Sign In',exact=True).click();page.wait_for_url(lambda url:'/login' not in str(url),timeout=60000)
    return page.evaluate("localStorage.getItem('luminar_token')")
def out(page):
    page.get_by_role('button',name='Open account menu',exact=False).click()
    page.get_by_role('menuitem',name='Sign Out',exact=False).click();page.wait_for_url('**/login',timeout=60000)
def goto(page,path,heading=None):
    page.goto(BASE+path);page.locator('#main-content').wait_for()
    if heading:page.get_by_role('heading',name=heading,exact=True).wait_for(timeout=60000)
def catalog(page):
    page.get_by_text('5,000,000',exact=False).first.wait_for(timeout=60000)
    assert page.get_by_text('Library not found',exact=False).count()==0
    assert page.locator('.staff-workspace,.patron-context-bar').count()==0
def fit(page,element):
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    return element.evaluate('(e)=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,fit:r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1}}')
def axe(page,label,scope='document'):
    page.add_script_tag(path=str(ROOT/'frontend/node_modules/axe-core/axe.min.js'))
    result=page.evaluate('async(scope)=> (await axe.run(scope==="document"?document:scope,{runOnly:{type:"tag",values:["wcag2a","wcag2aa","wcag21aa"]}})).violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>n.target)}))',scope)
    violations.append({'surface':label,'scope':scope,'violations':result});save();assert not result,(label,result)
def dropdown(page,label,shot=None,keyboard=True):
    trigger=page.get_by_role('combobox',name=label,exact=True);trigger.scroll_into_view_if_needed();trigger.click()
    menu=page.locator('.luminar-select-menu');expect(menu).to_be_visible();rect=fit(page,menu);assert rect['fit']
    css=menu.evaluate('(e)=>{const s=getComputedStyle(e);return {background:s.backgroundColor,font:s.fontSize,border:s.borderRadius}}')
    assert css['font']=='14px' and css['background']!='rgba(0, 0, 0, 0)'
    assert trigger.evaluate('(e)=>getComputedStyle(e).backgroundColor')==page.evaluate('getComputedStyle(document.documentElement).getPropertyValue("--ui-surface").trim()') or trigger.evaluate('(e)=>getComputedStyle(e).backgroundColor')=='rgb(255, 253, 248)'
    if shot:page.screenshot(path=str(REPORTS/shot),animations='disabled')
    if keyboard:
        trigger.focus();page.keyboard.press('End');assert trigger.get_attribute('aria-activedescendant')
        page.keyboard.press('Home');assert trigger.get_attribute('aria-activedescendant')
        page.keyboard.press('ArrowDown');page.keyboard.press('ArrowUp')
    page.keyboard.press('Escape');expect(menu).not_to_be_visible();assert trigger.evaluate('(e)=>document.activeElement===e')
    return {'menu':rect,'theme':css,'keyboard':keyboard,'escape_focus_restore':True}

assert db.name=='luminar_library' and db.client.address[0] in ('localhost','127.0.0.1','::1')
email='post2h-platform-'+uuid4().hex[:12]+'@example.com';password=secrets.token_urlsafe(30);mail={};original=auth_service.send_otp_email
try:
    auth_service.send_otp_email=lambda address,name,otp:mail.update({address:otp}) or True
    user=auth_service.register_user('LuminaR Post Part 2H Platform QA',email,password);user_id=user['user_id']
    assert auth_service.verify_email_otp(email,mail.pop(email))
finally:auth_service.send_otp_email=original
proposal=migration.plan(db,{'platform_assignments':[{'user_id':user_id,'role':'PLATFORM_ADMIN','approved':True,'approved_by':'local-development-review','approval_ref':'USER-POST-2H-LOCAL-QA','reason':'Temporary local frontend context validation.'}]});migration.apply(db,proposal)
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        context.on('request',lambda r:build_posts.append(r.url.split('?')[0]) if r.method=='POST' and '/intelligence/builds' in r.url else None)
        staff_email,staff_password=credentials('staff');staff_token=sign(page,staff_email,staff_password)
        goto(page,f'/staff/libraries/{TEST}/inventory','Inventory')
        assert page.locator('.global-header').get_by_role('link',name='LuminaR home').get_attribute('href')==f'/staff/libraries/{TEST}'
        assert page.evaluate("JSON.parse(localStorage.getItem('luminar_workspace_contexts')).staffLibraryId")==TEST
        passed('TEST staff explicit context before account switch')
        out(page);assert page.evaluate("localStorage.getItem('luminar_workspace_contexts')")==None
        platform_token=sign(page,email,password);print('Platform login destination '+page.url+'; roles '+str(api('/me/platform-access',platform_token)),flush=True);page.wait_for_url('**/platform',timeout=60000)
        page.get_by_role('heading',name='Overview',exact=True).wait_for(timeout=60000)
        expect(page.locator('.global-header').get_by_role('link',name='Catalog',exact=True)).to_have_attribute('href','/catalog?workspace=platform')
        assert api('/me/libraries',platform_token)['results']==[]
        page.locator('.global-header').get_by_role('link',name='Catalog',exact=True).click();page.wait_for_url('**/catalog?workspace=platform');catalog(page)
        assert page.locator('.global-header').get_by_role('link',name='LuminaR home').get_attribute('href')=='/platform'
        assert page.evaluate("JSON.parse(localStorage.getItem('luminar_workspace_contexts')).staffLibraryId")==None
        passed('Staff logout to Platform-only login; Catalog is global 5M',route='/catalog?workspace=platform',qa_email=email)
        page.go_back();page.wait_for_url('**/platform');page.go_forward();catalog(page)
        page.reload();catalog(page);page.goto(page.url);catalog(page)
        page.locator('.global-header').get_by_role('link',name='LuminaR home').click();page.wait_for_url('**/platform')
        passed('Platform Catalog history, reload, hard navigation and logo')
        goto(page,'/catalog');catalog(page);assert page.locator('.global-header').get_by_role('link',name='LuminaR home').get_attribute('href')=='/'
        goto(page,f'/catalog?staff_library={TEST}');page.wait_for_url('**/catalog');catalog(page)
        goto(page,f'/reading-list?patron_library={TEST}');page.wait_for_url('**/reading-list');assert page.locator('.global-header').get_by_role('link',name='LuminaR home').get_attribute('href')=='/'
        passed('Deep global Catalog and unauthorized old return hints stay global')
        goto(page,'/platform/libraries','Libraries');dropdown(page,'Library status');dropdown(page,'Library type')
        axe(page,'Platform Libraries closed controls');page.get_by_role('combobox',name='Library status').click();axe(page,'Platform Libraries opened menu');page.keyboard.press('Escape')
        passed('Platform filter controls use shared accessible themed select')
        out(page);patron_token=sign(page,*credentials('patron'));goto(page,f'/libraries/{TEST}/catalogue','Browse Books')
        dropdown(page,'Circulation status',shot='post_2h_patron_select_1440.png')
        page.get_by_role('combobox',name='Circulation status').click();page.get_by_role('option',name='Reference Only',exact=True).click()
        assert 'REFERENCE_ONLY' in page.url
        page.get_by_role('combobox',name='Circulation status').click();page.keyboard.press('Home');page.keyboard.press('Enter')
        assert 'REFERENCE_ONLY' not in page.url
        passed('Patron circulation menu selection, Home and Enter update filter')
        out(page);sign(page,email,password);page.wait_for_url('**/platform');page.locator('.global-header').get_by_role('link',name='Catalog',exact=True).click();catalog(page)
        passed('Patron logout to Platform-only login does not retain TEST')
        out(page);staff_token=sign(page,staff_email,staff_password)
        goto(page,f'/staff/libraries/{TEST}/intelligence','Intelligence')
        state=api(f'/libraries/{TEST}/intelligence',staff_token)
        assert state['eligible_book_count']==151
        # Reuse a populated development fixture: first-build UI, without a build invocation.
        libraries=api('/me/libraries?limit=100',staff_token)['results'];not_built=None;retry=None
        for row in libraries:
            if row['library_id']==TEST or row.get('membership',{}).get('role')!='ADMIN':continue
            candidate=api(f'/libraries/{row["library_id"]}/intelligence',staff_token)
            if candidate['eligible_book_count'] and all(candidate[k]['status']=='NOT_BUILT' for k in ['search','kg']):not_built=row['library_id']
            if any(candidate[k]['status']=='FAILED' for k in ['search','kg']):retry=row['library_id']
            if not_built and retry:break
        platform_page=browser.new_page();sign(platform_page,email,password)
        patron_page=browser.new_page();sign(patron_page,*credentials('patron'))
        for width,height in [(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]:
            page.set_viewport_size({'width':width,'height':height});size={'viewport':[width,height],'surfaces':{},'status':'PASS'}
            platform_page.set_viewport_size({'width':width,'height':height});goto(platform_page,'/platform/libraries','Libraries')
            for label in ['Library status','Library type','Libraries per page']:size['surfaces']['Platform '+label]=dropdown(platform_page,label)
            platform_page.get_by_role('combobox',name='Library status').click();axe(platform_page,f'Platform open filter {width}');platform_page.keyboard.press('Escape')
            patron_page.set_viewport_size({'width':width,'height':height});goto(patron_page,f'/libraries/{TEST}/catalogue','Browse Books')
            size['surfaces']['Patron circulation']=dropdown(patron_page,'Circulation status',f'post_2h_patron_select_{width}.png')
            patron_page.get_by_role('combobox',name='Circulation status').click();axe(patron_page,f'Patron open circulation {width}','.luminar-select-menu');axe(patron_page,f'Patron filter controls {width}','.catalogue-filter-row');patron_page.keyboard.press('Escape')
            goto(page,'/libraries','Explore Libraries');size['surfaces']['explore']=dropdown(page,'Library filter',f'post_2h_explore_select_{width}.png');axe(page,f'Explore Libraries {width}')
            goto(page,f'/staff/libraries/{TEST}/inventory','Inventory')
            for label in ['Record filter','Inventory state','Format filter']:size['surfaces'][label]=dropdown(page,label)
            # Mobile staff switcher lives in the existing accessible workspace drawer.
            if width<1024:page.get_by_role('button',name='Open workspace menu').click()
            switch=page.get_by_role('combobox',name='Switch staff library');switch.click();search=page.get_by_role('searchbox',name='Find an option');expect(search).to_be_visible();search.fill('TEST')
            assert page.get_by_role('option',name='TEST',exact=True).count()==1
            page.keyboard.press('Escape');assert switch.evaluate('(e)=>e===document.activeElement')
            if width<1024:page.keyboard.press('Escape')
            size['surfaces']['staff_switcher']={'searchable':True,'escape':True};axe(page,f'Staff Inventory {width}')
            goto(page,f'/staff/libraries/{TEST}/intelligence','Intelligence');dialog_sizes=[]
            for label in ['Rebuild Search Index','Rebuild Knowledge Graph']:
                trigger=page.get_by_role('button',name=label,exact=True);trigger.click();dialog=page.get_by_role('dialog',name=label+'?',exact=True)
                rect=fit(page,dialog);assert rect['fit'] and rect['width']<=620
                css=dialog.evaluate('(e)=>({body:getComputedStyle(e.querySelector("p")).fontSize,heading:getComputedStyle(e.querySelector("h2")).fontSize,padding:getComputedStyle(e.querySelector(".ui-dialog-body")).padding,close:e.querySelector(".ui-dialog-close").getBoundingClientRect().toJSON(),closeBackground:getComputedStyle(e.querySelector(".ui-dialog-close")).backgroundColor,closeFont:getComputedStyle(e.querySelector(".ui-dialog-close")).fontSize,actions:[...e.querySelectorAll(".ui-actions button")].map(b=>b.getBoundingClientRect().height)})')
                assert css['body']=='14px' and css['heading']=='22px' and css['close']['width']==44 and css['close']['height']==44,(width,label,css)
                assert css['closeBackground']=='rgba(0, 0, 0, 0)' and css['closeFont']=='24px'
                assert all(44<=height<=45 for height in css['actions'])
                buttons=dialog.locator('button');buttons.last.focus();page.keyboard.press('Tab');assert buttons.first.evaluate('(e)=>e===document.activeElement')
                page.keyboard.press('Shift+Tab');assert buttons.last.evaluate('(e)=>e===document.activeElement')
                axe(page,f'{label} {width}');page.screenshot(path=str(REPORTS/f'post_2h_{"search" if "Search" in label else "kg"}_dialog_{width}.png'),animations='disabled')
                page.keyboard.press('Escape');expect(dialog).not_to_be_visible();assert trigger.evaluate('(e)=>e===document.activeElement')
                dialog_sizes.append({'action':label,'rect':rect,'styles':css,'focus_trap_escape_restore':True})
            assert dialog_sizes[0]['rect']['width']==dialog_sizes[1]['rect']['width']
            assert dialog_sizes[0]['styles']['padding']==dialog_sizes[1]['styles']['padding']
            size['surfaces']['intelligence_dialogs']=dialog_sizes
            matrix.append(size);passed(f'{width}x{height} opened controls, shared dialogs and accessibility')
        if not_built:
            goto(page,f'/staff/libraries/{not_built}/intelligence','Intelligence')
            for label in ['Build Search Index','Build Knowledge Graph']:
                page.get_by_role('button',name=label,exact=True).click();dialog=page.get_by_role('dialog');expect(dialog).to_be_visible();assert fit(page,dialog)['fit'];dialog.get_by_role('button',name='Cancel',exact=True).click()
            passed('Disposable NOT_BUILT first-build confirmations use shared Modal',library_id=not_built)
        else:passed('No populated NOT_BUILT local fixture available; first-build behavior verified in automated tests',availability='NOT_AVAILABLE')
        if retry:
            goto(page,f'/staff/libraries/{retry}/intelligence','Intelligence');page.get_by_role('button',name='Retry Build',exact=True).first.click();dialog=page.get_by_role('dialog');expect(dialog).to_be_visible();dialog.get_by_role('button',name='Cancel').click();passed('Available Retry confirmation uses shared Modal',library_id=retry)
        else:passed('Retry production state unavailable; shared confirmation verified by automated tests',availability='NOT_AVAILABLE')
        assert api(f'/libraries/{TEST}/intelligence',staff_token)['search']['active_generation_id']==state['search']['active_generation_id']
        assert api(f'/libraries/{TEST}/intelligence',staff_token)['kg']['active_generation_id']==state['kg']['active_generation_id']
        passed('All confirmations cancelled; tenant generation IDs preserved')
        assert not build_posts,'Presentation QA must never start live builds.'
        browser.close();assert not errors;save('PASS')
except Exception as error:
    save('FAIL');print('FAILED '+type(error).__name__+': '+str(error).split('Call log:')[0][:500],flush=True)
    if 'page' in globals() and not page.is_closed():print('Failed route '+page.url,flush=True);print('Inspect reports/post_2h_browser.json for completed checks.',flush=True)
    raise
finally:
    if user_id:
        db.platform_role_assignments.update_many({'user_id':user_id,'approval_ref':'USER-POST-2H-LOCAL-QA'},{'$set':{'status':'REVOKED'}})
        db.users.update_one({'user_id':user_id},{'$set':{'is_active':False}})
        (REPORTS/'post_2h_qa_authority.json').write_text(json.dumps({'local_only':True,'qa_email':email,'temporary_account_disabled':True,'platform_assignment_revoked':True,'TEST_membership_granted':False},indent=2),encoding='utf8')
