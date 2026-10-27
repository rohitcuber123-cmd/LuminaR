"""Pure deterministic V2A plans and read-only existing-graph projections."""
import json
import sqlite3
from dataclasses import asdict
import pytest
from search.query_plan import parse_query,matches,primary_match
from search.query_expansion import global_expansion,select_related,apply_expansion

FACETS=['Fiction','Science fiction','Romance','Folktales','Detective and mystery stories','Computer networks']

@pytest.mark.parametrize('query,intent,topic',[
 ('fiction','BROWSE_CATEGORY',None),('science fiction','BROWSE_CATEGORY',None),
 ('books about wizards','DISCOVER_TOPIC','wizards'),
 ('I want an easy introduction to computer networks','LEARN','computer networks'),
 ('reference book for database normalization','REFERENCE','database normalization'),
 ('research material about neural networks','RESEARCH','neural networks'),
 ('online books about operating systems','FIND_ONLINE','operating systems'),
 ('books available now about robotics','FIND_AVAILABLE','robotics'),
 ('books by Isaac Asimov','FIND_AUTHOR',None),('OL123W','FIND_EXACT',None),
 ('books related to neural networks','DISCOVER_RELATED','neural networks'),
])
def test_intents_deterministic(query,intent,topic):
    a=parse_query(query,FACETS);b=parse_query(query,FACETS)
    assert a.intent==intent and a.semantic_text==topic and asdict(a)==asdict(b)
    assert a.parser_version and a.normalized_query

@pytest.mark.parametrize('q,low,high,exclusive',[('at least 4 stars',4,None,False),('under 3 stars',None,3,True),('rated over 4',4,None,True),('4+ stars',4,None,False)])
def test_extended_rating_patterns(q,low,high,exclusive):
    p=parse_query(q);assert (p.rating_min,p.rating_max)==(low,high)
    assert (p.rating_min_exclusive if low is not None else p.rating_max_exclusive)==exclusive

def test_negative_subject_constraint():
    p=parse_query('fiction about detectives but not romance',FACETS)
    assert p.subjects==['Fiction'] and p.semantic_text=='detectives' and p.exclude_subjects==['Romance']
    assert not matches(p,{'subjects':['Fiction','Romance'],'title':'Detective story'})
    assert matches(p,{'subjects':['Fiction'],'title':'Detective story'})
    assert parse_query(p.raw_query,FACETS,omit=['exclude']).exclude_terms==[]

def test_unknown_negative_phrase_and_word_boundaries():
    p=parse_query('Java but not JavaScript')
    assert matches(p,{'title':'Java introduction'}) and not matches(p,{'title':'Javascript introduction'})
    p=parse_query('AI books excluding deep learning')
    assert p.semantic_text=='ai' and p.exclude_terms==['deep learning']
    assert not matches(p,{'description':'An introduction to deep learning.'})

def test_normalized_title_and_formats():
    assert parse_query('  SCI－FI  ',FACETS).subjects==['Science fiction']
    assert parse_query('hard copy books about robotics').formats==['PHYSICAL']
    assert parse_query('physical and online books').formats==['BOTH']
    assert parse_query('books by Tolkien but not romance',FACETS).author_text=='tolkien'

def test_preferences_are_not_strict_fields():
    p=parse_query('I want an easy introduction to computer networks',FACETS)
    assert p.ranking_query()=='introductory beginner guide to computer networks'
    assert not p.subjects and matches(p,{'title':'Networks','description':'No difficulty tag'})
    assert primary_match(p,{'title':'Computer networks handbook'})

def test_cache_keys_cover_plan_context_and_generations():
    p=parse_query('books about wizards but not romance',FACETS)
    assert p.cache_key(library_id='A',hnsw_generation='1')!=p.cache_key(library_id='B',hnsw_generation='1')
    assert p.cache_key(hnsw_generation='1')!=p.cache_key(hnsw_generation='2')
    key=p.cache_key();apply_expansion(p,{'concepts':['Magic'],'generation':'KG2'})
    assert p.cache_key()!=key and 'KG2' in p.cache_key()

class Cursor(list):
    def max_time_ms(self,value):return self
class Books:
    def __init__(self,rows):self.rows=rows
    def find(self,query,projection):return Cursor(r for r in self.rows if r['work_id'] in query['work_id']['$in'])

def fixture_graph(path):
    with sqlite3.connect(path) as g:
        g.executescript('CREATE TABLE meta(key TEXT,value TEXT);CREATE TABLE books(id INTEGER,work_id TEXT);CREATE TABLE edges(book_id INTEGER,kind TEXT,term TEXT,label TEXT);CREATE INDEX feature ON edges(kind,term,book_id);')
        g.execute('INSERT INTO meta VALUES(?,?)',('summary',json.dumps({'version':'fixture-accepted-schema','catalogue_hash':'one'})))
        g.executemany('INSERT INTO books VALUES(?,?)',[(1,'OL1W'),(2,'OL2W')])
        g.executemany('INSERT INTO edges VALUES(?,?,?,?)',[(1,'subject','neural networks','Neural networks'),(1,'subject','deep learning','Deep learning'),(2,'subject','deep learning','Deep learning'),(2,'subject','romance','Romance')])

def test_kg_bounded_existing_one_projected_hop(tmp_path):
    path=tmp_path/'graph.sqlite';fixture_graph(path)
    books=Books([{'work_id':'OL1W','subjects':'Neural networks | Deep learning'},{'work_id':'OL2W','subjects':'Deep learning | Romance'}])
    p=parse_query('books about neural networks')
    a=global_expansion(p,books,path);b=global_expansion(p,books,path)
    assert a['concepts']==b['concepts']==['Deep learning']
    assert 'Romance' not in a['concepts'] and a['projected_hops']==1
    assert a['generation']=='fixture-accepted-schema:one'
    assert len(select_related(p,[f'Subject {i}' for i in range(100)]))==6

def test_kg_current_canonical_metadata_authority(tmp_path):
    path=tmp_path/'graph.sqlite';fixture_graph(path)
    assert global_expansion(parse_query('books about neural networks'),Books([]),path)['concepts']==[]
    books=Books([{'work_id':'OL1W','subjects':['Neural networks']}])
    assert global_expansion(parse_query('books about neural networks'),books,path)['concepts']==[]

def test_kg_unavailable_and_negative_exclusion(tmp_path):
    p=parse_query('books about neural networks excluding deep learning')
    assert global_expansion(p,Books([]),tmp_path/'missing.sqlite')['concepts']==[]
    path=tmp_path/'graph.sqlite';fixture_graph(path)
    assert global_expansion(p,Books([{'work_id':'OL1W','subjects':'Neural networks | Deep learning'}]),path)['concepts']==[]
