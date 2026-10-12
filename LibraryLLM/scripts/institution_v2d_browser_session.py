"""Disposable local QA, normal registration/login/membership APIs, real Chromium.

Passwords, OTPs, JWTs and invitation/access codes remain runtime-only. No auth
state is saved. Existing Patron/Owner accounts and TEST data are not promoted.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
exec(Path(__file__).with_name('full_product_browser_session.py').read_text(encoding='utf8').split("if __name__ == '__main__':")[0],globals())
import secrets
import requests
from datetime import datetime,timedelta,timezone
from uuid import uuid4
from backend.database.mongodb import db
from backend.services import auth_service
from scripts import migrate_management_authority as migration

assert db.name=='luminar_library' and db.client.address[0] in ['localhost','127.0.0.1','::1']
accounts={};auth_headers={};fixtures={};suffix=secrets.token_hex(5)
mailbox={};send_mail=auth_service.send_otp_email
def test_mail(email,name,otp):mailbox[email]=otp;return True
try:
    auth_service.send_otp_email=test_mail
    for purpose in ['owner','mixed','borrower','platform']:
        email=f'institution-v2d-{purpose}-{suffix}@example.com';password=secrets.token_urlsafe(32)
        user=auth_service.register_user('Part 2D QA '+purpose.title(),email,password)
        assert user and auth_service.verify_email_otp(email,mailbox.pop(email))
        accounts[purpose]={'email':email,'password':password,'user_id':user['user_id']}
        response=requests.post('http://127.0.0.1:8002/auth/login',json={'email':email,'password':password},timeout=30)
        assert response.status_code==200,'QA login failed'
        auth_headers[purpose]={'Authorization':'Bearer '+response.json()['access_token']}
finally:auth_service.send_otp_email=send_mail


def api(path,method='GET',body=None,account='owner',expected=200):
    response=requests.request(method,'http://127.0.0.1:8002'+path,json=body,headers=auth_headers[account],timeout=60)
    assert response.status_code==expected, f'{method} {path}: expected {expected}, got {response.status_code}'
    return response.json()


def cmd(**values):return {'idempotency_key':str(uuid4()),**values}


private_code=secrets.token_urlsafe(20)
for letter,purpose,private in [('A','owner',True),('B','mixed',False),('C','owner',False)]:
    payload={'name':'Part 2D QA Library '+letter,'slug':f'part2d-{letter.lower()}-{suffix}',
        'library_type':'PRIVATE_INSTITUTION' if private else 'PUBLIC_LIBRARY','access_mode':'PRIVATE_CODE' if private else 'PUBLIC'}
    if private:payload['access_code']=private_code
    fixtures[letter]=api('/libraries/register','POST',payload,purpose,201)['library']['library_id']
api(f'/libraries/{fixtures["A"]}/join','POST',{'access_code':private_code},'mixed')
for letter in ['B','C']:api(f'/libraries/{fixtures[letter]}/join','POST',{},'borrower')
invitation=api(f'/libraries/{fixtures["C"]}/invitations','POST',{'email':accounts['mixed']['email'],'role':'LIBRARIAN'},expected=201)
api('/invitations/'+invitation['invitation']['invitation_id']+'/accept','POST',{'token':invitation['invite_token']},'mixed')
for letter,owner in [('A','owner'),('B','mixed'),('C','owner')]:
    fixtures['book_'+letter]=api(f'/libraries/{fixtures[letter]}/inventory/books','POST',cmd(title='Part 2D QA lending book '+letter,subjects=['Community']),owner,201)['library_book_id']
proposal=migration.plan(db,{'platform_assignments':[{'user_id':accounts['platform']['user_id'],'role':'PLATFORM_ADMIN','approved':True,
    'approved_by':'local-development-review','approval_ref':'USER-INSTITUTION-V2D-QA',
    'reason':'Isolated local Part 2D platform-without-membership boundary and lifecycle fixture checks; revoke at cleanup.'}]})
migration.apply(db,proposal)
base_credentials=credentials
def credentials(account):
    return (accounts[account]['email'],accounts[account]['password']) if account in accounts else base_credentials(account)
def shot(name):
    target=REPORTS/f'institution_v2d_{name}.png';page.screenshot(path=str(target),full_page=True,animations='disabled');return str(target)
sys.stdout.reconfigure(encoding='utf8')
with sync_playwright() as playwright:
    browser=playwright.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':1440,'height':900})
    page=context.new_page();network=[];errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.on('response',lambda response:network.append({'path':urlparse(response.url).path,'status':response.status}) if '/api/' in response.url else None)
    print(json.dumps({'browser':browser.version,'fixtures':fixtures,'QA_accounts':[{k:v for k,v in row.items() if k!='password'} for row in accounts.values()],'mixed_roles':{'A':'GENERAL_USER','B':'ADMIN','C':'LIBRARIAN'}}),flush=True)
    for line in sys.stdin:
        try:
            command=json.loads(line)
            if command.get('stop'):break
            exec(command['code'],globals())
            print(json.dumps({'state':state(),'network':network[-8:],'errors':errors[-5:]},ensure_ascii=False),flush=True)
        except Exception as error:
            print(json.dumps({'error':type(error).__name__+': '+str(error).split('Call log:')[0],'state':state() if not page.is_closed() else None},ensure_ascii=False),flush=True)
    browser.close()
