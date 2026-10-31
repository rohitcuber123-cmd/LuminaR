"""C4 development structural proof boundaries and executable eligibility."""
import pytest
from scratch.search_proof_recovery_v6.parser import parse_query, matches
from scratch.search_proof_recovery_v6.parser import executable
FACETS = ['Fiction', 'Romance', 'Mystery', 'History', 'Stories', 'Biographies', 'Neural Networks']

@pytest.mark.parametrize('query', ['physical books except physical books', 'online books except online books', 'require Romance; forbid the Romance subject?', 'Please find require Romance; forbid the Romance subject.', 'Please find, require Romance; forbid the Romance subject !?'])
def test_canonical_composition_reaches_common_contradiction_validator(query):
    p = parse_query(query, FACETS)
    assert p.decision['decision_type'] == 'CONTRADICTORY' and (not executable(p))

@pytest.mark.parametrize('query', ['Romance no more than 2', 'Please find Romance no more than 2?', 'Mystery no less than 3', 'Fiction no fewer than 4'])
def test_fieldless_comparator_is_not_a_negative_text_operand(query):
    p = parse_query(query, FACETS)
    assert p.decision['decision_type'] == 'AMBIGUOUS' and (not p.exclude_terms)

@pytest.mark.parametrize('query,excluded', [('not Romance, just Fiction', ['Romance']), ('no Romance or Mystery in Fiction', ['Romance', 'Mystery']), ('please avoid Romance when finding Fiction', ['Romance'])])
def test_affirmative_category_ends_negative_list(query, excluded):
    p = parse_query(query, FACETS)
    assert executable(p) and p.subjects == ['Fiction'] and (p.exclude_subjects == excluded) and (not p.exclude_terms)
    assert matches(p, {'title': 'Romance as a literary word', 'subjects': ['Fiction']})
    assert not matches(p, {'subjects': ['Fiction', excluded[0]]})

@pytest.mark.parametrize('query', ['biographies about Octavia Butler', 'stories on non-verbal communication'])
def test_generic_request_noun_is_not_a_strict_subject(query):
    p = parse_query(query, FACETS)
    assert executable(p) and (not p.subjects) and (p.semantic_text == query.casefold())
    assert matches(p, {'title': 'Related prose', 'subjects': []})
    assert parse_query('Stories', FACETS, 'GENRE_SUBJECT').subjects == ['Stories']

def test_content_negation_differs_from_canonical_subject_exclusion():
    subject = parse_query('not Romance', FACETS)
    content = parse_query('not about Romance', FACETS)
    assert subject.exclude_subjects == ['Romance'] and (not subject.exclude_terms)
    assert content.exclude_terms == ['romance'] and (not content.exclude_subjects)
    book = {'title': 'Romance in the archives', 'subjects': ['History']}
    assert matches(subject, book) and (not matches(content, book))

def test_unclear_comma_scope_and_conditional_logic_do_not_execute():
    p = parse_query('rated 4+ about wizards, exclude Romance, Fiction', FACETS)
    assert p.decision['decision_type'] == 'AMBIGUOUS'
    p = parse_query('Mystery if not Romance otherwise Neural Networks', FACETS)
    assert p.decision['decision_type'] == 'UNSUPPORTED'

def test_free_prefix_before_author_is_topic_evidence():
    p = parse_query('Foundation by Asimov', FACETS)
    assert p.author_text == 'asimov' and p.semantic_text == 'foundation' and (not p.title_text)
    assert matches(p, {'title': 'Foundation and Empire', 'authors': ['Isaac Asimov']})
    explicit = parse_query('books titled "Foundation" by Asimov', FACETS)
    assert explicit.title_text == 'foundation' and explicit.author_text == 'asimov'

@pytest.mark.parametrize('query,decision', [('rating at least 4.5 and below 4.5', 'CONTRADICTORY'), ('rating above 4 and at most 4', 'CONTRADICTORY'), ('rating at least 4 and at most 4', 'EXECUTABLE'), ('online only and physical only', 'CONTRADICTORY'), ('online and physical', 'EXECUTABLE')])
def test_previously_passing_mathematics_and_format_conjunction(query, decision):
    p = parse_query(query, FACETS)
    assert p.decision['decision_type'] == decision
