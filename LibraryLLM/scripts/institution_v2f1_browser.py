"""Normal human QA logins and safe document/book workflows, current 2F.1 only."""
import sys,time,requests
from uuid import uuid4
sys.path.insert(0,str(ROOT))
from backend.database.mongodb import db
from scripts.institution_v2f_baseline import digest

fixtures=globals().get('fixtures',{})
critical_checks=globals().get('critical_checks',[])

def fresh_login(account):
    global context,page
    context.close();context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page()
    page.on('pageerror',lambda e:errors.append(str(e)))
    return login(account)

def api(path,method='GET',body=None,account='staff',expected=200):
    email,password=credentials(account)
    auth=requests.post('http://127.0.0.1:8002/auth/login',json={'email':email,'password':password},timeout=30)
    assert auth.status_code==200
    token=auth.json()['access_token']
    for attempt in range(12):
        result=requests.request(method,'http://127.0.0.1:8002'+path,json=body,headers={'Authorization':'Bearer '+token},timeout=45)
        if result.status_code!=503 or method!='GET':break
        time.sleep(.3)
    assert result.status_code==expected,f'{method} {path}: {result.status_code}'
    return result.json()

def bootstrap_formats():
    if 'format_library' not in fixtures:
        value=api('/libraries/register','POST',{'name':'Part 2F.1 Format QA','slug':'part2f1-format-'+uuid4().hex[:10],
            'library_type':'PUBLIC_LIBRARY','access_mode':'PUBLIC'},expected=201)
        fixtures['format_library']=value['library']['library_id']
        api(f'/libraries/{fixtures["format_library"]}/join','POST',{},'patron')
    sample=ROOT/'.scratch/institution-v2f/documents/LuminaR Digital Resources QA.pdf'
    assert sample.is_file()
    fixtures['sample']=str(sample)
    put('institution_v2f1_review_fixtures.json',{k:v for k,v in fixtures.items() if k!='sample'})

def form_book(mode,title=None):
    lib=fixtures['format_library'];fresh_login('staff');goto(f'/staff/libraries/{lib}/inventory')
    page.get_by_role('button',name='Add Book',exact=True).wait_for(timeout=45000)
    page.get_by_role('button',name='Add Book',exact=True).click()
    dialog=page.get_by_role('dialog',name='Add Book',exact=True)
    dialog.get_by_role('radio',name=mode,exact=True).check()
    assert dialog.get_by_role('radio').count()==3
    assert dialog.locator('input[type=radio]:checked').count()==1
    title=title or 'Part 2F.1 QA '+mode
    dialog.get_by_label('Title *',exact=True).fill(title);dialog.get_by_label('Subject / Genre *',exact=False).fill('Reference')
    physical=mode!='Online';online=mode!='Physical'
    assert dialog.get_by_label('Quantity *',exact=True).count()==int(physical)
    assert dialog.get_by_label('Shelf / Location',exact=True).count()==int(physical)
    assert dialog.get_by_label('Upload soft copy *',exact=True).count()==int(online)
    if physical:dialog.get_by_label('Quantity *',exact=True).fill('2');dialog.get_by_label('Shelf / Location',exact=True).fill('QA shelf')
    if online:dialog.get_by_label('Upload soft copy *',exact=True).set_input_files(fixtures['sample'])
    page.screenshot(path=str(REPORTS/f'institution_v2f1_form_{mode.replace(" ","_")}.png'),full_page=False)
    with page.expect_response(lambda r:f'/libraries/{lib}/inventory/books' in r.url and r.request.method=='POST',timeout=60000) as response:
        dialog.get_by_role('button',name='Save New Book',exact=True).click()
    assert response.value.status==201
    book=response.value.json();dialog.wait_for(state='hidden',timeout=150000)
    row=api(f'/libraries/{lib}/inventory/books/{book["library_book_id"]}')
    expected={'Physical':'PHYSICAL_ONLY','Online':'DIGITAL_ONLY','Physical + Online':'PHYSICAL_AND_DIGITAL'}[mode]
    assert row['book_format']==expected
    assert db.institution_holdings.count_documents({'library_id':lib,'library_book_id':book['library_book_id']})==int(physical)
    fixtures[mode]=row
    critical_checks.append({'scenario':mode,'status':'PASS','library_id':lib,'library_book_id':row['library_book_id'],'book_format':expected,'physical_holdings':int(physical)})
    put('institution_v2f1_review_fixtures.json',{k:v for k,v in fixtures.items() if k!='sample'})
    print('PASS add',mode,flush=True)

def existing_physical_attachment():
    fresh_login('staff');goto(f'/staff/libraries/{TEST}/inventory?search=TEST%20Reading%20Circle%20Discussion%20Notes')
    title='TEST Reading Circle Discussion Notes';page.get_by_role('heading',name=title,exact=True).wait_for(timeout=45000)
    book=db.institution_library_books.find_one({'library_id':TEST,'title':title},{'_id':0})
    assert book
    before=api(f'/libraries/{TEST}/inventory/books/{book["library_book_id"]}')
    assert before['book_format']=='PHYSICAL_ONLY'
    holding=db.institution_holdings.find_one({'library_id':TEST,'library_book_id':book['library_book_id']},{'_id':0})
    row=page.locator('tbody tr').filter(has=page.get_by_role('heading',name=title,exact=True))
    row.get_by_role('button',name='Actions for '+book['accession_number'],exact=True).click()
    page.get_by_role('menuitem',name='Add Online Copy',exact=True).click()
    dialog=page.get_by_role('dialog',name='Add Online Copy · '+title,exact=True);dialog.wait_for()
    assert page.get_by_role('dialog').count()==1
    dialog.get_by_label('Document file').set_input_files(fixtures['sample'])
    dialog.get_by_role('button',name='Add Online Copy',exact=True).click();dialog.wait_for(state='hidden',timeout=150000)
    after=api(f'/libraries/{TEST}/inventory/books/{book["library_book_id"]}')
    assert after['library_book_id']==before['library_book_id'] and after['accession_number']==before['accession_number']
    assert digest([db.institution_holdings.find_one({'library_id':TEST,'library_book_id':book['library_book_id']},{'_id':0})])==digest([holding])
    assert after['book_format']=='PHYSICAL_AND_DIGITAL'
    fixtures['TEST_attachment']=after
    critical_checks.append({'scenario':'Existing TEST Physical → Physical + Online','status':'PASS','book_id_preserved':True,'accession_preserved':True,'holding_unchanged':True,'asset_id':after['online_asset_id']})
    print('PASS existing physical attachment',flush=True)

def patron_formats():
    fresh_login('patron');lib=fixtures['format_library']
    for mode in ['Online','Physical + Online','Physical']:
        book=fixtures[mode];goto(f'/libraries/{lib}/books/{book["library_book_id"]}')
        page.get_by_role('heading',name=book['title'],exact=True).wait_for(timeout=45000)
        if mode!='Physical':page.get_by_role('link',name='Read Online',exact=True).wait_for(timeout=45000)
        else:assert page.get_by_role('link',name='Read Online',exact=True).count()==0
        assert page.get_by_role('button',name='Request Book',exact=True).count()==int(mode!='Online')
        if mode=='Online':assert page.get_by_text('Shelf not recorded',exact=True).count()==0
        critical_checks.append({'scenario':'Patron '+mode,'status':'PASS','read_online':mode!='Physical','request_book':mode!='Online'})
        page.screenshot(path=str(REPORTS/f'institution_v2f1_patron_{mode.replace(" ","_")}.png'),full_page=False)
    put('institution_v2f1_formats_browser.json',{'status':'PASS','checks':critical_checks,'fixtures':'institution_v2f1_review_fixtures.json','source':'Canonical library records, holdings and permitted READY assets; safe PDF native processing in existing RAG worker.'})
    print('PASS patron formats',flush=True)
