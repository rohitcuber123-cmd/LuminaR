"""Loaded into platform_completion_browser.py; no credentials or auth snapshots."""
from uuid import uuid4
from urllib.parse import parse_qs
import time
from backend.services.institution_repository import collection
SIZES=[(1440,900),(1366,768),(1024,768),(768,1024),(390,844),(375,812)]
checks=[];lifecycle_checks=[];boundary_checks=[];platform_matrix=[];platform_axe=[]
def ready_platform(selector='main h1'):
    page.locator(selector).first.wait_for(timeout=60000)
    page.get_by_text(re.compile('^Loading')).first.wait_for(state='hidden',timeout=60000)
    page.evaluate('document.fonts.ready')
def token():return page.evaluate("localStorage.getItem('luminar_token')")
def api(method,path,body=None,access=None):
    response=context.request.fetch(BASE+'/api'+path,method=method,data=body,headers={'Authorization':'Bearer '+(access or token())})
    return response.status,response.json() if response.headers.get('content-type','').startswith('application/json') else None
def tenant_snapshot(library_id):
    return {name:list(db[name].find({'library_id':library_id}).sort('_id')) for name in db.list_collection_names() if name.startswith('institution_') and name not in ['institution_libraries','institution_locks']}
def create_disposables():
    global disposable,qa_libraries,patron_access,retained
    qa_libraries=[]
    for n in range(6):
        status,row=api('POST','/libraries/register',{'name':'Platform QA '+('Lifecycle' if n==0 else 'Private' if n==1 else 'Paging '+str(n)),
            'slug':'platform-qa-'+uuid4().hex[:12],'library_type':'PRIVATE_INSTITUTION' if n==1 else 'PUBLIC_LIBRARY','access_mode':'PRIVATE_CODE' if n==1 else 'PUBLIC',
            **({'access_code':secrets.token_urlsafe(16)} if n==1 else {})})
        assert status==201,(status,row)
        qa_libraries.append(row['library']['library_id'])
    disposable=qa_libraries[0]
    status,book=api('POST',f'/libraries/{disposable}/inventory/books',{'idempotency_key':str(uuid4()),'title':'Platform lifecycle retained QA record','authors':['QA Author'],'subjects':['QA'],'copies':1})
    assert status==201,(status,book)
    # Normal login and lending on the disposable library; TEST is untouched.
    email,password=credentials('patron')
    response=context.request.post(BASE+'/api/auth/login',data={'email':email,'password':password})
    assert response.status==200
    patron_access=response.json()['access_token']
    assert api('POST',f'/libraries/{disposable}/join',{},patron_access)[0]==200
    status,request=api('POST',f'/libraries/{disposable}/lending/borrow-requests',{'idempotency_key':str(uuid4()),'library_book_id':book['library_book_id']},patron_access)
    assert status==201,(status,request)
    status,loan=api('POST',f'/libraries/{disposable}/staff/lending/borrow-requests/{request["lending_request_id"]}/approve',{'idempotency_key':str(uuid4())})
    assert status==200,(status,loan)
    retained=tenant_snapshot(disposable)
    print('DISPOSABLE_CREATED',disposable,'retained_book_holdings_membership_request_loan',flush=True)
def directory_flow():
    goto('/platform');ready_platform();assert page.locator('.global-logo').get_attribute('href')=='/platform';checks.append({'flow':'Overview','status':'PASS'});shot('platform_overview')
    page.get_by_role('link',name='Manage Libraries',exact=True).click();ready_platform('tbody tr');checks.append({'flow':'Libraries renders','status':'PASS'});shot('platform_libraries')
    test_library=collection('libraries').find_one({'library_id':TEST})
    owner=db.users.find_one({'user_id':test_library['owner_user_id']})
    for query,label in [('TEST','Name'),(TEST,'UUID'),(test_library['slug'],'Slug'),(owner['email'],'Owner email')]:
        page.get_by_role('searchbox').fill(query)
        with page.expect_response(lambda r:'/api/platform/libraries?' in r.url and parse_qs(urlparse(r.url).query).get('q')==[query],timeout=60000):
            page.get_by_role('button',name='Search',exact=True).click()
        page.get_by_role('link',name='View TEST',exact=True).wait_for(timeout=60000)
        assert page.locator('tbody tr').count()==1
        checks.append({'flow':'Search '+label,'status':'PASS'})
    goto('/platform/libraries?status=ACTIVE');ready_platform('tbody tr');assert page.get_by_role('link',name='View TEST',exact=True).count()==1;checks.append({'flow':'ACTIVE filter and TEST active','status':'PASS'})
    for kind in ['PUBLIC_LIBRARY','PRIVATE_INSTITUTION']:
        with page.expect_response(lambda r:'/api/platform/libraries?' in r.url and parse_qs(urlparse(r.url).query).get('library_type')==[kind],timeout=60000):
            page.get_by_role('combobox',name='Library type',exact=True).select_option(kind)
        ready_platform('tbody tr')
        text=page.locator('tbody').inner_text();assert ('Private institution' if kind=='PRIVATE_INSTITUTION' else 'Public library') in text
        checks.append({'flow':'Type '+kind,'status':'PASS'})
    goto('/platform/libraries?limit=5');ready_platform('tbody tr');first=page.locator('tbody tr').all_text_contents();assert len(first)==5
    with page.expect_response(lambda r:'/api/platform/libraries?' in r.url and parse_qs(urlparse(r.url).query).get('offset')==['5'],timeout=60000):page.get_by_role('button',name='Next',exact=True).click()
    ready_platform('tbody tr');second=page.locator('tbody tr').all_text_contents();assert second and not set(first)&set(second)
    checks.append({'flow':'Server pagination distinct slices','first_count':len(first),'second_count':len(second),'status':'PASS'})
    goto('/platform/libraries/'+TEST);ready_platform('main h1');page.get_by_role('heading',name='Library identity',exact=True).wait_for(timeout=60000)
    assert '150' in page.locator('main').inner_text();assert db.institution_memberships.count_documents({'library_id':TEST,'user_id':qa['user_id']})==0
    for name in ['Add Book','Edit Inventory','Shelf','Stock','Confirm Return','Invite Staff','Fee waiver','Access-code rotation']:
        assert page.get_by_role('button',name=name,exact=True).count()==0
    checks.append({'flow':'TEST detail safe aggregates, no tenant mutation controls','status':'PASS'});shot('platform_test_detail')
    page.get_by_role('button',name=re.compile('Open account menu')).click();menu=page.get_by_role('group',name='Platform',exact=True);assert menu.get_by_role('menuitem',name='Platform Administration',exact=True).count()==1
    assert page.get_by_role('group',name='Staff workspaces',exact=True).get_by_role('menuitem',name='Platform Administration',exact=True).count()==0
    page.keyboard.press('Escape');checks.append({'flow':'Avatar separates Platform','status':'PASS'})
    put('platform_libraries_browser.json',{'status':'PASS','qa_email':qa_email,'explicit_assignment':True,'checks':checks})
def lifecycle_flow():
    for action,before,after,label in [('suspend','ACTIVE','SUSPENDED','Suspend Library'),('restore','SUSPENDED','ACTIVE','Restore Library'),('remove','ACTIVE','REMOVED','Remove Library'),('restore','REMOVED','ACTIVE','Restore Library')]:
        goto('/platform/libraries/'+disposable);ready_platform();page.get_by_role('button',name=label,exact=True).wait_for(timeout=60000);page.get_by_role('button',name=label,exact=True).click()
        dialog=page.get_by_role('dialog',name=label,exact=True);dialog.wait_for();confirm=dialog.get_by_role('button',name=label,exact=True);assert confirm.is_disabled()
        dialog.get_by_label('Reason (required)',exact=True).fill('Local Platform Completion QA: '+action+' from '+before)
        shot('dialog_'+action+'_'+before.lower())
        with page.expect_response(lambda r:f'/platform/libraries/{disposable}/{action}' in r.url and r.request.method=='POST',timeout=60000) as response:confirm.click()
        assert response.value.status==200,response.value.json();dialog.wait_for(state='hidden');page.get_by_text('Loading library…',exact=True).wait_for(state='hidden',timeout=60000)
        assert collection('libraries').find_one({'library_id':disposable})['status']==after
        assert tenant_snapshot(disposable)==retained
        event=db.platform_audit.find_one({'event_id':response.value.json()['event_id']});assert event['state']=='COMMITTED' and event['reason'] and event['previous_state']==before and event['new_state']==after
        if after!='ACTIVE':
            assert api('GET',f'/libraries/{disposable}/staff/loans')[0]==404
            assert api('GET',f'/libraries/{disposable}/catalogue/books',access=patron_access)[0]==404
            assert api('POST',f'/libraries/{disposable}/join',{},patron_access)[0]==404
            goto('/platform/libraries?status='+after);ready_platform('tbody tr');assert page.get_by_role('link',name='View Platform QA Lifecycle',exact=True).count()==1
            assert disposable not in str(api('GET','/libraries',access=patron_access)[1])
        else:
            assert api('GET',f'/libraries/{disposable}/staff/loans')[0]==200
            assert api('GET',f'/libraries/{disposable}/catalogue/books',access=patron_access)[0]==200
        lifecycle_checks.append({'action':action,'previous_state':before,'new_state':after,'reason_required':True,'data_retained':True,'audit_event':event['event'],'event_id':event['event_id'],'status':'PASS'})
        print('LIFECYCLE',action,before,after,'PASS',flush=True)
    put('platform_library_lifecycle_browser.json',{'status':'PASS','library_id':disposable,'TEST_used':False,'retained_collections':{k:len(v) for k,v in retained.items()},'checks':lifecycle_checks})
def boundary_flow():
    goto('/staff/libraries/'+TEST);page.get_by_text('Unable to open this library',exact=True).wait_for(timeout=60000)
    boundary_checks.append({'flow':'Direct TEST Staff URL without membership','status':'PASS','TEST_membership':False});shot('platform_test_staff_denied')
    inventory=collection('library_books').find_one({'library_id':TEST,'status':'ACTIVE'})
    for label,method,path,body in [
        ('Edit inventory','PATCH',f'/inventory/books/{inventory["library_book_id"]}',{'title':'Forbidden platform edit'}),
        ('Approve request','POST',f'/staff/lending/borrow-requests/{uuid4()}/approve',{'idempotency_key':str(uuid4())}),
        ('Confirm return','POST',f'/staff/loans/{uuid4()}/receive',{'idempotency_key':str(uuid4())}),
        ('Manage staff','POST','/invitations',{'email':'forbidden@example.com','role':'LIBRARIAN'}),
        ('Waive fee','POST',f'/staff/fees/{uuid4()}/waive',{'idempotency_key':str(uuid4()),'reason':'Forbidden platform operation'}),
        ('Rotate access code','PUT','/access-code',{'access_code':secrets.token_urlsafe(16)}),
        ('Internal settings','PATCH','',{'name':'Forbidden'}),
    ]:
        status,_=api(method,'/libraries/'+TEST+path,body);assert status in [403,404],(label,status)
        boundary_checks.append({'flow':label,'http_status':status,'status':'PASS'})
    put('platform_boundary_browser.json',{'status':'PASS','checks':boundary_checks})
def axe_platform():
    page.add_script_tag(path=str(ROOT/'frontend/node_modules/axe-core/axe.min.js'))
    return page.evaluate("""async()=>{const r=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});return {violations:r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),incomplete:r.incomplete.map(v=>({id:v.id,count:v.nodes.length}))}}""")
def platform_geometry():
    return page.evaluate("""()=>{const d=document.querySelector('dialog[open]'),r=d?.getBoundingClientRect();return {width:innerWidth,height:innerHeight,document_width:document.documentElement.scrollWidth,dialog:r?{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom}:null,tables:[...document.querySelectorAll('.ui-table-wrap')].map(e=>({client:e.clientWidth,scroll:e.scrollWidth,overflow:getComputedStyle(e).overflowX}))}}""")
def platform_responsive():
    for name,route in [('Overview','/platform'),('Libraries','/platform/libraries'),('Detail','/platform/libraries/'+TEST)]:
        goto(route);ready_platform('tbody tr' if name=='Libraries' else 'main h1')
        if name=='Detail':page.get_by_role('heading',name='Library identity',exact=True).wait_for(timeout=60000)
        for w,h in SIZES:
            page.set_viewport_size({'width':w,'height':h});page.evaluate('document.fonts.ready')
            geometry=platform_geometry();audit=axe_platform();assert geometry['document_width']<=w,(name,w,geometry)
            platform_matrix.append({'page':name,'viewport':f'{w}x{h}','geometry':geometry,'status':'PASS'})
            platform_axe.append({'page':name,'viewport':f'{w}x{h}',**audit})
            shot('platform_'+name.lower()+f'_{w}x{h}')
            print('PLATFORM_MATRIX',name,w,'axe',len(audit['violations']),flush=True)
    for action,status,label in [('suspend','ACTIVE','Suspend Library'),('remove','ACTIVE','Remove Library'),('restore','SUSPENDED','Restore Library')]:
        if status=='SUSPENDED':assert api('POST',f'/platform/libraries/{disposable}/suspend',{'idempotency_key':str(uuid4()),'expected_status':'ACTIVE','reason':'Responsive restore dialog QA'})[0]==200
        goto('/platform/libraries/'+disposable);ready_platform();page.get_by_role('button',name=label,exact=True).wait_for(timeout=60000)
        trigger=page.get_by_role('button',name=label,exact=True);trigger.click();dialog=page.get_by_role('dialog',name=label,exact=True);dialog.wait_for()
        for w,h in SIZES:
            page.set_viewport_size({'width':w,'height':h});geometry=platform_geometry();audit=axe_platform();box=geometry['dialog']
            assert geometry['document_width']<=w and box['x']>=0 and box['y']>=0 and box['right']<=w and box['bottom']<=h,(label,w,box)
            for _ in range(8):page.keyboard.press('Tab');assert page.evaluate("document.querySelector('dialog[open]').contains(document.activeElement)")
            platform_matrix.append({'page':label,'viewport':f'{w}x{h}','geometry':geometry,'focus_trap':True,'status':'PASS'})
            platform_axe.append({'page':label,'viewport':f'{w}x{h}',**audit});shot('platform_'+action+f'_dialog_{w}x{h}')
            print('PLATFORM_MATRIX',label,w,'axe',len(audit['violations']),flush=True)
        page.keyboard.press('Escape');dialog.wait_for(state='hidden');assert trigger.evaluate('e=>e===document.activeElement')
        if status=='SUSPENDED':assert api('POST',f'/platform/libraries/{disposable}/restore',{'idempotency_key':str(uuid4()),'expected_status':'SUSPENDED','reason':'Finish responsive restore dialog QA'})[0]==200
    page.set_viewport_size({'width':1440,'height':900})
    put('platform_responsive.json',{'status':'PASS','matrix':platform_matrix,'measured_checks':len(platform_matrix)})
    violations=sum(len(a['violations']) for a in platform_axe)
    put('platform_accessibility.json',{'status':'PASS' if violations==0 else 'FAIL','audits':platform_axe,'axe_violations':violations,'focus_trap_escape_restore':True})
    assert violations==0,platform_axe
