"""Verify C5B and prepare C5C inputs without importing/executing the parser."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json

R = Path('reports')
P = 'search_v2c_c5c_'
B = 'search_v2c_c5b_'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))

def rows(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf8').splitlines() if s.strip()]

def write(name, value):
    path = R / (P + name)
    with path.open('x', encoding='utf8') as out:
        out.write(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n')

def jsonl(name, values):
    with (R / (P + name)).open('x', encoding='utf8') as out:
        for value in values:
            out.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + '\n')

def main():
    assert not list(R.glob(P + '*')), 'C5C already exists; never overwrite an evaluation attempt.'
    base = load(R / (B + 'baseline.json'))
    freeze = load(R / (B + 'freeze_manifest.json'))
    old = load(R / 'search_v2c_c5a_freeze_manifest.json')
    validation = load(R / (B + 'report_validation.json'))
    maps = {'C5B_protected_existing': base['protected_files'], 'C5A_payload': old['files'],
            'C5B_payload': freeze['files'], 'C5B_final_reports': validation['evidence_sha256'],
            'evaluators': freeze['evaluator_hashes_unchanged'], 'native': freeze['native_harness_hashes_unchanged'],
            'production_parser_policy': freeze['production_parser_and_policy_hashes'],
            'heldout_manifests': freeze['heldout_manifest_hashes']}
    checked = {kind: {'files': len(values), 'mismatches': [p for p, h in values.items() if sha(p) != h]}
               for kind, values in maps.items()}
    assert not any(v['mismatches'] for v in checked.values()), checked
    assert sha(R / 'search_v2c_c5a_freeze_manifest.json') == base['C5A_freeze_sha256']
    isolation = load(R / (B + 'structural_isolation.json'))
    # Hash-only reads. No heldout file is decoded or inspected.
    assert all(sha(x['path']) == x['sha256_after'] and x['unchanged'] for x in isolation['preservation'])
    admission = load(R / (B + 'corpus_admission.json'))
    readiness = load(R / (B + 'readiness.json'))
    assert admission['candidate_freeze_sha256'] == sha(R / (B + 'freeze_manifest.json'))
    assert admission['pre_admission_record_sha256'] == sha(R / (B + 'five_case_resolution.json'))
    assert all(admission['readiness_gates'].values()) and len(admission['cases']) == 5
    assert all(x['final_state'] == 'REVISED_AND_ACCEPTED' for x in admission['cases'])
    assert freeze['status'] == 'FROZEN_READY_CANDIDATE' and readiness['FINAL'] == 'PASS'
    provenance = load(R / (B + 'review_provenance.json'))
    assert not provenance['same_agent_self_review']
    for key in ['input', 'output']:
        assert sha(R / provenance[key + '_file']) == provenance[key + '_sha256']
    review = load(R / (B + 'independent_review_output_v2.json'))
    assert review['aggregate']['accepted'] == 5 and review['reviewer']['fresh_independent_context']
    assert all(n == 0 for n in review['audit']['prohibited_calls'].values())
    assert all(n == 0 for n in review['audit']['prohibited_data_reads'].values())
    corpus = rows(R / (B + 'calibration_cases.jsonl'))
    labels = {r['case_id']: r for r in rows(R / (B + 'expected_labels.jsonl'))}
    assert len(corpus) == len(labels) == 1024 and len({r['case_id'] for r in corpus}) == 1024
    caps = load(R / 'search_v2c_c5a_capability_matrix.json')['scopes']
    scopes = load(R / 'search_v2c_c_scope_vocabularies.json')
    for value in caps.values():
        assert value['subjects'] == scopes[value['snapshot_scope_key']]['subjects']
        assert value['capabilities'] == scopes[value['snapshot_scope_key']]['capabilities']
    admitted_ids = {x['case_id'] for x in admission['cases'] if x['quota_eligible'] and x['required_gold_complete']}
    population, masks, inputs, stale_eligibility_flags = [], [], [], []
    for case in corpus:
        for k, v in labels[case['case_id']].items():
            assert case[k] == v, (case['case_id'], k)
        assert case['partition'] == 'calibration'
        assert case['capability_profile']['capabilities'] == caps[case['scope_type']]['capabilities']
        native = case['unit'] == 'NATIVE_SEQUENCE' or case['requires_native_execution']
        if native:
            category, reason = 'NATIVE_SEQUENCE', 'Native sequence: all single-turn parser plan metrics inapplicable.'
        elif case['example_class'] == 'DERIVATIVE':
            category, reason = 'UNREVIEWED_DERIVATIVE', 'Derivative lacks independent gold review; no core or separate parser scoring.'
        elif case['review_status'].startswith('REJECTED'):
            category, reason = 'REJECTED_CORE', 'Rejected value-only diversity case; no accepted core credit or scoring.'
        elif case['review_status'] != 'AI_REVIEWED':
            category, reason = 'UNREVIEWED_OR_PARTIAL', 'Independent required-label review not established.'
        else:
            category = 'NEW_REVIEWED_CORE' if case['example_class'] == 'CORE' else 'RETAINED_REVIEWED_CORE'
            reason = 'Independently reviewed parser context with applicable typed and execution labels.'
        eligible = category in ['NEW_REVIEWED_CORE', 'RETAINED_REVIEWED_CORE']
        if eligible:
            assert case['parser_evaluable'] and type(case['expected_executable']) is bool
            assert case['expected_typed_decision'] in ['EXECUTABLE', 'EXECUTABLE_WITH_NOTICE', 'AMBIGUOUS', 'INCOMPLETE', 'UNSUPPORTED', 'CONTRADICTORY']
            if category == 'NEW_REVIEWED_CORE':
                # C5B's actual quota validator uses CORE + AI_REVIEWED + review_complete;
                # the append-only final admission supersedes the five inherited false flags.
                assert case['review_complete'] and not case['parser_output_used_for_authoring']
                if not case['core_eligible']:
                    assert case['case_id'] in admitted_ids
                    stale_eligibility_flags.append(case['case_id'])
                assert all(case['metric_applicability'][k]['status'] == 'APPLICABLE' for k in ['typed_decision', 'executable'])
            else:
                assert case['metric_applicability']['parser_plan_metrics']['status'] == 'APPLICABLE'
                assert case['reviewer_type'] == 'fresh_independent_output_blind_AI'
            # Metadata needed by the runner is strictly input-only. Strata/gold/review rationales never leave this process.
            inputs.append({'case_id': case['case_id'], 'query_text': case['query_text'], 'scope_type': case['scope_type'],
                           'workspace_type': case['workspace_type'], 'search_mode': case['search_mode']})
        population.append({'case_id': case['case_id'], 'category': category, 'eligible': eligible, 'reason': reason,
                           'example_class': case['example_class'], 'review_status': case['review_status'], 'unit': case['unit'],
                           'scope': case['scope_type'], 'stratum': case['decision_stratum'], 'input_record_sha256': digest(case),
                           'typed_gold': case['expected_typed_decision'], 'execution_gold': case['expected_executable'],
                           'valid_negative_execution_gold': eligible and case['expected_executable'] is False})
        masks.append({'case_id': case['case_id'], 'eligible': eligible, 'metric_applicability': case['metric_applicability'],
                      'meaning': 'APPLICABLE_ABSENCE is gold absence; false executable is a valid negative; UNRESOLVED operands are excluded, not missing required decision gold.'})
    counts = dict(Counter(x['category'] for x in population))
    assert counts == {'NATIVE_SEQUENCE': 230, 'RETAINED_REVIEWED_CORE': 50, 'NEW_REVIEWED_CORE': 594, 'UNREVIEWED_DERIVATIVE': 149, 'REJECTED_CORE': 1}, counts
    assert len(inputs) == 644
    # Preserve every prior Search milestone, including C5B append-only final admission/report validation.
    protected = dict(base['protected_files'])
    protected.update({str(p): sha(p) for p in R.glob('search_v2c_c*') if p.is_file() and not p.name.startswith(P)})
    protected.update({str(p): sha(p) for p in Path('scripts').glob('search_v2c_c*.py') if not p.name.startswith(P)})
    write('preflight.json', {'status': 'PASS', 'at_utc': datetime.now(timezone.utc).isoformat(), 'checks': checked,
          'C5B_freeze_sha256': sha(R / (B + 'freeze_manifest.json')), 'C5B_admission_sha256': sha(R / (B + 'corpus_admission.json')),
          'C5A_freeze_sha256': sha(R / 'search_v2c_c5a_freeze_manifest.json'), 'protected_files': protected,
          'heldout_hash_only_verification': isolation['preservation'], 'heldout_rows_decoded': 0,
          'review_provenance': 'PASS', 'final_admission': 'PASS', 'parser_executions_before_preflight': 0,
          'authorization': 'User C5C instruction explicitly authorizes frozen parser scoring only; C5B historical authorization field remains NO unchanged.',
          'authorization_instruction_sha256': sha(r'C:\Users\balak\.codex\attachments\2f0c8016-1435-44f6-b3b2-abe3f82b41e5\Pasted text.txt'),
          'preflight_attempts': [{'attempt': 1, 'result': 'STOPPED_BEFORE_PARSER', 'exception': 'AssertionError on inherited core_eligible=false for five finally admitted revised rows', 'parser_calls': 0, 'report_writes': 0},
                                {'attempt': 2, 'result': 'PASS', 'resolution': 'Use actual frozen C5B quota rule plus hash-bound final admission, as user explicitly instructs. No frozen file edited.'}],
          'stale_inherited_core_eligible_flags': stale_eligibility_flags})
    write('eligibility.json', {'total': 1024, 'eligible': 644, 'excluded': 380, 'category_counts': counts, 'cases': population,
          'primary_population': '594 independently reviewed new core + 50 retained independently reviewed original parser contexts. Always report cohorts separately.',
          'review_counts': dict(Counter(x['review_status'] for x in corpus)), 'historical_cases_authorized_for_reevaluation': 50,
          'native_AI_reviewed_not_parser_eligible': 30, 'stale_core_flag_ids_superseded_by_final_admission': stale_eligibility_flags})
    write('applicability_audit.json', {'cases': masks, 'eligible_mask_status_counts': dict(Counter(v['status'] for r in corpus if r['case_id'] in {x['case_id'] for x in inputs} for v in r['metric_applicability'].values())),
          'confidence_gold': 'No numerical target; descriptive native signals only.',
          'scope_actor_accuracy': 'N/A: scope/workspace are supplied evaluation context, not parser-selected outputs. No role prediction oracle exists.',
          'field_rules': {'APPLICABLE': 'Compare resolved value only.', 'APPLICABLE_ABSENCE': 'Assert absence using established plan default.',
                         'PARTIALLY_APPLICABLE': 'Compare common resolved scalar or list subset; do not assert unresolved remainder.',
                         'UNRESOLVED': 'Exclude operand assertion; retain definitive decision/execution gold.', 'INAPPLICABLE': 'Exclude metric; never count as failure.'}})
    jsonl('parser_inputs.jsonl', inputs)
    write('parser_configuration.json', {'version': 'C5C-offline-frozen-parser-1', 'input_sha256': sha(R / (P + 'parser_inputs.jsonl')),
          'caps_path': str(R / 'search_v2c_c5a_capability_matrix.json'), 'caps_sha256': sha(R / 'search_v2c_c5a_capability_matrix.json'),
          'parser_call': 'validate(parse_query(query_text, frozen_scope.subjects, search_mode), frozen_scope.capabilities)',
          'existing_evaluator': 'scripts/search_v2c_c5_baseline.py:main parser path via scripts/search_v2c_c_evaluate.py:evaluate_case',
          'scoring': 'Reuse unchanged C4 rescore, norm, atoms, BOTH equivalence and C5 protected-content convention; apply frozen per-label masks. No legacy entry point invoked.',
          'parser_gold_separation': 'Separate prediction process reads sanitized parser_inputs + frozen capability snapshot + configuration only; corpus and normative labels inaccessible there.',
          'network': 'Blocked by Python audit hook.', 'filesystem_writes': 'Only new reports/search_v2c_c5c_* files allowed; no bytecode.',
          'database_application_modules': 'Not imported; no issuance, session or execution API.', 'model_inference': 'None. Frozen parser is deterministic local Python.',
          'prediction_calls_planned': 644, 'retries_planned': 0, 'threshold_fitting': False, 'policy_candidates': 0,
          'parser_source_hashes': {**freeze['production_parser_and_policy_hashes'], **{str(p): sha(p) for p in Path('search').glob('query_*.py')}}, 'evaluator_hashes': freeze['evaluator_hashes_unchanged'],
          'frozen_before_prediction_scripts': {str(p): sha(p) for p in Path('scripts').glob(P + '*.py')}})
    print(json.dumps({'preflight': 'PASS', 'eligible': 644, 'excluded': 380, 'categories': counts, 'protected_files': len(protected), 'parser_calls': 0}))

if __name__ == '__main__':
    main()
