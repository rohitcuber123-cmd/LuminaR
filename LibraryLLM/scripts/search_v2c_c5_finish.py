"""C5 reports-only closure. Does not import or invoke a parser/evaluator."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as ET

R=Path('reports');P='search_v2c_c5_'
def read(name):return json.loads((R/(P+name)).read_text(encoding='utf8'))
def rows(path):return [json.loads(x) for x in Path(path).read_text(encoding='utf8').splitlines() if x.strip()]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(name,v):(R/(P+name)).write_text(json.dumps(v,indent=2,default=str)+'\n',encoding='utf8')
def rate(n,d):return {'numerator':n,'denominator':d,'percent':100*n/d if d else None,'status':'MEASURED' if d else 'NOT MEASURED'}
def display(v):return f"{v['numerator']}/{v['denominator']} {v['percent']:.4f}%" if v['denominator'] else 'NOT MEASURED (0 applicable cases)'
def suite(name):
    path=R/(P+name+'.xml');cases=ET.parse(path).getroot().findall('.//testcase');fail=[];skipped=[]
    for c in cases:
        e=c.find('failure')
        if e is None:e=c.find('error')
        if e is not None:fail.append({'class':c.get('classname'),'name':c.get('name'),'message':e.get('message')})
        if c.find('skipped') is not None:skipped.append(c.get('name'))
    return {'path':str(path),'cases':len(cases),'passed':len(cases)-len(fail)-len(skipped),'failures':fail,'skipped':skipped,'status':'FAIL' if fail or skipped else 'PASS','classes':dict(Counter(c.get('classname') for c in cases))}

def native_report():
    observations=rows(R/(P+'native/observations.jsonl'));assert len(observations)==len({x['query_id'] for x in observations})==220
    corpus=rows(R/(P+'calibration.jsonl'));unresolved=[r['query_id'] for r in corpus if r.get('requires_native_execution') and not r.get('sequence_steps')]
    assert len(unresolved)==10
    allowed={'Search choice changed. Submit the query again.','Search choice expired. Submit the query again.','Search context changed. Submit the query again.',
             'Insufficient library permissions.','Search choice is unavailable. Submit the query again.','Library resource not found.'}
    failures=[];leaks=[];unsafe=[];requests=0;timings=[];body_counts=Counter();commits=0
    for r in observations:
        for i,b in enumerate(r['boundaries']):
            requests+=1;timings.append(b['elapsed_ms']);action=r['action'];denied=True
            if action=='submit_valid_choice_then_replay_identical_choice' and i==0:denied=False
            if action=='resolve_another_users_clarification' and i==1:denied=False
            if denied and b['status']==200:unsafe.append({'id':r['query_id'],'boundary':i})
            before,after=b['state_before'],b['state_after']
            if b['status']>=400:
                body_counts[str(b['body'])]+=1
                if set(b['body'])!={'detail'} or b['body']['detail'] not in allowed:leaks.append({'id':r['query_id'],'boundary':i,'body':b['body']})
                exact=before==after
                ttl=(action=='submit_expired_or_superseded_clarification' and before['accepted']==after['accepted'] and before['profiles']==after['profiles'] and all(p in before['pending'] for p in after['pending']))
                if not exact and not ttl:failures.append({'id':r['query_id'],'boundary':i,'reason':'Denied request mutated accepted/pending/profile state'})
            else:
                a={x['_id']:x for x in before['accepted']};z={x['_id']:x for x in after['accepted']}
                changed=[k for k in a.keys()|z.keys() if a.get(k)!=z.get(k)]
                if len(changed)!=1 or changed[0] not in a or changed[0] not in z or z[changed[0]]['version']!=a[changed[0]]['version']+1:
                    failures.append({'id':r['query_id'],'boundary':i,'reason':'Authorized choice did not produce exactly one version increment'})
                else:commits+=1
    result={'status':'PARTIAL','executed_native_contexts':220,'total_native_contexts':230,'unresolved_unexecuted_contexts':unresolved,
        'native_requests':requests,'authorized_commits_observed':commits,'state_corruption':rate(len({r['id'] for r in failures}),220),'state_failures':failures,
        'private_leaks':len(leaks),'privacy_failures':leaks,'security_unsafe_execution':rate(len({r['id'] for r in unsafe}),220),'unsafe_cases':unsafe,
        'raw_new_harness_assertion_failures':sum(r['result']=='FAIL' for r in observations),'raw_authored_HTTP_agreement':rate(sum(bool(r['raw_status_match']) for r in observations),220),
        'raw_harness_status':'Preserved FAIL;66 over-specific adapter assertions are not silently relabeled PASS. Bodies/statuses agree with unchanged current authorization/lifecycle source.',
        'action_coverage_limits':{'proxy_typed_choice_contexts':88,'proxy_families':['resume_stale_correction','resume_stale_suggestion'],
            'reason':'Original sequences do not specify an actual correction/suggestion issuance contract; harness checks the shared issued-choice lifecycle. This does not establish full correction/suggestion calibration.',
            'cross_user_staff_recovery_not_executed':22,'missing_correction_contexts':10},
        'observations':P+'native/observations.jsonl','response_body_counts':dict(body_counts),
        'calibration_status':'PARTIAL: state/security observations are not independent full native gold for all230 contexts.',
        'by_scope':dict(Counter(r['scope'] for r in observations)),'resolution_elapsed_ms':timings}
    write('native_metrics.json',result);write('security.json',{k:v for k,v in result.items() if k not in ['resolution_elapsed_ms']})
    write('session_regression.json',{'status':'PASS_OBSERVED_INVARIANTS_ONLY' if not failures else 'FAIL','contexts_observed':220,'state_corruption':result['state_corruption'],'failures':failures,
        'native_calibration_status':'PARTIAL','limitations':result['action_coverage_limits'],'native_test_results':P+'native.xml'})
    return result

def main():
    pre=read('precondition.json');d=read('development_safety_regression.json');base=read('baseline_metrics.json');m=base['metrics'];quality=read('label_quality.json');selected=read('selected_policy.json');native=native_report()
    assert pre['status']=='PASS' and not selected['selected']
    suites={k:suite(k) for k in ['parser_raw','parser_reviewed','tenant_raw','tenant_reviewed','native','catalogue','inventory_current','retrieval']}
    originals=suites['parser_raw']['failures']+suites['tenant_raw']['failures'];contract=json.loads((R/'search_v2c_c4_reviewed_contract.json').read_text())
    unmapped=[f for f in originals if f['class']+'::'+f['name'] not in contract['historical_assertion_map']]
    assert not unmapped
    native_fail=[f for f in suites['native']['failures'] if not f['class'].endswith('test_query_v2c_c5_calibration')]
    current_pass=not native_fail and not unmapped and suites['parser_reviewed']['status']=='PASS' and suites['tenant_reviewed']['status']=='PASS'
    write('backend_regression.json',{'RAW_HISTORICAL_SUITE':'FAIL','REVIEWED_CURRENT_CONTRACT_SUITE':'PASS' if current_pass else 'FAIL',
        'suites':suites,'retained_historical_assertion_failures':originals,'unmapped_historical_failures':unmapped,
        'calibration_native_harness_failures':suites['native']['failures'],'accepted_B1_C1_failures':native_fail,
        'counting':'Reviewed parser/tenant suites overlap raw suites. Native XML includes220 calibration contexts plus37 B1/C1 tests; native sequence requests are not additional test cases.',
        'unique_raw_or_native_backend_cases':sum(suites[k]['cases'] for k in ['parser_raw','tenant_raw','native','catalogue','inventory_current','retrieval']),
        'failed_inventory_path_attempt':{'path':P+'inventory.log','status':'COMMAND_ERROR','tests':0,'reason':'Incorrect test directory; corrected command runs95 tests in inventory_current.xml.'}})
    front=(R/(P+'frontend_full.log')).read_text(encoding='utf8');passes=[int(x) for x in re.findall(r'ℹ pass (\d+)',front)];fails=[int(x) for x in re.findall(r'ℹ fail (\d+)',front)]
    build=(R/(P+'frontend_build.log')).read_text(encoding='utf8');lint=(R/(P+'frontend_lint.log')).read_text(encoding='utf8')
    front_ok=len(passes)==31 and sum(passes)==931 and sum(fails)==0
    build_ok='built in' in build and 'error TS' not in build
    lint_summary=[x for x in lint.splitlines() if 'Found ' in x or 'warning' in x and 'error' not in x]
    write('frontend_regression.json',{'status':'PASS' if front_ok and build_ok else 'FAIL','full_suite':{'passed':sum(passes),'failed':sum(fails),'node_process_groups':len(passes),'log':P+'frontend_full.log'},
        'Search_interaction_session_tests':'34/34 included inside full931 count, not added again','TypeScript':'PASS' if build_ok else 'FAIL','production_build':'PASS' if build_ok else 'FAIL',
        'lint':{'status':'PASS_WITH_WARNINGS','warning_lines':len(lint_summary),'log':P+'frontend_lint.log'},'frontend_source_changed':False})
    # No selected policy means no controlled rollout/acceptance to exercise.
    # Record blocked work explicitly instead of emitting empty PASS evidence.
    reason='No defensible calibrated policy selected. Controlled integration and calibrated-policy browser acceptance were not performed; C4 remains active.'
    write('browser.json',{'status':'BLOCKED','reason':reason,'Chromium_checks_run_in_C5':0,'C4_evidence_reference':'search_v2c_c4_browser.json (historical18/18; not a fresh C5 acceptance)',
        'contexts_required':['GLOBAL','PUBLIC_PATRON','PUBLIC_STAFF','PRIVATE_PATRON','PRIVATE_STAFF','PRIVATE_OUTSIDER'],
        'required_interactions_pending':['medium confidence notice','clarification acceptance/rejection','chip removal','session continuation','account switch','workspace denial','membership revocation'],
        'private_leaks_observed_in_C5_browser':'NOT MEASURED'})
    write('accessibility.json',{'status':'PARTIAL','reason':reason,'tested':'Full existing frontend unit/integration suite931/931, including Search interactions. No fresh C5 Chromium keyboard/focus/ARIA audit.',
        'full_product_accessibility_claim':False,'frontend_source_changed':False})
    write('responsive.json',{'status':'PARTIAL','widths_required':[320,375,390,768,1024,1440],'widths_browser_checked':[],
        'reason':reason,'overflow_claim':'NOT MEASURED','reduced_motion':'Existing source preserved; no fresh browser verification'})
    for scope,filename in [('GLOBAL','global.json'),('PUBLIC','public_tenant.json'),('PRIVATE','private_tenant.json')]:
        scoped=[(s,v) for s,v in base['by_scope'].items() if s==scope or s.startswith(scope+'_')]
        write(filename,{'status':'PARTIAL','policy_activated':False,'parser_scopes':dict(scoped),'native_observed_contexts':{s:v for s,v in native['by_scope'].items() if s==scope or s.startswith(scope+'_')},
            'missing_parser_scope_evidence':[s for s,v in scoped if v['parser_cases']==0],
            'reason':'No candidate satisfies measurable all-scope calibration evidence; private parser sample has only clear executable confidence1.0 cases. Native action cases cannot substitute for missing parser decision strata.',
            'authorization_code_changed':False})
    before=read('baseline_files.json')['files'];proof=[];changed=[]
    for p,h in before.items():
        after=sha(p);proof.append({'path':p,'before':h,'after':after,'unchanged':h==after})
        if h!=after:changed.append(p)
    runtime_log=read('runtime_log_append.json')
    assert changed==['reports\\search_v2c_c4_search_stdout.log'] or not changed,changed
    if changed:
        data=Path(runtime_log['path']).read_bytes()
        assert runtime_log['original_prefix_retained'] and hashlib.sha256(data[:runtime_log['before_bytes']]).hexdigest()==runtime_log['before_sha256']
    hold=read('holdout_preservation.json')
    for item in hold['proof']:assert sha(item['path'])==item['expected_sha256']
    for p,h in hold['manifests'].items():assert sha(p)==h
    hold['verified_again_at_closure']=True;write('holdout_preservation.json',hold)
    old=json.loads((R/'search_v2c_c_preservation.json').read_text());artifacts=[]
    for item in old['files']:
        p=item['file']
        if p.startswith(('data_pipeline/','local-data/','recommendation/','rag/')) or p=='scripts/search_v2c_c_author_gold.py':
            b=item['after'];s=Path(p).stat();same=sha(p)==b['sha256'] if 'sha256' in b else s.st_size==b['size'] and s.st_mtime_ns==b['mtime_ns'];assert same,p
            artifacts.append({'path':p,'unchanged':same,'method':'SHA256' if 'sha256' in b else 'size+mtime_ns; not a fresh full index checksum'})
    live=read('live_health.json');perf=read('performance.json')
    write('preservation.json',{'status':'PASS','parser_source_changed':False,'production_source_changes':[], 'source_and_historical_report_hashes':proof,'large_artifacts':artifacts,
        'global_books':live['book_count'],'health':live['health'],'model_or_index_rebuilds':0,'Recommendation_MLT_Inventory_Circulation_Fees_Assets_Authorization_changed':False,
        'runtime_auth_journal':'B1 logout tests may update rag/private_sessions.sqlite revoked_sessions; not a model/index/catalogue asset. This live authentication journal is not claimed byte-identical.',
        'runtime_service_log_append':runtime_log,
        'build_outputs':'Existing frontend build regenerated dist/ and TypeScript build caches; frontend source and digital asset storage unchanged.',
        'heldout_manifest_unchanged':True,'heldout_rows_deserialized':0})
    qa={'FINAL':'PARTIAL','V2C_C5_IMPLEMENTED':'NO','IMPLEMENTATION_DETAIL':'Integrity, parser baseline, candidate comparisons and regression evidence completed; no calibrated production policy selected or integrated.',
        'V2C_C4_PRECONDITION':pre['status'],'PARTITION_ACCOUNTING':read('partition_accounting.json')['status'],
        'CALIBRATION_CASES':280,'CALIBRATION_UNIQUE_CONTEXTS':280,'CALIBRATION_AI_REVIEWED':70,'CALIBRATION_HUMAN_REVIEWED':0,'CALIBRATION_UNREVIEWED':200,'CALIBRATION_UNRESOLVED_LABELS':10,
        'CALIBRATION_AI_PROVENANCE_INCLUDING_UNRESOLVED':80,'CALIBRATION_BASELINE_RUN':'YES','CALIBRATION_BASELINE_COMPLETENESS':'50 parser +220 native contexts observed;10 unresolved native contexts unexecuted and retained.',
        'CALIBRATION_POLICY_CANDIDATES':3,'CALIBRATION_POLICY_SELECTED':'NO','POLICY_VERSION':selected['POLICY_VERSION'],'POLICY_HASH':selected['POLICY_HASH'],
        'PARSER_SOURCE_CHANGED':'NO','HELDOUT_PARSER_INVOCATIONS':0,'HELDOUT_EVALUATOR_INVOCATIONS':0,'HELDOUT_EVALUATIONS':0,'HELDOUT_MANIFEST_UNCHANGED':'YES'}
    for label,key in [('EXACT_PLAN_MATCH','EXACT_PLAN_MATCH'),('DECISION_ACCURACY','DECISION_ACCURACY'),('HARD_CONSTRAINT_PRECISION','HARD_CONSTRAINT_PRECISION'),('HARD_CONSTRAINT_RECALL','HARD_CONSTRAINT_RECALL'),
        ('COMPARATOR_ACCURACY','COMPARATOR_ACCURACY'),('SUPPORTED_CONTRADICTION_RECALL','SUPPORTED_CONTRADICTION_RECALL'),('PROTECTED_ENTITY_PRESERVATION','PROTECTED_ENTITY_PRESERVATION'),('FALSE_HARD_FILTER_RATE','FALSE_HARD_FILTER_RATE'),
        ('BLOCKED_CASE_UNSAFE_AUTO_PARSE','UNSAFE_AUTO_PARSE_RATE'),('FALSE_CLARIFICATION_RATE','FALSE_CLARIFICATION_RATE'),('AUTO_EXECUTION_COVERAGE_BEFORE','AUTO_EXECUTION_COVERAGE'),('AUTO_EXECUTION_COVERAGE_AFTER','AUTO_EXECUTION_COVERAGE'),
        ('CLARIFICATION_RATE_BEFORE','CLARIFICATION_RATE'),('CLARIFICATION_RATE_AFTER','CLARIFICATION_RATE')]:qa[label]=display(m[key])
    qa.update(SECURITY_FAMILY_UNSAFE_AUTO_PARSE=display(native['security_unsafe_execution']),CROSS_SCOPE_LEAKAGE=display(m['CROSS_SCOPE_VOCABULARY_LEAKAGE_RATE']),
        SESSION_CORRUPTION=display(native['state_corruption']),PRIVATE_DATA_LEAKS=native['private_leaks'],GLOBAL_CALIBRATION='PARTIAL',PUBLIC_TENANT_CALIBRATION='PARTIAL',PRIVATE_TENANT_CALIBRATION='PARTIAL',
        V2C_C4_DEVELOPMENT_SAFETY_REGRESSION=d['status'],FRONTEND_FULL_SUITE=f"{sum(passes)}/{sum(passes)+sum(fails)}",TYPESCRIPT='PASS' if build_ok else 'FAIL',PRODUCTION_BUILD='PASS' if build_ok else 'FAIL',
        BROWSER_ACCEPTANCE='BLOCKED',ACCESSIBILITY='PARTIAL',RESPONSIVE='PARTIAL')
    for label in ['V2A_REGRESSION','V2B_REGRESSION','V2C_A_REGRESSION','V2C_A1_REGRESSION','V2C_B_REGRESSION','V2C_B1_REGRESSION','V2C_C1_REGRESSION']:qa[label]='PASS' if current_pass else 'FAIL'
    qa.update(RECOMMENDATION_REGRESSION=suites['catalogue']['status'],MORE_LIKE_THIS_REGRESSION=suites['catalogue']['status'],STAFF_INVENTORY_REGRESSION=suites['inventory_current']['status'])
    def latency(v):return f"{v['p50_ms']:.4f}/{v['p95_ms']:.4f}/{v['p99_ms']:.4f} ms (n={v['n']}, existing active policy)"
    qa.update(POLICY_P50_P95_P99=latency(perf['active_existing_policy']),PARSER_POLICY_P50_P95_P99=latency(perf['active_existing_parser_plus_policy']),
        GLOBAL_SEARCH_P50_P95_P99='NOT MEASURED',PUBLIC_SEARCH_P50_P95_P99='NOT MEASURED',PRIVATE_SEARCH_P50_P95_P99='NOT MEASURED',GLOBAL_BOOK_COUNT=live['book_count'],
        GLOBAL_SEARCH_HEALTH=f"{live['health']['index_status']} / {live['health']['status']}; baseline_verified={live['health']['baseline_verified']}")
    for field in ['GLOBAL_HNSW_REBUILT','GLOBAL_KG_REBUILT','TENANT_HNSW_KG_REBUILT','EMBEDDING_MODEL_CHANGED','CROSSENCODER_CHANGED','QWEN_CHANGED','RECOMMENDATION_CHANGED','MORE_LIKE_THIS_CHANGED','STAFF_INVENTORY_CHANGED','LLM_SECOND_OPINION_STARTED','PART_2I_STARTED','FINAL_HELDOUT_AUTHORIZED']:qa[field]='NO'
    qa.update(raw_historical_regression='FAIL:12 retained assertions; current reviewed suites PASS',new_native_adapter_assertion_failures=66,
        metric_population='50 parser calibration contexts only; native security/state are separately labeled220-context observations, not full independent calibration gold.',
        blocking_reasons=['Zero blocked/contradictory/incomplete/unsupported parser cases: safety recall/risk NOT MEASURED','No Global/public/staff parser calibration rows','No confidence variation: all50 at1.0; all3 candidates identical','10 native correction contexts lack sequence oracle;200 native labels unreviewed','88 native contexts use a shared choice-lifecycle proxy;66 new harness assertions fail','No calibrated policy selected; no browser/responsive acceptance or Search endpoint latency measurement'],
        completed_at=datetime.now(timezone.utc).isoformat())
    write('final_qa.json',qa)
    lines=['V2C-C remains PARTIAL.','Final held-out evaluation remains blocked.','',
        'C4 precondition and partition accounting pass. Canonical7211 contexts reconcile as6881 development +280 calibration +50 held-out. Development comprises6529 parser +352 native contexts. Calibration comprises50 parser +230 native contexts; repeated sequence steps and50 C3 label replacements are not new logical contexts. Held-out files were hashed only, never deserialized or evaluated.','',
        'The50 independently AI-reviewed parser rows are five dependent families in PRIVATE_PATRON scope, all expected executable and all confidence1.0. Three bounded policies route all50 identically to AUTO_EXECUTE. There is no evidence for selecting a confidence boundary, blocked-query safety, or Global/public/staff parser calibration. Existing C4 policy remains active; no production source changed.','',
        'Parser hard fields and semantic remainder match for all50; exact-plan0/50 consists solely of intent disagreements. Preserve these failures. Protected-entity content is50/50 after stripping paired syntactic quote delimiters; raw quote-inclusive containment is0/50. This representation rule was frozen before baseline predictions; no labels were changed.','',
        'Native220 contexts produced captured API/state boundaries;10 missing-context correction commands remain explicitly unexecuted. The new raw harness has66 retained assertion failures:44 stale-correction cases assumed the wrong generic body/authorization status, and22 staff cross-user cases deny403 before choice ownership. State/privacy observations are reported independently, not by relabeling these tests PASS.88 cases exercise a shared typed-choice lifecycle proxy rather than complete correction/suggestion issuance.','',
        'Reviewed accepted-regression suites are distinct from raw historical failures. Full frontend931/931, TypeScript/build/lint pass; lint warnings retained. Browser, responsive and fresh browser accessibility acceptance are not claimed because no new policy was selected.','',
        'The first C5 development regression adapter omitted two frozen concern tags, incorrectly using supported denominator585. Its source/log/metrics are retained as attempt1. The corrected evaluator copies the same concern metadata as C4: denominator583, all6529 metrics identical, no parser/label/threshold change. The first raw tenant invocation also lacked LUMINAR_SEARCH_SESSION_REPORT: five tests reached the evidence writer and failed on the existing historical report schema. No historical report was written; the retry directs evidence to a new C5 report. First-attempt logs/XML remain visible.','',
        'One runtime exception to byte identity is explicit: the resident C4 Search stdout log appended the59-byte C5 health-check access line. Its original6618 bytes retain the exact baseline SHA256 as a prefix; no historical scoring report was rewritten.','',
        '| QA field | Observed |','|---|---|']
    lines += [f'| {k} | {v} |' for k,v in qa.items() if not isinstance(v,(dict,list))]
    lines += ['', 'Blocking evidence:']+[f'- {x}' for x in qa['blocking_reasons']]
    lines += ['', 'No final held-out, LLM, Qwen, C.6 or Part2I work. Global count5,000,000 and health STALE/degraded with baseline_verified=False. Large artifact checks use inherited SHA256 or size/mtime as available; no fresh full index checksum claim.']
    (R/(P+'review.md')).write_text('\n'.join(lines)+'\n',encoding='utf8')
    (R/(P+'next_scope.md')).write_text('V2C-C remains PARTIAL.\nFinal held-out evaluation remains blocked.\n\nA separate authorized calibration-corpus repair is needed before policy selection: independently author/review decision strata across all five Search scopes, including blocked, contradictory, incomplete, unsupported and genuinely uncertain executable queries; preserve family isolation and all existing raw evidence. Complete the10 missing native correction contexts and actual correction/suggestion issuance oracles; preserve the66 failed adapter assertions while versioning any corrected harness. Do not use held-out content or predictions to fill gaps. Re-freeze inputs and evaluators before another calibration run. Existing C4 remains active.\n',encoding='utf8')
    new_sources=[str(p) for p in Path('scripts').glob(P+'*.py')]+['tests/institution_v2g/test_query_v2c_c5_calibration.py']
    write('changed_files.json',{'production_changes':[],'parser_source_changed':False,'new_sources':{p:sha(p) for p in new_sources},'reports':sorted(str(p) for p in R.glob(P+'*') if p.is_file()),
        'historical_scoring_reports_changed':[],'runtime_service_log_append':runtime_log,'git':'No staging, commit, reset, destructive cleanup or migration','runtime':'Normal auth journal, append-only service access log and frontend build output outside new C5 artifacts.'})
    print(json.dumps({'FINAL':'PARTIAL','selected_policy':False,'parser_baseline':50,'native_observed':220,'native_unresolved':10,'reviewed_regressions':'PASS' if current_pass else 'FAIL','frontend_passed':sum(passes),'C4_development':d['status'],'heldout_evaluations':0}))

if __name__=='__main__':main()
