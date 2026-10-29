"""Actual Chromium UI over Vite, all service data intercepted fixture responses.

No requests reach real application services or private data. This is browser
component/application routing evidence, not live JWT/Mongo/staging qualification.
"""
from pathlib import Path
import json,time,sys
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports';TAG=sys.argv[1] if len(sys.argv)>1 else '';assert not TAG or TAG.isalnum();BASE='http://127.0.0.1:5188'


def result(query,version=1):
    pending='[author]' in query
    return dict(results=[] if pending else [dict(work_id='OL1W',title='Biology: A Practical Introduction',authors=['Ada Sage'],subjects=['Biology'],rating=4.5,rating_count=12,readable=False,rag_available=False),
        dict(work_id='OL2W',title='Field Notes on Coastal Ecosystems',authors=['R. Vale'],subjects=['Ecology'],rating=4.2,rating_count=8,readable=False,rag_available=False)],
        total=None,offset=0,limit=10,has_more=False,coverage=dict(kind='RANKED_CANDIDATE_WINDOW',complete=False,notice='Filters are enforced. Results cover a bounded retrieval window; this is not a complete catalogue count.'),
        interpretation=dict(mode='SMART',chips=[] if pending else [dict(key='rating_min',label='Rating: ≥ 4'),dict(key='format',label='Format: Online only')],corrections=[]),
        preview=dict(state_id='server-fixture-state',accepted_plan_version=version,original_query=query,accepted_query=query,parser_version='v11',source_digest='fixture-source',ir_digest='fixture-ir',expires_at='future',mode='SMART',decision='INCOMPLETE' if pending else 'EXECUTABLE',message='Which author?' if pending else '',advisory='Prefer practical examples',operations=[dict(operation_id='issued-author',kind='complete',field='author',label='Complete author',input_type='text')] if pending else []))


def main():
    requests=[];errors=[];console_errors=[];external_stubs=[];steps=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        context=browser.new_context(viewport=dict(width=1440,height=1100),device_scale_factor=1)
        context.add_init_script("localStorage.setItem('luminar_token','preview-browser-fixture');localStorage.setItem('luminar_user',JSON.stringify({user_id:2,name:'Preview Reader',email:'fixture@example.com',role:'GENERAL_USER'}));")
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('console',lambda msg:console_errors.append(msg.text) if msg.type=='error' else None)
        def intercept(route):
            url=urlparse(route.request.url);path=url.path
            if url.netloc!='127.0.0.1:5188':
                external_stubs.append(dict(host=url.netloc,resource_type=route.request.resource_type))
                # An empty successful fixture resource lets the existing image
                # decoder use its generated cover fallback without a deliberate
                # ERR_FAILED network abort polluting application-console QA.
                route.fulfill(status=200,content_type='text/plain',body='');return
            if any(path.startswith(p) for p in ['/api/','/search-api/','/recommendation-api/','/rag-api/']):
                requests.append(dict(path=path,method=route.request.method))
                if path=='/search-api/query/features':value=dict(smart_preview=True,default='C4',max_query_length=500)
                elif path=='/search-api/query/preview':
                    body=route.request.post_data_json;query=body['query'];version=body.get('version',0)+1
                    if body.get('operation_id'):query=query.replace('[author]','"Ada Sage"')
                    value=result(query,version)
                elif '/institutions' in path or '/libraries' in path:value=dict(libraries=[],results=[],invitations=[],total=0)
                elif '/notifications' in path:value=dict(notifications=[],results=[],unread_count=0,total=0)
                else:value=dict(results=[],categories=[],recommendations=[],books=[],libraries=[],items=[],issues=[],reservations=[],total=0)
                route.fulfill(status=200,content_type='application/json',body=json.dumps(value));return
            route.continue_()
        page.route('**/*',intercept)
        page.goto(BASE+'/search?search_preview=1&q=books%20about%20biology%3B%20rating%20at%20least%204%3B%20only%20online')
        expect(page.get_by_role('heading',name='Search preview',exact=True)).to_be_visible()
        expect(page.get_by_role('article',name='Biology: A Practical Introduction')).to_be_visible()
        expect(page.get_by_role('group',name='Enforced filters')).to_be_visible()
        expect(page.get_by_text('Preference: Prefer practical examples')).to_be_visible()
        before=len([r for r in requests if r['path']=='/search-api/query/preview']);page.wait_for_timeout(300)
        assert len([r for r in requests if r['path']=='/search-api/query/preview'])==before==1
        page.screenshot(path=str(R/('search_arch11_desktop'+TAG+'.png')),full_page=True)
        steps.append(dict(check='desktop_cards_theme_filters_no_duplicate_initial_request',passed=True,layer='BROWSER_WITH_MOCK_SERVICE_DATA'))
        page.add_script_tag(path=str(ROOT/'frontend/node_modules/axe-core/axe.min.js'))
        axe=page.evaluate("async()=>{const x=await axe.run(document.querySelector('.product-catalogue'));return x.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,html:n.html,failure:n.failureSummary})),description:v.description}))}")
        steps.append(dict(check='axe_preview_surface',passed=len(axe)==0,violations=axe))
        page.set_viewport_size(dict(width=390,height=844));page.screenshot(path=str(R/('search_arch11_mobile'+TAG+'.png')),full_page=True)
        overflow=page.evaluate('document.documentElement.scrollWidth>window.innerWidth')
        assert not overflow
        steps.append(dict(check='mobile_no_horizontal_overflow',passed=True))
        textbox=page.get_by_role('textbox',name='Search query');textbox.fill('books about biology; by [author]')
        page.get_by_role('button',name='Search',exact=True).click();expect(page.get_by_text('Which author?',exact=True)).to_be_visible()
        page.get_by_role('textbox',name='Complete author').fill('Ada Sage');page.get_by_role('button',name='Apply',exact=True).click()
        expect(textbox).to_have_value('books about biology; by "Ada Sage"');expect(textbox).to_be_focused()
        steps.append(dict(check='keyboard_completion_accepted_source_and_focus',passed=True))
        textbox.fill('x'*501);expect(page.get_by_role('button',name='Search',exact=True)).to_be_disabled()
        assert '501/500' in page.locator('#search-preview-length').inner_text()
        steps.append(dict(check='long_query_validation_without_truncation',passed=True))
        page.get_by_role('link',name='Use standard search',exact=True).click()
        expect(page.get_by_role('heading',name='Search',exact=True)).to_be_visible()
        assert 'search_preview=1' not in page.url
        steps.append(dict(check='C4_UI_rollback_navigation',passed=True))
        browser.close()
    report=dict(status='PASS' if all(s['passed'] for s in steps) and not errors and not console_errors else 'ISSUES_FOUND',steps=steps,page_errors=errors,console_errors=console_errors,
        service_requests=requests,external_resource_stubs=external_stubs,real_service_requests=0,real_external_requests=0,real_jwt=False,mongo_mutations=0,
        screenshots=['reports/search_arch11_desktop'+TAG+'.png','reports/search_arch11_mobile'+TAG+'.png'],layer='ACTUAL_CHROMIUM_APPLICATION_UI_WITH_INTERCEPTED_FIXTURES')
    with (R/('search_arch11_browser_qa'+TAG+'.json')).open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))

if __name__=='__main__':main()
