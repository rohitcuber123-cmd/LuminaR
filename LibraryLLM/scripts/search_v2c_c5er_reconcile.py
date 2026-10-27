"""Reconcile fresh C5E-R authored cases with independent blind review."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json

R = Path('reports')
P = 'search_v2c_c5er_'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    authored_path = R / (P + 'authored_v2.jsonl')
    review_path = R / (P + 'independent_review.json')
    prov_path = R / (P + 'author_provenance_v2.json')
    packet_path = R / (P + 'v2_blind_reviewer_packet.json')

    authored_rows = [json.loads(s) for s in authored_path.read_text(encoding='utf8').splitlines() if s.strip()]
    review_data = json.loads(review_path.read_text(encoding='utf8'))
    reviewer_cases = review_data['cases']

    assert len(authored_rows) == 150
    assert len(reviewer_cases) == 150

    auth_map = {x['case_id']: x for x in authored_rows}
    rev_map = {x['case_id']: x for x in reviewer_cases}
    assert set(auth_map) == set(rev_map)

    reconciled_rows = []
    case_summaries = []
    disagreements = []

    for cid in sorted(auth_map):
        a = auth_map[cid]
        r = rev_map[cid]

        typed_agree = a['expected_typed_decision'] == r['expected_typed_decision']
        exec_agree = a['expected_executable'] == r['expected_executable']
        if not typed_agree or not exec_agree:
            disagreements.append({'case_id': cid, 'author_decision': a['expected_typed_decision'], 'reviewer_decision': r['expected_typed_decision']})

        # Reconciled record preserves metadata from author, normative judgments from reviewer
        row = {
            'case_id': cid,
            'query_text': a['query_text'],
            'scope_type': a['scope_type'],
            'workspace_type': a['workspace_type'],
            'search_mode': a['search_mode'],
            'decision_stratum': a['decision_stratum'],
            'family_id': a.get('family_id'),
            'structural_component_id': a.get('structural_component_id'),
            'shared_semantic_pattern_id': a.get('shared_semantic_pattern_id'),
            'expected_typed_decision': r['expected_typed_decision'],
            'expected_executable': r['expected_executable'],
            'expected_hard_constraints': r['expected_hard_constraints'],
            'expected_sort': r.get('expected_sort'),
            'expected_semantic_remainder': r.get('expected_semantic_remainder'),
            'expected_soft_preferences': r.get('expected_soft_preferences', a.get('expected_soft_preferences', [])),
            'expected_notices': r.get('expected_notices', a.get('expected_notices', [])),
            'unadapted_mandatory_assertions': r.get('unadapted_mandatory_assertions', a.get('expected_unadapted_mandatory_assertions', [])),
            'metric_applicability': r['metric_applicability'],
            'semantic_justification': r.get('semantic_justification', a.get('semantic_justification')),
            'author_original_record': a,
            'independent_reviewer_original_record': r,
            'reconciliation_metadata': {
                'actual_reviewer_identity': review_data['reviewer']['task_identity'],
                'model_family': review_data['reviewer']['declared_model_family'],
                'human_reviewed': 0,
                'author_reviewer_decision_agreement': typed_agree and exec_agree,
                'source_author_record_preserved': True,
                'source_reviewer_record_preserved': True
            }
        }
        reconciled_rows.append(row)
        case_summaries.append({
            'case_id': cid,
            'typed_agreement': typed_agree,
            'executable_agreement': exec_agree,
            'both_raw_records_preserved': True,
            'semantic_agreement_basis': r.get('semantic_justification')
        })

    out_pop = R / (P + 'reviewed_population.jsonl')
    with out_pop.open('w', encoding='utf8') as f:
        for r in reconciled_rows:
            f.write(json.dumps(r, sort_keys=True, ensure_ascii=False) + '\n')

    reconciliation = {
        'status': 'FROZEN_RECONCILED_PRE_INFERENCE',
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'case_count': 150,
        'typed_disagreements': len(disagreements),
        'executable_disagreements': len(disagreements),
        'disagreements': disagreements,
        'author_source_sha256': sha(authored_path),
        'review_source_sha256': sha(review_path),
        'reviewed_population_sha256': sha(out_pop),
        'cases': case_summaries
    }
    out_rec = R / (P + 'review_reconciliation.json')
    with out_rec.open('w', encoding='utf8') as f:
        json.dump(reconciliation, f, indent=2, sort_keys=True, ensure_ascii=False)

    print(json.dumps({
        'status': reconciliation['status'],
        'case_count': 150,
        'typed_disagreements': len(disagreements),
        'population_sha256': reconciliation['reviewed_population_sha256']
    }))

if __name__ == '__main__':
    main()
