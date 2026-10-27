"""Independent expected clause semantics against accepted canonical vocabulary."""
import json
from pathlib import Path

import pytest

from search.query_plan import FacetVocabulary, matches, parse_query

FACETS = [r['subject'] for r in json.loads((Path(__file__).resolve().parents[1] /
    'reports/search_v2a_facet_vocabulary.json').read_text(encoding='utf8'))['results']]

CONTRADICTIONS = [
    'include romance but exclude romance', 'include Fiction and exclude Fiction',
    'romance excluding romance', 'exclude Romance but include Romance',
    'Romance included but Romance excluded', 'include Romance, then exclude Romance',
    'include Romance while excluding Romance', 'include Romance, exclude Romance',
    'include Fiction and Romance but exclude Romance',
    'include Fiction but exclude Fiction and Romance',
    'include Romance except Romance', 'with Romance but without Romance',
    'include sci-fi but exclude Science Fiction',
]


def assert_evidence(plan):
    for c in plan.constraint_candidates:
        raw = c.get('source_query', plan.raw_query)
        assert 0 <= c['source_span_start'] < c['source_span_end'] <= len(raw)
        assert raw[c['source_span_start']:c['source_span_end']] == c['source_text']


@pytest.mark.parametrize('query', CONTRADICTIONS)
def test_canonical_clause_conflict(query):
    plan = parse_query(query, FACETS)
    assert plan.decision['decision_type'] == 'CONTRADICTORY'
    assert plan.decision['reason_code'] == 'SUBJECT_INCLUDE_EXCLUDE'
    assert set(plan.subjects) & set(plan.exclude_subjects)
    assert plan.semantic_text is None
    assert plan.decision['relevant_source_spans']
    assert not matches(plan, {'title': 'Unrelated', 'subjects': FACETS})
    assert_evidence(plan)


@pytest.mark.parametrize('query,included,excluded,topic', [
    ('include Romance', ['Romance'], [], None),
    ('exclude Romance', [], ['Romance'], None),
    ('include Fiction but exclude Romance', ['Fiction'], ['Romance'], None),
    ('include Romance but exclude Fiction', ['Romance'], ['Fiction'], None),
    ('include Mystery but exclude Horror', ['Mystery'], ['Horror'], None),
    ('include Science Fiction and exclude Romance', ['Science fiction'], ['Romance'], None),
    ('include Fiction and Mystery but exclude Romance', ['Fiction','Mystery'], ['Romance'], None),
    ('include fiction but exclude romance about wizards', ['Fiction'], ['Romance'], 'wizards'),
    ('include Fiction rated above 3 but exclude Romance', ['Fiction'], ['Romance'], None),
])
def test_valid_composition(query, included, excluded, topic):
    p = parse_query(query, FACETS)
    assert p.decision['decision_type'] == 'EXECUTABLE'
    assert p.subjects == included and p.exclude_subjects == excluded
    assert p.semantic_text == topic
    assert_evidence(p)


def test_include_list_keeps_existing_all_subjects_predicate():
    p = parse_query('include Fiction and Mystery but exclude Romance', FACETS)
    assert matches(p, {'subjects':['Fiction','Mystery'], 'title':'A book'})
    assert not matches(p, {'subjects':['Fiction'], 'title':'A book'})
    assert not matches(p, {'subjects':['Fiction','Mystery','Romance'], 'title':'A book'})
    assert parse_query('include Fiction or Mystery', FACETS).decision['decision_type'] == 'UNSUPPORTED'


@pytest.mark.parametrize('query', [
    'include Romance but exclude', 'exclude Romance but include', 'include but exclude Romance',
    'include Fiction and', 'exclude Romance or',
])
def test_incomplete_clause_is_not_a_topic(query):
    p = parse_query(query, FACETS)
    assert p.decision['decision_type'] == 'INCOMPLETE'
    assert p.semantic_text is None
    assert_evidence(p)


@pytest.mark.parametrize('query', [
    'books titled "Include Romance but Exclude Romance"',
    'books about the phrase "exclude Romance"', 'not only Romance',
    'Python 3', 'Catch-22', '1984',
])
def test_protected_text_has_no_subject_commands(query):
    p = parse_query(query, FACETS)
    assert p.decision['decision_type'] == 'EXECUTABLE'
    assert not p.subjects and not p.exclude_subjects and not p.exclude_terms
    assert not p.rating_min and not p.year_min
    assert_evidence(p)


def test_topical_negation_and_meaningful_connectors():
    p = parse_query('books about romance but not romance novels', FACETS)
    assert p.semantic_text == 'romance' and p.exclude_terms == ['romance novels']
    assert not p.subjects and not p.exclude_subjects
    p = parse_query('books about artificial intelligence excluding deep learning', FACETS)
    assert p.semantic_text == 'artificial intelligence' and p.exclude_terms == ['deep learning']
    assert parse_query('books about trials and errors but also hope', FACETS).semantic_text == 'trials errors but also hope'
    p = parse_query('non-fiction books', FACETS)
    assert p.subjects == [] and p.semantic_text == 'non-fiction' and not p.exclude_terms


def test_alias_scope_and_canonical_multiword_and():
    scoped = ['Detective and mystery stories','Science fiction','Romance']
    p = parse_query('include detective but exclude Detective and mystery stories', scoped)
    assert p.decision['decision_type'] == 'CONTRADICTORY'
    assert p.exclude_subjects == ['Detective and mystery stories']
    assert_evidence(p)
    assert FacetVocabulary(scoped).resolve('detective', fuzzy=False)[0] == scoped[0]
    for facets in [[], ['Romance'], ['Private Orchid']]:
        p = parse_query('include sci-fi but exclude Science Fiction', facets)
        assert p.decision['decision_type'] == 'UNSUPPORTED'
        assert 'Science fiction' not in p.subjects


def test_unicode_offsets_and_duplicate_clauses():
    p = parse_query('  include Ｒｏｍａｎｃｅ, but exclude Romance', FACETS)
    assert p.decision['decision_type'] == 'CONTRADICTORY'
    assert_evidence(p)
    p = parse_query('include Fiction and include Fiction but exclude Romance', FACETS)
    assert p.subjects == ['Fiction'] and p.exclude_subjects == ['Romance']
    assert p.semantic_text is None


def test_original_blocker_keeps_both_distinct_source_spans():
    p = parse_query(CONTRADICTIONS[0], FACETS)
    candidates = [c for c in p.constraint_candidates if c['field'] in ('subject','excluded_subject')]
    assert [(c['field'],c['source_text'],c['normalized_value']) for c in candidates] == [
        ('subject','include romance','Romance'), ('excluded_subject','exclude romance','Romance')]
    assert not any(k in p.public()['decision'] for k in ['recognized_candidates','relevant_source_spans'])
