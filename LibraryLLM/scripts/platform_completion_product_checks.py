"""Context and rendered shared-cover regression checks in the live QA browser."""
product_context_checks=[];cover_rows=[];card_rows=[]
STAFF_HOME='/staff/libraries/'+TEST
def product_record(label,expected):
    actual=page.locator('.global-logo').get_attribute('href');assert actual==expected,(label,actual,expected)
    product_context_checks.append({'flow':label,'route':urlparse(page.url).path+'?'+urlparse(page.url).query,'home':actual,'expected':expected,'status':'PASS'})
def owner_home_flow():
    email,password=credentials('staff')
    check=context.request.post(BASE+'/api/auth/login',data={'email':email,'password':password});assert check.status==200,'Owner runtime credentials need correction.'
    print(login('staff'),flush=True)
    role=collection('memberships').find_one({'library_id':TEST,'user_id':4,'status':'ACTIVE'})
    assert role and role['role']=='ADMIN'
    goto(STAFF_HOME);ready('main h1');product_record('Owner Staff Overview',STAFF_HOME)
    for section,selector in [('inventory','.inventory-table'),('circulation','main h1'),('reservations','main h1'),('fees','main h1'),('members','main h1'),('settings','main h1')]:
        goto(STAFF_HOME+'/'+section);ready(selector);product_record('Owner '+section,STAFF_HOME)
        page.locator('.global-logo').click();ready('main h1');assert urlparse(page.url).path==STAFF_HOME
    goto(STAFF_HOME+'/inventory');ready('.inventory-table')
    page.get_by_role('link',name='My reading list',exact=True).click()
    ready('main h1');product_record('Owner Reading List return',STAFF_HOME)
    page.locator('.global-logo').click();ready('main h1');assert urlparse(page.url).path==STAFF_HOME
    goto(STAFF_HOME);ready('main h1');page.get_by_role('button',name=re.compile('Open account menu')).click()
    page.get_by_role('menuitem',name='Profile',exact=True).click();ready('main h1');product_record('Owner Profile return',STAFF_HOME)
    page.locator('.global-logo').click();ready('main h1')
    page.locator('.global-desktop-nav').get_by_role('link',name='Catalog',exact=True).click();ready('.product-book-card');product_record('Staff invokes mature global Catalog',STAFF_HOME)
    assert 'staff_library='+TEST in page.url
    page.locator('.product-book-card > a').first.click();ready('.book-detail-view h1');product_record('Staff global Book Detail return',STAFF_HOME)
    page.locator('.global-logo').click();ready('main h1');assert urlparse(page.url).path==STAFF_HOME
    # Staff identity never renders same-library Patron Home, even a direct URL.
    goto('/libraries/'+TEST);page.wait_for_url(lambda u:STAFF_HOME in str(u),timeout=60000);ready('main h1');product_record('Owner patron URL corrects to Staff',STAFF_HOME)
    goto('/platform');page.get_by_text('Platform access required',exact=True).wait_for(timeout=60000)
    product_context_checks.append({'flow':'Library ADMIN without PlatformRoleAssignment denied','status':'PASS'})
    goto(STAFF_HOME);ready('main h1');page.get_by_role('button',name=re.compile('Open account menu')).click();page.get_by_role('menuitem',name='Sign Out',exact=True).click();page.wait_for_url(lambda u:'/login' in str(u))
    assert page.evaluate("localStorage.getItem('luminar_token')") is None
    goto('/');ready('#new-arrivals .product-book-card');assert page.locator('.global-logo').get_attribute('href')=='/'
    product_context_checks.append({'flow':'Logout clears workspace return context','status':'PASS'})
    put('staff_home_context_repair.json',{'status':'PASS','ROHIT_TEST_ROLE':'ADMIN / Owner','ROHIT_HOME_FROM_TEST_STAFF':STAFF_HOME,'ROHIT_ROUTED_TO_TEST_PATRON':False,'checks':product_context_checks})
def global_home_flow():
    for path,selector in [('/','#new-arrivals .product-book-card'),('/catalog','.product-book-card'),(GLOBAL,'.book-detail-view h1'),('/reading-list','main h1')]:
        goto(path);ready(selector);product_record('Explicit global '+path,'/')
        page.locator('.global-logo').click();ready('#new-arrivals .product-book-card');assert urlparse(page.url).path=='/' and not urlparse(page.url).query
    put('patron_home_context_repair.json',{'status':'PASS','PATRON_HOME_FROM_TEST_CONTEXT':PATRON_HOME,'GLOBAL_HOME_FROM_GLOBAL_CONTEXT':'/','checks':walk+product_context_checks})
def cover_geometry(selector):
    return page.locator(selector).evaluate_all("""elements=>elements.map(e=>{
      const r=e.getBoundingClientRect(),title=e.querySelector('.book-cover-title'),author=e.querySelector('.book-cover-author'),copy=e.querySelector('.book-cover-content'),sr=e.querySelector('.book-cover-text-scrim'),t=title?.getBoundingClientRect(),a=author?.getBoundingClientRect();
      const inside=x=>!x||x.x>=r.x-1&&x.y>=r.y-1&&x.right<=r.right+1&&x.bottom<=r.bottom+1;
      const style=title?getComputedStyle(title):null;
      return {title:title?.textContent,author:author?.textContent||null,width:r.width,height:r.height,ratio:r.width/r.height,text_inside:inside(t)&&inside(a),title_author_overlap:!!t&&!!a&&t.bottom>a.y+1,copy_last:copy===e.lastElementChild,scrims:e.querySelectorAll('.book-cover-text-scrim').length,title_background:style?.backgroundColor,title_font:style?.fontSize,title_lines:style?.webkitLineClamp,copy_after_scrim:!!sr&&!!(sr.compareDocumentPosition(title)&Node.DOCUMENT_POSITION_FOLLOWING)};
    })""")
def cover_and_card_matrix():
    surfaces=[('Global Home showcase','/','#top .book-cover-art', '#new-arrivals .product-book-card'),
      ('Global recommendation rail','/','#for-you-results .book-cover-art','#new-arrivals .product-book-card'),
      ('Global Catalog','/catalog','.product-book-grid .book-cover-art','.product-book-card'),
      ('Global Search','/search?q=money','.product-book-card .book-cover-art','.product-book-card'),
      ('Global Book Detail',GLOBAL,'.book-detail-view .book-cover-art','.book-detail-view h1'),
      ('TEST Home showcase',PATRON_HOME,'#top .book-cover-art','#new-arrivals .product-book-card'),
      ('TEST recommendation rail',PATRON_HOME,'#for-you-results .book-cover-art','#new-arrivals .product-book-card'),
      ('TEST Browse',PATRON_HOME+'/catalogue','.product-book-grid .book-cover-art','.product-book-card'),
      ('TEST Book Detail',LINKED,'.book-detail-view .book-cover-art','.book-detail-view h1'),
      ('Reading List','/reading-list'+RETURN,'.product-book-card .book-cover-art','.product-book-card')]
    for name,route,cover_selector,ready_selector in surfaces:
        goto(route);ready(ready_selector)
        # Hero and recommendation sections use their accepted IDs/classes.
        if page.locator(cover_selector).count()==0:
            cover_selector='.book-cover-art' if 'showcase' in name else '#for-you-results .book-cover-art'
        page.locator(cover_selector).first.wait_for(timeout=60000)
        for w,h in SIZES:
            page.set_viewport_size({'width':w,'height':h});page.evaluate('document.fonts.ready')
            samples=cover_geometry(cover_selector)
            assert samples and all(s['text_inside'] and not s['title_author_overlap'] and s['copy_last'] and s['copy_after_scrim'] and s['scrims']==1 and abs(s['ratio']-2/3)<.02 and s['title_background']=='rgba(0, 0, 0, 0)' for s in samples),(name,w,samples)
            page.locator(cover_selector).first.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})");time.sleep(.12)
            capture=shot('covers_'+re.sub('[^a-z0-9]+','_',name.lower())+f'_{w}x{h}')
            cover_rows.append({'surface':name,'viewport':f'{w}x{h}','samples':samples,'screenshot':capture,'status':'PASS'})
            for card in page.locator('.product-book-card').all()[:10]:
                actions=card.locator('button:not([disabled]),a.bg-brand,summary')
                for index in range(actions.count()):
                    action=actions.nth(index);action.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})");page.wait_for_timeout(50)
                    measurement=action.evaluate("""e=>{const r=e.getBoundingClientRect(),card=e.closest('.product-book-card').getBoundingClientRect(),at=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {name:(e.getAttribute('aria-label')||e.textContent).trim(),inside_card:r.x>=card.x-1&&r.right<=card.right+1,center_visible:!!at&&(at===e||e.contains(at)),width:r.width,height:r.height,on_screen:r.x>=0&&r.right<=innerWidth}}""")
                    # Rail contents outside the visible horizontal slice are intentionally scrollable.
                    assert measurement['inside_card'],(name,w,measurement)
                    if measurement['on_screen']:assert measurement['center_visible'],(name,w,measurement)
                    card_rows.append({'surface':name,'viewport':f'{w}x{h}',**measurement,'status':'PASS'})
            assert page.evaluate('document.documentElement.scrollWidth')<=w
            print('COVER_MATRIX',name,w,len(samples),'PASS',flush=True)
    page.set_viewport_size({'width':1440,'height':900})
    put('book_cover_visual_validation.json',{'status':'PASS','shared_renderer':True,'checks':cover_rows,'samples_measured':sum(len(r['samples']) for r in cover_rows),'screenshots_review_required':True})
    put('book_card_layout_validation.json',{'status':'PASS','checks':card_rows,'measured_actions':len(card_rows),'method':'Real cover bounds, DOM layer order, title/author bounds, aspect ratios and actual action hit-testing. Off-screen rail items are not counted as visible until scrolled.'})
