"""Close the disabled parser repair with unchanged C5C metrics and both versions."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import ast,difflib,json,xml.etree.ElementTree as ET
from scripts.search_v2c_c5d_repair_prepare import R,P,load,sha,write

V2='search_v2c_c5d_repair_v2_'
def read(prefix,name):return load(R/(prefix+name))
def rows(path):return [json.loads(x) for x in Path(path).read_text(encoding='utf8').splitlines() if x.strip()]
def save_rows(name,data):
    with (R/(P+name)).open('x',encoding='utf8') as out:
        for r in data:out.write(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n')
def rate(n,d):return {'numerator':n,'denominator':d,'percent':100*n/d if d else None,'status':'MEASURED' if d else 'N/A'}
def main():
    pre=read(P,'preflight.json');vpre=read(V2,'preflight.json')
    for prefix in [P,V2]:
        f=read(prefix,'candidate_freeze.json');assert all(sha(p)==h for p,h in f['files'].items())
        cap=read(prefix,'prediction_complete.json');assert cap['parser_calls']==cap['captured']==644 and cap['errors']==cap['retries']==0
        assert not cap['isolation_denials'] and sha(R/(prefix+'predictions.jsonl'))==cap['prediction_sha256']
        val=read(prefix+'validation_','prediction_complete.json');assert val['parser_calls']==val['captured']==6 and val['errors']==val['retries']==0
    assert all(sha(p)==h for p,h in vpre['protected_files'].items())
    gold={r['case_id']:r for r in rows(R/'search_v2c_c5b_calibration_cases.jsonl')}
    baseline={r['case_id']:r for r in rows(R/'search_v2c_c5c_scored_observations.jsonl')}
    v1={r['case_id']:r for r in rows(R/(P+'scored_observations.jsonl'))}
    final={r['case_id']:r for r in rows(R/(V2+'scored_observations.jsonl'))}
    predictions={r['case_id']:r for r in rows(R/(V2+'predictions.jsonl'))}
    assert baseline.keys()==v1.keys()==final.keys() and len(final)==644
    versions={'C5C_BASELINE':'search_v2c_c5c_','REPAIR_V1':P,'REPAIR_V2':V2}
    metrics={name:read(prefix,'typed_decision_scoring.json') for name,prefix in versions.items()}
    for name,source in [('C5C_BASELINE',baseline),('REPAIR_V1',v1),('REPAIR_V2',final)]:
        m=metrics[name]['overall'];cases=list(source.values());false=sum(r['execution'] and not r['expected_execution'] for r in cases);missed=sum(not r['execution'] and r['expected_execution'] for r in cases)
        assert m['false_execution_rate']==rate(false,394) and m['missed_execution_rate']==rate(missed,250)
        assert m['typed_accuracy']==rate(sum(r['typed_correct'] for r in cases),644)
        assert m['execution_accuracy']==rate(sum(r['execution_correct'] for r in cases),644)
    transitions=[]
    for k,b in baseline.items():
        a=v1[k];c=final[k]
        transitions.append({'case_id':k,'scope':c['scope'],'stratum':c['stratum'],'gold_decision':c['expected_decision'],'gold_execution':c['expected_execution'],
            'baseline_decision':b['decision'],'baseline_execution':b['execution'],'v1_decision':a['decision'],'v1_execution':a['execution'],
            'v2_decision':c['decision'],'v2_execution':c['execution'],
            'v1_new_false_execution':not c['expected_execution'] and a['execution'] and not b['execution'],
            'v2_new_false_execution':not c['expected_execution'] and c['execution'] and not b['execution'],
            'v1_new_missed_execution':c['expected_execution'] and not a['execution'] and b['execution'],
            'v2_new_missed_execution':c['expected_execution'] and not c['execution'] and b['execution']})
    assert sum(r['v1_new_false_execution'] for r in transitions)==28 and sum(r['v1_new_missed_execution'] for r in transitions)==15
    assert sum(r['v2_new_false_execution'] for r in transitions)==sum(r['v2_new_missed_execution'] for r in transitions)==0
    save_rows('decision_transitions.jsonl',transitions)
    investigated=[]
    for row in transitions:
        if not row['v1_new_false_execution'] and not row['v1_new_missed_execution']:continue
        kind=row['gold_decision'];cause='Scoped quoted typo was newly treated as unsupported instead of using established bounded vocabulary repair.' if row['v1_new_missed_execution'] else {
          'AMBIGUOUS':'Repairing extraction removed an accidental prior block, but unresolved grouping/reference/mandatory-advisory evidence was not completely owned.',
          'INCOMPLETE':'A broad exclusion placeholder or unnamed additional operand was outside the initial missing-value inventory.',
          'UNSUPPORTED':'An explicit mandatory clause contained unowned metadata/operation content outside the initial field list.',
          'CONTRADICTORY':'Broad literal exclusion wording without an explicit text/word token was unowned.'}[kind]
        investigated.append({**row,'query_text':gold[row['case_id']]['query_text'],'root_cause':cause,
            'v2_resolution':'Unowned mandatory-clause guard, relationship inventory, owned literal extraction or scoped canonical repair.',
            'v2_no_unsafe_regression':not row['v2_new_false_execution'] and not row['v2_new_missed_execution'],
            'v1_evidence_retained':True,'not_independent_validation':True})
    save_rows('introduced_regression_investigation.jsonl',investigated)
    matrix=read(V2,'stratified_matrix.json')['cells'];basecells=read('search_v2c_c5c_','stratified_matrix.json')['cells']
    bcell={(r['scope'],r['stratum']):r for r in basecells};cells=[]
    for cell in matrix:
        b=bcell[cell['scope'],cell['stratum']]
        subset=[r for r in transitions if r['scope']==cell['scope'] and r['stratum']==cell['stratum']]
        assert len(subset)==cell['eligible']
        assert sum(r['v2_execution'] and not r['gold_execution'] for r in subset)==cell['false_execution_count']
        cells.append({'scope':cell['scope'],'stratum':cell['stratum'],'eligible':cell['eligible'],'new_core':cell['new_reviewed_core'],
            'retained_original':cell['retained_original'],'patterns':cell['independently_reviewed_meaningful_patterns'],
            'baseline_typed':rate(b['correct_typed'],b['eligible']),'candidate_typed':rate(cell['correct_typed'],cell['eligible']),
            'baseline_false_execution':b['false_execution_count'],'candidate_false_execution':cell['false_execution_count'],
            'baseline_missed_execution':b['missed_execution_count'],'candidate_missed_execution':cell['missed_execution_count'],
            'new_false_execution':sum(r['v2_new_false_execution'] for r in subset),'new_missed_execution':sum(r['v2_new_missed_execution'] for r in subset)})
    write('thirty_cell_comparison.json',{'cell_count':30,'contexts':644,'cells':cells,'all_candidates_used_for_development':True})
    comparisons={name:{'overall':m['overall'],'cohorts':m['cohorts'],'by_scope':m['by_scope'],'by_stratum':m['by_stratum']} for name,m in metrics.items()}
    write('baseline_candidate_comparison.json',{'versions':comparisons,'same_scoring_definitions':True,'same_gold_and_masks':True,
        'frozen_C5C_scorer_sha256':sha('scripts/search_v2c_c5c_score.py'),'primary_measurements_per_candidate_version':1,
        'all_primary_candidate_calls':1288,'additional_grouped_development_calls':12,'capture_errors':0,'capture_retries':0,
        'v1_exposure_used_for_v2_development':True,'independent_validation_claim':False})
    validpop=load(R/'search_v2c_c5d_validation_population.json');ids=set(validpop['ids'])
    dev={r['query_id']:r for r in rows(R/'search_v2c_c2_v2_development.jsonl') if r['query_id'] in ids}
    independent={}
    for prefix in [P,V2]:
        val=rows(R/(prefix+'validation_predictions.jsonl'))
        independent[prefix]={'contexts':6,'structural_groups':1,'topology_overlap_with_primary':0,'blocked_gold':0,
          'typed_accuracy':rate(sum(r['typed_decision']==dev[r['case_id']]['expected_decision'] for r in val),6),
          'execution_accuracy':rate(sum(r['executable'] is dev[r['case_id']]['execution_allowed'] for r in val),6),
          'false_execution':rate(0,0),'missed_execution':rate(sum(not r['executable'] for r in val),6)}
    write('independent_validation_limits.json',{'availability':'LIMITED_HISTORICAL_DEVELOPMENT_POSITIVES','versions':independent,
       'test_assertions_final_candidate':1380,'candidate_tests_are_not_independent_semantic_labels':True,
       'limitations':['Both versions developed after C5C errors/gold exposure.','V1 primary outcomes informed V2 repair; V2 gains are development measurements.',
         'Six independently reviewed DEVELOPMENT examples form one group and have no blocked cases.','No fresh independent safety/generalization or native integration claim.']})
    remaining=[r for r in final.values() if r['execution'] and not r['expected_execution']]
    assert len(remaining)==1 and remaining[0]['case_id']=='C5A-1-3-12'
    residual=[{'case_id':r['case_id'],'query_text':gold[r['case_id']]['query_text'],'gold_decision':r['expected_decision'],
              'candidate_decision':r['decision'],'baseline_also_executed':baseline[r['case_id']]['execution'],
              'cause':'Format/access mandatory-versus-advisory ownership is not included in the generalized uncertainty field inventory; ONLINE is marked resolved.',
              'next_need':'Extend field ownership across format/access and advisory intent with independently reviewed positive/negative cases; frozen candidate remains unchanged.'} for r in remaining]
    typed_remaining=[r for r in final.values() if not r['typed_correct']]
    write('remaining_blockers.json',{'false_execution':residual,'typed_errors':len(typed_remaining),
       'typed_error_pairs':dict(Counter(r['expected_decision']+' -> '+r['decision'] for r in typed_remaining)),
       'missing_notice_cases':[r['case_id'] for r in final.values() if r['expected_decision']=='EXECUTABLE_WITH_NOTICE' and r['decision']=='EXECUTABLE'],
       'remaining_typed_notice_shortfall':35,'strict_dimension_mismatch_contexts':read(V2,'scoring_complete.json')['strict_error_contexts'],
       'other_limits':['Semantic remainder exactness remains338/644; not all mismatches mean lost intent.',
         'Structured advisory objects and scope/actor prediction accuracy remain N/A under the frozen contract.',
         'Fifty retained intent-priority mismatches remain; no label/contract normalization was introduced.',
         'Native rendering/issuance of new grammar repairs and end-to-end private/public interactions were not rerun; candidate is disabled.'],
       'production_acceptance_blocked':True,'final_regression_candidate_available':True})
    regressions={'v1_new_false_execution':28,'v1_new_missed_execution':15,'v2_new_false_execution':0,'v2_new_missed_execution':0,
       'v2_CLEAR_EXECUTABLE_accuracy':metrics['REPAIR_V2']['by_stratum']['CLEAR_EXECUTABLE']['typed_accuracy'],
       'v2_SAFE_UNCERTAIN_EXECUTABLE_execution':rate(100,100),'v2_SAFE_UNCERTAIN_EXECUTABLE_typed_notice':rate(65,100),
       'v2_additional_missed_by_scope':{scope:sum(r['v2_new_missed_execution'] for r in transitions if r['scope']==scope) for scope in metrics['REPAIR_V2']['by_scope']},
       'v2_additional_false_by_scope':{scope:sum(r['v2_new_false_execution'] for r in transitions if r['scope']==scope) for scope in metrics['REPAIR_V2']['by_scope']},
       'five_revised_cases':[{k:r[k] for k in ['case_id','decision','execution','typed_correct']} for r in read(V2,'five_case_ambiguity_diagnostic.json')['cases']]}
    write('safety_regressions.json',regressions)
    runfiles=[P+'regression_attempt1.xml',P+'regression_attempt2.xml',P+'regression_final.xml',V2+'regression_attempt1.xml']
    runs=[]
    for name in runfiles:
        suite=next(ET.parse(R/name).getroot().iter('testsuite'))
        runs.append({'file':str(R/name),'sha256':sha(R/name),'tests':int(suite.attrib['tests']),'failures':int(suite.attrib['failures']),'errors':int(suite.attrib['errors'])})
    assert runs[-1]['tests']==1380 and runs[-1]['failures']==runs[-1]['errors']==0
    write('regression_accounting.json',{'runs':runs,'initial_targeted_assertions_passed':29,'final_v2_assertions_passed':1380,
       'v2_regression_final_xml':'Byte copy of v2 attempt1 result, not another execution.',
       'unit_parser_invocation_count':'Not instrumented; do not combine unit assertions with measured parser-context denominators.',
       'conceptual_pre_freeze_candidate_probes':7,'native_transformer_test_excluded':1,
       'original_assertions_and_gold_unchanged':True,'test_adapter':str(R/(P+'regression_adapter.json'))})
    changed=[];diffs=[]
    base_ns='scratch.search_v2c_c5d_repair_v2.candidate_search.'
    candidate=Path('scratch/search_v2c_c5d_repair_v2/candidate_search')
    reasons={'query_plan.py':'Disabled candidate identity and isolated module imports; public modes/data contracts retained.',
      'query_constraints.py':'Explicit literal ownership, canonical scoped typo recovery, availability/format-only coverage and author boundaries.',
      'query_numeric.py':'Source-backed exact-publication-year wording.',
      'query_repair.py':'Preserve topic during title composition and invoke isolated preparation/requirement safety checks.',
      'semantic_safety.py':'Bounded source-backed grammar repair, original span restoration, requirement inventory and deterministic clarification/unsupported/contradiction checks.'}
    for path in sorted(candidate.glob('*.py')):
        parent=Path('search')/path.name;new=path.read_text(encoding='utf8');old=parent.read_text(encoding='utf8') if parent.exists() else ''
        normalized=new.replace(base_ns,'search.')
        semantic_changed=ast.dump(ast.parse(normalized))!=ast.dump(ast.parse(old)) if old else True
        changed.append({'candidate_path':str(path),'sha256':sha(path),'production_parent':str(parent) if parent.exists() else None,
          'production_parent_sha256':sha(parent) if parent.exists() else None,'semantic_change_beyond_namespace':semantic_changed,
          'reason':reasons.get(path.name,'Unchanged logic copied to keep candidate imports isolated.'),'production_file_edited':False})
        if semantic_changed:diffs.extend(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=str(parent),tofile=str(path)))
    with (R/(P+'candidate_changes.patch')).open('x',encoding='utf8') as out:out.writelines(diffs)
    write('changed_files.json',{'candidate_files':changed,'production_edits':[],
        'v1_frozen_candidate_retained':True,'v2_frozen_candidate':str(R/(V2+'candidate_freeze.json')),
        'additional_files':'Only disabled candidate/tests and versioned repair orchestration/evidence under scratch/, scripts/search_v2c_c5d_repair* and reports/search_v2c_c5d_repair*.'})
    assert ast.dump(ast.parse(Path('search/query_calibration.py').read_text(encoding='utf8')))==ast.dump(ast.parse((candidate/'query_calibration.py').read_text(encoding='utf8')))
    changes=[p for p,h in vpre['protected_files'].items() if sha(p)!=h];assert not changes,changes
    for phase in ['c5a','c5b','c5c','c5d']:
        freeze=load(R/('search_v2c_'+phase+'_freeze_manifest.json'));assert all(sha(p)==h for p,h in freeze['files'].items())
    for directory in ['search','backend','frontend/src']:
        for path in Path(directory).rglob('*'):
            if path.suffix in ['.py','.ts','.tsx','.json']:
                assert 'search_v2c_c5d_repair' not in path.read_text(encoding='utf8',errors='replace'),path
    write('preservation.json',{'status':'PASS','protected_files_verified':len(vpre['protected_files']),'production_source_files':462,'protected_changes':changes,
       'C5A_C5B_C5C_prior_C5D_byte_preserved':True,'v1_candidate_and_scores_preserved':True,'active_C4_policy_unchanged':True,
       'C5C_prediction_sha256':sha(R/'search_v2c_c5c_predictions.jsonl'),'gold_sha256':sha(R/'search_v2c_c5b_expected_labels.jsonl'),
       'candidate_activation':'Disabled namespace; no production route/import/feature-flag wiring.',
       'native_privacy_and_scope':'Authorization/owner/workspace/correction transaction modules unchanged; pure capability/predicate tests passed. No fresh end-to-end native validation claim.',
       'heldout_content_decoded':0,'heldout_scored':0,'production_parser_executions':0,'model_inferences':0,'live_database_actions':0,
       'index_rebuilds':0,'resident_endpoint_repolls':0,'global_metadata':'5,000,000 prior observation; unchanged, not rescanned.',
       'last_known_health':'STALE/degraded, baseline_verified=False; no current-health inference.'})
    readiness={'status':'DISABLED_DEVELOPMENT_CANDIDATE_AVAILABLE_WITH_BLOCKERS','development_repair_assessment_complete':True,
       'production_activation_authorized':False,'independent_safety_acceptance':False,'production_ready':False,
       'next_phase_started':False,'next_boundary':'Separately authorized final regression/validation planning for the frozen candidate; resolve the remaining mandatory/advisory format ambiguity and notice gaps before any production acceptance.',
       'blockers':['One remaining unsafe recommendation: C5A-1-3-12.','35 missing typed notices and10 safe-but-wrong blocked typed classes remain.',
         'Semantic/operand mismatches remain under unchanged scoring; no blanket representation correction.',
         'Fresh structurally separated safety validation and candidate native integration/notice rendering still required.']}
    write('next_phase_readiness.json',readiness)
    overall=metrics['REPAIR_V2']['overall'];base=metrics['C5C_BASELINE']['overall']
    qa={'FINAL':'PASS','meaning':'Completed auditable disabled development repair and regression assessment; not production safety or rollout approval.',
       'FINAL_CANDIDATE':'C5D-disabled-repair-v2','CANDIDATE_ACTIVATED':'NO','PRODUCTION_PARSER_CHANGED':'NO','ACTIVE_C4_POLICY_CHANGED':'NO',
       'C5A_C5B_C5C_PRIOR_C5D_PRESERVED':'YES','C5C_SCORER_AND_GOLD_CHANGED':'NO','SAME_CORPUS_USED_IN_DEVELOPMENT':'YES',
       'TOTAL_FROZEN_CONTEXTS':1024,'ELIGIBLE_CONTEXTS':644,'NEW_CORE_EVALUATED':594,'RETAINED_EVALUATED':50,'EXCLUDED_CONTEXTS':380,
       'PRIMARY_CANDIDATE_EVALUATIONS':{'v1':644,'v2':644,'total':1288},'SUPPLEMENTARY_DEVELOPMENT_EVALUATIONS':{'v1':6,'v2':6,'total':12},
       'CANDIDATE_RUNTIME_ERRORS':0,'CANDIDATE_CAPTURE_RETRIES':0,'PRODUCTION_PARSER_EVALUATIONS':0,
       'BASELINE_TYPED_ACCURACY':base['typed_accuracy'],'CANDIDATE_TYPED_ACCURACY':overall['typed_accuracy'],
       'BASELINE_EXECUTION_ACCURACY':base['execution_accuracy'],'CANDIDATE_EXECUTION_ACCURACY':overall['execution_accuracy'],
       'BASELINE_FALSE_EXECUTION':base['false_execution_rate'],'CANDIDATE_FALSE_EXECUTION':overall['false_execution_rate'],
       'BASELINE_MISSED_EXECUTION':base['missed_execution_rate'],'CANDIDATE_MISSED_EXECUTION':overall['missed_execution_rate'],
       'FINAL_NEW_FALSE_EXECUTION_REGRESSIONS':0,'FINAL_NEW_MISSED_EXECUTION_REGRESSIONS':0,
       'V1_NEW_FALSE_EXECUTION_REGRESSIONS_RETAINED':28,'V1_NEW_MISSED_EXECUTION_REGRESSIONS_RETAINED':15,
       'NEW_CORE_TYPED_ACCURACY':metrics['REPAIR_V2']['cohorts']['NEW_REVIEWED_CORE']['typed_accuracy'],
       'NEW_CORE_EXECUTION_ACCURACY':metrics['REPAIR_V2']['cohorts']['NEW_REVIEWED_CORE']['execution_accuracy'],
       'RECOGNITION':{kind:overall['per_decision'][kind]['recall'] for kind in ['AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY','EXECUTABLE_WITH_NOTICE']},
       'CLEAR_EXECUTABLE_TYPED_ACCURACY':metrics['REPAIR_V2']['by_stratum']['CLEAR_EXECUTABLE']['typed_accuracy'],
       'SAFE_UNCERTAIN_EXECUTABLE_EXECUTION':rate(100,100),'FIVE_REVISED_AMBIGUITY_RECOGNITION':rate(5,5),
       'REGRESSION_ASSERTIONS_PASSED':1380,'REGRESSION_ASSERTIONS_FAILED_FINAL':0,
       'SCOPE_ACTOR_PREDICTION_ACCURACY':'N/A: supplied context; native authorization stays external and unchanged.',
       'NATIVE_HARNESS_RERUN':'NO','PRIVATE_PUBLIC_ISOLATION':'Active boundaries preserved by hashes; candidate scoped offline cases assessed. End-to-end candidate native validation not performed.',
       'STRUCTURED_ADVISORY_ACCURACY':'N/A under unchanged C5C oracle.','THIRTY_CELL_REPORT':str(R/(P+'thirty_cell_comparison.json')),
       'REMAINING_FALSE_EXECUTION_IDS':['C5A-1-3-12'],'REMAINING_TYPED_ERRORS':46,'REMAINING_STRICT_DIMENSION_MISMATCH_CONTEXTS':504,
       'INDEPENDENT_VALIDATION':'Limited six historical reviewed positives, one complete structural group; no generalization/safety acceptance.',
       'PRODUCTION_SOURCE_HASH_VERIFICATION':'PASS (462 files)','PROTECTED_EVIDENCE_HASH_VERIFICATION':f"PASS ({len(vpre['protected_files'])} protected entries)",
       'SEALED_HELDOUT_HASH_UNCHANGED':'YES','THRESHOLD_FITTING_PERFORMED':'NO','POLICY_SELECTED':'NO','POLICY_ACTIVATED':'NO',
       'HELDOUT_EVALUATIONS':0,'HNSW_REBUILDS':0,'KG_REBUILDS':0,'MONGO_MUTATIONS':0,'QWEN_INFERENCES':0,'C5E_STARTED':'NO',
       'NEXT_PHASE_READINESS':readiness['status']}
    write('final_qa.json',qa)
    def rt(r):return f"{r['numerator']}/{r['denominator']} ({r['percent']:.2f}%)" if r['denominator'] else 'N/A'
    lines=['# C5D targeted parser repair — disabled candidate v2','',
      'FINAL: PASS for completed, auditable development repair/regression assessment. The candidate remains disabled and is not certified production-safe or authorized for rollout. One known unsafe recommendation remains.','',
      '## Implementation and isolation','',
      'The candidate lives under scratch/search_v2c_c5d_repair_v2/candidate_search. Production search/, active C4 policy, native authorization, frontend, databases and indexes were not modified. Seven pure parser modules were copied into a separate namespace; only explicit candidate evaluators/tests can import it. The earlier frozen C5D investigation is preserved under its original names.','',
      'Confirmed repairs: explicit field owners can consume quoted category/negative operands while keeping literal interiors opaque; title extraction preserves separate topical text; format-only/borrow-now/publication equality grammar is recognized; bounded unique grammar/scoped canonical repairs retain source provenance; mandatory relationships, missing values and unowned mandatory clauses are inventoried; deterministic guards distinguish existing executable, notice, clarification, unsupported and contradiction outcomes. Cross-field exclusions use production normalization and whole-word boundaries, preserving the earlier Marsh/ar counterexample.','',
      'Actual semantic-change files are query_constraints.py, query_numeric.py, query_repair.py, semantic_safety.py and the candidate version identity in query_plan.py. query_confidence.py, query_session.py and query_calibration.py keep inherited logic in the disabled namespace. changed_files.json and candidate_changes.patch provide parents, hashes and reasons.','',
      '## Parser/policy and scoring contracts','',
      'The established enum already permits EXECUTABLE_WITH_NOTICE, and unchanged C4 assessment maps repair provenance to EXECUTE_WITH_NOTICE. The candidate adds a source-backed producer for bounded grammar/scoped canonical repairs. It does not relabel every EXECUTABLE output or change the C4 policy. Native rendering/choice issuance for these new repair types remains an integration-validation prerequisite.','',
      'The exact frozen C5C scorer is reused with output namespace redirection only. Normative labels, BOTH normalization, per-field masks and inapplicable/unknown/false distinctions are unchanged. Structured advisory-object accuracy and scope/actor prediction accuracy stay N/A. Strict intent/field-code representation concerns are not normalized away.','',
      '## Frozen measurements','',
      '| Version | Typed accuracy | Execution recommendation accuracy | False execution / blocked | Missed execution / executable |','|---|---:|---:|---:|---:|']
    for name,m in metrics.items():
        s=m['overall'];lines.append(f"| {name} | {rt(s['typed_accuracy'])} | {rt(s['execution_accuracy'])} | {rt(s['false_execution_rate'])} | {rt(s['missed_execution_rate'])} |")
    lines+=['',
      'The final new-core results are548/594 typed correct (92.26%) and593/594 execution recommendations correct (99.83%). Retained originals stay50/50 on both metrics. False executions resolve190 previous failures with no newly introduced false executions; all43 previous missed valid executions resolve with no new missed executions.','',
      'V1 was frozen and measured once, then preserved after it introduced28 new false executions and15 newly missed queries. All43 introduced regressions have individual investigations and safe V2 outcomes. V2 was separately frozen and measured once. These are iterative development measurements on an exposed corpus, not independent validation. No candidate was silently edited or rerun after its measurement.','',
      'Primary parser-context calls are644 per version (1,288 total), plus six structurally grouped development contexts per version (12 additional). There were zero capture runtime errors/retries. Candidate unit-test parser invocations are not conflated with these denominators.','',
      '## Thirty scope/decision cells','',
      '| Scope | Stratum | Eligible | Baseline typed | V2 typed | Baseline false → V2 | Baseline missed → V2 |','|---|---|---:|---:|---:|---:|---:|']
    for c in cells:lines.append(f"| {c['scope']} | {c['stratum']} | {c['eligible']} | {c['baseline_typed']['numerator']}/{c['eligible']} | {c['candidate_typed']['numerator']}/{c['eligible']} | {c['baseline_false_execution']} → {c['candidate_false_execution']} | {c['baseline_missed_execution']} → {c['candidate_missed_execution']} |")
    lines+=['','Every cell has zero new false-execution and missed-execution regressions. The private patron clear cell contains50 retained cases in addition to20 new core; they remain explicitly separate in machine-readable cohort results.','',
      '## Recognition and semantic/operand findings','',
      '| Gold class | Baseline recall | V2 recall |','|---|---:|---:|']
    for kind in ['AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY','EXECUTABLE_WITH_NOTICE']:
        lines.append(f"| {kind} | {rt(base['per_decision'][kind]['recall'])} | {rt(overall['per_decision'][kind]['recall'])} |")
    lines+=['','All150 clear-executable contexts receive the correct typed decision, including100 new core. All100 safe-uncertain cases remain executable;65/100 receive the required typed notice. All five revised author-association cases now receive AMBIGUOUS/false.','',
      '| Applicable operand/semantic metric | Baseline | V2 |','|---|---:|---:|']
    oldfields=read('search_v2c_c5c_','operand_scoring.json')['per_field'];newfields=read(V2,'operand_scoring.json')['per_field']
    for field in ['subjects','exclude_subjects','exclude_terms','author_text','title_text','formats','exclusive_formats','availability','year_min','year_max','semantic_text','protected_entities']:
        lines.append(f"| {field} | {rt(oldfields[field])} | {rt(newfields[field])} |")
    lines+=['','Do not equate near-perfect execution classification with complete semantic correctness:504 contexts still have at least one strict scored-dimension mismatch. Semantic remainder exactness is338/644; affected-field granularity, residual words, exclusions and the unchanged retained intent-priority contract remain material limitations. No blanket semantic-equivalence adapter was introduced.','',
      '## Regression, independent validation and native boundaries','',
      'Final V2 passes1,380 assertions:1,342 existing namespace-adapted parser/numeric/C4 reviewed legacy assertions plus38 targeted requirement/semantic cases. The original assertions and gold are unchanged; only parser namespace and repository-root resolution were adapted. One native-transformer-dependent test was excluded from the pure suite because it imports application/session/database code. Initial development failures and all regression-run logs/XML are retained.','',
      'Six pre-existing independently reviewed DEVELOPMENT positives occupy one complete structural group disjoint in operation topology from C5C. Candidate outputs were captured without gold, then scored separately. Results are in independent_validation_limits.json. These six positives cannot validate blocked safety or generalization. No fresh independent-labeling claim is made.','',
      'Public/private and patron/staff capability contexts are evaluated across all30 cells. Active native authority/owner/workspace/expiry/commit code is byte-preserved, and capability/EXACT/predicate/source-span tests pass. No native API, inventory action, suggestion issuance or transaction was executed. Candidate end-to-end native rendering/workflows and privacy acceptance remain unverified and must precede activation.','',
      '## Remaining blockers and next boundary','',
      'One unsafe recommendation remains: C5A-1-3-12. Its note leaves ONLINE access mandatory versus advisory unresolved, but the uncertainty inventory lacks format/access ownership and marks the format resolved. The baseline also executed this case; it is not a new regression. The frozen V2 candidate is retained unchanged rather than silently tuning another reported result.','',
      'Other remaining typed errors:35 missing typed notices, five ambiguous cases called incomplete, and five incomplete cases called unsupported. The latter ten remain safely non-executable. Remaining notice grammar and structured/advisory/field-code ownership require further focused work and validation. Confidence remains the inherited heuristic; no probability claim or threshold was added.','',
      'A disabled candidate and transparent evidence are ready for separately authorized final regression/validation planning, with these blockers carried forward. No production acceptance, deployment, policy selection/activation, heldout evaluation or C5E execution is authorized or performed.','',
      '## Preservation and exact evidence','',
      f"All {len(vpre['protected_files'])} protected entries pass, including462 production source files and every prior C5A/B/C/D freeze. C5B labels and C5C predictions retain their original SHA256. No endpoint repoll, Qwen call, Mongo mutation, HNSW/KG rebuild or unrelated UI/backend change occurred. Global5,000,000 and STALE/degraded baseline_verified=False remain recorded prior observations.",'',
      '| QA field | Actual |','|---|---|']
    for k,v in qa.items():lines.append('| '+k+' | '+(json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else str(v))+' |')
    lines+=['','Evidence:']
    for n in ['changed_files.json','candidate_changes.patch','baseline_candidate_comparison.json','thirty_cell_comparison.json','decision_transitions.jsonl',
       'introduced_regression_investigation.jsonl','safety_regressions.json','regression_accounting.json','independent_validation_limits.json','remaining_blockers.json',
       'preservation.json','next_phase_readiness.json','final_qa.json','freeze_manifest.json']:
        lines.append('- reports/'+P+n)
    lines+=['- reports/'+V2+'candidate_freeze.json','- reports/'+V2+'predictions.jsonl','- reports/'+V2+'failures.jsonl','- reports/'+V2+'operand_scoring.json']
    with (R/(P+'review.md')).open('x',encoding='utf8') as out:out.write('\n'.join(lines)+'\n')
    write('validation.json',{'status':'PASS','at_utc':datetime.now(timezone.utc).isoformat(),'primary_metrics_independently_recomputed':True,
       'new_regressions_individually_audited':43,'final_new_false_execution':0,'final_new_missed_execution':0,'thirty_cell_counts_verified':True,
       'v1_v2_candidate_freezes_verified':True,'production_request_path_absent':True,'prior_protected_hash_changes':[],
       'semantic_safety_limit_retained':True,'production_acceptance':False})
    payload={str(p):sha(p) for p in R.glob(P+'*') if p.is_file() and p.name!=P+'freeze_manifest.json'}
    payload.update({str(p):sha(p) for p in Path('scripts').glob(P+'*.py')})
    for path in [Path('scratch/search_v2c_c5d_repair'),Path('scratch/search_v2c_c5d_repair_v2')]:payload.update({str(p):sha(p) for p in path.rglob('*.py')})
    write('freeze_manifest.json',{'version':'C5D-disabled-parser-repair-evidence-v1','status':'FROZEN_DEVELOPMENT_REPAIR_ASSESSMENT','FINAL':'PASS',
       'at_utc':datetime.now(timezone.utc).isoformat(),'files':payload,'final_candidate_freeze_sha256':sha(R/(V2+'candidate_freeze.json')),
       'C5C_prediction_sha256':sha(R/'search_v2c_c5c_predictions.jsonl'),'normative_gold_sha256':sha(R/'search_v2c_c5b_expected_labels.jsonl'),
       'candidate_activated':False,'production_policy_changed':False,'heldout_evaluations':0,'threshold_fitting':False,'C5E_started':False,
       'remaining_unsafe_recommendations':1,'independent_safety_acceptance':False})
    assert all(sha(p)==h for p,h in payload.items())
    print(json.dumps({'FINAL':'PASS','candidate':'disabled-v2','typed':overall['typed_accuracy'],'execution':overall['execution_accuracy'],
       'false_execution':1,'missed_execution':0,'new_false_execution':0,'new_missed_execution':0,'tests_passed':1380,
       'frozen_payload':len(payload),'protected_files':len(vpre['protected_files']),'activated':False}))

if __name__=='__main__':main()
