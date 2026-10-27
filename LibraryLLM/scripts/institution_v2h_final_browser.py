"""Final running-stack smoke and actual logout during a durable queued job."""
import sys,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
source=(ROOT/'scripts/institution_v2h_browser.py').read_text(encoding='utf8')
exec(source.split("assert db.name=='luminar_library'")[0],globals())
prior=json.loads((REPORTS/'institution_v2h_browser.json').read_text());checks=prior['checks'];matrix=prior['responsive']
fixture=json.loads((REPORTS/'institution_v2h_fixtures.json').read_text())['disposable_library_id']
def waitstack():
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        try:
            if all(requests.get(f'http://127.0.0.1:{port}/health',timeout=3).ok for port in [8002,8003,8005]) and requests.get('http://127.0.0.1:8004/docs',timeout=3).ok:return
        except requests.RequestException:pass
        time.sleep(1)
    raise RuntimeError('Local stack did not become ready')
def restart_search():subprocess.run(['powershell','-NoProfile','-File',str(ROOT/'.scratch/institution-v2g/start_stack.ps1')],cwd=ROOT,check=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
waitstack()
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
    patron_token=sign(page,*credentials('patron'))
    for route in ['/', '/catalog', '/search?q=computer%20networks', '/libraries/'+TEST, '/libraries/'+TEST+'/catalogue?search=computer%20networks', '/libraries/'+TEST+'/graph', '/libraries/'+TEST+'/resources', '/account/libraries', '/llm']:
        page.goto(BASE+route);page.locator('#main-content, .llm-page, .llm-layout').first.wait_for(timeout=60000) if route!='/llm' else page.get_by_role('link',name='LuminaR home',exact=True).wait_for(timeout=60000)
        page.wait_for_timeout(500);assert not page.get_by_text('Page not found',exact=True).count()
        if '/catalogue?search=' in route:page.get_by_text('Library semantic search',exact=True).wait_for(timeout=60000)
        if route.endswith('/graph'):page.locator('[data-graph-source=TENANT_KG]').wait_for(timeout=60000)
    page.goto(BASE+'/libraries/'+TEST);page.get_by_role('link',name='My reading list',exact=True).click();page.wait_for_url('**/reading-list?patron_library='+TEST)
    page.get_by_role('link',name='LuminaR home',exact=True).click();page.wait_for_url('**/libraries/'+TEST)
    passed('Karthikeya Patron, Global product, Search, Graph, Resources and Reading List context smoke')
    context.close();context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page();token=sign(page,*credentials('staff'))
    for section in ['inventory','circulation','reservations','fees','events','analytics','assets','members','activity','settings','audit','intelligence']:
        page.goto(BASE+f'/staff/libraries/{TEST}/{section}');page.locator('#main-content').wait_for(timeout=60000);page.wait_for_timeout(300)
        assert not page.get_by_text('Page not found',exact=True).count()
    ready(page,TEST);page.get_by_role('link',name='My reading list',exact=True).click();page.wait_for_url('**/reading-list?staff_library='+TEST)
    page.get_by_role('link',name='LuminaR home',exact=True).click();page.wait_for_url('**/staff/libraries/'+TEST)
    activity=api(f'/libraries/{TEST}/staff/activity?limit=100',token)
    assert any(r['event'].startswith('SEARCH_INDEX_BUILD_') and (r.get('actor') or {}).get('email') for r in activity['results'])
    passed('TEST Staff surfaces, Intelligence navigation, personal return context and hydrated build activity')
    assert db.institution_intelligence_jobs.count_documents({'effective_active':True,'state':{'$in':['QUEUED','RUNNING','VALIDATING','PUBLISHING']}})==0
    pause_command="$listener=Get-NetTCPConnection -State Listen -LocalPort 8003; $serviceProcess=Get-CimInstance Win32_Process -Filter ('ProcessId='+$listener.OwningProcess); if($serviceProcess.CommandLine -notmatch 'search.api'){throw 'Unexpected process'}; Stop-Process -Id $listener.OwningProcess"
    subprocess.run(['powershell','-NoProfile','-Command',pause_command],check=True)
    try:
        ready(page,fixture);clickbuild(page,'Rebuild Search Index');queued=api(f'/libraries/{fixture}/intelligence',token)['search']['current_job'];assert queued['state']=='QUEUED'
        page.get_by_role('button',name=__import__('re').compile('^Open account menu')).click();page.get_by_role('menuitem',name='Sign Out',exact=True).click();page.wait_for_url('**/login',timeout=60000)
        assert db.institution_intelligence_jobs.find_one({'job_id':queued['job_id']})['state']=='QUEUED'
        api(f'/libraries/{fixture}/intelligence',token,expected=401)
        token=sign(page,*credentials('staff'));ready(page,fixture)
        assert api(f'/libraries/{fixture}/intelligence',token)['search']['current_job']['job_id']==queued['job_id']
    finally:restart_search()
    waitstack();state=waitready(page,fixture,token,'search');passed('Actual Sign Out revokes session but preserves queued build; re-login and resident worker finish it',job_id=queued['job_id'],generation=state['search']['active_generation_id'])
    # Disable only local review accounts created by this phase, including an
    # abandoned unverified registration from the initial normalized-email check.
    for user in db.users.find({'name':{'$regex':'^Part 2H '},'email':{'$regex':'^v2h-'}},{'user_id':1}):
        db.users.update_one({'user_id':user['user_id']},{'$set':{'is_active':False}})
        db.platform_role_assignments.update_many({'user_id':user['user_id'],'approval_ref':'USER-PART-2H-ISOLATED-QA'},{'$set':{'status':'REVOKED'}})
    current=api(f'/libraries/{TEST}/intelligence',token);assert current['search']['status']==current['kg']['status']=='READY'
    runtime={str(port):requests.get(f'http://127.0.0.1:{port}/health' if port!=8004 else 'http://127.0.0.1:8004/docs',timeout=30).status_code for port in [8002,8003,8004,8005]}
    assert all(value==200 for value in runtime.values())
    put('final_browser',{'status':'PASS','runtime':runtime,'logout_durable_job':queued['job_id'],'TEST':current,'errors':errors,'temporary_grants_remaining':db.platform_role_assignments.count_documents({'approval_ref':'USER-PART-2H-ISOLATED-QA','status':'ACTIVE'})})
    put('browser',{**prior,'status':'PASS','browser':browser.version,'checks':checks,'errors':errors,'runtime':runtime})
    browser.close()

