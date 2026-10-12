"""Read-only real TEST Staff activity/audit addendum checks in the browser console."""
import time
import sys
import requests
from datetime import datetime, timezone
sys.path.insert(0, str(ROOT))
from backend.database.mongodb import db

SIZES = [(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]
activity_rows=[];audit_rows=[]
exec((ROOT/'scripts/institution_v2f_browser_checks.py').read_text(encoding='utf8').split('def check(')[0],globals())


def activity_login(account):
    global context, page
    context.close()
    context=browser.new_context(viewport={'width':1440,'height':900})
    page=context.new_page()
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('response',lambda response:network.append({'path':urlparse(response.url).path,'status':response.status}) if '/api/' in response.url else None)
    return login(account)


def activity_measure(route,size):
    page.set_viewport_size({'width':size[0],'height':size[1]})
    goto(f'/staff/libraries/{TEST}/{route}')
    label='Operational activity' if route=='activity' else 'Library audit'
    table=page.get_by_role('table',name=label,exact=True)
    table.wait_for(timeout=60000)
    page.evaluate('document.fonts.ready')
    region=page.get_by_role('region',name=label,exact=True)
    geometry=page.evaluate('''()=>{
      const region=document.querySelector('.staff-activity-results .staff-table-wrap'),table=region.querySelector('table');
      const r=region.getBoundingClientRect();
      return {document_width:document.documentElement.scrollWidth,viewport:innerWidth,region:{x:r.x,right:r.right,width:r.width,client_width:region.clientWidth,scroll_width:region.scrollWidth,overflow:getComputedStyle(region).overflowX},table_width:table.getBoundingClientRect().width,headers:[...table.querySelectorAll('th')].map(h=>({name:h.textContent,scope:h.scope})),cells:[...table.querySelectorAll('tbody td')].map(td=>{const s=getComputedStyle(td),r=td.getBoundingClientRect();return {x:r.x,right:r.right,padding_left:parseFloat(s.paddingLeft),padding_right:parseFloat(s.paddingRight),padding_top:parseFloat(s.paddingTop),line_height:parseFloat(s.lineHeight)}}),references:[...table.querySelectorAll('.staff-activity-reference')].map(e=>({full:e.title,accessible:e.querySelector('.sr-only').textContent,visible:e.querySelector('[aria-hidden]').textContent,width:e.getBoundingClientRect().width,cell_width:e.closest('td').getBoundingClientRect().width})),pager:[...document.querySelectorAll('.staff-activity-results .staff-pager button')].map(b=>{const r=b.getBoundingClientRect();return {name:b.textContent,width:r.width,height:r.height}})}
    }''')
    assert geometry['document_width']<=size[0]+1
    assert geometry['region']['x']>=-1 and geometry['region']['right']<=size[0]+1
    assert all(c['padding_left']>=12 and c['padding_right']>=12 and c['padding_top']>=12 and c['line_height']>=20 for c in geometry['cells'])
    assert all(h['scope']=='col' for h in geometry['headers'])
    assert all(r['full']==r['accessible'] and r['width']<r['cell_width'] and len(r['visible'])<=20 for r in geometry['references'])
    assert all(p['height']>=44 for p in geometry['pager'])
    page.keyboard.press('Tab');region.focus()
    assert region.evaluate('(e)=>e===document.activeElement')
    focus=region.evaluate('(e)=>({style:getComputedStyle(e).outlineStyle,width:getComputedStyle(e).outlineWidth})')
    assert focus['style']!='none' and float(focus['width'].replace('px',''))>=2
    if geometry['region']['scroll_width']>geometry['region']['client_width']:
        for _ in range(6): page.keyboard.press('ArrowRight')
        page.wait_for_timeout(300)
        assert region.evaluate('(e)=>e.scrollLeft')>0
        region.evaluate('(e)=>e.scrollLeft=0')
    page.evaluate('window.scrollTo(0,0)')
    page.add_script_tag(path=str(ROOT/'frontend/node_modules/axe-core/axe.min.js'))
    axe=page.evaluate("async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});return {violations:r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),passes:r.passes.length}}")
    assert not axe['violations'],axe
    contrasts=contrast_nodes(label,size,['.staff-activity-results th','.staff-activity-results td','.staff-activity-results .staff-activity-identity-note','.staff-activity-results button:not([disabled])'])
    assert all(row['ratio']>=row['required'] for row in contrasts),[r for r in contrasts if r['ratio']<r['required']]
    if size[0] in [1440,375]:
        page.screenshot(path=str(REPORTS/f'institution_v2f_{route}_{size[0]}.png'),full_page=False,animations='disabled')
    return {'route':f'/staff/libraries/{TEST}/{route}','viewport':list(size),'status':'PASS','geometry':geometry,'axe':axe,'contrast':contrasts,'keyboard_region_focus_and_scroll':'PASS','visible_focus':focus}


def validate_activity_addendum():
    activity_login('staff')
    canonical={row['user_id']:row['email'] for row in db.users.find({'user_id':{'$in':[4,10]}},{'_id':0,'user_id':1,'email':1})}
    token=page.evaluate("localStorage.getItem('luminar_token')")
    timings=[]
    for route in ['activity','audit']:
        path=f'/libraries/{TEST}/'+('staff/activity' if route=='activity' else 'audit')
        started=time.perf_counter()
        for attempt in range(10):
            response=requests.get('http://127.0.0.1:8002'+path,headers={'Authorization':'Bearer '+token},timeout=30)
            if response.status_code!=503:break
            time.sleep(.3)
        assert response.status_code==200, f'{route} API status {response.status_code}'
        data=response.json();timings.append({'surface':route,'milliseconds':round((time.perf_counter()-started)*1000,2),'rows':len(data['results'])})
        assert any(r['actor_user_id']==4 and r['actor']['email']==canonical[4] for r in data['results'])
        if route=='activity':
            assert any(r.get('target_user_id')==10 and r['member']['email']==canonical[10] for r in data['results'])
            assert any(r.get('actor') and r.get('member') and r['actor']['user_id']!=r['member']['user_id'] for r in data['results'])
        rows=activity_rows if route=='activity' else audit_rows
        for size in SIZES:
            rows.append(activity_measure(route,size));print('PASS',route,size,flush=True)
        goto(f'/staff/libraries/{TEST}/{route}')
        page.get_by_role('table',name='Operational activity' if route=='activity' else 'Library audit',exact=True).wait_for()
        assert page.get_by_text(canonical[4],exact=True).count()>0
        if route=='activity':assert page.get_by_text(canonical[10],exact=True).count()>0
        cells=page.locator('.staff-activity-table tbody').inner_text()
        assert not re.search(r'(?:User|Account) #(?:4|10)\b',cells)
        nav=page.get_by_role('navigation',name=('Operational activity' if route=='activity' else 'Library audit')+' pagination')
        nav.get_by_role('button',name='Next',exact=True).focus()
        with page.expect_response(lambda r:path in r.url and 'offset=20' in r.url,timeout=45000) as next_page:
            page.keyboard.press('Enter')
        assert next_page.value.status==200
        nav.get_by_text(re.compile(r'^21–40 of')).wait_for()
        nav.get_by_role('button',name='Previous',exact=True).click()
        nav.get_by_text(re.compile(r'^1–20 of')).wait_for()
    activity_login('patron')
    patron_token=page.evaluate("localStorage.getItem('luminar_token')")
    for route in ['staff/activity','audit']:
        for attempt in range(10):
            r=requests.get(f'http://127.0.0.1:8002/libraries/{TEST}/{route}',headers={'Authorization':'Bearer '+patron_token},timeout=30)
            if r.status_code!=503:break
            time.sleep(.3)
        assert r.status_code==403 and canonical[4] not in r.text, f'Patron {route} status {r.status_code}'
    for route in ['activity','audit']:
        goto(f'/staff/libraries/{TEST}/{route}')
        page.wait_for_url(lambda url:'/staff/libraries/' not in str(url),timeout=30000)
    assert not errors,errors
    baseline=json.loads((REPORTS/'institution_v2f_activity_baseline.json').read_text(encoding='utf8'))
    from scripts.institution_v2f_baseline import digest
    final_audits=list(db.institution_audit.find({'library_id':TEST},{'_id':0}))
    assert len(final_audits)==baseline['audit_rows']['count'] and digest(final_audits)==baseline['audit_rows']['sha256']
    shared={'status':'PASS','captured_at':datetime.now(timezone.utc).isoformat(),'canonical_owner_email_verified':True,'canonical_member_email_verified':True,'actor_member_distinct':True,'raw_resolvable_user_number_primary':False,'canonical_audit_rows_unchanged':True,'lookup_semantics':'CURRENT_ACCOUNT; existing target email snapshot only when current identity unavailable','pagination_keyboard':'PASS','patron_API_and_browser_denied':True,'page_errors':errors,'local_API_timings':timings}
    put('institution_v2f_activity_table_validation.json',{**shared,'viewports':activity_rows})
    put('institution_v2f_audit_identity_validation.json',{**shared,'viewports':audit_rows})
    print('Activity/audit addendum browser PASS',flush=True)
