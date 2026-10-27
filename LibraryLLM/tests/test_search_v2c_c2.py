"""Source-independent safety examples and execution counterexamples."""
import pytest
from search.query_plan import parse_query, matches
from search.query_confidence import validate, executable

FACETS=['Fiction','Romance','History']

@pytest.mark.parametrize('phrase,field,exclusive',[
    ('above 4','rating_min',True),('greater than 4','rating_min',True),
    ('more than 4 stars','rating_min',True),('over 4 stars','rating_min',True),
    ('at least 4','rating_min',False),('4 or higher','rating_min',False),
    ('4+','rating_min',False),('below 4','rating_max',True),
    ('less than 4','rating_max',True),('under 4 stars','rating_max',True),
    ('at most 4','rating_max',False),('4 or lower','rating_max',False),
    ('no more than 4','rating_max',False),('no less than 4','rating_min',False),
    ('minimum rating 4','rating_min',False),('maximum rating 4','rating_max',False),
])
def test_operator_and_equal_boundary(phrase,field,exclusive):
    query=phrase if 'rating' in phrase or phrase.startswith('4') else 'rating '+phrase
    p=parse_query(query)
    assert getattr(p,field)==4 and getattr(p,field+'_exclusive')==exclusive
    assert matches(p,{'title':'At boundary','rating':4,'rating_count':1}) is not exclusive

@pytest.mark.parametrize('query',[
    'rating at least 4.5 but below 4.5',
    'rating no more than 1 and no less than 4',
    'rating above 4 and at most 4',
    'rating above 4 and below 4',
    'published after 2020 and before 2020',
    'include Fiction but exclude Fiction',
    'online only and physical only',
])
def test_mathematical_conflicts(query):
    p=parse_query(query,FACETS)
    assert p.decision['decision_type']=='CONTRADICTORY' and not executable(p)
    assert not matches(p,{'subjects':FACETS,'rating':4.5,'rating_count':1})

def test_equal_inclusive_is_possible():
    p=parse_query('rating no less than 4 and no more than 4')
    assert executable(p) and matches(p,{'rating':4,'rating_count':1})

def test_author_topic_boundary():
    p=parse_query('fiction by Octavia Butler',FACETS)
    assert p.subjects==['Fiction'] and p.author_text=='octavia butler' and not p.title_text
    p=parse_query('books written by Octavia Butler about distant planets',FACETS)
    assert p.author_text=='octavia butler' and p.semantic_text=='distant planets'

def test_canonical_exclusion_is_not_broad_text_exclusion():
    p=parse_query('exclude Romance',FACETS)
    assert p.exclude_subjects==['Romance'] and not p.exclude_terms
    assert matches(p,{'title':'Romance in the archives','subjects':['History']})
    assert not matches(p,{'title':'An archive','subjects':['Romance']})

def test_topical_not_is_preserved():
    p=parse_query('books about not giving up',FACETS)
    assert not p.exclude_terms and p.semantic_text=='not giving up'

@pytest.mark.parametrize('query',['rating above','published after','books by','written by','exclude','include','under pages','books titled','rating between 3 and'])
def test_incomplete_blocks_with_request_framing(query):
    for text in [query,'Please find '+query+' ??']:
        assert parse_query(text,FACETS).decision['decision_type']=='INCOMPLETE'

@pytest.mark.parametrize('entity',['1984','Catch-22','Python 3','C++','C#','Windows 11','Dune 2','The Three-Body Problem','9780141036144'])
def test_protected_literal_survives(entity):
    p=parse_query('Please find "'+entity+'"',FACETS)
    assert entity.casefold() in (p.semantic_text or p.title_text or p.exact_text or '').casefold()
    assert p.rating_min is None and p.year_min is None

def test_scope_physical_unsupported():
    p=validate(parse_query('physical only books about radio'),{'formats':['ONLINE']})
    assert not executable(p) and p.decision['affected_fields']==['format']
