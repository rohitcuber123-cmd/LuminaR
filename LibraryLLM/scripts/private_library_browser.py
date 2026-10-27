"""Disposable private tenancy runtime/browser proof. No persisted passwords/codes."""
import json,sys,time,secrets,requests
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright,expect
from scripts.full_product_browser_session import credentials
from scripts.post2h_product_browser import sign,BASE,CORE
from backend.database.mongodb import db
from backend.services import auth_service,library_intelligence_store as store,library_intelligence_service as intelligence
from scripts.migrate_management_authority import plan,apply
R=ROOT/'reports';checks=[];network=[];pending=[];failures=[];accounts=[];fixture={};member_id=None
DISTINCT='Aster Vale Restricted Archive Orchid 731';SUBJECT='Community archive preservation';SEMANTIC='getting around when walking is difficult'
def save(state='IN_PROGRESS'):
 while pending:
    r=pending.pop(0)
    item={'endpoint':r.url.removeprefix(BASE),'status':r.status,'method':r.request.method}
    if r.status!=200:
     try:item['safe_error']=r.json().get('detail')
     except Exception:pass
    if r.status==200:
     try:
      b=r.json();item['source']=b.get('source');item['ranking']=b.get('ranking');item['results']=[{k:row.get(k) for k in ['library_id','library_book_id','source','global_work_id','work_id','title']} for row in b.get('results',b.get('recommendations',[]))]
     except Exception:pass
    network.append(item)
 (R/'private_library_browser_validation.json').write_text(json.dumps({'status':state,'browser':'Chromium','fixture':fixture,'checks':checks,'network':network,'page_errors':failures},indent=2,default=str),encoding='utf8')
def passed(name,**data):checks.append({'scenario':name,'status':'PASS',**data});save();print('PASS '+name,flush=True)
def api(path,token=None,method='GET',body=None,base=CORE,status=200):
 for _ in range(8):
    r=requests.request(method,base+path,headers={'Authorization':'Bearer '+token} if token else {},json=body,timeout=100)
    if r.status_code!=503:break
    time.sleep(.5)
 assert r.status_code==status,(path,r.status_code,r.text[:250]);return r.json()
def setup(context):
 page=context.new_page();page.on('response',lambda r:pending.append(r) if any(s in r.url for s in ['/catalogue/','/intelligence/graph','/context','/search-api/search','/recommendation-api/']) else None);page.on('pageerror',lambda e:failures.append(str(e)));return page
def normal_account(name):
 email='private-audit-'+uuid4().hex[:12]+'@example.com';password=secrets.token_urlsafe(32);mail={};previous=auth_service.send_otp_email
 try:
    auth_service.send_otp_email=lambda email,name,otp:mail.update({email:otp}) or True
    user=auth_service.register_user(name,email,password);assert auth_service.verify_email_otp(email,mail.pop(email))
 finally:auth_service.send_otp_email=previous
 accounts.append(user['user_id']);return user['user_id'],email,password
def scoped(rows,lid):assert rows and all(r['source']=='LIBRARY' and r['library_id']==lid and r['library_book_id'] for r in rows),rows
def no_private(data):
 def without_query(value):
  if isinstance(value,dict):return {k:without_query(v) for k,v in value.items() if k!='query'}
  if isinstance(value,list):return [without_query(v) for v in value]
  return value
 text=json.dumps(without_query(data),default=str);assert fixture['private'] not in text and DISTINCT not in text
 assert not any(row['library_book_id'] in text for row in fixture['books'])
def ready_asset(lid,bid,title,visibility,owner_token):
 content=(f'Safe synthetic private archive resource {title}.\nThis catalogue audit contains no personal documents.\n'*16).encode()
 r=requests.post(CORE+f'/libraries/{lid}/assets',headers={'Authorization':'Bearer '+owner_token,'X-Luminar-Upload':str(uuid4())},data={'title':title,'visibility':visibility,'library_book_id':bid},files={'file':('audit.txt',content,'text/plain')},timeout=60);assert r.status_code==202,r.text
 a=r.json()
 for _ in range(180):
    a=api(f'/libraries/{lid}/assets/{a["asset_id"]}',owner_token)
    if a['status']=='READY':return {'asset_id':a['asset_id'],'book_id':bid,'title':title,'visibility':visibility}
    assert a['status']!='FAILED';time.sleep(.5)
 raise AssertionError('Synthetic asset did not reach READY')
def fixture_save():(R/'private_library_fixture.json').write_text(json.dumps(fixture,indent=2),encoding='utf8')
if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf8');assert db.name=='luminar_library' and db.client.address[0] in ('localhost','127.0.0.1','::1')
 try:
  with sync_playwright() as p:
   browser=p.chromium.launch(headless=True);owner=setup(browser.new_context(viewport={'width':1440,'height':900}));owner_token=sign(owner,*credentials('staff'));code=secrets.token_urlsafe(24)
   f=R/'private_library_fixture.json'
   if f.exists():fixture=json.loads(f.read_text())
   for key,private in [('private',True),('public',False),('other_private',True)]:
    if key not in fixture:
     lib=api('/libraries/register',owner_token,'POST',{'name':{'private':'Private Archive QA A','public':'Public Archive QA B','other_private':'Private Archive QA C'}[key],'slug':'private-audit-'+key.replace('_','-')+'-'+uuid4().hex[:8],'library_type':'PRIVATE_INSTITUTION' if private else 'PUBLIC_LIBRARY','access_mode':'PRIVATE_CODE' if private else 'PUBLIC',**({'access_code':code} if private else {})},status=201)['library'];fixture[key]=lib['library_id'];fixture_save()
    elif private:api(f'/libraries/{fixture[key]}/access-code',owner_token,'PUT',{'access_code':code})
   lid=fixture['private']
   if 'books' not in fixture:
    fixture['books']=[];global_book=db.books.find_one({'work_id':{'$regex':'^OL[0-9]+W$'}},{'_id':0,'work_id':1,'title':1});fixture['global_work_id']=global_book['work_id']
    titles=[DISTINCT,'Accessible transport for residents with limited mobility','Private archive member online edition','Private copy of '+global_book['title'],
      'Community archive preservation handbook','Oral histories and family memory','Local museum conservation practice','Preserving historic photographs','Archives for neighbourhood researchers','Accessible public transport planning','Wheelchair travel and mobility guidance','Disaster recovery for community records','Restoring fragile manuscripts','Cataloguing family letters','Recording the history of a village']
    for i,title in enumerate(titles):
     payload={'title':title,'subjects':[SUBJECT,'Accessible transportation' if i in [1,9,10] else 'Archives'],'authors':['Private QA Archivist'],'description':'Accessible transportation and mobility for residents who find walking difficult.' if i in [1,9,10] else 'Practical conservation of community archives, local histories and records.','create_physical_holding':i!=2,'copies':0 if i==2 else 1,'idempotency_key':str(uuid4()),**({'shelf_location':'PRIVATE-QA-SHELF'} if i!=2 else {}),**({'global_work_id':global_book['work_id']} if i==3 else {})}
     b=api(f'/libraries/{lid}/inventory/books',owner_token,'POST',payload,status=201);fixture['books'].append({'library_book_id':b['library_book_id'],'title':title,'global_work_id':b.get('global_work_id'),'physical':i!=2});fixture_save()
    fixture['member_asset']=ready_asset(lid,fixture['books'][2]['library_book_id'],'Private member archive reading', 'MEMBERS',owner_token)
    fixture['staff_asset']=ready_asset(lid,fixture['books'][0]['library_book_id'],'Private staff conservation notes','STAFF_ONLY',owner_token)
    for key in ['public','other_private']:
     for i in range(12):api(f'/libraries/{fixture[key]}/inventory/books',owner_token,'POST',{'title':key+' Community History Guide '+str(i+1),'subjects':['Public oral history' if key=='public' else 'Other private archive'],'authors':['Other QA'],'copies':1,'create_physical_holding':True,'idempotency_key':str(uuid4())},status=201)
    fixture_save()
   assert len(fixture['books'])==15
   for target,name in [('SEARCH_INDEX','search'),('KNOWLEDGE_GRAPH','kg')]:
    status=api(f'/libraries/{lid}/intelligence',owner_token)[name]
    if status['status']!='READY':
     owner.goto(BASE+f'/staff/libraries/{lid}/intelligence');button=owner.get_by_role('button',name='Build Search Index' if name=='search' else 'Build Knowledge Graph',exact=True);button.wait_for(timeout=60000);button.click()
     with owner.expect_response(lambda r:'/intelligence/builds' in r.url and r.request.method=='POST',timeout=60000) as response:owner.get_by_role('dialog').get_by_role('button',name='Build Search Index' if name=='search' else 'Build Knowledge Graph',exact=True).click()
     assert response.value.status==202
     for _ in range(180):
      status=api(f'/libraries/{lid}/intelligence',owner_token)[name]
      if status['status']=='READY':break
      assert status['status'] not in ['FAILED','RECOVERY_REQUIRED'];time.sleep(.5)
    assert status['status']=='READY' and status['record_count']==15;fixture[name]=status;fixture_save();passed('Explicit disposable private '+target+' build READY',generation=status['active_generation_id'],count=15)
   member_id,email,password=normal_account('Private Archive Member QA');member=setup(browser.new_context(viewport={'width':1440,'height':900}));member_login=(email,password);member_token=sign(member,*member_login)
   member.goto(BASE+'/libraries');member.get_by_role('textbox',name='Search libraries').fill('Private Archive QA A');member.get_by_role('button',name='Search',exact=True).click();member.get_by_role('button',name='Enter Access Code',exact=True).click();member.get_by_label('Institution Access Code').fill(code);member.get_by_role('dialog').get_by_role('button',name='Join Library',exact=True).click();member.wait_for_url(BASE+f'/libraries/{lid}',timeout=60000)
   membership=api(f'/libraries/{lid}/context',member_token)['membership'];assert membership['role']=='GENERAL_USER';passed('Legitimate private-code join grants GENERAL_USER only',library_id=lid,user_id=member_id)
   api(f'/libraries/{fixture["public"]}/join',member_token,'POST',{})
   member.get_by_role('article').first.wait_for(timeout=100000);member.screenshot(path=str(R/'private_library_member_home.png'),full_page=True)
   for query in [DISTINCT,SUBJECT,SEMANTIC]:
    member.goto(BASE+f'/libraries/{lid}/catalogue');member.locator('#catalogue-query').fill(query)
    with member.expect_response(lambda r:'/catalogue/search?' in r.url and r.status==200,timeout=100000) as response:member.locator('form.product-catalogue-search').get_by_role('button',name='Search',exact=True).click()
    result=response.value.json();assert result['source']['search_source']=='TENANT_SEMANTIC';scoped(result['results'],lid)
    assert result['source']['search_generation_id']==fixture['search']['active_generation_id']
    passed('Authorized private semantic Search '+query,source=result['source'],result_ids=[r['library_book_id'] for r in result['results']],top_title=result['results'][0]['title'])
   member.screenshot(path=str(R/'private_library_member_search.png'),full_page=True)
   r=api(f'/libraries/{lid}/catalogue/recommendations',member_token,'POST',{'work_ids':[fixture['global_work_id'],'OL999999W'],'limit':50});scoped(r['results'],lid);assert any(b['global_work_id']==fixture['global_work_id'] for b in r['results']);passed('Private Recommendation final canonical projection with global preferred work',ranking=r['ranking'],result_ids=[b['library_book_id'] for b in r['results']])
   member.goto(BASE+f'/libraries/{lid}');rail=member.locator('#for-you-results');rail.locator('article').first.wait_for(timeout=100000)
   links=rail.locator('article > a:first-of-type').evaluate_all('(es)=>es.map(e=>e.getAttribute("href"))');assert all(f'/libraries/{lid}/books/' in l for l in links)
   next_button=rail.get_by_role('button',name='Next Recommendations',exact=True);expect(next_button).to_be_enabled(timeout=60000);next_button.click();expect(rail.locator('article')).to_have_count(5,timeout=60000);passed('Private Home For You Next remains canonical private records')
   rail.get_by_role('link',name='VIEW ALL',exact=True).click();member.wait_for_url('**/catalogue?view=for-you',timeout=60000);expect(member.locator('article[data-library-book-id]')).to_have_count(15,timeout=60000);passed('Private View All remains private library only')
   bid=fixture['books'][0]['library_book_id'];member.goto(BASE+f'/libraries/{lid}/books/{bid}');member.get_by_role('heading',name=DISTINCT,exact=True).wait_for(timeout=60000);assert not member.get_by_role('link',name='Read Online',exact=True).count();assert not member.get_by_text(fixture['staff_asset']['title'],exact=True).count();passed('Private book detail permitted but STAFF_ONLY asset hidden')
   member.goto(BASE+f'/libraries/{lid}/resources/{fixture["member_asset"]["asset_id"]}?book={fixture["member_asset"]["book_id"]}&open=1');member.locator('.asset-text-viewer').wait_for(timeout=60000);passed('Authorized private member online document works')
   member.goto(BASE+f'/libraries/{lid}/graph');member.get_by_role('region',name='Library graph map').wait_for(timeout=60000);passed('Authorized private member KG renders')
   # Exact routes/endpoints, same fresh private UUID and book/asset UUIDs.
   outsider_id,email,password=normal_account('Private Archive Outsider QA');outsider=setup(browser.new_context(viewport={'width':1440,'height':900}));outsider_login=(email,password);outsider_token=sign(outsider,*outsider_login)
   for key in ['public','other_private']:api(f'/libraries/{fixture[key]}/join',outsider_token,'POST',{'access_code':code} if key=='other_private' else {})
   endpoints=[('/context','GET',None,CORE),('/catalogue/home','GET',None,CORE),('/catalogue/books','GET',None,CORE),('/catalogue/books/'+bid,'GET',None,CORE),('/catalogue/search?search='+DISTINCT,'GET',None,'http://127.0.0.1:8003'),('/catalogue/recommendations','POST',{'work_ids':[fixture['global_work_id']],'limit':50},CORE),('/intelligence/graph','GET',None,CORE),('/assets','GET',None,CORE),('/assets/'+fixture['member_asset']['asset_id'],'GET',None,CORE),('/assets/'+fixture['member_asset']['asset_id']+'/preview','GET',None,CORE)]
   denial=[]
   for label,token,status in [('unauthenticated',None,401),('authenticated other-library member',outsider_token,404)]:
    for suffix,method,body,base in endpoints:
     result=api('/libraries/'+lid+suffix,token,method,body,base,status);no_private(result);denial.append({'actor':label,'endpoint':suffix,'method':method,'status':status})
   for route in ['', '/catalogue','/books/'+bid,'/graph','/resources/'+fixture['member_asset']['asset_id']]:
    outsider.goto(BASE+'/libraries/'+lid+route);outsider.get_by_text('Unable to open this library',exact=True).wait_for(timeout=60000);assert not outsider.get_by_role('article',name=DISTINCT,exact=True).count()
   outsider.screenshot(path=str(R/'private_library_outsider_denied.png'),full_page=True);passed('Outsider direct UI routes and API deny concealed 404; unauthenticated API 401',denials=denial)
   platform_id,email,password=normal_account('Private Platform Boundary QA');proposal=plan(db,{'platform_assignments':[{'user_id':platform_id,'role':'PLATFORM_ADMIN','approved':True,'approved_by':'user explicit private isolation audit','approval_ref':'private-library-addendum-83474a69','reason':'Temporary local-development Platform-only boundary validation; revoke after audit.'}]});apply(db,proposal)
   platform=setup(browser.new_context(viewport={'width':1440,'height':900}));platform_token=sign(platform,email,password);api('/platform/summary',platform_token)
   platform_denials=[]
   for suffix,method,body,base in endpoints:
    result=api('/libraries/'+lid+suffix,platform_token,method,body,base,404);no_private(result);platform_denials.append({'endpoint':suffix,'status':404})
   platform.goto(BASE+f'/libraries/{lid}/catalogue');platform.get_by_text('Unable to open this library',exact=True).wait_for(timeout=60000);passed('Platform-only assignment provides no private tenant discovery access',user_id=platform_id,denials=platform_denials)
   for key in ['public','other_private']:
    r=api(f'/libraries/{fixture[key]}/catalogue/search?search={DISTINCT}',outsider_token,base='http://127.0.0.1:8003');no_private(r)
    r=api(f'/libraries/{fixture[key]}/catalogue/recommendations',outsider_token,'POST',{'work_ids':[fixture['global_work_id']],'limit':50});scoped(r['results'],fixture[key]);no_private(r)
   for token,label in [(outsider_token,'Outsider'),(platform_token,'Platform-only')]:
    for path in ['/books/?search='+DISTINCT,'/experimental/kg/books?q='+DISTINCT]:no_private(api(path,token))
    r=api('/search',token,'POST',{'query':DISTINCT,'top_k':10,'save_history':False},base='http://127.0.0.1:8003');no_private(r)
    r=api('/recommendations?limit=10&offset=0',token,base='http://127.0.0.1:8004');no_private(r)
    no_private(api('/books/'+fixture['global_work_id'],token));passed(label+' global Search Catalogue KG Recommendations and global linked work contain no private overlay')
   outsider.goto(BASE+'/search?q='+requests.utils.quote(DISTINCT));outsider.locator('.product-book-grid').wait_for(timeout=100000);assert not outsider.get_by_role('article',name=DISTINCT,exact=True).count();passed('Outsider global Search browser exposes no distinctive private title')
   member.goto(BASE+f'/libraries/{lid}/catalogue?search='+requests.utils.quote(DISTINCT));member.get_by_role('article',name=DISTINCT,exact=True).wait_for(timeout=100000)
   member.get_by_role('combobox',name='Switch patron library',exact=True).click();member.get_by_role('option',name='Public Archive QA B',exact=True).click();member.wait_for_url('**/libraries/'+fixture['public'],timeout=60000);member.get_by_role('article').first.wait_for(timeout=100000);assert not member.get_by_role('article',name=DISTINCT,exact=True).count()
   member.get_by_role('combobox',name='Switch patron library',exact=True).click();member.get_by_role('option',name='Private Archive QA A',exact=True).click();member.wait_for_url('**/libraries/'+lid,timeout=60000);member.get_by_role('article').first.wait_for(timeout=100000);passed('Private A → Public B → Private A uses exact library scoped state')
   member.get_by_role('button',name='Open account menu',exact=False).click();member.get_by_role('menuitem',name='Sign Out',exact=False).click();member.wait_for_url('**/login');assert member.evaluate("localStorage.getItem('luminar_workspace_contexts')")==None;passed('Logout removes private workspace context')
   sign(member,*outsider_login);member.goto(BASE+'/');assert member.evaluate("JSON.parse(localStorage.getItem('luminar_workspace_contexts')||'null')?.patronLibraryId")!=lid;passed('Outsider login cannot inherit prior private member context')
   member.get_by_role('button',name='Open account menu',exact=False).click();member.get_by_role('menuitem',name='Sign Out',exact=False).click();member.wait_for_url('**/login')
   member_token=sign(member,*member_login);member.goto(BASE+f'/libraries/{lid}');member.locator('#for-you-results article').first.wait_for(timeout=100000)
   next_button=member.locator('#for-you-results').get_by_role('button',name='Next Recommendations',exact=True);expect(next_button).to_be_enabled(timeout=60000)
   api(f'/libraries/{lid}/memberships/{membership["membership_id"]}',owner_token,'PATCH',{'status':'REMOVED'})
   with member.expect_response(lambda r:'/catalogue/recommendations' in r.url and r.status==404,timeout=60000):next_button.click()
   member.wait_for_timeout(500);remaining=member.locator('article[data-library-book-id]').count()
   passed('Membership revocation denies next Search Recommendations KG detail and asset requests',cached_private_cards_remaining=remaining)
   for suffix,method,body,base in endpoints:api('/libraries/'+lid+suffix,member_token,method,body,base,404)
   (R/'private_library_revocation_after.json').write_text(json.dumps({'cached_private_cards_remaining':remaining,'denial_status':404,'workspace_context':member.evaluate("JSON.parse(localStorage.getItem('luminar_workspace_contexts')||'null')?.patronLibraryId")}),encoding='utf8')
   assert remaining==0,'Revoked membership leaves cached private Home cards visible'
   passed('Revoked private frontend cached content cleared');save('PASS');browser.close()
 except Exception:
  save('PARTIAL');raise
 finally:
  for uid in accounts:
   db.users.update_one({'user_id':uid},{'$set':{'is_active':False}})
   db.platform_role_assignments.update_many({'user_id':uid,'status':'ACTIVE'},{'$set':{'status':'REVOKED','revocation_reason':'Completed local private isolation QA'}})
