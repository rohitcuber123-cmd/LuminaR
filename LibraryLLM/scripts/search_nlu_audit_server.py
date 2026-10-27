"""Opt-in loopback NLU trace; no endpoints or diagnostic fields added to product."""
import json
import os
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from threading import Lock

assert os.getenv('SEARCH_GLOBAL_READ_ONLY')=='1'
from search import api, query_execution
from backend.database.mongodb import db
assert db.name=='luminar_library'
app=api.app
TAG=ContextVar('nlu_review_tag',default=False)
LOCK=Lock()
OUTPUT=Path(__file__).resolve().parents[1]/'.local/search_nlu_diagnostics.jsonl'
ALLOWED={'fiction','science fiction','detectve','folktail','books about wizards',
 'books about wizards with rating above 4','fiction books about wizards rated at least 4',
 'books by Tolkien rated above 4','online books about robotics','history books published after 2015',
 'Tolkien','OL19545719W','books about networking','online books about networking','History'}

@app.middleware('http')
async def tag(request,call_next):
    token=TAG.set(request.headers.get('X-Luminar-NLU-QA')=='query-understanding-v1')
    try:return await call_next(request)
    finally:TAG.reset(token)

def traced(function,scope):
    @wraps(function)
    def run(*args,**kwargs):
        query=args[0] if scope=='GLOBAL' else args[3]
        if not TAG.get() or query not in ALLOWED:return function(*args,**kwargs)
        kwargs['diagnostics']=True
        response=function(*args,**kwargs)
        diagnostic=response.pop('diagnostics')
        record={'scope':scope,'query':query,'library_id':None if scope=='GLOBAL' else args[1],
                'diagnostics':diagnostic,'timing_ms':response['timing_ms'],
                'results':[{k:r.get(k) for k in ('work_id','library_book_id','subjects','average_rating','publication_year','has_online','has_physical')} for r in response['results']]}
        with LOCK:
            with OUTPUT.open('a',encoding='utf-8') as handle:handle.write(json.dumps(record,ensure_ascii=False)+'\n')
        return response
    return run

api.human_search.search=traced(api.human_search.search,'GLOBAL')
query_execution.tenant_search=traced(query_execution.tenant_search,'TENANT')
