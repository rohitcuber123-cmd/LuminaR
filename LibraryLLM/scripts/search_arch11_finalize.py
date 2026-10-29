"""Small authoritative V11 closure report and evidence/source index."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,re,xml.etree.ElementTree as ET,zipfile,subprocess,sys

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
sys.path.insert(0,str(ROOT))
REBUILD='--rebuild-generated' in sys.argv
BACKEND=['search/smart_preview.py','search/preview_service.py','search/preview_state.py','search/preview_api.py',
         'search/smart_preview_capabilities.json','search/query_execution.py','search/interaction_api.py']
FRONTEND=['frontend/src/components/SearchPreview.tsx','frontend/src/lib/searchPreview.ts','frontend/src/styles/search-preview.css',
          'frontend/src/components/GlobalCatalogue.tsx','frontend/src/pages/LibraryCatalogue.tsx','frontend/package.json','frontend/tests/search-preview.test.tsx']
ALLOWED={'search/query_execution.py','search/interaction_api.py','frontend/src/components/GlobalCatalogue.tsx','frontend/src/pages/LibraryCatalogue.tsx'}
def read(name):return json.loads((R/name).read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,obj):
    if REBUILD and name not in {'search_arch11_final_report.json','search_arch11_source_manifest.json','search_arch11_delivery.json'}:raise ValueError('Not an owned report assembly output')
    with (R/name).open('w' if REBUILD else 'x',encoding='utf8') as f:json.dump(obj,f,indent=2,ensure_ascii=False)
def metric(n,d,pop,layer='MOCK_FIXTURE'):
    return dict(numerator=n,denominator=d,population=pop,status='MEASURED',evidence='DEVELOPMENT_NOT_INDEPENDENT',integration_layer=layer)
def xmlstats(name):
    cases=list(ET.parse(R/name).iter('testcase'));failed=sum(c.find('failure') is not None or c.find('error') is not None for c in cases)
    return dict(passed=metric(len(cases)-failed,len(cases),name),failed=metric(failed,len(cases),name))
def main():
    from search.smart_preview import VERSION,RELEASE_DECISION,REGISTRY_VERSION
    app=read('search_arch11_application_qa_release.json');broad=xmlstats('search_arch11_broad_release_tests.xml')
    api=xmlstats('search_arch11_api_frozen.xml');browser=read('search_arch11_browser_qaverified.json')
    assert broad['failed']['numerator']==0 and api['failed']['numerator']==0 and browser['status']=='PASS'
    frontend_log=(R/'search_arch11_frontend_full.log').read_text(encoding='utf8')
    ft=sum(map(int,re.findall(r'ℹ tests (\d+)',frontend_log)));fp=sum(map(int,re.findall(r'ℹ pass (\d+)',frontend_log)));ff=sum(map(int,re.findall(r'ℹ fail (\d+)',frontend_log)))
    assert ft==fp==943 and ff==0
    build=(R/'search_arch11_frontend_build_verified.log').read_text(encoding='utf8');assert 'built in' in build and 'error TS' not in build
    lint=(R/'search_arch11_frontend_lint_verified.log').read_text(encoding='utf8')
    assert not any('SearchPreview' in line or 'searchPreview' in line for line in lint.splitlines() if ': warning ' in line)
    baseline=read('search_arch11_baseline.json');changed_history=[p for p,h in baseline['historical_v10_hashes'].items() if not (ROOT/p).exists() or sha(ROOT/p)!=h]
    assert not changed_history,changed_history
    protected=read('search_arch9_preflight.json')['protected_files'];changed=[];missing=[]
    for name,h in protected.items():
        p=ROOT/name
        if not p.exists():missing.append(name)
        elif sha(p)!=h:changed.append(Path(name).as_posix())
    assert not missing and set(changed)==ALLOWED,(missing,changed)
    c4=['search/query_plan.py','search/query_confidence.py','search/query_session.py','search/session_store.py']
    lookup={Path(p).as_posix():h for p,h in protected.items()}
    assert all(sha(ROOT/p)==lookup[p] for p in c4)
    registry=json.loads((ROOT/'search/smart_preview_capabilities.json').read_text());assert registry['version']==REGISTRY_VERSION
    r=app['realistic'];d=app['dev72'];v=app['v8_exposed205'];perf=app['performance']
    na=dict(numerator=None,denominator=None,population='No fresh independent acceptance population',status='N/A',evidence='NOT_PERFORMED',integration_layer='N/A')
    blockers=[
        'Exposed supported complex queries still miss valid execution: 11/24 in V9 development and 48/67 in V8 exposed development.',
        'Unconstrained interpretation is not qualified; raw historical category/derived-format masks remain separately reported despite source-policy review.',
        'Real JWT/current membership, persisted Mongo CAS/expiry/recovery and full staging security have not been qualified under the no-live-write boundary.',
        'No independent book relevance oracle or available authorized live retrieval session; the 12-vector V10 probe is not production relevance.',
        'Current Search service root was unreachable; full index/service health and end-to-end operational performance remain unqualified.'
    ]
    qa={
      'FINAL':'CLOSED_WITH_ADVANCED_SEARCH_FROZEN',
      'CANDIDATE_ID':VERSION,'RELEASE_DECISION':RELEASE_DECISION,
      'ACTIVE_C4_PRESERVED':True,'FEATURE_FLAG_DEFAULT':'OFF; PRODUCTION_MODE_BLOCKS_PREVIEW_EVEN_WITH_FLAG_AND_ALLOWLIST',
      'BACKEND_INTEGRATION_STATUS':'ACTUAL_NATIVE_EXECUTION_ADAPTER_AND_HTTP_ROUTE_INTEGRATED; DEVELOPMENT_ONLY',
      'FRONTEND_INTEGRATION_STATUS':'GLOBAL_AND_LIBRARY_CATALOGUE_PREVIEW_INTEGRATED; DEFAULT_STANDARD_UI_RETAINED',
      'SMART_MODE_STATUS':'TOPIC_AND_EXPLICIT_FILTER_PREVIEW_IMPLEMENTED; ADVANCED_INTERPRETATION_FROZEN',
      'EXACT_MODE_STATUS':'UNCHANGED_NATIVE_C4_LEXICAL_PATH; NO_EXPERIMENTAL_COMPILER_CALL',
      'CAPABILITY_REGISTRY_VERSION':REGISTRY_VERSION,
      'QUERY_INTENT_STATUS':'REUSES_PINNED_V10_FOUR_CHANNEL_IR; ORIGINAL_ACCEPTED_SOURCE_MAP_AND_EXPLICIT_UNRESOLVED_FORMAT_GUARD_ADDED; FINITE_COVERAGE',
      'NATIVE_QUERYPLAN_STATUS':'VALIDATED_SERVER_OWNED_PLAN_TRANSPORTED_TO_SHARED_GLOBAL_TENANT_EXECUTORS; NO_CLIENT_PLAN_ACCEPTED',
      'NEGATIVE_FORMAT_FIX_STATUS':'PREVIEW_DERIVES_GLOBAL_ENTITLEMENTS_FOR_NEGATIVES_AND_REQUIRES_KNOWN_BOOLEAN_FLAGS; C4_ROLLBACK_POLICY_UNCHANGED',
      'COMPLEX_FILTER_STATUS':'COMMON_NATIVE_COMBINATIONS_AND_REFINEMENT_WORK; VARIED_COMPLEX_PROSE_FAILS_QUALIFICATION',
      'SOURCE_CORRECTION_STATUS':'SERVER_ISSUED_CANONICAL_APPLY_KEEP_AND_EQUIVALENT_EXPLICIT_FIELD_SYNTAX; ARBITRARY_NARRATIVE_CORRECTIONS_NOT_QUALIFIED',
      'CATEGORY_OWNERSHIP_STATUS':'EXPLICIT_REGISTERED_SELECTION_HARD; DESCRIPTIVE_TOPICS_SEMANTIC; REVIEWED_POLICY_NOT_CANDIDATE_FITTED_MASKS',
      'NATIVE_CHOICE_STATUS':'BOUND_SERVER_OPERATIONS_AND_SINGLE_ROW_CAS_IMPLEMENTED; LIVE_DURABILITY_NOT_VERIFIED',
      'QUERY_LENGTH_500_COMPATIBILITY':'NEW_PREVIEW_API_UI_ACCEPTED_SOURCE_AND_CHOICES_PASS_500_CHARACTER_TESTS_WITHOUT_TRUNCATION; C4_ROLLBACK_TRANSPORT_UNCHANGED',
      'REFINEMENT_STATUS':'ADD_REMOVE_FORMAT_RATING_SUBJECT_SORT_AND_COMPLETION_SYNC_WITH_ACCEPTED_SOURCE_VERSION; SOURCE_LOSS_FAILS_CLOSED',
      'REVIEWED_REGRESSION_RESULTS':dict(**broad,deselected=7,original_assertions_edited=False,new_silent_deselections=0,
          population='1820 archived V10 reviewed nodes plus 31 V11 application/native/API checks'),
      'FRONTEND_TEST_RESULTS':dict(full=metric(fp,ft,'Full frontend test command, 32 subprocess groups','JSDOM_MOCK_REQUESTS'),failed=metric(ff,ft,'Full frontend tests','JSDOM_MOCK_REQUESTS'),
          latest_preview=metric(12,12,'Focused latest preview component checks','JSDOM_MOCK_REQUESTS'),typecheck_build='PASS',lint='PASS_WITH_EXISTING_UNRELATED_WARNINGS',
          lint_warning_count=len(re.findall(': warning ',lint)),new_preview_warnings=0),
      'API_TEST_RESULTS':api,
      'INTEGRATION_TEST_RESULTS':dict(api=api,browser=metric(sum(s['passed'] for s in browser['steps']),len(browser['steps']),'Chromium desktop/mobile, focused axe, source completion, length, rollback','REAL_BROWSER_MOCK_SERVICE_DATA'),real_persisted='N/A',full_staging='N/A'),
      'ORDINARY_QUERY_RESULTS':r['strata']['complexity']['ordinary'],
      'MULTIFILTER_QUERY_RESULTS':r['strata']['complexity']['structured'],
      'COMPLEX_QUERY_RESULTS':dict(realistic=r['strata']['complexity']['complex'],legacy_dev72=d['summary'],legacy_v8_exposed205=v['summary']),
      'FALSE_EXECUTION':dict(realistic=r['summary']['false_execution'],dev72=d['summary']['false_execution'],v8_exposed205=v['summary']['false_execution'],layer='EXPOSED_DEVELOPMENT_ASGI_MOCK_DEPENDENCIES'),
      'MISSED_VALID_EXECUTION':dict(realistic=r['summary']['missed_valid'],dev72=d['summary']['missed_execution'],v8_exposed205=v['summary']['missed_execution'],layer='EXPOSED_DEVELOPMENT_ASGI_MOCK_DEPENDENCIES'),
      'CRITICAL_FIELD_MISMATCH':dict(realistic=r['summary']['hard_field_mismatch_cases'],
          raw_dev72=metric(len(d['critical_field_cases']),sum(p['executable'] for p in d['predictions']),'V9 development currently executed plans; unchanged historical field masks'),
          raw_v8=metric(len(v['critical_field_cases']),sum(p['executable'] for p in v['predictions']),'V8 exposed currently executed plans; unchanged historical field masks'),
          note='Raw masks retain category-as-hard and ONLY-derived exclusion disagreements; no silent score repair or independent credit.'),
      'SORT_AND_PAGINATION':'FILTER_BEFORE_PAGE; LOCAL_PUSH_DOWN_KEYSET_REFILL_UP_TO_5000; GLOBAL_RANKED_WINDOW_50; DETERMINISTIC_NATIVE_SORT_WITHIN_WINDOW; COMPLETE_TOTALS_NOT_CLAIMED',
      'APPLIED_FILTER_CORRECTNESS':'EXECUTABLE_CHIPS_ONLY; ONLY_AND_NEGATIVE_FORMAT_LABELS_FIXED; PREFERENCES_DISTINCT; BOUNDED_COUNT_NOTICE',
      'CORRECTION_AND_CLARIFICATION':'ISSUED_IDS_SOURCE_VERSION_OWNER_EXPIRY_BOUND; APPLY_KEEP_AND_SUPPORTED_OPERAND_COMPLETION_TESTED',
      'EXACT_REGRESSION_STATUS':'PASS_NATIVE_BASELINE_OUTPUT_COMPARISON_AND_LONG_EXACT_NO_EXPERIMENTAL_COMPILER_TESTS',
      'GLOBAL_SEARCH_STATUS':'MOCK_HTTP_NATIVE_EXECUTION_PASS; REAL_SERVICE_AND_RELEVANCE_NOT_QUALIFIED',
      'PUBLIC_LIBRARY_STATUS':'PATRON_STAFF_CONTEXT_FIXTURES_PASS; REAL_AUTHORITY_NOT_QUALIFIED',
      'PRIVATE_LIBRARY_STATUS':'PATRON_STAFF_CONTEXT_FIXTURES_PASS; REAL_AUTHORITY_NOT_QUALIFIED',
      'TENANT_ISOLATION':'BOUND_SCOPE_AND_FOREIGN_SERIALIZATION_FIXTURES_PASS; NO_REAL_SECURITY_CLAIM',
      'STAFF_PATRON_AUTHORIZATION':'EXISTING_NATIVE_AUTHORIZATION_SEMANTICS_UNCHANGED; MOCK_ROLES_TESTED',
      'OUTSIDER_CONCEALMENT':'MOCK_404_BEFORE_STATE_PROVIDER_ACCESS; REAL_MEMBERSHIP_N/A',
      'PRIVATE_GLOBAL_INDEPENDENCE':'UNLINKED_NATIVE_LOCAL_FALLBACK_FIXTURES_DO_NOT_USE_GLOBAL_SEMANTIC_PROVIDER; LINKED_METADATA_OUTAGE_INDEPENDENCE_UNVERIFIED',
      'REAL_JWT_VERIFIED':False,'MONGO_CAS_VERIFIED':False,
      'EXPIRY_AND_REPLAY_VERIFIED':dict(memory_mock_contracts=True,injected_mongo_conditional_replace=True,real_persisted=False,crash_recovery=False),
      'CACHE_SCOPE_ISOLATION':'NO_V11_RESULT_CACHE; COMPONENT_KEY_ACTOR_TOKEN_LIBRARY_WORKSPACE; ABORT_AND_STALE_TICKET_GUARDS_TESTED',
      'REAL_EMBEDDING_PROVIDER':'EXISTING_NATIVE_MINILM_INTERFACE_WIRED; NO_NEW_V11_REAL_INFERENCE; V10_PROBE_IS_HISTORICAL_COMPONENT_EVIDENCE',
      'VECTOR_INDEX_COMPATIBILITY':'NATIVE_GENERATION_MODEL_CHECKS_REUSED_UNCHANGED; NO_NEW_V11_LIVE_INDEX_QUALIFICATION',
      'RETRIEVAL_RELEVANCE':'NOT_QUALIFIED_NO_INDEPENDENT_BOOK_JUDGMENTS_OR_AVAILABLE_AUTHORIZED_LIVE_SESSION',
      'FILTER_RECALL':'BOUNDED_REFILL_COMPONENT_CHECK_2501_ROWS_THREE_BATCHES; WHOLE_CATALOG_RECALL_NOT_QUALIFIED',
      'FULL_API_P50_P95':dict(live='N/A_NOT_QUALIFIED',mock_http_warm=perf['warm'],first_context=perf['first_context'],note='First context is not cold model startup; measurements include ASGI route/parser/native mocked execution, not live service latency.'),
      'CONCURRENT_SEARCH':perf['concurrency'],'ERROR_TIMEOUT_RATE':dict(mock_regular_requests=perf['unexpected_http_errors'],fault_injected_timeout='EXPECTED_503_NO_OPERATION_CONSUMPTION',real_rate='N/A'),
      'CURRENT_SERVICE_HEALTH':read('search_arch11_service_observation.json'),
      'PERFORMANCE_SLO_STATUS':'NO_ADOPTED_SLO; MOCK_TIMINGS_NOT_A_GATE; OPTIONAL_FUTURE_OPERATIONAL_TARGET_IN_HANDOFF_REQUIRES_APPROVAL',
      'INDEPENDENT_EVALUATION_ELIGIBLE':False,'FRESH_INDEPENDENT_TEST_PERFORMED':False,
      'ACCEPTANCE_CONTEXTS':dict(value=0,status='NO_PRIMARY_POPULATION_CREATED'),
      'DISTINCT_LINGUISTIC_FAMILIES':dict(independent=na,development=metric(47,47,'47 authored realistic linguistic templates, 235 scope contexts','EXPOSED_TEMPLATE_REPLAY')),
      'TYPED_ACCURACY':dict(independent=na,development_realistic=r['summary']['typed'],development_dev72=d['summary']['typed_accuracy'],development_v8=v['summary']['typed_accuracy']),
      'EXECUTION_ACCURACY':dict(independent=na,development_realistic=r['summary']['execution'],development_dev72=d['summary']['execution_accuracy'],development_v8=v['summary']['execution_accuracy']),
      'INDEPENDENT_FALSE_EXECUTION':na,'INDEPENDENT_MISSED_VALID':na,'INDEPENDENT_CRITICAL_FIELD_MISMATCH':na,
      'STRUCTURAL_ISOLATION':'INTEGRATED_PREVIEW_REQUIRES_SERVER_GATE_AND_DEV_TEST_MODE; PRODUCTION_AND_DEFAULT_C4_CANNOT_ENTER_ADVANCED_COMPILER; HISTORICAL_SEALED_INPUTS_NOT_USED',
      'REVIEW_PROVENANCE':'SEPARATE_AGENT_SOURCE_ONLY_REVIEW_IN_reports/search_arch11_contract_review.json; EXISTING_EXPOSED_LABEL_REVIEW_REUSED; NO_FRESH_GOLD',
      'BACKEND_FILES_CHANGED':BACKEND,'FRONTEND_FILES_CHANGED':FRONTEND,
      'FEATURE_FLAG_FILES_CHANGED':['search/smart_preview.py','search/preview_api.py','search/interaction_api.py','frontend/src/lib/searchPreview.ts','frontend/src/components/GlobalCatalogue.tsx','frontend/src/pages/LibraryCatalogue.tsx'],
      'PRODUCTION_DATA_MUTATIONS':0,'INDEX_REBUILDS':0,'SEALED_HELDOUT_EVALUATIONS':0,
      'HISTORICAL_EVIDENCE_PRESERVED':dict(v10=metric(len(baseline['historical_v10_hashes']),len(baseline['historical_v10_hashes']),'V10 source/reports captured at V11 start','FILESYSTEM_HASH_VERIFICATION'),
          protected_unchanged=metric(len(protected)-len(changed),len(protected)-len(changed),'Protected entries outside four explicitly authorized integration source edits','FILESYSTEM_HASH_VERIFICATION'),
          authorized_changed=changed,total_original_manifest_entries=len(protected),missing=missing),
      'ROLLBACK_TEST_STATUS':dict(native=metric(3,3,'C4 outputs versus immutable baseline commit','NATIVE_FUNCTION_MOCK_IO'),browser='PASS_STANDARD_SEARCH_LINK',server_gate='PASS_PRODUCTION_CANNOT_ENABLE_PREVIEW'),
      'SEARCH_HANDOFF_DOCUMENT':'docs/search_v11_handoff.md','REMAINING_RELEASE_BLOCKERS':blockers,
      'STAGING_READINESS':'BLOCKED_ADVANCED_INTERPRETATION_FROZEN','PRODUCTION_READINESS':'NOT_QUALIFIED_NO_ACTIVATION',
      'FINAL_NEXT_ACTION':'RETAIN_C4_EXACT_AND_FROZEN_ADVANCED_ARCHIVE; POLISH_OTHER_LUMINAR_FEATURES; NO_NEW_MAJOR_PARSER_OR_MODEL_RESEARCH_PHASE'
    }
    request=Path(r'C:\Users\balak\.codex\attachments\59cf21ec-acad-4e89-9074-2fa9cd296195\Pasted text.txt').read_text(encoding='utf8')
    required=re.findall(r'^- ([A-Z][A-Z0-9_]+)\s*$',request.split('# 19. FINAL QA REQUIREMENTS')[1].split('# 20.')[0],re.M)
    assert set(required)==set(qa),(set(required)-set(qa),set(qa)-set(required))
    evidence=['reports/search_arch11_broad_release_tests.xml','reports/search_arch11_application_qa_release.json','reports/search_arch11_frontend_full.log',
        'reports/search_arch11_frontend_preview_final.log','reports/search_arch11_frontend_build_verified.log','reports/search_arch11_frontend_lint_verified.log',
        'reports/search_arch11_browser_qaverified.json','reports/search_arch11_desktopverified.png','reports/search_arch11_mobileverified.png',
        'reports/search_arch11_contract_review.json','reports/search_arch11_service_observation.json']
    report=dict(release_decision=RELEASE_DECISION,generated_at_utc=datetime.now(timezone.utc).isoformat(),qa=qa,
        evidence_index=[dict(path=p,sha256=sha(ROOT/p)) for p in evidence],
        note='No scored source was altered using a fresh population. All parser/search scores are exposed development with mock service dependencies. Report source mapping and field masks are not claims of complete understanding.',
        implementation_handoff='docs/search_v11_handoff.md',source_manifest='reports/search_arch11_source_manifest.json')
    write('search_arch11_final_report.json',report)
    sources=[ROOT/p for p in BACKEND+FRONTEND+['.gitattributes','docs/search_v11_handoff.md','tests/test_search_arch11_integration.py']]
    sources.extend((ROOT/'scripts').glob('search_arch11*.py'))
    for folder in ['scratch/search_architecture_v10','scratch/search_v2c_c5er/candidate_search_v4']:
        sources.extend((ROOT/folder).glob('*.py'))
    source_map={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(sources))}
    write('search_arch11_source_manifest.json',dict(candidate_id=VERSION,release_decision=RELEASE_DECISION,
        branch='codex/search-v11-finalization',baseline_commit='822b667e092ba251537f0f3647348b7aa6ca641c',
        source_files=source_map,c4_preserved={p:sha(ROOT/p) for p in c4},historical_v10_unchanged=True,
        authorized_protected_edits=changed,source_freeze='CLOSURE_FREEZE_NOT_INDEPENDENT_ACCEPTANCE_FREEZE',fresh_acceptance=False))
    # A short human report points to the complete QA object rather than
    # duplicating scores into dozens of research documents.
    def ratio(m):return f"{m['numerator']}/{m['denominator']}"
    text=f'''# LuminaR Smart Search V11 closure

**{RELEASE_DECISION}**

Backend/frontend integration is implemented on `codex/search-v11-finalization`.
The preview is production-blocked, disabled by default and available only to an
explicit development/test account allowlist with configured state storage. C4
and native EXACT remain the default. Nothing was deployed or activated.

| Measured exposed development population | Typed | Execution | False execution | Missed valid | Raw executed field-mismatch cases |
|---|---:|---:|---:|---:|---:|
| Realistic 235 contexts / 47 authored templates | {ratio(r['summary']['typed'])} | {ratio(r['summary']['execution'])} | {ratio(r['summary']['false_execution'])} expected blocked | {ratio(r['summary']['missed_valid'])} expected valid | {ratio(r['summary']['hard_field_mismatch_cases'])} executed |
| V9 development72 | {ratio(d['summary']['typed_accuracy'])} | {ratio(d['summary']['execution_accuracy'])} | {ratio(d['summary']['false_execution'])} expected blocked | {ratio(d['summary']['missed_execution'])} expected valid | {len(d['critical_field_cases'])}/{sum(p['executable'] for p in d['predictions'])} executed |
| V8 exposed205 | {ratio(v['summary']['typed_accuracy'])} | {ratio(v['summary']['execution_accuracy'])} | {ratio(v['summary']['false_execution'])} expected blocked | {ratio(v['summary']['missed_execution'])} expected valid | {len(v['critical_field_cases'])}/{sum(p['executable'] for p in v['predictions'])} executed |

These are actual ASGI/native-function workflows with **mock authority and data**.
The perfect small development replay is not independent generalization. Raw
historical field masks retain topical-category and derived-format disagreements;
they were not silently relabeled to pass. Capability-first missing pages is an
explicit source-reviewed V11 migration. The complex valid-miss rates prevent fresh
acceptance and activation, so advanced search is frozen rather than continued as
another parser/model research project.

The reviewed backend/compiler/application run passed
{ratio(broad['passed'])} nodes, with seven disclosed historical deselections.
Frontend tests passed {fp}/{ft}; the latest preview subset passed 12/12. Build and
typecheck passed. Lint passed with existing unrelated warnings. Chromium passed
{sum(s['passed'] for s in browser['steps'])}/{len(browser['steps'])} focused UI checks
with no page/console errors or focused axe violations. Browser service data and
external font resources were intercepted fixtures, not real account activity.

Implemented: shared native execution, server-controlled gating, source/IR/version
bound state, 500-character transport, issued Apply/Keep/completion/refinement,
known-flag negative formats, authoritative local-field pushdown, bounded refill,
truthful window counts, existing cards/actions, responsive UI and rollback.
An explicit missing-format omission found during testing was repaired and is
covered by source-owned completion tests; it is not evidence of arbitrary English
coverage. Canonical corrections are supported; complex narrative corrections are
not qualified.

Warm mock HTTP p50/p95 was {perf['warm']['p50_ms']:.2f}/{perf['warm']['p95_ms']:.2f} ms
over {perf['warm']['samples']} samples. Four-worker mock p95 was
{perf['concurrency']['p95_ms']:.2f} ms over {perf['concurrency']['samples']} requests.
Regular mock performance requests had {ratio(perf['unexpected_http_errors'])}
unexpected errors. These are not live full-service latency, cold embedding latency
or a production SLO. Real JWT/current membership, Mongo durability, retrieval
relevance and live operational qualification are unavailable. No fresh acceptance
population was created. The local Search service root was unreachable.

Preserved: all {len(baseline['historical_v10_hashes'])} captured V10 source/evidence
hashes, all four C4 parser/session policy hashes, and
{len(protected)-len(changed)}/{len(protected)-len(changed)} protected entries outside
the four authorized source integration edits. No production data mutation, index
rebuild, model/weight download, remote AI inference or sealed-heldout evaluation
occurred. Native rollback outputs match the immutable baseline in three fixtures.

The full **{len(required)} required QA fields**, denominators, layers and evidence
index are in [the final JSON report]({(R/'search_arch11_final_report.json').as_posix()}).
Use [the maintenance handoff]({(ROOT/'docs/search_v11_handoff.md').as_posix()}) for exact
files/functions, flags, endpoints, capabilities, tests and rollback. Source hashes
are in [the source manifest]({(R/'search_arch11_source_manifest.json').as_posix()}).

**Final next action:** retain the frozen advanced implementation and evidence,
keep C4/EXACT as default, and move to polishing LuminaR's other features.
'''
    with (R/'search_arch11_final_report.md').open('w' if REBUILD else 'x',encoding='utf8') as f:f.write(text)
    paths=set(sources)|{ROOT/p for p in evidence}|{R/'search_arch11_final_report.json',R/'search_arch11_final_report.md',R/'search_arch11_source_manifest.json'}
    output=R/'search_arch11_closeout_package.zip'
    with zipfile.ZipFile(output,'w' if REBUILD else 'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(paths):z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as z:assert z.testzip() is None
    write('search_arch11_delivery.json',dict(status='VERIFIED_FROZEN_CLOSEOUT',package=str(output.relative_to(ROOT)).replace('\\','/'),
        package_sha256=sha(output),package_bytes=output.stat().st_size,source_files=len(source_map),qa_fields=len(required),
        release_decision=RELEASE_DECISION,production_activation=False))
    print(json.dumps(dict(release_decision=RELEASE_DECISION,backend_tests=broad['passed'],frontend_tests=fp,qa_fields=len(required),package_bytes=output.stat().st_size)))

if __name__=='__main__':main()
