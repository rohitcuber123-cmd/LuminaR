"""Read-only Chromium check of operational lookup after the scoped repair."""
import sys,json
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright
from scripts.full_product_browser_session import credentials
BASE='http://127.0.0.1:5173'
lid=json.loads((ROOT/'reports/search_runtime_fixture.json').read_text())['library_id']
checks=[]
with sync_playwright() as p:
  browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':900})
  page.goto(BASE+'/login');email,password=credentials('staff')
  page.locator('input[type=email]').fill(email);page.locator('input[type=password]').fill(password)
  page.get_by_role('button',name='Sign In',exact=True).click();page.wait_for_url(lambda u:'/login' not in str(u),timeout=60000)
  page.goto(BASE+f'/staff/libraries/{lid}/inventory');field=page.get_by_role('textbox',name='Search library inventory')
  field.wait_for(timeout=60000);field.fill('QA-SEARCH')
  with page.expect_response(lambda r:'/inventory/books?' in r.url and 'QA-SEARCH' in r.url and r.status==200,timeout=60000) as result:
    page.locator('form.ui-filter-toolbar').get_by_role('button',name='Search',exact=True).click()
  body=result.value.json();assert body['total']==4 and all(r['library_id']==lid for r in body['results'])
  page.get_by_text('4 records',exact=True).wait_for(timeout=60000)
  checks.append({'scenario':'Current shelf deterministic lookup','endpoint':urlparse(result.value.url).path,'total':4,'status':'PASS'})
  page.screenshot(path=str(ROOT/'reports/search_runtime_inventory.png'),full_page=True)
  page.goto(BASE+f'/staff/libraries/{lid}/catalogue');page.locator('#catalogue-query').fill('Campus Network Practice Workbook')
  with page.expect_response(lambda r:'/catalogue/search?' in r.url and r.status==200,timeout=60000) as result:
    page.locator('form.product-catalogue-search').get_by_role('button',name='Search',exact=True).click()
  body=result.value.json();assert body['source']['search_source']=='TENANT_SEMANTIC'
  assert body['results'][0]['title']=='Campus Network Practice Workbook'
  checks.append({'scenario':'Exact catalogue title through real semantic endpoint','source':body['source'],'status':'PASS'})
  browser.close()
(ROOT/'reports/search_inventory_browser.json').write_text(json.dumps({'status':'PASS','checks':checks},indent=2),encoding='utf8')
print('PASS inventory shelf and semantic exact title browser checks')
