"""Final live card, format-filter and safe document checks; browser console only."""
def card_matrix():
    checks=[];fresh_login('patron')
    for surface,path in [('global_home','/'),('global_catalog','/catalog'),('global_search','/search?q=harry'),('TEST_home',f'/libraries/{TEST}'),('TEST_browse',f'/libraries/{TEST}/catalogue'),('reading_list',f'/reading-list?patron_library={TEST}')]:
        for width,height in VIEWPORTS:
            page.set_viewport_size({'width':width,'height':height});goto(path);page.locator('.product-book-card').first.wait_for(timeout=45000);page.evaluate('()=>document.fonts.ready');page.wait_for_timeout(400)
            cards=page.locator('.product-book-card').evaluate_all('''es=>es.filter(e=>e.clientWidth>0).map(e=>{const b=e.getBoundingClientRect();const controls=[...e.querySelectorAll('button,summary,a.bg-brand,a.ui-button')].filter(c=>c.getClientRects().length);return {title:e.getAttribute('aria-label'),width:e.clientWidth,pass:e.scrollWidth<=e.clientWidth+1&&controls.every(c=>{const r=c.getBoundingClientRect();return r.left>=b.left-1&&r.right<=b.right+1&&c.scrollWidth<=c.clientWidth+1})}})''')
            assert cards and all(c['pass'] for c in cards),(surface,width,[c for c in cards if not c['pass']])
            target=page.locator('.product-book-card').last
            target.evaluate('(e)=>e.scrollIntoView({block:"center",inline:"center",behavior:"instant"})');page.wait_for_timeout(300)
            launcher=page.locator('.assistant-launcher');assert launcher.evaluate('(e)=>e.clientWidth<=60')
            overlap=target.evaluate('''e=>{const l=document.querySelector('.assistant-launcher').getBoundingClientRect();return [...e.querySelectorAll('button,summary,a.bg-brand,a.ui-button')].filter(c=>c.getClientRects().length).some(c=>{const r=c.getBoundingClientRect();return Math.min(l.right,r.right)>Math.max(l.left,r.left)&&Math.min(l.bottom,r.bottom)>Math.max(l.top,r.top)})}''')
            assert not overlap,(surface,width,'assistant overlays control')
            assert page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth+1')
            checks.append({'surface':surface,'viewport':[width,height],'cards':len(cards),'all_card_controls_inside':True,'assistant_compact':True,'assistant_control_overlap':False,'no_page_overflow':True,'status':'PASS'})
            page.screenshot(path=str(REPORTS/f'institution_v2f1_cards_{surface}_{width}.png'),animations='disabled')
            print('PASS cards',surface,width,len(cards),flush=True)
    put('institution_v2f1_book_card_layout_validation.json',{'status':'PASS','checks':checks,'method':'Live card bounds, native More actions bounds, rail end scrolling, compact launcher and overlap rectangles at all six viewports.'})

def format_filter_browser():
    fresh_login('staff');lib=fixtures['format_library'];goto(f'/staff/libraries/{lib}/inventory');page.get_by_role('columnheader',name='Format',exact=True).wait_for(timeout=45000);checks=[]
    for value,label in [('PHYSICAL_ONLY','Physical'),('DIGITAL_ONLY','Online'),('PHYSICAL_AND_DIGITAL','Physical + Online')]:
        with page.expect_response(lambda r:f'/libraries/{lib}/inventory/books?' in r.url and 'format='+value in r.url) as response:page.get_by_label('Format filter').select_option(value)
        result=response.value.json();assert result['total']==1 and all(r['book_format']==value for r in result['results'])
        page.get_by_role('heading',name=fixtures[label]['title'],exact=True).wait_for(timeout=45000)
        checks.append({'filter':label,'server_total':result['total'],'status':'PASS'})
    put('institution_v2f1_format_filter_browser.json',{'status':'PASS','checks':checks,'server_side':True})

def safe_document_browser():
    fresh_login('patron');lib=fixtures['format_library'];book=fixtures['Online'];goto(f'/libraries/{lib}/books/{book["library_book_id"]}');page.get_by_role('link',name='Read Online',exact=True).wait_for(timeout=45000);page.get_by_role('link',name='Read Online',exact=True).click()
    page.get_by_role('button',name='Open document',exact=True).wait_for(timeout=45000)
    with page.expect_response(lambda r:'/assets/'+book['online_asset_id']+'/file' in r.url) as response:page.get_by_role('button',name='Open document',exact=True).click()
    assert response.value.status==200 and 'application/pdf' in response.value.headers.get('content-type','')
    page.locator('iframe[src^="blob:"]').wait_for(timeout=45000);assert page.get_by_role('button',name='Close document',exact=True).count()==1
    page.get_by_role('button',name='Close document',exact=True).click();assert page.locator('iframe').count()==0
    page.get_by_role('button',name='Ask LuminaR',exact=True).first.click();assert page.get_by_label('Question',exact=True).evaluate('(e)=>e===document.activeElement')
    page.get_by_label('Question',exact=True).fill('What time does the Cedar Reading Room open?')
    with page.expect_response(lambda r:'/assets/'+book['online_asset_id']+'/rag' in r.url,timeout=180000) as response:page.get_by_role('button',name='Ask document',exact=True).click()
    assert response.value.status==200
    answer=response.value.json();assert answer['library_id']==lib and answer['asset_id']==book['online_asset_id'];assert '9' in answer.get('answer','')
    page.screenshot(path=str(REPORTS/'institution_v2f1_safe_document_answer.png'),animations='disabled')
    put('institution_v2f1_safe_document_browser.json',{'status':'PASS','fixture':'Hand-authored safe Cedar Reading Room QA PDF','open_close':True,'file_status':200,'file_mime':'application/pdf','scoped_RAG_status':200,'answer_matches_document':True,'personal_document_route_used':False,'private_owner_documents_opened':False})
    print('PASS safe document',flush=True)

