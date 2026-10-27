"""Finish read-only Staff/provider/performance checks without rebuilding fixtures."""
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import recommendation_runtime_browser as qa
from playwright.sync_api import sync_playwright
report=json.loads((ROOT/'reports/recommendation_browser_validation.json').read_text(encoding='utf8'))
qa.checks=report['checks'];qa.network=report['network'];qa.errors=report['page_errors']
qa.fixture=json.loads((ROOT/'reports/recommendation_runtime_fixture.json').read_text(encoding='utf8'))
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    owner=qa.page_setup(browser.new_context(viewport={'width':1440,'height':900}))
    qa.sign(owner,*qa.credentials('staff'));owner.goto(qa.BASE+f'/staff/libraries/{qa.TEST}/catalogue?view=for-you')
    owner.locator('.staff-workspace').wait_for(timeout=90000)
    owner.get_by_role('heading',name='Browse Books',exact=True).wait_for(timeout=90000)
    owner.locator('.product-book-grid article > a:first-of-type').first.wait_for(timeout=90000)
    links=owner.locator('.product-book-grid article > a:first-of-type').evaluate_all('(es)=>es.map(e=>e.getAttribute("href"))')
    assert links and all(f'/staff/libraries/{qa.TEST}/books/' in href for href in links)
    qa.passed('Staff shared discovery remains canonical Staff catalogue, without patron authority',links=links)
    patron=qa.page_setup(browser.new_context(viewport={'width':1440,'height':900}));token=qa.sign(patron,*qa.credentials('patron'))
    # Real cold-start was measured with a clean QA account. Reproduce the same
    # empty recommender response locally to verify its View All repair safely.
    patron.route('**/recommendation-api/recommendations?**',lambda route:route.fulfill(status=200,json={'recommendations':[],'has_more':False}))
    patron.goto(qa.BASE+'/');region=qa.rail(patron)
    region.get_by_text('Popular books',exact=True).wait_for(timeout=60000)
    assert region.get_by_role('link',name='VIEW ALL',exact=True).get_attribute('href')=='/catalog?sort=popular'
    region.get_by_role('link',name='VIEW ALL',exact=True).click();patron.wait_for_url('**/catalog?sort=popular')
    patron.get_by_role('heading',name='Popular',exact=True).wait_for(timeout=60000)
    patron.locator('.product-book-grid article').first.wait_for(timeout=60000)
    qa.passed('Cold global Popular fallback View All keeps Popular provider',route='/catalog?sort=popular',
        test_method='Browser response fixture reproduces clean-account empty recommendations, real Core popular results')
    patron.unroute('**/recommendation-api/recommendations?**')
    seed=qa.fixture['preference_seed_work_id']
    patron.goto(qa.BASE+'/book/'+seed)
    with patron.expect_response(lambda r:'/kg/books/' in r.url and '/more-like-this' in r.url,timeout=60000) as related:
        patron.get_by_role('button',name='More Like This',exact=True).click(timeout=60000)
    response=related.value;data=response.json()
    assert response.status in [200,404,409,503]
    qa.passed('More Like This uses separate canonical graph endpoint',endpoint='/api/kg/books/'+seed+'/more-like-this',
        http_status=response.status,graph_version=data.get('graph_version'),result_count=len(data.get('recommendations',[])),
        availability='AVAILABLE' if response.status==200 else 'EXPLICIT_GRAPH_UNAVAILABLE',
        provider='GLOBAL_KG_METADATA_RELATIONSHIPS',for_you_provider_unchanged=True)
    pool=qa.api('/recommendations?limit=50',token,base='http://127.0.0.1:8004')
    samples=[]
    for i in range(5):
        for provider,path,method,body,base in [('global_cached','/recommendations?limit=50','GET',None,'http://127.0.0.1:8004'),
             ('tenant_projection',f'/libraries/{qa.TEST}/catalogue/recommendations','POST',{'work_ids':[r['work_id'] for r in pool['recommendations']],'limit':50},qa.CORE)]:
            start=time.perf_counter();result=qa.api(path,token,method,body,base)
            samples.append({'provider':provider,'ms':(time.perf_counter()-start)*1000,'final_count':len(result.get('results',result.get('recommendations',[])))})
    (ROOT/'reports/recommendation_runtime_latency_samples.json').write_text(json.dumps(samples,indent=2),encoding='utf8')
    qa.passed('Warm global cached pool and TEST canonical projection latency sampled',samples_per_provider=5)
    qa.save('PASS');browser.close()
print('PASS final Staff and performance browser closure')
