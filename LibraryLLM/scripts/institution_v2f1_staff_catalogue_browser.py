"""Current 2F.1 addendum: real Staff/Patron links and selected-library catalogue.

Executed in full_product_browser_session.py after the existing safe QA helper.
No credentials are persisted; only hand-authored QA PDFs are opened/uploaded.
"""
from urllib.parse import urlparse
import time

staff_catalogue_checks = globals().get('staff_catalogue_checks', [])
staff_catalogue_responsive = globals().get('staff_catalogue_responsive', [])
STAFF_BASE = f'/staff/libraries/{TEST}'


def record(scenario, **facts):
    staff_catalogue_checks.append({'scenario': scenario, 'status': 'PASS', **facts})
    put('institution_v2f1_staff_catalogue_browser.json', {'status': 'IN_PROGRESS', 'checks': staff_catalogue_checks})
    print('PASS ' + scenario, flush=True)


def current_route():
    url = urlparse(page.url)
    return url.path + ('?' + url.query if url.query else '')


def staff_catalogue_main():
    fresh_login('staff'); goto(STAFF_BASE)
    page.get_by_role('heading', name='Overview', exact=True).wait_for(timeout=45000)
    role = db.institution_memberships.find_one({'library_id': TEST, 'user_id': 4, 'status': 'ACTIVE'})
    assert role['role'] == 'ADMIN' and db.institution_libraries.find_one({'library_id':TEST})['owner_user_id'] == 4
    page.locator('header').get_by_role('link', name='Catalog', exact=True).click()
    page.locator('.product-book-card').first.wait_for(timeout=45000)
    assert current_route() == STAFF_BASE + '/catalogue'
    assert '150 local books in TEST' in page.locator('.catalogue-context').inner_text()
    assert page.locator('.inventory-table').count() == 0 and page.locator('.product-book-card').count() == 20
    ids = page.locator('.product-book-card').evaluate_all('(rows)=>rows.map(r=>r.dataset.libraryBookId)')
    assert db.institution_library_books.count_documents({'library_id': TEST, 'library_book_id': {'$in': ids}}) == 20
    assert page.get_by_role('button', name='Request Book', exact=True).count() == 0
    assert page.get_by_role('button', name='Join Waitlist', exact=True).count() == 0
    page.screenshot(path=str(REPORTS/'institution_v2f1_staff_catalogue_TEST.png'), full_page=True)
    record('A: Owner/Admin Catalog uses TEST cards', route=current_route(), role=role['role'], local_count=150, page_cards=20, all_owned_by_TEST=True, patron_actions=False)

    page.get_by_role('navigation', name='Staff workspace', exact=True).get_by_role('link', name='Inventory', exact=True).click()
    page.locator('.inventory-table tbody tr').first.wait_for(timeout=45000)
    assert current_route() == STAFF_BASE + '/inventory' and page.locator('.product-catalogue').count() == 0
    links = page.locator('.inventory-table tbody h2 a')
    assert links.count() == 20 and all(STAFF_BASE + '/books/' in link for link in links.evaluate_all('(nodes)=>nodes.map(n=>n.getAttribute("href"))'))
    record('B: Inventory remains management table with canonical title links', title_links=20, route=current_route())
    page.locator('header').get_by_role('link', name='Catalog', exact=True).click()
    page.locator('.product-book-card').first.wait_for(timeout=45000)
    record('C: Catalog returns to shared browsing grid', route=current_route(), shared_renderer=page.locator('.book-cover-art').count()==20)

    campus = db.institution_library_books.find_one({'library_id': TEST, 'title': 'TEST Campus Network Practice Workbook'})
    assert campus
    goto(STAFF_BASE + '/inventory?search=TEST%20Campus%20Network%20Practice%20Workbook')
    title = page.get_by_role('link', name=campus['title'], exact=True);title.wait_for(timeout=45000)
    assert title.get_attribute('href') == STAFF_BASE + '/books/' + campus['library_book_id']
    title.click();page.get_by_role('button', name='Edit Book', exact=True).wait_for(timeout=45000)
    page.get_by_role('link', name='Read Online', exact=True).wait_for(timeout=45000)
    assert page.get_by_text('Physical + Online', exact=True).count() > 0
    assert page.get_by_role('link', name='Manage Online Copy', exact=True).count() == 1
    page.screenshot(path=str(REPORTS/'institution_v2f1_staff_campus_detail.png'), full_page=True)
    record('Campus inventory title opens exact Staff detail', route=current_route(), library_book_id=campus['library_book_id'], format='Physical + Online', resources_visible=True, private_document_content_opened=False)

    previous = STAFF_BASE + '/inventory?search=a&kind=global&state=active&format=PHYSICAL_ONLY&page=1'
    goto(previous);page.locator('.inventory-table tbody h2 a').first.wait_for(timeout=45000)
    before = page.locator('.inventory-table tbody h2 a').evaluate_all('(nodes)=>nodes.map(n=>n.getAttribute("href"))')
    page.locator('.inventory-table tbody h2 a').first.click()
    back = page.get_by_role('link', name='Back to Inventory', exact=True);back.wait_for(timeout=45000)
    assert back.get_attribute('href') == previous
    back.click();page.locator('.inventory-table tbody h2 a').first.wait_for(timeout=45000)
    assert current_route() == previous and page.get_by_text('Page 2', exact=True).count() == 1
    assert page.locator('.inventory-table tbody h2 a').evaluate_all('(nodes)=>nodes.map(n=>n.getAttribute("href"))') == before
    record('Inventory Back restores search, record/state/format filters and page 2', route=current_route(), same_page_rows=True)


def staff_catalogue_online():
    book = fixtures['TEST_attachment'];bid = book['library_book_id'];aid = book['online_asset_id']
    assert aid == '197703fb-6af8-4a94-87cb-c28fdc83fba5'
    goto(STAFF_BASE + '/catalogue?search=' + book['title'].replace(' ', '%20'))
    article = page.get_by_role('article', name=book['title'], exact=True);article.wait_for(timeout=45000)
    assert article.get_by_text('Physical + Online', exact=True).count() == 1
    article.get_by_role('link', name='View Details', exact=True).click()
    page.get_by_role('link', name='Read Online', exact=True).wait_for(timeout=45000)
    assert current_route() == STAFF_BASE + '/books/' + bid
    read = page.get_by_role('link', name='Read Online', exact=True)
    assert read.get_attribute('href') == STAFF_BASE + '/assets/' + aid
    read.click();page.get_by_role('button', name='Open document', exact=True).wait_for(timeout=45000)
    page.get_by_role('button', name='Open document', exact=True).click()
    page.locator('iframe[title^="Read "]').wait_for(timeout=45000)
    assert page.locator('iframe').get_attribute('src').startswith('blob:')
    assert page.get_by_role('button', name='Ask LuminaR', exact=True).count() == 1
    assert page.get_by_role('button', name='Knowledge Tools', exact=True).count() == 1
    page.screenshot(path=str(REPORTS/'institution_v2f1_staff_read_online.png'), full_page=True)
    linked = page.get_by_role('link', name=book['title'], exact=True)
    assert linked.get_attribute('href') == STAFF_BASE + '/books/' + bid
    linked.click();page.get_by_role('button', name='Manage Stock', exact=True).wait_for(timeout=45000)
    record('D: Physical + Online card/detail → native safe PDF → linked Staff book', book_id=bid, asset_id=aid, authorized_file_open=True, asset_linked_book_clickable=True, staff_context=True, ask_and_knowledge_tools=True)

    # Exercise the existing upload form only in the disposable review library.
    lib = fixtures['format_library'];physical = fixtures['Physical'];pbid=physical['library_book_id']
    before = db.institution_holdings.find_one({'library_id': lib, 'library_book_id': pbid}, {'_id':0})
    goto(f'/staff/libraries/{lib}/books/{pbid}')
    page.get_by_role('button', name='Add Online Copy', exact=True).wait_for(timeout=45000)
    page.get_by_role('button', name='Add Online Copy', exact=True).click()
    dialog=page.get_by_role('dialog');assert page.get_by_role('dialog').count()==1
    dialog.get_by_label('Document file').set_input_files(str(ROOT/'.scratch/institution-v2f/documents/LuminaR Digital Resources QA.pdf'))
    dialog.get_by_label('Document title').fill('2F.1 clickable-title safe QA online copy')
    dialog.get_by_label('Visibility').select_option('STAFF_ONLY')
    dialog.get_by_role('button', name='Add Online Copy', exact=True).click()
    dialog.wait_for(state='hidden',timeout=150000)
    page.get_by_role('link',name='Read Online',exact=True).wait_for(timeout=45000)
    assert page.get_by_text('Physical + Online',exact=True).count()>0
    after = db.institution_holdings.find_one({'library_id': lib, 'library_book_id': pbid}, {'_id':0})
    assert digest([before]) == digest([after])
    created = db.institution_library_assets.find_one({'library_id':lib,'library_book_id':pbid,'title':'2F.1 clickable-title safe QA online copy'},{'_id':0,'asset_id':1,'status':1,'visibility':1})
    record('Add Online Copy works from shared Staff detail', library_id=lib, library_book_id=pbid, asset=created, holding_unchanged=True, TEST_untouched=True)


def staff_catalogue_switch_global():
    goto(STAFF_BASE + '/catalogue');page.locator('.product-book-card').first.wait_for(timeout=45000)
    page.get_by_label('Switch staff library',exact=True).select_option(fixtures['format_library'])
    page.get_by_role('heading',name='Overview',exact=True).wait_for(timeout=45000)
    page.locator('header').get_by_role('link',name='Catalog',exact=True).click()
    page.locator('.product-book-card').first.wait_for(timeout=45000)
    lib=fixtures['format_library'];assert current_route()==f'/staff/libraries/{lib}/catalogue'
    ids=page.locator('.product-book-card').evaluate_all('(rows)=>rows.map(r=>r.dataset.libraryBookId)')
    assert len(ids)==4 and db.institution_library_books.count_documents({'library_id':lib,'library_book_id':{'$in':ids}})==4
    assert db.institution_library_books.count_documents({'library_id':TEST,'library_book_id':{'$in':ids}})==0
    record('E: Explicit Staff switch loads the selected library only', library_id=lib, count=4, old_TEST_cards=False)
    page.get_by_role('link',name='Browse Global Catalogue',exact=True).click()
    page.locator('.product-book-card').first.wait_for(timeout=45000)
    page.get_by_text('Showing 1–20 of 5,000,000 titles',exact=True).wait_for(timeout=60000)
    assert current_route()=='/catalog'
    assert page.locator('.product-book-card[data-library-book-id]').count()==0
    assert page.locator('header').get_by_role('link',name='LuminaR home',exact=True).get_attribute('href')=='/'
    record('F: Explicit global action opens unchanged 5M catalogue', route=current_route(), global_count=5000000)


def staff_catalogue_sizes():
    for width,height in [(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]:
        page.set_viewport_size({'width':width,'height':height})
        for name,path,selector in [('catalogue',STAFF_BASE+'/catalogue','.product-book-card'),('inventory',STAFF_BASE+'/inventory','.inventory-table tbody h2 a'),('detail',STAFF_BASE+'/books/'+fixtures['TEST_attachment']['library_book_id'],'.library-book-resources')]:
            goto(path);page.locator(selector).first.wait_for(timeout=45000)
            page.wait_for_timeout(300)
            measured=page.evaluate('''() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,coverRatios:[...document.querySelectorAll('.book-cover-art')].map(e=>{const r=e.getBoundingClientRect();return r.width/r.height}),titleLinks:[...document.querySelectorAll('.inventory-table h2 a')].map(e=>({href:e.getAttribute('href'),name:e.textContent,tabIndex:e.tabIndex})),buttonsOutsideCards:[...document.querySelectorAll('.product-book-card')].flatMap(card=>[...card.querySelectorAll('button,a')].filter(e=>{const a=e.getBoundingClientRect(),b=card.getBoundingClientRect();return a.width&& (a.left<b.left-1||a.right>b.right+1)}).map(e=>e.textContent.trim()))})''')
            assert measured['scrollWidth']<=width+1,(width,name,measured)
            assert all(abs(r-2/3)<0.015 for r in measured['coverRatios'])
            assert not measured['buttonsOutsideCards']
            assert all(row['tabIndex']==0 and row['href'].startswith(STAFF_BASE+'/books/') for row in measured['titleLinks'])
            shotname=f'institution_v2f1_staff_{name}_{width}.png'
            page.screenshot(path=str(REPORTS/shotname),full_page=True)
            staff_catalogue_responsive.append({'surface':name,'viewport':[width,height],'status':'PASS','measurements':measured,'screenshot':shotname})
        print(f'PASS Staff catalogue/inventory/detail {width}x{height}',flush=True)
    page.set_viewport_size({'width':1440,'height':900})
    goto(STAFF_BASE+'/inventory?search=TEST%20Reading%20Circle%20Discussion%20Notes')
    title=page.locator('.inventory-table h2 a');title.wait_for(timeout=45000)
    found=False
    for _ in range(100):
        page.keyboard.press('Tab')
        if title.evaluate('(e)=>e===document.activeElement'):
            found=True;break
    assert found
    focus=title.evaluate('(e)=>({focusVisible:e.matches(":focus-visible"),outline:getComputedStyle(e).outlineStyle,outlineWidth:getComputedStyle(e).outlineWidth})')
    assert focus['focusVisible'] and focus['outline']!='none'
    page.keyboard.press('Enter');page.get_by_role('button',name='Edit Book',exact=True).wait_for(timeout=45000)
    trigger=page.get_by_role('button',name='Add Online Copy',exact=True);trigger.click()
    dialog=page.get_by_role('dialog');dialog.wait_for();assert page.evaluate('document.activeElement.closest("dialog")!==null')
    for _ in range(12):
        page.keyboard.press('Tab');assert page.evaluate('document.activeElement.closest("dialog")!==null')
    page.keyboard.press('Escape');dialog.wait_for(state='hidden')
    assert trigger.evaluate('(e)=>e===document.activeElement')
    record('Keyboard title activation and existing online-copy dialog focus trap/Escape/restore', focus=focus)
    put('institution_v2f1_staff_catalogue_responsive.json',{'status':'PASS','checks':staff_catalogue_responsive,'cases':len(staff_catalogue_responsive)})


def patron_global_titles():
    fresh_login('patron');goto(f'/libraries/{TEST}/catalogue')
    page.locator('.product-book-card').first.wait_for(timeout=45000)
    link=page.locator('.product-book-card').first.locator('h3').locator('xpath=ancestor::a')
    destination=link.get_attribute('href');assert destination.startswith(f'/libraries/{TEST}/books/')
    link.click();page.locator('.book-detail-view h1').wait_for(timeout=45000)
    assert current_route()==destination and page.get_by_role('button',name='Edit Book',exact=True).count()==0
    assert page.locator('header').get_by_role('link',name='LuminaR home',exact=True).get_attribute('href')==f'/libraries/{TEST}'
    record('Patron catalogue/title/detail remains Patron with TEST Home', route=current_route(), same_library=True)
    goto('/catalog');page.locator('.product-book-card').first.wait_for(timeout=45000)
    link=page.locator('.product-book-card').first.locator('h3').locator('xpath=ancestor::a')
    destination=link.get_attribute('href');assert destination.startswith('/book/OL')
    link.click();page.locator('.book-detail-view h1').wait_for(timeout=45000)
    assert current_route()==destination and page.locator('header').get_by_role('link',name='LuminaR home',exact=True).get_attribute('href')=='/'
    record('Explicit global catalogue/title/detail stays global', route=current_route(), global_home='/')
    put('institution_v2f1_staff_catalogue_browser.json',{'status':'PASS','checks':staff_catalogue_checks,'account_authority':'Runtime normal login; user 4 TEST Owner/Admin and user 10 GENERAL_USER. No grants or promotion.','private_documents_opened':False,'safe_pdf_only':True})


def staff_book_document_qa():
    # This fixture describes the Cedar Reading Room opening time, not a meeting.
    page.set_viewport_size({'width':1440,'height':900})
    goto(STAFF_BASE+'/books/'+fixtures['TEST_attachment']['library_book_id'])
    read=page.get_by_role('link',name='Read Online',exact=True);read.wait_for(timeout=45000);read.click()
    question=page.get_by_label('Question',exact=True);question.wait_for(timeout=45000)
    question.fill('What time does the Cedar Reading Room open?')
    page.get_by_role('button',name='Ask document',exact=True).click()
    page.locator('.asset-rag-answer').wait_for(timeout=150000)
    answer=page.locator('.asset-rag-answer').inner_text()
    assert re.search(r'\b09:00\b|\b9\s*a\.?m\.?',answer,re.I) and 'Page 1' in answer
    next(row for row in staff_catalogue_checks if row['scenario'].startswith('D:'))['native_RAG_from_book_flow']='PASS; safe authored Cedar Reading Room opening fact verified'
    put('institution_v2f1_staff_catalogue_browser.json',{**json.loads((REPORTS/'institution_v2f1_staff_catalogue_browser.json').read_text()),'checks':staff_catalogue_checks,'final_served_core_rechecked':True})
    page.screenshot(path=str(REPORTS/'institution_v2f1_staff_book_document_QA.png'),full_page=False)
    print('PASS final served Staff detail → scoped native document Q&A; safe QA fact verified',flush=True)
