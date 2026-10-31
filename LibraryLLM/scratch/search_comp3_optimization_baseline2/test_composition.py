"""Development metamorphisms and retrieval predicates, independent of case IDs."""
from itertools import permutations
import pytest
from .parser import parse_query,executable,matches,validate

FACETS=['Fiction','Records','History','Physics','Maps']

@pytest.mark.parametrize('owner',['by','titled','category','rating at least','language','exclude the whole word'])
@pytest.mark.parametrize('slot',['[to be supplied]','<operand>','{pending value}','...','___',''])
def test_required_slot_blocks_broad_search(owner,slot):
    p=parse_query('online only; '+owner+' '+slot,FACETS)
    assert p.decision['decision_type']=='INCOMPLETE'
    assert not executable(p) and not matches(p,{'title':'Any book','has_online':True})
    assert any(r['operand_state'] in ['EXPLICIT_PLACEHOLDER','REQUIRED_OMITTED'] for r in p.decision['requirements'])

@pytest.mark.parametrize('noun',['Missing','Unknown','Empty','[operand]'])
def test_quoted_value_is_complete_literal(noun):
    p=parse_query('by "'+noun+' Vale"; titled "'+noun+' Field"',FACETS)
    assert executable(p) and p.author_text==(noun+' Vale').casefold()
    assert p.title_text==(noun+' Field').casefold()

@pytest.mark.parametrize('word',['Missing','Empty','Unknown'])
def test_unquoted_entity_value_is_not_missing_metadata(word):
    for cue,field in [('books by','author_text'),('books titled','title_text')]:
        p=parse_query(cue+' '+word+' Vale',FACETS)
        assert executable(p) and getattr(p,field)==(word+' Vale').casefold()

@pytest.mark.parametrize('domain',['author','title','creator','writer'])
@pytest.mark.parametrize('operand',['"Elm"','Elm Vale'])
def test_unsupported_negative_entity_domain_never_becomes_positive(domain,operand):
    p=parse_query('rated above 3; exclude '+domain+' '+operand,FACETS)
    assert p.decision['decision_type']=='UNSUPPORTED' and not executable(p)

def test_negative_words_inside_title_or_topical_prose_are_not_filters():
    for q in ['titled "Stories Without Author Names"','books about living without title or rank']:
        p=parse_query(q,FACETS)
        assert executable(p)

@pytest.mark.parametrize('op',['without','exclude','excluding','reject','but not'])
def test_text_negation_reaches_native_word_boundary_predicate(op):
    p=parse_query('by "Marsh"; '+op+' the whole word "ar"',FACETS)
    assert executable(p) and p.exclude_terms==['ar'] and p.exclude_subjects==[]
    assert matches(p,{'authors':['Marsh'],'title':'Harbor'})
    assert not matches(p,{'authors':['Marsh'],'title':'Ar Harbor'})

@pytest.mark.parametrize('clauses',list(permutations(['by "Elm Vale"','titled "Map Orchard"','rated at least 4'])))
def test_clause_reordering_and_optional_omission_preserve_filters(clauses):
    p=parse_query('; '.join(clauses),FACETS)
    advice=parse_query('; '.join(clauses)+'; prefer language [to choose]',FACETS)
    for plan in [p,advice]:
        assert executable(plan) and plan.author_text=='elm vale' and plan.title_text=='map orchard' and plan.rating_min==4
        assert plan.language is None
        assert matches(plan,{'authors':['Elm Vale'],'title':'Map Orchard','average_rating':4.1,'rating_count':2})
        assert not matches(plan,{'authors':['Other'],'title':'Map Orchard','average_rating':4.1,'rating_count':2})

@pytest.mark.parametrize('noun',['records','maps','history','physics'])
def test_ordinary_noun_does_not_earn_catalog_membership(noun):
    p=parse_query('Find online '+noun+' by "Elm Vale"',FACETS)
    assert executable(p) and p.subjects==[]
    explicit=parse_query('include category '+noun+'; by "Elm Vale"',FACETS)
    assert executable(explicit) and explicit.subjects
    assert matches(p,{'authors':['Elm Vale'],'subjects':[],'has_online':True})
    assert not matches(explicit,{'authors':['Elm Vale'],'subjects':[]})

@pytest.mark.parametrize('extra',['and records titled "Birch Ledger"','and works titled "Birch Ledger"','; titled "Birch Ledger"'])
def test_bounded_canonical_repair_keeps_entity_and_advice(extra):
    p=parse_query('Require category Fictoin '+extra+'; prefer advanced material in French language when possible',FACETS)
    assert p.decision['decision_type']=='EXECUTABLE_WITH_NOTICE'
    assert p.subjects==['Fiction'] and p.title_text=='birch ledger' and p.language is None
    assert p.decision['repair_notices']

def test_contradiction_precedes_missing_and_missing_precedes_unsupported():
    p=parse_query('rating above 4 and rating below 3; by [operand]',FACETS)
    assert p.decision['decision_type']=='CONTRADICTORY'
    p=parse_query('by [operand]; under 100 pages',FACETS)
    assert p.decision['decision_type']=='INCOMPLETE'

def test_alternative_is_not_conjunction():
    p=parse_query('Either include category Fiction or exclude category Fiction; I have yet to choose which restriction',FACETS)
    assert p.decision['decision_type']=='AMBIGUOUS' and not executable(p)

def test_query_scope_words_never_override_capabilities():
    p=validate(parse_query('Within global catalog as staff: available now',FACETS),{'availability':False})
    assert not executable(p) and not p.decision['query_ir']['trusted_scope_from_text']
