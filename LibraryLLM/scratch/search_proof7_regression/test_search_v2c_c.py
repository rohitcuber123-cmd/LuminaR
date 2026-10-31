"""Categorical calibration is evidence, never execution or authorization authority."""
from copy import deepcopy
import pytest
from scratch.search_v2c_c5er.candidate_search_v4.query_calibration import assess
from scratch.search_proof_recovery_v7.parser import parse_query
from scratch.search_proof_recovery_v7.parser import validate, decide

@pytest.mark.parametrize('kind,policy', [('AMBIGUOUS', 'CLARIFY'), ('INCOMPLETE', 'CLARIFY'), ('UNSUPPORTED', 'UNSUPPORTED'), ('CONTRADICTORY', 'REJECT_CONTRADICTION')])
def test_safety_decision_overrides_heuristic_evidence(kind, policy):
    p = parse_query('fiction rated above 4', ['Fiction'])
    decide(p, kind, fields=['rating'])
    before = deepcopy(vars(p))
    assessment = assess(p)
    assert assessment['policy'] == policy and vars(p) == before
    assert assessment['slots']['rating_operator']['recognized']
    assert assessment['score_kind'] == 'categorical heuristic evidence; not probability'

def test_repairs_get_visible_interpretation_without_mutating_plan():
    p = parse_query('fiction above rating of 3', ['Fiction'])
    before = deepcopy(vars(p))
    r = assess(p)
    assert r['policy'] == 'EXECUTE_WITH_NOTICE' and vars(p) == before
    assert any((s['source_evidence'] for s in r['slots'].values()))

def test_zero_rating_is_a_recognized_slot_and_evidence_is_copied():
    p = parse_query('rated at least 0')
    r = assess(p)
    assert r['slots']['rating_operator']['recognized']
    r['slots']['rating_operator']['source_evidence'][0]['operator'] = 'invented'
    assert p.constraint_candidates[0]['operator'] != 'invented'

def test_evaluation_numeric_equivalence_does_not_invent_false_filters():
    from scripts.search_v2c_c_evaluate import atoms
    assert atoms({'rating_min': 3, 'rating_min_exclusive': True}) == atoms({'rating_min': 3.0, 'rating_min_exclusive': True})
    assert atoms({'rating_min': 3, 'rating_min_exclusive': True}) != atoms({'rating_min': 3.0, 'rating_min_exclusive': False})
    assert atoms({'subjects': ['Private']}, False) == set()

def test_semantic_metric_keeps_technical_punctuation():
    from scripts.search_v2c_c_evaluate import norm, token_f1
    assert norm('C++') != 'c' and norm('C#') != 'c'
    assert token_f1('neural networks', 'networks') == pytest.approx(2 / 3)
