import hashlib
import pytest
from knowledge_graph.core import CatalogueGraph, canonical, connect
from knowledge_graph.topics import phrases, choose_topics, description_hash, STOP
from knowledge_graph.relations import TOPIC_POLICY
from scripts.build_catalogue_graph import build
from scripts.build_kg_topics import enrich


DESCRIPTION='Personal finance and budget planning help with financial decisions. This book is a guide for the reader and includes an introduction to the subject for new readers.'


@pytest.fixture
def topic_graph(tmp_path):
    rows=[dict(work_id=f'OL{i}W',title=f'Book {i}',authors='Alice' if i<4 else None,
               subjects='Finance' if i<4 else None,description=DESCRIPTION if i<4 else None) for i in range(1,11)]
    v1=tmp_path/'v1.sqlite';v2=tmp_path/'v2.sqlite';build(rows,v1,len(rows))
    old_hash=hashlib.sha256(v1.read_bytes()).hexdigest()
    summary=enrich(v1,v2,lambda:iter(rows))
    assert old_hash==hashlib.sha256(v1.read_bytes()).hexdigest()
    return CatalogueGraph(v2),rows,summary


def test_topic_extraction_deterministic():
    candidate=phrases(DESCRIPTION)
    assert 'personal finance' in candidate and phrases(DESCRIPTION)==candidate
    degrees={phrase:3 for phrase in candidate}
    assert choose_topics(DESCRIPTION,degrees,100)==choose_topics(DESCRIPTION,degrees,100)


def test_topic_stopwords():
    assert all(not set(phrase.split())&STOP for phrase in phrases(DESCRIPTION))
    assert not phrases('Personal finance. Too short.')


def test_topic_limit_and_degree(topic_graph):
    graph,rows,summary=topic_graph
    with connect(graph.path) as db:
        assert db.execute("SELECT MAX(n) FROM (SELECT COUNT(*) n FROM edges WHERE kind='topic' GROUP BY book_id)").fetchone()[0]<=TOPIC_POLICY['max_topics_per_book']
        assert all(3<=row['degree']<=3 for row in db.execute("SELECT degree FROM features WHERE kind='topic'"))
    assert summary['features']['topic']>0


def test_topic_source_traceability_and_relation_contribution_sum(topic_graph):
    graph,rows,summary=topic_graph
    response=graph.more_like_this('OL1W')
    for book in response['recommendations']:
        assert sum(path['contribution'] for path in book['reason_paths'])==pytest.approx(book['score'])
        for path in book['reason_paths']:
            if path['kind']=='topic':
                assert path['predicates']==['HAS_TOPIC','HAS_TOPIC'] and path['label'] in canonical(DESCRIPTION)
                assert all(p['field']=='description' and p['description_sha256']==description_hash(DESCRIPTION) for p in path['provenance'])


def test_weak_relation_cannot_qualify_alone(tmp_path):
    rows=[dict(work_id=f'OL{i}W',title=f'Book {i}',language='English',publisher='Same publisher',publication_year=2000) for i in [1,2]]
    path=tmp_path/'weak.sqlite';build(rows,path,2)
    assert CatalogueGraph(path).more_like_this('OL1W')['recommendations']==[]


def test_generic_entity_downweighted_by_corpus_degree():
    candidates=phrases(DESCRIPTION)
    degrees={phrase:100 for phrase in candidates}
    assert choose_topics(DESCRIPTION,degrees,100)==[]


def test_topic_hash_freshness_guard(topic_graph):
    from backend.routes.knowledge_graph import features_current
    graph,rows,summary=topic_graph
    snapshot=graph.book('OL1W')
    assert features_current(snapshot,rows[0])
    assert not features_current(snapshot,{**rows[0],'description':DESCRIPTION+' changed'})
