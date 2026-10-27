"""Native cover/context sweep using real catalogue metadata and safe reading-list QA."""
exec((ROOT/'scripts/institution_v2f1_browser.py').read_text(encoding='utf8'))
exec((ROOT/'scripts/institution_v2f1_visual_browser.py').read_text(encoding='utf8'))
fresh_login('patron');goto(f'/reading-list?patron_library={TEST}')
page.get_by_role('heading',name='My Reading List',exact=True).wait_for(timeout=45000)
page.wait_for_timeout(800)
added=False
if not page.locator('.book-cover-art').count():
    goto('/catalog');page.locator('.product-book-card').first.wait_for(timeout=45000)
    button=page.get_by_role('button',name='Add to Reading List',exact=True).first
    button.click();page.get_by_role('button',name='In Reading List ✓',exact=True).first.wait_for(timeout=45000)
    added=True
surface_matrix()
samples=named_cover_samples();sample_matrix(samples)
assert all(r['status']=='PASS' for r in responsive_rows)
put('institution_v2f1_consolidated_covers.json',{'status':'PASS','checks':cover_rows,'responsive':responsive_rows,'samples':samples,'original_palette_preserved':True,'backplates':False,'safe_reading_list_addition':added})
print('PASS consolidated original cover matrix',len(responsive_rows),flush=True)
