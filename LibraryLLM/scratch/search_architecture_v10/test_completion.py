from dataclasses import replace
import pytest
from .parser import parse_query,PARSER_VERSION,_decode
from .completion import BoundContext,complete_draft
from .contract import State,digest

def fixture():
    q='category Fiction; rated at least 4; by [creator value omitted]'
    p=parse_query(q,['Fiction']);r=next(r for r in _decode(p.decision['query_ir_contract']).requirements if r.state==State.PLACEHOLDER)
    c=BoundContext('owner','login','library','STAFF',PARSER_VERSION,'SMART',digest(q),7,1000)
    return p,r,c

def test_source_span_completion_preserves_other_filters():
    p,r,c=fixture();draft=complete_draft(p,r.requirement_id,'Elm Vale',c,c,now=10,facets=['Fiction'],capabilities={},authorized=True)
    assert draft['plan'].author_text=='elm vale' and draft['plan'].rating_min==4 and draft['plan'].subjects==['Fiction']
    assert not draft['commit_performed'] and p.raw_query.endswith('[creator value omitted]')

@pytest.mark.parametrize('change',[{'owner':'foreign'},{'login_session':'foreign'},{'library_id':'foreign'},{'workspace':'PATRON'},
    {'parser_version':'old'},{'mode':'EXACT'},{'query_digest':'wrong'},{'base_version':8},{'expires_at':0},{'used':True}])
def test_context_binding_rejects_stale_or_foreign_completion(change):
    p,r,c=fixture()
    with pytest.raises(ValueError):complete_draft(p,r.requirement_id,'Elm',c,replace(c,**change),now=10,facets=['Fiction'],capabilities={},authorized=True)

def test_no_authorization_no_draft_and_injected_quote_rejected():
    p,r,c=fixture()
    with pytest.raises(ValueError):complete_draft(p,r.requirement_id,'Elm',c,c,now=10,facets=['Fiction'],capabilities={})
    with pytest.raises(ValueError):complete_draft(p,r.requirement_id,'Elm"; exclude online',c,c,now=10,facets=['Fiction'],capabilities={},authorized=True)
