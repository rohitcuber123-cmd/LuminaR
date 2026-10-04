"""Production handler test with isolated catalogue/model; no live auth or writes."""
import importlib.util
from pathlib import Path
import sys
import types

import numpy as np
from fastapi.testclient import TestClient

from search.lexical_store import LexicalSearchStore, search_with_lexical_diagnostics


def test_search_route_works_with_failed_lexical_and_keeps_public_schema(tmp_path,monkeypatch):
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
    client=TestClient(api.app)  # No lifespan: do not start any worker.
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
