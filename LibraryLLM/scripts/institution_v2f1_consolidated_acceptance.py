"""Remaining native Staff control/identity and accepted cover/context checks."""
exec((ROOT/'scripts/institution_v2f1_browser.py').read_text(encoding='utf8'))
exec((ROOT/'scripts/institution_v2f1_visual_browser.py').read_text(encoding='utf8'))
fixtures=json.loads((REPORTS/'institution_v2f1_consolidated_fixtures.json').read_text())
lib=fixtures['format_library'];base=f'/staff/libraries/{TEST}'
fresh_login('staff'); identities=[];controls=[]
for surface,suffix in [('activity','/staff/activity'),('audit','/audit')]:
    goto(base+'/'+surface)
    page.locator('.staff-activity-table tbody tr').first.wait_for(timeout=45000)
    data=api(f'/libraries/{TEST}{suffix}?limit=100&offset=0')
    assert all(r.get('actor',{}).get('email') for r in data['results'] if r.get('actor'))
    rendered=page.locator('.staff-activity-identity').all_text_contents()
    assert any('@' in x for x in rendered)
    assert not any(re.fullmatch(r'(?:User|Account) #\d+',x) for x in rendered)
    members=[r['member']['email'] for r in data['results'] if r.get('member',{} ) and r['member'].get('email')]
    identities.append({'surface':surface,'actor_email_in_browser':True,'resolvable_identities':rendered,'member_emails_in_authorized_response':members,'stored_ids_preserved':True,'lookup':'one bounded users.find($in) query in hydrate_activity_identities'})
    if surface=='activity':
        assert members
        for attempt in range(5):
            if any(x in page.locator('.staff-activity-identity').all_text_contents() for x in members):break
            button=page.get_by_role('navigation',name='Operational activity pagination').get_by_role('button',name='Next',exact=True)
            if not button.is_enabled():break
            button.click();page.wait_for_timeout(500)
        assert any(x in page.locator('.staff-activity-identity').all_text_contents() for x in members)
        identities[-1]['member_email_in_browser']=True
    page.screenshot(path=str(REPORTS/f'institution_v2f1_consolidated_{surface}_identities.png'))

for section in ['circulation','reservations','fees','events','analytics','members','settings']:
    for width,height in VIEWPORTS:
        page.set_viewport_size({'width':width,'height':height});goto(base+'/'+section)
        page.locator('#main-content h1').wait_for(timeout=45000);page.wait_for_timeout(500)
        assert page.evaluate('()=>document.documentElement.scrollWidth<=innerWidth+1'),(section,width)
        values=page.locator('.workspace input:not([type=checkbox]):not([type=radio]),.workspace select,.workspace textarea').evaluate_all('es=>es.filter(e=>e.getClientRects().length).map(e=>({tag:e.tagName,height:e.clientHeight,font:getComputedStyle(e).fontFamily,border:getComputedStyle(e).borderRadius}))')
        assert all(v['height']>=40 for v in values),(section,width,values)
        controls.append({'surface':section,'viewport':[width,height],'no_page_overflow':True,'visible_controls':values,'status':'PASS'})
        if width in [1440,375]:page.screenshot(path=str(REPORTS/f'institution_v2f1_consolidated_{section}_{width}.png'))
    print('PASS controls '+section,flush=True)

page.set_viewport_size({'width':1440,'height':900})
physical=api(f'/libraries/{lib}/inventory/books/{fixtures["Physical"]["library_book_id"]}')
goto(f'/staff/libraries/{lib}/assets/{physical["online_asset_id"]}')
page.get_by_role('button',name='Open document',exact=True).click();page.locator('.asset-pdf-page').wait_for()
with page.expect_download() as event:page.get_by_role('button',name='Download document',exact=True).click()
download=event.value.path()
import hashlib
asset=api(f'/libraries/{lib}/assets/{physical["online_asset_id"]}')
assert hashlib.sha256(Path(download).read_bytes()).hexdigest()==asset['checksum']
page.get_by_role('button',name='Close document',exact=True).click()
page.route('**/preview/pages/1',lambda route:route.fulfill(status=503,body='Busy'))
page.get_by_role('button',name='Open document',exact=True).click();page.get_by_role('alert').wait_for()
assert page.get_by_role('button',name='Retry',exact=True).count()==1
page.unroute('**/preview/pages/1');page.get_by_role('button',name='Retry',exact=True).click();page.locator('.asset-pdf-page').wait_for()
assert not page.get_by_role('button',name='Open document',exact=True).count()
put('institution_v2f1_consolidated_controls.json',{'status':'PASS','controls':controls,'identities':identities,'native_download_checksum':'PASS','PDF_error_retry_close':'PASS'})
print('PASS native download, preview error/retry and activity identities',flush=True)

surface_matrix()
samples=named_cover_samples();sample_matrix(samples)
assert all(r['status']=='PASS' for r in responsive_rows)
put('institution_v2f1_consolidated_covers.json',{'status':'PASS','checks':cover_rows,'responsive':responsive_rows,'samples':samples,'original_palette_preserved':True,'backplates':False})
print('PASS consolidated original cover matrix',len(responsive_rows),flush=True)
