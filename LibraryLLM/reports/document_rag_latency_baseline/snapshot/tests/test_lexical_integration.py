"""Production merge path with injected semantic candidates; no real HNSW."""
import types

import numpy as np

from search.lexical_build import build_snapshot
from search.lexical_delta import LexicalOverlayStore,initialize_delta
from search.lexical_integration import merge_lexical_candidates


class EmptyQueue:
    def latest(self): return 0


class Books:
    def __init__(self,docs): self.docs={doc['work_id']:dict(doc) for doc in docs}
    def find(self,query,projection=None):
        return [dict(self.docs[wid]) for wid in query['work_id']['$in'] if wid in self.docs]


def engine_with_semantic_stub(books,semantic_ids):
    from search.luminar_search import LuminaRSearchEngine
    engine=LuminaRSearchEngine.__new__(LuminaRSearchEngine)
    engine.device='cpu'
    snapshot=types.SimpleNamespace(
        base=types.SimpleNamespace(ntotal=len(semantic_ids)),
        delta=types.SimpleNamespace(ntotal=0),
        candidates=lambda vector,count:[{'work_id':wid,'hnsw_score':.9}
                                        for wid in semantic_ids])
    engine.index_manager=types.SimpleNamespace(
        snapshot=snapshot,encode=lambda texts:np.ones((1,8),dtype=np.float32))
    engine.books_collection=books
    engine.library_inventory=books
    engine.reranker=types.SimpleNamespace(
        predict=lambda pairs,**kw:np.array([.99 if 'Other' in pair[1] else .1
                                            for pair in pairs]))
    engine.lexical_store=None
    return engine


def test_flag_off_preserves_semantic_path_and_on_merges_exact_title(tmp_path,monkeypatch):
    docs=[{'work_id':'S','title':'Other','authors':['Someone'],'available_copies':1},
          {'work_id':'L','title':'Frankenstein','authors':['Mary Shelley'],
           'available_copies':1}]
    books=Books(docs)
    manifest=build_snapshot(docs,tmp_path,source_db='luminar_library')
    initialize_delta(tmp_path,manifest,0,EmptyQueue())
    store=LexicalOverlayStore(tmp_path)
    engine=engine_with_semantic_stub(books,['S'])
    engine.lexical_store=store
    try:
        monkeypatch.delenv('LEXICAL_SEARCH_ENABLED',raising=False)
        off=engine.search('Frankenstein',top_k=2)
        assert [item['work_id'] for item in off['results']]==['S']
        monkeypatch.setenv('LEXICAL_SEARCH_ENABLED','true')
        on=engine.search('Frankenstein',top_k=2)
        assert [item['work_id'] for item in on['results']]==['L','S']
        assert set(on['results'][0])==set(off['results'][0])
        assert 'lexical_evidence' not in on
        engine.index_manager.snapshot.candidates=lambda vector,count:[
            {'work_id':'L','hnsw_score':.9},{'work_id':'L','hnsw_score':.8},
            {'work_id':'S','hnsw_score':.7}]
        deduped=engine.search('Frankenstein',top_k=3)
        assert [item['work_id'] for item in deduped['results']]==['L','S']
    finally:
        store.close()


def test_author_signal_and_mongo_authority(tmp_path,monkeypatch):
    docs=[{'work_id':'S','title':'Other','authors':['Someone']},
          {'work_id':'L','title':'A Novel','authors':['Jane Austen']}]
    books=Books(docs)
    manifest=build_snapshot(docs,tmp_path,source_db='luminar_library')
    initialize_delta(tmp_path,manifest,0,EmptyQueue())
    store=LexicalOverlayStore(tmp_path)
    engine=engine_with_semantic_stub(books,['S'])
    engine.lexical_store=store
    monkeypatch.setenv('LEXICAL_SEARCH_ENABLED','true')
    try:
        result=engine.search('Jane Austen',top_k=2)
        assert [item['work_id'] for item in result['results']]==['L','S']
        books.docs['L']['authors']=['A Different Author']
        stale=engine.search('Jane Austen',top_k=2)
        assert [item['work_id'] for item in stale['results']]==['S']
        del books.docs['L']
        deleted=engine.search('Jane Austen',top_k=2)
        assert [item['work_id'] for item in deleted['results']]==['S']
    finally:
        store.close()


def test_lexical_failure_returns_semantic_results(tmp_path,monkeypatch):
    books=Books([{'work_id':'S','title':'Other','authors':['Someone']}])
    engine=engine_with_semantic_stub(books,['S'])
    monkeypatch.setenv('LEXICAL_SEARCH_ENABLED','true')
    for store in (None,
                  types.SimpleNamespace(health=lambda:{'lexical_available':False}),
                  types.SimpleNamespace(health=lambda:(_ for _ in ()).throw(OSError('unavailable')))):
        engine.lexical_store=store
        result=engine.search('Other')
        assert [item['work_id'] for item in result['results']]==['S']


def test_internal_evidence_keeps_all_signals_for_same_work(tmp_path):
    docs=[{'work_id':'L','title':'Frankenstein','authors':['Frankenstein']}]
    books=Books(docs)
    manifest=build_snapshot(docs,tmp_path,source_db='luminar_library')
    initialize_delta(tmp_path,manifest,0,EmptyQueue())
    store=LexicalOverlayStore(tmp_path)
    try:
        semantic=[{'work_id':'L','hnsw_score':.9}]
        merged,metadata,evidence=merge_lexical_candidates(
            store,'Frankenstein',semantic,books.docs,books,
            lambda collection,ids:{wid:collection.docs[wid] for wid in ids if wid in collection.docs})
        assert len(merged)==1
        assert evidence['L']=={'semantic','exact_title','exact_author'}
        assert metadata['L']['title']=='Frankenstein'
    finally:
        store.close()
