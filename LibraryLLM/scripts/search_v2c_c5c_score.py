"""Score immutable C5C predictions. No parser invocation, tuning or gold edits."""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import statistics
import sys

from scripts.search_v2c_c5c_prepare import R, P, B, sha, digest, load, rows, write, jsonl

KINDS = ['EXECUTABLE', 'EXECUTABLE_WITH_NOTICE', 'AMBIGUOUS', 'INCOMPLETE', 'UNSUPPORTED', 'CONTRADICTORY']
STRATA = ['CLEAR_EXECUTABLE', 'SAFE_UNCERTAIN_EXECUTABLE', 'AMBIGUOUS', 'INCOMPLETE', 'UNSUPPORTED', 'CONTRADICTORY']
LISTS = {'subjects','exclude_subjects','exclude_terms','formats','exclusive_formats','excluded_formats'}
OPERANDS = LISTS | {'author_text','title_text','exact_text','rating_min','rating_max','year_min','year_max','availability','language',
                    'rating_min_exclusive','rating_max_exclusive','year_min_exclusive','year_max_exclusive'}

def rate(n, d):
    return {'numerator': n, 'denominator': d, 'percent': 100*n/d if d else None, 'status': 'MEASURED' if d else 'N/A'}

def missing(reason):
    return {'numerator': None, 'denominator': 0, 'percent': None, 'status': 'N/A', 'reason': reason}

def summarize(group):
    valid = [x for x in group if x['valid_output']]
    positive = [x for x in valid if x['expected_execution'] is True]
    negative = [x for x in valid if x['expected_execution'] is False]
    correct = sum(x['typed_correct'] for x in valid)
    tp = sum(x['execution'] is True for x in positive)
    tn = sum(x['execution'] is False for x in negative)
    fp = sum(x['execution'] is True for x in negative)
    fn = sum(x['execution'] is False for x in positive)
    confusion = {k: dict(Counter(x['decision'] for x in valid if x['expected_decision'] == k)) for k in KINDS}
    per_class = {}
    for kind in KINDS:
        actual = sum(x['decision'] == kind for x in valid)
        gold = sum(x['expected_decision'] == kind for x in valid)
        hit = sum(x['decision'] == x['expected_decision'] == kind for x in valid)
        per_class[kind] = {'precision': rate(hit, actual), 'recall': rate(hit, gold), 'f1': rate(2*hit, actual+gold), 'gold_count': gold, 'predicted_count': actual}
    return {'eligible': len(group), 'evaluated': len(group), 'valid_outputs': len(valid), 'applicable_typed': len(group), 'applicable_execution': len(group),
            'correct_typed': correct, 'incorrect_typed': len(valid)-correct, 'typed_accuracy': rate(correct,len(valid)),
            'execution_accuracy': rate(tp+tn,len(valid)), 'correct_executable': tp, 'correct_non_executable': tn,
            'false_execution_count': fp, 'false_execution_rate': rate(fp,len(negative)),
            'missed_execution_count': fn, 'missed_execution_rate': rate(fn,len(positive)),
            'invalid_or_undecidable': len(group)-len(valid), 'unsupported_output_schema': sum(not x['valid_output'] for x in group),
            'abstentions': sum(x['execution'] is False for x in valid),
            'clarifications': sum(x['policy'] == 'CLARIFY' for x in valid), 'unsupported_decisions': sum(x['decision']=='UNSUPPORTED' for x in valid),
            'confusion_matrix': confusion, 'per_decision': per_class,
            'strict_scored_dimension_match': rate(sum(x['all_scored_dimensions_correct'] for x in valid),len(valid)),
            'note': 'False-execution denominator is applicable blocked gold; missed-execution denominator is applicable executable gold. These are recommendations, not application actions.'}

def main():
    complete = load(R / (P + 'prediction_complete.json'))
    prediction_path = R / (P + 'predictions.jsonl')
    assert sha(prediction_path) == complete['prediction_sha256']
    assert complete['parser_calls'] == complete['captured'] == 644 and complete['errors'] == complete['retries'] == 0
    assert not complete['isolation_denials']
    preflight = load(R / (P + 'preflight.json'))
    assert all(sha(p)==h for p,h in preflight['protected_files'].items())
    write('scoring_started.json', {'at_utc': datetime.now(timezone.utc).isoformat(), 'prediction_sha256': sha(prediction_path),
          'scorer_sha256': sha(__file__), 'parser_calls_authorized_in_scoring_process': 0, 'gold_access_begins_after_capture_complete': True})
    parser_calls = []
    def prohibit_parse(frame, event, arg):
        if event == 'call' and frame.f_code.co_name == 'parse_query' and frame.f_globals.get('__name__') == 'search.query_plan':
            parser_calls.append(True)
            raise RuntimeError('Parser calls prohibited during scoring')
    sys.setprofile(prohibit_parse)
    from scripts.search_v2c_c_evaluate import norm, expected, MAPPING, atoms, token_f1
    from scripts.search_v2c_c4_evaluate import rescore, normalize_both, both_normalization_proof
    proof = both_normalization_proof()
    corpus = {x['case_id']: x for x in rows(R / (B + 'calibration_cases.jsonl'))}
    eligibility = load(R / (P + 'eligibility.json'))
    categories = {x['case_id']: x['category'] for x in eligibility['cases']}
    predictions = rows(prediction_path)
    expected_ids = {x['case_id'] for x in eligibility['cases'] if x['eligible']}
    assert {x['case_id'] for x in predictions} == expected_ids and len(predictions)==len(expected_ids)
    gold_hash = sha(R/(B+'expected_labels.jsonl'))
    scorer_rows, failures, applicability, legacy_rows = [], [], [], []
    field_results = defaultdict(list)
    inverse = {v:k for k,v in MAPPING.items()}
    inverse.update(title_text='expected_title',language='expected_language')
    caps = load(R / 'search_v2c_c5a_capability_matrix.json')['scopes']
    for prediction in predictions:
        case = corpus[prediction['case_id']]
        actual = prediction['actual_plan']
        assert prediction['output_sha256'] == digest({k:prediction[k] for k in ['actual_plan','typed_decision','executable','assessment','native_interpretation_confidence']})
        valid = prediction['typed_decision'] in KINDS and type(prediction['executable']) is bool
        retained = case['example_class']=='RETAINED_CORE'
        legacy = {'query_id':case['case_id'],'family_id':case['family_id'],'split':'calibration','category':case['decision_stratum'],
                  'scope_type':case['scope_type'],'expected_decision':case['expected_typed_decision'],'execution_allowed':case['expected_executable']}
        masks = case['metric_applicability']
        partial_fields, excluded, allowed = set(), {}, set()
        if retained:
            legacy.update(case['retained_original_expected_labels'])
            gold = expected(legacy)
            allowed = set(gold)
        else:
            hard = case['expected_hard_constraints']
            for field in sorted(OPERANDS):
                mask = masks.get(field)
                if mask is None:
                    excluded[field] = {'status':'NO_GOLD_FIELD','reason':'No scalar applicability/reference in frozen schema.'}
                    continue
                state = mask['status']
                if state not in ['APPLICABLE','APPLICABLE_ABSENCE','PARTIALLY_APPLICABLE']:
                    excluded[field] = mask
                    continue
                if state == 'APPLICABLE_ABSENCE':
                    value = [] if field in LISTS else False if field.endswith('_exclusive') else None
                else:
                    assert field in hard or 'resolved_value' in mask, (case['case_id'],field)
                    value = mask.get('resolved_value', hard.get(field))
                    if field in hard: assert value==hard[field], (case['case_id'],field)
                if state == 'PARTIALLY_APPLICABLE': partial_fields.add(field)
                legacy[inverse[field]] = value
                allowed.add(field)
            if masks['semantic_remainder']['status']=='APPLICABLE':
                legacy['expected_semantic_text'] = case['expected_semantic_remainder']
                allowed.add('semantic_text')
            # The new structured advisory gold has no established adapter to the
            # production display-string preference. Do not invent semantic equality.
            excluded['soft_preferences'] = {'status':'UNAVAILABLE_OUTPUT_ORACLE_ADAPTER',
                'frozen_status':masks['soft_preferences']['status'], 'gold':case['expected_soft_preferences'],
                'reason':'Structured advisory object vs native display-string; no frozen scoring equivalence. Remains unscored, including partial advisory components.'}
            gold = {k:v for k,v in expected(legacy).items() if k in allowed}
        raw = {'decision':prediction['typed_decision'],'execution':prediction['executable'],'actual_plan':deepcopy(actual)}
        scored = rescore(legacy,raw,normalize_formats=True)
        normalized_gold, normalized_actual = normalize_both(gold), normalize_both(actual)
        mismatches = {k:v for k,v in scored['mismatches'].items() if k in allowed or k in ['decision','execution_allowed']}
        assertions=[]
        for field in sorted(allowed):
            wanted = normalized_gold[field]
            observed = normalized_actual.get(field)
            if field in partial_fields:
                assert isinstance(wanted,list) and isinstance(observed,list)
                good = set(norm(wanted)).issubset(set(norm(observed)))
                if good: mismatches.pop(field,None)
                else: mismatches[field]={'expected_common_subset':wanted,'actual':observed,'comparison':'Resolved subset only; unresolved additions not scored.'}
            else: good = norm(observed)==norm(wanted)
            assertions.append({'field':field,'correct':good,'expected':wanted,'actual':observed,'partial':field in partial_fields})
            field_results[field].append(good)
        # Retain C5 strict affected-field comparison, separately distinguish it
        # from typed recognition. Do not coerce rating_min into rating, etc.
        details = [('expected_unsupported_fields','UNSUPPORTED','expected_unsupported_fields'),
                   ('expected_incomplete_fields','INCOMPLETE','expected_incomplete_fields'),
                   ('expected_contradiction_fields','CONTRADICTORY',None)]
        for legacy_key, kind, current_key in details:
            if retained:
                if legacy_key not in legacy: continue
                wanted=legacy[legacy_key]
            else:
                mask_key={'UNSUPPORTED':'unsupported_fields','INCOMPLETE':'incomplete_fields','CONTRADICTORY':'contradiction'}[kind]
                if masks[mask_key]['status']!='APPLICABLE':continue
                wanted=case[current_key] if current_key else case['expected_contradiction']['fields']
            observed=actual['decision'].get('affected_fields',[]) if prediction['typed_decision']==kind else []
            good=norm(wanted)==norm(observed)
            assertions.append({'field':legacy_key,'correct':good,'expected':wanted,'actual':observed,'partial':False})
            field_results[legacy_key].append(good)
            if not good:mismatches[legacy_key]={'expected':wanted,'actual':observed}
        if retained:
            protected_raw=all(norm(x['text']) in norm(' '.join(str(actual.get(k) or '') for k in ['semantic_text','title_text','exact_text','author_text'])) for x in case['protected_entities'])
            legacy_rows.append({'case_id':case['case_id'],'strict_C5_rescore_exact':scored['exact'], 'mismatches':scored['mismatches'],
                                'C5_representation_normalized_plan':scored['actual_plan'],'protected_content_preserved':protected_raw,
                                'note':'Fresh reevaluation of retained50. Original historical C5 output is preserved separately.'})
        literal=' '.join(str(actual.get(k) or '') for k in ['semantic_text','title_text','exact_text','author_text'])
        protected=all(norm(x['text']) in norm(literal) for x in case['protected_entities'])
        if case['protected_entities']:
            field_results['protected_entities'].append(protected)
            if not protected:mismatches['protected_entities']={'expected':[x['text'] for x in case['protected_entities']],'actual_literal_fields':literal}
        foreign=[s for s in actual['subjects']+actual['exclude_subjects'] if norm(s) not in {norm(v) for v in caps[case['scope_type']]['subjects']}]
        if foreign:mismatches['foreign_canonical_values']={'expected':'Values from supplied scope vocabulary only','actual':foreign}
        semantic_f1=token_f1(actual['semantic_text'],gold['semantic_text']) if 'semantic_text' in gold else None
        row={'case_id':case['case_id'],'evaluation_unit':'LOGICAL_PARSER_CONTEXT','cohort':categories[case['case_id']],
             'scope':case['scope_type'],'workspace':case['workspace_type'],'actor_role_context':'STAFF' if case['workspace_type']=='STAFF' else 'GENERAL_USER',
             'actor_is_supplied_context_not_predicted':True,'mode':case['search_mode'],'stratum':case['decision_stratum'],
             'independent_pattern_id':case.get('independent_pattern_id'),'review_status':case['review_status'],
             'prediction_output_sha256':prediction['output_sha256'],'gold_artifact_sha256':gold_hash,
             'valid_output':valid,'expected_decision':case['expected_typed_decision'],'decision':prediction['typed_decision'],
             'expected_execution':case['expected_executable'],'execution':prediction['executable'],
             'typed_correct':prediction['typed_decision']==case['expected_typed_decision'],
             'execution_correct':prediction['executable'] is case['expected_executable'], 'policy':prediction['assessment']['policy'],
             'all_scored_dimensions_correct':not mismatches, 'mismatches':mismatches,'assertions':assertions,
             'semantic_f1':semantic_f1,'native_interpretation_confidence':prediction['native_interpretation_confidence'],
             'categorical_assessment':prediction['assessment'],'scoring_excluded_fields':excluded,
             'protected_entity_content_preserved':protected,'foreign_canonical_values':foreign,
             'strict_plan_match_limitation':'All scored dimensions only; excludes frozen unresolved/inapplicable fields and unavailable structured-advisory adapter.'}
        scorer_rows.append(row)
        applicability.append({'case_id':case['case_id'],'scored_fields':sorted(allowed),'partial_subset_fields':sorted(partial_fields),'excluded_fields':excluded})
        if mismatches or not valid:
            categories_error=set()
            detail_records=[]
            for field, difference in mismatches.items():
                disposition='PARSER_DEFECT';taxonomy='A. CONFIRMED PARSER DEFECT'
                if field=='decision':
                    category={'AMBIGUOUS':'SEMANTIC_AMBIGUITY_MISCLASSIFICATION','INCOMPLETE':'MISSING_INFORMATION_MISCLASSIFICATION',
                              'UNSUPPORTED':'UNSUPPORTED_REQUEST_MISCLASSIFICATION','CONTRADICTORY':'CONTRADICTION_MISSED'}.get(case['expected_typed_decision'],'WRONG_TYPED_DECISION')
                elif field=='execution_allowed':
                    category='FALSE_EXECUTABLE_CLASSIFICATION' if prediction['executable'] else 'FALSE_NON_EXECUTABLE_CLASSIFICATION'
                elif field in OPERANDS:
                    wanted=gold.get(field);observed=actual.get(field)
                    category='MISSING_REQUIRED_OPERAND' if wanted not in (None,[],False,'') and observed in (None,[],False,'') else 'HALLUCINATED_OPERAND' if wanted in (None,[],False,'') and observed not in (None,[],False,'') else 'INCORRECT_OPERAND'
                    if field in ['author_text','title_text']:categories_error.add('INCORRECT_AUTHOR_TITLE_EXTRACTION')
                elif field.startswith('expected_') and field.endswith('_fields'):
                    category='AFFECTED_FIELD_REPORTING_MISMATCH'; disposition='INDETERMINATE_FAILURE';taxonomy='G. UNKNOWN / REQUIRES REVIEW'
                elif field=='semantic_text':
                    category='SEMANTIC_REMAINDER_MISMATCH';disposition='INDETERMINATE_FAILURE';taxonomy='G. UNKNOWN / REQUIRES REVIEW'
                elif field=='protected_entities':category='PROTECTED_ENTITY_CONTENT_LOSS'
                elif field=='foreign_canonical_values':category='CROSS_SCOPE_VOCABULARY_LEAKAGE'
                else:
                    category='OTHER_AUTHORED_FIELD_MISMATCH';disposition='INDETERMINATE_FAILURE';taxonomy='G. UNKNOWN / REQUIRES REVIEW'
                categories_error.add(category)
                detail_records.append({'dimension':field,'category':category,'disposition':disposition,'project_taxonomy':taxonomy,'observed_expected':difference,
                     'gold_evidence':{'artifact':str(R/(B+'expected_labels.jsonl')),'case_id':case['case_id'],'sha256':row['gold_artifact_sha256']},
                     'limitation':'Affected-field granularity and semantic-remainder mismatches retain strict scores; causal interpretation requires future review.' if disposition=='INDETERMINATE_FAILURE' else 'Mismatch against frozen independently reviewed applicable gold; no gold correction inferred.'})
            if case['expected_executable'] is False and prediction['executable']:categories_error.add('UNSAFE_EXECUTION_RECOMMENDATION')
            if case['expected_typed_decision'] in ['AMBIGUOUS','INCOMPLETE'] and prediction['assessment']['policy']!='CLARIFY':categories_error.add('CLARIFICATION_REQUIRED_BUT_OMITTED')
            if case['expected_executable'] and not prediction['executable']:categories_error.add('OVERLY_CONSERVATIVE_ABSTENTION')
            failures.append({'case_id':case['case_id'],'scope':case['scope_type'],'stratum':case['decision_stratum'],'cohort':row['cohort'],
                 'query_text':case['query_text'],'prediction_output_sha256':prediction['output_sha256'],'failure_categories':sorted(categories_error),
                 'expected_decision':case['expected_typed_decision'],'observed_decision':prediction['typed_decision'],
                 'expected_execution':case['expected_executable'],'observed_execution':prediction['executable'],'details':detail_records,
                 'parser_defect_dimensions':sum(d['disposition']=='PARSER_DEFECT' for d in detail_records),
                 'indeterminate_dimensions':sum(d['disposition']=='INDETERMINATE_FAILURE' for d in detail_records),
                 'normative_gold_changed':False,'requires_independent_gold_review_if_disputed':True})
    all_summary=summarize(scorer_rows)
    by_cohort={c:summarize([x for x in scorer_rows if x['cohort']==c]) for c in ['NEW_REVIEWED_CORE','RETAINED_REVIEWED_CORE']}
    matrix=[]
    for scope in caps:
        for stratum in STRATA:
            group=[x for x in scorer_rows if x['scope']==scope and x['stratum']==stratum]
            new=[x for x in group if x['cohort']=='NEW_REVIEWED_CORE']
            patterns=Counter(x['independent_pattern_id'] for x in new)
            cell={'scope':scope,'stratum':stratum,**summarize(group),'new_reviewed_core':len(new),'retained_original':len(group)-len(new),
                  'independently_reviewed_meaningful_patterns':len(patterns),'pattern_counts':dict(patterns),
                  'small_or_imbalanced_sample':True,'warning':'Descriptive synthetic benchmark cell, 18-20 new core cases. No confidence interval or population generalization asserted.'}
            matrix.append(cell)
    assert len(matrix)==30 and sum(x['eligible'] for x in matrix)==644
    # Exact observed values only. No bins, cutoffs, calibration fitting or ECE fabricated.
    confidence_groups=[]
    for stratum in STRATA:
        for decision in KINDS:
            for outcome in [True,False]:
                group=[x for x in scorer_rows if x['stratum']==stratum and x['decision']==decision and x['typed_correct']==outcome]
                if not group:continue
                scores=[x['native_interpretation_confidence'] for x in group]
                confidence_groups.append({'stratum':stratum,'predicted_decision':decision,'typed_correct':outcome,'cases':len(group),
                                          'exact_observed_value_counts':dict(Counter(str(v) for v in scores)),
                                          'minimum':min(scores),'maximum':max(scores),'mean':statistics.mean(scores),'median':statistics.median(scores)})
    category_counts=Counter(c for f in failures for c in f['failure_categories'])
    dispositions=Counter(d['disposition'] for f in failures for d in f['details'])
    final_ids={x['case_id'] for x in load(R/(B+'corpus_admission.json'))['cases']}
    diagnostic=[{**x,'query_text':corpus[x['case_id']]['query_text']} for x in scorer_rows if x['case_id'] in final_ids]
    assert len(diagnostic)==5
    confidence={'available':True,'signal':'native interpretation_confidence and unchanged assess() categorical evidence',
                'meaning':'Existing heuristic signal, not a probability; blocked decisions can set confidence to zero by design.',
                'groups':confidence_groups,'categorical_bucket_counts':dict(Counter(x['categorical_assessment']['bucket'] for x in scorer_rows)),
                'native_value_by_typed_correctness':{str(outcome):dict(Counter(str(x['native_interpretation_confidence']) for x in scorer_rows if x['typed_correct']==outcome)) for outcome in [True,False]},
                'calibration_statistics':'N/A: no established probability target, reliability bin edges or probability calibration statistic for this categorical interface.',
                'thresholds_fitted':0,'thresholds_swept':0,'policies_compared':0}
    jsonl('scored_observations.jsonl',scorer_rows)
    jsonl('failures.jsonl',failures)
    jsonl('legacy_reevaluation.jsonl',legacy_rows)
    write('scoring_applicability.json',{'cases':applicability,'excluded_field_assertions':sum(len(x['excluded_fields']) for x in applicability),
          'exclusion_status_counts':dict(Counter(v['status'] for x in applicability for v in x['excluded_fields'].values())),
          'partial_scalar_or_subset_comparisons':sum(len(x['partial_subset_fields']) for x in applicability),
          'excluded_advisory_gold_contexts':594,'all_required_typed_and_execution_labels_applicable':644,
          'detailed_ambiguity_span_scoring':'N/A: normative alternatives have no established direct-output equivalence. Recognition measured by typed decision.',
          'scope_actor_prediction_accuracy':'N/A: context supplied, not selected by parser.'})
    write('typed_decision_scoring.json',{'overall':all_summary,'cohorts':by_cohort,'by_scope':{s:summarize([x for x in scorer_rows if x['scope']==s]) for s in caps},
          'by_stratum':{s:summarize([x for x in scorer_rows if x['stratum']==s]) for s in STRATA},
          'exact_label_vocabulary':KINDS,'policy_notice_not_typed_notice':'C4 policy may recommend notice for a repair even if typed decision is EXECUTABLE; do not replace typed output with policy output.'})
    write('execution_decision_scoring.json',{'overall':all_summary,'cohorts':by_cohort,'recommendation_only':True,'actual_application_executions':0,
          'false_execution_ids':[x['case_id'] for x in scorer_rows if not x['expected_execution'] and x['execution']],
          'missed_execution_ids':[x['case_id'] for x in scorer_rows if x['expected_execution'] and not x['execution']]})
    write('stratified_matrix.json',{'cells':matrix,'cell_count':30,'new_core_only_total':594,'retained_total':50,'mixed_cell_caution':'Retained50 all occupy PRIVATE_TENANT_PATRON/CLEAR_EXECUTABLE; cohort values remain separately available.'})
    write('operand_scoring.json',{'per_field':{k:rate(sum(v),len(v)) for k,v in field_results.items()},
          'semantic_remainder_token_f1':rate(sum(x['semantic_f1'] for x in scorer_rows if x['semantic_f1'] is not None),sum(x['semantic_f1'] is not None for x in scorer_rows)),
          'BOTH_equivalence_proof':proof,'list_case_whitespace_normalization':'Unchanged evaluator norm()',
          'strict_match':'All scored dimensions only, not complete-plan accuracy for partially applicable contexts.',
          'scope_accuracy':missing('Scope and authorization context supplied; parser emits no predicted scope.'),
          'actor_accuracy':missing('No predicted role output or independent actor oracle for this parser.'),
          'native_boundary_handling':'N/A: no native API assertions executed. Foreign vocabulary diagnostic only.',
          'new_structured_soft_preference_accuracy':missing('No established object-to-display-string scoring adapter.')})
    write('confidence_observations.json',confidence)
    write('failure_analysis.json',{'error_contexts':len(failures),'typed_error_contexts':all_summary['incorrect_typed'],
          'parser_defect_contexts':sum(x['parser_defect_dimensions']>0 for x in failures),
          'indeterminate_error_contexts':sum(x['indeterminate_dimensions']>0 for x in failures),
          'disposition_dimension_counts':dict(dispositions),'category_context_counts':dict(category_counts),
          'category_counts_overlap':True,'top_five_categories':category_counts.most_common(5),
          'taxonomy_source':'scripts/search_v2c_c2_diagnose.py A/B/C/D/E/F/G; additive descriptive C5C category tags, no gold amendments.',
          'confirmed_evaluator_runtime_defects':0,'confirmed_fixture_defects':0,'normative_gold_concerns_quarantined':[],
          'inapplicable_assertions':'Excluded and enumerated in scoring_applicability.json, not classified as parser errors.',
          'causal_limit':'Strict semantic remainder/affected-field/intent differences remain indeterminate where direct causal evidence is insufficient; disagreement never rewrites gold.'})
    write('five_case_ambiguity_diagnostic.json',{'cases':diagnostic,'typed_recognition':rate(sum(x['typed_correct'] for x in diagnostic),5),
          'safe_non_execution':rate(sum(not x['execution'] for x in diagnostic),5),'false_execution_count':sum(x['execution'] for x in diagnostic),
          'author_scalar_assertions':'Excluded for all five: intentionally unknown query operands, not missing gold.', 'not_tuning_targets':True})
    write('scoring_complete.json',{'completed_at_utc':datetime.now(timezone.utc).isoformat(),'prediction_sha256':sha(prediction_path),
          'scoring_parser_calls':len(parser_calls),'scored_contexts':len(scorer_rows),'metrics':all_summary,'cohorts':by_cohort,
          'strict_error_contexts':len(failures),'indeterminate_error_contexts':sum(x['indeterminate_dimensions']>0 for x in failures)})
    assert not parser_calls
    sys.setprofile(None)
    print(json.dumps({'scored':len(scorer_rows),'typed_accuracy':all_summary['typed_accuracy'],'execution_accuracy':all_summary['execution_accuracy'],
          'false_execution':all_summary['false_execution_count'],'missed_execution':all_summary['missed_execution_count'],
          'error_contexts':len(failures),'top_categories':category_counts.most_common(5),'scoring_parser_calls':len(parser_calls)}))

if __name__ == '__main__':
    main()
