"""Development properties; not independent acceptance or learned labels."""
from itertools import permutations
from dataclasses import replace
from copy import deepcopy
import pytest
from .parser import parse_query,executable,PARSER_VERSION,_decode,validate
from .source_roles import Modality,Role
from .proof import validate_ir
from .contract import digest,State
from .completion import BoundContext
from .recompilation import issue_completion,issue_correction,issue_remove,recompile

FACETS=['Fiction','Physics','History']

@pytest.mark.parametrize('fragments',list(permutations(['by "Oak Vale"','rating at least 4','preferably online'])))
def test_role_composition_under_reordering(fragments):
    p=parse_query('; '.join(fragments),FACETS)
    assert executable(p) and p.author_text=='oak vale' and p.rating_min==4 and p.formats==[]
    rr=_decode(p.decision['query_ir_contract']).requirements
    assert any(r.modality==Modality.SHOULD and r.source_role==Role.PREFERENCE for r in rr)

@pytest.mark.parametrize('modal',['preferably','prefer','should be','may be'])
@pytest.mark.parametrize('field',['online','physical','language [not supplied]','rated above [not supplied]'])
def test_advisory_never_becomes_hard(modal,field):
    p=parse_query('by "Oak Vale", '+modal+' '+field,FACETS)
    assert executable(p) and p.author_text=='oak vale' and not p.formats and p.language is None and p.rating_min is None

def test_nested_mandatory_advisory_boundary():
    p=parse_query('Find books about physics, preferably online, but rating at least 4 is mandatory',FACETS)
    assert executable(p) and p.rating_min==4 and not p.formats and 'physics' in p.semantic_text

@pytest.mark.parametrize('clause',['I cannot remember which author wrote another book','For example, suppose I wanted online books','Explain the meaning of the author field'])
def test_background_cannot_invent_or_block_explicit_search(clause):
    p=parse_query(clause+'; by "Oak Vale"; rating at least 4',FACETS)
    assert executable(p) and p.author_text=='oak vale' and not p.formats

def test_hypothetical_does_not_execute_catalogue_search():
    p=parse_query('If I wanted online books, what would that mean?',FACETS)
    assert not executable(p) and not p.formats

def test_explicit_missing_author_has_operand_role():
    p=parse_query('Find books by author [author not supplied]',FACETS)
    assert p.decision['decision_type']=='INCOMPLETE' and not executable(p)

def test_quoted_filter_words_owned_by_literal_title():
    p=parse_query('Find a title containing the words "available online"',FACETS)
    assert executable(p) and p.title_text=='available online' and not p.formats and not p.availability

def test_proof_rejects_forged_role_even_when_projection_unchanged():
    p=parse_query('by "Oak Vale"',FACETS);ir=_decode(p.decision['query_ir_contract'])
    r=ir.requirements[0]
    forged=replace(ir,requirements=(replace(r,modality=Modality.MAY),))
    assert not validate_ir(forged,p).valid

def context(p):return BoundContext('owner','login','library','STAFF',PARSER_VERSION,'SMART',digest(p.raw_query),7,1000)
def apply(p,edit):
    c=context(p)
    return recompile(edit,p,c,c,now=10,facets=FACETS,capabilities={},authorized=True)

@pytest.mark.parametrize('operation',['correction_apply','correction_keep'])
def test_corrections_recompile_full_source(operation):
    p=parse_query('category Fictoin; by "Oak Vale"; rating at least 4',FACETS)
    d=apply(p,issue_correction(p,operation,7));n=d['plan']
    assert executable(n) and n.author_text=='oak vale' and n.rating_min==4 and not n.corrections
    assert n.subjects==(['Fiction'] if operation=='correction_apply' else [])
    assert d['query']==n.raw_query and n.decision['source_edit_provenance']['full_reparse']

def test_field_removal_recompiles_other_requirements():
    p=parse_query('by "Oak Vale"; rating at least 4',FACETS)
    d=apply(p,issue_remove(p,'rating',7))
    assert executable(d['plan']) and d['plan'].rating_min is None and d['plan'].author_text=='oak vale'

@pytest.mark.parametrize('field,operand',[('by','Oak Vale'),('titled','Field Manual'),('language','English'),('rating at least','4'),('published after','2020'),('sort by','TITLE')])
def test_span_completion_with_unrelated_mandatory_condition(field,operand):
    p=parse_query('category Fiction; '+field+' [not supplied]',FACETS)
    r=next(r for r in _decode(p.decision['query_ir_contract']).requirements if r.state==State.PLACEHOLDER)
    d=apply(p,issue_completion(p,r.requirement_id,operand,7))
    assert executable(d['plan']) and d['plan'].subjects==['Fiction'] and '[not supplied]' not in d['query']

def test_plan_mutation_cannot_become_edit_authority():
    p=parse_query('category Fiction; by [not supplied]',FACETS)
    r=next(r for r in _decode(p.decision['query_ir_contract']).requirements if r.state==State.PLACEHOLDER)
    edit=issue_completion(p,r.requirement_id,'Oak',7);p.rating_min=4
    with pytest.raises(ValueError):apply(p,edit)

def test_forged_expected_query_is_rejected():
    p=parse_query('category Fiction; by [not supplied]',FACETS)
    r=next(r for r in _decode(p.decision['query_ir_contract']).requirements if r.state==State.PLACEHOLDER)
    edit=issue_completion(p,r.requirement_id,'Oak',7)
    with pytest.raises(ValueError):apply(p,replace(edit,expected_query='books'))

@pytest.mark.parametrize('field',['rating above','rating at least','published after','publication year before'])
@pytest.mark.parametrize('value',['banana','tomorrow','not-a-number'])
def test_invalid_numeric_operands_cannot_be_downgraded_to_topic(field,value):
    p=parse_query('category Fiction; '+field+' '+value,FACETS)
    assert not executable(p) and p.decision['decision_type']=='INCOMPLETE'

def test_soft_retrieval_projection_is_also_proved():
    p=parse_query('books about quantum optics; by "Oak Vale"',FACETS)
    p.semantic_text='unrelated topic'
    assert not executable(validate(p))

def test_existing_parser_bound_without_truncation_for_completion():
    q='by [not supplied]';q=q+' '*(500-len(q))
    p=parse_query(q,FACETS)
    r=next(r for r in _decode(p.decision['query_ir_contract']).requirements if r.state==State.PLACEHOLDER)
    d=apply(p,issue_completion(p,r.requirement_id,'Oak',7))
    assert len(p.raw_query)==500 and d['query'].endswith(' '*(500-len('by [not supplied]')))
    assert d['plan'].author_text=='oak'
    with pytest.raises(ValueError):parse_query(q+' ',FACETS)
