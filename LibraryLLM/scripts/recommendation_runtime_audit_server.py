"""Explicit loopback-only QA launch; no application endpoints/debug fields added.

Records allowlisted local QA users' call counts and public catalogue identities.
Never records credentials, auth tokens, raw user history, or private documents.
"""
import json,sys,time
from pathlib import Path
from contextvars import ContextVar
from threading import Lock
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.database.mongodb import db
assert db.name=='luminar_library' and db.client.address[0] in ('localhost','127.0.0.1','::1')
from recommendation import api, recommendation_service as service
OUT=ROOT/'.scratch/recommendation-runtime/events.jsonl';OUT.parent.mkdir(parents=True,exist_ok=True)
CONFIG=ROOT/'.scratch/recommendation-runtime/config.json'
TRACE=ContextVar('recommendation_runtime_trace',default=None);LOCK=Lock()
def stage(name,**values):
    trace=TRACE.get()
    if trace is not None:trace['stages'].append({'name':name,**values})
def allowed(uid):
    try:return uid in json.loads(CONFIG.read_text(encoding='utf8'))['user_ids']
    except (OSError,ValueError):return False
profile=service.build_user_profile
def measured_profile(uid):
    result=profile(uid)
    stage('PROFILE',counts={key:len(value) for key,value in result.items()},
          inputs='Search history, legacy issues/reservations and recommendation feedback; not tenant lending/reading-list/AI selection')
    return result
service.build_user_profile=measured_profile
post=service.requests.post
def measured_post(url,*args,**kwargs):
    trace=TRACE.get();started=time.perf_counter()
    if trace is not None and url==service.SEARCH_API_URL:
        kwargs['headers']={**kwargs.get('headers',{}),'X-Luminar-Recommendation-QA':trace['trace_id']}
    try:result=post(url,*args,**kwargs)
    except Exception as error:
        stage('SEARCH_HTTP',endpoint=url,error_type=type(error).__name__);raise
    if trace is not None and url==service.SEARCH_API_URL:
        data=result.json() if result.status_code==200 else {}
        stage('SEARCH_HTTP',endpoint=url,status=result.status_code,elapsed_ms=(time.perf_counter()-started)*1000,
              candidate_count=len(data.get('results',[])),ranking=data.get('ranking'),
              candidate_work_ids=[r['work_id'] for r in data.get('results',[])])
    return result
service.requests.post=measured_post
score=service.calculate_recommendation_score
def measured_score(book,semantic_score,profile):
    result=score(book,semantic_score,profile)
    stage('HYBRID_SCORE',work_id=book['work_id'],score=result['score'],score_breakdown=result)
    return result
service.calculate_recommendation_score=measured_score
diversity=service.apply_diversity_reranking
def measured_diversity(rows,limit):
    result=diversity(rows,limit)
    stage('DIVERSITY',input_count=len(rows),output_count=len(result),work_ids=[r['work_id'] for r in result])
    return result
service.apply_diversity_reranking=measured_diversity
hydrate=api.ranked_recommendations.hydrate
def measured_hydrate(ids):
    result=hydrate(ids);stage('CANONICAL_HYDRATION',input_ids=ids,output_ids=list(result));return result
api.ranked_recommendations.hydrate=measured_hydrate
page=api.ranked_recommendations.page
def measured_page(user,authorization,*args,**kwargs):
    if not allowed(int(user['sub'])):return page(user,authorization,*args,**kwargs)
    trace={'trace_id':str(uuid4()),'qa_user_id':int(user['sub']),'stages':[]};token=TRACE.set(trace);started=time.perf_counter()
    try:
        result=page(user,authorization,*args,**kwargs)
        trace.update(offset=result['offset'],limit=result['limit'],ranking=result['ranking'],
           final_count=result['count'],results=[{'work_id':r['work_id'],'title':r['title'],'score':r['score']} for r in result['recommendations']])
        return result
    except Exception as error:trace['error_type']=type(error).__name__;raise
    finally:
        trace['elapsed_ms']=(time.perf_counter()-started)*1000;TRACE.reset(token)
        with LOCK:
            with OUT.open('a',encoding='utf8') as handle:handle.write(json.dumps(trace,default=str)+'\n')
api.ranked_recommendations.page=measured_page
if __name__=='__main__':
    import uvicorn
    uvicorn.run(api.app,host='127.0.0.1',port=8004)
