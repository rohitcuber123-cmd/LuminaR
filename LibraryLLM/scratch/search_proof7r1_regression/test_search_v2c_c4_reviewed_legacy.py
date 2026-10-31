"""Versioned C4 contract view; original V2C-A source and assertions remain immutable."""
'Pre-authored candidate labels, exact predicates, spans and adversarial bounds.'
import json
from pathlib import Path
import pytest
from scratch.search_proof_recovery_v7r1.parser import parse_query, matches
from scratch.search_proof_recovery_v7r1.refinement import refine
from scratch.search_proof_recovery_v7r1.parser import validate, executable
ROOT = Path('D:\\SDC\\LibraryLLM')
FACETS = [r['subject'] for r in json.loads((ROOT / 'reports/search_v2a_facet_vocabulary.json').read_text())['results']]
GOLD = [json.loads(line) for line in (ROOT / 'reports/search_v2c_a_gold_queries.jsonl').read_text().splitlines()]
CONTRACT = json.loads((ROOT / 'reports/search_v2c_c4_reviewed_contract.json').read_text())
for case in GOLD:
    case['expected'].update(CONTRACT['overrides'].get(case['id'], {}))
META = [json.loads(line) for line in (ROOT / 'reports/search_v2c_a_metamorphic_queries.jsonl').read_text().splitlines()]

def plan_for(case):
    if case.get('sequence'):
        plan = None
        for q in case['sequence']:
            plan, _ = refine(plan, q, FACETS)
            validate(plan)
        return plan
    return parse_query(case['query'], FACETS, case.get('mode', 'SMART'))

def mismatches(case, plan):
    actual = {**vars(plan), 'decision_type': plan.decision.get('decision_type', 'EXECUTABLE')}
    return {k: {'expected': v, 'actual': actual.get(k)} for k, v in case['expected'].items() if actual.get(k) != v}

@pytest.mark.parametrize('case', GOLD, ids=lambda c: c['id'])
def test_curated_candidate_plan(case):
    plan = plan_for(case)
    assert not mismatches(case, plan), mismatches(case, plan)
    for c in plan.constraint_candidates:
        text = c.get('source_query', plan.raw_query)
        assert 0 <= c['source_span_start'] < c['source_span_end'] <= len(text)
        assert text[c['source_span_start']:c['source_span_end']] == c['source_text']
    if not executable(plan):
        assert not matches(plan, {'title': 'Any book', 'subjects': FACETS, 'average_rating': 5, 'has_online': True, 'has_physical': True})

@pytest.mark.parametrize('case', META, ids=lambda c: c['id'])
def test_seeded_composition(case):
    p = plan_for(case)
    assert not mismatches(case, p), mismatches(case, p)

@pytest.mark.parametrize('operator,value,accepted', [('above', 4, [False, False, True]), ('at least', 4, [False, True, True]), ('below', 4, [True, False, False]), ('at most', 4, [True, True, False])])
def test_exact_rating_predicate(operator, value, accepted):
    p = parse_query(f'rating {operator} {value}')
    assert [matches(p, {'average_rating': r, 'rating_count': 1}) for r in (3.99, 4, 4.01)] == accepted
    assert not matches(p, {})

@pytest.mark.parametrize('operator,accepted', [('after', [False, False, True]), ('since', [False, True, True]), ('before', [True, False, False])])
def test_exact_year_predicate(operator, accepted):
    p = parse_query(f'published {operator} 2020')
    assert [matches(p, {'publication_year': r}) for r in (2019, 2020, 2021)] == accepted
    assert not matches(p, {})

def test_quoted_technical_and_unicode_source_evidence():
    p = parse_query('  Fiction books above a rating of ３ about wizards', FACETS)
    assert p.rating_min == 3 and p.semantic_text == 'wizards'
    for c in p.constraint_candidates:
        assert p.raw_query[c['source_span_start']:c['source_span_end']] == c['source_text']
    p = parse_query('books about "rating above 4"', FACETS)
    assert p.rating_min is None and p.semantic_text == 'rating above 4'
    assert parse_query('history of events after 1945', FACETS).year_min is None

def test_bounded_inputs_and_public_no_provenance():
    with pytest.raises(ValueError):
        parse_query('x' * 501)
    p = parse_query('fiction 4', FACETS)
    assert not any((k in p.public()['decision'] for k in ('recognized_candidates', 'relevant_source_spans', 'unresolved_fragments')))

@pytest.mark.parametrize('query,decision', [('fiction rated above', 'INCOMPLETE'), ('fiction rating >', 'INCOMPLETE'), ('fiction rating above banana', 'INCOMPLETE'), ('fiction published after tomorrow', 'INCOMPLETE'), ('fiction rated above -1', 'UNSUPPORTED'), ('online books not online', 'CONTRADICTORY'), ('fiction without online books', 'EXECUTABLE')])
def test_independent_review_guards(query, decision):
    p = parse_query(query, FACETS)
    assert p.decision['decision_type'] == decision
    if query == 'fiction without online books':
        assert p.excluded_formats == ['ONLINE'] and (not p.formats)

@pytest.mark.parametrize('query', ['books about events between 1940 and 1950', 'books about history from 2020 onward', 'history from 2020 onward'])
def test_historical_ranges_are_topics(query):
    p = parse_query(query, FACETS)
    assert p.year_min is None and p.year_max is None

def test_mixed_negative_refinement_and_instead_provenance():
    old = parse_query('books about machine learning', FACETS)
    p, _ = refine(old, 'not romance rated above 4', FACETS)
    assert p.rating_min == 4 and p.rating_min_exclusive and (p.exclude_terms == CONTRACT['records']['mixed_refinement']['exclude_terms']) and (p.exclude_subjects == CONTRACT['records']['mixed_refinement']['exclude_subjects']) and (p.semantic_text == 'machine learning')
    p, _ = refine(old, 'not online', FACETS)
    assert p.excluded_formats == ['ONLINE']
    p, _ = refine(old, 'show me fiction instead', FACETS)
    assert p.subjects == ['Fiction'] and any((c['field'] == 'subjects' and c['source_text'] == 'show me fiction instead' for c in p.constraint_candidates))

def test_physical_borrow_uses_stock_not_online_entitlement():
    p = parse_query('available to borrow physically')
    assert p.formats == ['PHYSICAL'] and p.availability == 'REQUESTABLE' and p.physical_available_only
    assert not matches(p, {'has_physical': True, 'has_online': True, 'requestable_count': 0})
    assert matches(p, {'has_physical': True, 'circulation_status': 'CIRCULATING', 'requestable_count': 1})

def test_whitespace_does_not_truncate_exclusion_or_author():
    p = parse_query('AI but not deep  learning rated above 4', FACETS)
    assert p.rating_min == 4 and [s.casefold() for s in p.exclude_terms] == ['deep learning']
    p = parse_query('books by Isaac  Asimov rated above 4', FACETS)
    assert p.author_text.split() == ['isaac', 'asimov'] and p.rating_min == 4
