"""Real Chromium batch: normal QA login, native layouts and scoped live data."""
import sys,time,requests
sys.path.insert(0,str(ROOT))
from backend.database.mongodb import db
fixtures=json.loads((REPORTS/'institution_v2g_fixtures.json').read_text())
VIEWPORTS=[(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]
deadline=time.monotonic()+180
while time.monotonic()<deadline:
    try:
        if requests.get('http://127.0.0.1:8003/health',timeout=3).ok and requests.get('http://127.0.0.1:8002/health',timeout=3).ok:break
    except requests.RequestException:pass
    time.sleep(.5)
checks=[];responsive=[];badges=[];controls=[]
def receipt(status='IN_PROGRESS'):
    put('institution_v2g_browser.json',{'status':status,'browser':browser.version,'checks':checks,'responsive':responsive,'badges':badges,'controls':controls,'javascript_errors':errors})
def passed(scenario,**facts):
    checks.append({'scenario':scenario,'status':'PASS',**facts});receipt();print('PASS '+scenario,flush=True)
def fresh(account):
    global page,context
    context.close();context=browser.new_context(viewport={'width':1440,'height':900});page=context.new_page()
    page.on('pageerror',lambda e:errors.append(str(e)));login(account)
def ready(path,semantic=False):
    goto(path);page.locator('#main-content').wait_for(timeout=45000)
    if semantic:page.get_by_text('Library semantic search',exact=True).wait_for(timeout=60000)
    else:page.wait_for_function('()=>!document.querySelector(".ui-state-loading")',timeout=45000)
def ids():return page.locator('#for-you-results .product-book-card').evaluate_all('''es=>es.map(e=>e.querySelector('a[href*="/books/"]')?.getAttribute('href')).filter(Boolean)''')
def rail(path,lib=None):
    ready(path);area=page.locator('#for-you-results');area.wait_for(timeout=60000)
    area.get_by_role('button',name='Next Recommendations',exact=True).wait_for(timeout=60000)
    page.wait_for_function('()=>{const e=[...document.querySelectorAll("#for-you-results button")].find(e=>e.textContent==="Next Recommendations");return e&&!e.disabled}',timeout=60000)
    before=area.locator('article h3').all_text_contents()
    if not before:before=area.locator('article').all_text_contents()
    right=area.get_by_role('button',name='Scroll right',exact=True);right.wait_for();right.click();page.wait_for_timeout(500)
    position=area.locator('.product-book-rail').evaluate('(e)=>e.scrollLeft');assert position>0
    area.get_by_role('button',name='Scroll left',exact=True).click();page.wait_for_timeout(500)
    assert area.locator('.product-book-rail').evaluate('(e)=>e.scrollLeft')<2
    area.get_by_role('button',name='Next Recommendations',exact=True).click()
    page.wait_for_function('()=>{const e=[...document.querySelectorAll("#for-you-results button")].find(e=>e.textContent==="Previous Recommendations");return e&&!e.disabled}',timeout=60000)
    page.wait_for_timeout(700)
    after=area.locator('article h3').all_text_contents()
    if not after:after=area.locator('article').all_text_contents()
    assert before!=after and after
    if lib:assert all('/libraries/'+lib+'/books/' in href for href in ids())
    assert area.locator('.product-book-rail').evaluate('(e)=>e.scrollLeft')<2
    area.get_by_role('button',name='Previous Recommendations',exact=True).click();page.wait_for_timeout(700)
    restored=area.locator('article h3').all_text_contents()
    if not restored:restored=area.locator('article').all_text_contents()
    assert restored==before
    assert area.get_by_role('button',name='Previous Recommendations',exact=True).is_disabled()
    href=area.get_by_role('link',name='VIEW ALL',exact=True).get_attribute('href')
    if lib:assert href.startswith('/libraries/'+lib+'/catalogue')
    area.get_by_role('link',name='VIEW ALL',exact=True).click();page.wait_for_timeout(500)
    if lib:assert urlparse(page.url).path=='/libraries/'+lib+'/catalogue'
    passed('Carousel arrows and recommendation paging '+(lib or 'GLOBAL'),right_scroll=position,distinct_pages=True,view_all=href,scope_preserved=True)

fresh('patron');rail('/',None);rail('/libraries/'+TEST,TEST)
ready('/libraries/'+fixtures['A']['library_id']);page.locator('#for-you-results').wait_for(timeout=60000)
selector=page.locator('.patron-context-bar select');selector.select_option(fixtures['B']['library_id'])
page.wait_for_url('**/libraries/'+fixtures['B']['library_id'],timeout=45000)
page.wait_for_function('''lib=>[...document.querySelectorAll('#for-you-results article a[href*="/books/"]')].some(e=>e.getAttribute('href').includes(lib))''',arg=fixtures['B']['library_id'],timeout=60000)
assert not any(fixtures['A']['library_id'] in href for href in ids())
page.go_back();page.wait_for_url('**/libraries/'+fixtures['A']['library_id']);page.go_forward();page.wait_for_url('**/libraries/'+fixtures['B']['library_id'])
passed('Library switch resets recommendation context; Back and Forward remain scoped')

for account,prefix in [('patron','/libraries/'),('staff','/staff/libraries/')]:
    fresh(account);base=prefix+TEST
    ready(base+'/catalogue?search=computer%20networks',semantic=True)
    links=page.locator('.product-book-card a[href*="/books/"]').evaluate_all('(es)=>es.map(e=>e.getAttribute("href"))')
    assert links and all(base+'/books/' in h for h in links)
    assert not page.get_by_text('Global Catalogue',exact=True).count()
    passed(account+' live semantic Search',source='TENANT_SEMANTIC',results=len(links))
    ready(base+'/graph');page.locator('[data-graph-source=TENANT_KG]').wait_for(timeout=60000)
    assert page.get_by_role('region',name='Library graph map').count()==1
    page.get_by_role('button',name=re.compile('^Inspect book:')).first.click();page.get_by_role('link',name='Open book details',exact=True).wait_for()
    assert page.get_by_role('link',name='Open book details',exact=True).get_attribute('href').startswith(base+'/books/')
    assert not page.get_by_role('button',name=re.compile('Build|Rebuild',re.I)).count()
    passed(account+' tenant KG routing',source='TENANT_KG',no_build_controls=True)
    for surface,path in [('search',base+'/catalogue?search=networks'),('graph',base+'/graph'),('home',base)]:
        for width,height in VIEWPORTS:
            page.set_viewport_size({'width':width,'height':height});ready(path,semantic=surface=='search')
            if surface=='graph':page.locator('[data-graph-source=TENANT_KG]').wait_for(timeout=60000)
            if surface=='home' and account=='patron':page.locator('#for-you-results .product-book-card').first.wait_for(timeout=60000)
            assert page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth+1'),(account,surface,width)
            page.screenshot(path=str(REPORTS/f'institution_v2g_{account}_{surface}_{width}.png'),animations='disabled')
            responsive.append({'account':account,'surface':surface,'viewport':[width,height],'status':'PASS','page_overflow':False});receipt()

# Counts are display-only visual fixtures. No notifications or saved items are
# created, and no private message/credential contents are captured.
fresh('patron');count=1
def notification_fixture(route):route.fulfill(json={'notifications':[],'count':0,'unread_count':count})
page.route('**/api/notifications?**',notification_fixture)
for count in [1,12,120]:
    for width,height in VIEWPORTS:
        page.set_viewport_size({'width':width,'height':height});ready('/libraries/'+TEST)
        page.locator('.notification-count').wait_for(timeout=45000)
        page.evaluate('''async count=>{const m=await import('/src/store/useLibraryStore.ts');m.useLibraryStore.setState({readingList:Array.from({length:count},(_,i)=>({work_id:'visual-'+i}))})}''',count)
        values=page.evaluate('''()=>[...document.querySelectorAll('.notification-count,.global-saved .global-count')].filter(e=>e.getBoundingClientRect().width).map(e=>{const b=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect(),s=getComputedStyle(e);return {badge:e.className,text:e.textContent,parent_position:getComputedStyle(e.parentElement).position,bounds:{left:b.left,right:b.right,top:b.top,bottom:b.bottom},attached:b.left>=p.left-1&&b.right<=p.right+1&&b.top>=p.top-1&&b.bottom<=p.bottom+1,inside_viewport:b.left>=0&&b.right<=innerWidth&&b.top>=0,position:s.position}})''')
        assert values and all(v['attached'] and v['inside_viewport'] and v['position']=='absolute' for v in values),(count,width,values)
        assert values[0]['text']==('99+' if count>99 else str(count))
        badges.append({'count':count,'viewport':[width,height],'status':'PASS','badges':values,'saved_hidden_on_mobile':width<640});receipt()
page.unroute('**/api/notifications?**',notification_fixture)
passed('Header badges attached, one digit/two digits/99+, all six sizes',visual_fixtures_only=True)

for account,paths in [('patron',[('browse','/libraries/'+TEST+'/catalogue'),('reservations','/libraries/'+TEST+'/reservations'),('fees','/libraries/'+TEST+'/fees'),('global_catalog','/catalog')]),('staff',[(s,'/staff/libraries/'+TEST+'/'+s) for s in ['inventory','circulation','reservations','fees','events','analytics','assets','members','settings']])]:
    fresh(account)
    for surface,path in paths:
        for width,height in VIEWPORTS:
            page.set_viewport_size({'width':width,'height':height});ready(path);page.wait_for_timeout(150)
            assert page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth+1'),(surface,width)
            values=page.locator('main select, main input:not([type=radio]):not([type=checkbox]),main textarea,.patron-context-bar select').evaluate_all('''es=>es.filter(e=>e.getBoundingClientRect().width&&e.type!=='hidden').map(e=>{const control=e.classList.contains('ui-composite-input')?e.closest('.product-catalogue-search'):e,s=getComputedStyle(control),r=e.getBoundingClientRect();return {tag:e.tagName,type:e.type,height:r.height,border:s.borderTopWidth,radius:s.borderRadius,background:s.backgroundColor,color:s.color,composite:control!==e,native_select:e.tagName==='SELECT',pass:r.height>=38&&parseFloat(s.borderTopWidth)>=1&&parseFloat(s.borderRadius)>=6}})''')
            assert all(v['pass'] for v in values),(surface,width,values)
            if values:
                element=page.locator('main select,main input:not([type=radio]):not([type=checkbox]),main textarea,.patron-context-bar select').first
                element.focus();page.keyboard.press('Tab')
            controls.append({'account':account,'surface':surface,'viewport':[width,height],'status':'PASS','controls':values,'page_overflow':False});receipt()
passed('Native closed controls themed across Patron, Staff and global catalogue',cases=len(controls))

fresh('patron');ready('/experimental/kg');page.get_by_role('heading',name='Follow a book’s connections.',exact=True).wait_for(timeout=45000)
assert not page.locator('[data-graph-source=TENANT_KG]').count();passed('Global Graph Lab stays separate')
ready('/search?q=harry');page.locator('.product-book-card').first.wait_for(timeout=60000);assert not page.get_by_text('Library semantic search',exact=True).count();passed('Explicit global Search stays global')
assert not errors,errors
receipt('PASS');print('PASS final browser checks',len(checks),'responsive',len(responsive),'controls',len(controls),'badges',len(badges),flush=True)
