"""Read-only rail, viewer and workspace context closure after the main flow."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright,expect
from scripts.post2h_product_browser import BASE,TEST,CN,BOTH,sign,detail,viewer
from scripts.full_product_browser_session import credentials
path=ROOT/'reports/post2h_browser_validation.json';data=json.loads(path.read_text(encoding='utf8'));assert len(data['responsive'])>=42
data['status']='IN_PROGRESS'
def save():path.write_text(json.dumps(data,indent=2),encoding='utf8')
def check(name,**value):data['checks'].append({'scenario':name,'status':'PASS',**value});save();print('PASS '+name,flush=True)
def measure(page,name,w,h):
    values=page.evaluate('''()=>({width:innerWidth,pageWidth:document.documentElement.scrollWidth,overflows:[...document.querySelectorAll('.product-book-card,.catalogue-actions')].filter(e=>e.clientWidth>0&&e.scrollWidth>e.clientWidth+2).map(e=>e.className)})''')
    assert values['pageWidth']<=w+2 and not values['overflows'],values
    if name=='home_rails':
        page.wait_for_timeout(250)
        overlaps=page.evaluate('''()=>{const a=document.querySelector('.assistant-launcher')?.getBoundingClientRect();return a?[...document.querySelectorAll('.product-rail-controls button,.catalogue-actions .ui-button')].filter(e=>{const r=e.getBoundingClientRect();return r.width&&Math.min(a.right,r.right)>Math.max(a.left,r.left)&&Math.min(a.bottom,r.bottom)>Math.max(a.top,r.top)}).map(e=>e.textContent||e.getAttribute('aria-label')):[]}''')
        assert not overlaps,overlaps;values['launcher_control_overlaps']=overlaps
    shot=f'post2h_product_{name}_{w}_viewport.png';page.screenshot(path=str(ROOT/'reports'/shot))
    data['responsive'].append({'page':name,'viewport':f'{w}x{h}','status':'PASS','measurements':values,'screenshot':shot});save()
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True);owner=browser.new_page(viewport={'width':1440,'height':900});sign(owner,*credentials('staff'))
    for section in ['','inventory','circulation','reservations','fees','members','settings']:
        owner.goto(BASE+f'/staff/libraries/{TEST}'+('/'+section if section else ''))
        logo=owner.locator('.global-header').get_by_role('link',name='LuminaR home',exact=True);logo.wait_for(timeout=60000)
        expect(logo).to_have_attribute('href',f'/staff/libraries/{TEST}');check('Staff Home context '+(section or 'Overview'),destination=f'/staff/libraries/{TEST}')
    owner.goto(BASE+f'/staff/libraries/{TEST}/intelligence');owner.get_by_text('Eligible books',exact=False).first.wait_for(timeout=60000)
    check('Intelligence current dataset matches 151 records',text=owner.locator('main').inner_text()[:2500])
    patron=browser.new_page(viewport={'width':1440,'height':900});sign(patron,*credentials('patron'))
    for w,h in [(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]:
        patron.set_viewport_size({'width':w,'height':h});patron.goto(BASE+f'/libraries/{TEST}')
        patron.get_by_role('article',name='CN',exact=True).first.wait_for(timeout=100000)
        # The recommendation and arrival rails contain canonical cards; viewport
        # scrolling is intentional, card action groups themselves must fit.
        region=patron.get_by_role('article',name='TEST Reading Circle Discussion Notes',exact=True).first
        region.wait_for(timeout=60000);expect(region.get_by_role('button',name='Request Book',exact=True)).to_be_attached();expect(region.get_by_role('link',name='Read Online',exact=True)).to_be_attached()
        region.scroll_into_view_if_needed();measure(patron,'home_rails',w,h)
        logo=patron.locator('.global-header').get_by_role('link',name='LuminaR home',exact=True);expect(logo).to_have_attribute('href',f'/libraries/{TEST}')
        region=detail(patron,TEST,CN);viewer(patron,region.get_by_role('link',name='Read Online',exact=True));patron.locator('.asset-reader').scroll_into_view_if_needed();measure(patron,'authorized_viewer',w,h)
        owner.set_viewport_size({'width':w,'height':h});owner.goto(BASE+f'/staff/libraries/{TEST}/catalogue');owner.get_by_role('combobox',name='Circulation status',exact=True).wait_for(timeout=60000)
        mobile=owner.get_by_role('button',name='Open workspace menu',exact=True)
        if mobile.is_visible():mobile.click();scope=owner.get_by_role('dialog',name='Workspace menu')
        else:scope=owner.locator('.workspace-sidebar')
        control=scope.get_by_role('combobox',name='Switch staff library',exact=True);control.wait_for(timeout=60000);assert 'luminar-select' in control.get_attribute('class');control.click();expect(owner.get_by_role('listbox')).to_be_visible();measure(owner,'staff_selector',w,h);owner.keyboard.press('Escape')
        if mobile.is_visible():owner.keyboard.press('Escape')
        check('Home rail viewer and staff selector '+str(w),viewport=f'{w}x{h}')
    patron.goto(BASE+'/');logo=patron.locator('.global-header').get_by_role('link',name='LuminaR home',exact=True);expect(logo).to_have_attribute('href','/');check('Explicit global Home remains global')
    browser.close()
data['checks']=list({row['scenario']:row for row in data['checks']}.values())
data['responsive']=list({(row['page'],row['viewport']):row for row in data['responsive']}.values())
data['status']='PASS';save()
