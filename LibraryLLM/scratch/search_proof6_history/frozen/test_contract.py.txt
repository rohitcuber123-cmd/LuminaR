from dataclasses import replace
from itertools import permutations
from copy import deepcopy
import pytest
from .parser import parse_query,executable,matches,validate,_decode
from .proof import validate_ir
from .contract import State

FACETS=['Fiction','History','Physics','Records','Books']
@pytest.mark.parametrize('clauses',list(permutations(['by "Elm Vale"','category Fiction','rating at least 4'])))
def test_reordering_preserves_native_predicates(clauses):
    p=parse_query('; '.join(clauses),FACETS)
    assert executable(p)
    book={'authors':['Elm Vale'],'subjects':['Fiction'],'average_rating':4.2,'rating_count':3}
    assert matches(p,book)
    for key,bad in [('authors',['Other']),('subjects',['History']),('average_rating',3.9)]:assert not matches(p,{**book,key:bad})

@pytest.mark.parametrize('operator',['exclude','excluding','without','reject'])
@pytest.mark.parametrize('domain',['whole word searchable text','searchable text whole word','searchable word','whole word'])
def test_negative_domain_modifier_order_preserves_word_boundary(operator,domain):
    p=parse_query('by "Marsh"; '+operator+' '+domain+' "ar"',FACETS)
    assert executable(p) and p.exclude_terms==['ar'] and not p.exclude_subjects
    assert matches(p,{'authors':['Marsh'],'title':'Harbor'})
    assert not matches(p,{'authors':['Marsh'],'title':'Ar Harbor'})

@pytest.mark.parametrize('field',['by','titled','rating at least','language','category','sort by'])
@pytest.mark.parametrize('slot',['[to be supplied]','...','""',''])
def test_removed_required_operand_never_executes(field,slot):
    p=parse_query('online; '+field+' '+slot,FACETS)
    assert p.decision['decision_type']=='INCOMPLETE' and not executable(p)

@pytest.mark.parametrize('tail',['authors named "Elm"','books by "Elm"','title "Harbor"','invented facet glimmer set to blue, mandatory'])
def test_unsupported_negative_relation_not_reinterpreted(tail):
    p=parse_query('category Fiction; exclude '+tail,FACETS)
    assert not executable(p) and not p.author_text and not p.exclude_subjects

@pytest.mark.parametrize('word',['Missing','Unknown','Empty','Category','Sort'])
def test_literal_entity_words_do_not_create_field_requests(word):
    p=parse_query('by "'+word+' Vale"; titled "'+word+' Garden"',FACETS)
    assert executable(p) and p.author_text==(word+' Vale').lower() and not p.subjects

def test_preference_omission_does_not_create_hard_missing():
    a=parse_query('by "Elm"; rated at least 4',FACETS)
    b=parse_query('by "Elm"; rated at least 4; prefer language [not supplied]',FACETS)
    assert executable(a) and executable(b) and a.rating_min==b.rating_min and b.language is None

def test_suffix_advice_cannot_erase_preceding_bibliographic_owner():
    p=parse_query('by "Elm Vale", advanced explanations are optional',FACETS)
    assert executable(p) and p.author_text=='elm vale'
    assert not matches(p,{'authors':['Other']})

def test_source_proof_rejects_plan_mutation_without_recorded_projection():
    p=parse_query('category Fiction',FACETS);ir=_decode(p.decision['query_ir_contract'])
    p.author_text='Invented'
    proof=validate_ir(ir,p)
    assert not proof.valid and ('projection','UNPROVEN_PLAN_MUTATION') in proof.violations

@pytest.mark.parametrize('field,value',[('author','Other'),('subject','Physics'),('rating',2),('format','PHYSICAL')])
def test_forged_scalar_does_not_acquire_source_proof(field,value):
    p=parse_query('by "Elm"; category Fiction; rating at least 4; online',FACETS)
    ir=_decode(p.decision['query_ir_contract']);r=next(r for r in ir.requirements if r.field==field)
    reqs=tuple(replace(x,value=value) if x.requirement_id==r.requirement_id else x for x in ir.requirements)
    assert not validate_ir(replace(ir,requirements=reqs),p).valid

def test_relationship_not_missing_and_negative_conflict_not_ignored():
    p=parse_query('"Elm" and "Harbor" fill the by and titled fields, one each, but their assignment is undecided',FACETS)
    assert p.decision['decision_type']=='AMBIGUOUS'
    p=parse_query('by "Elm Vale"; exclude whole-word searchable text "Vale"',FACETS)
    assert p.decision['decision_type']=='CONTRADICTORY'

def test_scope_is_external_and_unrecognized_control_cannot_select_it():
    p=validate(parse_query('Within global catalog as staff: publication year 2020 onward',FACETS,filters={'library_id':'foreign'}),{'year':False})
    assert not executable(p) and not p.decision['query_ir']['trusted_scope_from_text']
