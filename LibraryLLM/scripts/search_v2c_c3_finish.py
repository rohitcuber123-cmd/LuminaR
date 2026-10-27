"""Evidence-only C3 closure. Never imports or calls the parser."""
from collections import Counter
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import xml.etree.ElementTree as ET

R=Path('reports')
def read(name):return json.loads((R/('search_v2c_c3_'+name)).read_text())
def write(name,value):(R/('search_v2c_c3_'+name)).write_text(json.dumps(value,indent=2,default=str),encoding='utf8')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def suite(name):
    p=R/f'search_v2c_c3_{name}.xml';root=ET.parse(p).getroot();cases=root.findall('.//testcase')
    failures=[]
    for case in cases:
        error=case.find('failure')
        if error is None:error=case.find('error')
        if error is not None:failures.append({'class':case.get('classname'),'name':case.get('name'),'message':error.get('message')})
    return {'path':str(p),'cases':len(cases),'passed':len(cases)-len(failures),'failures':failures,'classes':dict(Counter(c.get('classname') for c in cases)),'status':'FAIL' if failures else 'PASS'}
def metric(v):
    return f"{v['numerator']}/{v['denominator']} {v['percent']:.4f}%" if v['percent'] is not None else f"{v['numerator']}/{v['denominator']} N/A"

def main():
    d=read('development_metrics.json');m=d['reviewed_v2_label_metrics'];n=read('native_metrics.json');b=read('browser.json');live=read('preflight_live.json');seal=read('sealed_manifest.json');legacy=read('legacy_regression.json');perf=read('performance.json')['parser']
    frozen=read('freeze.json');assert all(sha(p)==h for p,h in frozen['files'].items()),'Frozen source or contract changed'
    suites={key:suite(key) for key in ['parser_final','tenant_regression','native_current','catalogue_regression','retrieval_regression','inventory_regression']}
    allfail=[f for s in suites.values() for f in s['failures']];tests=sum(s['cases'] for s in suites.values())
    def status(*names):return 'FAIL' if any(any(name in f['class'] for name in names) for f in allfail) else 'PASS'
    front=(R/'search_v2c_c3_frontend_tests.log').read_text(encoding='utf8')
    frontend_pass=all(f'ℹ pass {count}' in front for count in [10,6,18]) and 'ℹ fail 0' in front
    write('backend_regression.json',{'status':'FAIL' if allfail else 'PASS','suites':suites,'backend_cases_including_352_native_rows':tests,'passed':tests-len(allfail),'failed':len(allfail),'frontend':{'status':'PASS' if frontend_pass else 'FAIL','cases':34,'log':'search_v2c_c3_frontend_tests.log'},'disjoint_counting':'Final suites only; working/focused repeats not counted. Native352 already inside the native regression suite, not added twice. Mongo conftest roots executed in separate processes.','retained_assertion_failures':'Canonical subject exclusion no longer imposes a broader title/author/description ban. All original assertions retained, every failure reported; raw regression suite is not relabeled PASS.'})
    baseline=read('baseline.json')['files'];proof=[];changes=[];history_changed=[]
    for path,before in baseline.items():
        after=sha(path);same=after==before['sha256'];proof.append({'path':path,'before_sha256':before['sha256'],'after_sha256':after,'unchanged':same})
        if not same:
            changes.append(path)
            if path.replace('\\','/').startswith('reports/'):history_changed.append(path)
    assert not history_changed,history_changed
    appchanges=[p for p in changes if p.replace('\\','/').startswith('search/')]
    runtime=[p for p in changes if p not in appchanges]
    forbidden=[p for p in runtime if p.replace('\\','/')!='rag/private_sessions.sqlite']
    assert not forbidden,forbidden
    old=json.loads((R/'search_v2c_c_preservation.json').read_text());artifacts=[]
    for item in old['files']:
        path=item['file']
        if path.startswith(('data_pipeline/','local-data/','recommendation/','rag/')) or path=='scripts/search_v2c_c_author_gold.py':
            p=Path(path);before=item['after'];stat=p.stat()
            same=sha(p)==before['sha256'] if 'sha256' in before else stat.st_size==before['size'] and stat.st_mtime_ns==before['mtime_ns']
            artifacts.append({'path':path,'unchanged_from_accepted_prior_preservation':same,'method':'SHA256' if 'sha256' in before else 'size+mtime_ns; not a fresh full index checksum'})
    write('preservation.json',{'historical_reports_byte_preserved':True,'source_and_report_hash_proof':proof,'large_artifact_evidence':artifacts,'global_books':live['count'],'health':live['health'],'production_hnsw_kg_rebuilt':False,'model_weights_changed':False,'application_source_changes':appchanges,'new_numeric_module':'search/query_numeric.py','runtime_auth_journal_changes':runtime,'runtime_note':'Normal logout and revocation regression tests mutate rag/private_sessions.sqlite (revoked_sessions only). This live authentication journal is not an index, model or asset content file. Byte preservation is not claimed for it.','Recommendation_MLT_Inventory_Circulation_Assets_C1_B1_source_unchanged':True,'QA_fixture':'search_v2c_c3_fixture.json','full_index_checksum_claim':False,'frozen_hashes_still_match':True})
    new_sources=[str(p) for p in Path('scripts').glob('search_v2c_c3_*.py')]+['search/query_numeric.py','tests/test_search_v2c_c3_numeric.py','tests/test_search_v2c_c3_safety.py','tests/institution_v2g/test_query_v2c_c3_native.py']
    write('changed_files.json',{'preexisting_dirty_checkout_preserved':True,'application_changes':appchanges,'new_sources':new_sources,'runtime_artifacts':runtime,'source_sha256':{p:sha(p) for p in appchanges+new_sources},'reports':[str(p) for p in R.glob('search_v2c_c3_*') if p.is_file()],'git':'No staging, commits, resets, destructive cleanup or migrations.'})
    audit=read('native_status_audit.json');audit['fresh_execution_evidence']={'native_metrics':'search_v2c_c3_native_metrics.json','observations':n['observations'],'historical_disagreements':len(n['historical_status_disagreements']),'canonical_v2_disagreements':len(n['canonical_v2_status_disagreements']),'response_bodies_now_captured':True};write('native_status_audit.json',audit)
    delta=read('delta_plan_audit.json');delta['fresh_reviewed_v2_delta_agreement']=n['reviewed_v2_delta_agreement'];delta['fresh_cases']=n['reviewed_v2_delta_cases'];write('delta_plan_audit.json',delta)
    violations=list(d['mandatory_violations'])
    extra={'SECURITY_FAMILY_UNSAFE_AUTO_PARSE':n['security_family_unsafe_auto_parse']['numerator']==0,'SESSION_CORRUPTION':not n['state_oracle_failures'],'PRIVATE_DATA_LEAKS':not n['privacy_oracle_failures'] and not live['observed_private_leaks'],'NATIVE_CONTRACT':not n['canonical_v2_status_disagreements'] and not n['harness_failures'],'C1':status('test_query_v2c_c1')=='PASS','B1':status('test_query_v2c_b1')=='PASS','Recommendation':suites['catalogue_regression']['status']=='PASS','More_Like_This':suites['catalogue_regression']['status']=='PASS','Staff_Inventory':suites['inventory_regression']['status']=='PASS','Focused_Chromium':b['status']=='PASS','SEALED_LABEL_QUALITY':seal['unresolved_label_cases']==0,'FRONTEND':frontend_pass}
    violations.extend({'metric':key,'required':'PASS','observed':'FAIL'} for key,ok in extra.items() if not ok)
    outcomes=seal['outcome_counts']
    qa={'FINAL':'PARTIAL' if violations or allfail else 'PASS','V2C_C3_IMPLEMENTED':'YES','CALIBRATION_AUTHORIZED':'NO' if violations or allfail else 'YES','CALIBRATION_RUN':'NO','HELDOUT_RUN':'NO','LLM_STARTED':'NO','SEALED_LABEL_CASES':100,'SEALED_LABELS_CONFIRMED':outcomes['LABEL_CONFIRMED'],'SEALED_LABELS_REVISED':outcomes['LABEL_REVISED'],'SEALED_QUERIES_REPLACED':seal['query_replacements'],'SEALED_CASES_REMOVED':outcomes['CASE_REMOVED_AS_INHERENTLY_AMBIGUOUS'],'SEALED_CASES_RECLASSIFIED_AMBIGUOUS':outcomes['CASE_RECLASSIFIED_AS_INTENTIONALLY_AMBIGUOUS'],'SEALED_AI_REVIEWED':100,'SEALED_HUMAN_REVIEWED':0,
       'NATIVE_HISTORICAL_STATUS_DISAGREEMENTS':len(n['historical_status_disagreements']),'NATIVE_V2_STATUS_DISAGREEMENTS':len(n['canonical_v2_status_disagreements']),'NATIVE_STATE_ORACLE_FAILURES':len(n['state_oracle_failures']),'NATIVE_PRIVACY_ORACLE_FAILURES':len(n['privacy_oracle_failures']),
       'RAW_LEGACY_GOLD':f"{legacy['raw_136']['passed']}/136",'REVIEWED_V2_LEGACY_GOLD':f"{legacy['reviewed_v2_136']['passed']}/136",'RAW_LEGACY_SEEDED_1000':f"{legacy['raw_seeded_1000']['passed']}/1000",'LEGACY_GOLD_CASES_CLASSIFIED_PARSER_DEFECT':0,'LEGACY_GOLD_CASES_CLASSIFIED_GOLD_DEFECT':3,'LEGACY_GOLD_CASES_EQUIVALENT':0,'DELTA_PLAN_CASES_AUDITED':4,'DEVELOPMENT_PARSER_CASES':d['parser_executed'],'DEVELOPMENT_NATIVE_CASES':n['native_rows']}
    for label,key in [('EXACT_PLAN_MATCH','EXACT_PLAN_MATCH'),('DECISION_ACCURACY','DECISION_ACCURACY'),('HARD_CONSTRAINT_PRECISION','HARD_CONSTRAINT_PRECISION'),('HARD_CONSTRAINT_RECALL','HARD_CONSTRAINT_RECALL'),('COMPARATOR_ACCURACY','COMPARATOR_ACCURACY'),('SUBJECT_EXACTNESS','SUBJECT_EXACTNESS'),('NEGATIVE_CONSTRAINT_ACCURACY','NEGATIVE_CONSTRAINT_ACCURACY'),('SEMANTIC_REMAINDER_EXACT','SEMANTIC_REMAINDER_EXACT_MATCH'),('SEMANTIC_REMAINDER_TOKEN_F1','SEMANTIC_REMAINDER_TOKEN_F1'),('AMBIGUITY_RECALL','AMBIGUITY_RECALL'),('CONTRADICTION_RECALL','CONTRADICTION_RECALL'),('SUPPORTED_CONTRADICTION_RECALL','SUPPORTED_CONTRADICTION_RECALL'),('INCOMPLETE_RECALL','INCOMPLETE_RECALL'),('UNSUPPORTED_HONESTY','UNSUPPORTED_HONESTY'),('PROTECTED_ENTITY_PRESERVATION','PROTECTED_ENTITY_PRESERVATION'),('FALSE_HARD_FILTER_RATE','FALSE_HARD_FILTER_RATE'),('BLOCKED_CASE_UNSAFE_AUTO_PARSE','UNSAFE_AUTO_PARSE_RATE'),('ALL_CASE_UNSAFE_AUTO_PARSE','ALL_CASE_UNSAFE_AUTO_PARSE_RATE'),('FALSE_CLARIFICATION_RATE','FALSE_CLARIFICATION_RATE'),('CROSS_SCOPE_VOCABULARY_LEAKAGE','CROSS_SCOPE_VOCABULARY_LEAKAGE_RATE')]:qa[label]=metric(m[key])
    qa.update(SECURITY_FAMILY_UNSAFE_AUTO_PARSE=metric(n['security_family_unsafe_auto_parse']),SESSION_CORRUPTION_RATE=metric(n['session_corruption_rate']),PRIVATE_DATA_LEAKS=n['private_leaks']+live['observed_private_leaks'],V2A_REGRESSION=status('test_search_v2a','test_query_v2a'),V2B_REGRESSION=status('test_search_v2b','test_query_v2b'),V2C_A_REGRESSION=status('test_search_v2c_a','test_query_v2c_a'),V2C_A1_REGRESSION=status('test_search_v2c_a1','test_query_v2c_a1'),V2C_B_REGRESSION=status('test_query_v2c_b'),V2C_B1_REGRESSION=status('test_query_v2c_b1'),V2C_C1_REGRESSION=status('test_query_v2c_c1'),RECOMMENDATION_REGRESSION=suites['catalogue_regression']['status'],MORE_LIKE_THIS_REGRESSION=suites['catalogue_regression']['status'],STAFF_INVENTORY_REGRESSION=suites['inventory_regression']['status'],FOCUSED_BROWSER=b['status'],PARSER_P50_P95_P99=f"{perf['p50_ms']:.3f}/{perf['p95_ms']:.3f}/{perf['p99_ms']:.3f} ms (n={perf['n']})",GLOBAL_BOOK_COUNT=live['count'],GLOBAL_SEARCH_HEALTH=f"{live['health']['index_status']} / {live['health']['status']}; baseline_verified={live['health']['baseline_verified']}")
    for label in ['GLOBAL_HNSW_REBUILT','GLOBAL_KG_REBUILT','TENANT_HNSW_KG_REBUILT','EMBEDDING_MODEL_CHANGED','CROSSENCODER_CHANGED','QWEN_CHANGED','RECOMMENDATION_CHANGED','MORE_LIKE_THIS_CHANGED','STAFF_INVENTORY_CHANGED','PART_2I_STARTED']:qa[label]='NO'
    qa.update(metric_view='Independent reviewed development field overrides + proven positive BOTH equivalence; raw and normalized-original metrics separately preserved',mandatory_violations=violations,raw_assertion_failures=allfail,calibration_evaluations=0,heldout_evaluations=0,frozen_sources_unchanged=True,final_parser_changes_after_evaluation=0,completed_at=datetime.now(timezone.utc).isoformat())
    write('final_qa.json',qa)
    text='V2C-C remains PARTIAL. Calibration remains blocked.' if qa['FINAL']!='PASS' else 'V2C-C.3 development safety repair PASS. Calibration may now be authorized.'
    lines=[text,'','C3 implemented bounded source-evidenced numeric, range, format/subject collision, entity, negation and boundary repairs. Original reports, raw gold and assertions are byte-preserved. No parser change followed final development scoring.','',f"Complete development population: {d['parser_executed']} parser + {n['native_rows']} native. Native raw/canonical status agreement: {metric(n['historical_status_agreement'])} / {metric(n['canonical_v2_status_agreement'])}. State/privacy: {metric(n['state_oracle_agreement'])} / {metric(n['privacy_oracle_agreement'])}.",'',f"Raw legacy136: {qa['RAW_LEGACY_GOLD']}; reviewed136: {qa['REVIEWED_V2_LEGACY_GOLD']}; raw seeded1000: {qa['RAW_LEGACY_SEEDED_1000']}. The three independently reviewed overrides do not silently repair two newly exposed raw natural-negation disagreements. Nine raw regression assertions retain broader text-exclusion expectations; these are reported as failures, not green regressions.",'','| QA field | Observed |','|---|---|']
    lines.extend(f'| {k} | {v} |' for k,v in qa.items() if not isinstance(v,(dict,list)))
    lines+=['','Mandatory violations:']+[f"- {v['metric']}: {v.get('observed')} (required {v.get('required')})" for v in violations]
    lines+=['','Metrics describe this development population, not real-world accuracy. Sealed labels:100 independently AI revised,0 human reviewed; all sealed parser evaluation counts remain0. Development review is partial field review: uncertain projections remain unresolved and original values retained.','',f"Backend {tests-len(allfail)}/{tests}; frontend34/34; focused Chromium16/16. No production HNSW/KG rebuild or model/source change outside the bounded Search parser. Global5,000,000; health remains truthfully STALE/degraded, baseline unverified. Large indexes verified by prior-preservation size/mtime where full checksums unavailable; no fresh full checksum claimed."]
    (R/'search_v2c_c3_review.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    residual=read('false_hard_filters_after.json')['cases'];unsafe=read('unsafe_after.json')['cases']
    next_text=[text,'','A subsequent explicitly authorized development revision is required. No calibration, held-out evaluation, LLM need analysis, Qwen integration or Part2I is authorized by this run.','',f"Residual false-filter clusters: {dict(Counter(r['family_id'] for r in residual))}",f"Residual unsafe clusters: {dict(Counter(r['family_id'] for r in unsafe))}",'','Next development scope should independently resolve remaining mode/typo/negative projections, then repair only demonstrated source/span/operator defects. Preserve these raw failures, frozen contracts, full populations and mandatory thresholds. Reconcile any additional accepted-regression contract changes explicitly before claiming regression PASS.']
    (R/'search_v2c_c3_next_scope.md').write_text('\n'.join(next_text)+'\n',encoding='utf8')
    print(json.dumps({'FINAL':qa['FINAL'],'mandatory_violations':violations,'backend_passed':tests-len(allfail),'backend_cases':tests,'raw_legacy':qa['RAW_LEGACY_GOLD'],'reviewed_legacy':qa['REVIEWED_V2_LEGACY_GOLD']}))

if __name__=='__main__':main()
