import json
from dataclasses import replace
import pytest
from . import parser
from .ontology import DOMAINS,FAMILIES,NATIVE,target,scoring_fields
from .source_analysis import audit
from .contract import QueryIR
from .extraction import validate_proposal,compile_proposal

FACETS=['Fiction','History','Science']


@pytest.mark.parametrize('native,domain',list(NATIVE.items()))
def test_ontology_projection_roundtrip(native,domain):
    assert native in DOMAINS[domain].native
    if native.endswith('_exclusive') or native=='physical_available_only':
        with pytest.raises(ValueError):target(native)
    else:assert target(native).domain==domain


def test_numeric_direction_and_negative_domain_not_collapsed():
    assert target('rating_min').operators==('>','>=','=','RANGE')
    assert target('rating_max').operators==('<','<=','=','RANGE')
    assert scoring_fields('rating','>')==('rating_min',)
    assert scoring_fields('year','<=')==('year_max',)
    assert target('exclude_terms').domain=='exclude'
    assert target('exclude_subjects').domain=='excluded_subject'
    assert target('publisher').domain!='year'
    with pytest.raises(ValueError):target('tenant')


@pytest.mark.parametrize('domain',['publisher','price','imprint'])
@pytest.mark.parametrize('frame',['Books titled "Elm"; exclude records whose {} is "Delta"','Find online books; do not include books with {} "Delta"'])
def test_unsupported_negative_metadata_cannot_be_repaired_into_text(domain,frame):
    p=parser.parse_query(frame.format(domain),FACETS)
    assert not parser.executable(p) and not p.exclude_terms
    assert not any(n.get('from','').casefold()==domain for n in p.decision['repair_notices'])


@pytest.mark.parametrize('clauses',[
    ['Search for "Quiet Bay"','rated above 3.2','exclude the whole word "manual"'],
    ['rated above 3.2','exclude the whole word "manual"','Search for "Quiet Bay"'],
    ['exclude the whole word "manual"','Search for "Quiet Bay"','rated above 3.2'],
])
def test_literal_and_numeric_clause_order(clauses):
    p=parser.parse_query('; '.join(clauses),FACETS)
    assert parser.executable(p) and p.exact_text=='quiet bay' or parser.executable(p) and p.exact_text=='Quiet Bay'
    assert p.rating_min==3.2 and p.rating_min_exclusive and p.exclude_terms==['manual']
    assert parser.matches(p,{'title':'Quiet Bay','average_rating':4,'rating_count':1})
    assert not parser.matches(p,{'title':'About Quiet Bay','average_rating':4,'rating_count':1})


def test_coverage_detects_independent_removed_rating_obligation():
    p=parser.parse_query('Books must have rating above 4',FACETS)
    ir=parser._decode(p.decision['query_ir_contract'])
    omitted=replace(ir,requirements=tuple(r for r in ir.requirements if r.field!='rating'))
    assert any(v['domain']=='rating' for v in audit(omitted)['violations'])


def test_coverage_sort_argument_is_not_a_rating_floor():
    p=parser.parse_query('by "June Vale"; sort on highest rating',FACETS)
    assert parser.executable(p) and p.sort=='RATING' and p.rating_min is None


def test_advisory_numeric_content_does_not_create_hard_filter():
    p=parser.parse_query('by "June Vale"; publication year 2017 onward is optional',FACETS)
    assert parser.executable(p) and p.year_min is None


def proposal(query='by "June Vale"'):
    return {'query':query,'intent':'SEARCH','requirements':[{'start':0,'end':len(query),'source_text':query,'domain':'author','operator':'CONTAINS','operand':'june vale','role':'MANDATORY_SEARCH_CONDITION','modality':'MUST','polarity':'POSITIVE','state':'SUPPLIED'}]}


def test_schema_valid_proposal_is_still_proof_checked():
    x=proposal();r=compile_proposal(x['query'],json.dumps(x),FACETS)
    assert r['status']=='VALIDATED' and not r['retrieval_performed']
    x['requirements'][0]['operand']='unrelated'
    assert compile_proposal(x['query'],json.dumps(x),FACETS)['status']=='REJECTED'


@pytest.mark.parametrize('change',['tenant','wrong_span','changed_query','unknown_domain','wrong_operator','extra_requirement','infinite','too_many','too_long'])
def test_extractor_rejects_malformed_or_authority_bearing_output(change):
    x=proposal();q=x['query']
    if change=='tenant':x['tenant_id']='private-B'
    elif change=='wrong_span':x['requirements'][0]['end']-=1
    elif change=='changed_query':x['query']='another'
    elif change=='unknown_domain':x['requirements'][0]['domain']='mongo'
    elif change=='wrong_operator':x['requirements'][0]['operator']='$where'
    elif change=='extra_requirement':x['requirements'][0]['database_filter']={'$where':'js'}
    elif change=='infinite':x['requirements'][0]['operand']=float('inf')
    elif change=='too_many':x['requirements']*=33
    elif change=='too_long':x['query']=q='a'*501
    with pytest.raises(ValueError):validate_proposal(q,json.dumps(x))


def test_model_omitting_detected_mandatory_condition_cannot_execute():
    q='by "June Vale"; rating above 4';x=proposal(q)
    x['requirements'][0].update(end=14,source_text=q[:14])
    r=compile_proposal(q,json.dumps(x),FACETS)
    assert r['status']=='REJECTED' and r['reason']=='DETERMINISTIC_MANDATORY_OBLIGATION_OMITTED'


def test_duplicate_json_keys_rejected():
    with pytest.raises(ValueError):validate_proposal('', '{"query":"","query":"","intent":"SEARCH","requirements":[]}')
