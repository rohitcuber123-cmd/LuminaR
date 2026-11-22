"""Actual Chromium, real ASGI/JWT/Mongo; task-owned data only.

Browser requests bridge to the production FastAPI routes in TestClient. Only
unrelated search/recommendation/RAG/decorative network surfaces are stubbed.
The existing notification worker adapter is invoked explicitly in this fixture.
"""
import os,sys,json,time,subprocess,tempfile,traceback,secrets
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
NAME='luminar_institution_v2p1_browser_'+uuid4().hex[:24]
TMP=tempfile.TemporaryDirectory(prefix='luminar-v2p1-browser-')
os.environ.update(MONGO_URI='mongodb://127.0.0.1:27017',MONGO_DB_NAME=NAME,JWT_SECRET_KEY='part2p-owned-browser-key',
    NOTIFICATION_DUE_WORKER_ENABLED='0',NOTIFICATION_OUTBOX_WORKER_ENABLED='0',LUMINAR_SESSION_DB=str(Path(TMP.name)/'sessions.sqlite'),
    LIBRARY_ASSET_ROOT=str(Path(TMP.name)/'assets'),LIBRARY_INTELLIGENCE_ROOT=str(Path(TMP.name)/'intelligence'),LUMINAR_RAG_URL='http://127.0.0.1:9')
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright,expect
from backend.main import app
from backend.database.mongodb import db,client as mongo
from backend.utils.jwt_utils import create_access_token
from backend.services.auth_service import hash_password
from backend.services import institution_repository as repo,library_catalogue_repository as inventory,library_lending_journal,library_reservation_service,library_asset_service,library_catalogue_experience,event_service,notification_service,tenant_notification_service,library_announcement_service
BASE='http://127.0.0.1:5198'
REPORT=ROOT/'reports/institution_v2p1_browser.json'

def main():
    report={'layer':'Actual Chromium, production ASGI routes, actual JWT and isolated real standalone Mongo; in-process HTTP bridge',
        'database':NAME,'checks':[],'page_errors':[],'console_errors':[],'requests':[],'screenshots':[],'unrelated_stubs':[],'expected_denials':[]}
    client=TestClient(app);tokens={};contexts=[];server=None
    def passed(label,**data):report['checks'].append({'check':label,'passed':True,**data});print(label,flush=True)
    def api(path,method='GET',body=None,user=1,expected=200):
        r=client.request(method,path,json=body,headers={'Authorization':'Bearer '+tokens[user]})
        assert r.status_code==expected,(path,r.status_code,r.text[:160])
        return r.json()
    def shot(page,label):
        path=ROOT/f'reports/institution_v2p1_{label}.png';page.screenshot(path=str(path),full_page=True,animations='disabled');report['screenshots'].append(str(path))
    try:
        for module in [repo,inventory,library_lending_journal,library_reservation_service,library_asset_service,library_catalogue_experience,event_service,notification_service,tenant_notification_service,library_announcement_service]:module.ensure_indexes()
        password=secrets.token_urlsafe(24);hashed=hash_password(password)
        for uid in range(1,8):
            db.users.insert_one({'user_id':uid,'name':f'Part2P Browser {uid}','email':f'part2p-browser-{uid}@example.com','role':'GENERAL_USER','is_active':True,'is_email_verified':True,'password_hash':hashed})
            tokens[uid]=create_access_token(uid,f'part2p-browser-{uid}@example.com','GENERAL_USER')
        code=secrets.token_urlsafe(20)
        def library(letter,owner):
            return api('/libraries/register','POST',{'name':'Part2P Library '+letter,'slug':'part2p-'+uuid4().hex[:12],'library_type':'PRIVATE_INSTITUTION','access_mode':'PRIVATE_CODE','access_code':code},owner,201)['library']['library_id']
        a,b=library('A',1),library('B',5)
        for lib,uid,role in [(a,2,'GENERAL_USER'),(a,3,'LIBRARIAN'),(b,4,'GENERAL_USER')]:
            repo.collection('memberships').insert_one({'membership_id':str(uuid4()),'library_id':lib,'user_id':uid,'role':role,'status':'ACTIVE','joined_at':repo.now()})
        event=api(f'/libraries/{a}/events','POST',{'title':'Part2P Linked workshop','category':'LIBRARY_NOTICE','description':'Existing tenant event workflow.'},expected=201)
        api(f'/libraries/{a}/events/{event["event_id"]}/publish','POST')
        out=(ROOT/'reports/institution_v2p1_browser_vite.log').open('w',encoding='utf8')
        server=subprocess.Popen(['node',str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port','5198','--strictPort'],cwd=ROOT/'frontend',stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        import requests
        for _ in range(100):
            try:
                if requests.get(BASE,timeout=1).status_code==200:break
            except requests.RequestException:pass
            time.sleep(.1)
        else:raise RuntimeError('Owned Vite did not become ready')
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True);report['chromium']=browser.version
            def page_for(uid):
                context=browser.new_context(viewport={'width':1440,'height':1000});contexts.append(context)
                user={'user_id':uid,'name':f'Part2P Browser {uid}','email':f'part2p-browser-{uid}@example.com','role':'GENERAL_USER'}
                context.add_init_script("if(!sessionStorage.getItem('part2p-fixture-initialized')){localStorage.setItem('luminar_token',"+json.dumps(tokens[uid])+");localStorage.setItem('luminar_user',JSON.stringify("+json.dumps(user)+"));sessionStorage.setItem('part2p-fixture-initialized','1');}")
                page=context.new_page();page.on('pageerror',lambda e:report['page_errors'].append(str(e)))
                page.on('console',lambda m:report['console_errors'].append(m.text) if m.type=='error' else None)
                def route_request(route):
                    url=urlsplit(route.request.url)
                    if url.netloc!='127.0.0.1:5198':route.fulfill(status=200,content_type='text/plain',body='');return
                    if url.path.startswith('/api/'):
                        path=url.path[4:]+('?'+url.query if url.query else '')
                        headers={k:v for k,v in route.request.headers.items() if k.lower() in ['authorization','content-type']}
                        response=client.request(route.request.method,path,headers=headers,content=route.request.post_data)
                        report['requests'].append({'path':path,'method':route.request.method,'status':response.status_code,'fixture_user':uid})
                        route.fulfill(status=response.status_code,content_type=response.headers.get('content-type','application/json'),body=response.content)
                    elif url.path.startswith(('/rag-api/','/search-api/','/recommendation-api/')):
                        report['unrelated_stubs'].append(url.path);route.fulfill(status=200,content_type='application/json',body=json.dumps({'results':[],'items':[],'recommendations':[],'total':0}))
                    else:route.continue_()
                page.route('**/*',route_request);return page
            def open_page(page,lib,staff=False):
                page.goto(BASE+f'/{"staff/" if staff else ""}libraries/{lib}/announcements')
                expect(page.get_by_role('heading',name='Announcements',exact=True)).to_be_visible(timeout=30000)
            admin=page_for(1);open_page(admin,a,True)
            expect(admin.get_by_text('Create a draft to communicate with your members.')).to_be_visible()
            passed('Staff Announcements entry, empty state and existing workspace')
            admin.get_by_role('button',name='Create announcement',exact=True).click()
            dialog=admin.get_by_role('dialog',name='Create announcement',exact=True)
            expect(dialog.get_by_role('button',name='Save draft')).to_be_disabled()
            dialog.get_by_label('Title',exact=True).fill('Part2P Member announcement')
            dialog.get_by_label('Message',exact=True).fill('Members can read this message only with active membership.')
            dialog.get_by_role('combobox',name='Priority',exact=True).click();admin.get_by_role('option',name='Important',exact=True).click()
            dialog.get_by_role('combobox',name='Linked event (optional)',exact=True).click();admin.get_by_role('option',name=event['title'],exact=True).click()
            shot(admin,'staff_draft')
            dialog.get_by_role('button',name='Save draft').click();expect(dialog).not_to_be_visible()
            expect(admin.get_by_role('heading',name='Part2P Member announcement')).to_be_visible()
            row=api(f'/libraries/{a}/staff/announcements')['results'][0]
            passed('Actual draft creation, priority and linked existing event persisted')
            api(f'/libraries/{a}/announcements/{row["announcement_id"]}',user=2,expected=404)
            report['expected_denials'].append('Draft detail404 for member A')
            member=page_for(2);open_page(member,a)
            expect(member.get_by_text('Your library has no published announcements yet.')).to_be_visible()
            assert member.get_by_role('button',name='Create announcement').count()==0
            passed('Member cannot see draft or staff controls')
            admin.bring_to_front()
            admin.get_by_role('button',name='Edit draft',exact=True).click()
            shot(admin,'staff_edit')
            edit=admin.get_by_role('dialog',name='Edit draft',exact=True)
            edit.get_by_role('textbox',name='Message',exact=True).fill('Final published message for active members.')
            edit.get_by_role('button',name='Save draft').click();expect(edit).not_to_be_visible()
            admin.get_by_role('button',name='Preview',exact=True).click();preview=admin.get_by_role('dialog',name='Announcement preview')
            expect(preview.get_by_text('Final published message for active members.')).to_be_visible();admin.keyboard.press('Escape');expect(preview).not_to_be_visible()
            passed('Draft edit and preview; Escape closes shared dialog')
            admin.get_by_role('button',name='Publish',exact=True).click();confirm=admin.get_by_role('dialog',name='Publish announcement?')
            expect(confirm.get_by_text('Current eligible members will receive',exact=False)).to_be_visible()
            confirm.get_by_role('button',name='Publish announcement',exact=True).click();expect(confirm).not_to_be_visible()
            expect(admin.get_by_text('Published. Notification delivery pending',exact=False)).to_be_visible()
            passed('Explicit publication confirmation separates pending delivery from success')
            tenant_notification_service.materialize(500)
            member.reload();expect(member.get_by_role('link',name='Part2P Member announcement',exact=True)).to_be_visible()
            expect(member.get_by_role('button',name='Notifications, 1 unread')).to_be_visible()
            passed('Existing worker adapter materializes member A notification and unread badge')
            assert api('/notifications',user=4)['count']==0
            api(f'/libraries/{a}/announcements/{row["announcement_id"]}/withdraw','POST',{'revision':1},user=5,expected=404)
            report['expected_denials'].append('Other-library admin mutation404')
            passed('Library B member receives no A copy; Admin B cannot mutate A')
            member.get_by_role('button',name='Notifications, 1 unread').click()
            expect(member.get_by_role('region',name='Notification Center',exact=True).get_by_text('Part2P Library A',exact=True)).to_be_visible()
            member.get_by_role('button',name='Open Library announcement in Part2P Library A',exact=True).click()
            expect(member).to_have_url(BASE+f'/libraries/{a}/announcements/{row["announcement_id"]}')
            expect(member.get_by_text('Final published message for active members.')).to_be_visible()
            expect(member.get_by_role('button',name='Notifications',exact=True)).to_be_visible()
            member.reload();expect(member.get_by_role('button',name='Notifications',exact=True)).to_be_visible()
            assert api('/notifications',user=2)['notifications'][0]['read_at']
            passed('Fresh notification action navigates to A; read receipt survives browser reload')
            member.get_by_role('link',name='Open linked event',exact=True).click();expect(member.get_by_role('heading',name=event['title'],exact=True)).to_be_visible()
            passed('Linked event opens existing guarded event detail')
            librarian=page_for(3);librarian.goto(BASE+f'/staff/libraries/{a}/announcements')
            expect(librarian.get_by_role('heading',name='Announcements',exact=True)).to_be_visible(timeout=30000)
            expect(librarian.get_by_role('link',name='Part2P Member announcement',exact=True)).to_be_visible()
            assert librarian.get_by_role('button',name='Create announcement').count()==0
            api(f'/libraries/{a}/announcements','POST',{'title':'Denied notice','body':'No','request_id':str(uuid4())},user=3,expected=403)
            report['expected_denials'].append('Librarian create403')
            passed('Librarian retains Events workspace but has no announcement publishing permission')
            api(f'/libraries/{a}/announcements',user=6,expected=404)
            report['expected_denials'].append('Private-library outsider404')
            passed('Unrelated outsider cannot list private-library announcements')
            # Recipient A joins B only after A publication; no retroactive A copies.
            api(f'/libraries/{b}/join','POST',{'access_code':code},user=2)
            second=api(f'/libraries/{b}/announcements','POST',{'title':'Part2P Library B message','body':'B-only content','request_id':str(uuid4())},user=5,expected=201)
            api(f'/libraries/{b}/announcements/{second["announcement_id"]}/publish','POST',{'revision':0},user=5)
            tenant_notification_service.materialize(500)
            open_page(member,b);expect(member.get_by_role('link',name='Part2P Library B message')).to_be_visible()
            assert member.get_by_text('Final published message for active members.').count()==0
            passed('Library switch clears A content and shows canonical B messages')
            for width in [1440,1366,1024,768,390,375]:
                member.set_viewport_size({'width':width,'height':950});member.reload()
                expect(member.get_by_role('heading',name='Announcements',exact=True)).to_be_visible()
                overflow=member.evaluate('document.documentElement.scrollWidth>window.innerWidth+1')
                assert not overflow,('horizontal overflow',width)
                shot(member,f'member_{width}')
                passed(f'Member responsive viewport {width}, no document overflow')
            admin.set_viewport_size({'width':390,'height':950});open_page(admin,a,True)
            admin.get_by_role('button',name='Create announcement',exact=True).click();mobile=admin.get_by_role('dialog',name='Create announcement')
            expect(mobile.get_by_label('Title',exact=True)).to_be_visible()
            admin.add_script_tag(path=str(ROOT/'frontend/node_modules/axe-core/axe.min.js'))
            audit=admin.evaluate("async()=>await axe.run(document.querySelector('dialog'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
            assert not audit['violations'],[(v['id'],v['help']) for v in audit['violations']]
            report['axe']={'scope':'visible announcement draft dialog, WCAG2A/AA +2.1AA','violations':[]}
            shot(admin,'staff_mobile_dialog');admin.keyboard.press('Escape');expect(mobile).not_to_be_visible()
            expect(admin.get_by_role('button',name='Create announcement',exact=True)).to_be_focused()
            passed('Mobile staff draft, focused axe scan, keyboard Escape and focus restoration')
            open_page(admin,a,True);admin.get_by_role('button',name='Withdraw',exact=True).click()
            withdrawal=admin.get_by_role('dialog',name='Withdraw announcement?');withdrawal.get_by_role('button',name='Withdraw announcement',exact=True).click();expect(withdrawal).not_to_be_visible()
            api(f'/libraries/{a}/announcements/{row["announcement_id"]}',user=2,expected=404)
            open_page(member,a);expect(member.get_by_text('Your library has no published announcements yet.')).to_be_visible()
            assert api('/notifications',user=2)['notifications'][-1]['action_route'] is None
            report['expected_denials'].append('Withdrawn announcement404')
            passed('Withdrawal removes member content, retains safe generic inbox tombstone')
            # Real current authority change in owned fixture, followed by browser refresh.
            repo.collection('memberships').update_one({'library_id':b,'user_id':2},{'$set':{'status':'REMOVED'}})
            member.goto(BASE+f'/libraries/{b}/announcements')
            expect(member.get_by_role('alert').get_by_text('Unable to open this library',exact=True)).to_be_visible(timeout=30000)
            assert member.get_by_text('B-only content',exact=True).count()==0
            assert not [n for n in api('/notifications',user=2)['notifications'] if n.get('library_id')==b]
            report['expected_denials'].append('Revoked membership context404')
            passed('Membership revocation removes private B messages, inbox copy and unread count')
            # Logout uses actual revocation API; new login uses existing credentials.
            old=tokens[2];api('/auth/logout','POST',user=2)
            r=client.get('/notifications',headers={'Authorization':'Bearer '+old});assert r.status_code==401
            member.evaluate("localStorage.clear();sessionStorage.removeItem('luminar_workspace_contexts')")
            member.goto(BASE+'/login');expect(member.get_by_role('button',name='Sign In',exact=True)).to_be_visible(timeout=30000)
            logged=client.post('/auth/login',json={'email':'part2p-browser-2@example.com','password':password});assert logged.status_code==200
            tokens[2]=logged.json()['access_token']
            assert api('/notifications',user=2)['unread_count']==0
            passed('Actual logout revokes old JWT; login gets fresh session without revoked B content')
            # Existing2P all-member/lifecycle checks above are retained in this run.
            # Fresh fixture contexts exercise recipient scope with actual API authority.
            repo.collection('memberships').insert_one({'membership_id':str(uuid4()),'library_id':a,'user_id':7,'role':'GENERAL_USER','status':'ACTIVE','joined_at':repo.now()})
            repo.collection('memberships').insert_one({'membership_id':str(uuid4()),'library_id':a,'user_id':6,'role':'GENERAL_USER','status':'ACTIVE','joined_at':repo.now()})
            # Admin A can switch to B in the fixture without broader global authority.
            repo.collection('memberships').insert_one({'membership_id':str(uuid4()),'library_id':b,'user_id':1,'role':'ADMIN','status':'ACTIVE','joined_at':repo.now()})
            open_page(admin,a,True)
            admin.get_by_role('button',name='Create announcement',exact=True).click()
            targeted_dialog=admin.get_by_role('dialog',name='Create announcement',exact=True)
            targeted_dialog.get_by_role('combobox',name='Recipient scope',exact=True).click()
            admin.get_by_role('option',name='Specific member',exact=True).click()
            targeted_dialog.get_by_label('Title',exact=True).fill('Part2P1 Private recipient message')
            targeted_dialog.get_by_role('textbox',name='Message',exact=True).fill('Only the selected eligible member may read this message.')
            expect(targeted_dialog.get_by_role('button',name='Save draft',exact=True)).to_be_disabled()
            search_input=targeted_dialog.get_by_role('combobox',name='Find member by name or email',exact=True)
            search_input.fill('part2p-browser-7@example.com')
            option=targeted_dialog.get_by_role('option',name='Part2P Browser 7 part2p-browser-7@example.com Account 7',exact=True)
            expect(option).to_be_visible()
            admin.add_script_tag(path=str(ROOT/'frontend/node_modules/axe-core/axe.min.js'))
            audit=admin.evaluate("async()=>await axe.run(document.querySelector('dialog'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
            assert not audit['violations'],[(v['id'],v['help']) for v in audit['violations']]
            report['targeted_axe']={'scope':'mobile specific-member editor with open picker','violations':[]}
            search_input.press('ArrowDown');search_input.press('Enter')
            expect(targeted_dialog.get_by_text('Selected member: Part2P Browser 7',exact=True)).to_be_visible()
            passed('Actual bounded scoped email search, keyboard selection and explicit missing-recipient validation')
            for width in [1440,768,390,375]:
                admin.set_viewport_size({'width':width,'height':950})
                assert not admin.evaluate('document.documentElement.scrollWidth>window.innerWidth+1'),width
            shot(admin,'targeted_mobile_selected')
            targeted_dialog.get_by_role('button',name='Save draft',exact=True).click();expect(targeted_dialog).not_to_be_visible()
            private=next(r for r in api(f'/libraries/{a}/staff/announcements')['results'] if r['title']=='Part2P1 Private recipient message')
            article=admin.locator('article').filter(has=admin.get_by_role('heading',name=private['title'],exact=True))
            article.get_by_role('button',name='Publish',exact=True).click()
            confirmation=admin.get_by_role('dialog',name='Publish announcement?',exact=True)
            expect(confirmation.get_by_text('Selected member: Part2P Browser 7 (part2p-browser-7@example.com)',exact=True)).to_be_visible()
            confirmation.get_by_role('button',name='Publish announcement',exact=True).click();expect(confirmation).not_to_be_visible()
            tenant_notification_service.materialize(500)
            delivery=library_announcement_service.document(a,private['announcement_id'])['delivery']
            assert delivery['total']==delivery['delivered']==1
            assert db.notifications.count_documents({'source_id':private['announcement_id']})==1
            library_announcement_service.deliver_one(a,private['announcement_id'])
            assert db.notifications.count_documents({'source_id':private['announcement_id']})==1
            passed('Targeted publication confirmation, one shared-inbox copy, retry dedupe and no all-member fan-out')
            recipient=page_for(7);open_page(recipient,a)
            expect(recipient.get_by_role('link',name=private['title'],exact=True)).to_be_visible()
            expect(recipient.get_by_text('Private message for you',exact=True)).to_be_visible()
            expect(recipient.get_by_role('button',name='Notifications, 1 unread',exact=True)).to_be_visible()
            ordinary=page_for(6);open_page(ordinary,a)
            assert ordinary.get_by_role('link',name=private['title'],exact=True).count()==0
            assert ordinary.get_by_role('button',name='Notifications, 1 unread',exact=True).count()==0
            outsider=page_for(4);open_page(outsider,b)
            assert outsider.get_by_role('link',name=private['title'],exact=True).count()==0
            assert not [n for n in api('/notifications',user=6)['notifications'] if n.get('source_id')==private['announcement_id']]
            assert not [n for n in api('/notifications',user=4)['notifications'] if n.get('source_id')==private['announcement_id']]
            for uid in [6,4]:
                api(f'/libraries/{a}/announcements/{private["announcement_id"]}',user=uid,expected=404)
            ordinary.goto(BASE+f'/libraries/{a}/announcements/{private["announcement_id"]}')
            expect(ordinary.get_by_role('alert').get_by_text('Announcement not found or withdrawn.',exact=True)).to_be_visible()
            assert ordinary.get_by_text('Only the selected eligible member may read this message.',exact=True).count()==0
            assert api('/notifications',user=6)['unread_count']==0
            assert api('/notifications',user=4)['unread_count']==1
            passed('Recipient sees private message/unread; same-library other member and Library B cannot list, receive or forward URL')
            recipient.get_by_role('button',name='Notifications, 1 unread',exact=True).click()
            recipient.get_by_role('button',name='Open Library announcement in Part2P Library A',exact=True).click()
            expect(recipient).to_have_url(BASE+f'/libraries/{a}/announcements/{private["announcement_id"]}')
            expect(recipient.get_by_text('Only the selected eligible member may read this message.',exact=True)).to_be_visible()
            recipient.reload();expect(recipient.get_by_role('button',name='Notifications',exact=True)).to_be_visible()
            assert api('/notifications',user=7)['unread_count']==0
            passed('Targeted shared bell navigation and read receipt survive real browser refresh')
            open_page(admin,a,True);admin.get_by_role('button',name='Create announcement',exact=True).click()
            fresh=admin.get_by_role('dialog',name='Create announcement',exact=True)
            fresh.get_by_role('combobox',name='Recipient scope',exact=True).click();admin.get_by_role('option',name='Specific member',exact=True).click()
            fresh.get_by_role('combobox',name='Find member by name or email',exact=True).fill('part2p-browser-7@example.com')
            fresh.get_by_role('option',name='Part2P Browser 7 part2p-browser-7@example.com Account 7',exact=True).click()
            fresh.get_by_role('button',name='Cancel',exact=True).click()
            admin.set_viewport_size({'width':1440,'height':1000})
            admin.get_by_role('combobox',name='Switch staff library',exact=True).click()
            admin.get_by_role('option',name='Part2P Library B',exact=True).click()
            admin.get_by_role('navigation',name='Staff workspace',exact=True).get_by_role('link',name='Announcements',exact=True).click()
            expect(admin.get_by_role('heading',name='Announcements',exact=True)).to_be_visible()
            admin.get_by_role('button',name='Create announcement',exact=True).click()
            switched=admin.get_by_role('dialog',name='Create announcement',exact=True)
            assert switched.get_by_text('part2p-browser-7@example.com',exact=True).count()==0
            expect(switched.get_by_role('combobox',name='Recipient scope',exact=True)).to_contain_text('All active members')
            admin.keyboard.press('Escape')
            passed('Switching institution clears selected recipient; new draft remains explicit all-members default')

            expected_statuses={401,403,404}
            report['http_denials']=[r for r in report['requests'] if r['status']>=400]
            assert not [r for r in report['http_denials'] if r['status'] not in expected_statuses]
            assert not report['page_errors'],report['page_errors']
            unexpected=[m for m in report['console_errors'] if 'Failed to load resource' not in m]
            assert not unexpected,unexpected
            passed('No unexpected HTTP or page-JavaScript errors; denial responses explicitly recorded')
            report['result']='PASS'
            for context in contexts:context.close()
            browser.close()
    except Exception as error:
        report.update(result='FAIL',error=type(error).__name__,traceback=traceback.format_exc());raise
    finally:
        if server is not None:server.terminate();server.wait(timeout=20);out.close()
        assert db.name==NAME and NAME.startswith('luminar_institution_v2p1_browser_');mongo.drop_database(NAME)
        report['owned_database_removed']=True;TMP.cleanup();report['owned_temporary_files_removed']=True
        REPORT.write_text(json.dumps(report,indent=2),encoding='utf8')
if __name__=='__main__':main()
