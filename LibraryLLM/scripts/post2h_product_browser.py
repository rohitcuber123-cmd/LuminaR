"""Actual Chromium product repair validation; runtime credentials only, no TEST writes."""
import json,sys,secrets,time,requests
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright,expect
from scripts.full_product_browser_session import credentials
from backend.database.mongodb import db
from backend.services import auth_service
BASE='http://127.0.0.1:5173';CORE='http://127.0.0.1:8002';REPORTS=ROOT/'reports'
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae';CN='e5ad68eb-efc2-446f-8132-ab2db9ce12bd';BOTH='9a122a7b-0a76-4d4f-bacf-a4daf32851de';STAFF='a8a04662-23be-45ea-bb20-0f0b86bcfa12'
checks=[];network=[];responsive=[];errors=[];pending=[];fixture={};cleanup_saved=False;patron_token=None;qa_uid=None
def save(state='IN_PROGRESS'):
    while pending:
        r=pending.pop(0)
        item={'method':r.request.method,'endpoint':r.url.removeprefix(BASE),'status':r.status}
        try:
            if '/analytics?' in r.url:item['metrics']=r.json().get('overview');item['range']=r.json().get('range')
            if '/preview' in r.url:item['content_type']=r.headers.get('content-type')
        except Exception:pass
        network.append(item)
    (REPORTS/'post2h_browser_validation.json').write_text(json.dumps({'status':state,'browser':'Chromium','checks':checks,'responsive':responsive,'network':network,'page_errors':errors,'fixture':fixture},indent=2),encoding='utf8')
def passed(name,**data):checks.append({'scenario':name,'status':'PASS',**data});save();print('PASS '+name,flush=True)
def api(path,token,method='GET',body=None):
    for _ in range(8):
        r=requests.request(method,CORE+path,headers={'Authorization':'Bearer '+token},json=body,timeout=90)
        if r.status_code!=503:break
        time.sleep(.4)
    assert r.ok,(r.status_code,r.text[:500]);return r.json()
def sign(page,email,password):
    page.goto(BASE+'/login');page.locator('input[type=email]').fill(email);page.locator('input[type=password]').fill(password)
    page.get_by_role('button',name='Sign In',exact=True).click();page.wait_for_url(lambda u:'/login' not in str(u),timeout=60000)
    return page.evaluate("localStorage.getItem('luminar_token')")
def setup(context):
    page=context.new_page();page.on('response',lambda r:pending.append(r) if any(v in r.url for v in ['/analytics?','/preview','/catalogue/','/reading-list/my']) else None);page.on('pageerror',lambda e:errors.append(str(e)));return page
def detail(page,lid,bid):
    page.goto(BASE+f'/libraries/{lid}/books/{bid}');page.locator('.book-detail-view .catalogue-actions').wait_for(timeout=60000)
    return page.locator('.book-detail-view')
def viewer(page,link):
    link.click();page.get_by_role('button',name='Close document',exact=True).wait_for(timeout=60000)
    image=page.locator('.asset-pdf-page')
    if image.count():expect(image).to_be_visible();page.wait_for_function('document.querySelector(".asset-pdf-page")?.naturalWidth > 0')
    else:expect(page.locator('.asset-text-viewer')).to_be_visible()
    return page.url.removeprefix(BASE)
def measured(page,name,width,height):
    page.wait_for_timeout(250)
    values=page.evaluate('''()=>({width:innerWidth,pageWidth:document.documentElement.scrollWidth,overflows:[...document.querySelectorAll('.catalogue-actions,.analytics-toolbar,.product-book-card,.book-personal-actions')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&e.scrollWidth>e.clientWidth+2}).map(e=>e.className)})''')
    assert values['pageWidth']<=width+2,(name,width,values)
    assert not values['overflows'],(name,width,values)
    path=f'post2h_product_{name}_{width}.png';page.screenshot(path=str(REPORTS/path),full_page=True)
    responsive.append({'page':name,'viewport':f'{width}x{height}','status':'PASS','measurements':values,'screenshot':path});save()
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf8');assert db.name=='luminar_library' and db.client.address[0] in ('localhost','127.0.0.1','::1')
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True)
   owner=setup(browser.new_context(viewport={'width':1440,'height':900}));owner_token=sign(owner,*credentials('staff'))
   owner.goto(BASE+f'/staff/libraries/{TEST}/analytics');owner.get_by_role('heading',name='Current snapshot',exact=True).wait_for(timeout=60000)
   assert not owner.get_by_text('Unable to load analytics',exact=True).count()
   for label,key in [('7 days','7d'),('30 days','30d'),('90 days','90d'),('All time','all')]:
    owner.get_by_role('combobox',name='Activity range',exact=True).click()
    with owner.expect_response(lambda r:f'/analytics?range={key}' in r.url and r.status==200,timeout=60000) as response:owner.get_by_role('option',name=label,exact=True).click()
    body=response.value.json();assert body['overview']['active_books']==151;assert body['overview']['active_loans']==0;assert body['overview']['pending_borrow_requests']==0
    owner.get_by_role('heading',name='Current snapshot',exact=True).wait_for();passed('TEST Analytics range '+label,http_status=200,overview=body['overview'])
   with owner.expect_response(lambda r:'/analytics?' in r.url and r.status==200):owner.get_by_role('button',name='Refresh analytics',exact=True).click()
   passed('Analytics refresh succeeds')
   owner.goto(BASE+f'/staff/libraries/{TEST}');owner.get_by_text('Inventory records',exact=True).wait_for(timeout=60000)
   passed('Staff Overview canonical counts',text=owner.locator('main').inner_text()[:1800])
   owner.goto(BASE+f'/staff/libraries/{TEST}/catalogue');owner.get_by_role('combobox',name='Circulation status',exact=True).wait_for(timeout=60000)
   owner.get_by_role('combobox',name='Circulation status',exact=True).focus();owner.keyboard.press('Space');expect(owner.get_by_role('listbox')).to_be_visible();owner.keyboard.press('Escape');expect(owner.get_by_role('combobox',name='Circulation status',exact=True)).to_be_focused()
   passed('Staff Catalogue themed select keyboard open Escape focus restore',native_selects=owner.locator('select:visible').count())
   owner.goto(BASE+f'/staff/libraries/{TEST}/inventory?search=CN');owner.get_by_role('link',name='CN',exact=True).wait_for(timeout=60000)
   passed('CN inventory record retained',book_id=CN)
   patron=setup(browser.new_context(viewport={'width':1440,'height':900}));patron_token=sign(patron,*credentials('patron'))
   patron.goto(BASE+f'/libraries/{TEST}');cards=patron.get_by_role('article',name='CN',exact=True);cards.first.wait_for(timeout=100000)
   expect(cards.first.get_by_role('link',name='Read Online',exact=True)).to_be_visible();assert not cards.first.get_by_role('button',name='Request Book',exact=True).count()
   passed('CN online-only Home and New Arrivals card',read_link=cards.first.get_by_role('link',name='Read Online').get_attribute('href'))
   path=viewer(patron,cards.first.get_by_role('link',name='Read Online',exact=True));passed('CN Home Read Online opens authorized real PDF page',viewer=path)
   region=detail(patron,TEST,CN);expect(region.get_by_role('link',name='Read Online',exact=True)).to_be_visible();expect(region.get_by_role('heading',name='Digital Resources',exact=True)).to_be_visible()
   for label in ['Copies','Shelf / Location','Call number','Circulation status']:assert not region.get_by_text(label,exact=True).count()
   assert not region.get_by_role('button',name='Request Book',exact=True).count();passed('CN detail online-only has no physical fields')
   path=viewer(patron,region.get_by_role('link',name='Read Online',exact=True));passed('CN Detail Read Online opens viewer',viewer=path)
   region=detail(patron,TEST,BOTH);expect(region.get_by_role('button',name='Request Book',exact=True)).to_be_visible();expect(region.get_by_role('link',name='Read Online',exact=True)).to_be_visible()
   passed('TEST Reading Circle BOTH detail exposes Request and Read');viewer(patron,region.get_by_role('link',name='Read Online',exact=True));passed('TEST BOTH authorized online viewer')
   region=detail(patron,TEST,STAFF);assert not region.get_by_role('link',name='Read Online',exact=True).count();assert not region.get_by_text('Staff Reference',exact=True).count();passed('STAFF_ONLY book asset does not advertise Patron online access')
   for route,name in [(f'/libraries/{TEST}/catalogue?sort=new_arrivals','Browse'),(f'/libraries/{TEST}/catalogue?search=CN','Search'),(f'/libraries/{TEST}/new-arrivals','New Arrivals')]:
    patron.goto(BASE+route);article=patron.get_by_role('article',name='CN',exact=True);article.wait_for(timeout=100000);expect(article.get_by_role('link',name='Read Online',exact=True)).to_be_visible();assert not article.get_by_role('button',name='Request Book',exact=True).count();passed(name+' shared CN capability')
   target=f'local:{TEST}:{CN}';before=api('/reading-list/my',patron_token)['items'];was_saved=any(item['target_key']==target for item in before)
   region=detail(patron,TEST,CN)
   if not was_saved:
    region.get_by_role('button',name='Add to Reading List',exact=True).click();region.get_by_role('button',name='In Reading List ✓',exact=True).wait_for();cleanup_saved=True
   patron.goto(BASE+'/reading-list');article=patron.get_by_role('article',name='CN',exact=True);article.wait_for(timeout=60000);expect(article.get_by_role('link',name='Read Online',exact=True)).to_be_visible();passed('Reading List hydrates current CN read capability');viewer(patron,article.get_by_role('link',name='Read Online',exact=True));passed('Reading List Read Online opens real viewer')
   # A separate canonical library owns all zero-stock/multiple-resource QA data.
   fixture_path=REPORTS/'post2h_product_fixture.json'
   if fixture_path.exists():fixture=json.loads(fixture_path.read_text())
   if not fixture.get('library_id'):
    lib=api('/libraries/register',owner_token,'POST',{'name':'Post2H Product QA','slug':'post2h-product-'+uuid4().hex[:8],'library_type':'PUBLIC_LIBRARY','access_mode':'PUBLIC'})['library'];lid=lib['library_id'];fixture={'library_id':lid}
    empty=api(f'/libraries/{lid}/analytics?range=30d',owner_token);assert empty['overview']['active_books']==0 and empty['overview']['active_loans']==0;fixture['empty_analytics']=empty['overview']
    fixture_path.write_text(json.dumps(fixture,indent=2),encoding='utf8')
   lid=fixture['library_id']
   for key,title in [('zero','QA Physical Unavailable Online'),('multi','QA Multiple Online Resources')]:
     if key not in fixture:
      data=api(f'/libraries/{lid}/inventory/books',owner_token,'POST',{'title':title,'subjects':['QA Product Repair'],'authors':['QA'],'copies':1,'create_physical_holding':True,'shelf_location':'QA','idempotency_key':str(uuid4())});b=data['library_book_id'];fixture[key]={'book_id':b,'title':title,'assets':[]}
      fixture_path.write_text(json.dumps(fixture,indent=2),encoding='utf8')
     b=fixture[key]['book_id']
     for i in range(len(fixture[key]['assets']),2 if key=='multi' else 1):
      text=(f'Canonical local member document {key} choice {i+1}.\nPhysical and digital access are independent.\n'*16).encode()
      r=requests.post(CORE+f'/libraries/{lid}/assets',headers={'Authorization':'Bearer '+owner_token,'X-Luminar-Upload':str(uuid4())},data={'title':title+f' resource {i+1}','visibility':'MEMBERS','library_book_id':b},files={'file':(f'{key}-{i}.txt',text,'text/plain')},timeout=60);assert r.status_code==202,r.text;asset=r.json()
      for _ in range(150):
       asset=api(f'/libraries/{lid}/assets/{asset["asset_id"]}',owner_token)
       if asset['status']=='READY':break
       assert asset['status']!='FAILED',asset.get('error_code');time.sleep(.5)
      assert asset['status']=='READY';fixture[key]['assets'].append({'asset_id':asset['asset_id'],'title':asset['title']});fixture_path.write_text(json.dumps(fixture,indent=2),encoding='utf8')
   api(f'/libraries/{lid}/staff/lending/books/{fixture["zero"]["book_id"]}/stock',owner_token,'PUT',{'idempotency_key':str(uuid4()),'total_copies':1,'unavailable_stock':1,'circulation_status':'CIRCULATING','allocation_mode':'AGGREGATE'})
   passed('Empty library Analytics returns valid zero state',overview=fixture['empty_analytics'])
   # Create a normal verified, disposable local-development Patron; never persist its password.
   email='post2h-product-'+uuid4().hex[:10]+'@example.com';password=secrets.token_urlsafe(32);mail={};original=auth_service.send_otp_email
   try:
    auth_service.send_otp_email=lambda address,name,otp:mail.update({address:otp}) or True
    user=auth_service.register_user('Post2H Product QA',email,password);qa_uid=user['user_id'];assert auth_service.verify_email_otp(email,mail.pop(email))
   finally:auth_service.send_otp_email=original
   qa=setup(browser.new_context(viewport={'width':1440,'height':900}));qa_token=sign(qa,email,password);lid=fixture['library_id'];api(f'/libraries/{lid}/join',qa_token,'POST',{})
   region=detail(qa,lid,fixture['zero']['book_id']);expect(region.get_by_role('button',name='Join Waitlist',exact=True)).to_be_visible();assert not region.get_by_role('button',name='Request Book',exact=True).count();viewer(qa,region.get_by_role('link',name='Read Online',exact=True));passed('BOTH zero physical stock retains working Read Online and physical waitlist')
   qa.goto(BASE+f'/libraries/{lid}/catalogue');article=qa.get_by_role('article',name=fixture['multi']['title'],exact=True);article.wait_for(timeout=60000);link=article.get_by_role('link',name='Read Online',exact=True);assert link.get_attribute('href').endswith('#digital-resources');link.click();resources=qa.get_by_role('region',name='Digital Resources',exact=True);resources.wait_for(timeout=60000);assert resources.get_by_role('link').count()==2;viewer(qa,resources.get_by_role('link',name=fixture['multi']['assets'][1]['title'],exact=True));passed('Multiple resources require explicit second resource choice and open selected viewer')
   for width,height in [(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]:
    owner.set_viewport_size({'width':width,'height':height});patron.set_viewport_size({'width':width,'height':height});qa.set_viewport_size({'width':width,'height':height})
    owner.goto(BASE+f'/staff/libraries/{TEST}/analytics');owner.get_by_role('heading',name='Current snapshot',exact=True).wait_for(timeout=60000);measured(owner,'analytics',width,height)
    control=owner.get_by_role('combobox',name='Activity range',exact=True);control.focus();owner.keyboard.press('Space');expect(owner.get_by_role('listbox')).to_be_visible();measured(owner,'analytics_range',width,height);owner.keyboard.press('Escape');expect(control).to_be_focused()
    owner.goto(BASE+f'/staff/libraries/{TEST}/catalogue');control=owner.get_by_role('combobox',name='Circulation status',exact=True);control.wait_for(timeout=60000);control.click();expect(owner.get_by_role('listbox')).to_be_visible();measured(owner,'staff_catalogue',width,height);owner.keyboard.press('Escape')
    region=detail(patron,TEST,CN);measured(patron,'online_detail',width,height)
    region=detail(patron,TEST,BOTH);measured(patron,'both_detail',width,height)
    patron.goto(BASE+f'/libraries/{TEST}/catalogue?sort=new_arrivals');patron.get_by_role('article',name='CN',exact=True).wait_for(timeout=60000);measured(patron,'browse_actions',width,height)
    region=detail(qa,lid,fixture['zero']['book_id']);measured(qa,'zero_stock_actions',width,height)
   passed('Responsive actions Analytics and shared control matrix',checks=len(responsive))
   assert not errors,errors
   browser.close();save('PASS')
 finally:
  if cleanup_saved and patron_token:api(f'/reading-list/local:{TEST}:{CN}',patron_token,'DELETE')
  if qa_uid:db.users.update_one({'user_id':qa_uid},{'$set':{'is_active':False}})
  if checks:save('PASS' if len(responsive)==42 and not errors else 'PARTIAL')
