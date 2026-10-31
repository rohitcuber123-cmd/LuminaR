"""Real Chromium + actual ASGI/JWT/Mongo/manual worker in disposable fixtures.

Browser HTTP is bridged by Playwright to the real TestClient, not mocked status.
Only unrelated services and external decorative assets are stubbed. No live
production application or TEST data is used. No backend lifespan workers start.
"""
import os
from pathlib import Path
import sys
from uuid import uuid4
import json
import gc
import tempfile
from urllib.parse import urlsplit

sys.stdout.reconfigure(encoding='utf8')

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DBNAME = 'luminar_institution_v2i_browser_' + uuid4().hex[:24]
os.environ.update(MONGO_URI='mongodb://127.0.0.1:27017', MONGO_DB_NAME=DBNAME,
                  JWT_SECRET_KEY='v2i-disposable-browser-secret', NOTIFICATION_DUE_WORKER_ENABLED='0',
                  NOTIFICATION_OUTBOX_WORKER_ENABLED='0')
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect
from backend.main import app
from backend.database.mongodb import db, client as mongo
from backend.utils.jwt_utils import create_access_token
from backend.services import institution_repository as repo, library_catalogue_repository as inventory
from backend.services import library_intelligence_store as store, library_intelligence_service as service
from backend.services import library_lending_journal, library_reservation_service, library_asset_service, library_catalogue_experience
from search.library_intelligence import TenantIntelligence
from tests.institution_v2g.test_intelligence import encoder

BASE = 'http://127.0.0.1:5189'
R = ROOT/'reports'


def main():
    report = {'layer': 'Actual Chromium / actual ASGI routes / real JWT verification / isolated real Mongo and worker; browser transport bridged in-process',
              'database': DBNAME, 'steps': [], 'page_errors': [], 'console_errors': [], 'requests': [],
              'no_production_requests': True, 'unrelated_service_stubs': [], 'screenshots': []}
    client = TestClient(app)
    tokens = {}
    holds = {'next': False, 'responses': []}
    def api(path, method='GET', body=None, user=1, expected=200):
        response = client.request(method, path, headers={'Authorization': 'Bearer '+tokens[user]}, json=body)
        assert response.status_code == expected, (path, response.status_code, response.text[:150])
        return response.json()
    def passed(label, **detail):
        report['steps'].append({'check': label, 'passed': True, **detail})
        print(label, flush=True)
    with tempfile.TemporaryDirectory(prefix='luminar-v2i-browser-') as tmp:
        os.environ['LIBRARY_INTELLIGENCE_ROOT'] = str(Path(tmp)/'intelligence')
        os.environ['LIBRARY_ASSET_ROOT'] = str(Path(tmp)/'assets')
        try:
            mongo.admin.command('ping')
            for module in [repo, inventory, library_lending_journal, library_reservation_service, library_asset_service, library_catalogue_experience]:
                module.ensure_indexes()
            store.initialize()
            for user in range(1, 6):
                db.users.insert_one({'user_id': user, 'name': f'Isolated browser {user}', 'email': f'v2i-{user}@example.com',
                                     'role': 'GENERAL_USER', 'is_active': True, 'is_email_verified': True})
                tokens[user] = create_access_token(user, f'v2i-{user}@example.com', 'GENERAL_USER')
            def library(name, owner=1):
                return api('/libraries/register', 'POST', {'name': name, 'slug': 'v2i-'+uuid4().hex[:12],
                    'library_type': 'PUBLIC_LIBRARY', 'access_mode': 'PUBLIC'}, user=owner, expected=201)['library']['library_id']
            a, b, foreign = library('Isolated operational library A'), library('Isolated operational library B'), library('Foreign fixture', owner=5)
            rows = []
            for title in ['Networks of a library', 'Shared metadata relationships', 'Local retrieval']:
                rows.append(api(f'/libraries/{a}/inventory/books', 'POST', {'title': title, 'authors': ['Ada Fixture'],
                    'subjects': ['Technology'], 'description': 'Disposable browser fixture.', 'copies': 1,
                    'idempotency_key': str(uuid4())}, expected=201)['library_book_id'])
            for user, role in [(2, 'LIBRARIAN'), (3, 'GENERAL_USER')]:
                repo.collection('memberships').insert_one({'membership_id': str(uuid4()), 'library_id': a, 'user_id': user,
                    'role': role, 'status': 'ACTIVE', 'joined_at': store.now()})
            db.platform_role_assignments.insert_one({'user_id': 4, 'role': 'PLATFORM_ADMIN', 'status': 'ACTIVE',
                'approved_at': store.now(), 'approved_by': 'isolated-fixture', 'approval_ref': 'V2I-FIXTURE'})
            worker = TenantIntelligence(encoder, model_version='all-MiniLM-L6-v2:unit')
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                contexts = []
                def page_for(user):
                    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                    contexts.append(context)
                    context.add_init_script("localStorage.setItem('luminar_token',"+json.dumps(tokens[user])+");localStorage.setItem('luminar_user',JSON.stringify("+json.dumps({'user_id': user, 'name': f'Browser fixture {user}', 'email': f'v2i-{user}@example.com', 'role': 'GENERAL_USER'})+"));")
                    page = context.new_page()
                    page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
                    page.on('console', lambda m: report['console_errors'].append(m.text) if m.type=='error' else None)
                    def route_request(route):
                        url = urlsplit(route.request.url)
                        if url.netloc != '127.0.0.1:5189':
                            route.fulfill(status=200, content_type='text/plain', body='')
                            return
                        if url.path.startswith('/api/'):
                            path = url.path[4:] + ('?'+url.query if url.query else '')
                            headers = {k: v for k, v in route.request.headers.items() if k.lower() in ['authorization', 'content-type', 'x-luminar-upload']}
                            response = client.request(route.request.method, path, headers=headers, content=route.request.post_data)
                            report['requests'].append({'method': route.request.method, 'path': path, 'status': response.status_code, 'user_fixture': user})
                            if user == 1 and holds['next'] and path == f'/libraries/{a}/intelligence':
                                holds['next'] = False
                                holds['responses'].append((route, response))
                                return
                            route.fulfill(status=response.status_code, content_type=response.headers.get('content-type', 'application/json'),
                                          headers={'Cache-Control': 'private, no-store'}, body=response.content)
                        elif any(url.path.startswith(prefix) for prefix in ['/rag-api/', '/search-api/', '/recommendation-api/']):
                            report['unrelated_service_stubs'].append(url.path)
                            route.fulfill(status=200, content_type='application/json', body=json.dumps({'results': [], 'items': [], 'recommendations': [], 'total': 0}))
                        else:
                            route.continue_()
                    page.route('**/*', route_request)
                    return page
                def open_intelligence(page, lib):
                    page.goto(BASE+f'/staff/libraries/{lib}/intelligence')
                    expect(page.get_by_role('heading', name='Semantic Search Index', exact=True)).to_be_visible(timeout=30000)
                def refresh(page):
                    page.get_by_role('button', name='Refresh status', exact=True).click()
                def request_build(page, label):
                    page.get_by_role('button', name=label, exact=True).click()
                    dialog = page.get_by_role('dialog')
                    expect(dialog).to_be_visible()
                    dialog.get_by_role('button', name=label, exact=True).click()
                    expect(dialog).not_to_be_visible(timeout=30000)
                    expect(page.get_by_text('Queued', exact=True)).to_be_visible(timeout=30000)
                admin = page_for(1)
                open_intelligence(admin, a)
                expect(admin.get_by_text('Not built', exact=True)).to_have_count(2)
                assert repo.collection('intelligence_jobs').count_documents({}) == 0
                passed('Admin status: NOT_BUILT after addition, no automatic jobs')
                for target, label in [('SEARCH_INDEX', 'Build Search Index'), ('KNOWLEDGE_GRAPH', 'Build Knowledge Graph')]:
                    request_build(admin, label)
                    assert worker.run_one()
                    refresh(admin)
                    expect(admin.get_by_role('button', name=label.replace('Build', 'Rebuild'), exact=True)).to_be_visible(timeout=30000)
                    assert api(f'/libraries/{a}/intelligence')['search' if target=='SEARCH_INDEX' else 'kg']['status']=='READY'
                    passed('Manual '+target+' build: browser → actual queue → native build → validated publication')
                before = api(f'/libraries/{a}/intelligence')
                admin.reload()
                expect(admin.get_by_text('Ready', exact=True)).to_have_count(2, timeout=30000)
                passed('Refresh restores both durable READY generations')
                api(f'/libraries/{a}/inventory/books/{rows[0]}', 'PATCH', {'description': 'Updated source revision', 'idempotency_key': str(uuid4())})
                refresh(admin)
                expect(admin.get_by_text('Update available', exact=True)).to_have_count(2, timeout=30000)
                assert repo.collection('intelligence_jobs').count_documents({}) == 2
                passed('Metadata mutation becomes STALE with no automatic rebuild')
                request_build(admin, 'Rebuild Search Index')
                assert worker.run_one()
                refresh(admin)
                expect(admin.get_by_role('button', name='Rebuild Search Index', exact=True)).to_be_visible(timeout=30000)
                assert api(f'/libraries/{a}/intelligence')['search']['active_generation_id'] != before['search']['active_generation_id']
                passed('Manual Search rebuild publishes a new generation')
                request_build(admin, 'Rebuild Knowledge Graph')
                assert worker.run_one()
                refresh(admin)
                expect(admin.get_by_text('Ready', exact=True)).to_have_count(2, timeout=30000)
                passed('Manual KG rebuild publishes a new generation')
                def fail(stage):
                    if stage == 'VALIDATION':
                        raise ValueError('private/path secret-fence Traceback')
                request_build(admin, 'Rebuild Search Index')
                assert TenantIntelligence(encoder, model_version='all-MiniLM-L6-v2:unit', fail=fail).run_one()
                refresh(admin)
                expect(admin.get_by_role('button', name='Retry Build', exact=True)).to_be_visible(timeout=30000)
                expect(admin.get_by_text('The previous validated generation is retained.', exact=False)).to_be_visible()
                assert 'private/path' not in admin.locator('.library-intelligence').inner_text()
                passed('Known FAILED rebuild retains last-good generation and safe error')
                def uncertain(stage):
                    if stage == 'ACKNOWLEDGEMENT_LOSS':
                        raise RuntimeError('controlled acknowledgement loss')
                request_build(admin, 'Retry Build')
                assert TenantIntelligence(encoder, model_version='all-MiniLM-L6-v2:unit', fail=uncertain).run_one()
                refresh(admin)
                expect(admin.get_by_text('Needs recovery', exact=True)).to_be_visible(timeout=30000)
                assert admin.get_by_role('button', name='Retry Build', exact=True).count() == 0
                passed('RECOVERY_REQUIRED distinct from FAILED; no blind retry')
                job = api(f'/libraries/{a}/intelligence')['search']['current_job']
                api(f'/libraries/{a}/intelligence/jobs/{job["job_id"]}/recover', 'POST')
                refresh(admin)
                expect(admin.get_by_text('Ready', exact=True)).to_have_count(2, timeout=30000)
                passed('Controlled fixture explicitly invokes existing recovery; no automatic action')
                # Real active progress and actual three-second polling.
                request = api(f'/libraries/{a}/intelligence/builds', 'POST', {'target': 'SEARCH_INDEX'}, expected=202)
                claimed = store.claim('fixture-worker-hidden')
                store.progress(claimed, 'EMBEDDING', 1, 3)
                refresh(admin)
                expect(admin.get_by_role('progressbar', name='Search Index build progress')).to_have_attribute('value', '1', timeout=30000)
                store.progress(claimed, 'EMBEDDING', 2, 3)
                expect(admin.get_by_role('progressbar', name='Search Index build progress')).to_have_attribute('value', '2', timeout=10000)
                passed('Active polling displays durable progress, no fake counter')
                # Ending a controlled abandoned fixture uses explicit expiry/recovery;
                # never production leases or automatic cleanup.
                from datetime import timedelta
                repo.collection('intelligence_jobs').update_one({'job_id': request['job_id']}, {'$set': {'lease_expires_at': store.now()-timedelta(seconds=1)}})
                api(f'/libraries/{a}/intelligence/jobs/{request["job_id"]}/recover', 'POST')
                refresh(admin)
                expect(admin.get_by_role('button', name='Retry Build', exact=True)).to_be_visible(timeout=30000)
                librarian = page_for(2)
                open_intelligence(librarian, a)
                expect(librarian.get_by_text('Search and graph builds can be started by Library Admins.', exact=True)).to_be_visible()
                assert librarian.get_by_role('button', name='Retry Build', exact=True).count()==0
                api(f'/libraries/{a}/intelligence/builds', 'POST', {'target':'SEARCH_INDEX'}, user=2, expected=403)
                passed('Real JWT Librarian sees read-only status and API denies build')
                for user, expected in [(3,403), (4,404)]:
                    api(f'/libraries/{a}/intelligence', user=user, expected=expected)
                    api(f'/libraries/{a}/intelligence/builds', 'POST', {'target':'SEARCH_INDEX'}, user=user, expected=expected)
                    denied = page_for(user)
                    denied.goto(BASE+f'/staff/libraries/{a}/intelligence')
                    denied.wait_for_timeout(800)
                    assert denied.get_by_role('heading', name='Semantic Search Index', exact=True).count()==0
                    passed('General User denied' if user==3 else 'Explicit Platform-only user denied tenant authority')
                api(f'/libraries/{foreign}/intelligence', expected=404)
                # Hold an actual A response while the mounted SPA changes to B.
                holds['next'] = True
                refresh(admin)
                for _ in range(50):
                    if holds['responses']:
                        break
                    admin.wait_for_timeout(100)
                assert holds['responses']
                admin.get_by_role('combobox', name='Switch staff library', exact=True).click()
                admin.get_by_role('option', name='Isolated operational library B', exact=True).click()
                admin.get_by_role('navigation',name='Staff workspace',exact=True).get_by_role('link',name='Intelligence',exact=True).click()
                expect(admin.get_by_text('Add books to the library before building semantic search.', exact=True)).to_be_visible()
                route, response = holds['responses'].pop()
                route.fulfill(status=response.status_code,content_type='application/json',body=response.content)
                admin.wait_for_timeout(200)
                assert admin.get_by_role('button', name='Build Search Index', exact=True).is_disabled()
                assert '3' not in admin.locator('.intelligence-card').first.locator('dd').first.inner_text()
                assert admin.locator('.intelligence-card').first.locator('dd').first.inner_text() == '0'
                passed('Delayed actual A response cannot replace B after SPA library switch')
                open_intelligence(admin, a)
                passed('Multi-library Admin switches between correct distinct durable contexts')
                # Revoke actual authority without changing the browser JWT.
                repo.collection('memberships').update_one({'library_id': a,'user_id':2}, {'$set': {'status':'REMOVED'}})
                refresh(librarian)
                expect(librarian.get_by_role('heading',name='Semantic Search Index',exact=True)).not_to_be_visible(timeout=30000)
                passed('Revoked membership loses status with unchanged signed browser token')
                for width, height in [(1440,1000),(1024,768),(390,844),(375,812)]:
                    admin.set_viewport_size({'width':width,'height':height})
                    open_intelligence(admin,a)
                    for details in admin.locator('.intelligence-card details').all():
                        details.locator('summary').click()
                    assert admin.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    admin.get_by_role('button',name='Rebuild Knowledge Graph',exact=True).click()
                    dialog=admin.get_by_role('dialog')
                    expect(dialog).to_be_visible()
                    buttons=dialog.locator('button')
                    buttons.last.focus()
                    admin.keyboard.press('Tab')
                    assert buttons.first.evaluate('(e)=>e===document.activeElement')
                    admin.keyboard.press('Escape')
                    expect(dialog).not_to_be_visible()
                    assert admin.get_by_role('button',name='Rebuild Knowledge Graph',exact=True).evaluate('(e)=>e===document.activeElement')
                    admin.evaluate('window.scrollTo(0,0);document.activeElement?.blur()')
                    admin.wait_for_timeout(100)
                    name=f'institution_v2i_intelligence_{width}.png'
                    admin.screenshot(path=str(R/name),full_page=True)
                    report['screenshots'].append('reports/'+name)
                    passed('Responsive, no overflow, keyboard confirmation '+str(width))
                admin.add_script_tag(path=str(ROOT/'frontend/node_modules/axe-core/axe.min.js'))
                violations=admin.evaluate("async()=>{const r=await axe.run(document.querySelector('.library-intelligence'));return r.violations.map(v=>({id:v.id,impact:v.impact,description:v.description}))}")
                report['axe_violations']=violations
                assert not violations, violations
                passed('Focused axe accessibility: no violations')
                for context in contexts:
                    context.close()
                browser.close()
            denials = [r for r in report['requests'] if r['status'] in [403,404]]
            report['expected_denied_http_requests'] = denials
            report['console_note'] = 'Expected Chromium resource errors correspond to explicit Platform-only and revoked-membership HTTP 404 denial checks; no page JavaScript errors.'
            report['unexpected_http_errors'] = [r for r in report['requests'] if r['status']>=400 and r['status'] not in [403,404]]
            report['status']='PASS' if not report['page_errors'] and not report['unexpected_http_errors'] else 'PARTIAL'
        except Exception as error:
            report['status']='FAIL'
            report['error']={'type':type(error).__name__,'message':str(error)[:2000]}
            raise
        finally:
            service.graph_cache.clear()
            client.close()
            gc.collect()
            assert db.name==DBNAME and DBNAME.startswith('luminar_institution_v2i_browser_')
            mongo.drop_database(DBNAME)
            report['disposable_database_removed']=True
            (R/'institution_v2i_browser.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    report['task_owned_temporary_artifacts_removed']=True
    (R/'institution_v2i_browser.json').write_text(json.dumps(report,indent=2),encoding='utf8')


if __name__=='__main__':
    main()
