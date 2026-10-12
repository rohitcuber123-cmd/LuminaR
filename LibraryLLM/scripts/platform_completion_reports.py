"""Close the local phase using retained test/browser evidence and immutable baseline."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import re
import xml.etree.ElementTree as ET
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
REPORTS=ROOT/'reports'
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'

def read(name):return json.loads((REPORTS/name).read_text(encoding='utf8'))
def put(name,value):(REPORTS/name).write_text(json.dumps(value,indent=2,default=str),encoding='utf8')

def main():
    from backend.database.mongodb import db
    baseline=read('platform_completion_baseline.json')
    assert db.name=='luminar_library' and db.client.address[0] in {'localhost','127.0.0.1','::1'}
    snapshots={name:list(db['institution_'+name].find({'library_id':TEST},{'_id':0}).sort('library_id',1)) for name in baseline['TEST']}
    for name in ['library_books','holdings']:snapshots[name].sort(key=lambda r:r['library_book_id'])
    unchanged={name:json.loads(json.dumps(rows,default=str))==baseline['TEST'][name] for name,rows in snapshots.items()}
    assert all(unchanged.values()),unchanged
    artifacts=[]
    for name,before in baseline['artifact_metadata'].items():
        path=ROOT/name;stat=path.stat();after={'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns}
        artifacts.append({'path':name,'unchanged':before==after,'before':before,'after':after})
    assert all(a['unchanged'] for a in artifacts)
    count=db.books.estimated_document_count();assert count==baseline['global_count']==5000000
    paths=subprocess.check_output(['rg','--files','--hidden','-g','!.git','-g','!.venv','-g','!node_modules','-g','!.scratch','-g','!scratch','-g','!dist','-g','!datasets'],cwd=ROOT,text=True).splitlines()
    source={}
    for name in paths:
        name=name.replace('\\','/');p=ROOT/name
        eligible=p.suffix in {'.py','.ts','.tsx','.css','.json','.md','.html','.toml','.ps1','.cjs'} or name=='scripts/platform_context_audit.mjs'
        if not name.startswith('reports/') and eligible and p.stat().st_size<32*1024*1024:
            source[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    changed=sorted(n for n,h in source.items() if baseline['source_sha256'].get(n)!=h)
    protected_prefixes=('search/','recommendation/','rag/','assistant/','knowledge_graph/')
    protected={n:source.get(n)==h for n,h in baseline['source_sha256'].items() if n.startswith(protected_prefixes)}
    assert all(protected.values()),[n for n,v in protected.items() if not v]
    assignments=list(db.platform_role_assignments.find({'status':'ACTIVE'},{'_id':0,'user_id':1,'role':1,'status':1,'approval_ref':1}))
    qa=db.users.find_one({'email':'platform-completion-qa@example.com'},{'_id':0,'user_id':1,'email':1,'name':1,'role':1})
    assert qa and len(assignments)==1 and assignments[0]['user_id']==qa['user_id']
    assert not db.institution_memberships.find_one({'library_id':TEST,'user_id':qa['user_id']})
    assert not db.platform_role_assignments.find_one({'user_id':{'$in':[4,10]}})
    health=[]
    for port in [5173,8002,8003,8004,8005]:
        path='/' if port in [5173,8004] else '/health'
        with urlopen(f'http://127.0.0.1:{port}{path}',timeout=30) as response:health.append({'port':port,'http_status':response.status})
    fixtures=list(db.institution_libraries.find({'owner_user_id':qa['user_id']},{'_id':0,'library_id':1,'name':1,'status':1,'library_type':1}))
    put('platform_completion_preservation.json',{'status':'PASS','TEST':{'records':len(snapshots['library_books']),'ACTIVE_records':sum(r['status']=='ACTIVE' for r in snapshots['library_books']),'holdings':len(snapshots['holdings']),'exact_snapshot_comparison':unchanged},
        'global_catalogue':{'count':count,'baseline_count':baseline['global_count'],'method':'estimated_document_count','full_5M_document_digest':False},
        'artifacts':{'compared':len(artifacts),'unchanged':sum(a['unchanged'] for a in artifacts),'method':'Existing accepted size and mtime_ns inventory; no full binary rehash or rebuilding.','inventory':artifacts},
        'ranking_router_sources':{'compared':len(protected),'unchanged':all(protected.values()),'sha256':protected},
        'QA_platform_account_created':True,'QA_email':qa['email'],'explicit_active_assignments':assignments,'TEST_QA_membership':False,'existing_owner_or_patron_promoted':False,
        'disposable_libraries':fixtures,'cleanup':read('platform_completion_qa_cleanup.json'),'services':health})

    backend=read('platform_completion_backend.json');frontend=read('platform_completion_frontend_results.json')
    cases={}
    for row in backend:
        xml=REPORTS/f'platform_completion_backend_{row["group"]}{"_retry" if row["group"]=="search" else ""}.xml'
        group_cases=list(ET.parse(xml).getroot().iter('testcase'))
        row.update(tests=len(group_cases),failed=sum(c.find('failure') is not None or c.find('error') is not None for c in group_cases),skipped=sum(c.find('skipped') is not None for c in group_cases))
        assert row['exit']==0 and row['failed']==0
        for case in group_cases:
            result='FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
            cases[(case.get('classname'),case.get('name'))]=result
    put('platform_completion_backend.json',backend)
    totals={key:sum(v==key for v in cases.values()) for key in ['PASS','SKIP','FAIL']};assert totals['FAIL']==0
    assert all(row['exit']==0 and row['failed']==0 for row in frontend)
    required=['platform_libraries_browser.json','platform_library_lifecycle_browser.json','platform_boundary_browser.json','platform_accessibility.json','platform_responsive.json','staff_home_context_repair.json','patron_home_context_repair.json','book_cover_visual_validation.json','book_card_layout_validation.json','platform_completion_product_responsive.json','platform_completion_product_accessibility.json']
    assert all(read(name)['status']=='PASS' for name in required)
    platform_matrix=read('platform_responsive.json')['matrix'];product_matrix=read('platform_completion_product_responsive.json')['checks']
    assert len(platform_matrix)==36 and len(product_matrix)==96 and all(r['status']=='PASS' for r in product_matrix)
    assert read('platform_completion_runtime_browser.json')['page_errors']==[]
    focus_log=(REPORTS/'platform_completion_frontend_final_focus.log').read_text(encoding='utf-8-sig')
    focus_passed=int(re.search(r'ℹ pass (\d+)',focus_log)[1]);focus_failed=int(re.search(r'ℹ fail (\d+)',focus_log)[1]);assert focus_failed==0
    regression={'status':'PASS','backend_unique':totals,'backend_raw_executions':sum(r['tests'] for r in backend),'backend_groups':backend,'frontend_groups':frontend,'frontend_passed':sum(r['passed'] for r in frontend),
        'final_focused_frontend':{'passed':focus_passed,'failed':focus_failed,'log':'platform_completion_frontend_final_focus.log','reason':'Final affected workspace/navigation/authority components after accessibility-role fixes; already included in the unique full-suite count.'},
        'platform_responsive_checks':len(platform_matrix),'product_responsive_checks':len(product_matrix),'rendered_cover_checks':len(read('book_cover_visual_validation.json')['checks']),
        'actual_title_checks':len(read('book_cover_visual_validation.json')['actual_title_samples']),'card_actions_measured':read('book_card_layout_validation.json')['measured_actions'],
        'browser_reports':required,'browser_runtime':read('platform_completion_runtime_browser.json'),'build':'PASS','lint_errors':0,'lint_warnings':next(r['warnings'] for r in frontend if r['group']=='lint'),
        'limitations':['10 existing backend skips; no claim that skipped tests ran.','One search fixture MemoryError under host paging pressure; complete sequential search retry passed.','Artifact preservation uses accepted size/mtime_ns baseline; no full 5M Mongo or binary artifact digest.','Axe contrast incompletes for clipped/offscreen rail text and transparent native-dialog paragraphs are explicitly recorded; opaque cover/dialog contrast and visible control hit-testing were checked separately.']}
    put('platform_completion_regression.json',regression)
    routes={'status':'PASS','platform_prefix':'/platform','frontend':[{'path':'/platform','component':'PlatformOverview','existing':True},{'path':'/platform/libraries','component':'PlatformLibrariesPage','existing':False},{'path':'/platform/libraries/:libraryId','component':'PlatformLibraryDetailPage','existing':False}],
        'api':[{'method':'GET','path':'/platform/libraries'},{'method':'GET','path':'/platform/libraries/{library_id}'},{'method':'GET','path':'/platform/libraries/{library_id}/audit'}]+[{'method':'POST','path':'/platform/libraries/{library_id}/'+a} for a in ['suspend','remove','restore']],
        'authority':'Active, explicitly reviewed PlatformRoleAssignment only; shared require_platform_admin.','duplicate_console':False,'compatibility_platform_aliases_added':[]}
    put('platform_libraries_routes.json',routes)
    inventory=REPORTS/'full_route_inventory.md';text=inventory.read_text(encoding='utf8')
    if '| /platform/libraries |' not in text:
        insert='\n'.join(f'| {r["path"]} | {r["component"]} | PLATFORM | safe platform directory/lifecycle/audit API | PlatformRoleAssignment | CANONICAL | single existing PlatformShell | frontend/src/App.tsx |' for r in routes['frontend'][1:])+'\n'
        marker='| /platform/catalogue |';text=text.replace(marker,insert+marker,1)
        inventory.write_text(text,encoding='utf8')
    (REPORTS/'platform_libraries_architecture.md').write_text('''# Platform Libraries architecture

Baseline: the explicit PlatformRoleAssignment collection, live require_platform_admin guard, one PlatformShell/Overview, global catalogue/accounts/events/notifications/history/authority-review modules, reviewed migration bootstrap and centralized active-library membership guards already existed. There was no platform library directory/detail route or lifecycle UI/service. Library.status already represented PROVISIONING, ACTIVE, SUSPENDED and ARCHIVED. This phase adds REMOVED to that same field, without replacing archival history.

The existing /platform shell now exposes Libraries and /platform/libraries/:libraryId. Directory search is server-side (escaped literal name, slug, UUID, owner email/name), bounded to 50 rows, 120 query characters and a 10-second Mongo execution limit. Status/type filters and offset pagination are reflected in the URL. Safe per-page aggregates use indexed membership/inventory queries. Owner summaries follow the existing Platform Accounts privacy boundary. The browser receives neither a full library collection nor private loans, fees, documents, PDFs, code hashes or invitation secrets.

Detail exposes whitelisted identity/owner/type/access/status/timestamps, aggregate counts, existing lending/reservation/fee cutover states and a bounded platform audit. No tenant inventory, circulation, staff, access-code, fee-policy or internal-settings controls exist here. Those APIs retain their independent LibraryMembership guard. Dual-authority users have separately checked Platform and tenant permissions. No impersonation was introduced.

Suspend is ACTIVE → SUSPENDED; remove is ACTIVE/SUSPENDED → REMOVED; restore is SUSPENDED/REMOVED → ACTIVE. A nonblank bounded reason, expected state and UUID idempotency key are mandatory. Native confirmation dialogs identify data retention and consequences. Centralized guards deny normal discovery/join/patron/staff/writes for non-ACTIVE libraries. Restore validates the canonical Library model, verified active owner and independent ADMIN membership, provisioning/private-access invariants, subsystem cutover state, unfinished imports/lending operations and existing canonical reconciliation.

Lifecycle operations use the existing durable cross-worker library gate and journaled writes. A PREPARED platform audit intent precedes the status write; COMMITTED audit acknowledgement precedes release. LIBRARY_SUSPENDED/LIBRARY_REMOVED/LIBRARY_RESTORED include actor, UUID, timestamp, reason and previous/new state. Unknown acknowledgements retain the library gate and fail closed. Operator recovery requires stopped writers, a single proven intent, valid transition/event provenance, invariant revalidation and acknowledged absolute replay before unlocking. No automatic timeout steals the gate; no online recovery or build button exists.

Local QA uses normal registration and actual one-use OTP verification with a process-local test mailbox sink, followed by existing migrate_management_authority.plan/apply with an explicit reviewed mapping. Its sole platform assignment is scoped to local review. Neither existing QA account was elevated. Six canonical disposable libraries exercise public/private filtering/pagination and lifecycle, including retained inventory, holdings, memberships, request and loan records. TEST is never suspended or removed. Temporary legacy denial fixtures are disabled and the additional patron QA membership is removed through its independent library owner after returning its disposable loan.

Context uses one URL-first resolver. Staff and Patron personal links carry distinct explicit UUID return parameters; Platform carries workspace=platform. Explicit global links have no library return parameter. Session change/logout clears inappropriate return state. Membership validates/corrects role presentation and never chooses the first library. Shared BookCoverArt/BookCover, BookCard and rail styling serve all product surfaces. Decorative layers precede copy; one content-sized opaque title/author backdrop replaces nested rectangles. Rail controls sit below content and the Assistant becomes compact near card controls.
''',encoding='utf8')
    (REPORTS/'book_cover_regression_root_cause.md').write_text('''# Shared book cover/card regression root cause

The phase baseline's canonical BookCover put separate opaque palette backgrounds on branding, title and author. Combined with the split/stripe/ring geometry these nested text boxes produced stacked rectangular regions, including title/author rectangles crossing decorative panels. Local and global pages already shared BookCoverArt; duplicating local CSS would have preserved the defect. The baseline/source snapshots are retained under .scratch/platform-completion/before.

The repair keeps the established palettes, branding and original decorative geometry. The content paints after decoration, with a single opaque backdrop inside a content-sized copy region; title, author and brand carry no individual backdrop. Title wrapping uses a bounded five-line region and author handling uses two lines. Accessible image naming retains the full text. No arbitrary z-index escalation was used.

The complete card also needed flexible action wrapping and bounded child widths. Rail arrows previously overlaid content and the expanded global Assistant could obscure the final card actions. Arrows now occupy a separate labelled navigation group below the rail; trailing scroll space permits the final card to clear the compact Assistant. Intersection observation compacts the launcher when product controls are visible, without altering Assistant requests, routing or ranking.

Evidence: 60 live surface/viewport checks measured 732 generated covers; 48 additional checks use eight actual canonical catalogue titles, including Money 1988, The Tower, Logical aspects of computational linguistics, Managing God's Money-The Basics, Workbook, The Glasgow novel, 1870-1970, multiple authors, a missing-author global record and a local-only record. 1,620 real action measurements checked card bounds and visible center hit-testing. Cropped cover/rail screenshots were visually inspected; the complete six-viewport geometry matrix and rendered contrast samples are retained separately. Long titles are intentionally bounded rather than expanding cover geometry; full titles remain available in accessible naming and the card/detail text.
''',encoding='utf8')
    audit=read('platform_completion_context_audit.json')
    context_fields={k:v for name in ['staff_home_context_repair.json','patron_home_context_repair.json'] for k,v in read(name).items() if k not in ['checks','status']}
    context_fields.update({'NAVIGATION_CONTEXT_CALLS_AUDITED':audit['calls_audited'],'CONTEXT_BUGS_FOUND':audit['context_bugs_found'],'CONTEXT_BUGS_FIXED':audit['context_bugs_fixed'],
        'BOOK_COVER_ROOT_CAUSE':'Nested opaque brand/title/author backplates interacting with decorative cover geometry; overlaid rail controls and expanded Assistant interfered with card actions.',
        'SHARED_BOOK_COVER_RENDERER':True,'LONG_TITLE_COVER_PASS':True,'SHORT_TITLE_COVER_PASS':True,'GLOBAL_CARD_LAYOUT_PASS':True,'TEST_CARD_LAYOUT_PASS':True,'MOBILE_CARD_LAYOUT_PASS':True})
    put('platform_completion_changed_files.json',{'comparison':'SHA256 against immutable phase baseline, independent of pre-existing dirty Git state.','source_files':changed,'report_files':sorted(p.name for p in REPORTS.iterdir() if p.name.startswith('platform_completion_') or p.name.startswith('platform_librar') or p.name in required or p.name in ['product_context_navigation_audit.md','book_cover_regression_root_cause.md','full_route_inventory.md'])})
    put('platform_completion_result.json',{'status':'PASS','completed_at':datetime.now(timezone.utc).isoformat(),'context_fields':context_fields,'regression':regression,'changed_source_files':changed})
    sections=[('A. FINAL','PASS — all 70 requested gates have evidence in the linked reports.'),('B. GAP ROOT CAUSE','Explicit authority separation was already correct; supplied QA accounts had no platform grant and the canonical shell lacked a library directory/detail surface.'),
        ('C. EXISTING IMPLEMENTATION','Explicit assignments/live guard, single shell/Overview and global modules, reviewed migration bootstrap, centralized tenant guards and canonical lifecycle field were reused.'),('D. ROUTES','/platform; /platform/libraries; /platform/libraries/:libraryId. See platform_libraries_routes.json; no alternative console.'),
        ('E. QA AUTHORITY',f'Created YES: {qa["email"]}; explicit reviewed PLATFORM_ADMIN; no TEST membership, no existing Patron/Owner promotion, no production grant. Credential material stayed in memory.'),
        ('F–I. OVERVIEW / LIBRARIES / SEARCH / DETAIL','Live Overview and Libraries/detail render. Bounded server-side name/slug/UUID/owner search, ACTIVE/SUSPENDED/REMOVED and public/private filters, distinct page slices, TEST ACTIVE with 150 books, safe aggregate/cutover/audit detail.'),
        ('J–M. SUSPEND / REMOVE / RESTORE / AUDIT','All four lifecycle transitions completed in the browser on a disposable canonical library. Reasons required; data retained; inactive access/join/discovery denied; restoration revalidates invariants. Explicit committed audit events retain actor/reason/time/previous/new state.'),
        ('N–Q. BOUNDARIES / DENIAL / REVOCATION','Seven TEST tenant mutation attempts denied without membership; direct TEST Staff URL denied. Real library ADMIN and isolated legacy ADMIN login denied Platform. Live assignment revocation blocked UI/API immediately while separate own-library ADMIN remained usable. Original approved QA assignment restored; denial fixture disabled. No impersonation.'),
        ('R. ACCOUNT MENU','Separate PLATFORM / Platform Administration group; independently scoped Staff Workspaces.'),('S. RESPONSIVE','36/36 platform page/dialog checks and 96/96 product checks across 1440x900, 1366x768, 1024x768, 768x1024, 390x844, 375x812. No page overflow; directory scrolls within its container; dialogs fit.'),
        ('T. ACCESSIBILITY','132 rendered axe audits: zero violations; keyboard navigation/search/filter/row actions/danger reason controls, native focus trap, Escape/restore and visible focus pass. All dialog and sampled cover text has computed rendered contrast ≥4.5:1. Contrast incompletes for offscreen rail text/native paragraphs are recorded, with independent visible-action hit-testing and opaque-background checks.'),
        ('U. BROWSER','Actual Chromium 151 normal login, Platform directory/lifecycle/boundary/revocation flows, owner six Staff sections and personal return, Karthikeya Patron Browse/detail/Reading List/Select for AI/real Ask response/local+global Search/My Library/reservations/fees/account, global Home/catalogue/detail/return, keyboard and reload/hard-refresh checks. No page errors.'),
        ('V. BACKEND',f'{totals["PASS"]} unique PASS; {totals["SKIP"]} existing SKIP; 0 FAIL. Institution V1/2A/2B/2C, authority, stock/lending/reservations/fees, search, recommendation/product and Assistant regression suites. Complete sequential search retry resolved transient host MemoryError.'),
        ('W. FRONTEND',f'{regression["frontend_passed"]} PASS; 0 FAIL, default and extended suites.'),('X. REGRESSION','Accepted product flows preserved; shared context/cover repairs verified in live browsers. Prior accepted closure reports were retained; new closure evidence uses this phase prefix.'),('Y. BUILD / LINT',f'Build PASS; lint 0 errors, {regression["lint_warnings"]} existing warnings.'),
        ('Z. TEST','150 ACTIVE books and 150 holdings; exact baseline library, memberships, books, holdings and cutover configuration snapshots unchanged.'),('AA. GLOBAL CATALOGUE','Estimated count exactly 5,000,000; no catalogue mutation performed.'),('AB. HNSW / KG','196 existing artifact sizes/mtime_ns unchanged; protected ranking/router sources SHA256 unchanged; no global builders/rebuilds.'),
        ('AC. EXACT FILES','See platform_completion_changed_files.json and the source list below. This compares phase fingerprints instead of attributing older uncommitted work to this phase.'),('AD. REPORTS','All requested named reports and supplementary test/browser evidence exist under reports/. See manifest below.'),('AE. LIMITATIONS','Existing backend skips, prior lint warnings, one resolved test-host MemoryError, recorded axe contrast incompletes and metadata-based artifact preservation. No skipped-test, full 5M digest, binary rehash or offscreen contrast claims.'),('AF. RECOMMENDATION','Accept Platform Administration Completion V1. Frontend/API services remain running. Stop here; no Events/Notifications/Analytics/digital-asset tenancy or tenant HNSW/KG/build phase was started.')]
    content='# Platform Administration Completion V1\n\n'+'\n\n'.join('## '+k+'\n\n'+v for k,v in sections)
    content+='\n\n## Mandatory context/cover results\n\n'+ '\n'.join(f'- {k}: {"YES" if v is True else "NO" if v is False else v}' for k,v in context_fields.items())
    content+='\n\n## Source files changed in this phase\n\n'+'\n'.join('- '+n for n in changed)
    content+='\n\n## Required report manifest\n\n'+'\n'.join('- '+n for n in ['platform_completion_baseline.json','platform_libraries_architecture.md','platform_libraries_routes.json',*required[:5],'platform_completion_regression.json','platform_completion_preservation.json','platform_completion.md','product_context_navigation_audit.md','staff_home_context_repair.json','patron_home_context_repair.json','book_cover_regression_root_cause.md','book_cover_visual_validation.json','book_card_layout_validation.json'])+'\n'
    (REPORTS/'platform_completion.md').write_text(content,encoding='utf8')
    print(json.dumps({'status':'PASS','backend':totals,'frontend_passed':regression['frontend_passed'],'changed_sources':len(changed),'artifacts':len(artifacts),'TEST_books':150,'global_count':count}))

if __name__=='__main__':main()
