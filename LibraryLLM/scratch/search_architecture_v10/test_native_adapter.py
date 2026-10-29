from dataclasses import replace
from uuid import uuid4
from copy import deepcopy
import pytest
from pydantic import ValidationError
from fastapi import HTTPException
from .parser import parse_query,executable,PARSER_VERSION
from .contract import digest
from .completion import BoundContext
from .native_adapter import ChoiceRequest500,issue_choice,resolve_choice,transformer
from .refinement import refine

FACETS=['Fiction','History','Physics']
def fixture(query='category Fiction; by [not supplied]',operation='complete',field='author'):
    p=parse_query(query,FACETS);c=BoundContext('owner','login',str(uuid4()),'STAFF',PARSER_VERSION,'SMART',digest(p.raw_query),7,1000)
    i=issue_choice(p,c,operation,field)
    r=ChoiceRequest500(clarification_id=i.clarification_id,choice_id=i.choice_id,query=p.raw_query,library_id=c.library_id,staff=True,value='Élodie Ångström' if operation=='complete' else None)
    return p,c,i,r
def resolve(p,c,i,r):return resolve_choice(r,i,p,c,now=10,facets=FACETS,capabilities={},authorized=True)

def test_native_callback_completes_unicode_and_preserves_fields():
    p,c,i,r=fixture('category Fiction; rating at least 4; by [not supplied]')
    row={'issued_choice':i,'query':p.raw_query,'mode':'SMART'};choice={'choice_id':i.choice_id,'operation':'complete'}
    n=transformer(row,choice,r.value,current=c,now=10,authorized=True)(p,FACETS,{})
    assert executable(n) and n.author_text=='élodie ångström' and n.rating_min==4 and n.subjects==['Fiction']
    assert '[not supplied]' not in n.raw_query and n.decision['source_edit_provenance']['full_reparse']

@pytest.mark.parametrize('operation',['correction_apply','correction_keep'])
def test_native_callback_correction_operations(operation):
    p,c,i,r=fixture('category Fictoin; by "Oak Vale"; rating at least 4',operation,None)
    n=transformer({'issued_choice':i,'query':p.raw_query,'mode':'SMART'},{'choice_id':i.choice_id,'operation':operation},None,current=c,now=10,authorized=True)(p,FACETS,{})
    assert executable(n) and n.author_text=='oak vale' and n.rating_min==4 and not n.corrections
    assert n.subjects==(['Fiction'] if operation=='correction_apply' else [])

@pytest.mark.parametrize('length',[149,150,151,499,500])
def test_long_wire_preserves_exact_query(length):
    q='by [not supplied]';q+=' '*(length-len(q));p,c,i,r=fixture(q)
    r=r.model_copy(update={'value':'Éve'})
    r=ChoiceRequest500.model_validate_json(r.model_dump_json())
    n=resolve(p,c,i,r)
    assert len(r.query)==length and r.query==q and n['query'].endswith(' '*(length-len('by [not supplied]')))
    assert not n['commit_performed']

def test_result_over_parser_bound_is_rejected_without_truncation():
    q='by [not supplied]';q+=' '*(500-len(q));p,c,i,r=fixture(q)
    with pytest.raises(HTTPException) as e:resolve(p,c,i,r)
    assert e.value.status_code==422 and len(p.raw_query)==500

@pytest.mark.parametrize('change',[{'owner':'foreign'},{'login_session':'other'},{'library_id':str(uuid4())},{'workspace':'PATRON'},
    {'base_version':8},{'parser_version':'old'},{'used':True},{'mode':'EXACT'},{'query_digest':'wrong'}])
def test_bound_context_rejects_foreign_stale_or_replayed(change):
    p,c,i,r=fixture()
    with pytest.raises(HTTPException):resolve(p,replace(c,**change),i,r)

@pytest.mark.parametrize('value',['','Oak"; exclude online','Oak\nVale','x'*101])
def test_invalid_completion_never_becomes_query_syntax(value):
    p,c,i,r=fixture()
    with pytest.raises((HTTPException,ValidationError)):
        resolve(p,c,i,ChoiceRequest500(**{**r.model_dump(),'value':value}))

def test_expiry_auth_changed_original_and_client_offsets_reject():
    p,c,i,r=fixture()
    for now,auth,code in [(1000,True,410),(10,False,401)]:
        with pytest.raises(HTTPException) as e:resolve_choice(r,i,p,c,now=now,facets=FACETS,capabilities={},authorized=auth)
        assert e.value.status_code==code
    with pytest.raises(HTTPException):resolve(p,c,i,r.model_copy(update={'query':r.query+' '}))
    with pytest.raises(ValidationError):ChoiceRequest500(**{**r.model_dump(),'source_span':[0,2]})
    with pytest.raises(ValidationError):ChoiceRequest500(**{**r.model_dump(),'query':'x'*501})

def test_preview_does_not_claim_durability_and_consumed_state_rejects():
    p,c,i,r=fixture();a=resolve(p,c,i,r);b=resolve(p,c,i,r)
    assert a['query']==b['query'] and not a['commit_performed']
    with pytest.raises(HTTPException):resolve(p,replace(c,used=True),i,r)

def test_unsupported_result_and_changed_plan_cannot_execute():
    p,c,i,r=fixture('require edition 2; by [not supplied]')
    with pytest.raises(HTTPException):resolve(p,c,i,r)
    p,c,i,r=fixture();p.rating_min=4
    with pytest.raises(HTTPException):resolve(p,c,i,r)

def test_accepted_source_recompilation_keeps_prior_requirements_and_independent_topic_reset():
    p=parse_query('by "Oak Vale"; books about optics; rating at least 4',FACETS)
    n,continued=refine(p,'online only',FACETS)
    assert continued and n.author_text=='oak vale' and n.rating_min==4 and n.semantic_text=='optics'
    assert n.raw_query!= 'online only' and n.decision['accepted_source_refinement']['full_reparse']
    m,continued=refine(n,'show me physics instead',FACETS)
    assert continued and m.author_text is None and m.rating_min==4 and m.formats==['ONLINE'] and m.subjects==['Physics']
