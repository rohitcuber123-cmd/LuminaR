"""Supplemental live keyboard, explicit authority and actual-title checks.

Loaded in the existing in-memory QA browser; never saves credentials or tokens.
"""

def platform_keyboard_and_revocation():
    global page,context
    context=platform_context;page=platform_page
    rows=[]
    goto('/platform');ready_platform()
    focus=keyboard_target(page.locator('.workspace-sidebar').get_by_role('link',name='Libraries',exact=True))
    ready_platform('tbody tr');rows.append({'flow':'Platform navigation with Tab/Enter','focus':focus,'status':'PASS'})
    search=page.get_by_role('searchbox');keyboard_target(search,'Space');search.fill('TEST')
    keyboard_target(page.get_by_role('button',name='Search',exact=True));page.get_by_role('link',name='View TEST',exact=True).wait_for()
    rows.append({'flow':'Search input and submit with keyboard','status':'PASS'})
    keyboard_target(page.get_by_role('link',name='View TEST',exact=True));ready_platform();page.get_by_role('heading',name='Library identity',exact=True).wait_for()
    rows.append({'flow':'Library row detail with keyboard','status':'PASS'})
    goto('/platform/libraries');ready_platform('tbody tr')
    status=page.get_by_role('combobox',name='Library status',exact=True)
    keyboard_target(status,'ArrowDown');status.press('Enter');ready_platform('tbody tr')
    rows.append({'flow':'Native lifecycle filter ArrowDown/Enter','status':'PASS'})
    kind=page.get_by_role('combobox',name='Library type',exact=True)
    keyboard_target(kind,'ArrowDown');kind.press('Enter');ready_platform('tbody tr')
    rows.append({'flow':'Native type filter ArrowDown/Enter','status':'PASS'})
    goto('/platform/libraries/'+disposable);ready_platform()
    trigger=page.get_by_role('button',name='Suspend Library',exact=True)
    focus=keyboard_target(trigger);dialog=page.get_by_role('dialog',name='Suspend Library',exact=True);dialog.wait_for()
    reason=dialog.get_by_label('Reason (required)',exact=True);reason.fill('Keyboard reason entry QA; no mutation submitted')
    assert not dialog.get_by_role('button',name='Suspend Library',exact=True).is_disabled()
    keyboard_target(dialog.get_by_role('button',name='Suspend Library',exact=True),'Escape');dialog.wait_for(state='hidden')
    assert trigger.evaluate('e=>e===document.activeElement')
    rows.append({'flow':'Danger dialog reason, keyboard confirmation focus, Escape and focus restore','focus':focus,'status':'PASS'})
    value=json.loads((REPORTS/'platform_accessibility.json').read_text());value['keyboard_checks']=rows;put('platform_accessibility.json',value)
    # Revoke only the explicitly approved dedicated local QA fixture. Its exact
    # existing approval is restored in finally; no legacy account is promoted.
    grant=db.platform_role_assignments.find_one({'user_id':qa['user_id'],'role':'PLATFORM_ADMIN','status':'ACTIVE'})
    assert grant and grant['approval_ref']=='USER-PLATFORM-COMPLETION-V1'
    try:
        db.platform_role_assignments.update_one({'_id':grant['_id']},{'$set':{'status':'REVOKED'}})
        denied=api('GET','/platform/libraries')[0];assert denied==403
        goto('/platform/libraries');page.get_by_text('Platform access required',exact=True).wait_for(timeout=60000)
        assert api('GET',f'/libraries/{disposable}/staff/loans')[0]==200
        boundary_checks.append({'flow':'Live PlatformRoleAssignment revocation denies API and browser; independent own-library ADMIN still works','http_status':denied,'status':'PASS'})
        shot('role_revocation_denied')
    finally:
        db.platform_role_assignments.update_one({'_id':grant['_id']},{'$set':{'status':grant['status']}})
    goto('/platform/libraries');ready_platform('tbody tr')
    assert api('GET','/platform/libraries')[0]==200
    boundary_checks.append({'flow':'Only original reviewed local QA assignment restored after isolated revocation test','status':'PASS'})
    put('platform_boundary_browser.json',{'status':'PASS','checks':boundary_checks})
    print('PLATFORM_KEYBOARD_REVOCATION_PASS',len(rows),flush=True)

def legacy_denial_browser():
    global page,context
    legacy_email='legacy-admin-denial-qa-'+secrets.token_hex(4)+'@example.com'
    legacy_secret=secrets.token_urlsafe(32);previous=auth_service.send_otp_email
    try:
        auth_service.send_otp_email=local_test_mail
        legacy=auth_service.register_user('Legacy ADMIN denial QA',legacy_email,legacy_secret)
        assert auth_service.verify_email_otp(legacy_email,mailbox.pop(legacy_email))
    finally:auth_service.send_otp_email=previous
    db.users.update_one({'user_id':legacy['user_id']},{'$set':{'role':'ADMIN'}})
    assert not db.platform_role_assignments.find_one({'user_id':legacy['user_id']})
    previous_context,previous_page=context,page
    legacy_context=browser.new_context(viewport={'width':1440,'height':900});context=legacy_context;page=context.new_page()
    try:
        goto('/login');page.locator('input[type=email]').fill(legacy_email);page.locator('input[type=password]').fill(legacy_secret)
        page.get_by_role('button',name='Sign In',exact=True).click();page.wait_for_url(lambda u:'/login' not in str(u),timeout=60000)
        assert api('GET','/platform/libraries')[0]==403
        goto('/platform/libraries');page.get_by_text('Platform access required',exact=True).wait_for(timeout=60000)
        shot('legacy_admin_denied')
        boundary_checks.append({'flow':'Historical User.role=ADMIN only, no PlatformRoleAssignment: actual normal login and Platform browser/API denial','qa_email':legacy_email,'status':'PASS'})
    finally:
        # Leave no usable unintended authority fixture after the denial check.
        db.users.update_one({'user_id':legacy['user_id']},{'$set':{'role':'GENERAL_USER','is_active':False}})
        legacy_context.close();context=previous_context;page=previous_page
    put('platform_boundary_browser.json',{'status':'PASS','checks':boundary_checks})
    print('LEGACY_ADMIN_BROWSER_DENIAL_PASS',flush=True)

def actual_title_matrix():
    global page,context
    context=patron_context;page=patron_page
    samples=[('very long linked title',PATRON_HOME+'/books/5f7d5aff-683b-4071-8b11-af079a5f9467'),
        ('short linked title',PATRON_HOME+'/books/8bfba0bf-641d-4a00-8c30-b0612c6baa93'),
        ('medium linked title',PATRON_HOME+'/books/21c2ae7e-3416-43b2-8f88-0fc6aaa5509a'),
        ('long global workbook',"/book/OL8831559W"),
        ('missing author actual global record','/book/OL24712944W'),
        ('local-only record',LOCAL)]
    # Resolve actual multiple-author and Money 1988 records without guessing IDs.
    multi=next(b for b in collection('library_books').find({'library_id':TEST,'status':'ACTIVE'}) if len(b.get('authors',[]))>1)
    samples.append(('multiple authors actual linked record',PATRON_HOME+'/books/'+multi['library_book_id']))
    goto('/search?q=Money+1988');ready('.product-book-card')
    money=next((c.locator('> a').first.get_attribute('href') for c in page.locator('.product-book-card').all() if 'money 1988' in (c.get_attribute('aria-label') or '').lower()),None)
    if money:samples.append(('short global title Money 1988',money))
    rows=[]
    for label,route in samples:
        goto(route);ready('.book-detail-view h1');page.locator('.book-cover-art').wait_for()
        for w,h in SIZES:
            page.set_viewport_size({'width':w,'height':h});page.evaluate('document.fonts.ready')
            data=cover_geometry('.book-cover-art')[0]
            assert data['text_inside'] and not data['title_author_overlap'] and data['scrims']==1 and data['copy_after_scrim'] and abs(data['ratio']-2/3)<.02
            cover=page.locator('.book-cover-art');cover.evaluate("e=>e.scrollIntoView({block:'center',behavior:'instant'})")
            filename='platform_completion_actual_'+re.sub('[^a-z0-9]+','_',label.lower())+f'_{w}x{h}.png'
            cover.screenshot(path=str(REPORTS/filename),animations='disabled')
            rows.append({'sample':label,'route':route,'viewport':f'{w}x{h}',**data,'screenshot':filename,'status':'PASS'})
        print('ACTUAL_COVER',label,data['title'],'PASS',flush=True)
    page.set_viewport_size({'width':1440,'height':900})
    value=json.loads((REPORTS/'book_cover_visual_validation.json').read_text());value['actual_title_samples']=rows;put('book_cover_visual_validation.json',value)
    print('ACTUAL_TITLE_MATRIX_PASS',len(rows),flush=True)

CONTRAST_SCRIPT="""selectors=>{
 const c=document.createElement('canvas');c.width=c.height=1;const ctx=c.getContext('2d',{willReadFrequently:true});
 const rgb=value=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=value;ctx.fillRect(0,0,1,1);const a=[...ctx.getImageData(0,0,1,1).data];a[3]/=255;return a};
 const linear=n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4};
 const lum=v=>.2126*linear(v[0])+.7152*linear(v[1])+.0722*linear(v[2]);
 const rows=[];
 for(const e of document.querySelectorAll(selectors)){
  const r=e.getBoundingClientRect(),s=getComputedStyle(e);
  if(!r.width||!r.height||s.visibility==='hidden'||e.closest('[disabled]')||!e.textContent.trim())continue;
  const ancestors=[];let p=e;while(p){ancestors.unshift(p);p=p.parentElement}
  let bg=[255,255,255];for(const a of ancestors){const v=rgb(getComputedStyle(a).backgroundColor);bg=bg.map((n,i)=>v[i]*v[3]+n*(1-v[3]))}
  const scrim=e.matches('.book-cover-title,.book-cover-author')?e.closest('.book-cover-copy')?.querySelector('.book-cover-text-scrim'):null;
  if(scrim)bg=rgb(getComputedStyle(scrim).backgroundColor).slice(0,3);
  const fg=rgb(s.color),painted=bg.map((n,i)=>fg[i]*fg[3]+n*(1-fg[3])),a=lum(painted),b=lum(bg);
  rows.push({element:e.tagName,classes:e.className,text:e.textContent.trim().slice(0,90),foreground:s.color,background:bg,font_size:s.fontSize,ratio:(Math.max(a,b)+.05)/(Math.min(a,b)+.05)});
 }
 return rows;
}"""

def final_contrast_and_product_audits():
    global page,context
    context=platform_context;page=platform_page
    contrast=[]
    for label in ['Suspend Library','Remove Library','Restore Library']:
        if label=='Restore Library':assert api('POST',f'/platform/libraries/{disposable}/suspend',{'idempotency_key':str(uuid4()),'expected_status':'ACTIVE','reason':'Final rendered contrast restore dialog QA'})[0]==200
        goto('/platform/libraries/'+disposable);ready_platform()
        page.get_by_role('button',name=label,exact=True).wait_for();page.get_by_role('button',name=label,exact=True).click()
        dialog=page.get_by_role('dialog',name=label,exact=True);dialog.wait_for()
        for w,h in SIZES:
            page.set_viewport_size({'width':w,'height':h})
            rows=page.evaluate(CONTRAST_SCRIPT,'dialog[open] h2,dialog[open] p,dialog[open] label,dialog[open] button:not([disabled])')
            assert rows and all(x['ratio']>=4.5 for x in rows),(label,w,rows)
            contrast.append({'surface':label,'viewport':f'{w}x{h}','samples':rows,'status':'PASS'})
        page.keyboard.press('Escape')
        if label=='Restore Library':assert api('POST',f'/platform/libraries/{disposable}/restore',{'idempotency_key':str(uuid4()),'expected_status':'SUSPENDED','reason':'Finish final rendered contrast restore dialog QA'})[0]==200
    value=json.loads((REPORTS/'platform_accessibility.json').read_text());value['rendered_dialog_contrast']=contrast
    value['manual_incomplete_resolution']='Axe cannot resolve some transparent paragraph backgrounds inside native modal dialogs. Actual computed text/opaque dialog paint gives at least 4.5:1 at every viewport; paragraph bounds and center hit-testing also show no overlap.'
    put('platform_accessibility.json',value)
    context=patron_context;page=patron_page
    cover_contrast=[]
    sample_rows=json.loads((REPORTS/'book_cover_visual_validation.json').read_text())['actual_title_samples']
    for route in dict.fromkeys(r['route'] for r in sample_rows):
        goto(route);ready('.book-detail-view h1')
        rows=page.evaluate(CONTRAST_SCRIPT,'.book-cover-brand,.book-cover-title,.book-cover-author')
        assert rows and all(x['ratio']>=4.5 for x in rows),(route,rows)
        cover_contrast.append({'route':route,'samples':rows,'status':'PASS'})
    value=json.loads((REPORTS/'book_cover_visual_validation.json').read_text());value['rendered_text_contrast']=cover_contrast;put('book_cover_visual_validation.json',value)
    # Refresh only the accessibility evidence after the shared rail group role
    # repair. Existing geometry/screenshots stay intact; actual DOM is measured.
    for role,pages,target_context,target_page in [('GENERAL_USER',PATRON_PAGES+[('TEST Local-only Detail',LOCAL,'.book-detail-view h1')],patron_context,patron_page),('ADMIN',STAFF_PAGES,owner_context,owner_context.pages[0])]:
        context=target_context;page=target_page
        for name,route,selector in pages:
            goto(route);ready(selector)
            for w,h in SIZES:
                page.set_viewport_size({'width':w,'height':h});audit=rendered_audit()
                assert not audit['violations'] and not any(i['id']!='color-contrast' for i in audit['incomplete']),(name,w,audit)
                row=next(r for r in accessibility if r['page']==name and r['viewport']==f'{w}x{h}');row.update(audit)
            print('FINAL_A11Y',name,'PASS',flush=True)
    context=patron_context;page=patron_page;page.set_viewport_size({'width':1440,'height':900})
    put('platform_completion_product_accessibility.json',{'status':'PASS','checks':accessibility,'manual_contrast':'Generated covers use their actual opaque single scrim. Offscreen/clipped rail text is not presented as a resolved axe contrast check; visible actions were scrolled into view and independently hit-tested.'})

def finish_runtime_cleanup():
    global page,context
    context=patron_context;page=patron_page
    goto(PATRON_HOME);ready('#new-arrivals .product-book-card')
    switch=page.get_by_role('combobox',name='Switch patron library',exact=True)
    switch.select_option(disposable);page.wait_for_url(lambda u:'/libraries/'+disposable in str(u),timeout=60000);ready('#new-arrivals .product-book-card')
    assert page.locator('.global-logo').get_attribute('href')=='/libraries/'+disposable
    page.get_by_role('link',name='My reading list',exact=True).click();ready('main h1')
    assert page.locator('.global-logo').get_attribute('href')=='/libraries/'+disposable
    goto(PATRON_HOME);ready('#new-arrivals .product-book-card')
    value=json.loads((REPORTS/'patron_home_context_repair.json').read_text());value['checks'].append({'flow':'Real explicit library switch immediately updates Home and personal return; switch back to TEST','status':'PASS'});put('patron_home_context_repair.json',value)
    cleanup_personal()
    # Finish the disposable loan and remove only the additional QA membership,
    # using canonical tenant APIs with the QA owner's independent membership.
    context=platform_context;page=platform_page
    loan=collection('loans').find_one({'library_id':disposable,'user_id':10,'status':'ACTIVE'})
    assert loan
    status,_=api('POST',f'/libraries/{disposable}/staff/loans/{loan["loan_id"]}/receive',{'idempotency_key':str(uuid4())});assert status==200
    member=collection('memberships').find_one({'library_id':disposable,'user_id':10,'status':'ACTIVE'});assert member
    status,_=api('PATCH',f'/libraries/{disposable}/memberships/{member["membership_id"]}',{'status':'REMOVED'});assert status==200
    assert collection('loans').find_one({'loan_id':loan['loan_id']})['status']=='RETURNED'
    assert collection('memberships').find_one({'membership_id':member['membership_id']})['status']=='REMOVED'
    assert not db.institution_memberships.find_one({'user_id':qa['user_id'],'library_id':TEST})
    record_runtime_cleanup()

def record_runtime_cleanup():
    assert collection('loans').find_one({'library_id':disposable,'user_id':10,'status':'RETURNED'})
    assert collection('memberships').find_one({'library_id':disposable,'user_id':10,'status':'REMOVED'})
    assert collection('libraries').find_one({'library_id':disposable})['status']=='ACTIVE'
    # JUnit embeds parameter values in case names. Existing password-policy
    # fixtures happen to reuse a supplied QA password: redact those labels in
    # this phase's test artifacts, preserving pass/failure/skipped outcomes.
    secret_values=[secret,*[credentials(a)[1] for a in ['staff','patron']]]
    scanned=0;redacted=[]
    for folder in [REPORTS,ROOT/'scripts',ROOT/'.scratch/platform-completion']:
        for p in folder.iterdir():
            if p.is_file() and p.suffix in {'.json','.md','.log','.py','.ps1','.mjs','.xml'} and (folder!=REPORTS or p.name.startswith('platform_completion_') or p.name in ['platform_libraries_browser.json','platform_library_lifecycle_browser.json','platform_boundary_browser.json','platform_responsive.json','platform_accessibility.json','staff_home_context_repair.json','patron_home_context_repair.json','book_cover_visual_validation.json','book_card_layout_validation.json']):
                data=p.read_text(encoding='utf8',errors='replace')
                if p.suffix in {'.xml','.log'} and folder==REPORTS:
                    clean=data
                    for value in secret_values:clean=clean.replace(value,'[REDACTED TEST PARAMETER]')
                    if clean!=data:p.write_text(clean,encoding='utf8');redacted.append(p.name);data=clean
                assert not any(value in data for value in secret_values),'Credential found in '+p.name
                scanned+=1
    previous_report=REPORTS/'platform_completion_qa_cleanup.json'
    if previous_report.exists():redacted=sorted(set(redacted+json.loads(previous_report.read_text()).get('redacted_inherited_test_parameter_labels',[])))
    put('platform_completion_qa_cleanup.json',{'status':'PASS','personal_QA_additions_restored_via_UI':True,'disposable_loan_returned_via_canonical_API':True,'additional_patron_membership_removed_via_independent_QA_owner_ADMIN':True,'legacy_denial_fixture_disabled':True,'original_reviewed_QA_platform_assignment_active':True,'unexpected_TEST_grants':0,'credential_file_scan_pass':True,'text_files_scanned':scanned,'redacted_inherited_test_parameter_labels':redacted})
    put('platform_completion_runtime_browser.json',{'status':'PASS','engine':'Actual Chromium / Playwright','browser_version':browser.version,'frontend':BASE,'normal_logins':['Dedicated Platform QA','rohitcuber123@gmail.com','karthikeya.ixa.10@gmail.com','Isolated legacy ADMIN denial fixture'],
        'page_errors':errors,'qa_email':qa_email,'QA_platform_account_created':True,'explicit_assignment':True,'TEST_platform_QA_membership':False,'walk_steps':len(walk),'deep_link_checks':len(history_checks),'product_keyboard_checks':9,'platform_keyboard_checks':6,'credential_capture':False})
    goto('/platform/libraries');ready_platform('tbody tr')
    print('QA_CLEANUP_RUNTIME_PASS',scanned,'files','page_errors',len(errors),flush=True)
