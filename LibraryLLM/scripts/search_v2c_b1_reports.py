"""Publish V2C-B.1 evidence; retain the immutable original PARTIAL archive."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports';H=R/'search_v2c_b1_history'
def read(name):return json.loads((R/name).read_text(encoding='utf-8-sig'))
def write(name,data):
 p=R/name;p.write_text(data if isinstance(data,str) else json.dumps(data,indent=2,default=str),encoding='utf8')
def report(name,data):write('search_v2c_b1_'+name,data)
def suite(name):
 p=R/('search_v2c_b1_'+name+'.xml');tree=ET.parse(p);s=tree.getroot().find('testsuite');cases=list(tree.iter('testcase'))
 return {'path':str(p),'tests':len(cases),'failures':int(s.get('failures',0)),'errors':int(s.get('errors',0)),'skipped':int(s.get('skipped',0)),
 'cases':[{'name':c.get('name'),'module':c.get('classname'),'passed':c.find('failure') is None and c.find('error') is None} for c in cases]}
now=datetime.now(timezone.utc).isoformat()
suites={n:suite(n) for n in ['retained_reproducer','lifecycle','lifecycle_final','insert_guard','parser','v2ab','tenant','catalogue','retrieval','expanded_83_and_sessions','final_83_plus_cache']}
assert all(s['failures']==s['errors']==0 for s in suites.values())
assert suites['tenant']['tests']==252 and suites['final_83_plus_cache']['tests']==84
assert suites['parser']['tests']+suites['v2ab']['tests']==1307
front=(R/'search_v2c_b1_frontend_full.log').read_text(encoding='utf-8-sig');fc=sum(map(int,re.findall(r'ℹ tests (\d+)',front)))
assert fc==903 and not any(int(n) for n in re.findall(r'ℹ fail (\d+)',front))
assert '✓ built' in (R/'search_v2c_b1_build.log').read_text(encoding='utf-8-sig')
assert not (R/'search_v2c_b1_typescript.log').read_text(encoding='utf-8-sig').strip()
pre=read('search_v2c_b1_prepatch_reproducer.json');forged=read('search_v2c_b1_forged_choice.json')
assert pre['http_status']==404 and not pre['accepted_unchanged']
assert forged['http_status']==404 and forged['accepted_unchanged'] and forged['pending_unchanged'] and forged['personalization_and_suggestion_caches_unchanged']
raw=read('search_v2c_b1_browser_mongo_final.json');network=read('search_v2c_b1_browser_network_final.json');browser=read('search_v2c_b1_browser_observations.json');responsive=read('search_v2c_b1_responsive_observations.json')
assert raw['forged']['accepted_unchanged'] and raw['forged']['pending_unchanged'] and raw['valid']['exactly_one_commit']
assert raw['valid']['after']['version']==raw['accepted']['version']+1
chips=raw['chip_snapshots'];assert len(chips)==5
plans=[r['context']['current_plan'] for r in chips]
assert plans[0]['subjects']==['Fiction','Wizards'] and plans[0]['rating_min']==4 and plans[0]['exclude_terms']==['Romance'] and plans[0]['semantic_text']=='neural networks'
assert plans[1]['rating_min'] is None and plans[1]['subjects']==['Fiction','Wizards'] and plans[1]['exclude_terms']==['Romance'] and plans[1]['semantic_text']=='neural networks'
assert plans[2]['subjects']==['Fiction','Wizards'] and plans[2]['exclude_terms']==[] and plans[2]['semantic_text']=='neural networks'
assert plans[3]['subjects']==['Wizards'] and plans[3]['semantic_text']=='neural networks' and plans[3]['rating_min'] is None
assert plans[4]['subjects']==['Wizards'] and not plans[4]['semantic_text']
assert [r['context']['version'] for r in chips]==[3,4,5,6,7]
for edit in chips:
 sid=edit['context']['_id'];version=edit['context']['version']
 matching=[r for r in network if r.get('body',{}).get('interpretation',{}).get('session',{}).get('version')==version]
 assert matching and all(r['status']==200 and [b['title'] for b in r['body']['results']]==['V2CB1 Wizards Fiction'] for r in matching)
assert [r['width'] for r in responsive]==[320,375,390,768,1024,1440]
assert all(r['scrollWidth']==r['width'] and all(t['height']>=44 and t['x']>=0 and t['right']<=r['width'] for t in r['targets']) for r in responsive)
revoked=read('search_v2c_b1_revocation_observed.json');assert revoked['affected_scope_invalidated'] and revoked['unrelated_global_public_unchanged']
fixture=read('search_v2c_b1_fixture.json');assert fixture['status'].startswith('CLEANED')
live=read('search_v2c_b1_running_service_final.json');assert live['database']=='luminar_library' and live['global_book_count']==5000000 and live['health']['index_status']=='STALE' and not live['health']['baseline_verified']
measure=read('search_v2c_b1_after_measurements.json');before=read('search_v2c_b1_before_measurements.json')
def pair(v):return f"{v['p50_ms']:.3f} / {v['p95_ms']:.3f} ms (n={v['n']})"
def cases(*parts):return [c for c in suites['tenant']['cases'] if any(p in c['name'] or p in c['module'] for p in parts)]
def evidence(status='PASS',**kw):return {'status':status,'captured_at':now,**kw}
root_cause='''# V2C-B.1 verified root cause and repair

The original real-Mongo reproducer returned HTTP 404 for an unissued choice but deleted the accepted Search context. Full prepatch documents are retained in `search_v2c_b1_prepatch_reproducer.json`; the unchanged-state assertion failed before edits.

`authorized()` wrapped both `catalogue.read_context` and its `yield` in one HTTPException handler. The endpoint's choice lookup raised 404 after yield; Python propagated it back into that handler, which interpreted it as access loss and called invalidation. `tenant_search` had a second status-only invalidation path.

The patched dependency catches only context entry failures. `ExitStack` retains normal lock release while endpoint exceptions propagate outside the authorization handler. In both paths a fresh canonical patron/staff guard must confirm access loss before invalidating affected tenant context and personalization. A resource/choice/session 404 alone never proves access loss. Existing role policy remains unchanged.

Resolution loads a scope-bound issued choice, previews and validates it, releases the catalogue lock, obtains a one-use Mongo claim, and enters the existing executor with fresh authority. The accepted-context version CAS prevents stale overwrite. A pending deadline check and server-clock expiry predicate fence existing-context commits. The accepted document records a receipt; only after successful commit is pending marked used. Errors before commit release the claim, while errors after commit cannot make it reusable. No delete/recreate rollback or distributed transaction was added. A crashed claim requires resubmission after its bounded TTL rather than unsafe claim stealing.

Context-limit eviction now occurs only after successful insertion. A late expiry before first insertion cannot evict any other accepted context. Deterministic real-Mongo tests cover that edge, duplicate submissions, forged/valid overlap, expiry, revocation, a newer accepted plan, and errors before and after commit.

Chip addresses remain removal-only and backend validated. Multi-value subject/exclusion addresses remove one exact item; unknown/injected addresses cannot add fields, change scope, generation, identity or personalization owner. The accepted parser source is unchanged.
'''
report('root_cause.md',root_cause)
auth=evidence(confirmed_fresh_access_loss_only=True,downstream_statuses=[404,409,422],downstream_invalidation=False,
 source=['search/interaction_api.py','search/scope_authorization.py','search/query_execution.py'],tests=cases('downstream_status','membership','role_change'),mongo_scope_revocation='search_v2c_b1_revocation_observed.json')
report('authorization_boundary.json',auth)
report('state_integrity.json',evidence(real_mongo=True,forged=forged,browser_final=raw,revocation=revoked,
 ordering=['fresh authorization','scope-bound choice','preview validation','pending claim','fresh executor authorization','version CAS context commit plus receipt','pending consumption'],
 no_delete_recreate=True,context_limit_pruning_after_commit=True,tests=cases('interleaved','failure_before','error_after','late_expiry')))
report('valid_after_forged.json',evidence(final_running_service=raw['valid'],accepted_before=raw['accepted'],forged=raw['forged'],duplicate_denied=True,tests=cases('forgery_then_valid','interleaved')))
report('expiry.json',evidence(tests=cases('expiry','expired'),pending_ttl_seconds=300,accepted_idle_minutes=30,accepted_hard_minutes=60,no_reanimation=True))
report('concurrency.json',evidence(tests=cases('interleaved','failure_before','error_after','late_expiry'),frontend_race_tests=['older clarification response cannot refresh a newer clarification or account','late response from previous prefix cannot replace the current suggestions'],frontend='search_v2c_b1_frontend_focused.log',receipt_and_version_fencing=True))
report('role_change.json',evidence(tests=cases('workspace_binding','foreign_user'),actual_transition='GENERAL_USER patron -> LIBRARIAN staff',owner_admin_patron_fixture_used=False,policy_weakened=False))
chip_report=evidence(real_running_backend=True,session_versions=[3,4,5,6,7],context_id=chips[0]['context']['_id'],mongo=chips,network='search_v2c_b1_browser_network_final.json',result_titles_every_edit=['V2CB1 Wizards Fiction'],tests=cases('chip','one_chip'),forged_plan_json_rejected=422,unknown_remove_keys='ignored; no plan injection or ownership change')
report('chip_editing.json',chip_report)
backend=evidence(suites=suites,planner_unique_total=1307,full_tenant_unique=252,catalogue_unique=88,retrieval_unique=35,
 overlap_note='Focused lifecycle, accepted sessions, corrected role and original 83-case cases are subsets of the full tenant/planner suites; do not add counts across overlapping runs.',
 original_83_rerun='All 83 cases passed inside final 84-case run, plus a forged-choice cache-integrity test.',
 prior_attempt='First broad tenant run under accidental JSDOM assertion memory exhaustion:247 pass,1 fail,3 setup errors. Preserved in search_v2c_b1_tenant_memory_pressure.*; final clean run252 pass.',
 parser_gold={'queries':136,'seeded':1000,'provenance':'Existing independently AI-reviewed labels, not human-reviewed or a real-world accuracy estimate.'})
report('backend_regression.json',backend)
frontend=evidence(full_tests=fc,focused_tests=18,failures=0,typescript='PASS',production_build='PASS',lint='PASS with existing warnings',
 logs=['search_v2c_b1_frontend_full.log','search_v2c_b1_frontend_focused.log','search_v2c_b1_typescript.log','search_v2c_b1_build.log','search_v2c_b1_lint.log'],
 prior_attempt='New waitFor used assert.equal(element,null), causing enormous DOM inspection on a transient assertion. Corrected to boolean assertion. New focus and stale-response tests pass; final full run903/903.')
report('frontend_regression.json',frontend)
limits=['No physical screen-reader session or hardware touch session.','Structural axe checks exclude contrast; no complete product or browser contrast audit.']
access=evidence('PARTIAL',tested_surface='Changed V2C-B search controls only',keyboard='PASS: ArrowUp/Down, Enter, Escape, Tab, clarification/chip buttons, visible focus, focus restored to catalogue-query',
 roles_and_status='PASS: combobox controls/active descendant, listbox/option, status announcements, named chip buttons',IME='PASS automated composition regression',targets='PASS >=44px at all six widths',limits=limits,
 evidence=['search_v2c_b1_frontend_focused.log','search_v2c_b1_responsive_observations.json','search_v2c_b1_browser_observations.json'])
report('accessibility.json',access)
browser_report=evidence(engine='Real Chromium via Codex in-app browser',origin='http://127.0.0.1:5174',search_service='http://127.0.0.1:8003',database='luminar_library',final_pid=29156,
 contexts=['Global','TEST patron490','TEST staff4','private patron490','private staff4','private outsider491 denied'],
 final_boot_security='forged404 with identical accepted/pending documents; legitimate choice commits exactly once; focus restored',
 final_boot_chip_editing='Four removal requests, versions3->7, Mongo/network/results correlated',
 navigation_privacy='Private/Public/Global/library/account changes and logout clear old suggestions and clarification; final revoked popup and catalogue removed on next request.',
 deterministic_stale_response='Controlled late responses tested in React; live warm popup/navigation verified in Chromium. No artificial network race claimed.',
 transient='One private staff request explicitly returned503 Library update in progress; subsequent scoped prefix succeeded. Public staff first prefix also required a later retry after initial catalogue load.',
 responsive=responsive,observations='search_v2c_b1_browser_observations.json',network='search_v2c_b1_browser_network_final.json',mongo='search_v2c_b1_browser_mongo_final.json',fixture=fixture,
 original_user_restored=True,proof='search_v2c_b1_final_browser.png')
report('browser.json',browser_report)
perf=evidence(before='search_v2c_b1_before_measurements.json',after='search_v2c_b1_after_measurements.json',
 method='Same24 parser queries/facets600 samples;20 HTTP requests per Search scope;20 cold authorized projections and20 warm requests per scope;20 clarification generation/resolution pairs. Resident models/OS/Mongo remain warm. No claim of cold process performance.',
 comparable_query_mix=True,final_idle_run=True,prior_contended_run='search_v2c_b1_after_measurements_contended.json',
 claim='No overall speedup claimed. Global and TEST suggestion tail variability and Global Search p95 increase remain visible; small local sample is not a production latency SLA.',
 parser={'before':before['parser'],'after':measure['parser']},search={k:{'before':before['search'][k],'after':v} for k,v in measure['search'].items()},
 suggestions={k:{'before':before['suggestions'][k],'after':v} for k,v in measure['suggestions'].items()},clarification={'before':before['clarification'],'after':measure['clarification']},
 memory={'before':read('search_v2c_b1_memory_before_restart.json'),'after':read('search_v2c_b1_memory_after.json'),'caution':'Working set depends on OS paging; private bytes include resident model/index mappings. No model memory-saving claim.'})
report('performance.json',perf)
allowed={'search/interaction_api.py','search/query_execution.py','search/query_interaction.py','search/session_store.py','search/query_suggestions.py','frontend/src/components/SearchClarification.tsx'}
baseline=read('search_v2c_b1_source_before.json');checks=[]
for name,v in baseline.items():
 p=Path(name);relative=p.relative_to(ROOT).as_posix();st=p.stat();current={'size':st.st_size,'mtime_ns':st.st_mtime_ns}
 if 'sha256' in v:current['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();same=current['sha256']==v['sha256']
 else:same=st.st_size==v['size'] and st.st_mtime_ns==v['mtime_ns']
 authorized=relative in allowed or relative.startswith('reports/search_v2c_b_')
 checks.append({'file':relative,'before':v,'after':current,'unchanged':same,'authorized_current_report_or_application_edit':authorized})
assert all(c['unchanged'] or c['authorized_current_report_or_application_edit'] for c in checks)
manifest=json.loads((H/'manifest.json').read_text());assert all(hashlib.sha256((H/n).read_bytes()).hexdigest()==sha for n,sha in manifest.items())
preserve=evidence(global_book_count=5000000,global_health=live['health'],files=checks,historical_archive_files=len(manifest),historical_archive_hashes_match=True,
 frozen_parser_unchanged=all(c['unchanged'] for c in checks if c['file'] in ['search/query_plan.py','search/query_constraints.py','search/query_repair.py','search/query_confidence.py']),
 rebuilt={'Global HNSW':False,'Global KG':False,'Tenant HNSW/KG':False},
 changed={'Embedding model':False,'CrossEncoder':False,'Qwen':False,'Recommendation':False,'More Like This':False,'Staff Inventory':False,'Circulation':False,'Digital asset authorization':False},
 method='SHA256 for baseline files under10MB; large artifacts use exact size+mtime, not full-content hashes. Scope of baseline explicitly listed. Protected-source absence of edits plus fresh regression tests supports unchanged unrelated services.',
 migrations='None',production_index_rebuilds='None; isolated test database builds only',fixture_cleanup=fixture)
report('preservation.json',preserve)
changed=[c for c in checks if not c['unchanged'] and c['file'] in allowed]
extra=['search/scope_authorization.py','tests/institution_v2g/test_query_v2c_b1.py','tests/institution_v2g/test_query_v2c_b_stop_condition.py','frontend/tests/search-interactions.test.tsx','scripts/search_v2c_b1_fixture.py','scripts/search_v2c_b1_measure.py','scripts/search_v2c_b1_browser_mongo.py','scripts/search_v2c_b1_reports.py']
change_report=evidence(application_changes=changed,new_helper='search/scope_authorization.py',test_and_evidence_sources=[{'file':n,'sha256':hashlib.sha256((ROOT/n).read_bytes()).hexdigest()} for n in extra],
 generated_artifacts=[str(p.relative_to(ROOT)) for p in sorted(R.glob('search_v2c_b1*'))],
 preexisting_dirty_checkout=True,committed=False,staged=False,scope='Only clarification lifecycle, truthful templates, focus restoration, and their tests/evidence; V2C-C/Part2I untouched.')
report('changed_files.json',change_report)
qa={}
def set_many(names,value):
 for n in names.split():qa[n]=value
qa['FINAL']='PASS';set_many('V2C_B1_IMPLEMENTED ROOT_CAUSE_CONFIRMED','YES')
set_many('AUTHORIZATION_BOUNDARY_FIXED FORGED_CHOICE_REJECTED VALID_CHOICE_AFTER_FORGED_REQUEST EXPIRED_CLARIFICATION_STATE_SAFE CROSS_CLARIFICATION_REJECTED CROSS_USER_REJECTED CROSS_SID_REJECTED CROSS_LIBRARY_REJECTED CROSS_WORKSPACE_REJECTED DUPLICATE_CHOICE_SAFE CONCURRENT_STALE_OPERATIONS_SAFE MEMBERSHIP_REVOCATION_STILL_INVALIDATES V2B_SESSION_PRESERVED QUERY_CHIP_EDITING RUNNING_SERVER_CHIP_EDITING CORRECTED_ROLE_CHANGE_TEST SUPPORTED_FILTER_TEMPLATES INLINE_CLARIFICATION CATALOGUE_AWARE_AUTOCOMPLETE GLOBAL_SEARCH PUBLIC_TENANT_SEARCH PRIVATE_TENANT_SEARCH PRIVATE_OUTSIDER_DENIAL V2C_A_REGRESSION V2C_A1_REGRESSION RECOMMENDATION_REGRESSION MORE_LIKE_THIS_REGRESSION STAFF_INVENTORY_REGRESSION TYPESCRIPT PRODUCTION_BUILD BROWSER_ACCEPTANCE RESPONSIVE','PASS')
set_many('DOWNSTREAM_404_CAUSES_INVALIDATION FORGED_CHOICE_MUTATED_ACCEPTED_STATE FORGED_CHOICE_MUTATED_PENDING_STATE','NO')
set_many('TYPO_SUGGESTIONS TYPO_CORRECTION CORRECTIONS ACCESSIBILITY','PARTIAL')
qa['BACKEND_REGRESSION']='1307 planner (1253+54 disjoint cases);252 tenant;88 catalogue;35 retrieval. Original83+cache test=84 pass, overlapping. Focused counts are not added.'
qa['FRONTEND_FULL_SUITE']='903/903 PASS; focused18/18 overlaps.'
qa['PARSER_P50_P95']=pair(measure['parser'])
qa['SUGGESTION_WARM_P50_P95']={k:pair(v['warm_projection']) for k,v in measure['suggestions'].items() if 'warm_projection' in v}
qa['CLARIFICATION_GENERATION_P50_P95']=pair(measure['clarification']['generation_http_including_guard']);qa['CLARIFICATION_RESOLUTION_P50_P95']=pair(measure['clarification']['resolution_http_including_existing_search'])
for scope,field in [('GLOBAL','GLOBAL_SEARCH_P50_P95'),('TEST','PUBLIC_SEARCH_P50_P95'),('PRIVATE_READY','PRIVATE_READY_SEARCH_P50_P95'),('PRIVATE_NOT_BUILT','PRIVATE_NOT_BUILT_SEARCH_P50_P95')]:qa[field]=pair(measure['search'][scope])
qa['GLOBAL_BOOK_COUNT']=5000000;qa['GLOBAL_SEARCH_HEALTH']='STALE/degraded; baseline_verified=false; ordinary Search HTTP200'
set_many('GLOBAL_HNSW_REBUILT GLOBAL_KG_REBUILT TENANT_HNSW_KG_REBUILT EMBEDDING_MODEL_CHANGED CROSSENCODER_CHANGED QWEN_CHANGED RECOMMENDATION_CHANGED MORE_LIKE_THIS_CHANGED STAFF_INVENTORY_CHANGED V2C_C_STARTED PART_2I_STARTED','NO')
qa['acceptance_contract']={'mandatory_gates':'All20 gates satisfy tested scope. Gate18 PARTIAL only for untested nonblocking physical assistive technology/contrast scope.',
 'bounded_typos':'Accepted bounded coverage under section21: canonical scoped subjects, existing conservative parser repair, at most64 prefix-bucket candidates; no fuzzy author or title rewrite. PARTIAL describes breadth, not a failing lifecycle/privacy gate.',
 'templates':'Only executable scope-supported templates are displayed. Unfinished exclude suggestion removed; Global year/physical/availability enforcement and page-count/edition unsupported templates remain unavailable.',
 'privacy':'No private/cross-tenant leak in tested scenarios.', 'limitations':limits+['No overall speed improvement claimed; Global p95 tail increased in final small local sample.']}
qa['hard_gates']={str(i):('PARTIAL: tested controls PASS; untested physical/contrast scope' if i==18 else 'PASS') for i in range(1,21)}
qa['completion']='V2C-B corrective lifecycle patch PASS. V2C-B accepted for review. V2C-C may now be planned.'
report('final_qa.json',qa)
summary='# V2C-B.1 acceptance review\n\n'+qa['completion']+'\n\n'+root_cause.split('\n\n',1)[1]+'\n\nFresh verification: '+qa['BACKEND_REGRESSION']+' Frontend903/903; focused18/18; TypeScript/build pass. Lint completes with established warnings. No overlapping counts summed.\n\nReal Chromium covered all six required identities/scopes. Final server PID29156 passed the Mongo-correlated forged/valid sequence and four chip edits. Exact widths320/375/390/768/1024/1440 have no horizontal overflow and >=44px target heights. Original user restored; QA490/491 disabled, memberships removed, QA library archived.\n\nTypos/corrections remain explicitly PARTIAL for subject-only bounded breadth. Accessibility is PARTIAL only for untested hardware touch/screen-reader/contrast scope; tested keyboard/ARIA/focus/IME/geometry pass. No broad product accessibility claim. Global latency tail variation remains visible; no speedup claimed.\n\nAuthoritative Mongo luminar_library retains5,000,000 books and STALE/degraded baseline_verified=false health. No HNSW/KG/model/reco/MLT/Inventory changes or rebuilds. No destructive migration.\n\nOriginal PARTIAL evidence: search_v2c_b1_history/manifest.json, all68 archived hashes verified unchanged. Current B reports point to this corrective evidence; raw historical runs are not relabelled.\n\n'
summary+='| Field | Result |\n|---|---|\n'+'\n'.join('| '+k+' | '+(json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else str(v))+' |' for k,v in qa.items() if k not in ('acceptance_contract','hard_gates','completion'))+'\n'
report('review.md',summary)
# Update current human-facing B reports, preserving the original archive and raw runs.
map_reports={
'authorization_boundary.json':auth,'clarification_security.json':auth,'interpretation_chips.json':chip_report,'browser.json':browser_report,'accessibility.json':access,'performance.json':perf,'preservation.json':preserve,'changed_files.json':change_report,
'session_regression.json':evidence(tests=cases('query_v2b','query_v2c_a','query_v2c_a1'),state_integrity='search_v2c_b1_state_integrity.json'),
'clarification_cases.json':evidence(tests=cases('choices','clarification','forgery','incomplete','unsupported'),browser='search_v2c_b1_browser_observations.json'),
'suggestion_security.json':evidence(tests=cases('suggestion','projection','private_isolation'),running=measure['security'],revocation=revoked),
'suggestion_quality.json':evidence('PARTIAL: subject typo breadth intentionally bounded',running=measure['quality'],bounds='At most8 returned;32 indexed entity candidates;64 typo bucket candidates; no speculative author fuzzy rewrite.'),
'suggestion_sources.json':evidence(running=measure['quality'],source_unchanged_except_templates=True),
'corrections.json':evidence('PARTIAL',browser='search_v2c_b1_browser_observations.json',tests=cases('correction','guard'),limits=qa['acceptance_contract']['bounded_typos']),
'recommendation_regression.json':evidence(tests=[c for c in suites['catalogue']['cases'] if 'recommendation' in c['name'] or 'recommendation' in c['module']],source_unchanged=True),
'more_like_this_regression.json':evidence(tests=[c for c in suites['catalogue']['cases']+suites['retrieval']['cases'] if any(x in c['name'] for x in ['similar','more_like','recommend'])],source_unchanged=True),
'inventory_regression.json':evidence(tests=cases('inventory'),source_unchanged=True),
'v2ca_regression.json':evidence(planner=suites['parser'],integration=cases('query_v2c_a'),parser_source_unchanged=True),
'v2ca1_regression.json':evidence(planner=suites['parser'],integration=cases('query_v2c_a1'),parser_source_unchanged=True),
'personalization_regression.json':evidence(tests=cases('profile','personal','query_v2b'),default_off=True,forgery_caches_unchanged=True),
'multi_library.json':evidence(tests=cases('scope','foreign','cross','interleaved'),browser='search_v2c_b1_browser_observations.json',revocation=revoked),
'responsive.json':evidence(observations=responsive),
'global.json':evidence(measurement=measure['search']['GLOBAL'],health=live['health'],browser='search_v2c_b1_browser_observations.json'),
'public_tenant.json':evidence(measurement=measure['search']['TEST'],browser='search_v2c_b1_browser_observations.json'),
'private_tenant.json':evidence(ready=measure['search']['PRIVATE_READY'],not_built=measure['search']['PRIVATE_NOT_BUILT'],outsider_denied=True,revocation=revoked,browser='search_v2c_b1_browser_observations.json')}
for name,data in map_reports.items():
 data={**data,'corrective_evidence':'search_v2c_b1_final_qa.json','historical_partial_evidence':'search_v2c_b1_history/search_v2c_b_'+name}
 write('search_v2c_b_'+name,data)
write('search_v2c_b_final_qa.json',{**qa,'historical_partial_evidence':'search_v2c_b1_history/search_v2c_b_final_qa.json'})
write('search_v2c_b_review.md',summary);write('search_v2c_b_final_summary.md',summary)
write('search_v2c_b_current_blocker.md','# Corrective status\n\nThe prior lifecycle blocker is repaired and verified. See search_v2c_b1_final_qa.json and search_v2c_b1_root_cause.md.\n\nThe original failure and PARTIAL report remain unchanged in search_v2c_b1_history. Current raw historical XML/log filenames retain their original observations and are superseded by the B1 reports.\n')
write('search_v2c_b_clarification_architecture.md',root_cause)
write('search_v2c_b_next_scope.md','# Review boundary\n\nV2C-B corrective lifecycle patch PASS. V2C-B accepted for review. V2C-C may now be planned.\n\nNo V2C-C or Part2I implementation started.\n')
assert all(hashlib.sha256((H/n).read_bytes()).hexdigest()==sha for n,sha in manifest.items())
print(json.dumps({'final':qa['FINAL'],'frontend':fc,'tenant':suites['tenant']['tests'],'archive_unchanged':len(manifest),'reports':'search_v2c_b1_review.md'},indent=2))
