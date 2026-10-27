"""Pre-inference acceptance freeze for C5E-R candidate V4."""
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, xml.etree.ElementTree as ET

R = Path('reports')
P = 'search_v2c_c5er_'
C = Path('scratch/search_v2c_c5er/candidate_search_v4')

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def load(p):
    return json.loads(Path(p).read_text(encoding='utf8'))

def write(n, v):
    with (R / (P + n)).open('x', encoding='utf8') as f:
        json.dump(v, f, sort_keys=True, indent=2, ensure_ascii=False)

def xml(p, expected):
    s = next(ET.parse(p).getroot().iter('testsuite'))
    assert int(s.attrib['tests']) == expected and int(s.attrib['failures']) == int(s.attrib['errors']) == 0

def main():
    pre = load(R / (P + 'preflight.json'))
    assert all(sha(p) == h for p, h in pre['protected_files'].items())
    assert load(R / (P + 'v2_structural_isolation.json'))['status'] == 'PASS'
    xml(R / (P + 'v4_regression_attempt1.xml'), 1418)

    native = load(R / (P + 'offline_native_components_v4.json'))
    assert native['component_search_checks'] == 40 and native['status'] == 'PASS_WITH_LIMITED_QUALIFICATION'

    pop = R / (P + 'reviewed_population.jsonl')
    rows = [json.loads(s) for s in pop.read_text(encoding='utf8').splitlines() if s.strip()]
    author = [json.loads(s) for s in (R / (P + 'authored_v2.jsonl')).read_text(encoding='utf8').splitlines() if s.strip()]
    assert len(rows) == 150 and {r['case_id'] for r in rows} == {r['case_id'] for r in author}

    old = {r['case_id']: r for r in author}
    keys = ['case_id', 'query_text', 'scope_type', 'workspace_type', 'search_mode']
    assert all(all(r[k] == old[r['case_id']][k] for k in keys) for r in rows)

    review = load(R / (P + 'independent_review.json'))
    independent = {r['case_id']: r for r in review['cases']}
    assert all(r['expected_typed_decision'] == independent[r['case_id']]['expected_typed_decision'] and
               r['expected_executable'] == independent[r['case_id']]['expected_executable'] for r in rows)
    assert len({(r['scope_type'], r['expected_typed_decision']) for r in rows}) == 30
    assert all(sum(r['scope_type'] == s and r['expected_typed_decision'] == t for r in rows) == 5
               for s, t in {(r['scope_type'], r['expected_typed_decision']) for r in rows})

    inputs = R / (P + 'independent_parser_inputs.jsonl')
    with inputs.open('x', encoding='utf8') as f:
        for r in rows:
            f.write(json.dumps({k: r[k] for k in keys}, sort_keys=True, ensure_ascii=False) + '\n')

    code = {str(p): sha(p) for p in C.glob('*.py')}
    code.update({str(p): sha(p) for p in [
        Path('scripts/search_v2c_c5er_evaluation_adapter_v2.py'),
        Path('scripts/search_v2c_c5er_reconcile.py')
    ]})
    frozen = dict(code)
    artifacts = [
        'acceptance_design.json', 'reviewed_population.jsonl', 'authored_v2.jsonl',
        'author_provenance_v2.json', 'independent_review.json', 'review_reconciliation.json',
        'v2_structural_isolation.json', 'v2_sealed_structural_isolation.json',
        'v2_sealed_access_audit.json', 'independent_parser_inputs.jsonl',
        'v4_regression_attempt1.xml', 'offline_native_components_v4.json',
        'mask_adapter_v2_final_tests.xml'
    ]
    frozen.update({str(R / (P + n)): sha(R / (P + n)) for n in artifacts})
    frozen[str(Path(__file__).relative_to(Path.cwd()))] = sha(__file__)

    write('candidate_freeze.json', {
        'candidate_id': 'search-v2c-c5er-disabled-candidate-4',
        'at_utc': datetime.now(timezone.utc).isoformat(),
        'files': frozen,
        'primary_acceptance_not_started': True,
        'acceptance_primary_attempts': 1,
        'reviewed_contexts': 150,
        'scope_stratum_cells': 30,
        'contexts_per_cell': 5,
        'shared_semantic_patterns': len({r['shared_semantic_pattern_id'] for r in rows}),
        'independent_topologies': 30,
        'regression_assertions': 1418,
        'native_component_checks': 40,
        'production_activation': False,
        'scoring_contract': 'Evaluation adapter V2, prefix scalar masks, formats-only BOTH equivalence, exact whole-word exclusion distinct from substring, no invented fuzzy matches.',
        'independence_limits': 'AI author and AI independent reviewer; human 0. Blind reviewer reviewed without labels or candidate code.'
    })

    cap = R / 'search_v2c_c5a_capability_matrix.json'
    write('independent_parser_configuration.json', {
        'candidate_id': 'search-v2c-c5er-disabled-candidate-4',
        'input_sha256': sha(inputs),
        'caps_path': str(cap),
        'caps_sha256': sha(cap),
        'prediction_calls_planned': 150,
        'parser_source_hashes': {str(p): sha(p) for p in C.glob('*.py')},
        'frozen_before_prediction_scripts': code,
        'gold_population_path': str(pop),
        'gold_population_sha256': sha(pop),
        'candidate_freeze_sha256': sha(R / (P + 'candidate_freeze.json')),
        'gold_decoded_by_predictor': False,
        'gold_file_reads_by_predictor': 0,
        'activation': False,
        'model_calls_planned': 0,
        'primary_attempts': 1
    })

    print(json.dumps({
        'frozen_candidate': 'search-v2c-c5er-disabled-candidate-4',
        'contexts': 150,
        'scope_stratum_cells': 30,
        'files': len(frozen),
        'candidate_freeze_sha256': sha(R / (P + 'candidate_freeze.json'))
    }))

if __name__ == '__main__':
    main()
