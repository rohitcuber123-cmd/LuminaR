import pytest
from .parser import parse_query,executable,matches
@pytest.mark.parametrize('name',['Aster Vale','After Vale','Below Moss','Least Reed'])
def test_unquoted_author_operand_is_not_a_grammar_cue(name):
    p=parse_query('books by '+name,[])
    assert p.author_text==name.casefold() and executable(p)
    assert matches(p,{'title':'A Fixture','authors':[name]}) and not p.decision.get('repair_notices')
def test_cue_repair_before_entity_still_works():
    p=parse_query('books byy Alder Vale; rated gretaer than 3 stars',[])
    assert p.author_text=='alder vale' and p.rating_min==3 and p.rating_min_exclusive and p.decision['repair_notices']
