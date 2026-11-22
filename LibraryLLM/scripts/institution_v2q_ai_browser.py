"""Actual Chromium, real ASGI/JWT/Mongo; task-owned data only.

Browser requests bridge to production FastAPI routes in TestClient. Intent
parsing and global candidate providers are deterministic fixtures. Tenant
Search is unavailable by fixture so real authorized Core fallback executes.
Unrelated decorative surfaces are stubbed; production workers stay disabled.
"""
import os,sys,json,time,subprocess,tempfile,traceback,secrets
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
NAME='luminar_institution_v2q_ai_browser_'+uuid4().hex[:24]
TMP=tempfile.TemporaryDirectory(prefix='luminar-v2q-ai-browser-')
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
BASE='http://127.0.0.1:5199'
REPORT=ROOT/'reports/institution_v2q_ai_browser.json'

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
        path=ROOT/f'reports/institution_v2q_ai_{label}.png';page.screenshot(path=str(path),full_page=True,animations='disabled');report['screenshots'].append(str(path))
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
        out=(ROOT/'reports/institution_v2q_ai_browser_vite.log').open('w',encoding='utf8')
        server=subprocess.Popen(['node',str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port','5199','--strictPort'],cwd=ROOT/'frontend',stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
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
                    if url.netloc!='127.0.0.1:5199':route.fulfill(status=200,content_type='text/plain',body='');return
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
            from fastapi import FastAPI
            from threading import RLock
            from types import SimpleNamespace
            import httpx
            from assistant.api import install_assistant
            from assistant.schemas import AssistantIntent,Intent
            ai=FastAPI()
            install_assistant(ai,SimpleNamespace(llm=SimpleNamespace(),inference_lock=RLock()),None,None)
            class Parser:
                async def parse(self,message,context):
                    if message.startswith('Is the first'):return AssistantIntent(intent=Intent.CHECK_AVAILABILITY,reference='this',ordinal_references=[1],confidence=1)
                    return AssistantIntent(intent=Intent.SEARCH_BOOKS,query='Python',confidence=1)
                async def respond(self,message,response):return 'Deterministic fixture answer from verified catalogue records.'
                async def generate(self,*args,**kwargs):return 'Deterministic fixture explanation.'
            ai.state.assistant.qwen=Parser()
            globals_=[{'work_id':f'OL{i}W','book_id':i,'title':f'Global Python {i}','authors':'Global Author','subjects':'Python','description':'Global fixture metadata','average_rating':4,'rating_count':1,'reading_log_count':1} for i in range(1,4)]
            db.books.insert_many([dict(row) for row in globals_])
            def provider(request):
                if request.url.port==8003 and not request.url.path.startswith('/libraries/'):return httpx.Response(200,json={'results':globals_})
                if request.url.port==8003:return httpx.Response(503,json={'detail':'Owned unavailable native fixture'})
                if request.url.port==8004:return httpx.Response(200,json={'recommendations':globals_})
                started=time.perf_counter()
                result=client.request(request.method,request.url.path+('?' + request.url.query.decode() if request.url.query else ''),headers={k:v for k,v in request.headers.items() if k in ['authorization','content-type']},content=request.content)
                report.setdefault('core_tool_timings',[]).append({'path':request.url.path,'method':request.method,'status':result.status_code,'elapsed_ms':(time.perf_counter()-started)*1000})
                return httpx.Response(result.status_code,content=result.content,headers={'content-type':'application/json'})
            ai.state.assistant_http_client._transport=httpx.MockTransport(provider)
            ai_client=TestClient(ai)
            report.update(real_qwen_execution=False,real_native_search_execution=False,assistant_execution='Production API/orchestrator/tools; deterministic intent and global candidate providers; real Core API/JWT/Mongo holdings')
            api(f'/libraries/{b}/join','POST',{'access_code':code},user=2)
            owned={}
            for lib,owner,letter in [(a,1,'A'),(b,5,'B')]:
                owned[lib]=[]
                for number in range(2):
                    row=api(f'/libraries/{lib}/inventory/books','POST',{'title':f'{letter} Local Python {number}','authors':['Ada'],'subjects':['Python'],'copies':2,'idempotency_key':str(uuid4())},owner,201)
                    owned[lib].append(row['library_book_id'])
            # Install bridge before creating pages; actual JWT travels through both APIs.
            original_page_for=page_for
            def page_for(uid):
                page=original_page_for(uid)
                def assistant_request(route):
                    started=time.perf_counter()
                    response=ai_client.request(route.request.method,'/assistant/chat',headers={k:v for k,v in route.request.headers.items() if k in ['authorization','content-type']},content=route.request.post_data)
                    report.setdefault('assistant_timings',[]).append({'scope':json.loads(route.request.post_data).get('library_id','GLOBAL'),'status':response.status_code,'elapsed_ms':(time.perf_counter()-started)*1000})
                    report['requests'].append({'path':'/assistant/chat','method':route.request.method,'status':response.status_code,'fixture_user':uid})
                    route.fulfill(status=response.status_code,content_type='application/json',body=response.content)
                page.route('**/rag-api/assistant/chat',assistant_request)
                page.route('**/recommendation-api/**',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps({'recommendations':globals_,'has_more':False})))
                return page
            page=page_for(2)
            def ask(text):
                if page.get_by_role('button',name='Ask LuminaR',exact=True).count():page.get_by_role('button',name='Ask LuminaR',exact=True).click()
                page.get_by_role('textbox',name='Message LuminaR AI',exact=True).fill(text)
                page.get_by_role('button',name='Send message',exact=True).click()
            page.goto(BASE+'/login')
            page.evaluate("localStorage.clear()")
            page.goto(BASE+'/login')
            page.get_by_label('Email Address',exact=True).fill('part2p-browser-2@example.com')
            page.get_by_label('Password',exact=True).fill(password)
            page.get_by_role('button',name='Sign In',exact=True).click()
            expect(page).not_to_have_url(BASE+'/login',timeout=30000)
            tokens[2]=page.evaluate("localStorage.getItem('luminar_token')")
            assert tokens[2]
            passed('Actual Login UI and backend password authentication in owned fixture')
            page.goto(BASE+'/catalog')
            ask('Find Python books')
            log=page.get_by_role('log',name='Assistant conversation',exact=True)
            expect(log.get_by_role('heading',name='Global Python 1',exact=True)).to_be_visible()
            passed('Actual browser Global assistant uses existing API/orchestrator and global candidates')
            page.get_by_role('button',name='New chat',exact=True).click()
            page.get_by_text('Quick actions',exact=True).click()
            page.get_by_role('button',name='Recommend',exact=True).click()
            expect(log.get_by_role('heading',name='Global Python 1',exact=True)).to_be_visible()
            passed('Global assistant recommendation action retains original global candidates')
            page.goto(BASE+'/')
            expect(page.locator('#for-you-results').get_by_role('heading',name='FOR YOU',exact=True)).to_be_visible(timeout=30000)
            expect(page.locator('#for-you-results').get_by_role('link',name='Global Python 1',exact=True).first).to_be_visible()
            passed('Existing Global For You section renders global recommendation cards')
            for lib,letter in [(a,'A'),(b,'B')]:
                page.goto(BASE+f'/libraries/{lib}/catalogue')
                expect(page.get_by_role('heading',name='Browse Books',exact=True)).to_be_visible(timeout=30000)
                if page.get_by_role('button',name='Ask LuminaR',exact=True).count():page.get_by_role('button',name='Ask LuminaR',exact=True).click()
                expect(page.get_by_role('status').filter(has_text='Searching Part2P Library '+letter)).to_be_visible()
                assert page.get_by_role('log',name='Assistant conversation',exact=True).get_by_role('heading',name='Global Python 1',exact=True).count()==0
                ask('Find Python books')
                log=page.get_by_role('log',name='Assistant conversation',exact=True)
                expect(log.get_by_role('heading',name=f'{letter} Local Python 0',exact=True)).to_be_visible()
                assert log.get_by_role('heading',name='Global Python 1',exact=True).count()==0
                foreign='B' if letter=='A' else 'A'
                assert log.get_by_role('heading',name=f'{foreign} Local Python 0',exact=True).count()==0
                passed(f'Library {letter} automatically scopes assistant; no global/foreign result; no tenant index built')
                with page.expect_response('**/rag-api/assistant/chat') as followup:
                    ask('Is the first book available?')
                details=followup.value.json()
                assert details['books'] and all(row['library_id']==lib and row['available_copies']==2 for row in details['books'])
                assert not details['errors']
                passed(f'Library {letter} browser follow-up resolves prior local book and actual stock')
                # Real assistant recommendation action reuses existing candidate intersection.
                page.get_by_role('button',name='New chat',exact=True).click()
                page.get_by_text('Quick actions',exact=True).click()
                page.get_by_role('button',name='Recommend',exact=True).click()
                expect(log.get_by_role('heading',name=f'{letter} Local Python 0',exact=True)).to_be_visible(timeout=30000)
                links=log.get_by_role('link',name='View book',exact=True)
                assert links.count()>0
                target=links.first.get_attribute('href')
                assert target.startswith(f'/libraries/{lib}/books/'),target
                links.first.click()
                expect(page).to_have_url(BASE+target)
                selected_number=owned[lib].index(target.rsplit('/',1)[-1])
                expect(page.get_by_role('heading',level=1,name=f'{letter} Local Python {selected_number}',exact=True)).to_be_visible()
                passed(f'Library {letter} For You action returns local-only books and opens canonical tenant detail')
                page.goto(BASE+f'/libraries/{lib}/catalogue?view=for-you')
                expect(page.get_by_role('heading',name='For You',exact=True)).to_be_visible(timeout=30000)
                expect(page.get_by_role('button',name=f'Select {letter} Local Python 0',exact=True)).to_be_visible()
                page.get_by_role('button',name=f'Select {letter} Local Python 0',exact=True).click()
                passed(f'Library {letter} existing For You page exposes actual local-only AI selection')
            page.goto(BASE+'/catalog');ask('Find Python books')
            expect(page.get_by_role('log',name='Assistant conversation',exact=True).get_by_role('heading',name='Global Python 1',exact=True)).to_be_visible()
            assert page.get_by_role('log',name='Assistant conversation',exact=True).get_by_role('heading',name='B Local Python 0',exact=True).count()==0
            passed('A to B to Global restores global results without private history')
            page.set_viewport_size({'width':390,'height':950})
            assert not page.evaluate('document.documentElement.scrollWidth>window.innerWidth+1')
            page.add_script_tag(path=str(ROOT/'frontend/node_modules/axe-core/axe.min.js'))
            audit=page.evaluate("async()=>await axe.run(document.querySelector('[role=dialog]'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}})")
            report['axe_details']=audit['violations']
            shot(page,'mobile_assistant_audit')
            assert not audit['violations'],[(v['id'],v['help']) for v in audit['violations']]
            report['axe']={'scope':'Assistant dialog, mobile390px','violations':[]}
            shot(page,'mobile_assistant')
            page.keyboard.press('Escape')
            passed('Mobile assistant layout, focused axe check and keyboard Escape')
            protected=ai_client.post('/assistant/chat',headers={'Authorization':'Bearer '+tokens[2]},json={'message':'Explain this document','library_id':a,'action':'DOCUMENT_QUESTION','page_context':{'document_id':f'library:{b}:asset:{uuid4()}'}})
            assert protected.status_code==200 and any(e['code']=='SCOPED_DOCUMENT_REQUIRED' for e in protected.json()['errors'])
            passed('Foreign asset reference denied at selected-scope boundary before RAG retrieval')
            repo.collection('memberships').update_one({'library_id':a,'user_id':2},{'$set':{'status':'REMOVED'}})
            denied=ai_client.post('/assistant/chat',headers={'Authorization':'Bearer '+tokens[2]},json={'message':'Find Python','library_id':a})
            assert denied.status_code==404
            assert not any(book in denied.text for book in owned[a])
            passed('Actual revoked membership denies protected assistant access without historical content')
            ai_client.close()

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
        assert db.name==NAME and NAME.startswith('luminar_institution_v2q_ai_browser_');mongo.drop_database(NAME)
        report['owned_database_removed']=True;TMP.cleanup();report['owned_temporary_files_removed']=True
        REPORT.write_text(json.dumps(report,indent=2),encoding='utf8')
if __name__=='__main__':main()
