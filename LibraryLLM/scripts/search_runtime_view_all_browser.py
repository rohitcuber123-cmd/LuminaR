"""Focused actual-UI proof of the For You View All routing repair."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright
from scripts.full_product_browser_session import credentials
BASE='http://127.0.0.1:5173';TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae';checks=[]
with sync_playwright() as p:
  browser=p.chromium.launch(headless=True)
  for account in ['staff','patron']:
    print('Checking '+account+' View All',flush=True)
    context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page()
    email,password=credentials(account);page.goto(BASE+'/login')
    page.locator('input[type=email]').fill(email);page.locator('input[type=password]').fill(password)
    page.get_by_role('button',name='Sign In',exact=True).click();page.wait_for_url(lambda u:'/login' not in str(u),timeout=60000)
    if account=='patron':
      page.goto(BASE+f'/libraries/{TEST}')
      page.locator('#for-you-results').get_by_role('link',name='VIEW ALL',exact=True).click(timeout=60000)
      page.wait_for_url('**/*view=for-you*',timeout=60000)
    else:page.goto(BASE+f'/staff/libraries/{TEST}/catalogue?view=for-you')
    page.locator('#catalogue-query').wait_for(timeout=90000)
    page.locator('.product-catalogue .animate-pulse').first.wait_for(state='detached',timeout=90000)
    calls=[];page.on('request',lambda r:calls.append(r.url) if '/catalogue/' in r.url else None)
    page.locator('#catalogue-query').fill('community memories')
    with page.expect_response(lambda r:'/catalogue/search?' in r.url and r.status==200,timeout=120000) as response:
      page.locator('form.product-catalogue-search').get_by_role('button',name='Search',exact=True).click()
    body=response.value.json();assert body['source']['search_source']=='TENANT_SEMANTIC'
    assert body['results'][0]['title']=='TEST Community Oral History Handbook'
    page.get_by_text('Library semantic search',exact=True).wait_for(timeout=60000)
    assert not any('/recommendations' in url for url in calls)
    checks.append({'scenario':account+' For You View All submitted query executes tenant HNSW',
       'status':'PASS','route':page.url.removeprefix(BASE),'source':body['source'],'top_title':body['results'][0]['title'],
       'recommendation_request_after_query':False,'network_paths':calls})
    print('PASS '+account+' View All semantic query',flush=True)
    if account=='patron':
      with page.expect_response(lambda r:'/catalogue/recommendations' in r.url and r.status==200,timeout=90000):
        page.get_by_role('button',name='Clear search',exact=True).click()
      checks.append({'scenario':'Clearing query retains original For You recommendation provider','status':'PASS'})
    page.screenshot(path=str(ROOT/f'reports/search_runtime_view_all_{account}.png'),full_page=True)
    context.close()
  browser.close()
(ROOT/'reports/search_view_all_browser.json').write_text(json.dumps({'status':'PASS','checks':checks},indent=2),encoding='utf8')
print('PASS Staff/Patron View All semantic search and unqueried recommendation preservation')
