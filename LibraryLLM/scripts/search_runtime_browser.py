"""Real Chromium search execution evidence. Runtime-only QA credentials."""
import json, sys, time, requests
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse, parse_qs
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright, expect
from scripts.full_product_browser_session import credentials
from backend.database.mongodb import db
BASE='http://127.0.0.1:5173';CORE='http://127.0.0.1:8002';SEARCH='http://127.0.0.1:8003'
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae';REPORTS=ROOT/'reports'
checks=[];responses=[];errors=[];pending=[]

def save(status='IN_PROGRESS'):
    while pending:capture(pending.pop(0))
    (REPORTS/'search_browser_validation.json').write_text(json.dumps({'status':status,'browser':'Chromium',
        'checks':checks,'responses':responses,'page_errors':errors},indent=2),encoding='utf8')
def passed(name,**details):
    checks.append({'scenario':name,'status':'PASS',**details});save();print('PASS '+name,flush=True)
def api(path,token,method='GET',body=None,base=CORE):
    for attempt in range(10):
        r=requests.request(method,base+path,headers={'Authorization':'Bearer '+token},json=body,timeout=120)
        if r.status_code!=503:break
        time.sleep(.4)
    r.raise_for_status();return r.json()
def sign(page,account):
    email,password=credentials(account);page.goto(BASE+'/login')
    page.locator('input[type=email]').fill(email);page.locator('input[type=password]').fill(password)
    page.get_by_role('button',name='Sign In',exact=True).click()
    page.wait_for_url(lambda u:'/login' not in str(u),timeout=60000)
    return page.evaluate("localStorage.getItem('luminar_token')")
def capture(r):
    path=urlparse(r.url).path
    if '/catalogue/search' in path or path=='/search-api/search' or '/intelligence/graph' in path:
        try:
            body=r.json()
            responses.append({'endpoint':path,'query_parameters':parse_qs(urlparse(r.url).query),
              'method':r.request.method,'status':r.status,'source':body.get('source'),
              'ranking':body.get('ranking'),'timing_ms':body.get('timing_ms'),
              'results':[{k:v.get(k) for k in ('library_id','library_book_id','work_id','title','source')} for v in body.get('results',[])],
              'graph_nodes':len(body.get('nodes',[]))})
        except Exception as e:errors.append(type(e).__name__)
def query(page,path,text,header=False):
    page.goto(BASE+path);page.locator('#main-content').wait_for()
    if header:
        page.locator('.global-header').get_by_role('button',name='Search the catalog',exact=True).click()
        field=page.locator('#header-catalog-search');form=page.locator('form.global-search')
    else:
        field=page.locator('#catalogue-query');form=page.locator('form.product-catalogue-search')
    field.wait_for(timeout=90000);field.fill(text)
    with page.expect_response(lambda r: ('/catalogue/search?' in r.url or urlparse(r.url).path=='/search-api/search') and r.status!=503,timeout=120000) as wait:
        form.get_by_role('button',name='Search',exact=True).click()
    r=wait.value;assert r.status==200,(r.status,r.text());body=r.json()
    page.locator('.product-catalogue .animate-pulse').first.wait_for(state='detached',timeout=120000)
    assert not page.get_by_text('Unable to load books',exact=True).count()
    return body

if __name__=='__main__':
  sys.stdout.reconfigure(encoding='utf8')
  try:
    with sync_playwright() as p:
      browser=p.chromium.launch(headless=True)
      staff=browser.new_context(viewport={'width':1440,'height':900});page=staff.new_page()
      page.on('response',lambda r:pending.append(r) if '/search-api/' in r.url or '/intelligence/graph' in r.url else None)
      page.on('pageerror',lambda e:errors.append(str(e)))
      token=sign(page,'staff')
      for q,target in [('beginner computer networking','TEST Campus Network Practice Workbook'),
                       ('accessibility transportation','Mobility and transport for elderly and handicapped persons'),
                       ('community memories','TEST Community Oral History Handbook'),
                       ('equipment design workshop','TEST Makerspace Equipment Guide')]:
        result=query(page,f'/staff/libraries/{TEST}/catalogue',q)
        assert result['source']['search_source']=='TENANT_SEMANTIC',result['source']
        titles=[r['title'] for r in result['results']];assert target in titles,(q,titles)
        control=api(f'/libraries/{TEST}/catalogue/books?staff=true&search='+requests.utils.quote(q),token)
        passed('TEST Staff semantic: '+q,query=q,source=result['source'],target_rank=titles.index(target)+1,
               lexical_baseline=control['results'],final_results=[{'id':r['library_book_id'],'title':r['title']} for r in result['results']])
      page.screenshot(path=str(REPORTS/'search_runtime_TEST_staff.png'),full_page=True)
      result=query(page,f'/staff/libraries/{TEST}', 'community memories',header=True)
      assert result['source']['search_source']=='TENANT_SEMANTIC'
      passed('Staff header Search reaches tenant semantic catalogue',route=urlparse(page.url).path)
      fixture=REPORTS/'search_runtime_fixture.json'
      if fixture.exists():local=json.loads(fixture.read_text())
      else:
        local=api('/libraries/register',token,'POST',{'name':'Search Runtime QA','slug':'search-runtime-'+uuid4().hex[:12],
                  'library_type':'PUBLIC_LIBRARY','access_mode':'PUBLIC'})['library']
        fixture.write_text(json.dumps(local,indent=2),encoding='utf8')
        for title,subject,desc in [('Campus Network Practice Workbook','Computer networks','Hands-on campus routing and connectivity exercises'),
             ('Community Oral History Handbook','Local history','Preserving residents recollections in community archives'),
             ('Makerspace Equipment Guide','Engineering','Operating workshop tools for fabrication and prototyping'),
             ('Coastal Bird Watching','Natural history','Identifying shorebirds and seabirds')]:
          api(f'/libraries/{local["library_id"]}/inventory/books',token,'POST',{'title':title,'subjects':[subject],
              'authors':['Runtime QA'],'description':desc,'create_physical_holding':True,'copies':1,'shelf_location':'QA-SEARCH',
              'idempotency_key':str(uuid4())})
      lid=local['library_id'];status=api(f'/libraries/{lid}/intelligence',token)
      if status['search']['status']=='NOT_BUILT':
        result=query(page,f'/staff/libraries/{lid}/catalogue','beginner computer networking')
        assert result['source']['search_source']=='LOCAL_FALLBACK' and result['results']==[]
        passed('Disposable NOT_BUILT uses local fallback',library_id=lid,source=result['source'])
        page.goto(BASE+f'/staff/libraries/{lid}/intelligence')
        with page.expect_response(lambda r:'/intelligence/builds' in r.url and r.request.method=='POST',timeout=60000) as build:
          page.get_by_role('button',name='Build Search Index',exact=True).click()
          page.get_by_role('dialog').get_by_role('button',name='Build Search Index',exact=True).click()
        assert build.value.status==202
        for attempt in range(240):
          status=api(f'/libraries/{lid}/intelligence',token)
          if status['search']['status']=='READY':break
          assert status['search']['status'] not in ['FAILED','RECOVERY_REQUIRED'],status['search']
          time.sleep(1)
        assert status['search']['status']=='READY'
        passed('Disposable Search Index built through actual confirmation UI',library_id=lid,generation=status['search']['active_generation_id'])
      result=query(page,f'/staff/libraries/{lid}/catalogue','beginner computer networking')
      assert result['source']['search_source']=='TENANT_SEMANTIC'
      assert 'Campus Network Practice Workbook' in [r['title'] for r in result['results']]
      assert all(r['library_id']==lid and r['source']=='LIBRARY' for r in result['results'])
      assert status['kg']['status']=='NOT_BUILT'
      passed('Disposable READY HNSW works with KG NOT_BUILT and is isolated from TEST',library_id=lid,source=result['source'],results=[r['title'] for r in result['results']])
      query(page,f'/staff/libraries/{TEST}/catalogue','beginner computer networking')
      passed('Same query switched back to TEST keeps selected tenant',library_id=TEST)
      page.goto(BASE+f'/staff/libraries/{TEST}/graph')
      page.locator('[data-graph-source="TENANT_KG"]').wait_for(timeout=60000)
      passed('TEST Graph Lab uses tenant KG separately')
      for path,header in [('/catalog',False),('/search',False),('/Search',False),('/',True)]:
        result=query(page,path,'wizard boarding school adventures',header)
        assert result['results'] and result['ranking']['reranked_count']>0
        passed('Global UI Search '+path,endpoint='/search-api/search',ranking=result['ranking'],results=[r['title'] for r in result['results']])
      page.screenshot(path=str(REPORTS/'search_runtime_global.png'),full_page=True)
      patron=browser.new_context(viewport={'width':1440,'height':900});pp=patron.new_page()
      pp.on('response',lambda r:pending.append(r) if '/search-api/' in r.url or '/intelligence/graph' in r.url else None)
      sign(pp,'patron')
      result=query(pp,f'/libraries/{TEST}/catalogue','accessibility transportation')
      assert result['source']['search_source']=='TENANT_SEMANTIC'
      assert any(r['title']=='Mobility and transport for elderly and handicapped persons' for r in result['results'])
      assert all(r['library_id']==TEST and r['source']=='LIBRARY' for r in result['results'])
      passed('TEST Patron nonliteral semantic query',source=result['source'])
      result=query(pp,f'/libraries/{TEST}','community memories',header=True)
      assert result['source']['search_source']=='TENANT_SEMANTIC'
      passed('Patron header Search reaches tenant semantic catalogue',route=urlparse(pp.url).path)
      pp.screenshot(path=str(REPORTS/'search_runtime_TEST_patron.png'),full_page=True)
      # Bounded warm performance sampling. No ranking configuration changes.
      samples=[]
      for mode,lid2,q in [('tenant_hnsw',TEST,'beginner computer networking'),('local_fallback',lid,'Campus Network Practice Workbook')]:
        for i in range(5):
          path=f'/libraries/{lid2}/catalogue/'+('search' if mode=='tenant_hnsw' else 'books')+'?staff=true&search='+requests.utils.quote(q)
          start=time.perf_counter();body=api(path,token,base=SEARCH if mode=='tenant_hnsw' else CORE)
          samples.append({'mode':mode,'ms':(time.perf_counter()-start)*1000,'results':len(body['results'])})
      (REPORTS/'search_runtime_latency_samples.json').write_text(json.dumps(samples,indent=2),encoding='utf8')
      save('PASS');browser.close()
  except Exception as e:
    save('FAIL');print(type(e).__name__+': '+str(e),flush=True);raise
