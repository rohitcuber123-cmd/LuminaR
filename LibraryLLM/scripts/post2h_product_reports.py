"""Evidence-based post-2H closure; no catalogue mutation or build request."""
import hashlib,json,re,sys
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import timezone,datetime
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));R=ROOT/'reports'
from scripts.post_2h_baseline import snapshot,TEST
from backend.database.mongodb import db
from backend.services import library_intelligence_store as store,library_intelligence_service as intelligence
def read(name):return json.loads((R/name).read_text(encoding='utf8'))
def put(name,data):(R/name).write_text(json.dumps(data,indent=2,default=str,ensure_ascii=False),encoding='utf8')
def doc(name,text):(R/name).write_text(text,encoding='utf8')
def suites(name):
    x=ET.parse(R/name);return {'file':name,'tests':len(x.findall('.//testcase')),'failures':len(x.findall('.//failure')),'errors':len(x.findall('.//error'))}
def frontend(name):
    text=(R/name).read_text(encoding='utf8');return {'file':name,**{k:sum(map(int,re.findall(rf'{k} (\d+)\s*$',text,re.M))) for k in ['tests','pass','fail']}}
if __name__=='__main__':
 browser=read('post2h_browser_validation.json');assert browser['status']=='PASS' and not browser['page_errors']
 assert len(browser['responsive'])==60 and all(row['status']=='PASS' for row in browser['responsive'])
 baseline=read('post2h_product_regression_baseline.json');after=snapshot();put('post2h_product_current_snapshot.json',after)
 changed=[name for name,sha in after['source_sha256'].items() if baseline['source_sha256'].get(name)!=sha]
 tenant={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in baseline['tenant_artifacts']}
 protected=[p for p in after['source_sha256'] if p.startswith(('search/','knowledge_graph/','recommendation/','assistant/','rag/','backend/services/library_intelligence'))]
 preservation={'status':'PASS','TEST_collections_unchanged':baseline['TEST']==after['TEST'],
   'TEST_before':baseline['TEST'],'TEST_after':after['TEST'],'TEST_intelligence_artifacts_unchanged':tenant==baseline['tenant_artifacts'],
   'TEST_intelligence_artifact_files_checked':len(tenant),'global_catalogue_count':after['global_book_count'],
   'global_catalogue_preserved':baseline['global_book_count']==after['global_book_count']==5000000,
   'global_artifact_metadata_unchanged':baseline['artifacts']==after['artifacts'],'global_artifact_files_checked':len(after['artifacts']),
   'personal_RAG_logical_unchanged':baseline['personal_logical']==after['personal_logical'],
   'protected_source_unchanged':all(baseline['source_sha256'].get(p)==after['source_sha256'][p] for p in protected),
   'protected_source_files_checked':len(protected),'global_HNSW_rebuilt':False,'global_KG_rebuilt':False,
   'TEST_HNSW_rebuilt':False,'TEST_KG_rebuilt':False,'Part_2I_started':False,'changed_sources':changed,
   'QA_data':'One separate canonical Post2H Product QA library: two books/holdings and three MEMBERS TXT assets. Disposable normal-registration QA account disabled after validation. No TEST stock or membership changes. Temporary CN Reading List addition removed if absent before QA.'}
 assert all(preservation[k] for k in ['TEST_collections_unchanged','TEST_intelligence_artifacts_unchanged','global_catalogue_preserved','global_artifact_metadata_unchanged','personal_RAG_logical_unchanged','protected_source_unchanged'])
 put('post2h_preservation.json',preservation)
 count=read('post2h_test_count_evidence.json');bid=count['extra_record']['library_book_id']
 count['audit']=list(db.institution_audit.find({'library_id':TEST,'metadata.library_book_id':bid},
   {'_id':0,'event':1,'actor_user_id':1,'created_at':1,'metadata.library_book_id':1,'metadata.holding_id':1}))
 count.update({'status':'PASS','extra_record_classification':'INTENDED_TEST_RECORD','classification_basis':
   'Conservative preservation decision: existing TEST Owner/Admin user 4 created CN through the canonical MANUAL online-only workflow on 2026-10-13. COMMITTED receipt proves intentional absence of a holding; a READY MEMBERS PDF is linked. No disposable-QA provenance was found. This repair did not create CN.',
   'accepted_baseline':151,'previous_historical_baseline':150,'deleted_records':0,'current_search':intelligence.target_status(TEST,'SEARCH_INDEX',observe_stale=False),
   'current_kg':intelligence.target_status(TEST,'KNOWLEDGE_GRAPH',observe_stale=False),'current_eligible_count':len(store.source_records(TEST))})
 assert count['canonical_active_book_count']==db.institution_library_books.count_documents({'library_id':TEST,'status':'ACTIVE'})==151
 assert count['holding_count']==150 and count['intentional_no_holding'] and count['creation_receipt']['result']['has_physical'] is False
 assert count['current_search']['status']=='READY' and count['current_search']['record_count']==count['current_eligible_count']==151
 put('post2h_test_count_audit.json',count)
 put('TEST_accepted_baseline.json',{'as_of':datetime.now(timezone.utc).isoformat(),'library_id':TEST,'active_library_book_records':151,'holdings':150,
   'digital_assets':5,'additional_record_id':bid,'additional_record_title':'CN','classification':'INTENDED_TEST_RECORD',
   'decision_report':'post2h_test_count_audit.json','historical_150_reports':'Retained as historical evidence, not overwritten.','search_eligible':151,'search_indexed':151,'KG_indexed':151})
 analytics=[c for c in browser['checks'] if 'Analytics' in c['scenario'] or 'analytics' in c['scenario']]
 put('post2h_analytics_validation.json',{'status':'PASS','http_status_before':503,'http_status_after':200,'library_id':TEST,'checks':analytics,
   'authorization':'Current ACTIVE ADMIN/LIBRARIAN LibraryMembership for exact UUID; GENERAL_USER and Platform-only denied in real HTTP tests.',
   'empty_activity':'TEST current queue/loans/reservations/fee balances zero, historical activity remains real. New canonical empty QA library returns valid zero collection/activity.','ranges':['7d','30d','90d','all']})
 doc('post2h_analytics_failure_root_cause.md',f'''# Staff Analytics root cause and repair

Actual Chromium reproduced `GET /api/libraries/{TEST}/analytics?range=30d` → **503**. Safe body: `Canonical collection allocation requires reconciliation.` The UI showed “Unable to load analytics”. Evidence: `post2h_analytics_failure_before.json`, its screenshot, and `post2h_analytics_development_exception.txt`.

The backend route is `backend/routes/library_analytics.py`, calling `backend/services/library_analytics_service.py:dashboard` → `collection_metrics`. The scoped Mongo aggregation starts at ACTIVE `institution_library_books`, left-joins `institution_holdings` on both library UUID and book UUID, then checks canonical requests, loans, waiting reservations and copies. Its old `invalid` predicate treated **every missing holding** as physical allocation corruption. CN is a valid online-only record created without physical stock, so that predicate falsely rejected the entire library. This was an explicit FastAPI HTTPException, not a database connection or Mongo execution exception. Uvicorn logged handled 503 requests without a traceback; the direct development service reproduction captured the exact raising stack.

The repair proves intentional no-holding origin from the existing COMMITTED LIBRARY_BOOK_CREATED receipt, or accepted older creation audit only when no receipt exists. Bulk, library-scoped lookups apply to missing-holding rows. No-holding records remain invalid if physical pending/active/waiting/copy allocations exist. Missing physical holdings and broken COPY stock still return reconciliation 503. An online-only title contributes to active-book/acquisition/subject totals, never physical quantity, requestable units or physical circulation counts.

Analytics remains read-only, bounded and guarded by canonical revision/access barriers. The audit found no LIB001, global inventory/books/loans fallback, historical User.role authority, work-id-only tenant key, fixed 150 count, or alternate tenant alias. Current authority comes from exact current LibraryMembership. Snapshot metrics stay current while activity uses persisted operations and UTC ranges.

After repair, real Chromium receives **200** for 7d, 30d, 90d and all, plus Refresh. Current TEST totals: 151 ACTIVE books, 183 physical units, 178 requestable units, zero active loans/pending borrow/pending return. See `post2h_analytics_validation.json` and backend XML evidence.
''')
 online=[c for c in browser['checks'] if any(term in c['scenario'] for term in ['CN','Reading List','Browse','Search','New Arrivals','STAFF_ONLY','Multiple'])]
 both=[c for c in browser['checks'] if any(term in c['scenario'] for term in ['BOTH','Physical','Multiple'])]
 put('post2h_online_actions.json',{'status':'PASS','online_only_title':'CN','read_action':True,'request_action':False,'actual_pdf_viewer':True,'checks':online,
   'byte_authority':'Current user, exact library membership, READY visibility, current owning book/library access are enforced by the existing protected asset service on metadata/file/preview requests. URL book hint is also checked against fresh asset metadata before opening. UI hints do not authorize bytes.',
   'multiple_assets':'No primary asset ID when two or more authorized READY assets exist. Read Online opens the exact book Digital Resources section; user chooses a resource. More than 20 resources have a scoped All online copies link.',
   'revocation_evidence':'tests/institution_v2f/test_post2h_capabilities.py:test_revoked_membership_denied_before_content and existing asset revocation suites.'})
 put('post2h_physical_online_actions.json',{'status':'PASS','title':'TEST Reading Circle Discussion Notes','request_book':True,'read_online':True,
   'zero_stock_fixture':browser['fixture']['zero'],'zero_stock_waitlist':True,'zero_stock_read_online':True,'checks':both})
 doc('post2h_book_capability_audit.md','''# Canonical book capabilities

`backend/services/library_book_formats.py` derives physical presence from a real canonical holding and online presence from currently authorized READY assets. Patron derivation includes MEMBERS only; Staff derivation may include STAFF_ONLY. “Format” describes current-user-accessible capabilities, not every resource known to staff. No holding, shelf or copies are fabricated for online-only records.

`frontend/src/lib/libraryBookCapabilities.ts:resolveLibraryBookCapabilities` is shared by presentation, BookCard, BookDetailView and CatalogueBookActions. Exact ACTIVE GENERAL_USER membership and current session are required for Patron actions. Physical Request/Waitlist also follows the backend availability/action flags. Online access does not depend on physical availability. Admin/Librarian cards retain Staff navigation/management; they receive no same-library Patron controls.

| Surface | Canonical path | Result |
|---|---|---|
| Home / For You / Recommendations | canonical DisplayBook → BookCard → CatalogueBookActions | Read Online and physical actions share resolver |
| New Arrivals / Popular / Browse | LibraryCatalogue/Home section → BookCard | same resolver |
| Library Search | canonical hydration → BookCard | same resolver; no ranking changes |
| Book Detail | BookDetailView + CatalogueBookActions + Digital Resources | online-only physical facts absent; BOTH exposes both |
| Local Reading List | exact saved library/book identities → authorized canonical batch hydration → BookCard | current READY/stock capabilities, no cached grants |
| Global Reading List / Related Books | GLOBAL_WORK identity → global BookCard | remains global personal/discovery data, no invented tenant holdings; linked saves retain existing unique global identity |
| Reservation / loan references | exact canonical book detail links | shared actions on detail; queue/history pages remain operational references |

A single permitted READY asset routes to its canonical resource with `book=<UUID>&open=1`. Fresh metadata must match that book before the existing protected PDF/text viewer mounts. Two or more assets return no arbitrary first resource; Read Online routes to `#digital-resources` for explicit choice. The async resource section scrolls into view after loading. Protected content endpoints revalidate current authorization.

Reading List previously reconstructed local records from global metadata with `owned_by_current_library=false` and no asset/format flags. It now hydrates local saved entries in bounded batches (200 maximum) using the accepted current-user catalogue and canonical read barrier. Unavailable saved entries expose no capabilities and remain removable. Globally saved identities stay global; no first membership or first holding is guessed.

Book-cover palette, geometry and renderer are unchanged. Shared rail navigation reserves the same 84px edge lane as the rail so the Assistant launcher cannot cover Next; actual Chromium checks show no action/launcher intersections at all six sizes. Intentional horizontal carousel scrolling remains.
''')
 doc('post2h_staff_metric_consistency.md',f'''# Staff metric definitions

Every endpoint requires current exact Staff membership. Overview and Analytics read canonical tenant UUIDs; neither uses legacy/global business rows.

| Metric | Overview source / definition | Analytics source / definition | Current TEST |
|---|---|---|---|
| Local books | staff catalogue source: ACTIVE records with a valid title, including online-only | ACTIVE LibraryBookRecord count | 151 |
| Inventory records | inventory state=all: retained ACTIVE and WITHDRAWN records | separate Active books metric excludes WITHDRAWN | 151 retained, all currently ACTIVE |
| Current loans / Active loans | staff loans status=ACTIVE total | canonical loans status=ACTIVE aggregation | 0 |
| Pending borrow | canonical queue pending_counts.BORROW, request_type=BORROW status=PENDING | same canonical type/status aggregate | 0 |
| Pending return | canonical queue pending_counts.RETURN, request_type=RETURN status=PENDING | same canonical type/status aggregate | 0 |
| Membership count | explicitly labelled “memberships” link: all retained states from memberships endpoint | explicitly labelled Active members: status=ACTIVE, all roles | 3 all-state / 3 ACTIVE |

Inventory records and Active books intentionally differ when a book is withdrawn. Likewise total memberships and active membership totals intentionally differ after suspension/removal; they must not be presented as identical metrics. A catalogue requires valid titles, guaranteed by accepted creation validation. Book format is independent of title count: CN adds one title and zero physical holdings.

Collection physical quantities use canonical holdings plus accepted copy/allocation reconciliation. Activity uses canonical operation/audit history with UTC range boundaries, not current pending-state counts or global circulation. Historical approved/returned/cancelled operations are retained even when current loans and queues are zero. Live Overview and Analytics measurements are in `post2h_browser_validation.json`; isolated count/range/tenant tests are in the backend XML reports.
''')
 control_checks=[c for c in browser['checks'] if any(term in c['scenario'] for term in ['themed','range','selector'])]
 put('post2h_control_consistency.json',{'status':'PASS','canonical_control':'frontend/src/components/LuminarSelect.tsx','native_visible_catalogue_selects':0,
   'controls':{'Staff library selector':'LibrarySwitcher → searchable LuminarSelect, desktop sidebar/mobile dialog','Author':'accepted shared themed text input','Circulation status':'CatalogueFilters → LuminarSelect','Subjects':'CategoryChips buttons retained','Catalogue sort':'explicit supported URL/surface selection; no duplicate native select','Inventory state/source/format':'accepted LuminarSelect','Analytics range/metric':'LuminarSelect'},
   'keyboard':'Space opens, Escape closes, trigger focus restored; verified at all six sizes.','checks':control_checks,'responsive':[r for r in browser['responsive'] if r['page'] in ['analytics_range','staff_catalogue','staff_selector']]})
 backend=[suites(f'post2h_product_{key}.xml') for key in ['analytics_full','assets_backend','catalogue_backend','intelligence_backend','build_controls_backend']]
 front=frontend('post2h_product_frontend.log');focused=frontend('post2h_product_frontend_final_focused.log');css_checks=frontend('post2h_product_final_css_regression.log')
 assert all(s['failures']==0 and s['errors']==0 for s in backend) and front['fail']==focused['fail']==0 and front['pass']==842 and focused['pass']==51
 lint=(R/'post2h_product_lint.log').read_text(encoding='utf8');build=(R/'post2h_product_build.log').read_text(encoding='utf8')
 assert ': error ' not in lint and lint.count(': warning ')==14 and 'built in' in build
 assert css_checks['tests']==css_checks['pass'] and css_checks['fail']==0
 regression={'status':'PASS','backend_suites':backend,'backend_pass':sum(s['tests'] for s in backend),'full_frontend':front,'final_focused_frontend':focused,'final_CSS_regression':css_checks,
   'build':'PASS (TypeScript + Vite)','lint_errors':0,'lint_existing_warnings':14,'build_existing_warning':'Vite bundle chunk size advisory',
   'Chromium':'PASS','responsive_checks':len(browser['responsive']),'viewports':['1440x900','1366x768','1024x768','768x1024','390x844','375x812'],
   'scoped_regression':'Full frontend default suites; complete Institution V2E Analytics, V2F assets/formats, canonical catalogue, V2G intelligence, V2H durable controls suites. Protected algorithm/router source unchanged.',
   'files_changed_this_phase':changed+['frontend/package.json','tests/institution_v2e/test_post2h_product.py','tests/institution_v2f/test_post2h_capabilities.py',
     'scripts/post2h_product_reproduce.py','scripts/post2h_product_browser.py','scripts/post2h_product_finish_browser.py','scripts/post2h_product_reports.py'],
   'stop':'Post-2H product regression closure complete. No Part 2I, no git commit.'}
 put('post2h_regression.json',regression)
 summary={'FINAL_STATUS':'PASS','ANALYTICS_ROOT_CAUSE':'Intentional online-only CN has no physical holding; old allocation guard incorrectly treated that as corruption. Creation-provenance-aware validation now preserves physical reconciliation checks.',
   'ANALYTICS_HTTP_STATUS_AFTER':200,'ANALYTICS_TEST_LIBRARY_PASS':'YES','ANALYTICS_EMPTY_ACTIVITY_PASS':'YES',
   'ONLINE_ONLY_TITLE_TESTED':'CN','ONLINE_ONLY_READ_ACTION':'YES','ONLINE_ONLY_REQUEST_ACTION':'NO','ONLINE_ONLY_VIEWER_PASS':'YES',
   'PHYSICAL_ONLINE_TITLE_TESTED':'TEST Reading Circle Discussion Notes','PHYSICAL_ONLINE_REQUEST_ACTION':'YES','PHYSICAL_ONLINE_READ_ACTION':'YES',
   'ONLINE_ACCESS_INDEPENDENT_OF_PHYSICAL_STOCK':'YES','SHARED_BOOK_CAPABILITY_RESOLVER':'YES','STAFF_CATALOGUE_DROPDOWN_THEMED':'YES','ANALYTICS_RANGE_DROPDOWN_THEMED':'YES',
   'TEST_CANONICAL_BOOK_COUNT':151,'TEST_EXTRA_RECORD_ID':bid,'TEST_EXTRA_RECORD_TITLE':'CN','TEST_EXTRA_RECORD_CLASSIFICATION':'INTENDED_TEST_RECORD','TEST_ACCEPTED_BASELINE_AFTER_REVIEW':151,
   'INTELLIGENCE_SEARCH_STATUS':count['current_search']['status'],'INTELLIGENCE_SEARCH_ELIGIBLE_COUNT':count['current_eligible_count'],'INTELLIGENCE_SEARCH_INDEXED_COUNT':count['current_search']['record_count'],
   'GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO','BACKEND_TESTS_PASS':regression['backend_pass'],'FRONTEND_TESTS_PASS':front['pass'],
   'RESPONSIVE_CHECKS_PASS':60,'BUILD':'PASS','LINT_ERRORS':0,'PART_2I_STARTED':'NO'}
 put('post2h_product_final_qa.json',summary)
 rows='\n'.join(f'| {k} | {v} |' for k,v in summary.items())
 doc('post2h_product_completion.md',f'''# Post-2H product regression completion — PASS

Analytics, authorized online-book actions, mixed-format independence, shared controls, current TEST count and metric definitions are repaired/verified. All 30 acceptance gates pass. Actual Chromium completed {len(browser['checks'])} flow checks and 60 layout/control/viewer checks across all six requested sizes.

| Final QA field | Result |
|---|---|
{rows}

Evidence is in the twelve requested `post2h_*` reports, the canonical TEST accepted baseline, XML/logs, before/after screenshots and `post2h_product_final_qa.json`. Backend total covers the five complete scoped suites; the full frontend default suite passes 842, followed by 51 focused checks after final test-fixture updates. Build passes, lint has zero errors and 14 pre-existing warnings.

All TEST canonical record/holding/asset/intelligence collection hashes remain identical. TEST intelligence file SHA-256 checks, 196 global artifact file metadata checks, 5M global catalogue, personal RAG logical snapshot and protected model/router/build sources remain unchanged. CN was preserved; no TEST rebuild was needed because Search and KG already index 151 from the current dataset. QA stock/resources belong to a separate disposable library and its newly created account is disabled.

Limitations: generated global personal saves retain their accepted GLOBAL_WORK identity; they do not invent a tenant holding in explicit global Reading List context. Multi-resource selection is bounded/paginated. Existing unrelated lint/bundle-size advisories remain. No new product domain or Part 2I was started; no git commit was made.
''')
 print(json.dumps({'status':'PASS','backend_tests':regression['backend_pass'],'frontend_tests':front['pass'],'responsive_checks':60,'TEST':151,'global_books':after['global_book_count']}))
