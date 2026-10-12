"""Assertions run in the live Part 2F Chromium session; no stored authentication."""
import time
from scripts.institution_v2f_baseline import digest

SIZES = [(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]
checks = globals().get('checks', [])
security = globals().get('security', [])
geometry_rows = globals().get('geometry_rows', [])
axe_rows = globals().get('axe_rows', [])
contrast_rows = globals().get('contrast_rows', [])
timings = globals().get('timings', [])
assets = globals().get('assets', {})


def contrast_nodes(label,size,selectors):
    return page.evaluate('''({label,size,selectors})=>{
      const rgba=s=>{const n=(s.match(/[\\d.]+/g)||[]).map(Number);return [n[0]||0,n[1]||0,n[2]||0,n.length>3?n[3]:1]};
      const over=(fg,bg)=>fg.slice(0,3).map((c,i)=>c*fg[3]+bg[i]*(1-fg[3]));
      const lum=c=>c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
      return selectors.flatMap(selector=>[...document.querySelectorAll(selector)].filter(e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden').map(e=>{
        const chain=[];for(let p=e;p;p=p.parentElement)chain.unshift(p);
        let bg=[255,255,255];for(const p of chain)bg=over(rgba(getComputedStyle(p).backgroundColor),bg);
        const s=getComputedStyle(e),fg=over(rgba(s.color),bg),a=lum(fg),b=lum(bg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
        return {surface:label,viewport:size,selector,foreground:s.color,background:bg.map(Math.round),ratio:Math.round(ratio*100)/100,required:parseFloat(s.fontSize)>=24||parseFloat(s.fontSize)>=18.66&&parseInt(s.fontWeight)>=700?3:4.5};
      }));
    }''',{'label':label,'size':list(size),'selectors':selectors})


def check(bucket, name, **values):
    bucket.append({'check': name, 'status': 'PASS', **values})
    print('PASS ' + name, flush=True)


def assets_ready(title='Digital Assets'):
    page.get_by_role('heading', name=title, exact=True).wait_for(timeout=60000)
    page.get_by_text('Loading library documents…', exact=True).wait_for(state='hidden', timeout=60000)
    page.evaluate('document.fonts.ready')


def wait_asset(library_id, asset_id, account='owner'):
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        response = requests.get(f'http://127.0.0.1:8002/libraries/{library_id}/assets/{asset_id}', headers=auth_headers[account], timeout=30)
        if response.status_code == 503:
            # Canonical metadata publication briefly holds the existing tenant
            # coherence barrier. Poll only this documented transient response.
            time.sleep(.2)
            continue
        assert response.status_code == 200, response.status_code
        row = response.json()
        if row['status'] == 'READY':
            return row
        assert row['status'] != 'FAILED', row.get('error_code')
        time.sleep(1)
    raise AssertionError('Asset processing did not finish within local QA deadline')


def upload_ui(account, library_id, title, book_id=None, visibility='MEMBERS'):
    login(account)
    goto(f'/staff/libraries/{library_id}/assets')
    assets_ready()
    page.get_by_role('button', name='Upload Document', exact=True).click()
    dialog = page.get_by_role('dialog', name='Upload Document', exact=True)
    dialog.wait_for()
    dialog.locator('#asset-upload-file').set_input_files(str(sample))
    dialog.locator('#asset-upload-title').fill(title)
    dialog.locator('#asset-upload-visibility').select_option(visibility)
    if book_id:
        option = dialog.locator(f'#asset-book-link option[value="{book_id}"]')
        if not option.count():
            book = db.institution_library_books.find_one({'library_id': library_id, 'library_book_id': book_id})
            dialog.locator('#asset-book-search').fill(book['title'])
            dialog.get_by_role('button', name='Find books', exact=True).click()
        dialog.locator(f'#asset-book-link option[value="{book_id}"]').wait_for(state='attached', timeout=30000)
        dialog.locator('#asset-book-link').select_option(book_id)
    started = time.perf_counter()
    with page.expect_response(lambda r: r.request.method == 'POST' and urlparse(r.url).path == f'/api/libraries/{library_id}/assets', timeout=60000) as uploaded:
        dialog.get_by_role('button', name='Upload Document', exact=True).click()
    assert uploaded.value.status == 202
    row = uploaded.value.json()
    assert row['status'] == 'PROCESSING' and row['library_id'] == library_id
    dialog.wait_for(state='hidden')
    assets_ready()
    page.get_by_role('link', name=title, exact=True).wait_for(timeout=30000)
    row = wait_asset(library_id, row['asset_id'], 'staff' if account == 'staff' else account)
    timings.append({'surface': 'PDF upload through READY', 'ms': round((time.perf_counter()-started)*1000,2), 'bytes': row['byte_size'], 'pages': row['pages']})
    check(checks, 'Normal browser upload PROCESSING to READY', library_id=library_id, asset_id=row['asset_id'], visibility=visibility)
    return row


def initial_uploads():
    refresh('staff'); refresh('patron')
    linked = db.institution_library_books.find_one({'library_id': TEST, 'status': 'ACTIVE', 'global_work_id': {'$ne': None}})
    local = db.institution_library_books.find_one({'library_id': TEST, 'status': 'ACTIVE', '$or': [{'global_work_id': None}, {'global_work_id': {'$exists': False}}]})
    assert linked and local
    fixtures['TEST_linked_book'] = linked['library_book_id']
    fixtures['TEST_local_book'] = local['library_book_id']
    fixtures['TEST_global_work'] = linked['global_work_id']
    assets['TEST_members'] = upload_ui('staff', TEST, 'LuminaR QA — Member Reading Guide', linked['library_book_id'])
    assets['TEST_staff'] = upload_ui('staff', TEST, 'LuminaR QA — Staff Reference', local['library_book_id'], 'STAFF_ONLY')
    for letter, account in [('A','owner'), ('B','mixed'), ('C','mixed')]:
        assets[letter] = upload_ui(account, fixtures[letter], 'Part 2F '+letter+' Resource Guide', fixtures['books_'+letter][0])
    assert len({row['asset_id'] for row in assets.values()}) == 5
    assert len({row['checksum'] for row in assets.values()}) == 1
    check(checks, 'Identical PDF remains separate across canonical libraries/assets', asset_ids=[r['asset_id'] for r in assets.values()])
    put('institution_v2f_live_assets.json', {name:{k:row[k] for k in ['asset_id','library_id','visibility','library_book_id','checksum','status']} for name,row in assets.items()})


def visibility_browser():
    row = assets['TEST_members']; path=f'/libraries/{TEST}/resources/{row["asset_id"]}'
    login('patron'); goto(f'/libraries/{TEST}/resources'); assets_ready('Library Resources')
    assert page.get_by_role('link',name=row['title'],exact=True).is_visible()
    assert page.get_by_text(assets['TEST_staff']['title'],exact=True).count() == 0
    page.get_by_role('link',name=row['title'],exact=True).click()
    page.locator('#asset-question').wait_for(timeout=30000)
    page.get_by_role('button',name='Open document',exact=True).click()
    page.get_by_role('iframe',name='Read '+row['title']).wait_for(timeout=30000) if False else page.locator('.asset-reader iframe').wait_for(timeout=30000)
    assert page.locator('.asset-reader iframe').get_attribute('src').startswith('blob:')
    check(checks,'Patron sees ready MEMBERS resource and opens authorized PDF; STAFF_ONLY hidden')
    shot('test_patron_document')
    login('staff'); goto('/staff'+path.replace('/resources/','/assets/')); page.locator('#asset-question').wait_for(timeout=30000)
    page.get_by_role('button',name='Edit metadata',exact=True).click();dialog=page.get_by_role('dialog',name='Edit document',exact=True)
    dialog.locator('#asset-edit-visibility').select_option('STAFF_ONLY');dialog.get_by_role('button',name='Save document',exact=True).click();dialog.wait_for(state='hidden')
    login('patron');goto(path);page.get_by_text('Document unavailable',exact=True).wait_for(timeout=30000)
    check(security,'Browser visibility MEMBERS to STAFF_ONLY immediately denies patron direct detail')
    login('staff');goto('/staff'+path.replace('/resources/','/assets/'));page.locator('#asset-question').wait_for(timeout=30000)
    page.get_by_role('button',name='Edit metadata',exact=True).click();dialog=page.get_by_role('dialog',name='Edit document',exact=True)
    dialog.locator('#asset-edit-visibility').select_option('MEMBERS');dialog.get_by_role('button',name='Save document',exact=True).click();dialog.wait_for(state='hidden')
    check(checks,'Staff retains document access and restores member visibility')


def ask_browser(account, library_id, row, staff=False):
    login(account);goto(f'{"/staff" if staff else ""}/libraries/{library_id}/{"assets" if staff else "resources"}/{row["asset_id"]}')
    page.locator('#asset-question').wait_for(timeout=30000)
    page.locator('#asset-question').fill('What time does the Cedar Reading Room open?')
    started=time.perf_counter()
    with page.expect_response(lambda r:'/assets/'+row['asset_id']+'/rag' in r.url and r.request.method=='POST',timeout=240000) as response:
        page.get_by_role('button',name='Ask document',exact=True).click()
    assert response.value.status==200, response.value.status
    data=response.value.json()
    assert data['library_id']==library_id and data['asset_id']==row['asset_id']
    assert '09:00' in data['answer'] or '9:00' in data['answer'] or '9 AM' in data['answer'] or '9 am' in data['answer'], data['answer']
    assert data['sources'] and all(s['library_id']==library_id and s['asset_id']==row['asset_id'] for s in data['sources'])
    page.locator('.asset-answer').wait_for(timeout=30000)
    timings.append({'surface':'Authorized existing document Q&A','ms':round((time.perf_counter()-started)*1000,2),'library_id':library_id,'asset_id':row['asset_id']})
    check(checks,'Actual resident Qwen browser document Q&A uses selected tenant asset',library_id=library_id,asset_id=row['asset_id'],sources=len(data['sources']))
    shot('document_answer_'+account+'_'+row['asset_id'][:8])
    return data


def book_resources_browser():
    login('patron');goto(f'/libraries/{TEST}/books/{fixtures["TEST_linked_book"]}')
    page.get_by_role('region',name='Library Resources',exact=True).wait_for(timeout=60000)
    assert page.get_by_role('link',name=assets['TEST_members']['title'],exact=True).is_visible()
    goto('/book/'+fixtures['TEST_global_work']);page.locator('.book-detail-view h1').wait_for(timeout=60000)
    assert page.get_by_role('region',name='Library Resources',exact=True).count()==0
    check(checks,'TEST linked book shows permitted library resource; explicit global detail has none')
    api(f'/libraries/{TEST}/assets/{assets["TEST_staff"]["asset_id"]}','PATCH',{'visibility':'MEMBERS'},'staff')
    goto(f'/libraries/{TEST}/books/{fixtures["TEST_local_book"]}');page.get_by_role('link',name=assets['TEST_staff']['title'],exact=True).wait_for(timeout=60000)
    api(f'/libraries/{TEST}/assets/{assets["TEST_staff"]["asset_id"]}','PATCH',{'visibility':'STAFF_ONLY'},'staff')
    check(checks,'Local-only TEST book resource association works without global attachment')


def measure(name,size,dialog=False):
    page.evaluate('document.fonts.ready')
    scope='dialog' if dialog else '.library-assets'
    geometry=page.evaluate('''scope=>{const nodes=[...document.querySelectorAll(scope+' button,'+scope+' input,'+scope+' select,'+scope+' textarea,'+scope+' .ui-button')].filter(e=>e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden');return {width:innerWidth,document_width:document.documentElement.scrollWidth,controls:nodes.map(e=>{const r=e.getBoundingClientRect();return {name:e.id||e.textContent.trim().slice(0,80),x:r.x,right:r.right,height:r.height,width:r.width}}),dialogs:[...document.querySelectorAll('dialog[open]')].map(e=>{const r=e.getBoundingClientRect();return {x:r.x,right:r.right,y:r.y,bottom:r.bottom,clientHeight:e.clientHeight,scrollHeight:e.scrollHeight}})}}''',scope)
    assert geometry['document_width']<=size[0]+1,geometry
    assert all(x['x']>=-1 and x['right']<=size[0]+1 and x['height']>=43.5 for x in geometry['controls']),geometry
    assert all(x['y']>=-1 and x['bottom']<=size[1]+1 for x in geometry['dialogs']),geometry
    for i in range(page.locator(scope+' button').count()):
        control=page.locator(scope+' button').nth(i)
        if control.is_visible() and control.is_enabled():
            control.scroll_into_view_if_needed()
            assert control.evaluate('(e)=>{const r=e.getBoundingClientRect(),h=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return h===e||e.contains(h)}'),control.inner_text()
    # Hit tests intentionally visit off-screen controls. Return to a consistent
    # audit viewport before axe measures visible target intersections.
    page.evaluate("window.scrollTo(0,0); document.querySelectorAll('dialog[open]').forEach(e=>e.scrollTop=0)")
    page.add_script_tag(path=str(ROOT/'frontend/node_modules/axe-core/axe.min.js'))
    axe=page.evaluate("async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});return {violations:r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),passes:r.passes.length}}")
    assert not axe['violations'],axe
    geometry_rows.append({'surface':name,'viewport':list(size),'status':'PASS','geometry':geometry});axe_rows.append({'surface':name,'viewport':list(size),**axe})
    selectors=['dialog h2','dialog p','dialog label','dialog button:not([disabled])'] if dialog else ['.library-assets h1','.library-assets h2','.library-assets p','.library-assets label','.library-assets dt','.library-assets dd','.library-assets button:not([disabled])']
    contrasts=contrast_nodes(name,size,selectors)
    assert all(r['ratio']>=r['required'] for r in contrasts),[r for r in contrasts if r['ratio']<r['required']]
    contrast_rows.extend(contrasts)
    if size[0] in [1440,375]:
        shot(name.lower().replace(' ','_')+'_'+str(size[0]))
    put('institution_v2f_responsive.json',{'status':'IN_PROGRESS','rows':geometry_rows})
    put('institution_v2f_accessibility.json',{'status':'IN_PROGRESS','audits':axe_rows,'rendered_contrast':contrast_rows})
    print('MEASURED',name,size,flush=True)


def dialog_keys(dialog,trigger):
    assert dialog.evaluate('(e)=>e.contains(document.activeElement)')
    for _ in range(12):
        page.keyboard.press('Tab');assert dialog.evaluate('(e)=>e.contains(document.activeElement)')
    page.keyboard.press('Escape');dialog.wait_for(state='hidden')
    assert trigger.evaluate('(e)=>document.activeElement===e')


def responsive_staff():
    login('staff')
    identity=assets['TEST_members']['asset_id']
    for size in SIZES:
        page.set_viewport_size({'width':size[0],'height':size[1]})
        goto(f'/staff/libraries/{TEST}/assets');assets_ready();measure('Staff Digital Assets',size)
        trigger=page.get_by_role('button',name='Upload Document',exact=True);trigger.focus();trigger.click();dialog=page.get_by_role('dialog',name='Upload Document',exact=True);dialog.wait_for();measure('Upload dialog',size,True);dialog_keys(dialog,trigger)
        goto(f'/staff/libraries/{TEST}/assets/{identity}');page.locator('#asset-question').wait_for(timeout=30000);measure('Staff Document Detail',size)
        for action,title in [('Edit metadata','Edit document'),('Delete document','Delete document')]:
            trigger=page.get_by_role('button',name=action,exact=True);trigger.focus();trigger.click();dialog=page.get_by_role('dialog',name=title,exact=True);dialog.wait_for();measure(title+' dialog',size,True);dialog_keys(dialog,trigger)
    check(checks,'Staff asset surfaces and upload/edit/delete dialogs pass six viewports and keyboard trap/Escape/focus restore')


def responsive_patron():
    login('patron')
    for size in SIZES:
        page.set_viewport_size({'width':size[0],'height':size[1]})
        goto(f'/libraries/{TEST}/resources');assets_ready('Library Resources');measure('Patron Resources',size)
        goto(f'/libraries/{TEST}/resources/{assets["TEST_members"]["asset_id"]}');page.locator('#asset-question').wait_for(timeout=30000);measure('Patron Document Q&A',size)
        page.get_by_role('button',name='Knowledge Tools',exact=True).click();page.get_by_role('tablist',name='Artifact types').wait_for(timeout=30000);page.get_by_text('Loading artifacts…',exact=True).wait_for(state='hidden',timeout=30000);measure('Library Knowledge Tools',size)
    check(checks,'Patron Resources/document Q&A/shared Knowledge Tools pass all six sizes')
    put('institution_v2f_responsive.json',{'status':'PASS','rows':geometry_rows})
    put('institution_v2f_accessibility.json',{'status':'PASS','audits':axe_rows,'rendered_contrast':contrast_rows,'keyboard':'Native modal initial focus, Tab trap, Escape, restored trigger at all six viewports; controls >=44px and hit-tested against Assistant.'})


def security_api():
    for account in accounts:
        refresh(account)
    refresh('staff');refresh('patron')
    wrong=assets['B']['asset_id'];a=fixtures['A']
    for tail,method,body in [('', 'GET',None),('/file','GET',None),('/rag','POST',{'query':'Use the PDF from Library B'}),('/artifacts','GET',None)]:
        target='http://127.0.0.1:'+('8005' if tail in ['/rag','/artifacts'] else '8002')+f'/libraries/{a}/assets/{wrong}'+tail
        response=requests.request(method,target,json=body,headers=auth_headers['mixed'],timeout=30)
        assert response.status_code==404,response.status_code
        check(security,'Cross-UUID denied before private retrieval '+tail,HTTP=response.status_code)
    for tail,port,method,body in [('',8002,'GET',None),('/file',8002,'GET',None),('/rag',8005,'POST',{'query':'Show the staff reference'}),('/artifacts',8005,'GET',None)]:
        response=requests.request(method,f'http://127.0.0.1:{port}/libraries/{TEST}/assets/{assets["TEST_staff"]["asset_id"]}'+tail,json=body,headers=auth_headers['patron'],timeout=30)
        assert response.status_code==404
        check(security,'STAFF_ONLY concealed from patron '+tail,HTTP=404)
    for account,expected in [('platform',404),('borrower',403)]:
        with sample.open('rb') as stream:
            response=requests.post(f'http://127.0.0.1:8002/libraries/{a}/assets',files={'file':(sample.name,stream,'application/pdf')},data={'title':'Denied ownership attempt','visibility':'MEMBERS'},headers={**auth_headers[account],'X-Luminar-Upload':str(uuid4())},timeout=30)
        assert response.status_code==expected,response.status_code
        check(security,account+' cannot create institution asset',HTTP=expected)
    target=f'http://127.0.0.1:8002/libraries/{TEST}/assets/{assets["TEST_members"]["asset_id"]}/file'
    response=requests.get(target,headers={**auth_headers['patron'],'Range':'bytes=0-31'},timeout=30)
    assert response.status_code==206 and response.content.startswith(b'%PDF-') and len(response.content)==32
    assert 'no-store' in response.headers['Cache-Control'] and response.headers['X-Content-Type-Options']=='nosniff'
    check(security,'Authorized file uses bounded Range streaming and private no-store',HTTP=206,bytes=32)
    login('platform');goto(f'/staff/libraries/{TEST}/assets');page.get_by_text('Unable to open this library',exact=True).wait_for(timeout=30000)
    assert page.locator('.asset-list,#asset-question').count()==0
    check(security,'Platform-only browser direct Staff asset route denied without TEST membership')


def knowledge_browser():
    login('patron');goto(f'/libraries/{TEST}/resources/{assets["TEST_members"]["asset_id"]}');page.locator('#asset-question').wait_for(timeout=30000)
    page.get_by_role('button',name='Knowledge Tools',exact=True).click();page.get_by_role('tab',name='Summary',exact=True).click()
    page.get_by_text('Loading saved artifacts…',exact=True).wait_for(state='hidden',timeout=30000)
    generate=page.get_by_role('button',name='Generate',exact=True)
    if generate.count():
        with page.expect_response(lambda r:'/artifacts/summary' in r.url and r.request.method=='POST',timeout=120000) as response:
            generate.click()
        assert response.value.status==200,response.value.status
        artifact=response.value.json()['artifact']
    else:
        artifact=next(a for a in rag_api(f'/libraries/{TEST}/assets/{assets["TEST_members"]["asset_id"]}/artifacts',account='patron')['artifacts'] if a['type']=='EXTRACTIVE_SUMMARY')
    assert artifact['libraryId']==TEST and artifact['assetId']==assets['TEST_members']['asset_id']
    assert artifact['sourceChunkIds'] and all(TEST in c and assets['TEST_members']['asset_id'] in c for c in artifact['sourceChunkIds'])
    page.locator('.knowledge-tools-shell button').filter(has_text=re.compile(r'^(View source|Page \d+)')).first.click();page.get_by_role('complementary',name='Source excerpt',exact=True).wait_for(timeout=30000)
    assert 'Cedar' in page.get_by_role('complementary',name='Source excerpt',exact=True).inner_text()
    check(checks,'Shared Knowledge Tools generates authorized library summary with scoped source preview',artifact_id=artifact['id'])
    results=[]
    for letter in ['A','B']:
        row=assets[letter];data=rag_api(f'/libraries/{fixtures[letter]}/assets/{row["asset_id"]}/artifacts/summary','POST',{'scope':'document','mode':'quick'},'mixed')
        cached=rag_api(f'/libraries/{fixtures[letter]}/assets/{row["asset_id"]}/artifacts/summary','POST',{'scope':'document','mode':'quick'},'mixed')
        assert cached['cached'] and cached['artifact']['id']==data['artifact']['id']
        results.append(data['artifact'])
    assert results[0]['id']!=results[1]['id'] and results[0]['libraryId']!=results[1]['libraryId']
    assert results[0]['sourceRevision']!=results[1]['sourceRevision']
    check(security,'Identical content/query Knowledge Tool cache remains tenant and asset isolated',artifact_ids=[r['id'] for r in results])
    shot('library_knowledge_summary')


def lifecycle_browser():
    identity=fixtures['C'];row=assets['C'];source=ROOT/f'local-data/library-assets/{identity}/{row["asset_id"]}/source.pdf'
    before=digest(db.institution_library_assets.find({'library_id':identity},{'_id':0}))
    for action,state,previous in [('suspend','SUSPENDED','ACTIVE'),('restore','ACTIVE','SUSPENDED'),('remove','REMOVED','ACTIVE'),('restore','ACTIVE','REMOVED')]:
        api('/platform/libraries/'+identity+'/'+action,'POST',cmd(reason='Disposable Part 2F asset lifecycle browser QA',expected_status=previous),'platform')
        assert db.institution_libraries.find_one({'library_id':identity})['status']==state and source.exists()
        assert digest(db.institution_library_assets.find({'library_id':identity},{'_id':0}))==before
        login('mixed');goto(f'/staff/libraries/{identity}/assets/{row["asset_id"]}')
        if state!='ACTIVE':
            page.get_by_text('Ask about this document',exact=True).wait_for(state='hidden',timeout=30000)
            for port,tail,method,body in [(8002,'/file','GET',None),(8005,'/rag','POST',{'query':'What time does the room open?'})]:
                response=requests.request(method,f'http://127.0.0.1:{port}/libraries/{identity}/assets/{row["asset_id"]}'+tail,json=body,headers=auth_headers['mixed'],timeout=30)
                assert response.status_code==404
        else:
            page.locator('#asset-question').wait_for(timeout=30000)
        check(security,'Disposable library '+action+' preserves asset and centralized access',library_id=identity,status=state)


def revocation_browser():
    identity=fixtures['A'];row=assets['A'];member=db.institution_memberships.find_one({'library_id':identity,'user_id':accounts['borrower']['user_id'],'status':'ACTIVE'})
    assert member
    login('borrower');goto(f'/libraries/{identity}/resources/{row["asset_id"]}');page.locator('#asset-question').wait_for(timeout=30000)
    page.get_by_role('button',name='Open document',exact=True).click();page.locator('.asset-reader iframe').wait_for(timeout=30000)
    api(f'/libraries/{identity}/memberships/{member["membership_id"]}','PATCH',{'status':'REMOVED'},'owner')
    page.locator('#asset-question').fill('What time does the room open?')
    with page.expect_response(lambda r:'/assets/'+row['asset_id']+'/rag' in r.url,timeout=45000) as response:
        page.get_by_role('button',name='Ask document',exact=True).click()
    assert response.value.status==404
    with page.expect_response(lambda r:'/assets/'+row['asset_id']+'/file' in r.url,timeout=45000) as response:
        page.get_by_role('button',name='Download document',exact=True).click()
    assert response.value.status==404
    page.locator('.asset-reader iframe').wait_for(state='hidden',timeout=30000)
    check(security,'Same logged-in browser next RAG and file request denied after canonical membership removal',HTTP=404)


def deletion_browser():
    identity=fixtures['B'];row=assets['B'];login('mixed');goto(f'/staff/libraries/{identity}/assets/{row["asset_id"]}');page.locator('#asset-question').wait_for(timeout=30000)
    page.get_by_role('button',name='Delete document',exact=True).click();dialog=page.get_by_role('dialog',name='Delete document',exact=True);dialog.wait_for()
    dialog.get_by_role('button',name='Confirm Delete',exact=True).click();page.wait_for_url(BASE+f'/staff/libraries/{identity}/assets',timeout=30000);assets_ready()
    stored=db.institution_library_assets.find_one({'library_id':identity,'asset_id':row['asset_id']})
    assert stored['status']=='DELETED' and stored['deleted_at']
    directory=ROOT/f'local-data/library-assets/{identity}/{row["asset_id"]}'
    assert (directory/'retired/source.pdf').exists() and not (directory/'generation').exists()
    assert db.institution_audit.count_documents({'library_id':identity,'event':'ASSET_DELETED','metadata.asset_id':row['asset_id']})>=1
    login('borrower');goto(f'/libraries/{identity}/resources/{row["asset_id"]}');page.get_by_text('Document unavailable',exact=True).wait_for(timeout=30000)
    for port,tail,method,body in [(8002,'/file','GET',None),(8005,'/rag','POST',{'query':'Show deleted source'}),(8005,'/artifacts','GET',None)]:
        response=requests.request(method,f'http://127.0.0.1:{port}/libraries/{identity}/assets/{row["asset_id"]}'+tail,json=body,headers=auth_headers['borrower'],timeout=30)
        assert response.status_code==404
    assert not api(f'/libraries/{identity}/assets',account='borrower')['results']
    check(security,'Browser deletion tombstones metadata/source, removes derived index, denies next file/RAG/tool access',asset_id=row['asset_id'])


def personal_browser():
    login('mixed');goto('/llm');page.get_by_role('button',name='Add Document',exact=True).first.wait_for(timeout=45000)
    before=api(f'/libraries/{fixtures["A"]}/assets',account='mixed')['total']
    with page.expect_response(lambda r:urlparse(r.url).path=='/rag-api/rag/upload' and r.request.method=='POST',timeout=120000) as response:
        page.locator('input[type=file]').first.set_input_files(str(sample))
    assert response.value.status==200,response.value.status
    document=response.value.json()['document'];identity=document['document_id']
    assert identity.startswith('doc_') and 'library_id' not in document and 'asset_id' not in document
    page.get_by_role('button',name='Knowledge Tools',exact=True).wait_for(timeout=45000)
    docs=rag_api('/rag/documents',account='mixed')['documents']
    # API login above is a separate session, so its personal list stays empty;
    # the browser's own session shows its just-uploaded source.
    assert not docs
    goto(f'/libraries/{fixtures["A"]}/resources');assets_ready('Library Resources')
    assert api(f'/libraries/{fixtures["A"]}/assets',account='mixed')['total']==before
    assert page.get_by_text(sample.name,exact=True).count()==1  # Canonical A source only; no extra personal entry.
    personal_id=identity
    # Purge exactly the QA browser session via the already accepted logout API.
    result=page.evaluate("async()=>{const token=localStorage.getItem('luminar_token');if(!token)throw Error('No authenticated session');const r=await fetch('/rag-api/rag/session/logout',{method:'POST',headers:{Authorization:'Bearer '+token}});return {status:r.status}}")
    assert result['status']==200
    check(checks,'Normal personal document UI remains session-owned and never appears as library resource',document_id=personal_id,personal_session_cleanup=True)


def performance_live():
    refresh('staff');refresh('patron')
    row=assets['TEST_members']
    samples=[]
    for label,path,headers in [('Staff asset list',f'/libraries/{TEST}/assets?limit=20',auth_headers['staff']),('Patron asset metadata',f'/libraries/{TEST}/assets/{row["asset_id"]}',auth_headers['patron']),('Authorized file Range startup',f'/libraries/{TEST}/assets/{row["asset_id"]}/file',{**auth_headers['patron'],'Range':'bytes=0-31'})]:
        values=[]
        for _ in range(3):
            started=time.perf_counter();response=requests.get('http://127.0.0.1:8002'+path,headers=headers,timeout=30);values.append(round((time.perf_counter()-started)*1000,2));assert response.status_code in [200,206]
        samples.append({'operation':label,'ms':values,'max_ms':max(values)})
    put('institution_v2f_performance.json',{'status':'MEASURED','local_host_only':True,'samples':samples,'browser_processing_and_RAG':timings,'pipeline':'Existing OCR/MiniLM/FAISS/resident Qwen reused; no new throughput gate or load-test claim.'})


def staff_product_regression():
    page.set_viewport_size({'width':1440,'height':900});login('staff');rows=[]
    for suffix in ['', '/inventory','/circulation','/reservations','/fees','/members','/settings','/events','/analytics','/activity','/audit']:
        path='/staff/libraries/'+TEST+suffix;goto(path);product_ready('main h1')
        page.get_by_text(re.compile('^Loading')).first.wait_for(state='hidden',timeout=60000)
        assert page.locator('.global-logo').get_attribute('href')=='/staff/libraries/'+TEST
        assert urlparse(page.url).path==path
        page.locator('.global-logo').click();page.wait_for_url(BASE+'/staff/libraries/'+TEST);product_ready('main h1')
        rows.append({'surface':suffix or '/overview','home':'/staff/libraries/'+TEST,'status':'PASS'})
    goto('/reading-list?staff_library='+TEST);product_ready('main h1')
    assert page.locator('.global-logo').get_attribute('href')=='/staff/libraries/'+TEST
    rows.append({'surface':'Personal Reading List','home':'/staff/libraries/'+TEST,'status':'PASS'})
    run_matrix(STAFF_PAGES+[('Staff Analytics','/staff/libraries/'+TEST+'/analytics','#analytics-snapshot-heading')],'STAFF')
    login('patron');goto('/events?view=past');product_ready('main h1')
    assert page.locator('.global-logo').get_attribute('href')=='/'
    goto('/libraries/'+TEST+'/events');product_ready('main h1');assert page.locator('.global-logo').get_attribute('href')=='/libraries/'+TEST
    page.get_by_role('button',name=re.compile('^Notifications')).click();panel=page.get_by_role('region',name='Notification Center');panel.wait_for(timeout=30000);page.keyboard.press('Escape')
    rows.append({'surface':'Existing Events/Notification Center','status':'PASS'})
    login('platform');goto('/platform');page.get_by_role('heading',name='Overview',exact=True).wait_for(timeout=60000)
    goto('/platform/libraries');page.get_by_role('heading',name='Libraries',exact=True).wait_for(timeout=60000)
    goto('/platform/libraries/'+TEST);page.get_by_role('heading',name='TEST',exact=True).wait_for(timeout=60000)
    assert page.get_by_role('button',name='Add Book',exact=True).count()==0
    rows.append({'surface':'Platform Overview/Libraries/TEST detail','status':'PASS','tenant_mutation_controls':False})
    put('institution_v2f_staff_product_regression.json',{'status':'PASS','checks':rows})
    put('institution_v2f_product_responsive_final.json',{'status':'PASS','rows':matrix})
    put('institution_v2f_product_accessibility_final.json',{'status':'PASS','audits':accessibility})
    check(checks,'Accepted Staff/Home/Events/Notifications/Analytics/Platform browser regression',checks=len(rows))


def cleanup_qa():
    assert len(geometry_rows)==48 and len(matrix)==96 and not errors
    assert walk and all(row['context_pass'] for row in walk)
    old=json.loads((ROOT/'.scratch/institution-v2f/previous_fixture.json').read_text(encoding='utf8'))
    removed=[]
    identities=set(fixtures[name] for name in ['A','B','C'])|set(old['libraries'].values())
    for identity in identities:
        current=db.institution_libraries.find_one({'library_id':identity})['status']
        if current!='REMOVED':
            api('/platform/libraries/'+identity+'/remove','POST',cmd(reason='Part 2F local browser QA complete; retain disposable fixture data for audit.',expected_status=current),'platform')
        removed.append(identity)
    disabled=[]
    qa=list(db.users.find({'email':{'$regex':'^institution-v2f-'}},{'_id':0,'user_id':1,'is_active':1}))
    # Revocation proof on the currently authenticated local QA account.
    # The platform self-disable guard remains respected.
    current_id=accounts['platform']['user_id']
    for row in qa:
        if row['user_id']!=current_id and row.get('is_active',True):
            api('/platform/accounts/'+str(row['user_id']),'PATCH',{'is_active':False},'platform')
            disabled.append(row['user_id'])
    grants=db.platform_role_assignments.update_many({'user_id':{'$in':[r['user_id'] for r in qa]},'status':'ACTIVE','approval_ref':'USER-INSTITUTION-V2F-QA'},{'$set':{'status':'REVOKED','revoked_at':datetime.now(timezone.utc),'revocation_reason':'Local Part 2F QA complete.'}})
    response=requests.get('http://127.0.0.1:8002/platform/libraries',headers=auth_headers['platform'],timeout=30)
    assert response.status_code==403
    assert not db.platform_role_assignments.count_documents({'user_id':{'$in':[r['user_id'] for r in qa]},'status':'ACTIVE'})
    check(security,'Temporary platform grants revoked; same token immediately denied',HTTP=403)
    # Scan only phase evidence for runtime secrets; redact frozen-suite parameter
    # names where a historical fixture happens to equal a supplied QA password.
    secrets_to_check=[row['password'] for row in accounts.values()]+[credentials(a)[1] for a in ['staff','patron']]
    for path in REPORTS.glob('institution_v2f*'):
        if path.suffix not in ['.json','.md','.xml','.log']:
            continue
        text=path.read_text(encoding='utf8')
        for secret in secrets_to_check:
            if secret in text:
                assert path.suffix in ['.xml','.log'] and 'regression' in path.name,'Secret found in phase evidence'
                text=text.replace(secret,'[REDACTED_QA_SECRET]');path.write_text(text,encoding='utf8')
        assert not re.search(r'eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+',text),'JWT found in phase evidence'
    put('institution_v2f_qa_cleanup.json',{'status':'PASS','disposable_libraries_soft_removed':removed,'ordinary_QA_accounts_disabled':disabled,'current_QA_platform_account':'Retained ordinary unprivileged account; self-disable guard respected','temporary_platform_grants_revoked':grants.modified_count,'same_token_revocation_status':403,'TEST_resources_retained':2,'personal_QA_cleaned':True,'credentials_persisted':False,'existing_human_authority_changed':False})
    put('institution_v2f_browser.json',{'status':'PASS','engine':'Real Chromium '+browser.version,'checks':checks,'security':security,'scenarios':'A-J completed through canonical API/browser paths','errors':errors,'QA_cleanup':'institution_v2f_qa_cleanup.json'})
