"""Opt-in loopback QA wrapper; normal API responses never include diagnostics."""
import json
import os
from contextvars import ContextVar
from functools import wraps
from pathlib import Path
from threading import Lock
assert os.getenv('SEARCH_GLOBAL_READ_ONLY')=='1'
from search import api,query_execution
from backend.database.mongodb import db
assert db.name=='luminar_library'
app=api.app
TAG=ContextVar('v2a_review',default=None);LOCK=Lock()
OUTPUT=Path(__file__).resolve().parents[1]/'.local/search_v2a_events.jsonl'
ALLOWED={'fiction','detectve','books about wizards','fiction books about wizards rated above 4',
 'fiction about detectives but not romance','online books about computer networks',
 'I want an easy introduction to computer networks','books about neural networks',
 'books about neural networks rated above 4','OL19545719W','History','books about networking',
 'books about machine learning','books about computer networks','books related to neural networks',
 'reference book for database normalization','research material about neural networks'}

@app.middleware('http')
async def tag(request,call_next):
    value=request.headers.get('X-Luminar-V2A-KG','on') if request.headers.get('X-Luminar-NLU-QA')=='query-understanding-v2a' else None
    token=TAG.set(value)
    try:return await call_next(request)
    finally:TAG.reset(token)

def traced(function,scope):
    @wraps(function)
    def run(*args,**kwargs):
        query=args[0] if scope=='GLOBAL' else args[3]
        if TAG.get() is None or query not in ALLOWED:return function(*args,**kwargs)
        kwargs.update(diagnostics=True,kg_enabled=TAG.get()!='off')
        response=function(*args,**kwargs);diagnostic=response.pop('diagnostics')
        record={'scope':scope,'query':query,'kg_enabled':TAG.get()!='off',
          'library_id':None if scope=='GLOBAL' else args[1],'diagnostics':diagnostic,
          'timing_ms':response['timing_ms'],'interpretation':response['interpretation'],
          'results':[{k:r.get(k) for k in ('title','work_id','library_book_id','subjects','average_rating','publication_year','has_online','has_physical')} for r in response['results']]}
        with LOCK:
            with OUTPUT.open('a',encoding='utf-8') as handle:handle.write(json.dumps(record,ensure_ascii=False)+'\n')
        return response
    return run
api.human_search.search=traced(api.human_search.search,'GLOBAL')
query_execution.tenant_search=traced(query_execution.tenant_search,'TENANT')
