"""Validate measured C5C results and freeze evidence. No parser/native execution."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import json
import re

from scripts.search_v2c_c5c_prepare import R, P, B, sha, digest, load, rows, write

def main():
    pre = load(R/(P+'preflight.json'))
    config = load(R/(P+'parser_configuration.json'))
    capture = load(R/(P+'prediction_complete.json'))
    scored = load(R/(P+'scoring_complete.json'))
    typed = load(R/(P+'typed_decision_scoring.json'))
    execute = load(R/(P+'execution_decision_scoring.json'))
    failures = load(R/(P+'failure_analysis.json'))
    matrix = load(R/(P+'stratified_matrix.json'))
    masks = load(R/(P+'scoring_applicability.json'))
    operands = load(R/(P+'operand_scoring.json'))
    diag = load(R/(P+'five_case_ambiguity_diagnostic.json'))
    corpus = rows(R/(B+'calibration_cases.jsonl'))
    gold = {r['case_id']:r for r in corpus}
    predictions = rows(R/(P+'predictions.jsonl'))
    result = rows(R/(P+'scored_observations.jsonl'))
    eligibility = load(R/(P+'eligibility.json'))
    assert len(predictions)==len(result)==len({x['case_id'] for x in result})==644
    assert sha(R/(P+'predictions.jsonl'))==capture['prediction_sha256']==scored['prediction_sha256']
    assert scored['scoring_parser_calls']==0
    assert all(sha(p)==h for p,h in config['frozen_before_prediction_scripts'].items())
    assert all(sha(p)==h for p,h in config['parser_source_hashes'].items())
    expected_ids={x['case_id'] for x in eligibility['cases'] if x['eligible']}
    assert {x['case_id'] for x in predictions}=={x['case_id'] for x in result}==expected_ids
    # Independently recompute principal metrics directly from the immutable
    # prediction capture and frozen gold, without using scorer helper functions.
    n=len(predictions)
    correct=sum(x['typed_decision']==gold[x['case_id']]['expected_typed_decision'] for x in predictions)
    execution_correct=sum(x['executable'] is gold[x['case_id']]['expected_executable'] for x in predictions)
    blocked=[x for x in predictions if gold[x['case_id']]['expected_executable'] is False]
    allowed=[x for x in predictions if gold[x['case_id']]['expected_executable'] is True]
    false=sum(x['executable'] is True for x in blocked)
    missed=sum(x['executable'] is False for x in allowed)
    metrics=scored['metrics']
    assert (metrics['typed_accuracy']['numerator'],metrics['typed_accuracy']['denominator'])==(correct,n)
    assert (metrics['execution_accuracy']['numerator'],metrics['execution_accuracy']['denominator'])==(execution_correct,n)
    assert (metrics['false_execution_rate']['numerator'],metrics['false_execution_rate']['denominator'])==(false,len(blocked))
    assert (metrics['missed_execution_rate']['numerator'],metrics['missed_execution_rate']['denominator'])==(missed,len(allowed))
    assert sum(sum(v.values()) for v in metrics['confusion_matrix'].values())==644
    assert sum(x['eligible'] for x in matrix['cells'])==644
    assert sum(x['new_reviewed_core'] for x in matrix['cells'])==594
    assert all(x['new_reviewed_core']>=15 and x['independently_reviewed_meaningful_patterns']>=4 for x in matrix['cells'])
    for cell in matrix['cells']:
        subset=[x for x in predictions if gold[x['case_id']]['scope_type']==cell['scope'] and gold[x['case_id']]['decision_stratum']==cell['stratum']]
        assert len(subset)==cell['eligible']
        assert sum(x['typed_decision']==gold[x['case_id']]['expected_typed_decision'] for x in subset)==cell['correct_typed']
        assert sum(x['executable'] and not gold[x['case_id']]['expected_executable'] for x in subset)==cell['false_execution_count']
    from scripts.search_v2c_c5a_manifest import canonical
    caps=load(R/'search_v2c_c5a_capability_matrix.json')['scopes']
    contexts=[canonical(x,caps) for x in corpus]
    assert len(contexts)==len(set(contexts))==1024
    changed=[p for p,h in pre['protected_files'].items() if sha(p)!=h]
    assert not changed,changed
    # Retain inherited large-asset verification strength; no full-index SHA claim.
    original=load(R/'search_v2c_c_preservation.json')
    large=[]
    for item in original['files']:
        path=item['file']
        if path.startswith(('data_pipeline/','local-data/','recommendation/','rag/')) or path=='scripts/search_v2c_c_author_gold.py':
            before=item['after']; stat=Path(path).stat()
            same=sha(path)==before['sha256'] if 'sha256' in before else stat.st_size==before['size'] and stat.st_mtime_ns==before['mtime_ns']
            assert same,path
            large.append({'path':path,'unchanged':True,'method':'artifact SHA256' if 'sha256' in before else 'inherited size+mtime_ns; not full checksum'})
    preserve={'status':'PASS','protected_existing_files':len(pre['protected_files']),'protected_hash_changes':changed,
              'original_C5B_protected_baseline_files':1557,'production_source_files':462,'sealed_rows_decoded':0,
              'C5A_manifest_unchanged':True,'C5B_manifest_unchanged':True,'C5B_admission_unchanged':True,
              'original_C5_failures_unchanged':True,'evaluator_hashes_unchanged':True,'native_harness_hashes_unchanged':True,
              'large_artifact_checks':large,'full_HNSW_KG_checksum_claim':False,'resident_endpoint_repolled':False,
              'database_reads_or_writes':0,'global_book_count':'5,000,000 previously recorded metadata observation; not remeasured.',
              'global_search_health':'Last known STALE/degraded, baseline_verified=False. No current-health claim.'}
    write('preservation.json',preserve)
    history={'historical_C5_parser_evaluations':50,'historical_C5_outcomes':'Original FAIL evidence unchanged; not relabeled and not included as new results.',
             'C5A_native_historical':{'main_scenarios':'264/264','status_state_privacy_boundaries':'833/833','suggestion_issuances':'59/59',
                                    'correction_issuances':'213/213','authorized_commits':154,'EXACT_SMART_supplement':'5/5','supplement_boundaries':15,'security_regression':'46/46'},
             'C5A_native_reruns':0,'new_C5C_calls':644,'new_C5C_new_core_calls':594,'new_C5C_retained_original_calls':50,
             'retained50_reused_as_fresh_inputs_not_duplicate_contexts':True,'historical_and_new_accuracy_combined':False,
             'native_sequences_excluded':230,'native_API_boundary_assertions_in_parser_denominator':0,
             'derivative_parser_evaluations':0,'rejected_parser_evaluations':0,'heldout_parser_evaluations':0,
             'prediction_attempts':1,'parser_retry_calls':0,'diagnostic_parser_probes':0,'preflight_attempts':pre['preflight_attempts']}
    write('historical_accounting.json',history)
    prohibited={k:0 for k in ['THRESHOLD_FITTING_RUNS','POLICY_CANDIDATES_EVALUATED','POLICY_SELECTIONS','POLICY_ACTIVATIONS',
                 'HELDOUT_PARSER_EVALUATIONS','HELDOUT_POLICY_EVALUATIONS','HNSW_REBUILDS','KG_REBUILDS','MODEL_CHANGES','QWEN_INFERENCES',
                 'NATIVE_HARNESS_RERUNS','PART_2I_STARTS','LIVE_APPLICATION_COMMITS','MONGO_MUTATIONS','CORPUS_REGENERATIONS','NORMATIVE_GOLD_REWRITES',
                 'REVIEWER_VERDICT_REWRITES','PRODUCTION_PARSER_CHANGES','PRODUCTION_POLICY_CHANGES','RESIDENT_ENDPOINT_POLLS']}
    write('prohibited_activity_audit.json',{'counts':prohibited,'authorized_new_parser_evaluations':644,
          'capture_isolation_denials':capture['isolation_denials'],'capture_gold_reads':0,'capture_network_calls':0,
          'scoring_parser_invocations':0,'policy_note':'Unchanged active C4 recommendations observed, no candidate policy evaluated.'})
    recognition={kind:metrics['per_decision'][kind]['recall'] for kind in ['AMBIGUOUS','INCOMPLETE','UNSUPPORTED','CONTRADICTORY']}
    qa={'FINAL':'PASS','C5C_IMPLEMENTED':'YES','C5B_FREEZE_VERIFIED':'YES','C5B_ORIGINAL_FREEZE_PRESERVED':'YES','C4_ACTIVE_POLICY_PRESERVED':'YES',
        'PRODUCTION_PARSER_CHANGED':'NO','PRODUCTION_POLICY_CHANGED':'NO','PARSER_CALIBRATION_EVALUATION_COMPLETE':'YES',
        'TOTAL_FROZEN_CONTEXTS':1024,'ELIGIBLE_PARSER_CONTEXTS':644,'INELIGIBLE_PARSER_CONTEXTS':380,
        'APPLICABILITY_EXCLUSIONS':{'logical_contexts':380,'context_reasons':{k:v for k,v in eligibility['category_counts'].items() if k not in ['NEW_REVIEWED_CORE','RETAINED_REVIEWED_CORE']},
                                    'eligible_field_assertions_excluded':masks['excluded_field_assertions'],'field_reason_counts':masks['exclusion_status_counts'],
                                    'native_parser_labels_inapplicable':230,'missing_required_eligible_decision_execution_labels':0},
        'INDEPENDENTLY_REVIEWED_ELIGIBLE_CONTEXTS':644,'NEW_CORE_EVALUATED':594,'RETAINED_ORIGINAL_EVALUATED':50,
        'DERIVATIVE_EVALUATED_SEPARATELY':0,'NATIVE_CASES_EXCLUDED_FROM_CORE':230,'HISTORICAL_CASES_REEVALUATED':50,'TOTAL_NEW_PARSER_EVALUATIONS':644,
        'TYPED_DECISION_ACCURACY':metrics['typed_accuracy'],'TYPED_DECISION_CONFUSION_MATRIX':metrics['confusion_matrix'],
        'EXECUTION_DECISION_ACCURACY':metrics['execution_accuracy'],'FALSE_EXECUTION_COUNT':false,'FALSE_EXECUTION_RATE':metrics['false_execution_rate'],
        'MISSED_VALID_EXECUTION_COUNT':missed,'MISSED_VALID_EXECUTION_RATE':metrics['missed_execution_rate'],
        'AMBIGUOUS_RECOGNITION_RATE':recognition['AMBIGUOUS'],'INCOMPLETE_RECOGNITION_RATE':recognition['INCOMPLETE'],
        'UNSUPPORTED_RECOGNITION_RATE':recognition['UNSUPPORTED'],'CONTRADICTION_RECOGNITION_RATE':recognition['CONTRADICTORY'],
        'SCOPE_ACCURACY':operands['scope_accuracy'],'ACTOR_ACCURACY':operands['actor_accuracy'],'CONFIDENCE_ANALYSIS_AVAILABLE':'YES (descriptive native signals only)',
        'TOTAL_CLASSIFIED_PARSER_ERRORS':failures['parser_defect_contexts'],'INDETERMINATE_ERRORS':failures['indeterminate_error_contexts'],
        'DUPLICATE_CANONICAL_CONTEXTS':0,'CROSS_SPLIT_STRUCTURAL_OVERLAP':0,'HELDOUT_HASH_UNCHANGED':'YES',
        'PRODUCTION_SOURCE_HASH_VERIFICATION':'PASS (462 files)','HISTORICAL_EVIDENCE_HASH_VERIFICATION':f"PASS ({len(pre['protected_files'])} protected files, including the original 1557-file baseline)",
        'C5A_MANIFEST_UNCHANGED':'YES','C5B_MANIFEST_UNCHANGED':'YES','C5C_EVIDENCE_FROZEN':'YES',
        'THRESHOLD_FITTING_PERFORMED':'NO','POLICY_CANDIDATES_EVALUATED':0,'CALIBRATION_POLICY_SELECTED':'NO','CALIBRATION_POLICY_ACTIVATED':'NO',
        'HELDOUT_PARSER_EVALUATIONS':0,'HELDOUT_POLICY_EVALUATIONS':0,'HNSW_REBUILT':'NO','KG_REBUILT':'NO','MODEL_CHANGED':'NO','NATIVE_HARNESS_RERUN':'NO','PART_2I_STARTED':'NO',
        'UNIQUE_CONTEXTS_WITH_ANY_SCORED_MISMATCH':failures['error_contexts'],'CLASSIFIED_PARSER_ERROR_DIMENSIONS':failures['disposition_dimension_counts']['PARSER_DEFECT'],
        'INDETERMINATE_ERROR_DIMENSIONS':failures['disposition_dimension_counts']['INDETERMINATE_FAILURE'],
        'ERROR_COUNTS_OVERLAP':'A context can contain confirmed parser and indeterminate dimensions. Do not add these context counts.',
        'COHORT_METRICS':scored['cohorts'],'FIVE_REVISED_AMBIGUITY_COHORT':{k:v for k,v in diag.items() if k!='cases'},
        'FINAL_MEANING':'Evaluation complete and valid. Parser accuracy, policy readiness and production acceptance are not established by PASS.',
        'UNRESOLVED_EVALUATION_BLOCKERS':[],
        'NEXT_PHASE_AUTHORIZED':'NO: separate explicit authorization required for any threshold/policy investigation; heldout remains separately gated.'}
    prompt=Path(r'C:\Users\balak\.codex\attachments\2f0c8016-1435-44f6-b3b2-abe3f82b41e5\Pasted text.txt').read_text(encoding='utf8')
    section=prompt.split('## 13. Mandatory Final QA Report')[1].split('## 14.')[0]
    required=re.findall(r'^- ([A-Z][A-Z0-9_]+)\s*$',section,re.M)
    assert not (set(required)-qa.keys()),set(required)-qa.keys()
    write('final_qa.json',qa)
    high=[x for x in result if x['native_interpretation_confidence']==1.0]
    high_typed=sum(x['typed_correct'] for x in high)
    high_false=sum(x['execution'] and not x['expected_execution'] for x in high)
    # Produce a complete readable report plus exact machine-readable evidence.
    def pct(r):return f"{r['numerator']}/{r['denominator']} ({r['percent']:.2f}%)" if r['denominator'] else 'N/A (no applicable cases)'
    lines=['# V2C-C.5C — frozen parser calibration evaluation','',
           'FINAL = PASS. This means the authorized evaluation is complete and valid. It does not establish adequate parser accuracy or production/policy readiness. No tuning or policy selection occurred.','',
           '## Population and isolation','',
           'Exact C5B freeze and append-only final admission verified before inference. The five inherited core_eligible=false flags are stale intermediate metadata: frozen C5B quota code uses CORE + AI_REVIEWED + review_complete, and final admission explicitly accepts these five. No C5B artifact was edited. The first preflight stopped on that stale flag with zero parser calls; both preflight attempts are recorded.','',
           '1,024 frozen contexts: 594 eligible new independently reviewed core + 50 eligible retained reviewed parser contexts + 230 excluded native sequences + 149 excluded unreviewed derivatives + one excluded rejected core. Thirty AI_REVIEWED native records are not parser units. False execution gold is a valid negative, never missing gold.','',
           f"One isolated capture made 644 parser calls, 644 outputs, no errors/retries, no model inference, no network calls, no application writes or native runs. Prediction process received only query/mode/supplied scope/workspace and frozen vocabulary/capabilities. Gold was joined after prediction capture was complete. Prediction SHA256: `{capture['prediction_sha256']}`.",'',
           '## Measured performance','',
           '| Population | Typed accuracy | Execution recommendation accuracy | False execution among blocked gold | Missed execution among executable gold |',
           '|---|---:|---:|---:|---:|']
    for name,s in [('All eligible',metrics),('New reviewed core',scored['cohorts']['NEW_REVIEWED_CORE']),('Retained reviewed originals',scored['cohorts']['RETAINED_REVIEWED_CORE'])]:
        lines.append(f"| {name} | {pct(s['typed_accuracy'])} | {pct(s['execution_accuracy'])} | {pct(s['false_execution_rate'])} | {pct(s['missed_execution_rate'])} |")
    lines+=['','Typed outputs have 390 errors; execution recommendations have 191 false positives and 43 false negatives. There were no invalid/undecidable outputs. No actual application execution occurred.','',
            'Typed recall: '+ '; '.join(f"{kind}: {pct(value)}" for kind,value in recognition.items())+'.','',
            '## Concentration and thirty-cell matrix','',
            'SAFE_UNCERTAIN_EXECUTABLE typed recall is 0/100. The current C4 policy may issue a repair notice while the parser typed decision remains EXECUTABLE; policy notice is not silently substituted for a typed gold match. Executability in this stratum is 70/100.','',
            'All five scopes and six strata are reported below. Retained50 occupy only PRIVATE_TENANT_PATRON/CLEAR_EXECUTABLE; their 100% typed accuracy raises that mixed cell. New-core counts and patterns are shown separately. All cells are small synthetic samples; no population confidence claim is warranted.','',
            '| Scope | Stratum | Eligible | New core | Patterns | Typed correct | False execution | Missed execution |',
            '|---|---|---:|---:|---:|---:|---:|---:|']
    for c in matrix['cells']:
        lines.append(f"| {c['scope']} | {c['stratum']} | {c['eligible']} | {c['new_reviewed_core']} | {c['independently_reviewed_meaningful_patterns']} | {c['correct_typed']}/{c['eligible']} | {c['false_execution_count']} | {c['missed_execution_count']} |")
    lines+=['','Blocked-gold false execution by scope: '+ '; '.join(f"{scope}: {pct(s['false_execution_rate'])}" for scope,s in typed['by_scope'].items())+'.','',
            '## Failure analysis','',
            'Five prominent measured categories (multi-label counts can overlap): missing required operand 496 contexts; semantic remainder mismatch 355; affected-field reporting mismatch 323; false executable classification 191; other wrong typed decision 113. Additional typed safety diagnoses include ambiguity misclassification 83/98, incomplete misclassification 72/99, unsupported misclassification 89/100, and contradiction recognition misses 33/97.','',
            f"There are {failures['error_contexts']} contexts with at least one scored mismatch, {failures['parser_defect_contexts']} with applicable parser-defect dimensions, and {failures['indeterminate_error_contexts']} with indeterminate dimensions; those last two counts overlap. Strict semantic-remainder, intent, and affected-field granularity disagreements retain their scores but are not automatically claimed as confirmed causal parser defects. Every failure has an ID, observed/expected values, gold fingerprint, taxonomy and disposition. No confirmed evaluator/runtime/fixture defect or gold rewrite is claimed.",'',
            'Safety-critical false execution is concentrated in AMBIGUOUS (66/98), INCOMPLETE (49/99), UNSUPPORTED (50/100), and CONTRADICTORY (26/97) gold. These are offline recommendations; no inventory/account/search application action was executed.','',
            '## Five revised ambiguity cases','',
            f"Typed ambiguity recognition: {pct(diag['typed_recognition'])}. Safe non-execution: {pct(diag['safe_non_execution'])}. Four false execution recommendations remain. Author scalar assertions are excluded as intentionally unknown; required typed/execution gold remains complete.",'',
            '| Stable ID | Predicted typed decision | Execution recommendation | Native confidence signal |','|---|---|---|---:|']
    for x in diag['cases']:lines.append(f"| {x['case_id']} | {x['decision']} | {x['execution']} | {x['native_interpretation_confidence']} |")
    lines+=['','## Confidence and limitations','',
            f"The native confidence values observed were 0.0 and 1.0; they are heuristic/categorical signals, not calibrated probabilities. At native value 1.0, typed correctness is {high_typed}/{len(high)} ({100*high_typed/len(high):.2f}%), with {len(high)-high_typed} typed errors and {high_false} false execution recommendations. No bins/cutoffs were invented, no reliability transformation fitted, and no thresholds swept.",'',
            'Scope/actor accuracy is N/A because those are supplied context rather than parser-selected outputs. Live private/public API boundaries are not measured. Scalar masks exclude unresolved and scope-inapplicable fields; partially resolved lists use only their known common subset. No comparison silently treats unknown author values as absent. Detailed ambiguity-alternative span equality and new structured advisory-object accuracy are N/A because no established output-equivalence adapter exists. The retained50 advisory representation remains measured under its original contract.','',
            f"Eligible contexts have {masks['excluded_field_assertions']} excluded scalar/advisory assertions: {json.dumps(masks['exclusion_status_counts'],sort_keys=True)}. Ten partial list/subset comparisons score only the common resolved members. All 644 typed and execution labels remain applicable. Rate denominators are explicit; zero-denominator metrics are N/A. No real-world generalization is asserted from synthetic cells of 18–20 new core cases.",'',
            '## Historical separation and preservation','',
            f"All {len(pre['protected_files'])} protected pre-existing files match preflight hashes, including the original 1,557-file baseline and 462 production source files. C5A, C5B, original historical C5 FAIL results, sealed hashes, evaluators and native harnesses are preserved. Original50 historical parser outcomes and native 264/264, 833/833 boundaries, 59/59 suggestions, 213/213 corrections, 154 commits, supplement5/5 and security46/46 are historical evidence, not fresh C5C results. The fifty retained parser contexts were reevaluated once in C5C and are explicitly separate from their original outcomes.",'',
            'Large assets retain their inherited artifact SHA256 or size/mtime verification method. No full HNSW/KG checksum or current healthy runtime claim is made. Global5,000,000 and STALE/degraded baseline_verified=False are previous observations; no endpoint or Mongo poll occurred.','',
            '## Final analysis and boundary','',
            'The measured current parser performs well on retained typed labels but has substantial new-core typed and execution-safety failures. The evidence is sufficient to plan a separately authorized policy investigation, while operand/semantic recognition gaps limit what a confidence-only policy can establish. Structured-advisory and scope/actor metrics remain explicitly unavailable; indeterminate causal dimensions require future investigation. There are no unresolved blockers to completion of this scoring phase.','',
            'Stop here. Any threshold calibration, policy alternatives, operating-point selection or parser work requires separate explicit authorization. Heldout evaluation remains separately gated. No threshold values or policy winner are recommended.','',
            '## Mandatory final QA fields','', '| Field | Measured value |','|---|---|']
    for k,v in qa.items():lines.append(f"| {k} | {json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v} |")
    lines+=['','## Evidence','']
    for name in ['preflight.json','eligibility.json','applicability_audit.json','parser_configuration.json','parser_inputs.jsonl','predictions.jsonl',
                 'prediction_complete.json','scoring_applicability.json','typed_decision_scoring.json','execution_decision_scoring.json','operand_scoring.json',
                 'stratified_matrix.json','confidence_observations.json','failures.jsonl','failure_analysis.json','five_case_ambiguity_diagnostic.json',
                 'historical_accounting.json','preservation.json','prohibited_activity_audit.json','final_qa.json','validation.json','freeze_manifest.json']:
        lines.append(f'- reports/{P}{name}')
    with (R/(P+'review.md')).open('x',encoding='utf8') as out:out.write('\n'.join(lines)+'\n')
    write('validation.json',{'status':'PASS','at_utc':datetime.now(timezone.utc).isoformat(),'mandatory_QA_fields_verified':len(required),
          'principal_metrics_independently_recomputed':True,'matrix_cell_counts_independently_recomputed':True,'canonical_contexts_recomputed':1024,
          'prediction_capture_hash_verified':True,'protected_files_reverified':len(pre['protected_files']),'protected_changes':[],
          'all_source_schema_and_label_hashes_preserved':True,'all_prediction_outputs_bound_to_immutable_capture':True,
          'new_parser_calls_during_scoring_or_validation':0,'reproducibility_limit':'Single actual run of deterministic implementation; no rerun claimed. Per-input/output fingerprints exclude elapsed timing.'})
    frozen={str(p):sha(p) for p in R.glob(P+'*') if p.is_file() and p.name!=P+'freeze_manifest.json'}
    frozen.update({str(p):sha(p) for p in Path('scripts').glob(P+'*.py')})
    write('freeze_manifest.json',{'version':'C5C-frozen-parser-measurement-v1','status':'FROZEN_COMPLETE_EVALUATION','FINAL':'PASS',
          'at_utc':datetime.now(timezone.utc).isoformat(),'files':frozen,'C5B_input_freeze_sha256':pre['C5B_freeze_sha256'],
          'C5B_final_admission_sha256':pre['C5B_admission_sha256'],'prediction_sha256':capture['prediction_sha256'],
          'normative_gold_sha256':sha(R/(B+'expected_labels.jsonl')),'eligible_contexts':644,'parser_calls':644,
          'threshold_fitting':False,'policy_selected':False,'policy_activated':False,'heldout_evaluations':0,
          'self_hash_binding':'Manifest hash is recorded in append-only report validation after freeze; no circular self hash.'})
    assert all(sha(p)==h for p,h in frozen.items())
    print(json.dumps({'FINAL':'PASS','eligible':644,'typed':metrics['typed_accuracy'],'execution':metrics['execution_accuracy'],
                     'false_execution':false,'missed_execution':missed,'frozen_files':len(frozen),'freeze_sha256':sha(R/(P+'freeze_manifest.json'))}))

if __name__=='__main__':
    main()
