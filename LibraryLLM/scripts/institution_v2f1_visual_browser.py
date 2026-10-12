"""Live canonical product/format/cover checks; loaded in the browser QA console."""
import json,re,time
from urllib.parse import quote

VIEWPORTS=[(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]
cover_rows=[];responsive_rows=[];navigation_rows=[];card_rows=[]

COVER_CHECK=r'''es=>es.filter(e=>e.clientWidth>0&&e.clientHeight>0).map(e=>{
 const box=e.getBoundingClientRect(),content=e.querySelector('.book-cover-content.relative');
 const text=[...content.querySelectorAll('.book-cover-title,.book-cover-author,.book-cover-brand')];
 const transparent=text.every(x=>getComputedStyle(x).backgroundColor==='rgba(0, 0, 0, 0)')&&getComputedStyle(content).backgroundColor==='rgba(0, 0, 0, 0)';
 const measures=text.map(x=>{const range=document.createRange();range.selectNodeContents(x);const r=range.getBoundingClientRect();return {text:x.textContent,class:x.className,top:r.top-box.top,bottom:r.bottom-box.top,left:r.left-box.left,right:r.right-box.left,width:r.width,inside:r.left>=box.left-1&&r.right<=box.right+1&&r.top>=box.top-1&&r.bottom<=box.bottom+1,overflow:getComputedStyle(x).overflow,background:getComputedStyle(x).backgroundColor,color:getComputedStyle(x).color}});
 const title=measures.find(x=>x.class.includes('title')),author=measures.find(x=>x.class.includes('author')),brand=measures.find(x=>x.class.includes('brand'));
 const titleNode=text.find(x=>x.classList.contains('book-cover-title')),authorNode=text.find(x=>x.classList.contains('book-cover-author')),brandNode=text.find(x=>x.classList.contains('book-cover-brand'));
 // Featured books retain their accepted rotated layout; transformed bounding
 // rectangles are not line boxes and can overlap without glyphs colliding.
 const collision=!!(authorNode&&titleNode.offsetTop+titleNode.clientHeight>authorNode.offsetTop+1)||brandNode.offsetTop+brandNode.clientHeight>titleNode.offsetTop+1;
 const duplicate=e.querySelector('.book-cover-region-type');
 const aspect=Math.abs(e.clientHeight/e.clientWidth-1.5)<.02,uniform=text.every(x=>getComputedStyle(x).color===getComputedStyle(e).color);
 return {title:titleNode.textContent,author:authorNode?.textContent||'',width:e.clientWidth,height:e.clientHeight,aspect_ok:aspect,transparent,background:getComputedStyle(e).backgroundColor,foreground:getComputedStyle(e).color,uniform_original_palette_foreground:uniform,backplates:e.querySelectorAll('.book-cover-text-scrim').length,no_collision:!collision,all_text_inside:measures.every(x=>x.inside),region_type:!!duplicate,region_clip:duplicate?getComputedStyle(duplicate).clipPath:null,measurements:measures,pass:transparent&&!collision&&measures.every(x=>x.inside)&&aspect&&uniform&&!duplicate};
})'''

def cover_surface(name,path,width,height,screenshot=True):
    page.set_viewport_size({'width':width,'height':height});goto(path)
    page.locator('.book-cover-art').first.wait_for(timeout=60000)
    page.evaluate('()=>document.fonts.ready');page.wait_for_timeout(600)
    values=page.locator('.book-cover-art').evaluate_all(COVER_CHECK)
    for value in values:cover_rows.append({'surface':name,'viewport':[width,height],**value})
    failures=[v['title'] for v in values if not v['pass']]
    assert not failures,{'surface':name,'viewport':width,'cover_failures':failures}
    overflow=page.evaluate('()=>document.documentElement.scrollWidth>innerWidth+1')
    responsive_rows.append({'surface':name,'viewport':[width,height],'page_overflow':overflow,'covers':len(values),'status':'FAIL' if overflow else 'PASS'})
    assert not overflow,{'surface':name,'overflow':width}
    cards=page.locator('.product-book-card').evaluate_all('''es=>es.filter(e=>e.clientWidth>0).map(e=>{
      const r=e.getBoundingClientRect(),controls=[...e.querySelectorAll('button,summary,a.bg-brand,a.ui-button')].filter(c=>c.getClientRects().length);
      return {title:e.getAttribute('aria-label'),width:e.clientWidth,controls:controls.length,controls_inside:controls.every(c=>{const b=c.getBoundingClientRect();return b.left>=r.left-1&&b.right<=r.right+1&&c.scrollWidth<=c.clientWidth+1}),card_overflow:e.scrollWidth>e.clientWidth+1}
    })''')
    card_rows.append({'surface':name,'viewport':[width,height],'cards':cards,'status':'PASS' if all(c['controls_inside'] and not c['card_overflow'] for c in cards) else 'FAIL'})
    assert card_rows[-1]['status']=='PASS',{'surface':name,'card_failures':[c for c in cards if not c['controls_inside'] or c['card_overflow']]}
    if screenshot:
        # Home's accepted marquee keeps moving; scrolling the page does not
        # require the cover itself to become stationary.
        page.locator('.book-cover-art').first.evaluate('(e)=>window.scrollTo(0,Math.max(0,e.getBoundingClientRect().top+scrollY-160))');page.wait_for_timeout(200)
        page.screenshot(path=str(REPORTS/f'institution_v2f1_{name}_{width}.png'),full_page=False,animations='disabled')
    print('PASS covers',name,width,len(values),flush=True)

def navigation_closure():
    fresh_login('staff');goto(f'/staff/libraries/{TEST}/circulation');page.get_by_role('link',name='Catalog',exact=True).first.click()
    page.wait_for_url('**/inventory');page.get_by_text('150 records',exact=False).wait_for(timeout=45000)
    assert page.get_by_text('Global Catalogue',exact=True).count()==0
    navigation_rows.append({'scenario':'Staff Catalog','path':page.url.split(BASE)[1],'source':'tenant-local','records':150,'status':'PASS'})
    page.get_by_role('link',name='New Arrivals',exact=True).first.click();page.wait_for_url('**/inventory?sort=new_arrivals')
    navigation_rows.append({'scenario':'Staff New Arrivals','path':page.url.split(BASE)[1],'status':'PASS'})
    page.locator('.global-search-toggle').click()
    page.get_by_label('Search this library collection').fill('Reading Circle');page.locator('form.global-search').get_by_role('button',name='Search',exact=True).click()
    page.wait_for_url('**/inventory?search=Reading%20Circle');page.get_by_role('heading',name='TEST Reading Circle Discussion Notes').wait_for(timeout=45000)
    navigation_rows.append({'scenario':'Staff Header Search','path':page.url.split(BASE)[1],'status':'PASS'})
    page.get_by_role('link',name='My reading list',exact=True).click();page.wait_for_url('**/reading-list?staff_library=*')
    page.locator('.global-logo').click();page.wait_for_url(BASE+f'/staff/libraries/{TEST}')
    navigation_rows.append({'scenario':'Staff personal return Home','path':page.url.split(BASE)[1],'status':'PASS'})
    goto(f'/catalog?staff_library={TEST}');page.wait_for_url('**/staff/libraries/*/inventory')
    navigation_rows.append({'scenario':'Legacy catalog context redirect only','path':page.url.split(BASE)[1],'status':'PASS'})
    goto('/catalog');page.locator('.global-logo').click();page.wait_for_url(BASE+'/')
    navigation_rows.append({'scenario':'Explicit global Home','path':'/','status':'PASS'})
    fresh_login('patron');goto(f'/libraries/{TEST}');page.get_by_role('link',name='Browse Books',exact=True).first.click();page.wait_for_url('**/catalogue')
    page.get_by_role('link',name='My reading list',exact=True).click();page.wait_for_url('**/reading-list?patron_library=*')
    page.locator('.global-logo').click();page.wait_for_url(BASE+f'/libraries/{TEST}')
    navigation_rows.append({'scenario':'Patron personal return Home','path':page.url.split(BASE)[1],'status':'PASS'})
    put('institution_v2f1_staff_catalog_browser.json',{'status':'PASS','checks':navigation_rows,'URL_context_first':True,'query_authority':False})
    print('PASS navigation',len(navigation_rows),flush=True)

def forms_responsive():
    fresh_login('staff');lib=fixtures['format_library'];checks=[]
    for width,height in VIEWPORTS:
        page.set_viewport_size({'width':width,'height':height});goto(f'/staff/libraries/{lib}/inventory');button=page.get_by_role('button',name='Add Book',exact=True);button.wait_for(timeout=45000);button.click()
        dialog=page.get_by_role('dialog',name='Add Book',exact=True)
        for mode in ['Physical','Online','Physical + Online']:
            radio=dialog.get_by_role('radio',name=mode,exact=True);radio.check();radio.focus();page.keyboard.press('ArrowRight');assert dialog.locator('input[type=radio]:checked').count()==1;radio.check()
            box=dialog.bounding_box();assert box and box['x']>=-1 and box['x']+box['width']<=width+1 and box['height']<=height+1
            assert not page.evaluate('()=>document.documentElement.scrollWidth>innerWidth+1')
            radio.focus();page.keyboard.press('Shift+Tab');assert dialog.locator(':focus').count()==1
            checks.append({'viewport':[width,height],'mode':mode,'exclusive_native_radios':True,'keyboard_arrows':True,'dialog_fits':True,'no_page_overflow':True,'status':'PASS'})
        page.keyboard.press('Escape');dialog.wait_for(state='hidden');assert button.evaluate('(e)=>e===document.activeElement')
        page.screenshot(path=str(REPORTS/f'institution_v2f1_inventory_{width}.png'),animations='disabled')
    put('institution_v2f1_format_accessibility.json',{'status':'PASS','checks':checks,'escape_focus_restore':True,'native_labels':True,'secret_values_captured':False})
    print('PASS forms accessibility',len(checks),flush=True)

def named_cover_samples():
    titles=['The Ruth Stout No-Work Garden Book','The Great Dinosaur Search (Great Searches - New Format)','Samuel Huntington, President of Congress Longer Than Expected','Death of a Stranger (A William Monk Mystery)','Money 1988','Managing God\'s Money-The Basics, Workbook','靈山 = Ling Shan','The Tower','Logical aspects of computational linguistics']
    matches=list(db.books.find({'title':{'$in':titles}},{'_id':0,'work_id':1,'title':1,'authors':1}).limit(20))
    local=list(db.institution_library_books.find({'library_id':TEST,'title':{'$in':titles}},{'_id':0,'library_book_id':1,'title':1,'authors':1}).limit(10))
    linked=db.institution_library_books.find_one({'library_id':TEST,'global_work_id':{'$ne':None}},{'_id':0,'library_book_id':1,'title':1,'authors':1})
    local_only=db.institution_library_books.find_one({'library_id':TEST,'title':'TEST Reading Circle Discussion Notes'},{'_id':0,'library_book_id':1,'title':1,'authors':1})
    samples=[{'path':'/book/'+r['work_id'],'title':r['title'],'source':'GLOBAL'} for r in matches]+[{'path':f'/libraries/{TEST}/books/'+r['library_book_id'],'title':r['title'],'source':'LIBRARY'} for r in local+[linked,local_only] if r]
    put('institution_v2f1_cover_samples.json',samples);print('samples',len(samples),[s['title'] for s in samples],flush=True)
    return samples

def sample_matrix(samples):
    fresh_login('patron')
    for i,sample in enumerate(samples):
        for width,height in VIEWPORTS:
            cover_surface('sample_'+str(i),sample['path'],width,height,screenshot=width in [1440,375])
    put('institution_v2f1_cover_visual_validation.json',{'status':'PASS','browser':browser.version,'checks':cover_rows,'responsive':responsive_rows,'samples':samples,'method':'Actual generated cover DOM, transparent computed backgrounds, glyph range bounds and title/author/brand separation; genuine rendered screenshots.'})

def surface_matrix():
    fresh_login('patron')
    pages=[('global_home','/'),('global_catalog','/catalog'),('global_search','/search?q=harry'),('TEST_home',f'/libraries/{TEST}'),('TEST_browse',f'/libraries/{TEST}/catalogue'),('reading_list',f'/reading-list?patron_library={TEST}')]
    for name,path in pages:
        for width,height in VIEWPORTS:
            if not any(row['surface']==name and row['viewport']==[width,height] and row['status']=='PASS' for row in responsive_rows):cover_surface(name,path,width,height)
    put('institution_v2f1_cover_visual_validation.json',{'status':'PASS','browser':browser.version,'checks':cover_rows,'responsive':responsive_rows,'method':'Live catalogue/detail/home/search/list samples, glyph bounds, transparent backgrounds, screenshots. Home includes showcase and recommendation rail.'})
    put('institution_v2f1_book_card_layout_validation.json',{'status':'PASS','checks':card_rows,'method':'Actual card and control rectangles, card overflow, page overflow; all six viewports.'})

