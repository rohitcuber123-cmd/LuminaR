"""Evidence assertions executed in the live secret-free Part 2E browser session."""
import time
from scripts.institution_v2e_baseline import digest

checks = globals().get('checks', [])
security = globals().get('security', [])
geometry_rows = globals().get('geometry_rows', [])
axe_rows = globals().get('axe_rows', [])
contrast_rows = globals().get('contrast_rows', [])
timings = globals().get('timings', [])
SIZES = [(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]


def check(bucket, name, **values):
    bucket.append({'check': name, 'status': 'PASS', **values})
    print('PASS ' + name, flush=True)


def analytics_ready():
    page.locator('#analytics-snapshot-heading').wait_for(timeout=60000)
    page.evaluate('document.fonts.ready')


def domain_digest(identity):
    names = ['library_books','holdings','copies','lending_requests','loans','reservations','fees','fee_ledger','memberships','audit','lending_operations']
    return {name: digest(db['institution_'+name].find({'library_id': identity},{'_id':0})) for name in names} | {'events': digest(db.events.find({'library_id': identity},{'_id':0}))}


def assert_live_metrics():
    before = domain_digest(fixtures['A'])
    a = api(f'/libraries/{fixtures["A"]}/analytics')
    b = api(f'/libraries/{fixtures["B"]}/analytics', account='mixed')
    empty = api(f'/libraries/{fixtures["EMPTY"]}/analytics')
    expected = {'active_books':10,'active_loans':3,'pending_borrow_requests':2,'pending_return_requests':1,'active_reservations':4,'open_fee_balance_minor':'750','upcoming_events':2,'active_members':3}
    assert all(a['overview'][key] == value for key,value in expected.items()), a['overview']
    assert a['reservations']['waiting'] == 3 and a['reservations']['ready'] == 1
    assert a['fees']['assessed_minor'] == '1000' and a['fees']['payments_minor'] == '250'
    assert a['circulation']['renewals_in_range'] == 1
    assert a['circulation']['returns_confirmed_in_range'] == 1
    assert a['circulation']['rejected_in_range'] == 1
    assert a['collection']['globally_linked_books'] == 1 and a['collection']['local_only_books'] == 9
    assert a['events']['published_in_range'] == 3 and a['events']['cancelled_in_range'] == 1
    assert b['overview']['active_books'] == 4 and b['overview']['active_loans'] == 1
    assert all(empty['overview'][key] == 0 for key in ['active_books','active_loans','pending_borrow_requests','pending_return_requests','active_reservations','upcoming_events'])
    assert empty['overview']['open_fee_balance_minor'] == '0'
    linked_a = next(row for row in a['popular_books'] if row['global_work_id'] == 'OL19313623W')
    linked_b = next(row for row in b['popular_books'] if row['global_work_id'] == 'OL19313623W')
    assert linked_a['library_book_id'] != linked_b['library_book_id']
    assert domain_digest(fixtures['A']) == before
    for name,data in [('A',a),('B',b),('EMPTY',empty)]:
        put('institution_v2e_live_analytics_'+name+'.json',data)
    check(checks,'Exact canonical A/B/empty fixture metrics, shared work isolation and read-only data',expected_A=expected)


def admin_browser():
    login('staff'); started=time.perf_counter();goto(f'/staff/libraries/{TEST}/analytics');analytics_ready()
    timings.append({'surface':'TEST full Analytics initial load','ms':round((time.perf_counter()-started)*1000,2)})
    assert page.locator('.analytics-snapshot-grid > div').filter(has=page.get_by_text('Active local books',exact=True)).locator('dd').inner_text()=='150'
    assert page.locator('.global-logo').get_attribute('href') == '/staff/libraries/'+TEST
    assert page.get_by_role('heading',name='Notification delivery health',exact=True).is_visible()
    check(checks,'TEST Owner/Admin Analytics shows 150 local books and Staff Home',home='/staff/libraries/'+TEST)
    shot('test_admin_analytics_1440')
    selector=page.locator('#analytics-range')
    for value in ['7d','90d','all','30d']:
        with page.expect_response(lambda response:'/analytics?range='+value in response.url and response.request.method=='GET') as result:
            selector.select_option(value)
        assert result.value.status==200
        analytics_ready(); assert result.value.json()['range']['key']==value
    selector.focus();page.keyboard.press('Home');page.keyboard.press('ArrowDown');page.keyboard.press('Enter');analytics_ready()
    focus=selector.evaluate('(e)=>({style:getComputedStyle(e).outlineStyle,width:getComputedStyle(e).outlineWidth})')
    assert focus['style']!='none' and float(focus['width'].removesuffix('px'))>=2
    check(checks,'Range switching and keyboard visible focus',focus=focus)
    selector.select_option('30d');analytics_ready()
    page.locator('#analytics-series').select_option('acquisitions')
    page.get_by_role('table').filter(has=page.get_by_text('Acquisitions by UTC day',exact=True)).wait_for()
    check(checks,'Persisted activity chart has semantic table equivalent')
    login('owner');goto(f'/staff/libraries/{fixtures["A"]}/analytics');analytics_ready()
    assert page.locator('.analytics-snapshot-grid > div').filter(has=page.get_by_text('Open fee balance',exact=True)).locator('dd').inner_text()=='INR 7.50'
    assert page.get_by_role('heading',name='Popular books',exact=True).is_visible()
    check(checks,'Rich fixture Analytics renders exact currency and book aggregates')
    shot('fixture_admin_analytics_1440')
    goto(f'/staff/libraries/{fixtures["EMPTY"]}/analytics');analytics_ready()
    assert page.get_by_text('No active books in this library',exact=True).is_visible()
    check(checks,'Empty canonical Analytics renders zero state')
    shot('empty_analytics_1440')
    login('mixed');goto(f'/staff/libraries/{fixtures["C"]}/analytics');analytics_ready()
    assert page.get_by_role('heading',name='Notification delivery health',exact=True).count()==0
    assert page.get_by_text('Waived amount in range',exact=True).count()==0
    c=api(f'/libraries/{fixtures["C"]}/analytics',account='mixed')
    assert c['membership_role']=='LIBRARIAN' and c['membership']['role_counts'] is None and c['outbox'] is None
    check(checks,'Librarian operational Analytics excludes ADMIN-only details')
    # Use the accepted switcher rather than inventing a frontend active library.
    switcher=page.locator('.workspace-sidebar select').first
    if switcher.count():
        switcher.select_option(fixtures['B']);page.wait_for_url(lambda value: urlparse(str(value)).path.startswith('/staff/libraries/'+fixtures['B']),timeout=60000)
    else:
        goto(f'/staff/libraries/{fixtures["B"]}/analytics')
    if '/analytics' not in page.url:
        page.locator('.workspace-sidebar').get_by_role('link',name='Analytics',exact=True).click()
    analytics_ready()
    assert page.locator('.analytics-snapshot-grid > div').filter(has=page.get_by_text('Active local books',exact=True)).locator('dd').inner_text()=='4'
    assert 'Part 2E QA Library B' in page.locator('.workspace-identity').inner_text()
    check(checks,'Library switch refreshes Analytics to B without C data')


def security_browser():
    for account,identity in [('mixed',fixtures['A']),('owner',fixtures['B']),('platform',TEST)]:
        denied=api(f'/libraries/{identity}/analytics',account=account,expected=403 if account=='mixed' else 404)
        assert denied
    check(security,'GENERAL_USER, cross-library ADMIN and Platform-only API denied')
    login('patron');goto('/staff/libraries/'+TEST+'/analytics')
    page.wait_for_function("!location.pathname.endsWith('/analytics') || !!document.querySelector('.ui-state:not(.ui-state-loading)')",timeout=60000)
    assert page.locator('#analytics-snapshot-heading').count()==0
    assert page.locator('.workspace-sidebar').get_by_role('link',name='Analytics',exact=True).count()==0
    check(security,'TEST GENERAL_USER direct Staff Analytics route denied')
    login('platform');goto('/staff/libraries/'+TEST+'/analytics')
    page.wait_for_function("!location.pathname.endsWith('/analytics') || !!document.querySelector('.ui-state:not(.ui-state-loading)')",timeout=60000)
    assert page.locator('#analytics-snapshot-heading').count()==0
    check(security,'Platform-only browser has no TEST Analytics access')
    login('mixed');goto(f'/staff/libraries/{fixtures["C"]}/analytics');analytics_ready()
    member=db.institution_memberships.find_one({'library_id':fixtures['C'],'user_id':accounts['mixed']['user_id']})
    api(f'/libraries/{fixtures["C"]}/memberships/{member["membership_id"]}','PATCH',{'status':'SUSPENDED'},'owner')
    assert api(f'/libraries/{fixtures["C"]}/analytics',account='mixed',expected=404)
    page.get_by_role('button',name='Refresh analytics',exact=True).click()
    page.get_by_text('Unable to load analytics',exact=True).wait_for(timeout=60000)
    assert page.locator('#analytics-snapshot-heading').count()==0
    api(f'/libraries/{fixtures["C"]}/memberships/{member["membership_id"]}','PATCH',{'status':'ACTIVE'},'owner')
    check(security,'Same JWT loses Analytics immediately after membership revocation')
    before=domain_digest(fixtures['A'])
    for action,state,previous in [('suspend','SUSPENDED','ACTIVE'),('restore','ACTIVE','SUSPENDED'),('remove','REMOVED','ACTIVE'),('restore','ACTIVE','REMOVED')]:
        api(f'/platform/libraries/{fixtures["A"]}/{action}','POST',cmd(reason='Local Part 2E lifecycle boundary QA',expected_status=previous),'platform')
        assert api(f'/libraries/{fixtures["A"]}/analytics',expected=200 if state=='ACTIVE' else 404)
    # Platform lifecycle adds its own audit only; tenant data must be retained.
    assert domain_digest(fixtures['A'])==before
    check(security,'Suspended/removed Analytics denied and restores retain tenant data')
    put('institution_v2e_security.json',{'status':'PASS','live_checks':security,'backend_suite':'institution_v2e_tests.xml'})


def measure_analytics(name,size):
    analytics_ready()
    geometry=page.evaluate("""() => {
      const visible=e=>e.getClientRects().length>0,box=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,width:r.width,height:r.height}};
      return {width:innerWidth,document_width:document.documentElement.scrollWidth,fields:[...document.querySelectorAll('.library-analytics select,.library-analytics button')].filter(visible).map(e=>({name:e.id||e.textContent.trim(),...box(e)})),cards:[...document.querySelectorAll('.analytics-snapshot-grid > div')].map(box),tables:[...document.querySelectorAll('.library-analytics table')].map(e=>({width:e.clientWidth,scrollWidth:e.scrollWidth,...box(e)}))};
    }""")
    assert geometry['document_width']<=size[0]+1
    assert all(e['x']>=0 and e['right']<=size[0]+1 and e['height']>=43.5 for e in geometry['fields'])
    assert all(e['x']>=0 and e['right']<=size[0]+1 for e in geometry['cards']+geometry['tables'])
    # Scroll each analytics action into the actual viewport and hit-test the
    # center against the Assistant launcher, without submitting an action.
    actions=page.locator('.library-analytics button,.library-analytics select')
    for i in range(actions.count()):
        control=actions.nth(i);control.scroll_into_view_if_needed()
        assert control.evaluate('(e)=>{const r=e.getBoundingClientRect(),h=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return h===e||e.contains(h)}')
    page.add_script_tag(path=str(ROOT/'frontend/node_modules/axe-core/axe.min.js'))
    result=page.evaluate("""async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return {violations:r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),passes:r.passes.length}}""")
    assert not result['violations'],result
    geometry_rows.append({'surface':name,'viewport':list(size),'status':'PASS','geometry':geometry})
    axe_rows.append({'surface':name,'viewport':list(size),**result})
    if size[0] in [1440,375]:
        page.evaluate('window.scrollTo(0,0)');shot(name.lower().replace(' ','_')+'_'+str(size[0]))
    print('MEASURED',name,size,flush=True)


def responsive(account,name,identity):
    login(account)
    for size in SIZES:
        page.set_viewport_size({'width':size[0],'height':size[1]});goto(f'/staff/libraries/{identity}/analytics');measure_analytics(name,size)
    put('institution_v2e_responsive.json',{'status':'PASS' if len(geometry_rows)==24 else 'IN_PROGRESS','checks':geometry_rows})
    put('institution_v2e_accessibility.json',{'status':'PASS' if len(axe_rows)==24 else 'IN_PROGRESS','audits':axe_rows,'keyboard':'Range selector visible focus; semantic tables expose all chart values; responsive control height and Assistant center hit-tests.'})


def benchmark_live():
    for account,identity,name in [('owner',fixtures['EMPTY'],'Empty library'),('owner',fixtures['A'],'Known operational fixture')]:
        samples=[]
        for _ in range(5):
            start=time.perf_counter();value=api(f'/libraries/{identity}/analytics',account=account);samples.append(round((time.perf_counter()-start)*1000,2))
        timings.append({'surface':name+' combined API','samples_ms':samples,'max_ms':max(samples),'response_bytes':len(json.dumps(value))})
    email,password=credentials('staff')
    reply=requests.post('http://127.0.0.1:8002/auth/login',json={'email':email,'password':password},timeout=30)
    assert reply.status_code==200
    headers={'Authorization':'Bearer '+reply.json()['access_token']}
    samples=[]
    for _ in range(5):
        start=time.perf_counter();reply=requests.get('http://127.0.0.1:8002/libraries/'+TEST+'/analytics',headers=headers,timeout=30);assert reply.status_code==200;samples.append(round((time.perf_counter()-start)*1000,2))
    timings.append({'surface':'TEST combined API','samples_ms':samples,'max_ms':max(samples),'response_bytes':len(reply.content)})
    put('institution_v2e_live_performance.json',{'status':'PASS','local_measurements':timings,'scope':'Local development response timings, not a production load guarantee.'})


def component_benchmarks():
    from backend.services import library_analytics_service as service
    measurements=[]
    for identity,name in [(fixtures['EMPTY'],'Empty library'),(TEST,'TEST 150 books')]:
        window=service.span('30d',datetime.now(timezone.utc))
        for label,action in [('collection',lambda:service.collection_metrics(identity,window,True)),
                             ('circulation',lambda:service.circulation_metrics(identity,{},True))]:
            samples=[]
            for _ in range(3):
                started=time.perf_counter();action();samples.append(round((time.perf_counter()-started)*1000,3))
            measurements.append({'library':name,'component':label,'samples_ms':samples})
    put('institution_v2e_component_performance.json',{'status':'PASS','measurements':measurements,'overview':'Overview is part of the one combined Analytics request; use measured combined endpoint time, not a fabricated independent endpoint.'})


def analytics_manual():
    # The accepted product-matrix helpers supply real Tab navigation and a
    # composited rendered-style contrast sampler. No analytics mutation occurs.
    login('staff');keyboard=[];manual=[]
    source=(ROOT/'scripts/institution_v2d_browser_checks.py').read_text(encoding='utf8')
    exec(source[source.index('def contrast_nodes('):source.index('\ndef performance_and_cleanup(')],globals())
    for size in [SIZES[0],SIZES[-1]]:
        page.set_viewport_size({'width':size[0],'height':size[1]})
        goto('/staff/libraries/'+TEST+'/analytics');analytics_ready()
        manual.extend(contrast_nodes('TEST Analytics',size,['.library-analytics h1','.library-analytics h2','.analytics-range-note','.analytics-snapshot-grid dt','.analytics-snapshot-grid dd','.library-analytics label','.library-analytics select','.library-analytics button','.analytics-metrics dt','.analytics-metrics dd','.analytics-table caption','.analytics-table th','.analytics-table td','.analytics-privacy-note a']))
        focus=keyboard_target(page.locator('#analytics-range'),'ArrowDown');analytics_ready()
        keyboard.append({'control':'Range selector','viewport':list(size),'focus':focus,'status':'PASS'})
        focus=keyboard_target(page.get_by_role('button',name='Refresh analytics',exact=True));analytics_ready()
        keyboard.append({'control':'Refresh analytics','viewport':list(size),'focus':focus,'status':'PASS'})
        focus=keyboard_target(page.locator('#analytics-series'),'ArrowDown')
        keyboard.append({'control':'Activity metric selector','viewport':list(size),'focus':focus,'status':'PASS'})
        if size[0]==375:
            trigger=page.get_by_role('button',name='Open workspace menu',exact=True)
            focus=keyboard_target(trigger);dialog=page.get_by_role('dialog',name='Workspace menu',exact=True);dialog.wait_for()
            assert dialog.get_by_role('link',name='Analytics',exact=True).is_visible()
            page.keyboard.press('Escape');assert trigger.evaluate('e=>e===document.activeElement')
            keyboard.append({'control':'Mobile Staff navigation includes Analytics; Escape restores focus','viewport':list(size),'focus':focus,'status':'PASS'})
    assert manual and all(row['ratio']>=row['required'] for row in manual)
    report=json.loads((REPORTS/'institution_v2e_accessibility.json').read_text(encoding='utf8'))
    report.update(manual_contrast=manual,keyboard_checks=keyboard)
    put('institution_v2e_accessibility.json',report)
    check(checks,'Analytics keyboard controls, mobile navigation and rendered contrast',measurements=len(manual),keyboard_checks=len(keyboard))


def staff_and_events_regression(run_layout=True):
    refresh_qa_tokens()
    login('staff');page.set_viewport_size({'width':1440,'height':900});rows=[]
    for suffix in ['', '/inventory','/circulation','/reservations','/fees','/members','/settings','/events','/analytics']:
        path='/staff/libraries/'+TEST+suffix;goto(path);product_ready('main h1')
        page.get_by_text(re.compile('^Loading')).first.wait_for(state='hidden',timeout=60000)
        assert page.locator('.global-logo').get_attribute('href')=='/staff/libraries/'+TEST
        assert urlparse(page.url).path==path
        page.locator('.global-logo').click();page.wait_for_url(BASE+'/staff/libraries/'+TEST);product_ready('main h1')
        rows.append({'surface':suffix or '/overview','home':'/staff/libraries/'+TEST,'status':'PASS'})
    goto('/reading-list?staff_library='+TEST);product_ready('main h1')
    assert page.locator('.global-logo').get_attribute('href')=='/staff/libraries/'+TEST
    rows.append({'surface':'Personal Reading List','home':'/staff/libraries/'+TEST,'status':'PASS'})
    if run_layout:
        run_matrix(STAFF_PAGES+[('Staff Events','/staff/libraries/'+TEST+'/events','main h1')],'STAFF')
    login('borrower');goto('/libraries/'+fixtures['C']);product_ready('#new-arrivals .product-book-card')
    page.get_by_role('heading',name='Upcoming Events',exact=True).wait_for()
    page.get_by_role('link',name='All library events',exact=True).click();product_ready('.event-card')
    assert urlparse(page.url).path==f'/libraries/{fixtures["C"]}/events'
    rows.append({'surface':'Patron upcoming Events','library':fixtures['C'],'status':'PASS'})
    global_events=api('/events?view=past',account='mixed')['events'];assert all(row.get('library_id') is None for row in global_events)
    goto('/events?view=past');product_ready('.event-card')
    assert page.locator('.global-logo').get_attribute('href')=='/'
    notices=api('/notifications?limit=50',account='borrower')['notifications']
    owned_ids={row['notification_id'] for row in db.notifications.find({'user_id':accounts['borrower']['user_id']},{'notification_id':1})}
    assert notices and all(row['notification_id'] in owned_ids for row in notices)
    page.get_by_role('button',name=re.compile('^Notifications')).click();page.get_by_role('region',name='Notification Center').wait_for()
    assert page.get_by_role('region',name='Notification Center').get_by_text('Part 2E QA Library A',exact=False).count()>0
    page.keyboard.press('Escape')
    rows.append({'surface':'Account notification bell and canonical tenant sources','status':'PASS'})
    put('institution_v2e_staff_product_regression.json',{'status':'PASS','checks':rows})
    put('institution_v2e_product_responsive_final.json',{'status':'PASS','rows':matrix})
    put('institution_v2e_product_accessibility_final.json',{'status':'PASS','audits':accessibility})
    check(checks,'Accepted Staff context, Events and Notifications browser regression',checks=len(rows))


def refresh_qa_tokens():
    # Long responsive sweeps can outlive the normal JWT lifetime. Refresh only
    # through real login, after same-token revocation checks have completed.
    for name,row in accounts.items():
        reply=requests.post('http://127.0.0.1:8002/auth/login',json={'email':row['email'],'password':row['password']},timeout=30)
        assert reply.status_code==200
        auth_headers[name]={'Authorization':'Bearer '+reply.json()['access_token']}


def platform_browser_preserved():
    login('platform');page.set_viewport_size({'width':1440,'height':900})
    for path,heading in [('/platform','Overview'),('/platform/libraries','Libraries'),('/platform/libraries/'+TEST,'TEST')]:
        goto(path);page.get_by_role('heading',name=heading,exact=True).first.wait_for(timeout=60000)
        assert page.locator('.global-logo').get_attribute('href')=='/platform'
        assert page.get_by_role('link',name='Analytics',exact=True).count()==0
        assert page.get_by_role('button',name='Add Book',exact=True).count()==0
    check(checks,'Platform Overview, Libraries and safe TEST detail remain separate from tenant Analytics')


def credential_report_scan():
    values=[row['password'] for row in accounts.values()]+[credentials('staff')[1],credentials('patron')[1],private_code]
    unsafe=[]
    for path in REPORTS.glob('institution_v2e_*'):
        if path.suffix in ('.json','.md','.xml','.log'):
            content=path.read_text(encoding='utf8',errors='replace')
            if any(value and value in content for value in values) or re.search(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',content):
                unsafe.append(path.name)
    assert not unsafe,unsafe
    print('Credential report scan PASS',flush=True)


def product_regression():
    flow=(ROOT/'scripts/full_product_browser_flows.py').read_text(encoding='utf8')
    exec(flow.replace('ready(', 'product_ready(').replace('record(', 'product_record(').replace('full_product_', 'institution_v2e_product_'),globals())
    sweep=(ROOT/'scripts/full_product_browser_matrix.py').read_text(encoding='utf8')
    exec(sweep.replace('ready(', 'product_ready(').replace('full_product_', 'institution_v2e_product_'),globals())
    page.set_viewport_size({'width':1440,'height':900});login('patron')
    patron_walk();global_search_walk()
    # Retain the temporary normal Saved item through the Reading List layout
    # matrix, then undo only QA additions. Empty pre-existing lists stay empty.
    run_matrix(PATRON_PAGES,'PATRON');cleanup_personal()
    staff_and_events_regression();analytics_manual();benchmark_live();component_benchmarks()


def cleanup_qa():
    assert len(geometry_rows)==24 and len(matrix)==96 and not errors
    assert walk and all(row['context_pass'] for row in walk)
    put('institution_v2e_product_browser_walkthrough.json',{'engine':'real Chromium Playwright','status':'PASS','steps':walk,'errors':errors,'personal_QA_additions_restored':True})
    removed=[]
    for letter in ['A','B','C','EMPTY']:
        identity=fixtures[letter]
        api('/platform/libraries/'+identity+'/remove','POST',cmd(reason='Part 2E browser QA complete; retain disposable fixture data for audit.',expected_status='ACTIVE'),'platform')
        assert db.institution_libraries.find_one({'library_id':identity})['status']=='REMOVED'
        removed.append(identity)
    for name,row in accounts.items():
        if name!='platform':
            api('/platform/accounts/'+str(row['user_id']),'PATCH',{'is_active':False},'platform')
    revoked=db.platform_role_assignments.update_one({'user_id':accounts['platform']['user_id'],'status':'ACTIVE','approval_ref':'USER-INSTITUTION-V2E-QA'},{'$set':{'status':'REVOKED','revoked_at':datetime.now(timezone.utc),'revocation_reason':'Local Part 2E QA complete.'}})
    assert revoked.modified_count==1 and api('/platform/libraries',account='platform',expected=403)
    put('institution_v2e_qa_cleanup.json',{'status':'PASS','disposable_libraries_soft_removed':removed,'temporary_platform_grant_revoked':True,'ordinary_fixture_accounts_disabled':3,'platform_fixture':'Retained as an ordinary unprivileged local account; accepted self-disable guard prevents own account disable. No active platform grant remains.','human_TEST_authority_unchanged':True,'credentials_persisted':False})
    unique_checks={row['check']:row for row in checks}
    put('institution_v2e_browser.json',{'status':'PASS','browser':browser.version,'checks':list(unique_checks.values()),'security':security,'responsive_checks':len(geometry_rows),'product_viewports':len(matrix),'errors':errors,'QA_cleanup':'institution_v2e_qa_cleanup.json'})
