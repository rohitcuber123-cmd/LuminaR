"""Local QA provisioning and real Chromium review. Secrets live only in memory.

Run from the project with stdin open. The test mailbox sink exists only in this
process and still verifies the normally generated, hashed, one-use OTP.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
exec(Path(__file__).with_name('full_product_browser_session.py').read_text(encoding='utf8').split("if __name__ == '__main__':")[0],globals())
import secrets
from backend.database.mongodb import db
from backend.services import auth_service
from scripts import migrate_management_authority as migration

assert db.name=='luminar_library' and db.client.address[0] in {'localhost','127.0.0.1','::1'},'Local review database required.'
secret=secrets.token_urlsafe(32)
qa_email='platform-completion-qa@example.com'
if db.users.find_one({'email':qa_email}):qa_email='platform-completion-qa-'+secrets.token_hex(4)+'@example.com'
mailbox={};original_mail=auth_service.send_otp_email
def local_test_mail(email,name,otp):mailbox[email]=otp;return True
try:
    auth_service.send_otp_email=local_test_mail
    qa=auth_service.register_user('LuminaR Platform QA',qa_email,secret)
    assert qa and auth_service.verify_email_otp(qa_email,mailbox.pop(qa_email))
finally:auth_service.send_otp_email=original_mail
proposal=migration.plan(db,{'platform_assignments':[{'user_id':qa['user_id'],'role':'PLATFORM_ADMIN',
    'approved':True,'approved_by':'local-development-review','approval_ref':'USER-PLATFORM-COMPLETION-V1',
    'reason':'Dedicated local-development browser QA explicitly authorized by the user.'}]})
migration.apply(db,proposal)
assert db.institution_memberships.count_documents({'user_id':qa['user_id'],'library_id':TEST})==0
base_credentials=credentials
def credentials(account):
    if account=='platform':return qa_email,secret
    return base_credentials(account)
def shot(name):
    target=REPORTS/f'platform_completion_{name}.png';page.screenshot(path=str(target),full_page=True,animations='disabled');return str(target)
def put(name,value):
    # Preserve all reports from previously accepted product closure.
    if name.startswith('full_product_'):name='platform_completion_'+name
    (REPORTS/name).write_text(json.dumps(value,indent=2,default=str),encoding='utf8')
sys.stdout.reconfigure(encoding='utf8')
with sync_playwright() as playwright:
    browser=playwright.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':1440,'height':900})
    page=context.new_page();network=[];errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('response',lambda response:network.append({'path':urlparse(response.url).path,'status':response.status}) if '/api/' in response.url else None)
    print(json.dumps({'browser':browser.version,'qa_account_created':True,'email':qa_email,'user_id':qa['user_id'],'platform_assignment':'EXPLICIT','TEST_membership':False}),flush=True)
    for line in sys.stdin:
        try:
            command=json.loads(line)
            if command.get('stop'):break
            exec(command['code'],globals())
            print(json.dumps({'state':state(),'network':network[-8:],'errors':errors[-5:]},ensure_ascii=False),flush=True)
        except Exception as error:
            print(json.dumps({'error':type(error).__name__+': '+str(error).split('Call log:')[0],'state':state() if not page.is_closed() else None},ensure_ascii=False),flush=True)
    browser.close()
