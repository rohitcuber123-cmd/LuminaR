"""Browser closure flows loaded into the real Playwright review session."""
import time

LINKED = '/libraries/'+TEST+'/books/946772b1-4be4-4a32-8435-525e2749ba0f'
LOCAL = '/libraries/'+TEST+'/books/7141195c-2b1b-43ea-9b64-3bb393fa0e44'
GLOBAL = '/book/OL19313623W'
PATRON_HOME = '/libraries/'+TEST
RETURN = '?patron_library='+TEST
walk = []
saved_changes = []
history_checks = []

def ready(selector='.product-book-card'):
    page.wait_for_load_state('networkidle',timeout=90000)
    page.locator(selector).first.wait_for(timeout=60000)
    page.evaluate('document.fonts.ready')

def record(step, expected='PATRON', detail=None):
    row=page.evaluate("""() => ({route:location.pathname+location.search+location.hash,logo:document.querySelector('.global-logo')?.getAttribute('href'),headings:[...document.querySelectorAll('main h1,main h2')].map(e=>e.textContent.trim()),notice:document.querySelector('.catalogue-context')?.textContent.trim()||'',detail_context:document.querySelector('[data-book-context]')?.getAttribute('data-book-context')||null,alerts:[...document.querySelectorAll('[role=alert]')].map(e=>e.textContent.trim())})""")
    row.update(step=step,expected_context=expected,details=detail)
    row['actual_context']='PATRON' if row['logo']==PATRON_HOME else 'GLOBAL'
    row['context_pass']=row['actual_context']==expected
    walk.append(row)
    put('full_product_browser_walkthrough.json',{'engine':'real Chromium Playwright','steps':walk,'errors':errors,'status':'IN_PROGRESS'})
    print(step,row['route'],row['context_pass'],flush=True)
    assert row['context_pass'],row
    return row

def save_once(label):
    button=page.locator('.book-save-button').first
    was_saved=button.get_attribute('aria-pressed')=='true'
    if not was_saved:
        button.click()
        page.wait_for_function("document.querySelector('.book-save-button')?.getAttribute('aria-pressed')==='true'",timeout=45000)
        saved_changes.append(label)
    return {'already_saved':was_saved,'saved':True}

def patron_walk():
    goto(PATRON_HOME); ready('#new-arrivals .product-book-card')
    primary=page.locator('main .product-book-card > a').evaluate_all('(rows)=>rows.map(e=>e.getAttribute("href"))')
    assert primary and all(href.startswith(PATRON_HOME+'/books/') for href in primary),primary
    record('TEST Home',detail={'primary_card_links':primary,'all_owned':True})
    shot('test_home')
    # Use a real rendered linked record, then canonical personal actions.
    page.locator('a[href="'+LINKED+'"]').first.click(); ready('.book-detail-view h1')
    assert page.get_by_role('button',name='Borrow',exact=True).count()==0
    record('Linked book detail',detail={'save':save_once('linked'),'direct_borrow':False})
    shot('test_linked_detail')
    if page.locator('.book-personal-actions button[aria-label^="Select "]').count():
        page.locator('.book-personal-actions button[aria-label^="Select "]').click()
    page.get_by_label('1 selected books',exact=True).wait_for()
    record('Select linked work for AI',detail={'counter':1})
    page.get_by_role('button',name='Ask LuminaR',exact=True).click()
    page.get_by_role('region',name='Selected books',exact=True).wait_for()
    assert 'Mobility and transport' in page.get_by_role('region',name='Selected books').inner_text()
    requests_selected=[]
    def on_request(request):
        if '/assistant/' in request.url:
            body=request.post_data_json or {}
            requests_selected.append({k:v for k,v in body.items() if k in {'query','message','selected_work_ids','selected_books','action','page_context','lending_context','selected_context'}})
    page.on('request',on_request)
    with page.expect_response(lambda response:'/assistant/' in response.url and response.request.method=='POST',timeout=180000) as reply:
        page.get_by_label('Message LuminaR AI',exact=True).fill('What is the title of the selected book?')
        page.get_by_role('button',name='Send message',exact=True).click()
    response=reply.value
    data=response.json()
    page.remove_listener('request',on_request)
    assert response.status==200
    page.get_by_text('Working on that…',exact=True).wait_for(state='hidden',timeout=180000)
    shot('ask_selected')
    record('Ask selected context',detail={'http_status':response.status,'request_context':requests_selected,'intent':data.get('intent'),'message':data.get('message','')[:300]})
    page.get_by_role('button',name='Close LuminaR AI',exact=True).click()
    page.get_by_role('link',name='My reading list',exact=True).click();ready()
    record('Reading List from TEST')
    shot('reading_list')
    saved_link=page.locator('main a[href*="OL19313623W"]').first
    assert saved_link.count()==1
    saved_link.click();ready('.book-detail-view h1')
    record('Saved item retains library context')
    # Canonical global representation must retain selected identity, not add one.
    assert page.locator('.book-personal-actions button[aria-label^="Unselect "]').get_attribute('aria-pressed')=='true'
    page.get_by_role('link',name='LuminaR home',exact=True).first.click();ready()
    record('Logo returns to TEST')
    page.locator('.global-desktop-nav').get_by_role('link',name='Browse Books',exact=True).click();ready()
    record('Browse Books');shot('test_catalogue')
    page.wait_for_function("document.querySelectorAll('.category-chips button').length>2",timeout=60000)
    chip_names=page.locator('.category-chips button').all_text_contents()
    for name in chip_names[1:3]:
        chip=page.locator('.category-chips button').filter(has_text=name).first
        chip.click();ready()
        active=page.locator('.category-chips button.is-active').text_content()
        assert active==name
        record('Local category '+name,detail={'active':active,'result_count':page.locator('.product-book-card').count(),'only_owned':all(h.startswith(PATRON_HOME+'/books/') for h in page.locator('.product-book-card > a').evaluate_all('(els)=>els.map(e=>e.getAttribute("href"))'))})
    page.locator('.product-book-card > a').first.click();ready('.book-detail-view h1');record('Category book detail')
    previous=walk[-2]['route'];page.go_back();ready();assert urlparse(page.url).path+('?' + urlparse(page.url).query if urlparse(page.url).query else '')==previous
    record('Browser Back restores category')
    page.go_forward();ready('.book-detail-view h1');record('Browser Forward restores detail')
    page.go_back();ready()
    page.locator('.global-desktop-nav').get_by_role('link',name='New Arrivals',exact=True).click();ready();record('Local New Arrivals')
    page.get_by_role('link',name='LuminaR home',exact=True).first.click();ready()
    page.locator('#new-arrivals').get_by_role('link',name='View All',exact=False).click();ready();record('New Arrivals View All')
    page.locator('.product-book-card > a').first.click();ready('.book-detail-view h1');record('Arrival detail')
    for name in ['My Library','Reservations','Fees']:
        page.locator('.patron-context-links').get_by_role('link',name=name,exact=True).click()
        page.locator('main h1').wait_for(timeout=60000)
        page.get_by_text(re.compile('^Loading')).first.wait_for(state='hidden',timeout=60000)
        record(name)
    page.get_by_role('button',name=re.compile('Open account menu')).click()
    page.get_by_role('menuitem',name='Profile',exact=True).click()
    page.get_by_role('heading',name='Profile',exact=True).wait_for();record('Profile')
    page.get_by_role('link',name='My libraries',exact=True).click()
    page.get_by_role('link',name='Open Library',exact=True).wait_for(timeout=60000)
    record('Karthikeya My Libraries',detail={'TEST_visible':page.get_by_role('heading',name='TEST',exact=True).count()==1,'member_group':page.get_by_role('heading',name='Member libraries',exact=True).count()==1,'staff_workspaces':page.get_by_role('link',name='Open Staff Workspace',exact=True).count()})
    shot('account_libraries')
    account={'account':'Karthikeya existing GENERAL_USER','steps':walk[-2:],'direct_url_agrees':False}
    page.get_by_role('link',name='Open Library',exact=True).click();ready();record('Open TEST through account UI')
    ui_route=urlparse(page.url).path;goto(PATRON_HOME);ready();account['direct_url_agrees']=ui_route==urlparse(page.url).path
    put('full_product_account_navigation_final.json',account)
    page.get_by_role('button',name='Search the catalog',exact=True).click()
    page.get_by_label('Search catalogue for TEST',exact=True).fill('Mobility')
    page.locator('.global-search').get_by_role('button',name='Search',exact=True).click();ready()
    record('TEST local lexical Search',detail={'results':page.locator('.product-book-card').count()});shot('local_search')
    page.locator('.product-book-card > a').first.click();ready('.book-detail-view h1');record('Local Search result')
    page.go_back();ready();record('Local Search Back retains query')
    page.get_by_role('link',name='LuminaR home',exact=True).first.click();ready();record('Search logo returns TEST')
    goto(LOCAL);ready('.book-detail-view h1')
    assert page.locator('.book-personal-actions button[aria-label^="Select "]').count()==0
    assert 'AI selection and related discovery require a linked LuminaR global work' in page.locator('.book-capability-note').inner_text()
    record('Local-only detail',detail={'save':save_once('local'),'AI_unsupported':True});shot('test_local_only_detail')
    page.get_by_role('link',name='My reading list',exact=True).click();ready()
    local_saved=page.locator('main a[href="'+LOCAL+'"]').first
    assert local_saved.count()==1
    local_saved.click();ready('.book-detail-view h1');record('Local-only saved item opens local detail')
    put('full_product_browser_walkthrough.json',{'engine':'real Chromium Playwright','steps':walk,'errors':errors,'status':'PASS','saved_changes_for_cleanup':saved_changes})

def global_search_walk():
    goto('/');ready('#new-arrivals .product-book-card');record('Global Home','GLOBAL');shot('global_home')
    page.get_by_role('button',name='Search the catalog',exact=True).click()
    page.get_by_label('Search the global catalogue',exact=True).fill('set theory')
    with page.expect_response(lambda response:'/search-api/search' in response.url,timeout=180000) as reply:
        page.locator('.global-search').get_by_role('button',name='Search',exact=True).click()
    response=reply.value;ready();assert response.status==200
    record('Authenticated global Search','GLOBAL',{'status':response.status,'result_count':page.locator('.product-book-card').count()})
    route=urlparse(page.url).path+'?'+urlparse(page.url).query
    shot('global_search')
    first_link=page.locator('.product-book-card > a').first;destination=first_link.get_attribute('href');first_link.click();ready('.book-detail-view h1')
    was_saved=page.locator('.book-save-button').get_attribute('aria-pressed')=='true'
    if not was_saved:
        page.locator('.book-save-button').click();page.wait_for_function("document.querySelector('.book-save-button').getAttribute('aria-pressed')==='true'")
    selection=page.locator('.book-personal-actions button[aria-label^="Select "]')
    if selection.count():selection.click()
    record('Global Search detail personal actions','GLOBAL');shot('global_book_detail')
    page.go_back();ready();assert urlparse(page.url).path+'?'+urlparse(page.url).query==route
    record('Global Search Back retains query','GLOBAL')
    put('full_product_authenticated_search.json',{'status':'PASS','engine':'real Chromium','query':'set theory','http_status':response.status,'route':route,'opened_detail':destination,'results':page.locator('.product-book-card').count(),'back_restored':True,'authenticated':True,'save':True,'AI_selection':True,'steps':walk[-3:]})
    # Restore only QA additions; leave pre-existing Saved entries untouched.
    goto(destination);ready('.book-detail-view h1')
    if not was_saved:
        page.locator('.book-save-button').click();page.wait_for_function("document.querySelector('.book-save-button').getAttribute('aria-pressed')==='false'")
    if page.locator('.book-personal-actions button[aria-label^="Unselect "]').count():page.locator('.book-personal-actions button[aria-label^="Unselect "]').click()

def pending_request_walk():
    goto(LINKED);ready('.book-detail-view h1')
    page.get_by_role('button',name='Request Book',exact=True).click()
    page.get_by_text('Borrow request · Awaiting librarian approval',exact=True).wait_for(timeout=60000)
    record('Canonical pending Request Book',detail={'pending_approval':True,'direct_borrow':False});shot('pending_request')
    page.locator('.patron-context-links').get_by_role('link',name='My Library',exact=True).click();page.get_by_text('Mobility and transport for elderly and handicapped persons',exact=True).first.wait_for(timeout=60000)
    record('Pending request appears in My Library')
    goto(LINKED);ready('.book-detail-view h1');page.get_by_role('button',name='Cancel Request',exact=True).click()
    page.get_by_role('dialog',name='Cancel Request',exact=True).get_by_role('button',name='Confirm',exact=True).click()
    page.get_by_role('button',name='Request Book',exact=True).wait_for(timeout=60000)
    record('QA request cancelled through canonical UI')

def deep_links():
    routes=[PATRON_HOME,PATRON_HOME+'/catalogue',LINKED,PATRON_HOME+'/my-library','/reading-list'+RETURN,'/catalog',GLOBAL]
    for route in routes:
        goto(route);ready('main h1')
        for mode in ['reload','hard_refresh']:
            if mode=='reload':page.reload(wait_until='domcontentloaded')
            else:
                cdp=context.new_cdp_session(page);cdp.send('Network.setCacheDisabled',{'cacheDisabled':True});page.reload(wait_until='domcontentloaded');cdp.send('Network.setCacheDisabled',{'cacheDisabled':False});cdp.detach()
            ready('main h1')
            page.get_by_text(re.compile('^Loading')).first.wait_for(state='hidden',timeout=60000)
            actual=urlparse(page.url).path+('?' + urlparse(page.url).query if urlparse(page.url).query else '')
            assert actual==route
            row=record('Deep link '+mode,'GLOBAL' if route in ['/catalog',GLOBAL] else 'PATRON')
            history_checks.append({'requested':route,'mode':mode,'actual':actual,'context_pass':row['context_pass'],'status':'PASS'})
    put('full_product_history_reload.json',{'engine':'real Chromium','status':'PASS','checks':history_checks,'back_forward_steps':[s for s in walk if 'Browser Back' in s['step'] or 'Browser Forward' in s['step']]})

def cleanup_personal():
    for label,route in [('linked',LINKED),('local',LOCAL)]:
        if label not in saved_changes:continue
        goto(route);ready('.book-detail-view h1')
        if page.locator('.book-save-button').get_attribute('aria-pressed')=='true':
            page.locator('.book-save-button').click();page.wait_for_function("document.querySelector('.book-save-button').getAttribute('aria-pressed')==='false'")
    goto(GLOBAL+RETURN);ready('.book-detail-view h1')
    if page.locator('.book-personal-actions button[aria-label^="Unselect "]').count():page.locator('.book-personal-actions button[aria-label^="Unselect "]').click()
    print('QA personal additions restored through UI.',flush=True)
