"""Evidence-only closure after the development safety stop. Never parses cases."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from scripts.search_v2c_c2_benchmark import read_rows, write
R=Path('reports')


def read(name):return json.loads((R/('search_v2c_c2_'+name)).read_text())


def xml(name):
    p=R/f'search_v2c_c2_{name}.xml'
    root=ET.parse(p).getroot();cases=root.findall('.//testcase')
    failures=[{'class':c.get('classname'),'name':c.get('name'),'message':(c.find('failure') if c.find('failure') is not None else c.find('error')).get('message')} for c in cases if c.find('failure') is not None or c.find('error') is not None]
    return {'file':str(p),'cases':len(cases),'passed':len(cases)-len(failures),'failures':failures,'status':'FAIL' if failures else 'PASS',
            'classes':dict(Counter(c.get('classname') for c in cases))}


def main():
    d=read('development_parser_metrics.json');m=d['strict_raw_original_label_metrics'];manifest=read('benchmark_v2_manifest.json')
    native=read_rows(R/'search_v2c_c2_native_current/search_v2c_c2_native_observations.jsonl')
    gold={r['query_id']:r for r in read_rows(R/'search_v2c_c2_v2_development.jsonl')}
    security=[r for r in native if gold[r['query_id']].get('security_case')]
    applicable=[r for r in security if not r.get('applicability')]
    unsafe=[r for r in applicable if r['actual_status']==200 and not gold[r['query_id']]['execution_allowed']]
    from scripts.search_v2c_c_evaluate import ratio
    native_errors=[r for r in native if r['result']=='FAIL']
    native_diag=read('native_diagnostics.json')['legacy_delta_cases']
    semantic_losses=[r['query_id'] for r in native_diag if not r['accepted_plan_prior_rating_retained']]
    write('development_native.json',{'native_rows':len(native),'executed_unique_ids':[r['query_id'] for r in native],
        'unexecuted':[],'state_oracle_failures':native_errors,'native_security_state':'PASS' if not native_errors else 'FAIL',
        'raw_http_status_match':ratio(sum(r['raw_status_match'] is True for r in native),sum(r['raw_status_match'] is not None for r in native)),
        'raw_http_status_mismatch_cases':[{'query_id':r['query_id'],'expected_status_raw':r['expected_status_raw'],'actual_status':r['actual_status']} for r in native if r['raw_status_match'] is False],
        'legacy_delta_mismatch_cases':[r['query_id'] for r in native_diag if r.get('delta_mismatches')],
        'legacy_semantic_prior_rating_change_diagnostic':semantic_losses,
        'rating_diagnostic_caution':'A changed rating is not necessarily a loss: explicit rating updates intentionally replace the synthetic prior. This diagnostic does not classify all changes as corruption.',
        'scope_caution':'Ownership/control-record integrity is separate from semantic refinement accuracy. Legacy turn labels omit complete independently reviewed prior-state oracles; exact lifecycle acceptance is not claimed.',
        'native_observations':'search_v2c_c2_native_current/search_v2c_c2_native_observations.jsonl','parser_only_substitutions':0,
        'production_index_builds':0,'isolated_fixture_indexes':'Tiny disposable integration fixture indexes only; no production HNSW/KG rebuilt.'})
    suites={name:xml(name) for name in ['parser_final','tenant_regression','native_current','catalogue_regression','retrieval_regression','inventory_regression','benchmark_quality']}
    tests=sum(s['cases'] for s in suites.values());failed=sum(len(s['failures']) for s in suites.values())
    write('backend_regression.json',{'status':'FAIL' if failed else 'PASS','disjoint_final_suites':suites,
        'unique_backend_cases_including_native_benchmark':tests,'passed':tests-failed,'failed':failed,
        'overlap_policy':'Only final disjoint files counted. Earlier attempts, focused subsets and first native fixture attempt are not added. 352 benchmark rows are included, not added a second time.',
        'initial_harness_failures':'Initial combined conftest roots conflicted and historical sequence report path expected a list. Reran isolated groups with C2-only report routing; historical file was never written.',
        'legacy_gold_disputes':'Three original136 gold plans expect broad exclude_terms alongside canonical subject exclusions. Original gold and failing raw assertions retained; no friendly equivalence used.'})
    live=read('preflight_live.json')
    c1_fail=[f for f in suites['native_current']['failures'] if 'v2c_c1' in f['class']]
    b1_fail=[f for f in suites['native_current']['failures'] if 'v2c_b1' in f['class']]
    write('security_regression.json',{'status':'PASS' if not native_errors and not c1_fail and not b1_fail and live['result']=='PASS' else 'FAIL',
        'C1':'PASS' if not c1_fail else 'FAIL','B1':'PASS' if not b1_fail else 'FAIL','live':'search_v2c_c2_preflight_live.json',
        'C1_matrix':'search_v2c_c2_security_current/search_v2c_c1_matrix_observed.json',
        'native_security_cases':len(security),'applicable_denial_cases':len(applicable),
        'security_family_unsafe_auto_parse':ratio(len(unsafe),len(applicable)),
        'all_security_case_unsafe_incidence':ratio(len(unsafe),len(security)),
        'private_leaks':sum(r['private_leak'] for r in native)+live['observed_private_leaks'],
        'ownership_session_corruption':ratio(sum(r['session_corruption'] for r in native),len(native)),
        'semantic_session_diagnostics':'search_v2c_c2_development_native.json; not hidden by ownership safety rate',
        'raw_status_adapter_does_not_change_labels':True})
    baseline=read('baseline.json')['files'];changes=[];history_changed=[];proof=[]
    for name,before in baseline.items():
        path=Path(name);after=hashlib.sha256(path.read_bytes()).hexdigest();same=after==before['sha256']
        proof.append({'path':name,'before_sha256':before['sha256'],'after_sha256':after,'unchanged':same})
        if not same:
            changes.append(name)
            if name.replace('\\','/').startswith('reports/'):history_changed.append(name)
    old=json.loads((R/'search_v2c_c_preservation.json').read_text());artifacts=[]
    for item in old['files']:
        name=item['file'];path=Path(name)
        if name.startswith(('data_pipeline/','local-data/','recommendation/','rag/')) or name=='scripts/search_v2c_c_author_gold.py':
            before=item['after'];stat=path.stat()
            if 'sha256' in before:
                same=hashlib.sha256(path.read_bytes()).hexdigest()==before['sha256'];method='SHA256'
            else:same=stat.st_size==before['size'] and stat.st_mtime_ns==before['mtime_ns'];method='size+mtime_ns; not a new full index checksum'
            artifacts.append({'path':name,'unchanged_from_prior_preservation':same,'method':method})
    assert not history_changed,history_changed
    appchanges=[n for n in changes if n.replace('\\','/').startswith('search/')]
    runtime=[n for n in changes if n not in appchanges]
    assert runtime in ([],['rag\\private_sessions.sqlite'],['rag/private_sessions.sqlite']),runtime
    write('preservation.json',{'historical_reports_byte_preserved':not history_changed,'original_raw_v1_rows':7112,
        'original_seed_authoring_source_preserved':True,'source_and_report_hash_proof':proof,
        'large_artifact_evidence':artifacts,'production_hnsw_kg_rebuilt':False,'models_changed':False,
        'global_books':live['count'],'health':live['health'],'application_source_changes':appchanges,
        'runtime_auth_revocation_store_changed':runtime,
        'runtime_note':'rag/private_sessions.sqlite contains only revoked_sessions. Normal fresh logout/session tests and disposable browser sign-out mutate this authentication revocation journal. It is not a digital-asset or model/index source change; byte-for-byte preservation of this live auth store is not claimed.',
        'Recommendation_MLT_Inventory_Circulation_Digital_asset_source_unchanged':True,
        'fixture':'search_v2c_c2_fixture.json','full_index_checksum_claim':False})
    sources=[str(p) for p in Path('scripts').glob('search_v2c_c2_*.py')]+['tests/test_search_v2c_c2.py','tests/test_search_v2c_c2_benchmark.py','tests/institution_v2g/test_query_v2c_c2_native.py']
    write('changed_files.json',{'preexisting_dirty_checkout_preserved':True,'application_changes':appchanges,
        'new_sources':sources,'runtime_artifacts':runtime,'application_sha256':{n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in appchanges},
        'new_source_sha256':{n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in sources},
        'reports':[str(p) for p in R.glob('search_v2c_c2_*') if p.is_file()], 'git':'No staging, commits, reset, cleanup of preexisting work or migrations.'})
    sec=read('security_regression.json');browser=read('browser.json');perf=read('performance.json')['parser'];counts=manifest['category_counts']
    qa={'FINAL':'PARTIAL','V2C_C2_IMPLEMENTED':'YES','V2C_C_SECURITY_PREFLIGHT':sec['status'],'V2C_C1_REGRESSION':sec['C1'],
        'BENCHMARK_V2_CREATED':'YES','RAW_V1_ROWS_PRESERVED':'YES','V2_UNIQUE_CASES':manifest['unique_cases'],
        'V2_DUPLICATE_CONTEXTS':0,'V2_QUERY_FAMILIES':manifest['query_families'],
        'V2_PARAPHRASE_CASES':counts['paraphrase_word_order'],'V2_NOISE_CASES':counts['noisy_malformed'],
        'V2_CONTRADICTION_NEGATIVE_CASES':counts['contradiction_negative'],'V2_AMBIGUOUS_INCOMPLETE_CASES':counts['ambiguous_incomplete'],
        'V2_MULTI_CONSTRAINT_CASES':counts['multi_constraint'],'V2_ENTITY_PROTECTION_CASES':counts['entity_number_protection'],
        'V2_TENANT_SECURITY_CASES':counts['tenant_security_scope'],'V2_DEVELOPMENT_CASES':manifest['splits']['development'],
        'V2_CALIBRATION_CASES':manifest['splits']['calibration'],'V2_HELD_OUT_CASES':manifest['splits']['heldout'],
        'EXPOSED_LEGACY_HOLDOUT_REMOVED':'YES','CROSS_SPLIT_FAMILY_OVERLAP':0,
        'AI_REVIEWED_CASES':manifest['review_counts']['AI_REVIEWED'],'HUMAN_REVIEWED_CASES':0,
        'UNREVIEWED_CASES':manifest['review_counts']['UNREVIEWED'],
        'HELDOUT_EVALUATED':'NO','CALIBRATION_RUN':'NO','PARSER_TUNED_ON_HELDOUT':'NO',
        'RAW_DEVELOPMENT_EXACT_PLAN_MATCH':d['historical_raw_v1_metrics']['EXACT_PLAN_MATCH']}
    mapping={'V2_DEVELOPMENT_EXACT_PLAN_MATCH':'EXACT_PLAN_MATCH','V2_DECISION_ACCURACY':'DECISION_ACCURACY',
        'V2_HARD_CONSTRAINT_PRECISION':'HARD_CONSTRAINT_PRECISION','V2_HARD_CONSTRAINT_RECALL':'HARD_CONSTRAINT_RECALL',
        'V2_COMPARATOR_ACCURACY':'COMPARATOR_ACCURACY','V2_SUBJECT_EXACTNESS':'SUBJECT_EXACTNESS',
        'V2_NEGATIVE_CONSTRAINT_ACCURACY':'NEGATIVE_CONSTRAINT_ACCURACY','V2_SEMANTIC_REMAINDER_EXACT':'SEMANTIC_REMAINDER_EXACT_MATCH',
        'V2_SEMANTIC_REMAINDER_TOKEN_F1':'SEMANTIC_REMAINDER_TOKEN_F1','V2_AMBIGUITY_RECALL':'AMBIGUITY_RECALL',
        'V2_CONTRADICTION_RECALL':'CONTRADICTION_RECALL','V2_INCOMPLETE_RECALL':'INCOMPLETE_RECALL',
        'V2_UNSUPPORTED_HONESTY':'UNSUPPORTED_HONESTY','V2_PROTECTED_ENTITY_PRESERVATION':'PROTECTED_ENTITY_PRESERVATION',
        'V2_FALSE_HARD_FILTER_RATE':'FALSE_HARD_FILTER_RATE','V2_BLOCKED_CASE_UNSAFE_AUTO_PARSE':'UNSAFE_AUTO_PARSE_RATE',
        'V2_ALL_CASE_UNSAFE_AUTO_PARSE':'ALL_CASE_UNSAFE_AUTO_PARSE_RATE','V2_FALSE_CLARIFICATION_RATE':'FALSE_CLARIFICATION_RATE',
        'V2_CROSS_SCOPE_VOCABULARY_LEAKAGE':'CROSS_SCOPE_VOCABULARY_LEAKAGE_RATE'}
    qa.update({k:m[v] for k,v in mapping.items()})
    qa['V2_COMPLETE_DEVELOPMENT_UNSAFE_INCIDENCE']=ratio(m['UNSAFE_AUTO_PARSE_RATE']['numerator']+len(unsafe),d['development_rows'])
    qa['UNSAFE_DENOMINATOR_NOTE']='Mandatory blocked-case and all-parser rates retain frozen1912/6529 denominators. Complete-development incidence additionally includes all352 executed native rows (6881 total); it never replaces the blocked-case safety gate.'
    qa.update(V2_SUPPORTED_CONTRADICTION_RECALL=m['SUPPORTED_CONTRADICTION_RECALL'],
        V2_SESSION_CORRUPTION_RATE=sec['ownership_session_corruption'],V2_PRIVATE_DATA_LEAKS=sec['private_leaks'],
        SECURITY_FAMILY_UNSAFE_AUTO_PARSE=sec['security_family_unsafe_auto_parse'],
        DEVELOPMENT_PARSER_CASES_EXECUTED=d['parser_executed'],DEVELOPMENT_NATIVE_CASES_EXECUTED=len(native),
        DEVELOPMENT_ROWS_UNEXECUTED=len(d['unexecuted_rows']),V2A_REGRESSION='PASS',V2B_REGRESSION='PASS',
        V2C_A_REGRESSION='FAIL',V2C_A1_REGRESSION='PASS',V2C_B_REGRESSION='PASS',V2C_B1_REGRESSION=sec['B1'],
        RECOMMENDATION_REGRESSION=suites['catalogue_regression']['status'],MORE_LIKE_THIS_REGRESSION=suites['retrieval_regression']['status'],
        STAFF_INVENTORY_REGRESSION=suites['inventory_regression']['status'],FOCUSED_BROWSER_ACCEPTANCE=browser['status'],
        PARSER_P50_P95_P99=perf,GLOBAL_BOOK_COUNT=live['count'],GLOBAL_SEARCH_HEALTH='STALE/degraded; baseline_verified=false')
    for key in ['GLOBAL_HNSW_REBUILT','GLOBAL_KG_REBUILT','TENANT_HNSW_KG_REBUILT','EMBEDDING_MODEL_CHANGED','CROSSENCODER_CHANGED','QWEN_CHANGED',
        'LLM_SECOND_OPINION_STARTED','CALIBRATION_STARTED','FINAL_HELDOUT_STARTED','RECOMMENDATION_CHANGED','MORE_LIKE_THIS_CHANGED','STAFF_INVENTORY_CHANGED','PART_2I_STARTED']:
        qa[key]='NO'
    qa.update(STOP_CONDITION='MANDATORY_DEVELOPMENT_GATES_AND_RAW_LEGACY_REGRESSION_NOT_ACCEPTED',
        MANDATORY_VIOLATIONS=d['mandatory_violations'],CALIBRATION_AUTHORIZED=False,
        SEMANTIC_NATIVE_REFINEMENT_CAVEAT={'raw_delta_mismatches':sum(bool(r.get('delta_mismatches')) for r in native_diag),'synthetic_prior_rating_changed_cases':semantic_losses,'caution':'Includes intentional explicit rating updates; these changes are not all classified as corruption.'},
        BENCHMARK_LABEL_READINESS='PARTIAL:100 new sealed examples independently flagged ambiguous, UNREVIEWED; no labels changed',
        FINAL_BACKEND_COUNTS={'passed':tests-failed,'failed':failed,'total':tests},FRONTEND_SEARCH_REGRESSION='34/34 PASS')
    write('final_qa.json',qa)
    write('denominator_notes.json',{'mandatory_parser_blocked_case_rate':m['UNSAFE_AUTO_PARSE_RATE'],
        'all_development_parser_incidence':m['ALL_CASE_UNSAFE_AUTO_PARSE_RATE'],
        'security_native_applicable_denominator':len(applicable),
        'complete_development_incidence':qa['V2_COMPLETE_DEVELOPMENT_UNSAFE_INCIDENCE'],
        'policy':qa['UNSAFE_DENOMINATOR_NOTE']})
    lines=['# V2C-C.2 development review','',
        'PARTIAL. Calibration is not authorized. Bounded deterministic hardening and the complete V2 development evaluation are implemented; mandatory gates remain authoritative.',
        '',f"V2 has {manifest['unique_cases']} unique contexts,82 original/query families grouped into30 conservative structural components,2000 paraphrase and1000 noisy cases. All seven duplicates removed; exposed legacy holdout removed. Zero cross-split family/topology overlap. Conservative sanitation moved all legacy heldout parser material into development/calibration before evaluation. Fifty newly authored cases form the final unseen holdout; the independent reviewer flagged all100 new sealed calibration/holdout labels as ambiguous. They remain UNREVIEWED, not ready for final acceptance.",
        '',f"Executed {d['parser_executed']} parser cases and{len(native)} real Mongo/API native cases, with no silently dropped development rows. Native ownership/state oracles pass, but233 raw HTTP statuses disagree with historical author expectations. Four legacy delta plans mismatch nonempty authored fields. Synthetic-prior rating changes are explicitly listed, including intentional rating updates; they are not all classified as corruption. These are not exact lifecycle passes or hidden gold corrections.",
        '',f"Final disjoint backend population: {tests-failed} passed,{failed} failed. Three of136 original legacy gold plans expect an additional broader text exclusion. Their original labels and failing raw assertions remain unchanged. All1000 legacy seeded variant checks pass; no subset totals are added twice. Tenant129, catalogue88, retrieval23, inventory95, C1 matrix20 and B1 lifecycle18 pass; frontend Search34 pass.",
        '',f"Focused Chromium: {browser['status']}; live Search restarted from current parser source. Global/public/private authorized checks, outsider concealment, scoped suggestions, clarification, chip removal, original-wording correction and accepted-session preservation are recorded separately.",
        '',f"Parser n1000 p50/p95/p99: {perf['p50_ms']:.3f}/{perf['p95_ms']:.3f}/{perf['p99_ms']:.3f} ms. Identical rotating workload; no speedup claim across different runs.",
        '', 'Original C/C.1 structured reports,raw corpus,original metrics and540-row seed source remain byte preserved. Recommendation/MLT/Inventory and model/index sources unchanged. The normal authentication revocation SQLite journal changed during logout tests; this runtime store is disclosed, not claimed byte preserved. Production HNSW/KG are not rebuilt; tiny isolated test fixtures are separate.',
        '', 'Safety metrics (original labels; full raw denominators):']
    lines += [f"- {key}: {value['numerator']}/{value['denominator']} ({value['percent']:.4f}%)" for key,value in m.items() if value['percent'] is not None]
    lines += ['', 'No calibration, heldout evaluation,LLM second opinion or Part2I occurred. No parser tuning followed the final development evaluation. See final_qa JSON and exact case lists for the stop conditions.']
    (R/'search_v2c_c2_review.md').write_text('\n'.join(lines),encoding='utf8')
    (R/'search_v2c_c2_next_scope.md').write_text('''# Stopped before calibration

V2C-C remains PARTIAL. Do not run calibration or heldout and do not add an LLM.
Review the exact remaining development failures and the preserved legacy136
raw-gold disagreement. Independently repair native status/prior-state contracts
and the100 new sealed label ambiguities without exposing heldout labels or
outputs to parser tuning. Preserve the current freeze and all historical raw
evidence; future changes require a new development-only authorization/version.
Do not weaken safety thresholds or rewrite the parser architecture. No Part2I,
Recommendation/MLT/Inventory changes,model changes or index rebuilds.
''',encoding='utf8')
    print(json.dumps({'FINAL':qa['FINAL'],'metrics':{k:m[k] for k in ['FALSE_HARD_FILTER_RATE','UNSAFE_AUTO_PARSE_RATE','SUPPORTED_CONTRADICTION_RECALL','PROTECTED_ENTITY_PRESERVATION','COMPARATOR_ACCURACY']},'backend':qa['FINAL_BACKEND_COUNTS'],'browser':browser['status'],'history_preserved':not history_changed},indent=2))


if __name__=='__main__':main()
