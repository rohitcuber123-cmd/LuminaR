"""Opt-in QA timing only; no raw history, profile vocabulary or user IDs logged."""
import json
import os
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from threading import Lock
assert os.getenv('SEARCH_GLOBAL_READ_ONLY') == '1'
from search import api, query_execution
from backend.database.mongodb import db
assert db.name == 'luminar_library'
app = api.app
TAG = ContextVar('v2b_review',default=False)
LOCK = Lock()
OUTPUT = Path(__file__).resolve().parents[1]/'.local/search_v2b_events.jsonl'

@app.middleware('http')
async def tag(request,call_next):
    token = TAG.set(request.headers.get('X-Luminar-V2B-QA') == 'bounded-search-review')
    try:
        response = await call_next(request)
        response.headers['Cache-Control'] = 'private, no-store'
        return response
    finally:
        TAG.reset(token)

def traced(function,scope):
    @wraps(function)
    def run(*args,**kwargs):
        if not TAG.get():
            return function(*args,**kwargs)
        kwargs['diagnostics'] = True
        response = function(*args,**kwargs)
        diagnostic = response.pop('diagnostics')
        record = {'scope':scope,'session':bool(kwargs.get('session_id')),
                  'personalized':bool(kwargs.get('personalized')),'profile':diagnostic.get('profile'),
                  'personalization':diagnostic.get('personalization'),
                  'provider':diagnostic.get('provider'),'hnsw_used':diagnostic.get('hnsw_used'),
                  'kg_used':diagnostic.get('kg_used'),'reranker_used':diagnostic.get('reranker_used'),
                  'timing_ms':response['timing_ms']}
        with LOCK:
            with OUTPUT.open('a',encoding='utf8') as output:
                output.write(json.dumps(record)+'\n')
        return response
    return run

api.human_search.search = traced(api.human_search.search,'GLOBAL')
query_execution.tenant_search = traced(query_execution.tenant_search,'LIBRARY')
