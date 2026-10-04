import math
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from knowledge_graph.core import CatalogueGraph,canonical,connect,terms
from knowledge_graph.metrics import compare,diversity
from scripts.build_catalogue_graph import build

BOOKS=[
    dict(work_id='OL1W',title='Starting book',authors='Smith, Jane',subjects='Rare topic | Fiction | Rare Topic',private_note='must not enter graph'),
    dict(work_id='OL2W',title='Shared rare topic',authors='Other author',subjects='rare TOPIC | Fiction'),
    dict(work_id='OL3W',title='Same author',authors='  SMITH,   JANE ',subjects='Different topic'),
    dict(work_id='OL4W',title='Generic overlap',authors='Another',subjects='Fiction'),
    dict(work_id='OL5W',title='Isolated',authors=None,subjects=None),
    dict(work_id='OL6W',title='Disabled',authors='Smith, Jane',subjects='Rare topic',active=False),
]

@pytest.fixture
def graph(tmp_path):
    path=tmp_path/'graph.sqlite';build(BOOKS,path,len(BOOKS))
    return CatalogueGraph(path)

def test_full_graph_has_typed_deduplicated_edges_and_no_private_fields(graph):
    meta=graph.meta();assert meta['books']==5 and meta['isolated_books']==1 and meta['skipped_books']==1
    with connect(graph.path) as db:
        assert db.execute('SELECT COUNT(*) FROM edges WHERE book_id=1').fetchone()[0]==3
        assert 'private_note' not in str(db.execute('SELECT * FROM books').fetchall())
        with pytest.raises(Exception):db.execute("DELETE FROM books")

def test_normalization_preserves_comma_names_and_separates_feature_types():
    assert terms('Smith, Jane | Other author')=={'smith, jane':'Smith, Jane','other author':'Other author'}
    assert canonical('Ｃomputer  Science')=='computer science'

def test_more_like_this_paths_are_real_and_contributions_sum_to_score(graph):
    result=graph.more_like_this('OL1W')
    assert result['candidate_count']==3
    assert {r['work_id'] for r in result['recommendations']}=={'OL2W','OL3W','OL4W'}
    for item in result['recommendations']:
        assert math.isclose(sum(p['contribution'] for p in item['reason_paths']),item['score'])
        assert 0<item['score']<=1
        for path in item['reason_paths']:
            assert path['nodes'][0]=='OL1W' and path['nodes'][2]==item['work_id']
            field=path['provenance'][0]['field']
            assert canonical(path['label']) in terms(graph.book('OL1W')[field])
            assert canonical(path['label']) in terms(item[field])

def test_rarity_weighting_and_fair_exclusions(graph):
    with connect(graph.path) as db:
        weights={r['term']:r['weight'] for r in db.execute("SELECT * FROM features WHERE kind='subject'")}
    assert weights['rare topic']>weights['fiction']
    assert all(r['work_id']!='OL2W' for r in graph.more_like_this('OL1W',excluded={'OL2W'})['recommendations'])

def test_isolated_unknown_invalid_and_empty_graph(graph):
    assert graph.more_like_this('OL5W')['recommendations']==[]
    with pytest.raises(KeyError):graph.more_like_this('missing')
    with pytest.raises(ValueError):graph.more_like_this('OL1W',51)
    with pytest.raises(FileNotFoundError):CatalogueGraph(graph.path.with_name('missing.sqlite')).meta()

def test_exploration_keeps_only_returned_books_and_real_paths(graph):
    response=graph.more_like_this('OL1W',1);explore=graph.exploration(response)
    nodes={n['id'] for n in explore['nodes']}
    assert {n['id'] for n in explore['nodes'] if n['kind']=='book'}=={'OL1W',response['recommendations'][0]['work_id']}
    assert all(e['source'] in nodes and e['target'] in nodes for e in explore['edges'])

def test_metrics_handle_sparse_metadata_and_report_exact_sets():
    existing=[dict(work_id='A',subjects='Science',authors='Alice'),dict(work_id='B',subjects='Art',authors='Bob')]
    kg=[dict(work_id='B',subjects='Art',authors='Bob'),dict(work_id='C',subjects='Art',authors='Bob')]
    result=compare(existing,kg)
    assert result['overlap_at_k']==.5 and result['jaccard']==pytest.approx(1/3)
    assert result['kg_only_ids']==['C']
    assert result['existing_diversity']['subject_pairwise_distance']==1
    assert result['kg_diversity']['subject_pairwise_distance']==0
    assert diversity([{'work_id':'A'}])['subject_pairwise_distance'] is None

@pytest.fixture
def api(graph,monkeypatch):
    from backend.routes import knowledge_graph as routes
    monkeypatch.setattr(routes,'graph',graph)
    monkeypatch.setattr(routes,'current_books',lambda collection,ids:{b['work_id']:b for b in BOOKS if b['work_id'] in ids and b.get('active',True)})
    monkeypatch.setattr(routes,'exclusions',lambda user:{'OL4W'})
    app=FastAPI();app.include_router(routes.router)
    app.dependency_overrides[routes.identity]=lambda:{'sub':'1'}
    app.dependency_overrides[routes.security]=lambda:SimpleNamespace(credentials='fixture-token')
    return TestClient(app),routes

def test_authenticated_routes_validate_seed_and_preserve_reason_paths(api):
    client,routes=api
    response=client.post('/experimental/kg/more-like-this',json={'work_id':'OL1W','limit':2})
    assert response.status_code==200
    assert all(b['work_id']!='OL4W' for b in response.json()['recommendations'])
    assert client.post('/experimental/kg/more-like-this',json={'work_id':'../../secret'}).status_code==422
    assert client.post('/experimental/kg/more-like-this',json={'work_id':'OL1W','limit':51}).status_code==422
    assert client.post('/experimental/kg/more-like-this',json={'work_id':'OL1W','user_id':2}).status_code==422
    assert client.post('/experimental/kg/more-like-this',json={'work_id':'missing'}).status_code==404

def test_stale_seed_fails_closed(api,monkeypatch):
    client,routes=api
    monkeypatch.setattr(routes,'current_books',lambda collection,ids:{'OL1W':dict(BOOKS[0],subjects='Changed')})
    assert client.post('/experimental/kg/more-like-this',json={'work_id':'OL1W'}).status_code==409

def test_no_baseline_comparison_is_fabricated_on_dependency_failure(api,monkeypatch):
    client,routes=api
    import requests
    def unavailable(*args,**kwargs):raise requests.ConnectionError('fixture')
    monkeypatch.setattr(routes.requests,'post',unavailable)
    assert client.post('/experimental/kg/compare',json={'work_id':'OL1W'}).status_code==503

def test_experiment_requires_identity_and_rejects_revoked_identity(graph,monkeypatch):
    from backend.routes import knowledge_graph as routes
    app=FastAPI();app.include_router(routes.router);client=TestClient(app)
    assert client.get('/experimental/kg/meta').status_code in {401,403}
    app.dependency_overrides[routes.get_current_user]=lambda:{'sub':'1'}
    monkeypatch.setattr(routes,'current_identity',lambda user:None)
    assert client.get('/experimental/kg/meta').status_code==401

def test_build_refuses_overwrite(graph):
    with pytest.raises(FileExistsError):build(BOOKS,graph.path,len(BOOKS))
