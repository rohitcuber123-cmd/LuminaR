from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_knowledge_graph import graph, BOOKS


@pytest.fixture
def product(graph, monkeypatch):
    from backend.routes import knowledge_graph as routes
    from backend.services import availability_service
    live = {book['work_id']: dict(book, book_id=i+1, average_rating=4.5, rating_count=7,
                                shelf_location='LIVE-A', total_copies=3, available_copies=2)
            for i, book in enumerate(BOOKS) if book.get('active', True)}
    monkeypatch.setattr(routes, 'graph', graph)
    monkeypatch.setattr(routes, 'current_books', lambda collection, ids: {wid: live[wid] for wid in ids if wid in live})
    monkeypatch.setattr(routes, 'exclusions', lambda user: set())
    monkeypatch.setattr(availability_service, 'library_inventory_collection', SimpleNamespace(find_one=lambda query: {'available_copies':0,'total_copies':9} if query['work_id']=='OL2W' else None))
    app = FastAPI(); app.include_router(routes.product_router)
    app.dependency_overrides[routes.identity] = lambda: {'sub':'1'}
    return TestClient(app), routes, live


def get(product, seed='OL1W'):
    return product[0].get(f'/kg/books/{seed}/more-like-this?limit=10')


def test_more_like_this_book_detail_endpoint(product):
    response = get(product)
    assert response.status_code == 200
    body = response.json()
    assert body['seed_work_id']=='OL1W' and body['graph_version'].startswith('kg1-2')
    assert body['has_more'] is False and len(body['recommendations'])==3


def test_more_like_this_seed_excluded(product):
    assert 'OL1W' not in [book['work_id'] for book in get(product).json()['recommendations']]


def test_more_like_this_no_qwen(product, monkeypatch):
    from assistant.qwen import QwenGateway
    parse = AsyncMock(side_effect=AssertionError('Qwen forbidden'))
    respond = AsyncMock(side_effect=AssertionError('Qwen forbidden'))
    monkeypatch.setattr(QwenGateway, 'parse', parse); monkeypatch.setattr(QwenGateway, 'respond', respond)
    assert get(product).status_code == 200
    parse.assert_not_awaited(); respond.assert_not_awaited()


def test_more_like_this_not_existing_recommender(product, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError('Existing recommender forbidden')
    monkeypatch.setattr(product[1].requests,'post',forbidden)
    assert get(product).status_code == 200


def test_more_like_this_rehydrates_live_metadata(product):
    product[2]['OL2W'].update(title='Fresh catalogue title', average_rating=3.7, rating_count=42, shelf_location='UPDATED')
    book=next(book for book in get(product).json()['recommendations'] if book['work_id']=='OL2W')
    assert (book['title'],book['average_rating'],book['rating_count'],book['shelf_location'])==('Fresh catalogue title',3.7,42,'UPDATED')


def test_more_like_this_rehydrates_availability(product):
    book=next(book for book in get(product).json()['recommendations'] if book['work_id']=='OL2W')
    assert book['available_copies']==0 and book['total_copies']==9 and book['availability_source']=='physical'


def test_more_like_this_reason_paths_valid(product):
    for book in get(product).json()['recommendations']:
        assert sum(path['contribution'] for path in book['reason_paths'])==pytest.approx(book['score'])
        for path in book['reason_paths']:
            assert path['relation_weight']==pytest.approx(2 if path['kind']=='author' else 1)
            assert path['feature_weight']==pytest.approx(path['relation_weight']*path['importance'])
        assert all(path['nodes'][0]=='OL1W' and path['nodes'][2]==book['work_id'] for path in book['reason_paths'])


def test_more_like_this_sparse_empty(product):
    assert get(product,'OL5W').json()['recommendations']==[]


def test_more_like_this_stale_graph_friendly_error(product):
    product[2]['OL1W']['subjects']='Changed'
    response=get(product)
    assert response.status_code==409 and response.json()['detail']=='Related-book data for this title is being refreshed.'


def test_more_like_this_deterministic_order(product):
    assert get(product).json()['recommendations']==get(product).json()['recommendations']


def test_product_invalid_identity_limit_and_changed_candidate(product):
    client,routes,live=product
    assert client.get('/kg/books/OL1W/more-like-this?limit=51').status_code==422
    live['OL2W']['subjects']='Changed'
    assert 'OL2W' not in [b['work_id'] for b in get(product).json()['recommendations']]
    client.app.dependency_overrides.clear()
    assert get(product).status_code in {401,403}
