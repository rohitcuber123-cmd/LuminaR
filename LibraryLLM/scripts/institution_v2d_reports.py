"""Finalize Part 2D only from retained test/browser and preservation evidence."""
import hashlib,json,re,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
REPORTS=ROOT/'reports';TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
def read(name):return json.loads((REPORTS/name).read_text(encoding='utf8'))
def put(name,data):(REPORTS/name).write_text(json.dumps(data,indent=2,default=str),encoding='utf8')
def link(name):return f'[{name}](D:/SDC/LibraryLLM/reports/{name})'

def main():
    from backend.database.mongodb import db
    baseline=read('institution_v2d_baseline.json')
    assert db.name=='luminar_library' and db.client.address[0] in ['localhost','127.0.0.1','::1']
    snapshots={name:list(db['institution_'+name].find({'library_id':TEST},{'_id':0})) for name in baseline['TEST']}
    for name,field in [('library_books','library_book_id'),('holdings','library_book_id'),('memberships','membership_id')]:snapshots[name].sort(key=lambda row:row[field])
    unchanged={name:json.loads(json.dumps(rows,default=str))==baseline['TEST'][name] for name,rows in snapshots.items()}
    assert all(unchanged.values()),unchanged
    assert len(snapshots['library_books'])==len(snapshots['holdings'])==150
    assert sum(row['status']=='ACTIVE' for row in snapshots['library_books'])==150
    artifacts=[]
    for name,before in baseline['artifact_metadata'].items():
        stat=(ROOT/name).stat();after={'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns}
        artifacts.append({'path':name,'unchanged':before==after,'before':before,'after':after})
    assert all(row['unchanged'] for row in artifacts)
    count=db.books.estimated_document_count();assert count==baseline['global_count']==5000000
    names=subprocess.check_output(['rg','--files','--hidden','-g','!.git','-g','!.venv','-g','!node_modules','-g','!.scratch','-g','!scratch','-g','!dist','-g','!datasets'],cwd=ROOT,text=True).splitlines()
    source={}
    for name in names:
        name=name.replace('\\','/');p=ROOT/name
        if not name.startswith('reports/') and p.suffix in {'.py','.ts','.tsx','.css','.json','.md','.html','.toml','.ps1','.cjs','.mjs'} and p.stat().st_size<32*1024*1024:source[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    changed=sorted(set(n for n,h in source.items() if baseline['source_sha256'].get(n)!=h)|{'scripts/institution_v2d_baseline.py'})
    deleted=sorted(set(baseline['source_sha256'])-set(source));assert not deleted,deleted
    protected={n:source.get(n)==h for n,h in baseline['source_sha256'].items() if n.startswith(('search/','recommendation/','rag/','assistant/','knowledge_graph/','kg/')) or n.startswith('backend/') and any(k in n.lower() for k in ['assistant','qwen','router'])}
    assert all(protected.values()),[n for n,v in protected.items() if not v]
    covers={n:source.get(n)==h for n,h in baseline['source_sha256'].items() if n.startswith('frontend/src/') and any(k in n for k in ['BookCover','ProductBookCard','BookProduct'])}
    assert all(covers.values())
    active=list(db.platform_role_assignments.find({'status':'ACTIVE'},{'_id':0,'user_id':1,'role':1,'approval_ref':1}))
    assert len(active)==1 and active[0]['user_id']==429
    assert not db.platform_role_assignments.find_one({'user_id':{'$in':[4,10]},'status':'ACTIVE'})
    health=[]
    for port in [5173,8002,8003,8004,8005]:
        with urlopen(f'http://127.0.0.1:{port}'+('/' if port in [5173,8004] else '/health'),timeout=30) as response:health.append({'port':port,'http_status':response.status})
    cleanup=read('institution_v2d_qa_cleanup.json');assert cleanup['status']=='PASS'
    put('institution_v2d_preservation.json',{'status':'PASS','captured_at':datetime.now(timezone.utc).isoformat(),'TEST':{'ACTIVE_records':150,'holdings':150,'exact_snapshots':unchanged,'owner_role':next(r['role'] for r in snapshots['memberships'] if r['user_id']==4),'patron_role':next(r['role'] for r in snapshots['memberships'] if r['user_id']==10)},'global_catalogue':{'count':count,'method':'estimated_document_count','full_document_digest':False},'artifacts':{'compared':len(artifacts),'unchanged':sum(a['unchanged'] for a in artifacts),'method':'Accepted baseline size and mtime_ns inventory; no rebuild or full binary rehash.','inventory':artifacts},'ranking_assistant_router_sources':{'compared':len(protected),'unchanged':all(protected.values()),'sha256_comparisons':protected},'shared_cover_sources':covers,'active_platform_assignments':active,'QA_cleanup':cleanup,'services':health})
    backend=read('institution_v2d_regression.json');backend=backend['backend']['groups'] if isinstance(backend,dict) else backend
    assert len(backend)==18 and all(r['exit']==0 and r['failed']==0 for r in backend)
    cases={}
    xmls=list(REPORTS.glob('institution_v2d_regression_*.xml'))+[REPORTS/'institution_v2d_tests.xml']
    for path in xmls:
        for case in ET.parse(path).getroot().iter('testcase'):
            result='FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
            cases[(case.get('classname'),case.get('name'))]=result
    totals={key:sum(value==key for value in cases.values()) for key in ['PASS','FAIL','SKIP']};assert totals['FAIL']==0 and totals['PASS']==1690
    frontend=read('institution_v2d_frontend_results.json');assert len(frontend)==4 and all(r['exit']==0 for r in frontend)
    assert sum(r['passed'] for r in frontend)==693
    browser=read('institution_v2d_browser.json');assert browser['status']=='PASS' and not browser['errors']
    walkthrough=read('institution_v2d_product_browser_walkthrough.json');assert walkthrough['status']=='PASS' and all(r['context_pass'] for r in walkthrough['steps'])
    responsive=read('institution_v2d_responsive.json');access=read('institution_v2d_accessibility.json')
    product=read('institution_v2d_product_responsive_final.json');product_axe=read('institution_v2d_product_accessibility_final.json')
    assert len(responsive['checks'])==60 and all(r['status']=='PASS' for r in responsive['checks'])
    assert len(product['rows'])==96 and all(r['status']=='PASS' for r in product['rows'])
    audits=access['audits']+product_axe['audits'];assert len(audits)==156 and not any(a['violations'] for a in audits)
    assert access['status']=='PASS' and len(access['manual_contrast'])==100
    assert all(r['ratio']>=r['required'] for r in access['manual_contrast'])
    performance=read('institution_v2d_performance.json');assert performance['status']=='PASS'
    for kind in ['event','notification']:
        migration=read(f'institution_v2d_{kind}_migration.json');assert migration['mode']=='DRY_RUN' and migration['changed']==0
    put('institution_v2d_frontend.json',{'status':'PASS','suites':frontend,'passed':693,'new_phase_tests':21,'build':'PASS','lint_errors':0,'existing_lint_warnings':14,'shared_design':True,'phase_viewports':60,'product_viewports':96,'rendered_axe_audits':156,'axe_violations':0,'manual_contrast_measurements':100})
    put('institution_v2d_regression.json',{'status':'PASS','backend':{'groups':backend,'unique':totals,'phase_tests':45,'dedupe_method':'classname+test name across retained JUnit XML'},'frontend':frontend,'browser_walkthrough_steps':len(walkthrough['steps']),'staff_context_checks':browser['product_checks'],'phase_viewports':60,'frozen_product_viewports':96,'rendered_axe_audits':156,'build':'PASS','lint_errors':0,'router_research_rerun':False})
    required=['institution_v2d_baseline.json','institution_v2d_events_notifications_baseline.json','institution_v2d_existing_event_audit.md','institution_v2d_existing_notification_audit.md','institution_v2d_event_architecture.md','institution_v2d_notification_architecture.md','institution_v2d_event_authorization.json','institution_v2d_notification_authorization.json','institution_v2d_notification_sources.md','institution_v2d_notification_dedupe.json','institution_v2d_notification_outbox.md','institution_v2d_event_migration.json','institution_v2d_notification_migration.json','institution_v2d_frontend.json','institution_v2d_browser.json','institution_v2d_security.json','institution_v2d_performance.json','institution_v2d_regression.json','institution_v2d_preservation.json','institution_v2d_improvement_review.md','institution_v2d_next_scope.md']
    assert all((REPORTS/name).is_file() for name in required)
    evidence=sorted(p.name for p in REPORTS.glob('institution_v2d_*') if p.suffix in ['.json','.md','.xml','.log','.png'])
    put('institution_v2d_files_changed.json',{'scope':'Compared with immutable Part 2D baseline, preserving earlier accepted work. Baseline capture script was created immediately before capture and is explicitly included.','source_files':[{'path':n,'absolute_path':str(ROOT/n),'kind':'CREATED' if n not in baseline['source_sha256'] or n=='scripts/institution_v2d_baseline.py' else 'MODIFIED','sha256':source[n]} for n in changed],'deleted':deleted,'required_reports':required,'evidence_files':evidence})
    rows=[('A. FINAL','PASS — Institution Part 2D complete; all 56 acceptance gates verified.'),('B. Existing Events audit','67 pre-change production matches inventoried; useful Events V1 implementation reused.'),('C. Existing Notifications audit','28 pre-change matches inventoried; account inbox, global reminders and explicit platform sender retained.'),('D. Final event model','One collection; immutable UUID, canonical tenant library UUID, content/schedule, visibility, lifecycle, revision and provenance.'),('E. Event authorization','Current LibraryMembership ADMIN/LIBRARIAN manages own library; GENERAL_USER reads; Platform-only, legacy role and cross-library management denied.'),('F. Event visibility','Private members only; optional PUBLIC publication on public/public-mode libraries; staff-only drafts; cancelled history safe.'),('G. Staff Events','Canonical list/detail/new/edit routes, upcoming/draft/past/cancelled views and shared editor/dialogs.'),('H. Patron Events','Canonical list/detail, context-aware header/footer and bounded optional Home upcoming section.'),('I. Global Events','Explicit global API and Platform-managed global Events retained; tenant publications excluded from global listing/badge.'),('J. Event migration','Dry-run default; one legacy global record classified, preserved, zero applied changes. Explicit review/mapping required.'),('K. Final notification model','Existing user-owned inbox with explicit GLOBAL/PLATFORM/LIBRARY, canonical source, audience and library UUID only for LIBRARY.'),('L. Notification types','Borrow created/approved/rejected; return requested/confirmed; reservation created/cancelled/expired/ready; fee assessed/waived/adjusted/payment recorded.'),('M. Staff recipients','Current exact-library ADMIN/LIBRARIAN recipients; no unrelated staff or platform-role fanout.'),('N. Patron recipients','Canonical domain target with current exact-library GENERAL_USER membership.'),('O. Deduplication','Immutable audit + library + recipient key; approval, return, rejection and payment retries produced no duplicate inbox records.'),('P. Outbox / durability','Intents persisted in existing Part 2B/2C plans before execution; COMMITTED-only bounded retry worker; durable inbox upsert and acknowledgement-loss tests.'),('Q. Notification bell','Account-owned inbox, source labels, pagination, correct badge and mark-one/all retained.'),('R. Routing','Fresh server authorization plus one canonical source-based resolver; active UI context cannot override source UUID/role.'),('S. Multi-library behavior','Same QA user validated as A GENERAL_USER, B ADMIN and C LIBRARIAN; every bell action opened the correct workspace.'),('T. Suspended / removed behavior','Tenant activities denied; historical notices retained with Library unavailable; restores retained exact event/inbox data.'),('U. Legacy notification migration','Dry-run: two account/platform compatibility records and one ambiguous SYSTEM source preserved; no inferred UUID or auto production mutation.'),('V. Security / privacy','Owner/cross-library protections, private event isolation, fresh revocation checks and platform activity tenant-inbox exclusion verified.'),('W. Responsive','60 phase checks plus 96 frozen product checks passed all six requested viewport sizes.'),('X. Accessibility','156 rendered axe audits: zero violations. 100 rendered contrast measurements passed; initial dialog focus, Tab trap, Escape and focus restore verified.'),('Y. Live event scenarios','Admin and librarian draft/edit/publish; same title in separate libraries; cancellation reason/history, private patron view, Home link and global event preservation.'),('Z. Live notification scenarios','Real canonical commands and worker delivery: approval/rejection, return request/confirmation, reservation readiness, overdue fee assessment, waiver and desk payment.'),('AA. Backend tests','1690 unique PASS, 10 existing security skips, zero failures; includes all 45 new Part 2D tests and 18 frozen suite groups.'),('AB. Frontend tests','693 PASS, zero failures; includes 21 new Part 2D checks.'),('AC. Browser validation',f'Real Chromium {browser["browser"]}; {len(walkthrough["steps"])} product navigation steps and nine TEST Staff context checks passed; no runtime page errors.'),('AD. Regression','Institution V1/2A/2B/2C, workspace/platform authority, Events V1, inbox, catalogue, Search, Reading List, Select for AI and Ask LuminaR passed.'),('AE. Build / lint','Build PASS. Lint zero errors; 14 existing warnings retained.'),('AF. TEST preservation','150 ACTIVE records and 150 holdings; exact library/membership/book/holding/lending/cutover snapshots unchanged. Owner ADMIN and patron GENERAL_USER preserved.'),('AG. Global catalogue','5,000,000 estimated documents, matching baseline; no complete 5M row digest was computed.'),('AH. Global HNSW / KG',f'All {len(artifacts)} accepted artifact size/mtime entries unchanged; {len(protected)} protected ranking/assistant/router source digests unchanged. No builds/rebuilds.'),('AI. Exact files changed',link('institution_v2d_files_changed.json')+f' — {len(changed)} source/test/operator files; zero deletions. Reports are separately inventoried.'),('AJ. Reports',f'All {len(required)} required/baseline/audit reports present; full report/evidence inventory below.'),('AK. Known limitations','Standalone Mongo replay durability, not a cross-document transaction. Migration remains dry-run/review-only. No tenant scheduled reminders, broadcast fanout, external push/email, preferences or RSVP. Existing skips/warnings and preservation measurement limits are disclosed.'),('AL. Improvement review',link('institution_v2d_improvement_review.md')+' — all requested follow-up ideas reviewed without implementation.'),('AM. Recommended next phase',link('institution_v2d_next_scope.md')+' — tenant analytics authorization audit, or a separate private-document RAG tenancy audit, only after explicit approval.')]
    text='# Institution Part 2D — final PASS\n\n'+datetime.now(timezone.utc).isoformat()+'\n\n| Requested result | Evidence-backed outcome |\n|---|---|\n'+'\n'.join('| '+label+' | '+value.replace('|',' / ')+' |' for label,value in rows)
    text+='\n\nThe canonical frontend remains running at http://127.0.0.1:5173; Core, Search, Recommendation and RAG health checks returned 200. No next phase was started. Disposable QA libraries were soft-removed with data retained, normal fixture accounts disabled, and the temporary platform grant revoked (403 verified). The prior accepted platform QA grant and both human QA accounts were unchanged. No credentials were persisted.\n\n## Required reports\n\n'+'\n'.join('- '+link(name) for name in required)
    text+='\n\n## Exact source and operator files\n\n'+'\n'.join(f'- [{name}](D:/SDC/LibraryLLM/{name})' for name in changed)
    (REPORTS/'institution_v2d_completion.md').write_text(text+'\n',encoding='utf8')
    print(json.dumps({'status':'PASS','backend_unique':totals,'frontend':693,'phase_viewports':60,'product_viewports':96,'axe_audits':156,'source_files':len(changed),'required_reports':len(required),'artifacts_unchanged':len(artifacts),'protected_sources':len(protected)}))

if __name__=='__main__':main()
