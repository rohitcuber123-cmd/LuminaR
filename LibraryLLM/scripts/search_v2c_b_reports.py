"""Observed V2C-B stop-condition handoff. Never turns a failed gate into PASS."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,xml.etree.ElementTree as ET
from backend.database.mongodb import db

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
def read(name):return json.loads((R/name).read_text(encoding='utf-8-sig'))
def write(name,data):
    path=R/('search_v2c_b_'+name)
    path.write_text(data if isinstance(data,str) else json.dumps(data,indent=2,default=str),encoding='utf8')
def xml(name):
    path=R/f'search_v2c_b_{name}.xml';root=ET.parse(path).getroot();suite=root.find('testsuite')
    if suite is None:suite=root
    cases=list(root.iter('testcase'))
    return {'report':str(path),'tests':int(suite.get('tests',0)),'failures':int(suite.get('failures',0)),
            'errors':int(suite.get('errors',0)),'skipped':int(suite.get('skipped',0)),
            'failed_cases':[c.get('name') for c in cases if c.find('failure') is not None],
            'cases':[c.get('name') for c in cases]}
baseline=read('search_v2c_b_baseline.json');live=read('search_v2c_b_live_first_measurement.json')
stop=read('search_v2c_b_stop_condition_observed.json');browser=read('search_v2c_b_browser_observations.json')
responsive=read('search_v2c_b_responsive_observations.json');fixture=read('search_v2c_b_fixture.json')
suites={name:xml(name) for name in ['gate_planner','gate_session','regression_planner','regression_sessions','interactions_test','interactions_final','tenant_full','catalogue_regression','retrieval_regression','stop_condition']}
now=datetime.now(timezone.utc).isoformat()
front=(R/'search_v2c_b_frontend_test.log').read_text(encoding='utf-8-sig')
front_count=sum(map(int,re.findall(r'ℹ tests (\d+)',front)))
assert front_count==900 and not any(int(n) for n in re.findall(r'ℹ fail (\d+)',front))
assert stop['forged_choice_http_status']==404 and not stop['accepted_context_unchanged']
critical={'status':'FAIL','stop_condition':stop,'reproducer_command':r'.venv\Scripts\python.exe -m pytest tests/institution_v2g/test_query_v2c_b_stop_condition.py -q --junitxml=reports/search_v2c_b_stop_condition.xml',
          'evidence':['reports/search_v2c_b_stop_condition_observed.json','reports/search_v2c_b_stop_condition.xml','reports/search_v2c_b_interactions_final.xml'],
          'implementation_stopped':True,'repair_applied_after_stop':False}
write('current_blocker.md','''# V2C-B stopped: forged choice deletes accepted Search context

Current V2C-A/A.1 gate passes. This is a new V2C-B interaction lifecycle defect.

An authenticated, authorized patron first commits an accepted Search context.
A contradictory query correctly leaves it intact and issues a pending choice.
Submitting an unissued choice UUID returns 404, but the accepted context is then
missing. The isolated Mongo reproducer fails the required unchanged-state assertion.
See search_v2c_b_stop_condition_observed.json and search_v2c_b_stop_condition.xml.

Cause: search/interaction_api.py authorized() wraps `yield` in the same
HTTPException handler as authorization. The operation's expected choice-not-found
404 reaches that handler, which calls invalidate(actor, library_id). This deletes
the caller's accepted contexts and pending clarifications. It does not require
foreign data access. No cross-user/private vocabulary leak was observed.

The prompt explicitly requires stopping if a forged clarification/choice can
mutate Search state. Implementation stopped; the defect has not been repaired
or hidden by changing the assertion. FINAL is PARTIAL, not accepted.

Next authorized development must separate actual authorization loss from an
operation's ordinary 403/404. Invalidation must require fresh confirmed loss of
membership/access. Forged choices must return a denial without deleting, touching,
creating or replacing accepted contexts. A valid pending choice must remain usable.
Run the retained reproducer first, then the complete final gates and browser checks.

Additional validation note: one earlier test incorrectly assumed an owner ADMIN
could browse a GENERAL_USER patron workspace; the fixture has been corrected to
test a real patron-to-librarian role change. That corrected test was not rerun after
the stop condition. The production patron-role policy was preserved.

Disposable accounts 488/489 were disabled, their memberships removed, their Search
contexts cleared, and only the V2CB Clause QA library archived. Original Test User
was restored to the Global Catalogue. Existing services remain running. Some final
source edits were tested in isolated processes after the last Search-service boot;
restart Search after fixing this blocker before claiming running-service acceptance.
''')
write('precondition.json',{'status':'PASS','captured_at':now,'implementation_started':True,
       'scope':'Current V2C-B implementation; V2C-A and V2C-A.1 admission verified before implementation.',
       'parser_version':'search-v2c-a1-compositional-1','original_admission':'8/8',
       'fresh_planner':suites['gate_planner'],'fresh_session':suites['gate_session'],
       'historical_gate_preserved':'reports/search_v2c_b_precondition_at_implementation_start.json',
       'historical_blockers_are_not_current_parser_failures':True,'current_V2CB_blocker':'reports/search_v2c_b_current_blocker.md'})

application=['search/api.py','search/query_execution.py','search/session_store.py','search/query_session.py','search/library_intelligence_api.py',
 'search/interaction_api.py','search/query_interaction.py','search/query_suggestions.py',
 'frontend/src/components/CatalogueSurface.tsx','frontend/src/components/GlobalCatalogue.tsx','frontend/src/components/SearchIntelligence.tsx',
 'frontend/src/components/SearchAutocomplete.tsx','frontend/src/components/SearchClarification.tsx','frontend/src/pages/LibraryCatalogue.tsx',
 'frontend/src/lib/searchNlu.ts','frontend/src/styles/product.css','frontend/package.json']
tests=['tests/institution_v2g/test_query_v2c_b.py','tests/institution_v2g/test_query_v2c_b_stop_condition.py',
 'frontend/tests/search-nlu.test.tsx','frontend/tests/search-session.test.tsx','frontend/tests/search-interactions.test.tsx']
scripts=['scripts/search_v2c_b_fixture.py','scripts/search_v2c_b_baseline.py','scripts/search_v2c_b_live.py','scripts/search_v2c_b_reports.py']
changed=[];protected=[];missing=[]
for name,before in baseline['files'].items():
    p=Path(name);p=p if p.is_absolute() else ROOT/p
    if not p.exists():missing.append(str(p));continue
    st=p.stat();after={'size':st.st_size,'mtime_ns':st.st_mtime_ns}
    if 'sha256' in before:after['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    item={'path':str(p),'before':before,'after':after,'preserved':after==before}
    (protected if item['preserved'] else changed).append(item)
allowed={str((ROOT/p).resolve()) for p in application+tests+scripts+['reports/search_v2c_b_current_blocker.md','reports/search_v2c_b_precondition.json','reports/search_v2c_b_final_qa.json']}
unexpected=[row for row in changed if row['path'] not in allowed]
assert not missing and not unexpected,(missing,unexpected)
preservation={'status':'PASS','captured_at':now,'global_book_count':db.books.count_documents({}),
 'protected_files':protected,'authorized_application_changes':changed,'unexpected_changes':unexpected,
 'new_application_files':[p for p in application if p not in baseline['files']],
 'large_file_method':'Existing baseline size+mtime_ns; SHA256 compared for files whose baseline includes it. Multi-GB artifacts were not rehashed.',
 'mongo_indexes_before':baseline['mongo_indexes'],'mongo_indexes_after':{n:db[n].index_information() for n in baseline['mongo_indexes']},
 'only_auxiliary_index_added':'institution_library_books.v2cb_author_prefix: library_id,status,authors; case-insensitive en strength2 collation.',
 'hnsw_kg_rebuilt':False,'qwen_changed':False,'recommendation_changed':False,'more_like_this_changed':False,'inventory_algorithm_changed':False,
 'fixture_cleanup':fixture}
assert preservation['global_book_count']==5000000
write('preservation.json',preservation)
write('changed_files.json',{'application':application,'tests':tests,'scripts':scripts,
       'reports':[str(p.relative_to(ROOT)) for p in R.glob('search_v2c_b_*') if p.is_file()],
       'screenshots':[str(p.relative_to(ROOT)) for p in (R/'search_v2c_b_screens').glob('*.png')],
       'unrelated_work_preserved':True,'commit_created':False,'blanket_staging':False,'source_fingerprints':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in application+tests+scripts}})
write('clarification_architecture.md','''# Implemented interaction layer — acceptance blocked

search/query_interaction.py consumes the accepted typed decision and candidates;
it does not recognize a replacement query grammar. Choices address one bounded
field; operands and rewritten fragments use the existing parser and validator.
No Qwen/model calls were added. Literal choices retain explicit controls.

Pending documents share search_sessions_v2b with a clarification: UUID prefix,
five-minute expiry, max16 per user/login/scope/workspace. IDs and choice IDs are
opaque UUIDs. User, JWT sid, workspace, scope, parser version, query, mode and
accepted context version are checked. Preview precedes one-use CAS consumption;
the existing execution pipeline repeats validation and session version checks.
Normal unaccepted queries do not commit/touch the accepted plan. Clear/context
invalidation also deletes attached pending documents. Actual lookup failures must
not invalidate accepted state: the current authorized() handler violates this
invariant on an unissued choice 404. See current_blocker and the retained failing test.
''')
write('suggestion_architecture.md','''# Authorized bounded autocomplete — observed implementation

GET /query/suggestions and POST /query/suggestions/select authenticate and authorize
before any vocabulary/cache/entity lookup. Maximum8, prefix2 for subjects,3 for
authors/titles, bounded150 characters. Exact/quoted/numeric forms abstain.

Global uses the existing SQLite TITLE/AUTHOR prefix range indexes (32 relationships
per source per base/delta) and indexed canonical work_id hydration. It never scans
the 5M catalogue, invokes HNSW/KG/CrossEncoder, or uses Global filler for tenants.
Tenant titles use the existing library_id,normalized_title index; authors use one
small auxiliary Mongo library_id,status,authors index with en strength2 collation.
At most32 candidates/source are fetched before the unchanged usable()/format
pipeline verifies canonical visibility. Subjects use a bounded2048 tenant/4096
Global projection; a max16 LRU expires30s and is keyed by user,sid,library,workspace
and latest indexed audit generation. Cached subject candidates receive fresh
bounded indexed discoverability proofs, including after removal. No response
cache can bypass authorization. Typo matching uses at most64 subject candidates
from a prebuilt prefix bucket and conservative threshold/margin; proper names are
not silently rewritten. Broad author typo/infix completion is intentionally absent.

Suggestion IDs are random opaque tokens in a max2048 process cache, expire120s,
and bind exact query/mode/owner/workspace/generation. Selecting requires fresh
authorization and canonical revalidation. Viewing/typing does not commit Search.
The frontend debounces200ms, cancels with AbortController, gates by full scope/token/
query/mode key, checks async selection keys, handles IME and keyboard listbox input.
403/404 reuse the existing context revalidation path to remove revoked private UI.
''')

write('clarification_cases.json',{'status':'PARTIAL','observed_browser_cases':[b for b in browser if any(w in b['name'].lower() for w in ['ambiguous','incomplete','bounds','include','unsupported','correction'])],
       'tests':suites['interactions_final'],'critical_failure':critical,
       'unsupported_behavior':'No strict page/year/edition promise is invented. Global year choices suppressed. Page removal leaves other unsupported requirements rejected.',
       'author_topic':'books about Asimov stays executable semantic topic; no unnecessary author rewrite.'})
write('clarification_security.json',critical)
write('suggestion_sources.json',{'status':'PASS for observed prefixes','architecture':'reports/search_v2c_b_suggestion_architecture.md','samples':live['quality'],
       'limits':'Prefix windows can omit less frequent values. No infix completion or broad author fuzzy lookup. Only whole-query/current prefix completion is implemented.'})
write('suggestion_quality.json',{'status':'PARTIAL','observed_samples':live['quality'],
       'method':'Synthetic scoped fixture and existing Global/TEST spot checks; no production accuracy benchmark or ranking-improvement claim.',
       'conservative_abstention':'Python 3, C++, C#, Catch-22, 1984, quoted literals, Dune 2, rare author names protected in tests. Author typo expansion is not implemented.'})
write('suggestion_security.json',{'status':'PASS for observed denial checks; overall V2CB blocked','live':live['security'],
       'browser':[b for b in browser if any(w in b['name'].lower() for w in ['revok','outsider','switch','navigation','logout'])],
       'new_security_tests':suites['interactions_final'],'critical_clarification_failure':critical})
write('corrections.json',{'status':'PARTIAL','browser':[b for b in browser if 'correction' in b['name'].lower()],
       'preserves_original_wording':True,'accepted_parser_unchanged':True,
       'limits':'Scoped subject corrections only; no speculative author rewrite; general choice lifecycle remains blocked by the forged-choice invalidation defect.'})
write('interpretation_chips.json',{'status':'PARTIAL','browser':[b for b in browser if any(w in b['name'].lower() for w in ['chip','removal','refinement','clear search'])],
       'final_targeted_backend':'Multi-subject/exclusion remove-only addresses passed in the 83-case run, but two unrelated cases failed; whole V2CB acceptance stopped.',
       'final_targeted_frontend':'32/32: search-nlu, search-session, search-interactions. Full prior frontend run900/900.',
       'unverified_running_service_change':'Final per-item remove addresses were not rechecked in the running Search process after source edit. Restart/retest after blocker repair.',
       'soft_strict':'Soft preference visibly labelled Preference and dashed border; no unsupported strict-page chips. Empty KG disclosure remains hidden.'})
for name,key in [('global','GLOBAL'),('public_tenant','TEST'),('private_tenant','PRIVATE_NOT_BUILT')]:
    write(name+'.json',{'status':'PARTIAL overall; observed ordinary searches functional','search_measurement':live['search'][key],
         'browser':[b for b in browser if any(w in b['name'] for w in ({'global':['GLOBAL'],'public_tenant':['PUBLIC TEST'],'private_tenant':['PRIVATE']}[name]))],
         'critical_gate':critical if name=='private_tenant' else 'V2CB acceptance stopped by forged-choice state mutation.'})
write('multi_library.json',{'status':'PARTIAL','browser':[b for b in browser if any(w in b['name'].lower() for w in ['switch','navigation','public test','private'])],
       'accepted_isolation_regression':suites['regression_sessions'],'stop_condition':critical})
write('session_regression.json',{'status':'FAIL','accepted_V2B_regression':suites['regression_sessions'],'new_forged_choice_reproducer':suites['stop_condition'],'observed':stop})
write('personalization_regression.json',{'status':'PASS for accepted suites; V2CB session lifecycle FAIL','tests':suites['regression_sessions'],
       'browser':[b for b in browser if 'personalization' in b['name'].lower()],
       'semantics':'OFF default; own Reading List only; no new hidden signals; eligibility/rerank limits unchanged.'})
for name in ['v2ca','v2ca1']:
    write(name+'_regression.json',{'status':'PASS','planner':suites['regression_planner'],'session':suites['regression_sessions'],
          'gold_queries':136,'seeded_deterministic_assertions':1000,'original_admission':'8/8',
          'label_provenance':'136 independently AI-reviewed gold queries; not human-verified. Seeded assertions are not real-world search accuracy.'})
for name,words in [('recommendation',['recommendation']),('more_like_this',['like_this']),('inventory',['inventory'])]:
    suite_keys=['retrieval_regression'] if name=='more_like_this' else ['catalogue_regression','tenant_full']
    matches=[{'suite':key,'cases':[case for case in suites[key]['cases'] if any(word in case.lower() for word in words)]} for key in suite_keys]
    write(name+'_regression.json',{'status':'PASS for applicable observed regression suites','suites':{key:{k:v for k,v in suites[key].items() if k!='cases'} for key in suite_keys},
        'matching_cases':matches,'source_and_artifacts_preserved':True,'overlapping_counts_not_summed':True,
        'limits':'Source preservation is separate from exercised cases; see matching cases for exact coverage.'})
write('performance.json',{'status':'MEASURED; acceptance blocked','baseline':'reports/search_v2c_b_baseline.json','after':live,
       'method':'First completed after run: same24 parser queries,600 samples;20 resident HTTP requests/group. Cold suggestions mean cold authorized projection using distinct sid, with warm OS/Mongo/resident models. Warm suggestions20/scope. Generation includes HTTP+guard; resolution includes existing Search.',
       'later_attempt':'A later rerun was aborted when an owner ADMIN was used in a GENERAL_USER-only patron workspace; 403 is correct. Do not use incomplete rerun as performance evidence.',
       'memory_before':read('search_v2c_b_memory_before.json'),'memory_after':read('search_v2c_b_memory_after.json'),
       'memory_limit':'Different process lifetime/Windows paging; do not claim memory improvement from these snapshots.',
       'interpretation':'No general parser speedup claimed; inspect p50 and p95 separately. Measured ordinary Search changes are modest and Private READY p95 decreased in this run, without a throughput claim.',
       'final_source_limit':'Measurements precede final per-item chip addressing and JWT-sid guard. Final post-repair measurement still required.'})
write('browser.json',{'status':'PARTIAL','origin':'http://127.0.0.1:5174','browser':'Real Chromium in Codex IAB','observations':browser,
       'six_contexts_observed':['GLOBAL','PUBLIC TEST PATRON','PUBLIC TEST STAFF','PRIVATE PATRON','PRIVATE STAFF','PRIVATE OUTSIDER DENIAL'],
       'limits':['Touch event injection is unsupported by IAB; no physical touch acceptance claimed.','Final per-item chip addressing was not browser-retested after the mandatory stop.','Full acceptance cannot be PASS while the forged-choice invariant fails.'],
       'cleanup':fixture,'restored_account':'Original Test User at /catalog; QA accounts are disabled.'})
write('accessibility.json',{'status':'PASS for changed surfaces observed; final acceptance PARTIAL',
       'structural_axe':'Component checks with color-contrast rule disabled, included in passing frontend suites.',
       'browser_checks':['ArrowDown and ARIA active descendant','Escape closes popup','Enter verifies selection','Tab closes without selecting','No modal clarification/focus trap','Status count announcement','Visible focus CSS; controls >=44px'],
       'limits':['No physical screen reader or hardware touch session.','No full-browser automated contrast audit.'],
       'evidence':['reports/search_v2c_b_browser_observations.json','reports/search_v2c_b_frontend_interactions_final.log','reports/search_v2c_b_responsive_observations.json']})
write('responsive.json',{'status':'PASS for measured surfaces','observations':responsive,
       'checks':{'exact_widths':[320,375,390,768,1024,1440],
                 'horizontal_overflow':any(r['documentWidth']>r['width'] for r in responsive),
                 'popup_outside_viewport':any(r.get('panel') and (r['panel']['x']<0 or r['panel']['right']>r['width'] or r['panel']['bottom']>950) for r in responsive)},
       'screenshots':'reports/search_v2c_b_screens','limits':'950px CSS height; mobile panel scrolls; hardware touch unavailable.'})

qa={'FINAL':'PARTIAL','V2C_A_PRECONDITION_PASS':'YES','V2C_A1_PRECONDITION_PASS':'YES','ORIGINAL_V2C_B_ADMISSION':'8/8',
 'V2C_A_REGRESSION_PASS':'PASS','V2C_A1_REGRESSION_PASS':'PASS','INCLUDE_EXCLUDE_CONTRADICTION_REGRESSION':'PASS','V2C_A1_SESSION_REGRESSION':'PASS',
 'V2C_A1_PARSER_P50_P95':f"{live['parser']['p50_ms']:.3f}/{live['parser']['p95_ms']:.3f} ms, n600",'INLINE_CLARIFICATION':'YES','AMBIGUOUS_NUMBERS_SAFE':'YES','INCOMPLETE_QUERY_RESOLUTION':'YES','CONTRADICTION_RESOLUTION':'YES','INCLUDE_EXCLUDE_CLARIFICATION':'YES','UNSUPPORTED_OPTIONS_SUPPRESSED':'YES','FALSE_ZERO_RESULTS_AVOIDED':'YES',
 'CLARIFICATION_AUTHORIZATION':'FAIL','EXPIRED_CLARIFICATION_REJECTED':'YES','FORGED_CLARIFICATION_REJECTED':'YES','FORGED_CHOICE_ACCEPTED':'NO','UNACCEPTED_QUERY_COMMITTED':'NO',
 'CATALOGUE_AWARE_AUTOCOMPLETE':'YES','GLOBAL_SUGGESTIONS':'PASS','PUBLIC_TENANT_SUGGESTIONS':'PASS','PRIVATE_TENANT_SUGGESTIONS':'PASS','SUBJECT_SUGGESTIONS':'PASS','AUTHOR_SUGGESTIONS':'PASS','TITLE_SUGGESTIONS':'PASS','SUPPORTED_FILTER_TEMPLATES':'PARTIAL','TYPO_SUGGESTIONS':'PARTIAL','STALE_RESPONSE_PROTECTION':'PASS','AUTOCOMPLETE_FULL_SCAN':'NO','CROSS_TENANT_SUGGESTION_LEAK':'NO','PRIVATE_CLARIFICATION_LEAK':'NO','PRIVATE_CORRECTION_LEAK':'NO','TYPO_CORRECTION':'PARTIAL','CORRECTION_ACCEPTANCE':'PASS','CORRECTION_REJECTION':'PASS','QUERY_CHIP_EDITING':'FAIL','SOFT_VS_STRICT_CHIPS':'PASS','EMPTY_KG_DISCLOSURE_FIXED':'YES','V2B_SESSION_PRESERVED':'FAIL','V2B_PERSONALIZATION_PRESERVED':'PASS','PRIVATE_MEMBERSHIP_REVOCATION_PASS':'PASS',
 'GLOBAL_SEARCH_PASS':'PASS','PUBLIC_TENANT_SEARCH_PASS':'PASS','PRIVATE_READY_SEARCH_PASS':'PASS','PRIVATE_FALLBACK_SEARCH_PASS':'PASS','PRIVATE_OUTSIDER_DENIAL_PASS':'PASS','HNSW_PRESERVED':'PASS','KG_PRESERVED':'PASS','CROSSENCODER_PRESERVED':'PASS','RECOMMENDATION_REGRESSION_PASS':'PASS','MORE_LIKE_THIS_REGRESSION_PASS':'PASS','STAFF_INVENTORY_EXACT_SEARCH_PASS':'PASS','V2C_A_GOLD_REGRESSION':'136/136 independently AI-reviewed; not human-verified','V2C_A_SEEDED_REGRESSION':'1000/1000 deterministic/metamorphic; not real-world accuracy',
 'BACKEND_REGRESSION':'1307/1307 planner;34/34 accepted session;230/230 earlier tenant full;88/88 catalogue;35/35 retrieval. Later83-case run81 pass/2 fail (one fixture-role assumption, corrected but not rerun). Dedicated forged-choice reproducer1 fail. Overlapping suites not summed.',
 'FRONTEND_FULL_SUITE':f'{front_count}/{front_count}; final32/32 focused tests overlap; one added chip case is in focused run only.',
 'TYPESCRIPT_CHECK':'PASS','PRODUCTION_BUILD':'PASS','BROWSER_ACCEPTANCE':'FAIL','ACCESSIBILITY':'PARTIAL','RESPONSIVE':'PASS',
 'SUGGESTION_COLD_P50_P95':{k:{n:live['suggestions'][k]['cold_projection'][n] for n in ['p50_ms','p95_ms']} for k in ['GLOBAL','TEST','PRIVATE_PATRON','PRIVATE_STAFF']},
 'SUGGESTION_WARM_P50_P95':{k:{n:live['suggestions'][k]['warm_projection'][n] for n in ['p50_ms','p95_ms']} for k in ['GLOBAL','TEST','PRIVATE_PATRON','PRIVATE_STAFF']},
 'CLARIFICATION_GENERATION_P50_P95':{k:live['clarification']['generation_http_including_guard'][k] for k in ['p50_ms','p95_ms']},
 'CLARIFICATION_RESOLUTION_P50_P95':{k:live['clarification']['resolution_http_including_existing_search'][k] for k in ['p50_ms','p95_ms']},
 'PARSER_P50_P95':{k:live['parser'][k] for k in ['p50_ms','p95_ms']},
 **{label:{k:live['search'][scope][k] for k in ['p50_ms','p95_ms']} for label,scope in [('GLOBAL_SEARCH_P50_P95','GLOBAL'),('PUBLIC_SEARCH_P50_P95','TEST'),('PRIVATE_READY_SEARCH_P50_P95','PRIVATE_READY'),('PRIVATE_NOT_BUILT_SEARCH_P50_P95','PRIVATE_NOT_BUILT')]},
 'GLOBAL_SEARCH_HEALTH':live['health'],'GLOBAL_BOOK_COUNT':preservation['global_book_count'],
 **{k:'NO' for k in ['GLOBAL_HNSW_REBUILT','GLOBAL_KG_REBUILT','TENANT_HNSW_KG_REBUILT','EMBEDDING_MODEL_CHANGED','CROSSENCODER_CHANGED','QWEN_CHANGED','RECOMMENDATION_CHANGED','MORE_LIKE_THIS_CHANGED','STAFF_INVENTORY_CHANGED','V2C_C_STARTED','PART_2I_STARTED']},
 'FORGED_CHOICE_MUTATED_ACCEPTED_STATE':'YES — deleted the caller accepted context; this is the mandatory stop condition.',
 'stop':critical,'limitations':['No acceptance claim; no repair after mandatory stop.','Some final source edits are not loaded in the running Search process; restart after fixing and rerun all final gates.','First completed performance run retained; later aborted rerun is excluded.']}
write('final_qa.json',qa)
summary=[]
for key,value in qa.items():
    if key in ('stop','limitations'):continue
    if key=='GLOBAL_SEARCH_HEALTH':value='STALE/degraded; baseline_verified=false; HNSW5,000,000; HTTP200 ordinary searches functional'
    summary.append(key+':\n'+(json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else str(value)))
write('final_summary.md','\n\n'.join(summary)+'\n')
write('review.md',f'''# V2C-B implementation review — PARTIAL, stopped

The three requested capabilities have implementation and observed working paths.
They are not accepted. The stop-condition reproducer shows an unissued choice
returns404 and deletes the caller's previous accepted V2B context. See current_blocker.
No correction was applied after that mandatory stop.

V2C-A/A.1 current regression1307/1307 and accepted session34/34 still pass,
including136 AI-reviewed gold queries and1000 seeded assertions. Earlier broad
tenant230/230, catalogue88/88 and retrieval35/35 passed. The expanded83-case run
then exposed2 failures: the genuine lifecycle defect and an incorrect owner/patron
fixture assumption. A corrected role-change test is saved but unverified after stop.
The dedicated reproducer intentionally remains red. Do not add overlapping totals.

Full frontend{front_count}/{front_count} passed before the last per-item chip case;
final focused32/32 passed afterwards. TypeScript/build/lint exit0. Existing build
chunk/dynamic-import warnings and unrelated lint warnings remain. No changed Search
component lint warning was present in the final lint log.

Six real Chromium contexts and six exact widths were observed. Mobile touch event
injection is unsupported; tap geometry was measured, without a hardware-touch claim.
Browser acceptance remains FAIL because the backend integrity gate fails, and final
per-item chip edits were not browser-retested after stop.

Performance is reported from the first completed comparable run, without a general
speedup claim. Later measurements attempted an owner in a patron-only workspace and
correctly got403; that incomplete run is excluded. Final post-fix timing is required.

Protected source/artifact fingerprints and Global5,000,000 book count were preserved;
only one auxiliary author-prefix Mongo read index was added. No model/index rebuild,
Qwen, Recommendation, More Like This or operational Inventory algorithm change.

Disposable fixture cleanup completed. Original Test User restored to /catalog.
Services remain running. No commit, blanket stage, reset, or unrelated file cleanup.
''')
write('next_scope.md','''# Resume V2C-B only after this stop report

Do not start V2C-C or Part2I. V2C-B is not accepted.

1. Read current_blocker.md, stop_condition_observed.json and the failing reproducer.
2. Repair authorized() error boundaries: a missing/unissued choice is not evidence
   that current membership was revoked. Confirm authorization loss freshly before
   invalidation; an operation404 must not clear or touch accepted contexts.
3. Keep the reproducer's unchanged-context assertion. Also verify a valid pending
   choice still works after a forged request and concurrent/stale operations remain
   denied without state corruption. Run the corrected patron-to-librarian role test.
4. Freeze implementation, restart Search on the existing authoritative MongoDB,
   and rerun all required backend/frontend/browser gates. Recheck final per-item
   subject/exclusion removals against the running server, not only component tests.
5. Use new explicitly disposable QA fixtures; prior488/489 accounts are disabled and
   the V2CB Clause QA library is archived. Preserve existing evidence. Capture a fresh
   comparable after benchmark. Complete remaining acceptance without masking the
   existing STALE/degraded Global health or rebuilding HNSW/KG.

No repair was applied after the user-mandated stop in this run.
''')
# Refresh the report inventory after every output exists. It describes this run,
# including preserved historical snapshots, without pretending they were all edits.
changed_manifest=read('search_v2c_b_changed_files.json')
changed_manifest['reports']=[str(p.relative_to(ROOT)) for p in R.glob('search_v2c_b_*') if p.is_file()]
write('changed_files.json',changed_manifest)
print(json.dumps({'FINAL':qa['FINAL'],'reports_written':len(list(R.glob('search_v2c_b_*'))),'protected_fingerprints':len(protected),'authorized_changed_baseline_files':len(changed),'unexpected_changes':len(unexpected),'global_book_count':qa['GLOBAL_BOOK_COUNT'],'frontend_full':front_count,'stop_condition':stop}))
