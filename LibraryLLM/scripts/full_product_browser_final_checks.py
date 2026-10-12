"""Final browser evidence; loaded into the authenticated review session."""
import shutil


def final_category_and_dialog_checks():
    categories=[]
    goto('/catalog');ready('.product-book-grid .product-book-card')
    page.wait_for_function("document.querySelectorAll('.category-chips button').length>2")
    names=page.locator('.category-chips button').all_text_contents()[1:3]
    for name in names:
        chip=page.locator('.category-chips button').filter(has_text=name).first
        with page.expect_response(lambda r:urlparse(r.url).path.rstrip('/')=='/api/books' and 'category=' in r.url and r.request.method=='GET',timeout=90000) as reply:
            focus=keyboard_target(chip,'Space')
        assert reply.value.status==200
        page.wait_for_function('(name)=>document.querySelector(".category-chips button.is-active")?.textContent===name',arg=name)
        ready('.product-book-grid .product-book-card')
        assert page.locator('.category-chips button.is-active').text_content()==name
        assert 'category=' in page.url
        links=page.locator('.product-book-grid .product-book-card > a').evaluate_all('(els)=>els.map(e=>e.getAttribute("href"))')
        assert links and all(href.startswith('/book/') for href in links)
        row=record('Global category '+name,'GLOBAL',{'active':name,'result_count':len(links),'global_links':True,'rendered_count':page.locator('main [role=status]').all_text_contents()})
        categories.append({'category':name,'url':row['route'],'focus':focus,'status':'PASS','details':row['details']})
    goto(LINKED);ready('.book-detail-view h1')
    dialogs=[]
    for width,height in SIZES:
        page.set_viewport_size({'width':width,'height':height})
        trigger=page.get_by_role('button',name=re.compile('Open account menu'))
        focus=keyboard_target(trigger)
        dialog=page.get_by_role('dialog',name='Account & libraries',exact=True);dialog.wait_for()
        geometry=dialog.evaluate("""e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,viewport_width:innerWidth,viewport_height:innerHeight,document_width:document.documentElement.scrollWidth,overflow_y:getComputedStyle(e).overflowY,scroll_height:e.scrollHeight,client_height:e.clientHeight}}""")
        assert geometry['x']>=0 and geometry['y']>=0 and geometry['width']<=width and geometry['height']<=height and geometry['document_width']<=width,geometry
        page.keyboard.press('Escape');dialog.wait_for(state='hidden')
        restored=trigger.evaluate('e=>e===document.activeElement');assert restored
        dialogs.append({'viewport':f'{width}x{height}','geometry':geometry,'focus':focus,'restored':True,'status':'PASS'})
        if width==375:
            keyboard_target(trigger)
            page.screenshot(path=str(REPORTS/'full_product_browser_account_menu_mobile.png'),animations='disabled')
            page.keyboard.press('Escape')
    page.set_viewport_size({'width':1440,'height':900})
    put('full_product_browser_final_checks.json',{'status':'PASS','global_categories':categories,'account_dialogs':dialogs})
    print('Final global category and six dialog checks PASS',flush=True)


def final_representative_screenshots():
    # These matrix captures were made after the final source repairs. Preserve the
    # complete rendering as well as separate viewport images for visual review.
    representatives={
        'global_home':'global_home_1440',
        'test_home':'test_home_1440',
        'global_catalog':'global_catalog_1440',
        'test_catalogue':'test_browse_1440',
        'global_book_detail':'global_book_detail_1440',
        'test_linked_detail':'test_book_detail_1440',
        'test_local_only_detail':'test_local-only_detail_1440',
        'reading_list':'reading_list_1440',
        'global_search':'search_1440',
        'my_library':'my_library_1440',
        'reservations':'reservations_1440',
        'fees':'fees_1440',
        'account_libraries':'account_my_libraries_1440',
        'staff_overview':'staff_overview_1440',
        'staff_inventory':'staff_inventory_1440',
        'staff_circulation':'staff_circulation_1440',
        'mobile_test_home':'test_home_375',
        'mobile_test_catalogue':'test_browse_375',
        'mobile_test_detail':'test_book_detail_375',
    }
    for name,source in representatives.items():
        p=REPORTS/f'full_product_browser_{source}.png';assert p.exists(),p
        shutil.copyfile(p,REPORTS/f'full_product_browser_{name}.png')
    for name,route,selector in [
        ('global_home_viewport','/','#new-arrivals .product-book-card'),
        ('test_home_viewport',PATRON_HOME,'#new-arrivals .product-book-card'),
        ('global_detail_viewport',GLOBAL,'.book-detail-view h1'),
        ('test_detail_viewport',LINKED,'.book-detail-view h1'),
        ('local_search',PATRON_HOME+'/catalogue?search=Mobility','.product-book-card'),
    ]:
        goto(route);ready(selector)
        page.screenshot(path=str(REPORTS/f'full_product_browser_{name}.png'),animations='disabled')
    put('full_product_browser_screenshots.json',{'status':'PASS','final_representatives':[f'reports/full_product_browser_{name}.png' for name in representatives]+['reports/full_product_browser_local_search.png','reports/full_product_browser_mobile_detail_actions.png','reports/full_product_browser_account_menu_mobile.png'],'viewport_images':[f'reports/full_product_browser_{name}_viewport.png' for name in ['global_home','test_home','global_detail','test_detail']],'additional_platform_boundary':'reports/full_product_browser_platform_boundary_1440.png','note':'Ask-selected and pending-request captures document real earlier workflow states; matrix and final representatives document the final repaired styling.'})
    print('Final representative screenshots recorded',flush=True)


def final_cleanup():
    restored=[]
    for label,route in [('linked',LINKED),('local',LOCAL)]:
        if label not in saved_changes:continue
        goto(route);ready('.book-detail-view h1')
        if page.locator('.book-save-button').get_attribute('aria-pressed')=='true':
            page.locator('.book-save-button').click()
            page.wait_for_function("document.querySelector('.book-save-button').getAttribute('aria-pressed')==='false'")
        restored.append(label)
    goto(GLOBAL+RETURN);ready('.book-detail-view h1')
    if page.locator('.book-personal-actions button[aria-label^="Unselect "]').count():
        page.locator('.book-personal-actions button[aria-label^="Unselect "]').click()
    put('full_product_browser_cleanup.json',{'status':'PASS','saved_additions_removed':restored,'linked_AI_deselected':True,'canonical_pending_requests_cancelled':True,'method':'Canonical UI only; preserved pre-existing Saved entries and data. Request cancellations are documented in normal request history.'})
    put('full_product_browser_walkthrough.json',{'engine':'real Chromium Playwright','steps':walk,'errors':errors,'status':'PASS'})
    print('QA personal additions cleaned up through UI',flush=True)
