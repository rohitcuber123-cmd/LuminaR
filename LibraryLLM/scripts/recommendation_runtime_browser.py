"""Real Chromium recommendation audit; clean local QA account, no credentials persisted."""
import json,sys,time,secrets,requests
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright,expect
from scripts.full_product_browser_session import credentials
from backend.database.mongodb import db
from backend.services import auth_service
BASE='http://127.0.0.1:5173';CORE='http://127.0.0.1:8002';TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
REPORTS=ROOT/'reports';checks=[];pending=[];network=[];errors=[];uid=None;fixture={}

def drain():
    while pending:
        r=pending.pop(0);path=urlparse(r.url).path
        if not ('/recommendations' in path or '/catalogue/home' in path or '/books/popular' in path):continue
        try:
            b=r.json();rows=b.get('results',b.get('recommendations',b.get('for_you',[])))
            network.append({'endpoint':path,'url':r.url.removeprefix(BASE),'status':r.status,'method':r.request.method,
               'source':b.get('source'),'ranking':b.get('ranking'),'intersection_count':b.get('intersection_count'),
               'offset':b.get('offset'),'total':b.get('total_ranked_candidates'),'has_more':b.get('has_more'),
               'results':[{k:v.get(k) for k in ['library_id','library_book_id','global_work_id','work_id','title','source']} for v in rows]})
        except Exception:pass
def save(status='IN_PROGRESS'):
    drain();(REPORTS/'recommendation_browser_validation.json').write_text(json.dumps({'status':status,'browser':'Chromium',
         'checks':checks,'network':network,'page_errors':errors,'fixtures':fixture},indent=2),encoding='utf8')
def passed(name,**values):
    checks.append({'scenario':name,'status':'PASS',**values});save();print('PASS '+name,flush=True)
def api(path,token,method='GET',body=None,base=CORE):
    for attempt in range(10):
        r=requests.request(method,base+path,headers={'Authorization':'Bearer '+token},json=body,timeout=100)
        if r.status_code!=503:break
        time.sleep(.5)
    r.raise_for_status();return r.json()
def sign(page,email,password):
    page.goto(BASE+'/login');page.locator('input[type=email]').fill(email);page.locator('input[type=password]').fill(password)
    page.get_by_role('button',name='Sign In',exact=True).click();page.wait_for_url(lambda u:'/login' not in str(u),timeout=60000)
    return page.evaluate("localStorage.getItem('luminar_token')")
def page_setup(context):
    page=context.new_page();page.on('response',lambda r:pending.append(r) if any(x in r.url for x in ['/recommendation-api/','/catalogue/','/books/popular']) else None)
    page.on('pageerror',lambda e:errors.append(str(e)));return page
def rail(page):
    region=page.locator('#for-you-results');region.wait_for(timeout=100000)
    region.locator('article').first.wait_for(timeout=100000);return region
def ids(region):
    return region.locator('article > a:first-of-type').evaluate_all('(es)=>es.map(e=>e.getAttribute("href"))')
def scoped(region,lid):
    links=ids(region);assert links and all(f'/libraries/{lid}/books/' in p for p in links),links
    assert len(set(links))==len(links);return links
def next_page(page,region,lid=None):
    before=ids(region);button=region.get_by_role('button',name='Next Recommendations',exact=True)
    expect(button).to_be_enabled(timeout=100000);button.click()
    expect(region.locator('article > a:first-of-type').first).not_to_have_attribute('href',before[0],timeout=100000)
    return scoped(region,lid) if lid else ids(region)

if __name__=='__main__':
 sys.stdout.reconfigure(encoding='utf8')
 assert db.name=='luminar_library' and db.client.address[0] in ('localhost','127.0.0.1','::1')
 previous=REPORTS/'recommendation_runtime_fixture.json'
 if previous.exists():fixture={key:value for key,value in json.loads(previous.read_text(encoding='utf8')).items() if key in ['A','B']}
 email='recommendation-runtime-'+uuid4().hex[:12]+'@example.com';password=secrets.token_urlsafe(32);mail={}
 original=auth_service.send_otp_email
 try:
    auth_service.send_otp_email=lambda address,name,otp:mail.update({address:otp}) or True
    user=auth_service.register_user('LuminaR Recommendation Runtime QA',email,password);uid=user['user_id']
    assert auth_service.verify_email_otp(email,mail.pop(email))
 finally:auth_service.send_otp_email=original
 allowed=[uid,db.users.find_one({'email':'karthikeya.ixa.10@gmail.com'})['user_id']]
 (ROOT/'.scratch/recommendation-runtime/config.json').write_text(json.dumps({'user_ids':allowed}),encoding='utf8')
 fixture['qa_user_id']=uid;fixture['qa_email']=email
 try:
  with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    owner_context=browser.new_context(viewport={'width':1440,'height':900});owner=page_setup(owner_context)
    owner_token=sign(owner,*credentials('staff'))
    for key in ['A','B']:
        if key in fixture:continue
        lib=api('/libraries/register',owner_token,'POST',{'name':'Recommendation Runtime '+key,'slug':'recommendation-runtime-'+key.lower()+'-'+uuid4().hex[:8],
             'library_type':'PUBLIC_LIBRARY','access_mode':'PUBLIC'})['library']
        fixture[key]=lib['library_id']
    context=browser.new_context(viewport={'width':1440,'height':900});page=page_setup(context);token=sign(page,email,password)
    cold=api('/recommendations?limit=10',token,base='http://127.0.0.1:8004')
    assert cold['recommendations']==[]
    page.goto(BASE+'/');region=rail(page);region.get_by_text('Popular books',exact=True).wait_for(timeout=100000)
    passed('Clean user global cold start uses explicitly labelled Popular fallback',history_count=db.search_history.count_documents({'user_id':uid}),global_recommendation_count=0,popular_cards=len(ids(region)))
    for key in ['A','B']:api(f'/libraries/{fixture[key]}/join',token,'POST',{})
    page.goto(BASE+f'/libraries/{fixture["A"]}');region=rail(page)
    page.get_by_text('Global Catalogue',exact=False).first.wait_for(timeout=60000)
    assert region.locator('article[data-library-book-id]').count()==0
    assert all('/global-books/' in link or '/book/' in link for link in ids(region))
    passed('Empty Patron library uses labelled global discovery',library_id=fixture['A'])
    # Meaningful catalogue records; preference tests use actual persisted Search input.
    for key in ['A','B']:
        lid=fixture[key]
        for index in range(25):
            topic=(['Campus routing','Network security','Wireless planning','Systems administration','Distributed computing'] if key=='A' else
                   ['Oral history','Community archives','Local museums','Family memories','Historic preservation'])[index%5]
            api(f'/libraries/{lid}/inventory/books',owner_token,'POST',{'title':f'{topic} Practical Guide {index+1}',
                'subjects':['Computer networks' if key=='A' else 'Local history',topic],'authors':[f'QA Author {index+1}'],
                'description':f'Practical exercises and case studies in {topic.lower()}.','create_physical_holding':True,'copies':1,
                'shelf_location':'QA-'+key,'idempotency_key':str(uuid4())})
    page.goto(BASE+f'/libraries/{fixture["A"]}');region=rail(page);first=scoped(region,fixture['A'])
    assert db.search_history.count_documents({'user_id':uid})==0
    passed('Clean user populated tenant cold start switches to canonical local acquisitions',library_id=fixture['A'],links=first)
    before=api(f'/libraries/{fixture["A"]}/catalogue/recommendations',token,'POST',{'work_ids':[],'limit':50})
    status=api(f'/libraries/{fixture["A"]}/intelligence',owner_token);assert status['search']['status']=='NOT_BUILT' and status['kg']['status']=='NOT_BUILT'
    passed('Tenant For You before HNSW build',source=before['source'],ranking=before['ranking'],results=[r['library_book_id'] for r in before['results']])
    owner.goto(BASE+f'/staff/libraries/{fixture["A"]}/intelligence')
    with owner.expect_response(lambda r:'/intelligence/builds' in r.url and r.request.method=='POST',timeout=60000) as built:
        owner.get_by_role('button',name='Build Search Index',exact=True).click()
        owner.get_by_role('dialog').get_by_role('button',name='Build Search Index',exact=True).click()
    assert built.value.status==202
    for attempt in range(240):
        status=api(f'/libraries/{fixture["A"]}/intelligence',owner_token)
        if status['search']['status']=='READY':break
        assert status['search']['status'] not in ['FAILED','RECOVERY_REQUIRED']
        time.sleep(1)
    assert status['search']['status']=='READY'
    after=api(f'/libraries/{fixture["A"]}/catalogue/recommendations',token,'POST',{'work_ids':[],'limit':50})
    assert [r['library_book_id'] for r in after['results']]==[r['library_book_id'] for r in before['results']]
    page.reload();region=rail(page);scoped(region,fixture['A'])
    passed('Tenant recommendations unchanged after HNSW READY with KG NOT_BUILT',ranking=after['ranking'],generation=status['search']['active_generation_id'],local_result_count=len(after['results']))
    # Query through actual global UI, then fresh login supplies a new accepted cache session.
    page.goto(BASE+'/search');page.locator('#catalogue-query').fill('beginner computer networking')
    with page.expect_response(lambda r:urlparse(r.url).path=='/search-api/search' and r.status==200,timeout=100000):
        page.locator('form.product-catalogue-search').get_by_role('button',name='Search',exact=True).click()
    page.locator('.product-catalogue .animate-pulse').first.wait_for(state='detached',timeout=100000)
    page.get_by_role('button',name='Open account menu',exact=False).click();page.get_by_role('menuitem',name='Sign Out',exact=False).click();page.wait_for_url('**/login')
    token=sign(page,email,password);page.goto(BASE+'/');region=rail(page)
    expect(region.get_by_role('button',name='Next Recommendations',exact=True)).to_be_enabled(timeout=100000)
    recommendations=api('/recommendations?limit=50',token,base='http://127.0.0.1:8004')
    assert recommendations['recommendations']
    seed=recommendations['recommendations'][0];fixture['preference_seed_work_id']=seed['work_id']
    subjects=seed.get('subjects') or '';assert any(term in str(subjects).lower() for term in ['computer','network','technolog','program','systems'])
    passed('Global personalized For You uses real nonliteral persisted search preference',query='beginner computer networking',profile_search_count=db.search_history.count_documents({'user_id':uid}),top_title=seed['title'],top_subjects=subjects)
    global_first=ids(region);global_second=next_page(page,region)
    assert not set(global_first)&set(global_second)
    region.get_by_role('button',name='Previous Recommendations',exact=True).click()
    expect(region.locator('article > a:first-of-type').first).to_have_attribute('href',global_first[0],timeout=60000)
    region.get_by_role('link',name='VIEW ALL',exact=True).click();page.wait_for_url('**/*view=for-you*')
    page.locator('.product-catalogue .animate-pulse').first.wait_for(state='detached',timeout=100000)
    passed('Global recommendation Next/Previous/View All retains recommender provider',first=global_first,second=global_second)
    # A owns a globally preferred work; B does not. Keep TEST unchanged.
    canonical=db.books.find_one({'work_id':seed['work_id']})
    linked=api(f'/libraries/{fixture["A"]}/inventory/books',owner_token,'POST',{'title':canonical['title'],
         'subjects':[s.strip() for s in str(canonical.get('subjects') or 'Technology').split('|') if s.strip()][:30],
         'global_work_id':seed['work_id'],'create_physical_holding':True,'copies':1,'shelf_location':'QA-LINKED','idempotency_key':str(uuid4())})
    fixture['linked_library_book_id']=linked['library_book_id']
    # Metadata change intentionally makes only the disposable generation STALE; no rebuild.
    page.goto(BASE+f'/libraries/{fixture["A"]}');region=rail(page);a_first=scoped(region,fixture['A'])
    assert any(linked['library_book_id'] in link for link in a_first)
    a_second=next_page(page,region,fixture['A']);a_third=next_page(page,region,fixture['A'])
    assert not(set(a_first)&set(a_second) or set(a_first)&set(a_third) or set(a_second)&set(a_third))
    region.get_by_role('button',name='Previous Recommendations',exact=True).click()
    expect(region.locator('article > a:first-of-type').first).to_have_attribute('href',a_second[0],timeout=60000)
    region.get_by_role('button',name='Scroll right',exact=True).click()
    page.wait_for_function('document.querySelector("#for-you-results .product-book-rail").scrollLeft>0')
    expect(region.get_by_role('button',name='Scroll left',exact=True)).to_be_enabled()
    region.get_by_role('button',name='Scroll left',exact=True).click()
    passed('Tenant Next twice/Previous/carousel traversal preserve provider and unique local pages',library_id=fixture['A'],pages=[a_first,a_second,a_third])
    region.get_by_role('link',name='VIEW ALL',exact=True).click();page.wait_for_url('**/*view=for-you*')
    page.locator('.product-catalogue .animate-pulse').first.wait_for(state='detached',timeout=100000)
    assert all(f'/libraries/{fixture["A"]}/books/' in href for href in page.locator('.product-book-grid article > a:first-of-type').evaluate_all('(es)=>es.map(e=>e.getAttribute("href"))'))
    page.go_back();region=rail(page);scoped(region,fixture['A']);page.go_forward()
    passed('Tenant View All and browser Back/Forward retain library context',library_id=fixture['A'])
    page.goto(BASE+f'/libraries/{fixture["A"]}');region=rail(page);scoped(region,fixture['A'])
    page.get_by_role('combobox',name='Switch patron library',exact=True).click()
    page.get_by_role('option',name='Recommendation Runtime B',exact=False).click()
    page.wait_for_url(BASE+f'/libraries/{fixture["B"]}',timeout=60000);region=rail(page);b_first=scoped(region,fixture['B'])
    assert not any(linked['library_book_id'] in link for link in b_first)
    passed('Same GENERAL_USER switches A to B without cache/ownership leakage',A=fixture['A'],B=fixture['B'],B_links=b_first)
    page.screenshot(path=str(REPORTS/'recommendation_runtime_library_B.png'),full_page=True)
    # Search failure is simulated at the browser boundary for tenant candidate retrieval.
    page.route('**/recommendation-api/recommendations?**',lambda route:route.fulfill(status=503,json={'detail':'QA dependency unavailable'}))
    page.goto(BASE+f'/libraries/{fixture["B"]}');region=rail(page);scoped(region,fixture['B'])
    passed('Unavailable global recommendation dependency keeps safe local tenant discovery',library_id=fixture['B'])
    page.unroute('**/recommendation-api/recommendations?**')
    # Existing TEST Patron acceptance and several pages, no TEST profile writes.
    patron_context=browser.new_context(viewport={'width':1440,'height':900});patron=page_setup(patron_context)
    sign(patron,*credentials('patron'));patron.goto(BASE+f'/libraries/{TEST}');region=rail(patron)
    test_pages=[scoped(region,TEST)]
    for i in range(3):test_pages.append(next_page(patron,region,TEST))
    assert len(set(sum(test_pages,[])))==len(sum(test_pages,[]))
    region.get_by_role('button',name='Previous Recommendations',exact=True).click()
    expect(region.locator('article > a:first-of-type').first).to_have_attribute('href',test_pages[-2][0],timeout=100000)
    passed('TEST Patron For You and three next pages remain TEST-only',pages=test_pages)
    patron.screenshot(path=str(REPORTS/'recommendation_runtime_TEST.png'),full_page=True)
    owner.goto(BASE+f'/staff/libraries/{TEST}/catalogue?view=for-you')
    owner.locator('.product-catalogue .animate-pulse').first.wait_for(state='detached',timeout=100000)
    assert owner.locator('.staff-workspace').count() and all(f'/staff/libraries/{TEST}/books/' in href for href in owner.locator('.product-book-grid article > a:first-of-type').evaluate_all('(es)=>es.map(e=>e.getAttribute("href"))'))
    passed('Staff shared discovery remains canonical Staff catalogue, without patron authority')
    # Warm performance of candidate pool and canonical tenant projection, five samples.
    timings=[]
    for i in range(5):
        for label,path,method,body,base in [('global_cached','/recommendations?limit=50','GET',None,'http://127.0.0.1:8004'),
                ('tenant_projection',f'/libraries/{fixture["B"]}/catalogue/recommendations','POST',{'work_ids':[r['work_id'] for r in recommendations['recommendations']],'limit':50},CORE)]:
            started=time.perf_counter();body=api(path,token,method,body,base);timings.append({'provider':label,'ms':(time.perf_counter()-started)*1000})
    (REPORTS/'recommendation_runtime_latency_samples.json').write_text(json.dumps(timings,indent=2),encoding='utf8')
    save('PASS');browser.close()
 except Exception:
    save('FAIL');raise
 finally:
    if uid:
        db.users.update_one({'user_id':uid},{'$set':{'is_active':False}})
        fixture['qa_account_disabled_after_review']=True
        (REPORTS/'recommendation_runtime_fixture.json').write_text(json.dumps(fixture,indent=2),encoding='utf8')
