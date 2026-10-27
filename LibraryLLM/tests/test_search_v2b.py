"""Pure continuation and bounded post-CrossEncoder ranking contracts."""
from dataclasses import asdict
import json
import pytest
from search.query_plan import parse_query, matches
from search.query_session import refine, omit_fields
from search.personalization import profile_from_books, rerank, empty, MAX_BOOST

FACETS = ['Fiction','Romance','Science fiction','Deep learning','Artificial intelligence']

def chain(*queries):
    plan = None
    for query in queries:
        plan, _ = refine(plan,query,FACETS)
    return plan

def test_search_session_first_query_and_learning_sequence():
    plan = chain('I want books for learning artificial intelligence','only beginner friendly ones',
                 'online only','rated above 4','not deep learning')
    assert plan.semantic_text == 'artificial intelligence'
    assert plan.intent == 'LEARN' and plan.soft_preference
    assert plan.formats == ['ONLINE'] and plan.rating_min == 4 and plan.rating_min_exclusive
    assert plan.exclude_subjects == ['Deep learning']

@pytest.mark.parametrize('query,field,value',[
    ('only online','formats',['ONLINE']),('physical instead','formats',['PHYSICAL']),
    ('rating above 4','rating_min',4),('after 2020','year_min',2020),
    ('sort by rating','sort','RATING'),('show newer books','sort','NEWEST'),
    ('only ones available now','availability','AVAILABLE_NOW'),
    ('only highly rated','rating_min',4),('more advanced','intent','RESEARCH'),
])
def test_search_session_refinement(query,field,value):
    plan = chain('machine learning',query)
    assert plan.semantic_text == 'machine learning' and getattr(plan,field) == value

@pytest.mark.parametrize('query,field,value',[
    ('remove rating filter','rating_min',None),('show all ratings','rating_min',None),
    ('show all formats','formats',[]),('any year','year_min',None),
    ('include romance again','exclude_terms',[]),('sort by relevance','sort','RELEVANCE')
])
def test_search_session_remove_constraint(query,field,value):
    plan = chain('machine learning','online only','rating above 4','after 2020','not romance','sort by rating',query)
    assert getattr(plan,field) == value and plan.semantic_text == 'machine learning'

def test_search_session_new_topic_replaces_topic():
    plan = chain('machine learning','online only','rating above 4','ancient history')
    assert plan.semantic_text == 'ancient history' and not plan.formats and plan.rating_min is None
    plan = chain('machine learning','online only','rating above 4','show me operating systems instead')
    assert plan.semantic_text == 'operating systems' and plan.formats == ['ONLINE'] and plan.rating_min == 4

def test_search_session_clear_and_chip_removal():
    plan = chain('machine learning','online only','rating above 4')
    omit_fields(plan,['format'])
    plan, _ = refine(plan,'not romance',FACETS)
    assert not plan.formats and plan.rating_min == 4
    assert not chain('machine learning','something different').semantic_text

@pytest.mark.parametrize('mode',['EXACT','TITLE_AUTHOR','GENRE_SUBJECT'])
def test_explicit_modes_do_not_inherit_session(mode):
    old = chain('machine learning','online only')
    plan,continued = refine(old,'Fiction',FACETS,mode)
    assert not continued and not plan.formats and plan.mode == mode

def candidates(scores=(0.01,0.009,0.008,8.,-8.)):
    return [dict(work_id=str(i),title='Neural networks',subjects=['Systems' if i == 2 else 'Other'],
                 authors=['A'],rerank_score=score) for i,score in enumerate(scores)]

def test_personalization_on_can_rerank_close_candidates_and_is_bounded():
    rows = candidates()[:3]
    profile = profile_from_books([{'subjects':['Systems']}]*3)
    ranked,diag = rerank(rows,parse_query('books about neural networks'),profile,True)
    assert ranked[0]['work_id'] == '2' and diag['order_changed']
    assert diag['max_boost'] == MAX_BOOST and diag['max_shift'] == 2

def test_personalization_does_not_override_relevance_or_explicit_sort():
    rows = candidates((8.,-8.,-9.))
    profile = profile_from_books([{'subjects':['Systems']}]*10)
    ranked,_ = rerank(rows,parse_query('neural networks'),profile,True)
    assert ranked[0]['work_id'] == '0'
    plan = parse_query('neural networks',filters={'sort':'RATING'})
    ranked,_ = rerank(rows,plan,profile,True)
    assert [r['work_id'] for r in ranked] == ['0','1','2']
    saturated = candidates((8.,4.,3.))
    saturated[1]['subjects'] = ['Systems']
    ranked,_ = rerank(saturated,parse_query('neural networks'),profile,True)
    assert ranked[0]['work_id'] == '0'  # sigmoid saturation cannot collapse large CE gaps

def test_personalization_neutral_cold_start_and_off_exact_order():
    rows = candidates()[:3]
    for profile,enabled in [(empty(),True),(profile_from_books([{'subjects':['Systems']}]),False)]:
        ranked,_ = rerank(rows,parse_query('neural networks'),profile,enabled)
        assert [r['work_id'] for r in ranked] == [r['work_id'] for r in rows]
        assert not any('Reading List' in reason for r in ranked for reason in r['search_reasons'])

@pytest.mark.parametrize('query,bad',[
    ('fiction rating above 4',{'subjects':['Fiction'],'average_rating':3}),
    ('fiction',{'subjects':['Romance']}),('online books about neural networks',{'has_online':False}),
    ('books about neural networks but not romance',{'subjects':['Romance']})
])
def test_personalization_does_not_override_strict_filters(query,bad):
    plan = parse_query(query,FACETS)
    eligible = [r for r in [bad] if matches(plan,r)]
    ranked,_ = rerank(eligible,plan,profile_from_books([bad]),True)
    assert ranked == []

def test_reasons_truthful_bounded_and_no_internal_scores():
    rows = candidates()[:3]
    rows[2]['has_online'] = True
    ranked,_ = rerank(rows,parse_query('books about neural networks'),profile_from_books([{'subjects':['Systems']}]),True)
    assert 'Systems' in ranked[0]['search_reasons'][0]
    assert all(len(r['search_reasons']) <= 2 for r in ranked)
    assert not any(k in json.dumps(ranked) for k in ['rerank_score','hnsw_score','personalization_score','_search_relevance'])

def test_personalization_preserves_kg_primary_group_and_v2a_plan():
    plan = parse_query('books about neural networks')
    plan.kg_expansion_used = True
    rows = [{'title':'Neural networks','subjects':['Other'],'rerank_score':0.,'work_id':'A'},
            {'title':'Deep learning','subjects':['Systems'],'rerank_score':.001,'work_id':'B'}]
    before = asdict(plan)
    ranked,_ = rerank(rows,plan,profile_from_books([{'subjects':['Systems']}]*5),True)
    assert [r['work_id'] for r in ranked] == ['A','B'] and asdict(plan) == before

def test_existing_subject_index_shortcut_is_readonly_bounded(tmp_path):
    import sqlite3
    from search.structured_subjects import candidate_ids
    path=tmp_path/'catalogue.sqlite'
    with sqlite3.connect(path) as graph:
        graph.executescript("CREATE TABLE books(id INTEGER,work_id TEXT);CREATE TABLE edges(book_id INTEGER,kind TEXT,term TEXT);CREATE INDEX features ON edges(kind,term,book_id);")
        graph.executemany('INSERT INTO books VALUES(?,?)',[(1,'OL1W'),(2,'OL2W')])
        graph.executemany('INSERT INTO edges VALUES(?,?,?)',[(1,'subject','machine learning'),(2,'subject','machine learning')])
    before=path.read_bytes()
    assert candidate_ids('Machine learning',limit=1,path=path)==['OL1W']
    assert candidate_ids('Unknown subject',path=path) is None
    assert path.read_bytes()==before
