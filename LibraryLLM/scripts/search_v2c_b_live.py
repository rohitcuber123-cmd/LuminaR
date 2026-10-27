"""Current running-service evidence, without production catalogue edits."""
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
import json,statistics,time
import httpx
from backend.database.mongodb import db
from backend.utils.jwt_utils import create_access_token
from search.query_plan import parse_query

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reports'
baseline=json.loads((R/'search_v2c_b_baseline.json').read_text())
fixture=json.loads((R/'search_v2c_b_fixture.json').read_text())
client=httpx.Client(base_url='http://127.0.0.1:8003',timeout=60)
def headers(uid=4):
    u=db.users.find_one({'user_id':uid});return {'Authorization':'Bearer '+create_access_token(uid,u['email'],u['role'])}
owner=headers();member=headers(fixture['member_id']);outsider=headers(fixture['outsider_id'])
private_patron=member
def measure(values):return {'n':len(values),'p50_ms':statistics.median(values),'p95_ms':sorted(values)[max(0,int(.95*len(values))-1)],'samples_ms':values}
def timed(method,url,**kw):
    start=time.perf_counter();r=getattr(client,method)(url,**kw);elapsed=(time.perf_counter()-start)*1000;r.raise_for_status();return r.json(),elapsed
report={'captured_at':datetime.now(timezone.utc).isoformat(),'search':{},'suggestions':{},'clarification':{},'quality':[],'security':[],'private_patron_measurement_identity':'disposable general-user member in patron workspace; temporarily restored only for final measurement after the successful revocation test'}
for name,group in baseline['search'].items():
    samples=[]
    for _ in range(20):
        if group['library_id']:data,t=timed('get',f'/libraries/{group["library_id"]}/catalogue/search',headers=owner,params={'search':group['query'],'staff':'true','limit':10,'personalized':'false'})
        else:data,t=timed('post','/search',headers=owner,json={'query':group['query'],'limit':10,'save_history':False,'personalized':False})
        samples.append(t)
    report['search'][name]={**measure(samples),'query':group['query'],'before':{k:group[k] for k in ('p50_ms','p95_ms')},'returned':len(data['results'])}
facets=[r['subject'] for r in client.get('/facets',headers=owner).json()['results']]
samples=[]
for _ in range(25):
    for q in baseline['parser']['queries']:
        start=time.perf_counter();parse_query(q,facets);samples.append((time.perf_counter()-start)*1000)
report['parser']={**measure(samples),'same_queries':baseline['parser']['queries'],'same_facets':facets==baseline['parser']['facets'],'before':{k:baseline['parser'][k] for k in ('p50_ms','p95_ms')}}
for name,lid,staff,actor,q in [('GLOBAL',None,False,owner,'neur'),('TEST',fixture['public_library_id'],False,member,'comp'),('PRIVATE_PATRON',fixture['library_id'],False,private_patron,'neur'),('PRIVATE_STAFF',fixture['library_id'],True,owner,'neur')]:
    params={'q':q,'mode':'SMART'}
    if lid:params.update(library_id=lid,staff=str(staff).lower())
    cold=[];warm=[]
    for _ in range(20):
        # Distinct login sid forces an uncached, authorized projection. OS/DB
        # page caches and resident models remain warm; this is not cold boot.
        data,t=timed('get','/query/suggestions',headers=headers(fixture['member_id'] if actor is member else 4),params=params);cold.append(t)
    for _ in range(20):data,t=timed('get','/query/suggestions',headers=actor,params=params);warm.append(t)
    report['suggestions'][name]={'cold_projection':measure(cold),'warm_projection':measure(warm),'sample':data}
    assert len(data['suggestions'])<=8
    report['quality'].append({'scope':name,'query':q,'suggestions':[{k:v for k,v in i.items() if k!='id'} for i in data['suggestions']]})
    if data['suggestions']:
        body={'q':q,'mode':'SMART','suggestion_id':data['suggestions'][0]['id']}
        if lid:body.update(library_id=lid,staff=staff)
        response=client.post('/query/suggestions/select',headers=actor,json=body)
        report['security'].append({'case':name+' issued suggestion selection','status':response.status_code});assert response.status_code==200
        response=client.post('/query/suggestions/select',headers=actor,json={**body,'suggestion_id':'forged'})
        report['security'].append({'case':name+' forged suggestion denied','status':response.status_code});assert response.status_code==409
for name,lid,staff,actor,q,mode in [('GLOBAL_TITLE',None,False,owner,'the hob','TITLE_AUTHOR'),('GLOBAL_AUTHOR',None,False,owner,'isaac','TITLE_AUTHOR'),('GLOBAL_SUBJECT',None,False,owner,'fict','GENRE_SUBJECT'),('GLOBAL_TYPO',None,False,owner,'histroy','SMART'),('PRIVATE_AUTHOR',fixture['library_id'],False,private_patron,'synthetic','TITLE_AUTHOR'),('PRIVATE_TITLE',fixture['library_id'],False,private_patron,'v2cb','TITLE_AUTHOR'),('PRIVATE_TYPO',fixture['library_id'],False,private_patron,'detectve fiction','SMART')]:
    params={'q':q,'mode':mode}
    if lid:params.update(library_id=lid,staff=staff)
    samples=[]
    for _ in range(20):data,t=timed('get','/query/suggestions',headers=actor,params=params);samples.append(t)
    report['suggestions'][name]={**measure(samples),'sample':data}
    report['quality'].append({'scope':name,'query':q,'suggestions':[{k:v for k,v in i.items() if k!='id'} for i in data['suggestions']]})
for uid,label,staff in [(fixture['outsider_id'],'private outsider',False),(fixture['member_id'],'patron cannot use staff',True)]:
    response=client.get('/query/suggestions',headers=headers(uid),params={'q':'v2cb','library_id':fixture['library_id'],'staff':staff})
    report['security'].append({'case':label,'status':response.status_code,'body':response.json()});assert response.status_code in (403,404)
data,_=timed('get','/query/suggestions',headers=owner,params={'q':'v2cb'})
assert not any('V2CB' in i['display'] for i in data['suggestions']);report['security'].append({'case':'private vocabulary absent from Global','passed':True})
generation=[];resolution=[];contexts=[]
try:
    for _ in range(20):
        sid=str(uuid4());contexts.append(sid)
        data,t=timed('post','/search',headers=owner,json={'query':'fiction rating above','session_id':sid,'limit':10,'save_history':False});generation.append(t)
        assert not db.search_sessions_v2b.find_one({'_id':sid})
        choice=data['interpretation']['clarification']
        data,t=timed('post','/query/resolve',headers=owner,json={'clarification_id':choice['clarification_id'],'choice_id':choice['candidate_choices'][0]['choice_id'],'query':'fiction rating above','session_id':sid,'value':'3'});resolution.append(t)
        assert any(c['label']=='Rating: > 3' for c in data['interpretation']['chips'])
    report['clarification']={'generation_http_including_guard':measure(generation),'resolution_http_including_existing_search':measure(resolution),'unaccepted_contexts_committed':False,'strict_rating_preserved':True}
finally:
    db.search_sessions_v2b.delete_many({'user_id':'4','$or':[{'_id':{'$in':contexts}},{'search_session_id':{'$in':contexts}}]})
report['health']=client.get('/health').json();report['global_book_count']=db.books.count_documents({})
(R/'search_v2c_b_live_observations.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf8')
print(json.dumps({'search':{k:{x:v[x] for x in ('p50_ms','p95_ms')} for k,v in report['search'].items()},'parser':{k:report['parser'][k] for k in ('p50_ms','p95_ms')},'suggestions':{k:({x:v['warm_projection'][x] for x in ('p50_ms','p95_ms')} if 'warm_projection' in v else {x:v[x] for x in ('p50_ms','p95_ms')}) for k,v in report['suggestions'].items()}}))
