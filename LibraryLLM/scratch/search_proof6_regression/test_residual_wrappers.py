import pytest
from scratch.search_proof_recovery_v6.parser import parse_query
@pytest.mark.parametrize('q,formats',[
    ('digital format',['ONLINE']),('in both physical and online formats',['BOTH']),
    ('physical version',['PHYSICAL']),('online format only',['ONLINE'])])
def test_format_wrapper_is_not_a_semantic_topic(q,formats):
    p=parse_query(q,[]);assert p.formats==formats and not p.semantic_text
@pytest.mark.parametrize('advice',['beginner explanations','advanced treatments'])
def test_advisory_intent_does_not_inject_a_topic(advice):
    p=parse_query('titled "An Amber Notebook"; prefer '+advice,[])
    assert p.title_text=='an amber notebook' and not p.semantic_text
