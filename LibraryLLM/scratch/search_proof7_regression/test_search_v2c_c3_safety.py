"""Development-only structural safety and candidate-eligibility checks."""
import pytest
from scratch.search_proof_recovery_v7.parser import parse_query, matches
from scratch.search_proof_recovery_v7.parser import executable
from scratch.search_proof_recovery_v7.refinement import refine
FACETS = ['Fiction', 'Romance', 'Mystery', 'Wizards', 'Neural Networks', 'History']

@pytest.mark.parametrize('cue', ['exclude', 'without any', 'not', 'leave out', 'with no', 'minus'])
def test_canonical_negation_does_not_reject_incidental_title(cue):
    plan = parse_query(cue + ' Romance', FACETS)
    assert plan.exclude_subjects == ['Romance'] and (not plan.exclude_terms)
    assert matches(plan, {'title': 'Romance in the archives', 'subjects': ['History']})
    assert not matches(plan, {'title': 'The archives', 'subjects': ['Romance']})

@pytest.mark.parametrize('query', ['stories where characters do not trust machines', 'why not learn C++', 'books about the word not', 'books about things that are not numbers', 'not just Fiction, something about hope'])
def test_prose_negation_is_not_a_filter(query):
    plan = parse_query(query, FACETS)
    assert executable(plan) and (not plan.exclude_terms) and (not plan.exclude_subjects)

@pytest.mark.parametrize('query', ['must be Fiction and must never be Fiction', 'require Romance; forbid the Romance subject', 'Mystery is required and Mystery is forbidden', 'Wizards is mandatory; Wizards must be absent', 'physical only yet an online version is required', 'online-only Mystery that also must be physical', 'require an online version but disallow online', 'physical is mandatory but physical must be excluded', 'nothing physical, but a physical-only book is required', 'require both versions while excluding physical'])
def test_explicit_collisions_are_blocked(query):
    plan = parse_query(query, FACETS)
    assert plan.decision['decision_type'] == 'CONTRADICTORY'
    assert not matches(plan, {'subjects': FACETS, 'has_online': True, 'has_physical': True})

@pytest.mark.parametrize('query', ['books about .NET 8', 'why not learn C++', 'books about the word not'])
def test_technical_and_word_literals_survive(query):
    plan = parse_query(query, FACETS)
    entity = '.NET 8' if '.NET' in query else 'C++' if 'C++' in query else 'not'
    assert entity.casefold() in (plan.semantic_text or plan.title_text or '').casefold()
    assert plan.rating_min is None and plan.year_min is None

def test_author_and_negative_have_independent_source_boundaries():
    plan = parse_query('not about Borges; written by Borges', FACETS)
    assert plan.author_text == 'borges' and plan.exclude_terms == ['borges']
    assert not plan.title_text
    plan = parse_query('books by Terry Pratchett about witches', FACETS)
    assert plan.author_text == 'terry pratchett' and plan.semantic_text == 'witches'

@pytest.mark.parametrize('query', ['books called 1984', 'books titled "Rating Below 3"'])
def test_explicit_title_owns_numeric_literal(query):
    plan = parse_query(query, FACETS)
    assert executable(plan) and plan.title_text and (plan.rating_max is None) and (plan.year_min is None)

def test_prefix_instead_replaces_only_topic():
    previous = parse_query('Neural Networks rated at least 2', FACETS)
    replacement, continued = refine(previous, 'instead History', FACETS)
    assert continued and replacement.subjects == ['History'] and (replacement.rating_min == 2)

def test_unrepresentable_format_or_is_not_executed():
    assert parse_query('online Mystery or physical Romance', FACETS).decision['decision_type'] == 'UNSUPPORTED'
