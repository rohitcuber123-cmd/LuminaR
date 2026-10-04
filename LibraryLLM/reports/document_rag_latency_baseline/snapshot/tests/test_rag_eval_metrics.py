"""Evaluation semantics, especially overlapping source spans."""
from rag.evaluation.metrics import aggregate, evaluate_query, oracle


def test_overlap_equivalence_and_reciprocal_rank():
    query = {'accepted_passages': [
        {'source_start': 100, 'source_end': 200, 'relevance_grade': 2},
        {'source_start': 500, 'source_end': 600, 'relevance_grade': 2},
        {'source_start': 700, 'source_end': 800, 'relevance_grade': 1},
    ]}
    chunks = {'bad': {'start': 0, 'end': 80},
              'first': {'start': 110, 'end': 220},
              'overlap_copy': {'start': 90, 'end': 190},
              'support_only': {'start': 700, 'end': 800},
              'second': {'start': 490, 'end': 590}}
    row = evaluate_query(query,
                         ['bad', 'first', 'overlap_copy', 'support_only', 'second'],
                         chunks)
    assert row['first_rank'] == 2
    assert row['mrr'] == 0.5
    assert row['hit']['1'] == 0 and row['hit']['3'] == 1
    assert row['recall']['3'] == 0.5  # overlap copy is the same source span
    assert row['recall']['5'] == 1.0  # supporting grade 1 is not primary gold


def test_boundary_threshold_and_questionable_exclusion():
    query = {'accepted_passages': [
        {'source_start': 100, 'source_end': 200, 'relevance_grade': 2}]}
    chunks = {'just_below': {'start': 100, 'end': 179},
              'enough': {'start': 120, 'end': 200}}
    row = evaluate_query(query, ['just_below', 'enough'], chunks)
    assert row['first_rank'] == 2
    assert row['hit']['1'] == 0 and row['hit']['3'] == 1
    assert evaluate_query({'accepted_passages': []}, ['enough'], chunks) is None


def test_macro_metrics_and_oracle():
    query = {'accepted_passages': [
        {'source_start': 100, 'source_end': 200, 'relevance_grade': 2}]}
    chunks = {'good': {'start': 100, 'end': 200},
              'bad': {'start': 0, 'end': 90}}
    first = evaluate_query(query, ['good'], chunks)
    second = evaluate_query(query, ['bad', 'good'], chunks)
    metrics = aggregate([first, second, None])
    assert metrics['evaluated'] == 2
    assert metrics['mrr'] == 0.75
    assert metrics['hit']['1'] == 0.5
    assert oracle([first, second, None], 5)['mrr'] == 1.0
