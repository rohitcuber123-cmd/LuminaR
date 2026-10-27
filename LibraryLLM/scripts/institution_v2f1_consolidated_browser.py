"""Executed by the existing Chromium console; all uploads are authored QA data."""
exec((ROOT/'scripts/institution_v2f1_browser.py').read_text(encoding='utf8'))
exec((ROOT/'scripts/institution_v2f1_visual_browser.py').read_text(encoding='utf8'))
from io import BytesIO
from zipfile import ZipFile
import hashlib

checks=[]; sizes=[]
old_put=put
def put(name,value):
    # Historical receipts remain immutable during this new sweep.
    if name=='institution_v2f1_review_fixtures.json': name='institution_v2f1_consolidated_fixtures.json'
    old_put(name,value)
def passed(name,**facts):
    checks.append({'scenario':name,'status':'PASS',**facts})
    put('institution_v2f1_consolidated_browser.json',{'status':'IN_PROGRESS','checks':checks,'responsive':sizes})
    print('PASS '+name,flush=True)

resume=os.getenv('LUMINAR_CLOSURE_RESUME')=='docs'
fixtures=json.loads((REPORTS/('institution_v2f1_consolidated_fixtures.json' if resume else 'institution_v2f1_review_fixtures.json')).read_text())
fixtures['sample']=str(ROOT/'.scratch/institution-v2f/documents/LuminaR Digital Resources QA.pdf')
lib=fixtures['format_library'];base=f'/staff/libraries/{TEST}'
if not resume:
    fresh_login('staff');goto(base)
    page.locator('header').get_by_role('link',name='Catalog',exact=True).click()
    page.locator('.product-book-card').first.wait_for(timeout=45000)
    assert urlparse(page.url).path==base+'/catalogue'
    assert '150 local books in TEST' in page.locator('.catalogue-context').inner_text()
    assert not page.get_by_role('button',name='Request Book',exact=True).count()
    page.locator('header').locator('a[href="'+base+'"]').first.click()
    assert urlparse(page.url).path==base
    passed('A: Staff Catalog and logo',catalogue=base+'/catalogue',logo=base,library=TEST)
    goto(base+'/inventory');page.locator('.inventory-table tbody h2 a').first.wait_for(timeout=45000)
    link=page.locator('.inventory-table tbody h2 a').first;destination=link.get_attribute('href');link.click()
    page.get_by_role('button',name='Edit Book',exact=True).wait_for(timeout=45000)
    assert '/staff/libraries/'+TEST+'/books/' in destination
    passed('B/C: separate Inventory and canonical Staff detail',route=destination)
    
    for mode in ['Physical','Online','Physical + Online']:
        form_book(mode,'Consolidated 2F.1 QA '+mode)
        passed('Add Book '+mode,book_id=fixtures[mode]['library_book_id'],format=fixtures[mode]['book_format'],real_holding=mode!='Online')
    patron_formats();passed('H/I: Patron physical and online actions')
    physical=fixtures['Physical'];before=api(f'/libraries/{lib}/inventory/books/{physical["library_book_id"]}')
    holding=digest(list(db.institution_holdings.find({'library_id':lib,'library_book_id':physical['library_book_id']},{'_id':0})))
    fresh_login('staff');goto(f'/staff/libraries/{lib}/books/{physical["library_book_id"]}')
    page.get_by_role('button',name='Add Online Copy',exact=True).click()
    dialog=page.get_by_role('dialog');dialog.get_by_label('Document file').set_input_files(fixtures['sample'])
    dialog.get_by_role('button',name='Add Online Copy',exact=True).click();dialog.wait_for(state='hidden',timeout=180000)
    after=api(f'/libraries/{lib}/inventory/books/{physical["library_book_id"]}')
    assert before['library_book_id']==after['library_book_id'] and before['accession_number']==after['accession_number']
    assert after['book_format']=='PHYSICAL_AND_DIGITAL' and digest(list(db.institution_holdings.find({'library_id':lib,'library_book_id':physical['library_book_id']},{'_id':0})))==holding
    passed('G: Existing physical attaches online without recreating book',book_id_preserved=True,accession_preserved=True,holding_preserved=True)
    
else:
    checks=json.loads((REPORTS/'institution_v2f1_consolidated_browser.json').read_text())['checks']
    after=api(f'/libraries/{lib}/inventory/books/{fixtures["Physical"]["library_book_id"]}')
    fresh_login('staff')

asset=api(f'/libraries/{lib}/assets/{after["online_asset_id"]}')
asset_route=f'/staff/libraries/{lib}/assets/{asset["asset_id"]}'
goto(asset_route);page.get_by_role('button',name='Open document',exact=True).click()
page.locator('.asset-pdf-page').wait_for(timeout=45000)
frame=page.locator('.asset-pdf-page');assert frame.get_attribute('src').startswith('blob:')
email,password=credentials('staff');token=requests.post('http://127.0.0.1:8002/auth/login',json={'email':email,'password':password}).json()['access_token'];headers={'Authorization':'Bearer '+token}
source=requests.get(f'http://127.0.0.1:8002/libraries/{lib}/assets/{asset["asset_id"]}/file',headers=headers)
assert source.headers['content-type']=='application/pdf' and hashlib.sha256(source.content).hexdigest()==asset['checksum']
page.locator('.asset-pdf-page').wait_for();page.wait_for_function('()=>{const i=document.querySelector(".asset-pdf-page");return i&&i.complete&&i.naturalWidth>0}');page.locator('.asset-pdf-page').scroll_into_view_if_needed();page.screenshot(path=str(REPORTS/'institution_v2f1_consolidated_pdf.png'))
passed('J: actual source PDF page rendered with checksum verified',checksum_matches=True,content_type=source.headers['content-type'])
page.get_by_role('button',name='Close document',exact=True).click()
assert not page.locator('.asset-pdf-page').count()
page.locator('.asset-action-group').get_by_role('button',name='Ask LuminaR',exact=True).click()
page.locator('.assistant-drawer').wait_for()
assert not page.locator('.asset-rag-form').count()
page.locator('.assistant-composer textarea').fill('What time does the Cedar Reading Room open?')
with page.expect_response(lambda r:'/assistant/chat' in r.url,timeout=180000) as response:
    page.locator('.assistant-composer textarea').press('Enter')
answer=response.value.json();assert response.value.status==200 and answer['intent']=='DOCUMENT_QUESTION'
assert re.search(r'09:00|9\s*a\.?m\.?',answer['rag']['answer'],re.I)
assert answer['rag']['library_id']==lib and answer['rag']['asset_id']==asset['asset_id']
page.screenshot(path=str(REPORTS/'institution_v2f1_consolidated_assistant.png'))
passed('M: Existing shared Assistant grounded document turn',assistant_api=True,existing_widget=True,library_id=lib,asset_id=asset['asset_id'],source_count=len(answer['rag'].get('sources',[])))
page.get_by_role('button',name='Close LuminaR AI',exact=True).click()
page.get_by_role('button',name='Knowledge Tools',exact=True).click()
page.get_by_role('tab',name='Flashcards',exact=True).click()
try:
    page.get_by_label('Flashcard',exact=True).wait_for(timeout=10000)
except Exception:
    page.get_by_role('button',name=re.compile('Generate')).first.click()
    page.get_by_label('Flashcard',exact=True).wait_for(timeout=180000)
passed('N: Existing Knowledge Tools generates scoped flashcards')

for kind in ['TXT','DOCX']:
    content='Cedar Reading Room opens at 09:00.\nSafe consolidated document preview. <script>inert</script>'
    path=ROOT/'.scratch/institution-v2f/documents'/('Consolidated QA.'+kind.lower())
    if kind=='TXT': path.write_text(content,encoding='utf8')
    else:
        with ZipFile(path,'w') as package:
            package.writestr('[Content_Types].xml','<Types/>')
            package.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Cedar Reading Room opens at 09:00. Safe DOCX extracted preview.</w:t></w:r></w:p></w:body></w:document>')
    goto(f'/staff/libraries/{lib}/assets');page.get_by_role('button',name='Upload Document',exact=True).click()
    dialog=page.get_by_role('dialog');dialog.get_by_label('Document file').set_input_files(str(path));dialog.get_by_label('Title',exact=True).fill('Consolidated safe '+kind);dialog.locator('#asset-upload-visibility').select_option('MEMBERS')
    with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/assets'),timeout=60000) as response: dialog.get_by_role('button',name='Upload Document',exact=True).click()
    row=response.value.json();dialog.wait_for(state='hidden',timeout=60000)
    deadline=time.time()+180
    while time.time()<deadline:
        row=api(f'/libraries/{lib}/assets/{row["asset_id"]}')
        if row['status'] in ['READY','FAILED']: break
        time.sleep(1)
    assert row['status']=='READY',row.get('error_code')
    goto(f'/staff/libraries/{lib}/assets/{row["asset_id"]}');page.get_by_role('button',name='Open document',exact=True).click()
    page.locator('.asset-text-viewer').wait_for();assert 'Cedar Reading Room' in page.locator('.asset-text-viewer').inner_text()
    assert not page.locator('.asset-reader script').count()
    download=requests.get(f'http://127.0.0.1:8002/libraries/{lib}/assets/{row["asset_id"]}/file',headers=headers)
    assert download.content==path.read_bytes() and hashlib.sha256(download.content).hexdigest()==row['checksum']
    page.screenshot(path=str(REPORTS/f'institution_v2f1_consolidated_{kind}.png'))
    passed(kind+' native preview and original download',asset_id=row['asset_id'],checksum_matches=True,preview='extracted text' if kind=='DOCX' else 'plain text')

fresh_login('staff')
for surface,path in [('catalogue',base+'/catalogue'),('inventory',base+'/inventory'),('activity',base+'/activity'),('audit',base+'/audit'),('assets',f'/staff/libraries/{lib}/assets'),('document',asset_route)]:
    for width,height in VIEWPORTS:
        page.set_viewport_size({'width':width,'height':height});goto(path);page.locator('#main-content').wait_for();page.wait_for_timeout(500)
        assert page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth+1'),(surface,width)
        if surface=='catalogue':
            page.locator('.book-cover-art').first.wait_for(timeout=45000)
            covers=page.locator('.book-cover-art').evaluate_all(COVER_CHECK);assert all(c['pass'] for c in covers)
        if surface=='inventory':
            page.locator('.inventory-table tbody tr').first.wait_for(timeout=45000)
            assert page.locator('.inventory-title-cell').first.evaluate('(e)=>e.getBoundingClientRect().width>=260')
        page.screenshot(path=str(REPORTS/f'institution_v2f1_consolidated_{surface}_{width}.png'))
        sizes.append({'surface':surface,'viewport':[width,height],'status':'PASS','page_overflow':False})
    passed('Responsive '+surface,viewports=6)
put('institution_v2f1_consolidated_browser.json',{'status':'PASS','browser':'Chromium '+browser.version,'checks':checks,'responsive':sizes,'QA_library':lib,'new_QA_books':{k:fixtures[k]['library_book_id'] for k in ['Physical','Online','Physical + Online']}})
