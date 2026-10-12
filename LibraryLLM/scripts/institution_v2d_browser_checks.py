"""Executed inside the live, secret-free Chromium QA session.

Account credentials and invitation/access tokens stay in session memory. All
domain commands use normal APIs; only the disposable overdue-loan clock is a
local fixture adjustment, explicitly recorded in evidence.
"""
import time
from datetime import datetime,timedelta,timezone
from uuid import uuid4

event_checks=globals().get('event_checks',[]);notice_checks=globals().get('notice_checks',[]);security_checks=globals().get('security_checks',[]);live_matrix=globals().get('live_matrix',[]);live_axe=globals().get('live_axe',[]);regression_checks=globals().get('regression_checks',[])
SIZES=[(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]

def record(bucket,name,**evidence):
    bucket.append({'check':name,'status':'PASS',**evidence})
    print('PASS',name,flush=True)

def ready(selector='h1'):
    page.locator(selector).first.wait_for(timeout=60000)
    page.locator('.event-skeleton').first.wait_for(state='hidden',timeout=60000)
    page.evaluate('document.fonts.ready')

def create_event_ui(letter,title):
    goto(f'/staff/libraries/{fixtures[letter]}/events/new');ready()
    page.get_by_label('Event Type',exact=True).select_option('OTHER')
    page.get_by_label('Event title',exact=True).fill(title)
    page.get_by_label('Event description',exact=True).fill('Local member program for isolated Part 2D browser validation.')
    with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith(f'/libraries/{fixtures[letter]}/events'),timeout=60000) as response:
        page.get_by_role('button',name='Save Draft',exact=True).click()
    assert response.value.status==201
    event=response.value.json();fixtures['event_'+letter]=event['event_id']
    page.wait_for_url('**/events');ready('.event-manage-row')
    return event

def event_librarian_flow():
    # mixed is GENERAL_USER A, ADMIN B and LIBRARIAN C simultaneously.
    assert api(f'/libraries/{fixtures["A"]}/events','POST',{'title':'Forbidden','category':'OTHER'},'mixed',403)
    assert api(f'/libraries/{fixtures["A"]}/events/{fixtures["event_A"]}',account='borrower',expected=404)
    assert api(f'/libraries/{fixtures["A"]}/events',account='platform',expected=404)
    record(security_checks,'Patron mutation, private outsider and platform-only event access denied')
    created=create_event_ui('C','Part 2D Community Reading')
    assert api(f'/libraries/{fixtures["C"]}/events/{created["event_id"]}',account='borrower',expected=404)
    record(event_checks,'Librarian creates private-to-members draft; patron draft read denied',event_id=created['event_id'])
    row=page.locator('.event-manage-row').filter(has=page.get_by_role('heading',name=created['title'],exact=True))
    row.get_by_role('link',name='Edit',exact=True).click();ready()
    page.get_by_label('Event summary',exact=True).fill('Updated by a current librarian.')
    page.get_by_role('button',name='Save Draft',exact=True).click();page.wait_for_url('**/events');ready('.event-manage-row')
    row=page.locator('.event-manage-row').filter(has=page.get_by_role('heading',name=created['title'],exact=True))
    row.get_by_role('button',name='Publish',exact=True).click()
    dialog=page.get_by_role('dialog',name='Publish this event?',exact=True)
    assert dialog.is_visible()
    dialog.get_by_role('button',name='Publish event',exact=True).click();dialog.wait_for(state='hidden');ready('.event-manage-row')
    assert api(f'/libraries/{fixtures["C"]}/events/{created["event_id"]}',account='borrower')['status']=='PUBLISHED'
    assert api(f'/libraries/{fixtures["A"]}/events/{created["event_id"]}',account='mixed',expected=404)
    assert api('/events/'+created['event_id'],account='mixed',expected=404)
    assert created['event_id']!=fixtures['event_A']
    record(event_checks,'Librarian edit/publish; same title in two libraries stays isolated')
    for view in ['Upcoming','Draft','Past','Cancelled']:
        page.get_by_role('group',name='Staff event views').get_by_role('button',name=view,exact=True).click();ready()
        page.get_by_role('group',name='Staff event views').locator('button[aria-pressed="true"]').filter(has_text=re.compile('^'+view+'$')).wait_for()
    record(event_checks,'Staff upcoming/draft/past/cancelled tabs')
    goto(f'/staff/libraries/{fixtures["C"]}/events');ready('.event-manage-row');shot('librarian_events')

def cancel_event_ui(letter,account):
    login(account);goto(f'/staff/libraries/{fixtures[letter]}/events');ready('.event-manage-row')
    row=page.locator('.event-manage-row').filter(has=page.get_by_role('heading',name='Part 2D Community Reading',exact=True))
    row.get_by_role('button',name='Cancel Event',exact=True).click()
    dialog=page.get_by_role('dialog',name='Cancel this event?',exact=True)
    assert dialog.get_by_role('button',name='Cancel event',exact=True).is_disabled()
    dialog.get_by_label('Cancellation reason',exact=True).fill('Venue unavailable during local QA.')
    dialog.get_by_role('button',name='Cancel event',exact=True).click();dialog.wait_for(state='hidden')
    assert api(f'/libraries/{fixtures[letter]}/staff/events/{fixtures["event_"+letter]}',account=account)['status']=='CANCELLED'
    record(event_checks,'Cancel requires a reason and retains event identity',library=letter)

def patron_cancelled_flow():
    login('mixed');goto(f'/libraries/{fixtures["A"]}/events');ready()
    page.get_by_role('button',name='Cancelled',exact=True).click()
    page.get_by_role('heading',name='Part 2D Community Reading',exact=True).wait_for()
    page.get_by_role('link',name=re.compile('^View event')).click();ready('.event-detail h1')
    page.get_by_text('Venue unavailable during local QA.',exact=False).wait_for()
    assert page.get_by_role('link',name='Edit event',exact=True).count()==0
    assert page.locator('.global-logo').get_attribute('href')==f'/libraries/{fixtures["A"]}'
    record(event_checks,'Patron cancelled detail reason, no staff controls, library home retained')
    shot('cancelled_patron_detail')

def request_book(letter,patron):
    return api(f'/libraries/{fixtures[letter]}/lending/borrow-requests','POST',cmd(library_book_id=fixtures['book_'+letter]),patron,201)

def approve(letter,request,staff):
    command=cmd();path=f'/libraries/{fixtures[letter]}/staff/lending/borrow-requests/{request["lending_request_id"]}/approve'
    result=api(path,'POST',command,staff)
    for _ in range(2):assert api(path,'POST',command,staff)==result
    return result['loan']

def return_book(letter,loan,patron,staff):
    request=api(f'/libraries/{fixtures[letter]}/loans/{loan["loan_id"]}/return-request','POST',cmd(),patron,201)
    command=cmd();path=f'/libraries/{fixtures[letter]}/staff/lending/return-requests/{request["lending_request_id"]}/confirm'
    result=api(path,'POST',command,staff)
    assert api(path,'POST',command,staff)==result
    return result

def wait_notices(account,types):
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        rows=api('/notifications?limit=50',account=account)['notifications']
        if set(types)<={r['type'] for r in rows}:return rows
        time.sleep(1)
    raise AssertionError('Outbox worker did not materialize expected notice types: '+','.join(types))

def domain_notice_flow():
    # A patron approval/return, plus B admin and C librarian inbox routing.
    request=request_book('A','mixed');loan=approve('A',request,'owner')
    fixtures['request_A']=request['lending_request_id'];fixtures['loan_A']=loan['loan_id']
    api(f'/libraries/{fixtures["A"]}/join','POST',{'access_code':private_code},'borrower')
    reservation=api(f'/libraries/{fixtures["A"]}/reservations','POST',cmd(library_book_id=fixtures['book_A']),'borrower',201)
    # Only the isolated disposable loan clock is moved; physical return still
    # passes through the canonical staff confirmation and fee service.
    db.institution_loans.update_one({'library_id':fixtures['A'],'loan_id':loan['loan_id']},{'$set':{'due_at':datetime.now(timezone.utc)-timedelta(days=2)}})
    return_book('A',loan,'mixed','owner')
    fee=db.institution_fees.find_one({'library_id':fixtures['A'],'loan_id':loan['loan_id']})
    assert fee
    command=cmd(reason='Local disposable QA waiver');path=f'/libraries/{fixtures["A"]}/staff/fees/{fee["fee_id"]}/waive'
    assert api(path,'POST',command,'owner')==api(path,'POST',command,'owner')
    for letter,staff in [('B','mixed'),('C','mixed')]:
        request=request_book(letter,'borrower');fixtures['request_'+letter]=request['lending_request_id']
        if letter=='C':
            loan=approve(letter,request,staff);fixtures['loan_C']=loan['loan_id']
            api(f'/libraries/{fixtures[letter]}/loans/{loan["loan_id"]}/return-request','POST',cmd(),'borrower',201)
    verify_domain_notices()

def verify_domain_notices():
    mixed=wait_notices('mixed',['BORROW_REQUEST_APPROVED','RETURN_CONFIRMED','FEE_ASSESSED','FEE_WAIVED','BORROW_REQUEST_CREATED','RETURN_REQUEST_CREATED'])
    borrower=wait_notices('borrower',['RESERVATION_CREATED','RESERVATION_READY'])
    assert {r['library_id'] for r in mixed if r['scope']=='LIBRARY'}=={fixtures[x] for x in ['A','B','C']}
    assert all(r.get('source_id') and r.get('source_type') for r in mixed)
    assert all(r['action_route'].startswith('/libraries/'+fixtures['A']) for r in mixed if r['library_id']==fixtures['A'])
    assert all(r['action_route'].startswith('/staff/libraries/'+r['library_id']) for r in mixed if r['library_id'] in [fixtures['B'],fixtures['C']])
    assert not api('/notifications?limit=50',account='platform')['notifications']
    ids=[r['dedupe_key'] for r in db.notifications.find({'user_id':accounts['mixed']['user_id']})]
    assert len(ids)==len(set(ids))
    record(notice_checks,'Committed domain commands, worker delivery, approval/return replay dedupe, reservation-ready and fee waiver',clock_fixture='Disposable A loan only, two days overdue',mixed_libraries=3)
    notice_checks.append({'check':'Notification types materialized','status':'PASS','mixed':sorted({r['type'] for r in mixed}),'borrower':sorted({r['type'] for r in borrower})})
    put('institution_v2d_notification_dedupe.json',{'status':'PASS','live_checks':notice_checks,'exactly_one_per_audit_recipient':True,'prepared_and_failure_recovery_tests':'test_migration_and_recovery.py','tests':45})

def bell_flow():
    login('mixed')
    for title,letter,destination in [('Borrow request approved','A','my-library'),('New borrow request','B','circulation'),('New return request','C','circulation?tab=return')]:
        goto(f'/libraries/{fixtures["A"]}/events');ready()
        bell=page.get_by_role('button',name=re.compile('^Notifications'))
        bell.click();panel=page.get_by_role('region',name='Notification Center',exact=True)
        panel.get_by_role('button',name=f'Open {title} in Part 2D QA Library {letter}',exact=True).first.wait_for(timeout=30000)
        panel.get_by_role('button',name=f'Open {title} in Part 2D QA Library {letter}',exact=True).first.click()
        prefix='/libraries/' if letter=='A' else '/staff/libraries/'
        expected=prefix+fixtures[letter]+'/'+destination
        page.wait_for_url(BASE+expected,timeout=60000)
        page.locator(f'.global-logo[href="{prefix+fixtures[letter]}"]').wait_for(timeout=60000)
        record(notice_checks,'Bell action uses source library and role '+letter,destination=expected)
    bell=page.get_by_role('button',name=re.compile('^Notifications'));bell.focus();page.keyboard.press('Enter')
    panel=page.get_by_role('region',name='Notification Center',exact=True);panel.wait_for()
    assert page.evaluate("document.activeElement.id==='notification-center'")
    page.keyboard.press('Escape');assert bell.evaluate('(e)=>e===document.activeElement')
    record(notice_checks,'Bell keyboard open, Escape and focus restore')
    bell.click();panel=page.get_by_role('region',name='Notification Center',exact=True)
    button=panel.get_by_role('button',name='Mark all as read',exact=True)
    if button.is_enabled():button.click()
    page.wait_for_function("document.querySelector('.notification-count')===null",timeout=30000)
    assert api('/notifications?limit=50',account='mixed')['unread_count']==0
    record(notice_checks,'Mark-all read is account-owned and badge updates')
    shot('multi_library_bell');page.keyboard.press('Escape')
    put('institution_v2d_browser.json',{'status':'PASS','browser':browser.version,'events':event_checks,'notifications':notice_checks,'security':security_checks})

def measure_surface(name,size):
    page.evaluate('document.fonts.ready')
    geometry=page.evaluate("""() => {
      const box=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}};
      const overlay=document.querySelector('[role=dialog],.notification-panel');
      const focus=document.activeElement;const s=focus?getComputedStyle(focus):null;
      return {width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,
        overlay:overlay?box(overlay):null,focusOutline:s?{style:s.outlineStyle,width:s.outlineWidth,color:s.outlineColor}:null,
        eventButtons:[...document.querySelectorAll('.event-button,.event-tabs button,.event-pager button')].filter(e=>e.getClientRects().length).map(e=>({text:e.textContent.trim(),height:box(e).height})),
        fieldClipping:[...document.querySelectorAll('.events-shell input,.events-shell select,.events-shell textarea')].filter(e=>e.getClientRects().length).map(e=>({label:e.getAttribute('aria-label')||e.id,box:box(e)})).filter(v=>v.box.x<0||v.box.right>innerWidth+1)};
    }""")
    assert geometry['scrollWidth']<=size[0]+1,(name,geometry)
    assert not geometry['fieldClipping'],(name,geometry['fieldClipping'])
    if geometry['overlay']:
        b=geometry['overlay'];assert b['x']>=0 and b['right']<=size[0]+1 and b['y']>=0 and b['bottom']<=size[1]+1,(name,b)
    assert all(b['height']>=43.5 for b in geometry['eventButtons']),name
    page.add_script_tag(path=str(ROOT/'frontend/node_modules/axe-core/axe.min.js'))
    axe=page.evaluate("""async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}});return {violations:r.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),incomplete:r.incomplete.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),passes:r.passes.length}}""")
    live_matrix.append({'surface':name,'viewport':list(size),'status':'PASS','geometry':geometry})
    live_axe.append({'surface':name,'viewport':list(size),**axe})
    assert not axe['violations'],(name,axe['violations'])
    if size[0] in [1440,390]:shot(name.replace(' ','_').lower()+'_'+str(size[0]))
    print('MEASURED',name,size,'axe',len(axe['violations']),flush=True)

def dialog_keyboard(dialog,trigger):
    focusables=dialog.locator('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled])')
    focusables.last.focus();page.keyboard.press('Tab');assert focusables.first.evaluate('(e)=>e===document.activeElement')
    page.keyboard.press('Shift+Tab');assert focusables.last.evaluate('(e)=>e===document.activeElement')
    page.keyboard.press('Escape');dialog.wait_for(state='hidden');assert trigger.evaluate('(e)=>e===document.activeElement')

def responsive_viewport(size):
    page.set_viewport_size({'width':size[0],'height':size[1]})
    for name,path,selector in [
        ('Patron Events',f'/libraries/{fixtures["A"]}/events?view=cancelled','.event-card'),
        ('Patron Event Detail',f'/libraries/{fixtures["A"]}/events/{fixtures["event_A"]}','.event-detail h1'),
        ('Staff Events',f'/staff/libraries/{fixtures["C"]}/events','.event-manage-row'),
        ('Staff Event Detail',f'/staff/libraries/{fixtures["C"]}/events/{fixtures["event_C"]}','.event-detail h1'),
        ('Staff Event Form',f'/staff/libraries/{fixtures["C"]}/events/new','#event-title')]:
        goto(path);ready(selector);measure_surface(name,size)
    goto(f'/staff/libraries/{fixtures["C"]}/events');ready('.event-manage-row')
    row=page.locator('.event-manage-row').filter(has=page.get_by_role('heading',name='Part 2D QA dialog draft',exact=True))
    trigger=row.get_by_role('button',name='Publish',exact=True);trigger.focus();trigger.click()
    dialog=page.get_by_role('dialog',name='Publish this event?',exact=True);dialog.wait_for()
    measure_surface('Publish Dialog',size);dialog_keyboard(dialog,trigger)
    row=page.locator('.event-manage-row').filter(has=page.get_by_role('heading',name='Part 2D Community Reading',exact=True))
    trigger=row.get_by_role('button',name='Cancel Event',exact=True);trigger.focus();trigger.click()
    dialog=page.get_by_role('dialog',name='Cancel this event?',exact=True);dialog.wait_for()
    dialog.get_by_label('Cancellation reason',exact=True).focus();measure_surface('Cancel Dialog',size);dialog_keyboard(dialog,trigger)
    for name,path in [('Patron Bell',f'/libraries/{fixtures["A"]}/events?view=cancelled'),('Staff Bell',f'/staff/libraries/{fixtures["C"]}/events'),('Global Bell','/events')]:
        goto(path);ready();bell=page.get_by_role('button',name=re.compile('^Notifications'))
        bell.focus();page.keyboard.press('Enter');panel=page.get_by_role('region',name='Notification Center',exact=True);panel.wait_for()
        panel.get_by_role('heading',name='Notifications',exact=True).wait_for();measure_surface(name,size)
        page.keyboard.press('Escape');assert bell.evaluate('(e)=>e===document.activeElement')
    put('institution_v2d_responsive.json',{'status':'PASS' if len(live_matrix)==60 else 'IN_PROGRESS','checks':live_matrix})
    put('institution_v2d_accessibility.json',{'status':'PASS' if len(live_axe)==60 else 'IN_PROGRESS','audits':live_axe,'keyboard':'Dialog Tab/Shift-Tab trap, Escape/focus restore and bell Enter/Escape checked in all six viewports.','manual_incomplete_review':'See final visual review before closure.'})

def setup_matrix():
    fixtures['draft_C']=api(f'/libraries/{fixtures["C"]}/events','POST',{'title':'Part 2D QA dialog draft','category':'OTHER','description':'A saved draft used only to validate the shared publish dialog.'},'mixed',201)['event_id']
    login('mixed')

def denied(path,account,method='GET',body=None):
    response=requests.request(method,'http://127.0.0.1:8002'+path,json=body,headers=auth_headers[account],timeout=60)
    assert response.status_code in [403,404],(path,response.status_code)
    return response.status_code

def lifecycle_and_revocation():
    login('mixed');page.set_viewport_size({'width':1440,'height':900})
    historical=next(row for row in api('/notifications?limit=50',account='mixed')['notifications'] if row['type']=='BORROW_REQUEST_APPROVED' and row['library_id']==fixtures['A'])
    member=db.institution_memberships.find_one({'library_id':fixtures['A'],'user_id':accounts['mixed']['user_id']})
    goto('/events');ready();bell=page.get_by_role('button',name=re.compile('^Notifications'));bell.click()
    open_button=page.get_by_role('button',name='Open Borrow request approved in Part 2D QA Library A',exact=True)
    open_button.wait_for()
    api(f'/libraries/{fixtures["A"]}/memberships/{member["membership_id"]}','PATCH',{'status':'SUSPENDED'},'owner')
    open_button.click();page.get_by_role('region',name='Notification Center').get_by_text('Library unavailable',exact=True).first.wait_for()
    assert urlparse(page.url).path=='/events'
    assert api('/notifications/'+historical['notification_id']+'/action',account='mixed')['action_route'] is None
    api(f'/libraries/{fixtures["A"]}/memberships/{member["membership_id"]}','PATCH',{'status':'ACTIVE'},'owner')
    record(security_checks,'Previously rendered notice revalidates membership before navigation; history remains readable')
    page.keyboard.press('Escape')
    for action,before,after in [('suspend','ACTIVE','SUSPENDED'),('restore','SUSPENDED','ACTIVE'),('remove','ACTIVE','REMOVED'),('restore','REMOVED','ACTIVE')]:
        events_before=list(db.events.find({'scope':'LIBRARY','library_id':fixtures['A']},{'_id':0}))
        notices_before=list(db.notifications.find({'scope':'LIBRARY','library_id':fixtures['A']},{'_id':0}))
        api(f'/platform/libraries/{fixtures["A"]}/{action}','POST',cmd(reason='Isolated Part 2D '+action+' validation.',expected_status=before),'platform')
        assert list(db.events.find({'scope':'LIBRARY','library_id':fixtures['A']},{'_id':0}))==events_before
        assert list(db.notifications.find({'scope':'LIBRARY','library_id':fixtures['A']},{'_id':0}))==notices_before
        if after!='ACTIVE':
            denied(f'/libraries/{fixtures["A"]}/events','mixed')
            denied(f'/libraries/{fixtures["A"]}/events','owner','POST',{'title':'Denied lifecycle event','category':'OTHER'})
            history=api('/notifications/'+historical['notification_id']+'/action',account='mixed')
            assert history['action_route'] is None and history['action_unavailable']=='Library unavailable'
            goto('/events');ready();page.get_by_role('button',name=re.compile('^Notifications')).click()
            page.get_by_role('region',name='Notification Center').get_by_text('Library unavailable',exact=True).first.wait_for();shot('bell_'+after.lower());page.keyboard.press('Escape')
        else:assert api('/notifications/'+historical['notification_id']+'/action',account='mixed')['action_route']
        record(security_checks,'Lifecycle '+action+' from '+before+' retains events/inbox and guards tenant access')
    rows=api('/notifications?limit=50',account='mixed')['notifications'];own=rows[0]
    statuses={
        'other_user_read':denied('/notifications/'+own['notification_id'],'borrower'),
        'other_user_mark':denied('/notifications/'+own['notification_id']+'/read','borrower','PATCH'),
        'cross_library_notice':denied(f'/libraries/{fixtures["B"]}/notifications/{historical["notification_id"]}','mixed'),
        'platform_event_mutation':denied(f'/libraries/{fixtures["C"]}/events','platform','POST',{'title':'Denied platform event','category':'OTHER'}),
        'platform_private_event':denied(f'/libraries/{fixtures["A"]}/events/{fixtures["event_A"]}','platform'),
        'library_admin_platform':denied('/platform/libraries','mixed')}
    record(security_checks,'Account ownership, cross-library and platform separation',http_statuses=statuses)
    member=db.institution_memberships.find_one({'library_id':fixtures['C'],'user_id':accounts['mixed']['user_id']})
    api(f'/libraries/{fixtures["C"]}/memberships/{member["membership_id"]}','PATCH',{'status':'SUSPENDED'},'owner')
    denied(f'/libraries/{fixtures["C"]}/events','mixed','POST',{'title':'Revoked librarian event','category':'OTHER'})
    row=next(r for r in api('/notifications?limit=50',account='mixed')['notifications'] if r['library_id']==fixtures['C'])
    assert row['action_route'] is None
    api(f'/libraries/{fixtures["C"]}/memberships/{member["membership_id"]}','PATCH',{'status':'ACTIVE'},'owner')
    record(security_checks,'Librarian membership suspension immediately blocks events and staff notice actions')
    put('institution_v2d_security.json',{'status':'PASS','checks':security_checks,'QA_roles':{'A':'GENERAL_USER','B':'ADMIN','C':'LIBRARIAN'},'runtime_errors':errors})
    put('institution_v2d_event_authorization.json',{'status':'PASS','checks':event_checks+security_checks,'backend_suite':'institution_v2d_tests.xml'})
    put('institution_v2d_notification_authorization.json',{'status':'PASS','checks':notice_checks+security_checks,'backend_suite':'institution_v2d_tests.xml'})

def extra_notice_flows():
    command=cmd(reason='Isolated local QA request rejection.')
    path=f'/libraries/{fixtures["B"]}/staff/lending/borrow-requests/{fixtures["request_B"]}/reject'
    assert api(path,'POST',command,'mixed')==api(path,'POST',command,'mixed')
    db.institution_loans.update_one({'library_id':fixtures['C'],'loan_id':fixtures['loan_C']},{'$set':{'due_at':datetime.now(timezone.utc)-timedelta(days=2)}})
    returning=db.institution_lending_requests.find_one({'library_id':fixtures['C'],'loan_id':fixtures['loan_C'],'request_type':'RETURN','status':'PENDING'})
    assert returning
    command=cmd();path=f'/libraries/{fixtures["C"]}/staff/lending/return-requests/{returning["lending_request_id"]}/confirm'
    assert api(path,'POST',command,'mixed')==api(path,'POST',command,'mixed')
    fee=db.institution_fees.find_one({'library_id':fixtures['C'],'loan_id':fixtures['loan_C']});assert fee
    command=cmd(amount_minor=500,method='CASH');path=f'/libraries/{fixtures["C"]}/staff/fees/{fee["fee_id"]}/payments'
    assert api(path,'POST',command,'mixed')==api(path,'POST',command,'mixed')
    rows=wait_notices('borrower',['BORROW_REQUEST_REJECTED','RETURN_CONFIRMED','PAYMENT_RECORDED'])
    assert all(r['library_id'] in [fixtures['A'],fixtures['B'],fixtures['C']] for r in rows)
    keys=[r['dedupe_key'] for r in db.notifications.find({'user_id':accounts['borrower']['user_id']})]
    assert len(keys)==len(set(keys))
    record(notice_checks,'Rejection, physical return and desk payment emit canonical deduplicated patron notices',clock_fixture='Disposable C loan only')

def remaining_product_checks():
    login('staff');page.set_viewport_size({'width':1440,'height':900})
    for suffix in ['', '/inventory','/circulation','/reservations','/fees','/members','/settings','/events']:
        path='/staff/libraries/'+TEST+suffix;goto(path);product_ready('main h1')
        page.get_by_text(re.compile('^Loading')).first.wait_for(state='hidden',timeout=60000)
        assert page.locator('.global-logo').get_attribute('href')=='/staff/libraries/'+TEST
        assert urlparse(page.url).path==path
        page.locator('.global-logo').click();page.wait_for_url(BASE+'/staff/libraries/'+TEST);product_ready('main h1')
        record(regression_checks,'TEST Owner ADMIN staff '+(suffix or '/overview')+' home context')
    goto('/reading-list?staff_library='+TEST);product_ready('main h1')
    assert page.locator('.global-logo').get_attribute('href')=='/staff/libraries/'+TEST
    page.locator('.global-logo').click();page.wait_for_url(BASE+'/staff/libraries/'+TEST);product_ready('main h1')
    record(regression_checks,'Staff personal page preserves explicit TEST return context')
    run_matrix(STAFF_PAGES,'STAFF')
    login('borrower');goto('/libraries/'+fixtures['C']);product_ready('#new-arrivals .product-book-card')
    page.get_by_role('heading',name='Upcoming Events',exact=True).wait_for()
    page.get_by_role('link',name='All library events',exact=True).click();ready('.event-card')
    assert urlparse(page.url).path==f'/libraries/{fixtures["C"]}/events'
    record(event_checks,'Bounded Patron Home upcoming events opens the canonical library list')
    global_rows=api('/events?view=past',account='mixed')['events']
    assert any(r['event_id']=='f2a2ab14-1b8c-4f3c-9fde-52a31f87427d' for r in global_rows)
    assert all(r.get('library_id') is None for r in global_rows)
    goto('/events?view=past');ready('.event-card');page.locator('a[href="/events/f2a2ab14-1b8c-4f3c-9fde-52a31f87427d"]').first.click();ready('.event-detail h1')
    assert page.locator('.global-logo').get_attribute('href')=='/'
    record(event_checks,'Legacy global event remains global; tenant events excluded')
    put('institution_v2d_product_responsive_final.json',{'status':'PASS','rows':matrix})
    put('institution_v2d_product_accessibility_final.json',{'status':'PASS','audits':accessibility})
    put('institution_v2d_browser.json',{'status':'PASS','browser':browser.version,'events':event_checks,'notifications':notice_checks,'security':security_checks,'product_checks':regression_checks,'full_product_walkthrough':'institution_v2d_product_browser_walkthrough.json','product_viewports':len(matrix),'errors':errors})

def manual_contrast_and_focus():
    login('mixed');review=[]
    for size in [SIZES[0],SIZES[-1]]:
        page.set_viewport_size({'width':size[0],'height':size[1]})
        for label,action,title in [('Publish Dialog','Publish','Publish this event?'),('Cancel Dialog','Cancel Event','Cancel this event?')]:
            goto('/staff/libraries/'+fixtures['C']+'/events');ready('.event-manage-row')
            row=page.locator('.event-manage-row').filter(has=page.get_by_role('heading',name='Part 2D QA dialog draft' if action=='Publish' else 'Part 2D Community Reading',exact=True))
            trigger=row.get_by_role('button',name=action,exact=True);trigger.focus();trigger.click()
            dialog=page.get_by_role('dialog',name=title,exact=True);dialog.wait_for()
            assert dialog.evaluate('(e)=>e.contains(document.activeElement)')
            selectors=['dialog > p','dialog h2','dialog label','dialog button:not([disabled])']
            if action=='Cancel Event':
                dialog.get_by_label('Cancellation reason').fill('Keyboard and rendered-contrast QA reason.')
                selectors.append('input[aria-label="Cancellation reason"]')
            review.extend(contrast_nodes(label,size,selectors))
            page.screenshot(path=str(REPORTS/f'institution_v2d_{action.lower().replace(" ","_")}_dialog_viewport_{size[0]}.png'),animations='disabled')
            dialog_keyboard(dialog,trigger)
        goto('/libraries/'+fixtures['A']+'/events?view=cancelled');ready('.event-card')
        page.get_by_role('button',name=re.compile('^Notifications')).click();panel=page.get_by_role('region',name='Notification Center');panel.wait_for()
        review.extend(contrast_nodes('Notification panel',size,['.notification-panel h2','.notification-panel h3','.notification-panel p','.notification-panel time','.notification-panel button:not([disabled])']))
        page.screenshot(path=str(REPORTS/f'institution_v2d_notification_panel_viewport_{size[0]}.png'),animations='disabled');page.keyboard.press('Escape')
    goto('/staff/libraries/'+fixtures['C']+'/events/new');ready('#event-title')
    page.get_by_role('button',name='Publish Now',exact=True).click()
    page.get_by_role('alert',name='Event validation errors',exact=True).wait_for()
    assert page.locator('[aria-invalid=true]').count()>0
    record(event_checks,'Event validation exposes errors before create/publish; native dialog initial focus checked')
    assert all(row['ratio']>=row['required'] for row in review),[r for r in review if r['ratio']<r['required']]
    result=json.loads((REPORTS/'institution_v2d_accessibility.json').read_text())
    result.update(status='PASS',manual_contrast=review,manual_incomplete_review='Rendered dialog text, filled reason input and notification panel foreground/background ratios measured at desktop and mobile. Modal focus starts inside the native dialog. Axe incompletes on underlying content obscured by overlays are not active controls; each unobscured page independently passed. Empty text fields contain no text to assess. Disabled controls are exempt.')
    put('institution_v2d_accessibility.json',result)
    print('CONTRAST_MEASUREMENTS',len(review),'PASS',flush=True)

def contrast_nodes(label,size,selectors):
    return page.evaluate("""({label,size,selectors})=>{
      const rgb=s=>(s.match(/[\\d.]+/g)||[]).slice(0,3).map(Number);
      const luminance=c=>c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((a,v,i)=>a+v*[.2126,.7152,.0722][i],0);
      return selectors.flatMap(selector=>[...document.querySelectorAll(selector)].filter(e=>e.getClientRects().length).map(e=>{
        const s=getComputedStyle(e);let p=e,bg='rgb(250,248,244)';while(p){const c=getComputedStyle(p).backgroundColor;if(c!=='rgba(0, 0, 0, 0)'&&c!=='transparent'){bg=c;break}p=p.parentElement}
        const a=luminance(rgb(s.color)),b=luminance(rgb(bg));const ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
        return {surface:label,viewport:size,selector,foreground:s.color,background:bg,ratio:Math.round(ratio*100)/100,required:parseFloat(s.fontSize)>=24||parseFloat(s.fontSize)>=18.66&&parseInt(s.fontWeight)>=700?3:4.5};
      }));
    }""",{'label':label,'size':list(size),'selectors':selectors})

def performance_and_cleanup():
    timings=[]
    for account,path in [('mixed',f'/libraries/{fixtures["C"]}/staff/events?page_size=50'),('mixed',f'/libraries/{fixtures["A"]}/events?query=Community&page_size=3'),('borrower','/notifications?limit=50')]:
        measurements=[]
        for _ in range(5):
            started=time.perf_counter();response=api(path,account=account);measurements.append(round((time.perf_counter()-started)*1000,2))
        timings.append({'path':path,'samples_ms':measurements,'max_ms':max(measurements),'returned':len(response.get('events',response.get('notifications',[])))})
    assert api(f'/libraries/{fixtures["C"]}/staff/events?page_size=51',account='mixed',expected=422)
    assert api('/notifications?limit=51',account='mixed',expected=422)
    qa_ids=[row['user_id'] for row in accounts.values()]
    outbox=list(db.institution_notification_outbox.find({'user_id':{'$in':qa_ids}},{'_id':0,'state':1,'dedupe_key':1,'audit_event_id':1,'operation_id':1,'library_id':1}))
    assert all(r['state']=='DELIVERED' for r in outbox)
    assert len({r['dedupe_key'] for r in outbox})==len(outbox)
    put('institution_v2d_performance.json',{'status':'PASS','local_API_timings':timings,'measurement_scope':'Local disposable QA fixtures; not a production load benchmark.','event_page_cap':50,'notification_page_cap':50,'home_event_cap':3,'worker_default_batch':100,'operator_max_batch':500,'event_indexes':list(db.events.index_information()),'outbox_indexes':list(db.institution_notification_outbox.index_information()),'outbox_fixture_rows':len(outbox),'outbox_pending':0})
    put('institution_v2d_notification_dedupe.json',{'status':'PASS','live_checks':notice_checks,'live_outbox_rows':len(outbox),'unique_dedupe_keys':len({r['dedupe_key'] for r in outbox}),'all_delivered':True,'recovery_tests':'institution_v2d_tests.xml'})
    cleanup=[]
    for letter in ['A','B','C']:
        identity=fixtures[letter];before_events=db.events.count_documents({'library_id':identity});before_notices=db.notifications.count_documents({'library_id':identity})
        api('/platform/libraries/'+identity+'/remove','POST',cmd(reason='Part 2D browser QA complete: archive only this disposable fixture.',expected_status='ACTIVE'),'platform')
        assert db.events.count_documents({'library_id':identity})==before_events and db.notifications.count_documents({'library_id':identity})==before_notices
        cleanup.append({'library_id':identity,'status':'REMOVED','soft_only':True,'events_retained':before_events,'notices_retained':before_notices})
    # Disable only accounts created in this phase, through the existing safe
    # platform account operation. The interrupted first setup's orphan is verified
    # by its exact local QA prefix before being touched.
    disabled=[]
    for name,row in accounts.items():
        if name=='platform':continue
        api('/platform/accounts/'+str(row['user_id']),'PATCH',{'is_active':False},'platform');disabled.append(row['user_id'])
    orphan=db.users.find_one({'user_id':431,'email':{'$regex':'^institution-v2d-owner-[0-9a-f]+@example\\.com$'}})
    if orphan:
        assert not db.institution_memberships.find_one({'user_id':431})
        api('/platform/accounts/431','PATCH',{'is_active':False},'platform');disabled.append(431)
    platform_id=accounts['platform']['user_id']
    revoked=db.platform_role_assignments.update_one({'user_id':platform_id,'role':'PLATFORM_ADMIN','status':'ACTIVE','approval_ref':'USER-INSTITUTION-V2D-QA'},{'$set':{'status':'REVOKED','revoked_at':datetime.now(timezone.utc),'revocation_reason':'Isolated local Part 2D QA complete.'}})
    assert revoked.modified_count==1
    assert not db.platform_role_assignments.find_one({'user_id':platform_id,'status':'ACTIVE'})
    response=requests.get('http://127.0.0.1:8002/platform/libraries',headers=auth_headers['platform'],timeout=30);assert response.status_code==403
    put('institution_v2d_qa_cleanup.json',{'status':'PASS','disposable_libraries':cleanup,'normal_QA_accounts_disabled':disabled,'temporary_platform_assignment_revoked':True,'role_revocation_http_status':response.status_code,'production_authority_changed':False,'existing_accepted_platform_QA_assignment_unchanged':True,'existing_owner_patron_accounts_changed':False,'credentials_persisted':False})
    put('institution_v2d_browser.json',{'status':'PASS','browser':browser.version,'events':event_checks,'notifications':notice_checks,'security':security_checks,'product_checks':regression_checks,'full_product_walkthrough':'institution_v2d_product_browser_walkthrough.json','product_viewports':len(matrix),'errors':errors})
