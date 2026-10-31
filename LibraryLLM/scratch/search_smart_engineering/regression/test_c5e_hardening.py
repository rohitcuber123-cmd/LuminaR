"""Exposed C5D blockers and independently specified operand/provenance tests."""
import pytest
from scratch.search_smart_engineering.parser import parse_query
from scratch.search_smart_engineering.parser import executable

FACETS=['History','Physics','Detective Fiction','Fiction']
def test_unresolved_access_ownership():
    q='Find books my note says online, but I cannot remember whether that is mandatory access or merely a preference; by Jalen Dalmere; titled "A Paper Workshop"; rated at least 4 stars.'
    p=parse_query(q,FACETS)
    assert p.decision['decision_type']=='AMBIGUOUS' and not executable(p)
    assert any(r['field']=='format' and r['status']=='AMBIGUOUS' for r in p.decision['requirements'])
    assert not any(r['field']=='format' and r['status']=='RESOLVED' for r in p.decision['requirements'])

@pytest.mark.parametrize('q',[ 'online onyl', 'prefer beginer explanations', 'prefer advnaced treatments', 'prefer shrot works', 'prefer refrence works', 'exlcude every record containing the text "Cobalt"', 'include subject "History" adn subject "Physics"'])
def test_source_backed_notice(q):
    p=parse_query(q,FACETS)
    assert p.decision['decision_type']=='EXECUTABLE_WITH_NOTICE'
    assert p.public()['notice'] and p.decision['repair_notices']
    for r in p.decision['repair_notices']:
        a,b=r['source_span'];assert q[a:b]==r['from']
    for r in p.decision['requirements']:
        a,b=r['source_span'];assert q[a:b]==r['source_text']

@pytest.mark.parametrize('q,kind',[
    ('not category "History" or "Physics"; I lost the parentheses around the negative part','AMBIGUOUS'),
    ('include subject "History" and one more subject that I have not named','INCOMPLETE'),
    ('prefer online access; by Arden Vale','EXECUTABLE'),
    ('require online format; by Arden Vale','EXECUTABLE'),
    ('require at least 300 pages; by Arden Vale','UNSUPPORTED')])
def test_requirement_ownership(q,kind):
    p=parse_query(q,FACETS);assert p.decision['decision_type']==kind
    if q.startswith('prefer online'):
        assert p.formats==[] and any(r['status']=='ADVISORY' for r in p.decision['requirements'])

def test_literal_spelling_is_opaque_and_negative_is_material():
    p=parse_query('titled "A Shrot Guide"; exclude every record containing the text "online"; rated above 3',FACETS)
    assert p.title_text=='a shrot guide' and p.exclude_terms==['online'] and p.rating_min_exclusive
    assert not p.corrections

def test_scoped_canonical_repair_uses_existing_correction_schema():
    p=parse_query('include subject "Detectve Fiction"',FACETS)
    assert p.subjects==['Detective Fiction']
    assert {'from':'Detectve Fiction','to':'Detective Fiction','kind':'typo'} in p.corrections
    assert p.public()['notice']
