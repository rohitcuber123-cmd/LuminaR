"""Development assertions from documented semantics, not candidate output snapshots."""
import pytest
from scratch.search_proof_recovery_v8.parser import parse_query,matches
from scratch.search_proof_recovery_v8.parser import executable,validate
from scratch.search_v2c_c5er.candidate_search_v4.query_calibration import assess

FACETS=['Ecology','Astronomy','Mystery','History','Physics','Fiction','Romance']

def test_owned_literals_and_independent_topic():
    p=parse_query('include subject "Ecology"; exclude category "Astronomy"; titled "A Cedar Atlas"; about wetland fieldwork',FACETS)
    assert executable(p) and p.subjects==['Ecology'] and p.exclude_subjects==['Astronomy']
    assert p.title_text=='a cedar atlas' and p.semantic_text=='wetland fieldwork'
    assert not p.exclude_terms

def test_supported_borrow_and_only_modifier():
    p=parse_query('physical format only; available to borrow now; published exactly in 2018',FACETS)
    assert executable(p) and p.exclusive_formats==['PHYSICAL'] and p.availability=='AVAILABLE_NOW'
    assert p.year_min==p.year_max==2018

@pytest.mark.parametrize('query',[
 'rated at leat 3.5 stars; include subject "Ecology"',
 'rated gretaer than 3 stars',
 'books byy Alder Vale; titled "A Reed Atlas"',
 'books titeld "A Reed Atlas"; online only',
 'onlien only; rated at least 3 stars'])
def test_bounded_repairs_are_visible_and_executable(query):
    p=parse_query(query,FACETS)
    assert p.decision['decision_type']=='EXECUTABLE_WITH_NOTICE' and executable(p)
    assert assess(p)['policy']=='EXECUTE_WITH_NOTICE'
    assert any(c.get('repair_provenance') for c in p.constraint_candidates)
    assert all(query[c['source_span_start']:c['source_span_end']]==c['source_text'] for c in p.constraint_candidates)

def test_repaired_lower_bound_never_invents_upper_bound():
    p=parse_query('rated at leat 3.5 stars',FACETS)
    assert p.rating_min==3.5 and p.rating_max is None

@pytest.mark.parametrize('query',[
 'books by ...; titled "A Reed Atlas"; online only',
 'rated between ... and 4 stars; by Alder Vale',
 'titled "A ..."; by Alder Vale',
 'language ...; online only'])
def test_mandatory_missing_value_requests_clarification(query):
    p=parse_query(query,FACETS);assert p.decision['decision_type']=='INCOMPLETE' and not executable(p)

def test_unresolved_author_association_is_not_a_literal_author():
    p=parse_query('My note lists two authors; by the author paired with the requested title; titled "A Cedar Atlas"',FACETS)
    assert p.decision['decision_type']=='AMBIGUOUS' and not executable(p)

def test_optional_anecdote_is_not_a_mandatory_author():
    p=parse_query('I cannot remember which author wrote another book; by Alder Vale; titled "A Cedar Atlas"',FACETS)
    assert executable(p)

def test_meaningful_uncertainty_differs_from_optional_uncertainty():
    p=parse_query('my rating note is 3 stars; I cannot tell whether it means an exact rating or a minimum',FACETS)
    assert p.decision['decision_type']=='AMBIGUOUS'
    assert executable(parse_query('books about uncertainty in ecological forecasting',FACETS))

@pytest.mark.parametrize('query',[
 'require edition 2; include subject "Ecology"',
 'require a price ceiling of 10 dollars',
 'require a machine-verified difficulty level',
 'delete a catalogue record'])
def test_unsupported_requests_are_not_reinterpreted_as_search(query):
    p=parse_query(query,FACETS);assert p.decision['decision_type']=='UNSUPPORTED' and not executable(p)

@pytest.mark.parametrize('query',[
 'include subject "Ecology"; exclude category "Ecology"',
 'titled "A Cedar Atlas"; exclude every record containing the exact text "Cedar"',
 'rated at least 4 stars and rated at most 3 stars',
 'language French; language English'])
def test_both_sides_of_conflicts_survive(query):
    p=parse_query(query,FACETS);assert p.decision['decision_type']=='CONTRADICTORY' and not executable(p)

def test_whole_word_exclusion_counterexample_remains_valid():
    p=parse_query('books by Marsh; exclude every record containing the word "ar"',FACETS)
    assert executable(p) and matches(p,{'authors':['Marsh'],'subjects':[]})

def test_exact_mode_preserves_raw_text_without_smart_repairs():
    raw='rated at leat 3 stars; exclude category "Ecology"'
    p=parse_query(raw,FACETS,'EXACT')
    assert p.exact_text==raw and p.rating_min is None and not p.exclude_subjects and executable(p)

def test_quoted_title_interior_is_not_a_filter():
    p=parse_query('titled "Rated above 3 and Return a Book"',FACETS)
    assert executable(p) and p.rating_min is None and p.title_text=='rated above 3 and return a book'

def test_scope_capability_is_still_enforced():
    p=validate(parse_query('published exactly in 2018',FACETS),{'year':False,'formats':['ONLINE']})
    assert p.decision['decision_type']=='UNSUPPORTED' and not executable(p)

def test_explicit_filter_and_omit_controls_keep_ownership():
    p=parse_query('books by Alder Vale',FACETS,filters={'author':'Birch Vale'})
    assert executable(p) and p.author_text=='Birch Vale'
    p=parse_query('include subject "Ecology"',FACETS,omit=['subject'])
    assert executable(p) and not p.subjects

def test_semantic_missing_word_is_not_missing_operand():
    assert executable(parse_query('Find books about missing title pages',FACETS))

def test_introductory_material_reuses_existing_advisory_intent():
    p=parse_query('Introductory physics material',FACETS)
    assert executable(p) and p.intent=='LEARN' and p.soft_preference and 'physics' in p.semantic_text

def test_unresolved_author_alternatives_do_not_become_a_proven_conflict():
    p=parse_query('by Alder Vale and Birch Vale, excluding Alder Vale; I cannot tell whether these are joint or alternative authors',FACETS)
    assert p.decision['decision_type']=='AMBIGUOUS' and not executable(p)
