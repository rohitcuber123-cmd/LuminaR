"""Opt-in loopback QA runner. Wraps real calls; adds no application endpoint.

Only allowlisted catalogue queries are recorded. Never records auth, actors,
documents or arbitrary traffic. Run explicitly with SEARCH_GLOBAL_READ_ONLY=1.
The normal search.api launch does not import this module.
"""
import json
import os
import sys
import time
from contextvars import ContextVar
from pathlib import Path
from threading import Lock
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
assert os.environ.get('SEARCH_GLOBAL_READ_ONLY') == '1'
from backend.database.mongodb import db
assert db.name == 'luminar_library' and db.client.address[0] in ('localhost', '127.0.0.1', '::1')
from search import api
from search.index_manager import Snapshot
from backend.services import library_catalogue_experience as catalogue

OUTPUT = ROOT / os.environ.get('LUMINAR_SEARCH_QA_OUTPUT', '.scratch/search-runtime/events.jsonl')
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
ALLOWED = {'beginner computer networking', 'accessibility transportation',
           'community memories', 'equipment design workshop',
           'getting around when walking is difficult', 'wizard boarding school adventures',
           'Campus Network Practice Workbook'}
CURRENT = ContextVar('search_runtime_trace', default=None)
CORRELATION = ContextVar('recommendation_qa_correlation', default=None)
LOCK = Lock()

@api.app.middleware('http')
async def correlate(request, call_next):
    supplied=request.headers.get('X-Luminar-Recommendation-QA')
    try: supplied=str(__import__('uuid').UUID(supplied)) if supplied else None
    except ValueError: supplied=None
    token=CORRELATION.set(supplied)
    try:return await call_next(request)
    finally:CORRELATION.reset(token)

def stage(name, **data):
    trace = CURRENT.get()
    if trace is not None:
        trace['stages'].append({'name': name, **data})

def traced(function, provider):
    def call(*args, **kwargs):
        query = kwargs.get('query') if provider == 'GLOBAL' else args[2]
        if query not in ALLOWED or (os.environ.get('LUMINAR_SEARCH_QA_TAGGED_ONLY')=='1' and not CORRELATION.get()):
            return function(*args, **kwargs)
        trace = {'trace_id': str(uuid4()), 'provider_scope': provider, 'query': query,
                 'library_id': args[0] if provider == 'TENANT' else None, 'stages': [],
                 'recommendation_trace_id':CORRELATION.get()}
        token = CURRENT.set(trace)
        started = time.perf_counter()
        try:
            result = function(*args, **kwargs)
            trace['response_source'] = result.get('source', result.get('ranking'))
            trace['final_results'] = [{k: r.get(k) for k in
                ('library_book_id','library_id','work_id','title','subjects','source','rerank_score')}
                for r in result.get('results', [])]
            return result
        except Exception as error:
            trace['error_type'] = type(error).__name__
            raise
        finally:
            trace['elapsed_ms'] = round((time.perf_counter()-started)*1000, 3)
            CURRENT.reset(token)
            with LOCK:
                with OUTPUT.open('a', encoding='utf8') as handle:
                    handle.write(json.dumps(trace, default=str)+'\n')
    return call

tenant = api.app.state.tenant_intelligence
load = tenant.cache.load
class MeasuredIndex:
    def __init__(self, index, records): self.index, self.records = index, records
    def search(self, *args, **kwargs):
        started = time.perf_counter(); scores, labels = self.index.search(*args, **kwargs)
        stage('FAISS_SEARCH', index_type=type(self.index).__name__, ntotal=self.index.ntotal,
              elapsed_ms=(time.perf_counter()-started)*1000, vector_ids=labels[0].tolist(),
              candidates=[{'library_book_id':self.records[int(label)]['library_book_id'],
                           'title':self.records[int(label)]['title'], 'score':float(score)}
                          for label,score in zip(labels[0],scores[0]) if 0<=label<len(self.records)])
        return scores, labels
def measured_load(*args, **kwargs):
    manifest, records, index = load(*args, **kwargs)
    stage('ARTIFACT_SELECTED', library_id=manifest['library_id'], generation_id=manifest['generation_id'],
          model_version=manifest['model_version'], book_count=len(records))
    return manifest, records, MeasuredIndex(index, records)
tenant.cache.load = measured_load

predict = api.engine.reranker.predict
def measured_predict(pairs, *args, **kwargs):
    started = time.perf_counter(); scores = predict(pairs, *args, **kwargs)
    stage('CROSS_ENCODER', model='cross-encoder/ms-marco-MiniLM-L-6-v2',
          count=len(pairs), elapsed_ms=(time.perf_counter()-started)*1000,
          ranked=sorted([{'text':p[1], 'score':float(s)} for p,s in zip(pairs,scores)],
                        key=lambda r:-r['score']))
    return scores
api.engine.reranker.predict = measured_predict

candidates = Snapshot.candidates
def measured_candidates(self, *args, **kwargs):
    started=time.perf_counter(); result=candidates(self,*args,**kwargs)
    stage('GLOBAL_FAISS_SEARCH', generation=self.manifest, index_type=type(self.base).__name__,
          ntotal=self.base.ntotal, elapsed_ms=(time.perf_counter()-started)*1000, candidates=result)
    return result
Snapshot.candidates = measured_candidates

hydrate = catalogue.hydrate
def measured_hydrate(library_id, actor, rows, *args, **kwargs):
    result=hydrate(library_id,actor,rows,*args,**kwargs)
    stage('CANONICAL_TENANT_HYDRATION', library_id=library_id,
          input_ids=[r['library_book_id'] for r in rows], output_ids=[r['library_book_id'] for r in result])
    return result
catalogue.hydrate = measured_hydrate

import search.ranked_pages as pages
current_books = pages.current_books
def measured_current_books(*args, **kwargs):
    result=current_books(*args,**kwargs)
    stage('CANONICAL_GLOBAL_HYDRATION', input_count=len(args[1]), output_ids=list(result))
    return result
pages.current_books=measured_current_books
tenant.semantic = traced(tenant.semantic, 'TENANT')
api.ranked_search.search = traced(api.ranked_search.search, 'GLOBAL')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(api.app, host='127.0.0.1', port=8003)
