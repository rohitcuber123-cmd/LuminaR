"""Rendered responsive, axe contrast, touch and keyboard evidence in Chromium."""
SIZES=[(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]
PATRON_PAGES=[('Global Home','/','#new-arrivals .product-book-card'),('TEST Home',PATRON_HOME,'#new-arrivals .product-book-card'),('Global Catalog','/catalog','.product-book-grid .product-book-card'),('TEST Browse',PATRON_HOME+'/catalogue','.product-book-grid .product-book-card'),('Global Book Detail',GLOBAL,'.book-detail-view h1'),('TEST Book Detail',LINKED,'.book-detail-view h1'),('Reading List','/reading-list'+RETURN,'.product-book-card'),('Search','/search?q=set+theory','.product-book-card'),('My Library',PATRON_HOME+'/my-library','main h1'),('Reservations',PATRON_HOME+'/reservations','main h1'),('Fees',PATRON_HOME+'/fees','main h1'),('Account/My Libraries','/account/libraries'+RETURN,'a:has-text("Open Library")')]
STAFF_PAGES=[('Staff Overview','/staff/libraries/'+TEST,'main h1'),('Staff Inventory','/staff/libraries/'+TEST+'/inventory','.inventory-table'),('Staff Circulation','/staff/libraries/'+TEST+'/circulation','main h1')]
matrix=[]
accessibility=[]

GEOMETRY="""() => {
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
 const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};
 const headers=[...document.querySelectorAll('.global-header-inner > *, .global-header-actions > *')].filter(visible).map(e=>({name:e.className,...rect(e)}));
 const top=[...document.querySelectorAll('.global-header-inner > *')].filter(visible);
 const overlaps=[];for(let i=0;i<top.length;i++)for(let j=i+1;j<top.length;j++){const a=rect(top[i]),b=rect(top[j]);if(Math.min(a.right,b.right)-Math.max(a.x,b.x)>1&&Math.min(a.bottom,b.bottom)-Math.max(a.y,b.y)>1)overlaps.push([top[i].className,top[j].className])}
 const controls=[...document.querySelectorAll('button,a.ui-button,.global-saved,.global-logo,input,select,summary')].filter(visible).map(e=>({name:(e.getAttribute('aria-label')||e.textContent||e.placeholder||'').trim().slice(0,70),tag:e.tagName,disabled:!!e.disabled,...rect(e)}));
 const tables=[...document.querySelectorAll('.ui-table-wrap,.institution-table-wrap,.staff-table-wrap')].filter(visible).map(e=>({width:e.clientWidth,scrollWidth:e.scrollWidth,overflow:getComputedStyle(e).overflowX,...rect(e)}));
 const grid=document.querySelector('.product-book-grid'); const cover=document.querySelector('.book-detail-view .book-cover');
 return {width:innerWidth,height:innerHeight,document_width:document.documentElement.scrollWidth,body_width:document.body.scrollWidth,header:headers,header_overlaps:overlaps,controls,tables,grid_columns:grid?getComputedStyle(grid).gridTemplateColumns:null,detail_cover:cover?rect(cover):null,book_cards:document.querySelectorAll('.product-book-card').length,headings:[...document.querySelectorAll('main h1')].map(e=>e.textContent.trim()),logo:document.querySelector('.global-logo')?.getAttribute('href'),alerts:[...document.querySelectorAll('[role=alert],.ui-state-error,.institution-error')].map(e=>e.textContent.trim())};
}"""

def rendered_audit():
    page.wait_for_function("document.getAnimations().every(a=>a.effect?.getComputedTiming().iterations===Infinity || a.playState==='finished' || a.playState==='idle')",timeout=15000)
    page.add_script_tag(path=str(ROOT/'frontend/node_modules/axe-core/axe.min.js'))
    return page.evaluate("""async () => { const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});return {passes:r.passes.map(p=>p.id),violations:r.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary,checks:n.any.map(c=>({id:c.id,data:c.data}))}))})),incomplete:r.incomplete.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))}; }""")

def run_matrix(pages,role):
    for name,route,selector in pages:
        goto(route);ready(selector)
        page.get_by_text(re.compile('^Loading')).first.wait_for(state='hidden',timeout=60000)
        if 'Catalog' in name or name=='TEST Browse':page.wait_for_function("document.querySelectorAll('.category-chips button').length>2",timeout=60000)
        for width,height in SIZES:
            page.set_viewport_size({'width':width,'height':height})
            page.evaluate('document.fonts.ready')
            geometry=page.evaluate(GEOMETRY)
            axe=rendered_audit()
            row={'page':name,'role':role,'route':route,'viewport':f'{width}x{height}','geometry':geometry}
            row['status']='PASS' if geometry['document_width']<=width and not geometry['header_overlaps'] and not geometry['alerts'] else 'FAIL'
            matrix.append(row)
            accessibility.append({'page':name,'role':role,'viewport':row['viewport'],**axe})
            shot(name.lower().replace('/','_').replace(' ','_')+'_'+str(width))
            print('MATRIX',name,row['viewport'],row['status'],'axe',len(axe['violations']),flush=True)
            put('full_product_responsive_final.json',{'engine':'real Chromium','status':'IN_PROGRESS','rows':matrix})
            put('full_product_accessibility_final.json',{'engine':'real Chromium / rendered axe','status':'IN_PROGRESS','audits':accessibility})
    page.set_viewport_size({'width':1440,'height':900})

def keyboard_target(locator,key='Enter'):
    locator.scroll_into_view_if_needed()
    # Reach the target with real Tab, not programmatic focus.
    reached=False
    for _ in range(400):
        if locator.evaluate('(e)=>document.activeElement===e'):reached=True;break
        page.keyboard.press('Tab')
    assert reached,'Tab could not reach '+str(locator)
    focus=locator.evaluate("e=>{const s=getComputedStyle(e);return {outline:s.outlineStyle,width:s.outlineWidth,color:s.outlineColor,boxShadow:s.boxShadow}}")
    assert focus['outline']!='none' and float(focus['width'].replace('px',''))>=2,focus
    locator.press(key)
    return focus

def keyboard_flows():
    checks=[]
    goto(LINKED);ready('.book-detail-view h1')
    trigger=page.get_by_role('button',name=re.compile('Open account menu'))
    focus=keyboard_target(trigger)
    dialog=page.get_by_role('dialog',name='Account & libraries',exact=True);dialog.wait_for()
    first=page.evaluate('document.activeElement.textContent.trim()');page.keyboard.press('ArrowDown')
    next_item=page.evaluate('document.activeElement.textContent.trim()');page.keyboard.press('Escape');dialog.wait_for(state='hidden')
    restored=trigger.evaluate('e=>e===document.activeElement');assert restored
    checks.append({'flow':'Account menu Tab/Enter/ArrowDown/Escape','focus':focus,'first':first,'next':next_item,'restored':restored,'status':'PASS'})
    button=page.locator('.book-personal-actions button[aria-label]').first
    before=button.get_attribute('aria-pressed');focus=keyboard_target(button,'Space');assert button.get_attribute('aria-pressed')!=before
    button.press('Space');checks.append({'flow':'Select/deselect for AI with Space','focus':focus,'status':'PASS'})
    more=page.locator('.book-personal-actions summary');focus=keyboard_target(more,'Space');assert page.locator('.book-personal-actions details').get_attribute('open') is not None
    more.press('Space');checks.append({'flow':'Book discovery disclosure keyboard','focus':focus,'status':'PASS'})
    save=page.locator('.book-save-button');before=save.get_attribute('aria-pressed');focus=keyboard_target(save,'Space');page.wait_for_function('(b)=>document.querySelector(".book-save-button").getAttribute("aria-pressed")!==b',arg=before)
    save.press('Space');page.wait_for_function('(b)=>document.querySelector(".book-save-button").getAttribute("aria-pressed")===b',arg=before);checks.append({'flow':'Saved toggle keyboard','focus':focus,'status':'PASS'})
    goto(PATRON_HOME+'/catalogue');ready();page.wait_for_function("document.querySelectorAll('.category-chips button').length>2")
    chip=page.locator('.category-chips button').nth(1);focus=keyboard_target(chip,'Space');ready();checks.append({'flow':'Category chip keyboard','focus':focus,'url':urlparse(page.url).query,'status':'PASS'})
    page.locator('.category-chips button').first.press('Space');ready()
    next_page=page.get_by_role('button',name='Next page',exact=True);focus=keyboard_target(next_page);ready();assert 'offset=' in page.url;checks.append({'flow':'Pagination keyboard','focus':focus,'url':urlparse(page.url).query,'status':'PASS'})
    cover=page.locator('.product-book-card > a').first;focus=keyboard_target(cover);ready('.book-detail-view h1');checks.append({'flow':'Book card keyboard opens detail','focus':focus,'status':'PASS'})
    goto(PATRON_HOME);ready('#new-arrivals .product-book-card')
    rail=page.locator('#new-arrivals').get_by_role('button',name='Scroll right',exact=True);focus=keyboard_target(rail);checks.append({'flow':'Carousel keyboard','focus':focus,'status':'PASS'})
    page.set_viewport_size({'width':375,'height':812})
    menu=page.get_by_role('button',name='Toggle menu',exact=True);focus=keyboard_target(menu);page.get_by_role('dialog',name='LuminaR navigation',exact=True).wait_for();page.keyboard.press('Escape');assert menu.evaluate('e=>e===document.activeElement');checks.append({'flow':'Mobile navigation keyboard and focus restoration','focus':focus,'status':'PASS'})
    page.set_viewport_size({'width':1440,'height':900})
    put('full_product_browser_keyboard.json',{'status':'PASS','checks':checks})
    print('Keyboard checks',len(checks),'PASS',flush=True)

def staff_keyboard():
    page.set_viewport_size({'width':375,'height':812});goto('/staff/libraries/'+TEST);ready('main h1')
    trigger=page.get_by_role('button',name='Open workspace menu',exact=True);focus=keyboard_target(trigger)
    dialog=page.get_by_role('dialog',name='Workspace menu',exact=True);dialog.wait_for()
    box=dialog.bounding_box();assert box['width']<=375 and box['height']<=812
    page.keyboard.press('Escape');assert trigger.evaluate('e=>e===document.activeElement')
    put('full_product_browser_staff_keyboard.json',{'status':'PASS','focus':focus,'drawer':box,'restored':True})
    page.set_viewport_size({'width':1440,'height':900})

def action_geometry():
    checks=[]
    for name,route in [('Global Detail',GLOBAL),('TEST Detail',LINKED),('Local-only Detail',LOCAL),('TEST Browse',PATRON_HOME+'/catalogue')]:
        goto(route);ready('.book-detail-view h1' if 'Detail' in name else '.product-book-card')
        for width,height in SIZES:
            page.set_viewport_size({'width':width,'height':height})
            actions=page.locator('main .book-personal-actions button, main .catalogue-actions button, main .product-pagination button:not([disabled])')
            count=actions.count()
            for index in range(min(count,9)):
                action=actions.nth(index)
                if action.is_disabled():continue
                action.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})")
                measurement=action.evaluate("""e=>{const r=e.getBoundingClientRect(),x=r.x+r.width/2,y=r.y+r.height/2,h=document.elementFromPoint(x,y);return {name:(e.getAttribute('aria-label')||e.textContent).trim(),width:r.width,height:r.height,visible_center:!!h&&(h===e||e.contains(h)),covering:h?.closest('.assistant-launcher')?'assistant':null}}""")
                assert measurement['visible_center'],measurement
                if width<640:assert measurement['height']>=44,measurement
                checks.append({'page':name,'viewport':f'{width}x{height}',**measurement})
            if name=='TEST Detail' and width==375:page.screenshot(path=str(REPORTS/'full_product_browser_mobile_detail_actions.png'))
    page.set_viewport_size({'width':1440,'height':900})
    put('full_product_browser_action_geometry.json',{'status':'PASS','method':'Real viewport scroll to action, rendered dimensions and center hit-testing against actual assistant launcher; no action submissions.','checks':checks})

def request_dialog_keyboard():
    goto(LINKED);ready('.book-detail-view h1')
    keyboard_target(page.get_by_role('button',name='Request Book',exact=True))
    page.get_by_role('button',name='Cancel Request',exact=True).wait_for(timeout=60000)
    trigger=page.get_by_role('button',name='Cancel Request',exact=True);focus=keyboard_target(trigger)
    dialog=page.get_by_role('dialog',name='Cancel Request',exact=True);dialog.wait_for()
    page.keyboard.press('Escape');assert trigger.evaluate('e=>e===document.activeElement')
    keyboard_target(trigger)
    confirmation=dialog.get_by_role('button',name='Confirm',exact=True);keyboard_target(confirmation)
    page.get_by_role('button',name='Request Book',exact=True).wait_for(timeout=60000)
    put('full_product_browser_dialog_keyboard.json',{'status':'PASS','flow':'Keyboard Request Book -> pending -> Cancel confirmation -> Escape focus restore -> reopen -> keyboard Confirm cancellation','focus':focus,'restored':True,'pending_cancelled':True})

def contrast_samples():
    goto(LINKED);ready('.book-detail-view h1')
    samples=page.evaluate("""() => {
      const canvas=document.createElement('canvas');canvas.width=canvas.height=1;const ctx=canvas.getContext('2d',{willReadFrequently:true});
      const rgb=s=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=s;ctx.fillRect(0,0,1,1);const c=[...ctx.getImageData(0,0,1,1).data];c[3]/=255;return c};
      const linear=n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4};
      const lum=c=>.2126*linear(c[0])+.7152*linear(c[1])+.0722*linear(c[2]);
      const selectors=['.global-logo','.global-desktop-nav a','.book-detail-view h1','.book-facts dt','.book-save-button','.book-detail-body .rounded-full','.book-detail-view .font-display[style]','.book-detail-view .font-display[style]+div p','.assistant-launcher'];
      const output=[];for(const selector of selectors){const e=document.querySelector(selector);if(!e)continue;const s=getComputedStyle(e),ancestors=[];let p=e;while(p){ancestors.unshift(p);p=p.parentElement}let bg=[255,255,255];for(const node of ancestors){const c=rgb(getComputedStyle(node).backgroundColor);bg=bg.map((v,i)=>c[i]*c[3]+v*(1-c[3]))}const c=rgb(s.color),fg=bg.map((v,i)=>c[i]*c[3]+v*(1-c[3])),a=lum(fg),b=lum(bg);output.push({selector,text:e.textContent.trim().slice(0,70),foreground:s.color,background:bg,font_size:s.fontSize,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)})}return output;
    }""")
    assert samples and all(s['ratio']>=4.5 for s in samples),samples
    put('full_product_browser_contrast_samples.json',{'status':'PASS','method':'Computed styles on final real rendered elements, opaque nearest painted backgrounds; axe also measures rendered contrast across all 90 checked surfaces. Covers now have opaque text backplates to keep decorative rings/stripes from obscuring letters.','samples':samples})
