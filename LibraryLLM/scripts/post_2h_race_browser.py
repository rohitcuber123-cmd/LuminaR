"""Delayed tenant response across real UI logout/login in one Chromium document."""
import sys,json,secrets,requests
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from playwright.sync_api import sync_playwright,expect
from scripts.full_product_browser_session import credentials
from backend.database.mongodb import db
from backend.services import auth_service
from scripts import migrate_management_authority as migration
BASE='http://127.0.0.1:5173';CORE='http://127.0.0.1:8002';TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
assert db.name=='luminar_library' and db.client.address[0] in ('localhost','127.0.0.1','::1')
email='post2h-race-'+uuid4().hex[:12]+'@example.com';password=secrets.token_urlsafe(30);mail={};original=auth_service.send_otp_email
try:
    auth_service.send_otp_email=lambda address,name,otp:mail.update({address:otp}) or True
    user=auth_service.register_user('Post Part 2H delayed response QA',email,password)
    assert auth_service.verify_email_otp(email,mail.pop(email))
finally:auth_service.send_otp_email=original
migration.apply(db,migration.plan(db,{'platform_assignments':[{'user_id':user['user_id'],'role':'PLATFORM_ADMIN','approved':True,'approved_by':'local-development-review','approval_ref':'USER-POST-2H-LOCAL-QA','reason':'Temporary delayed-response browser validation.'}]}))
report={'status':'IN_PROGRESS','method':'Actual Chromium UI auth transitions; controlled delay of an authorized tenant-context response.'}
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1440,'height':900})
        page.goto(BASE+'/login');staff_email,staff_password=credentials('staff')
        page.locator('input[type=email]').fill(staff_email);page.locator('input[type=password]').fill(staff_password);page.get_by_role('button',name='Sign In',exact=True).click();page.wait_for_url(lambda u:'/login' not in str(u))
        token=page.evaluate("localStorage.getItem('luminar_token')")
        response=requests.get(CORE+f'/libraries/{TEST}/context',headers={'Authorization':'Bearer '+token},timeout=60);response.raise_for_status();old_context=response.json()
        held=[]
        def hold(route):
            if not held:held.append(route)
            else:route.continue_()
        page.route('**/api/libraries/'+TEST+'/context',hold)
        page.goto(BASE+f'/staff/libraries/{TEST}/inventory')
        for _ in range(100):
            if held:break
            page.wait_for_timeout(50)
        assert held,'Tenant context request must actually be pending.'
        page.get_by_role('button',name='Open account menu',exact=False).click();page.get_by_role('menuitem',name='Sign Out',exact=False).click();page.wait_for_url('**/login')
        # Stay in the same document: no navigation reload that could merely cancel the delayed request.
        page.locator('input[type=email]').fill(email);page.locator('input[type=password]').fill(password);page.get_by_role('button',name='Sign In',exact=True).click();page.wait_for_url('**/platform',timeout=60000)
        expect(page.locator('.global-header').get_by_role('link',name='Catalog',exact=True)).to_have_attribute('href','/catalog?workspace=platform')
        page.locator('.global-header').get_by_role('link',name='Catalog',exact=True).click();page.get_by_text('5,000,000',exact=False).first.wait_for(timeout=60000)
        held[0].fulfill(status=200,json=old_context)
        expect(page.locator('.global-header').get_by_role('link',name='LuminaR home')).to_have_attribute('href','/platform')
        page.get_by_text('5,000,000',exact=False).first.wait_for();assert page.locator('.staff-workspace,.patron-context-bar').count()==0
        assert page.get_by_text('Library not found',exact=False).count()==0
        assert page.evaluate("JSON.parse(localStorage.getItem('luminar_workspace_contexts')).staffLibraryId")==None
        report.update({'status':'PASS','old_response_delivered':True,'same_browser_document':True,'route':'/catalog?workspace=platform','tenant_projection_restored':False,'spurious_library_error':False,'qa_account_disabled':True,'qa_assignment_revoked':True})
        browser.close();print('PASS delayed tenant HTTP response ignored after real account switch')
except Exception:
    report['status']='FAIL';raise
finally:
    db.platform_role_assignments.update_many({'user_id':user['user_id'],'approval_ref':'USER-POST-2H-LOCAL-QA'},{'$set':{'status':'REVOKED'}})
    db.users.update_one({'user_id':user['user_id']},{'$set':{'is_active':False}})
    (ROOT/'reports/post_2h_account_race_browser.json').write_text(json.dumps(report,indent=2),encoding='utf8')
