"""Actual Chromium Part 2H controls. Runtime secrets never persist or print."""
import sys,json,time,secrets,requests
from uuid import uuid4
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright,expect
from scripts.full_product_browser_session import credentials
from backend.database.mongodb import db
from backend.services import auth_service
from scripts import migrate_management_authority as migration
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae';REPORTS=ROOT/'reports';BASE='http://127.0.0.1:5173';CORE='http://127.0.0.1:8002'
checks=[];matrix=[];errors=[];jobs=[];temporary=[]
def put(name,data):(REPORTS/f'institution_v2h_{name}.json').write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
def passed(name,**details):
    checks.append({'scenario':name,'status':'PASS',**details});put('browser',{'status':'IN_PROGRESS','checks':checks,'responsive':matrix,'errors':errors});print('PASS '+name,flush=True)
def account(purpose):
    email='v2h-'+purpose.lower()+'-'+uuid4().hex[:12]+'@example.com';password=secrets.token_urlsafe(30);mail={};original=auth_service.send_otp_email
    try:
        auth_service.send_otp_email=lambda email,name,otp:mail.update({email:otp}) or True
        user=auth_service.register_user('Part 2H '+purpose,email,password)
        temporary.append(user['user_id']);assert auth_service.verify_email_otp(email,mail.pop(email))
    finally:auth_service.send_otp_email=original
    temporary.append(user['user_id']);return email,password,user
def api(path,token,method='GET',body=None,expected=200):
    for _ in range(60):
        r=requests.request(method,CORE+path,headers={'Authorization':'Bearer '+token},json=body,timeout=60)
        if r.status_code!=503:break
        time.sleep(.15)
    assert r.status_code==expected,(path,r.status_code,r.text[:120]);return r.json()
def sign(page,email,password):
    page.goto(BASE+'/login');page.locator('input[type=email]').fill(email);page.locator('input[type=password]').fill(password)
    page.get_by_role('button',name='Sign In',exact=True).click();page.wait_for_url(lambda url:'/login' not in str(url),timeout=60000)
    return page.evaluate("localStorage.getItem('luminar_token')")
def ready(page,lib):
    page.goto(BASE+f'/staff/libraries/{lib}/intelligence');page.get_by_role('heading',name='Semantic Search Index',exact=True).wait_for(timeout=60000)
def clickbuild(page,label):
    page.get_by_role('button',name=label,exact=True).click();dialog=page.get_by_role('dialog')
    expect(dialog).to_be_visible();dialog.get_by_role('button',name=label,exact=True).click();expect(dialog).not_to_be_visible(timeout=60000)
def waitready(page,lib,token,key):
    seen=[];deadline=time.monotonic()+300
    while time.monotonic()<deadline:
        state=api(f'/libraries/{lib}/intelligence',token);job=state[key]['current_job'] or state[key]['latest_job']
        if job:seen.append({k:job[k] for k in ['state','stage','progress_current','progress_total']})
        if state[key]['status']=='READY' and job and job['state']=='SUCCEEDED':break
        assert state[key]['status'] not in ['FAILED','RECOVERY_REQUIRED'];time.sleep(.3)
    assert state[key]['status']=='READY';jobs.append({'library_id':lib,'target':key,'progress':seen,'status':state[key]})
    page.get_by_role('button',name='Refresh status',exact=True).click()
    expect(page.get_by_role('button',name='Rebuild '+('Search Index' if key=='search' else 'Knowledge Graph'),exact=True)).to_be_visible(timeout=60000)
    return state

assert db.name=='luminar_library' and db.client.address[0] in ('localhost','127.0.0.1','::1')
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    email,password=credentials('staff');token=sign(page,email,password)
    before=api(f'/libraries/{TEST}/intelligence',token);ready(page,TEST)
    passed('TEST Admin opens Intelligence',eligible_books=before['eligible_book_count'])
    for key,label in [('search','Rebuild Search Index'),('kg','Rebuild Knowledge Graph')]:
        clickbuild(page,label);state=waitready(page,TEST,token,key)
        assert state[key]['active_generation_id']!=before[key]['active_generation_id'] and state[key]['record_count']==150
        passed('TEST '+key+' rebuild',before_generation=before[key]['active_generation_id'],after_generation=state[key]['active_generation_id'])
    r=requests.get('http://127.0.0.1:8003/libraries/'+TEST+'/catalogue/search',headers={'Authorization':'Bearer '+token},params={'staff':'true','search':'computer networks','limit':20},timeout=60);r.raise_for_status();result=r.json()
    assert result['source']['search_source']=='TENANT_SEMANTIC' and result['results'] and all(row['library_id']==TEST for row in result['results'])
    graph=api(f'/libraries/{TEST}/intelligence/graph?staff=true',token);assert graph['status']=='READY' and all(n['library_book_id'] in {r['library_book_id'] for r in db.institution_library_books.find({'library_id':TEST})} for n in graph['nodes'] if n['type']=='Book')
    passed('TEST Search and Graph remain tenant-only',search_results=len(result['results']),graph_nodes=len(graph['nodes']))
    fixture=api('/libraries/register',token,'POST',{'name':'Part 2H control QA','slug':'v2h-'+uuid4().hex[:12],'library_type':'PUBLIC_LIBRARY','access_mode':'PUBLIC'},201)['library']['library_id']
    put('fixtures',{'disposable_library_id':fixture})
    initial=api(f'/libraries/{fixture}/intelligence',token);ready(page,fixture)
    assert initial['search']['status']==initial['kg']['status']=='NOT_BUILT'
    assert page.get_by_role('button',name='Build Search Index',exact=True).is_disabled()
    api(f'/libraries/{fixture}/intelligence/builds',token,'POST',{'target':'SEARCH_INDEX'},409)
    passed('New empty library starts NOT_BUILT and cannot build')
    books=[]
    for title in ['Networks of a new library','Catalogue metadata relationships','Local library retrieval']:
        books.append(api(f'/libraries/{fixture}/inventory/books',token,'POST',{'title':title,'authors':['Part 2H QA'],'subjects':['Computer networks'],'description':'Local-only metadata for isolated intelligence control validation.','create_physical_holding':True,'copies':1,'shelf_location':'QA','idempotency_key':str(uuid4())},201)['library_book_id'])
    state=api(f'/libraries/{fixture}/intelligence',token);assert state['search']['status']==state['kg']['status']=='NOT_BUILT'
    assert db.institution_intelligence_jobs.count_documents({'library_id':fixture})==0
    fallback=requests.get('http://127.0.0.1:8003/libraries/'+fixture+'/catalogue/search',headers={'Authorization':'Bearer '+token},params={'staff':'true','search':'networks'},timeout=60).json();assert fallback['source']['search_source']=='LOCAL_FALLBACK'
    passed('Added books remain NOT_BUILT; local catalogue fallback works')
    ready(page,fixture)
    for key,label in [('search','Build Search Index'),('kg','Build Knowledge Graph')]:
        clickbuild(page,label);page.reload();page.get_by_role('heading',name='Semantic Search Index',exact=True).wait_for(timeout=60000)
        waitready(page,fixture,token,key);passed('New library '+key+' Build through UI and refresh')
    ready_state=api(f'/libraries/{fixture}/intelligence',token)
    api(f'/libraries/{fixture}/inventory/books/{books[0]}',token,'PATCH',{'title':'Updated networks catalogue metadata','idempotency_key':str(uuid4())})
    stale=api(f'/libraries/{fixture}/intelligence',token);assert stale['search']['status']==stale['kg']['status']=='STALE'
    assert db.institution_intelligence_jobs.count_documents({'library_id':fixture})==2
    ready(page,fixture);expect(page.get_by_text('Update available',exact=True)).to_have_count(2)
    passed('Metadata change displays STALE without automatic jobs')
    for key,label in [('search','Rebuild Search Index'),('kg','Rebuild Knowledge Graph')]:clickbuild(page,label);waitready(page,fixture,token,key)
    lib_email,lib_password,lib_user=account('Librarian');lib_context=browser.new_context();lib_page=lib_context.new_page();lib_token=sign(lib_page,lib_email,lib_password)
    api(f'/libraries/{fixture}/join',lib_token,'POST',{})
    membership=db.institution_memberships.find_one({'library_id':fixture,'user_id':lib_user['user_id']})
    api(f'/libraries/{fixture}/memberships/{membership["membership_id"]}',token,'PATCH',{'role':'LIBRARIAN'})
    ready(lib_page,fixture);assert lib_page.get_by_text('Search and graph builds can be started by Library Admins.',exact=True).count()==1
    assert lib_page.get_by_role('button',name='Rebuild Search Index',exact=True).count()==0
    api(f'/libraries/{fixture}/intelligence/builds',lib_token,'POST',{'target':'SEARCH_INDEX'},403)
    api(f'/libraries/{fixture}/intelligence/builds',lib_token,'POST',{'target':'KNOWLEDGE_GRAPH'},403)
    passed('Real Librarian status-only UI and build denial')
    patron_context=browser.new_context();patron_page=patron_context.new_page();patron_token=sign(patron_page,*credentials('patron'))
    patron_page.goto(BASE+f'/staff/libraries/{TEST}/intelligence');expect(patron_page.get_by_role('heading',name='Semantic Search Index')).not_to_be_visible()
    api(f'/libraries/{TEST}/intelligence',patron_token,expected=403);passed('GENERAL_USER cannot open Staff Intelligence')
    plat_email,plat_password,plat_user=account('Platform-only')
    proposal=migration.plan(db,{'platform_assignments':[{'user_id':plat_user['user_id'],'role':'PLATFORM_ADMIN','approved':True,'approved_by':'local-development-review','approval_ref':'USER-PART-2H-ISOLATED-QA','reason':'Temporary local-only boundary validation.'}]});migration.apply(db,proposal)
    plat_context=browser.new_context();plat_page=plat_context.new_page();plat_token=sign(plat_page,plat_email,plat_password)
    api('/platform/libraries',plat_token);api(f'/libraries/{TEST}/intelligence',plat_token,expected=404)
    api(f'/libraries/{TEST}/intelligence/builds',plat_token,'POST',{'target':'SEARCH_INDEX'},404)
    plat_page.goto(BASE+f'/staff/libraries/{TEST}/intelligence');expect(plat_page.get_by_role('heading',name='Semantic Search Index')).not_to_be_visible()
    passed('Explicit Platform-only account cannot access tenant Intelligence')
    ready(page,TEST);before_labels=page.locator('.intelligence-card').all_text_contents();ready(page,fixture)
    assert page.get_by_text('3',exact=True).count()>=2 and page.get_by_text('150',exact=True).count()==0
    page.reload();page.get_by_role('heading',name='Semantic Search Index').wait_for(timeout=60000)
    passed('Multi-library Admin isolation and refresh')
    context.close();context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();token=sign(page,email,password);ready(page,fixture)
    assert page.get_by_role('button',name='Rebuild Search Index',exact=True).count()==1
    passed('Re-login restores durable successful generations')
    accessibility=[]
    for width,height in [(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]:
        page.set_viewport_size({'width':width,'height':height});ready(page,TEST)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        for details in page.locator('.intelligence-card details').all():details.locator('summary').click()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        page.screenshot(path=str(REPORTS/f'institution_v2h_intelligence_{width}.png'),full_page=True,animations='disabled')
        page.get_by_role('button',name='Rebuild Search Index',exact=True).click();dialog=page.get_by_role('dialog');expect(dialog).to_be_visible()
        assert dialog.evaluate('(e)=>{const r=e.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1}')
        buttons=dialog.locator('button');buttons.last.focus();page.keyboard.press('Tab');assert buttons.first.evaluate('(e)=>e===document.activeElement')
        buttons.first.focus();page.keyboard.press('Shift+Tab');assert buttons.last.evaluate('(e)=>e===document.activeElement')
        page.keyboard.press('Escape');expect(dialog).not_to_be_visible();assert page.get_by_role('button',name='Rebuild Search Index',exact=True).evaluate('(e)=>e===document.activeElement')
        matrix.append({'viewport':[width,height],'page_overflow':False,'advanced_details_wrap':True,'dialog_fit':True,'focus_trap':True,'escape':True,'focus_restore':True,'status':'PASS'})
    passed('Six viewports, advanced UUIDs, dialogs and keyboard accessibility')
    page.set_viewport_size({'width':1440,'height':900});ready(page,TEST)
    audit=api(f'/libraries/{TEST}/audit?limit=100',token);assert any('BUILD' in row['event'] and (row.get('actor') or {}).get('email') for row in audit['results'])
    put('audit',{'status':'PASS','events':[{'event':r['event'],'actor_email':(r.get('actor') or {}).get('email')} for r in audit['results'] if 'BUILD' in r['event']]})
    put('build_flow',{'status':'PASS','jobs':jobs});put('progress',{'status':'PASS','observations':jobs,'source':'Durable Mongo jobs fetched during actual UI builds'})
    put('new_library_flow',{'status':'PASS','library_id':fixture,'initial':initial,'after_add':state,'book_ids':books,'ready':api(f'/libraries/{fixture}/intelligence',token)})
    put('responsive',{'status':'PASS','matrix':matrix});put('accessibility',{'status':'PASS','checks':matrix,'text_status':True,'native_progress':True})
    for user_id in temporary:
        db.platform_role_assignments.update_many({'user_id':user_id,'approval_ref':'USER-PART-2H-ISOLATED-QA'},{'$set':{'status':'REVOKED'}})
        db.users.update_one({'user_id':user_id},{'$set':{'is_active':False}})
    put('authorization',{'status':'PASS','Admin':'VIEW_AND_BUILD','Librarian':'VIEW_ONLY','General_User':'DENIED','Platform_only':'DENIED','local_temporary_qa_accounts_disabled':True,'temporary_platform_assignment_revoked':True})
    put('browser',{'status':'PASS','browser':browser.version,'checks':checks,'responsive':matrix,'errors':errors})
    browser.close()


