"""Production handler test with isolated catalogue/model; no live auth or writes."""
import importlib.util
from pathlib import Path
import sqlite3
import sys
import types
from unittest.mock import Mock

import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from search.lexical_store import LexicalSearchStore, search_with_lexical_diagnostics


@pytest.fixture
def isolated_search(monkeypatch):
    import search.luminar_search as lm
    rows={'A':{'work_id':'A','title':'Current title','authors':'Author',
               'description':'Current Mongo description','total_copies':1,'available_copies':1}}
    class Books:
        def find(self,query,projection=None):
            return [dict(rows[wid]) for wid in query['work_id']['$in'] if wid in rows]
    snapshot=types.SimpleNamespace(base=types.SimpleNamespace(ntotal=2),delta=types.SimpleNamespace(ntotal=0),
        candidates=lambda vector,count:[{'work_id':'A','hnsw_score':.9},{'work_id':'deleted','hnsw_score':.8}])
    engine=lm.LuminaRSearchEngine.__new__(lm.LuminaRSearchEngine)
    engine.device='cpu'
    engine.index_manager=types.SimpleNamespace(snapshot=snapshot,encode=lambda texts:np.ones((1,8),dtype=np.float32),
        status=lambda:{'index_status':'STALE','active_vectors':2},start=lambda:None)
    engine.books_collection=Books()
    engine.library_inventory=Books()
    engine.reranker=types.SimpleNamespace(predict=lambda pairs,**kw:np.ones(len(pairs)))
    monkeypatch.setattr(lm,'LuminaRSearchEngine',lambda:engine)
    # Isolated test doubles avoid loading any production auth/database service.
    jwt=types.ModuleType('backend.utils.jwt_utils')
    jwt.decode_access_token=lambda token: {'sub':'1'} if token=='isolated-test' else None
    history=types.ModuleType('backend.services.search_history_service')
    history.create_search_history=lambda **kw: (_ for _ in ()).throw(AssertionError('History write'))
    history.get_user_search_history=lambda *a,**kw: []
    monkeypatch.setitem(sys.modules,jwt.__name__,jwt)
    monkeypatch.setitem(sys.modules,history.__name__,history)
    path=Path(__file__).resolve().parents[1]/'search/api.py'
    spec=importlib.util.spec_from_file_location('isolated_search_api',path)
    api=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    return api, TestClient(api.app, raise_server_exceptions=False), engine, rows


def test_search_route_works_with_failed_lexical_and_keeps_public_schema(tmp_path, isolated_search):
    _, client, engine, rows = isolated_search
    health=client.get('/health').json()
    assert 'lexical' in health and not health['lexical']['lexical_available']
    assert client.post('/search',json={'query':'test','save_history':False}).status_code==401
    for state in ('missing','corrupt','stale'):
        root=tmp_path/state
        if state=='corrupt':
            root.mkdir()
            (root/'active_lexical.json').write_text('not json')
        if state=='stale':
            from search.lexical_build import build_snapshot
            build_snapshot([{'work_id':'A','title':'Old title'}],root,source_db='test')
        lexical=LexicalSearchStore(root,required_generation=999 if state=='stale' else None)
        diagnostic=search_with_lexical_diagnostics(engine,lexical,'test')
        assert not diagnostic['lexical_diagnostics']['health']['lexical_available']
        response=client.post('/search',headers={'Authorization':'Bearer isolated-test'},
            json={'query':'test','save_history':False,'diagnostics':True})
        assert response.status_code==200
        data=response.json()
        assert 'diagnostics' not in data and 'lexical_diagnostics' not in data
        assert [r['work_id'] for r in data['results']]==['A']
        assert data['results'][0]['description']=='Current Mongo description'
        rows['A']['title']='New Mongo title'
        assert client.post('/search',headers={'Authorization':'Bearer isolated-test'},
            json={'query':'test','save_history':False}).json()['results'][0]['title']=='New Mongo title'


@pytest.mark.parametrize('mode,author,failed_lookup', [
    ('EXACT', '', 'exact'),
    ('TITLE_AUTHOR', '', 'exact'),
    ('TITLE_AUTHOR', '', 'fuzzy'),
    ('SMART', 'Author', 'exact'),
])
def test_structured_provider_error_keeps_canonical_constraints(isolated_search, monkeypatch, mode, author, failed_lookup):
    _, client, engine, _ = isolated_search
    class Cursor(list):
        def sort(self, *_): return self
        def limit(self, _): return self
        def max_time_ms(self, _): return self

    books = Mock(spec=['find'])
    books.find.return_value = Cursor([
        {'work_id': 'A', 'title': 'Current title', 'authors': 'Author'},
        {'work_id': 'B', 'title': 'Other book', 'authors': 'Someone Else'},
    ])
    engine.books_collection = books
    lexical = Mock()
    lexical.exact.return_value = []
    getattr(lexical, failed_lookup).side_effect = sqlite3.OperationalError('sidecar unavailable')
    engine.lexical_store = lexical
    engine.search = Mock(side_effect=AssertionError('Structured fallback must not use semantic ranking'))
    capabilities = types.ModuleType('backend.services.book_capability_service')
    capabilities.with_capabilities = lambda rows: rows
    monkeypatch.setitem(sys.modules, capabilities.__name__, capabilities)
    response = client.post('/search', headers={'Authorization':'Bearer isolated-test'}, json={
        'query': '' if author else 'Current title', 'mode': mode, 'author': author, 'save_history': False})
    assert response.status_code == 200
    assert [row['work_id'] for row in response.json()['results']] == ['A']
    assert '$and' in books.find.call_args.args[0]
    engine.search.assert_not_called()


def test_structured_provider_authorization_error_does_not_fallback(isolated_search):
    _, client, engine, _ = isolated_search
    engine.books_collection = Mock(spec=['find'])
    engine.lexical_store = types.SimpleNamespace(exact=Mock(side_effect=HTTPException(403, 'Denied')))
    response = client.post('/search', headers={'Authorization':'Bearer isolated-test'},
        json={'query':'Current title','mode':'EXACT','save_history':False})
    assert response.status_code == 403
    engine.books_collection.find.assert_not_called()


@pytest.mark.parametrize('contract,overrides', [
    ('MACHINE', {'library_id':'94fc6761-a5b8-4cff-b2d0-29f4768a28ac'}),
    ('MACHINE', {'library_id':'LIB001','available_at_library':True}),
    ('HUMAN', {'library_id':'94fc6761-a5b8-4cff-b2d0-29f4768a28ac'}),
    ('MACHINE', {'rating_min':0}),
    ('MACHINE', {'format':'ONLINE'}),
])
def test_global_route_rejects_unsupported_scope_or_constraint_before_dispatch(isolated_search, contract, overrides):
    api, client, _, _ = isolated_search
    api.ranked_search.search = Mock(return_value={'results':[]})
    api.human_search.search = Mock(return_value={'results':[]})
    response = client.post('/search', headers={'Authorization':'Bearer isolated-test'},
        json={'query':'topic','query_contract':contract,'save_history':False,**overrides})
    assert response.status_code == 422
    api.ranked_search.search.assert_not_called()
    api.human_search.search.assert_not_called()


def test_global_route_preserves_human_placeholder_and_unscoped_machine(isolated_search):
    api, client, _, _ = isolated_search
    api.human_search.search = Mock(return_value={'results':[]})
    api.ranked_search.search = Mock(return_value={'results':[]})
    for payload in ({'library_id':'LIB001','available_at_library':True},
                    {'query_contract':'MACHINE','category':'History','author':'Example'}):
        response = client.post('/search', headers={'Authorization':'Bearer isolated-test'},
            json={'query':'topic','save_history':False,**payload})
        assert response.status_code == 200
    api.human_search.search.assert_called_once()
    api.ranked_search.search.assert_called_once_with(
        query='topic', limit=10, offset=0, library_id=None, available_at_library=False,
        category='History', author='Example')
