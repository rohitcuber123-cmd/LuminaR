"""Check real sign-in and platform boundary; never grant a role from legacy ADMIN."""
print(login('platform'),flush=True)
rows=[]
page.goto(BASE+'/platform',wait_until='domcontentloaded')
page.get_by_text('Platform access required',exact=True).wait_for(timeout=60000)
assert page.get_by_text('This console requires an explicitly approved platform assignment.',exact=True).is_visible()
for width,height in [(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]:
    page.set_viewport_size({'width':width,'height':height})
    rows.append(page.evaluate("""() => ({viewport:innerWidth+'x'+innerHeight,document_width:document.documentElement.scrollWidth,title:document.querySelector('.ui-state strong')?.textContent,role_boundary:'Explicit platform assignment required',result:'AUTHORIZED_SURFACE_NOT_VERIFIED'})"""))
    shot('platform_boundary_'+str(width))
put('full_product_browser_platform.json',{'status':'PARTIAL','account':'User-supplied legacy Admin QA account','login':'PASS','platform_boundary':'PASS: rejected legacy-only Admin','explicit_assignment':False,'libraries_route':'No /platform/libraries route exists in accepted route inventory; tenant library management remains membership-scoped Staff Workspace. No new platform feature was invented.','rows':rows})
print('Platform sign-in PASS; legacy-only ADMIN denied correctly; authorized Console not verified.',flush=True)
