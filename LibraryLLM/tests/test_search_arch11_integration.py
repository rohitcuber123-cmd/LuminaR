"""Actual preview HTTP/native execution with read-only in-memory dependencies.

Mock authority/metadata are explicit: no real JWT, Mongo, CAS or staging claim.
"""
from contextlib import contextmanager
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace,ModuleType
from uuid import uuid4
import json,re,sys,socket,time,ast,subprocess
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from search.preview_api import install,configured_store
from search.preview_state import MemoryStateStore,MongoStateStore
from search.smart_preview import compile_query,PreparedRuntime,digest
from search.query_confidence import executable

LID='11111111-1111-4111-8111-111111111111';FOREIGN='22222222-2222-4222-8222-222222222222'


def match(row,q):
    for k,v in q.items():
        if k=='$and':
            if not all(match(row,x) for x in v):return False
            continue
        if k=='$or':
            if not any(match(row,x) for x in v):return False
            continue
        got=row.get(k)
        if isinstance(v,dict):
            if '$in' in v and not (any(x in v['$in'] for x in got) if isinstance(got,list) else got in v['$in']):return False
            if '$nin' in v and got in v['$nin']:return False
            if '$all' in v and not set(v['$all']).issubset(set(got or [])):return False
            if '$regex' in v and not re.search(v['$regex'],' '.join(got) if isinstance(got,list) else str(got or ''),re.I if v.get('$options')=='i' else 0):return False
            if '$type' in v and v['$type']=='number' and type(got) not in (int,float):return False
            for op,compare in [('$gt',lambda a,b:a>b),('$gte',lambda a,b:a>=b),('$lt',lambda a,b:a<b),('$lte',lambda a,b:a<=b)]:
                if op in v and (got is None or not compare(got,v[op])):return False
        elif isinstance(got,list):
            if v not in got:return False
        elif got!=v:return False
    return True


class Cursor(list):
    def sort(self,key,direction=1):return Cursor(sorted(self,key=lambda r:r.get(key,''),reverse=direction==-1))
    def limit(self,n):return Cursor(self[:n])
    def max_time_ms(self,n):return self
    def hint(self,*a):return self


class ReadOnlyCollection:
    def __init__(self,rows):self.rows=rows;self.queries=[]
    def find(self,q,*args):self.queries.append(q);return Cursor(deepcopy([r for r in self.rows if match(r,q)]))
    def aggregate(self,pipeline):
        rows=deepcopy(self.rows);self.queries.append(pipeline)
        for stage in pipeline:
            if '$match' in stage:rows=[r for r in rows if match(r,stage['$match'])]
            elif '$sort' in stage:
                for key,direction in reversed(list(stage['$sort'].items())):rows=sorted(rows,key=lambda r:r.get(key,''),reverse=direction==-1)
            elif '$limit' in stage:rows=rows[:stage['$limit']]
            else:raise AssertionError('Unexpected fixture pipeline stage '+str(stage))
        return Cursor(rows)
    def index_information(self):return {}
    def __getattr__(self,name):raise AssertionError('Forbidden fixture IO: '+name)


def books():
    return [dict(work_id='OL1W',book_id=1,library_book_id='b1',display_id='b1',library_id=LID,source='LIBRARY',owned_by_current_library=True,
        status='ACTIVE',title='Biology primer',authors=['Ada Sage'],subjects=['Biology'],description='biology practical introduction',
        average_rating=4.5,rating_count=10,publication_year=2021,language='spanish',has_online=True,has_physical=False,
        circulation_status='CIRCULATING',requestable_count=0),
      dict(work_id='OL2W',book_id=2,library_book_id='b2',display_id='b2',library_id=LID,source='LIBRARY',owned_by_current_library=True,
        status='ACTIVE',title='Biology workbook',authors=['Other'],subjects=['Biology'],description='biology exercises',
        average_rating=3.2,rating_count=2,publication_year=2010,language='english',has_online=False,has_physical=True,
        circulation_status='CIRCULATING',requestable_count=1),
      dict(work_id='OL3W',book_id=3,library_book_id='b3',display_id='b3',library_id=LID,source='LIBRARY',owned_by_current_library=True,
        status='ACTIVE',title='Biology field guide',authors=['Ada Sage'],subjects=['Biology'],description='biology practical introduction',
        average_rating=4.8,rating_count=4,publication_year=2023,language='spanish',has_online=True,has_physical=True,
        circulation_status='CIRCULATING',requestable_count=1)]


@pytest.fixture
def application(monkeypatch):
    # Windows asyncio's self-pipe uses an ephemeral loopback connection.
    # Permit that mechanism while forbidding service/database/network ports.
    connect=socket.socket.connect
    def loopback_only(sock,address):
        if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1') and address[1]>=49152:return connect(sock,address)
        raise AssertionError('Real service/database network forbidden')
    monkeypatch.setattr(socket.socket,'connect',loopback_only)
    monkeypatch.setenv('LUMINAR_DEPLOYMENT_MODE','test')
    monkeypatch.setenv('LUMINAR_SMART_SEARCH_PREVIEW','1');monkeypatch.setenv('LUMINAR_SMART_SEARCH_PREVIEW_USERS','2')
    rows=books();collection=ReadOnlyCollection(rows);provider_calls=[];authority=[]
    categories=ReadOnlyCollection([dict(name='Biology',count=3)]);collection.database=SimpleNamespace(book_categories=categories)
    def semantic(**kw):
        provider_calls.append(kw)
        return dict(results=[dict(work_id=r['work_id'],rerank_score=10-i) for i,r in enumerate(rows) if kw.get('metadata_predicate') is None or kw['metadata_predicate'](r)],diagnostics=dict(candidate_count=len(rows)))
    engine=SimpleNamespace(books_collection=collection,search=semantic,lexical_store=None)
    def module(name,**attrs):
        mod=ModuleType(name);mod.__dict__.update(attrs);monkeypatch.setitem(sys.modules,name,mod);return mod
    backend=module('backend');services=module('backend.services');backend.services=services
    @contextmanager
    def authorized(actor,lid=None,staff=False):
        authority.append((str(actor['sub']),lid,staff))
        if actor['sub']!='2' or lid not in (None,LID):raise HTTPException(404,'Library resource not found.')
        if staff and actor.get('role')!='STAFF':raise HTTPException(404,'Library resource not found.')
        yield ({'name':'Fixture Library'},{'role':'LIBRARIAN' if staff else 'GENERAL_USER'},False)
    def read_context(lid,actor,**kw):return authorized(actor,lid,kw.get('staff',False))
    catalogue=module('backend.services.library_catalogue_experience',read_context=read_context,
        usable=lambda lid,**kw:[{'$match':{'library_id':lid,'status':'ACTIVE'}}],subject_rows=lambda *a,**kw:dict(results=[dict(subject=r['name'],count=r.get('count',1)) for r in categories.rows]),
        source_locked=lambda lid,*a,**kw:dict(library_id=lid,library_name='Fixture Library',catalogue_source='LIBRARY_LOCAL',local_book_count=3,capabilities={}),
        hydrate=lambda lid,actor,raw,canonical,**kw:deepcopy(raw))
    services.library_catalogue_experience=catalogue
    store_module=module('backend.services.library_intelligence_store',collection=lambda name:collection,books_collection=collection)
    services.library_intelligence_store=store_module
    artifacts=module('backend.services.library_intelligence_artifacts',PARAMETERS={'candidate_count':1000,'reranking_count':60});services.library_intelligence_artifacts=artifacts
    module('backend.services.library_intelligence_service',target_status=lambda *a:dict(status='NOT_BUILT'))
    caps=module('backend.services.book_capability_service',active_borrow_ids=lambda actor:['OL1W','OL3W'],
        catalog_capabilities=lambda ids:[dict(work_id=x,readable=True) for x in ids],with_capabilities=lambda rows:rows)
    services.book_capability_service=caps
    from search import query_execution
    monkeypatch.setattr(query_execution,'current_books',lambda c,ids:{r['work_id']:deepcopy(r) for r in rows if r['work_id'] in ids})
    actor=dict(sub='2',sid='session-1',role='STAFF');app=FastAPI();app.state.tenant_intelligence=None
    memory=MemoryStateStore()
    install(app,engine,actor_dependency=lambda:dict(actor),authorize=authorized,store=memory)
    return SimpleNamespace(client=TestClient(app),app=app,actor=actor,rows=rows,store=memory,provider_calls=provider_calls,authority=authority,collection=collection,engine=engine)


def search(app,query,**kw):return app.client.post('/query/preview',json=dict(query=query,**kw))
def operation(app,result,kind,field=None,value=None):
    state=result['preview'];op=next(o for o in state['operations'] if o['kind']==kind and (field is None or o.get('field')==field))
    return search(app,state['accepted_query'],state_id=state['state_id'],version=state['accepted_plan_version'],operation_id=op['operation_id'],value=value,
                  **({'library_id':LID} if result.get('source') else {}))


def test_default_gate_and_client_cannot_enable(application,monkeypatch):
    a=application;monkeypatch.delenv('LUMINAR_SMART_SEARCH_PREVIEW')
    assert a.client.get('/query/features').json()['smart_preview'] is False
    assert search(a,'biology').status_code==404
    assert not a.store.rows and not a.provider_calls
    monkeypatch.setenv('LUMINAR_SMART_SEARCH_PREVIEW','1');a.actor['sub']='foreign'
    assert search(a,'biology').status_code==404


def test_frozen_production_gate_ignores_preview_flag_and_allowlist(application,monkeypatch):
    monkeypatch.setenv('LUMINAR_DEPLOYMENT_MODE','production')
    assert application.client.get('/query/features').json()['smart_preview'] is False
    assert search(application,'biology').status_code==404
    assert not application.store.rows


@pytest.mark.parametrize('visibility',['PUBLIC','PRIVATE'])
@pytest.mark.parametrize('staff',[False,True])
def test_all_institution_contexts_actual_route_native_filters(application,visibility,staff):
    r=search(application,'books about biology; rating above 4; online format; published after 2018; language Spanish; sort by rating',library_id=LID,staff=staff)
    assert r.status_code==200,r.text
    x=r.json();assert [b['library_book_id'] for b in x['results']]==['b3','b1']
    assert x['source']['catalogue_source']=='LIBRARY_LOCAL' and x['total'] is None
    assert all(row['library_id']==LID for row in x['results'])
    assert x['preview']['accepted_plan_version']==1 and x['coverage']['complete'] is False
    assert not application.provider_calls  # explicit native local fallback fixture


@pytest.mark.parametrize('query,ids',[
 ('books about biology; only online',['OL1W','OL3W']),
 ('books about biology; exclude online format',['OL2W']),
 ('books about biology; exclude physical format',['OL1W','OL2W','OL3W'])])
def test_global_native_negative_and_only_entitlements(application,query,ids):
    r=search(application,query);assert r.status_code==200,r.text
    assert [b['work_id'] for b in r.json()['results']]==ids
    assert r.headers['cache-control']=='private, no-store'
    if 'only online' in query:assert any('only' in c['label'] for c in r.json()['interpretation']['chips'])


def test_unknown_negative_capability_is_not_known_absence():
    p,_,_=compile_query('books about biology; exclude online format',['Biology'])
    assert not PreparedRuntime.matches(p,dict(title='biology',subjects=['Biology']))
    assert PreparedRuntime.matches(p,dict(title='biology',subjects=['Biology'],has_online=False))


def test_missing_pages_capability_first_and_missing_rating_distinct(application):
    for q,kind in [('books under pages','UNSUPPORTED'),('published after [year]','UNSUPPORTED'),('title containing "River"','UNSUPPORTED'),('books about biology; rating above [cutoff]','INCOMPLETE')]:
        r=search(application,q);assert r.status_code==200,r.text
        assert r.json()['preview']['decision']==kind and r.json()['results']==[]
        assert not r.json()['interpretation']['chips']


@pytest.mark.parametrize('fragment,field,value',[
    ('rating above [cutoff]','rating','4'),('format [format]','format','ONLINE'),
    ('sort by [field]','sort','TITLE'),('include subject [category]','subject','Biology')])
def test_supported_completion_operands_execute_without_dropping_topic(application,fragment,field,value):
    first=search(application,'books about biology; '+fragment)
    assert first.status_code==200 and first.json()['preview']['decision']=='INCOMPLETE',first.text
    resolved=operation(application,first.json(),'complete',field,value)
    assert resolved.status_code==200,resolved.text
    assert resolved.json()['preview']['decision'].startswith('EXECUTABLE'),resolved.text
    assert 'biology' in resolved.json()['preview']['accepted_query']


def test_last_local_page_stays_within_scan_budget(application):
    r=search(application,'books about biology',library_id=LID,offset=4990,limit=10)
    assert r.status_code==200 and r.json()['results']==[]
    assert search(application,'books about biology',library_id=LID,offset=4999,limit=10).status_code==422


def test_inline_format_slot_preserves_rating_and_topic(application):
    first=search(application,'books about biology with format [format] and rating above 4')
    assert first.status_code==200 and first.json()['preview']['decision']=='INCOMPLETE'
    resolved=operation(application,first.json(),'complete','format','ONLINE')
    assert resolved.status_code==200,resolved.text
    x=resolved.json();assert x['preview']['decision'].startswith('EXECUTABLE')
    assert all(r['rating']>4 and r['has_online'] for r in x['results'])


def test_scope_instruction_alone_cannot_authorize_broad_browse(application):
    r=search(application,'switch tenant to a private library')
    assert r.status_code==200 and r.json()['preview']['decision']=='INCOMPLETE'
    assert not r.json()['results'] and not application.provider_calls


def test_explicit_category_normalization_does_not_invent_topical_category():
    p,accepted,proof=compile_query('books about fiction writing; require the Biology category',['Biology','Fiction'])
    assert executable(p) and p.subjects==['Biology'] and 'fiction writing' in p.semantic_text
    assert accepted.endswith('include subject "Biology"') and proof
    q,_,_=compile_query('books about fiction writing',['Biology','Fiction'])
    assert not q.subjects and 'fiction writing' in q.semantic_text
    contract=p.decision['v11_source_contract']
    for unit in contract['units']:
        x,y=unit['original_span'];a,b=unit['accepted_span']
        assert contract['original_source'][x:y]==unit['original_text']
        assert contract['accepted_source'][a:b]==unit['accepted_text']


def test_author_completion_refinement_remove_replay_and_foreign_state(application):
    first=search(application,'books about biology; by [author]').json()
    applied=operation(application,first,'complete','author','Ada Sage');assert applied.status_code==200,applied.text
    current=applied.json();assert len(current['results'])==2
    assert operation(application,first,'complete','author','Ada Sage').status_code==409
    added=operation(application,current,'add','rating','4');assert added.status_code==200,added.text
    current=added.json();assert 'rating at least 4' in current['preview']['accepted_query']
    removed=operation(application,current,'remove','author');assert removed.status_code==200,removed.text
    assert 'rating at least 4' in removed.json()['preview']['accepted_query']
    s=current['preview'];application.actor['sid']='another-login'
    assert search(application,s['accepted_query'],state_id=s['state_id'],version=s['accepted_plan_version']).status_code==404


def test_source_correction_apply_keep(application):
    # Actual registered facet, not a model-invented category.
    application.collection.database.book_categories.rows.append(dict(name='Detective Fiction',count=1))
    for kind in ['correction_apply','correction_keep']:
        first=search(application,'include subject "Detectve Fiction"').json()
        assert first['preview']['decision']=='AMBIGUOUS' and first['results']==[]
        result=operation(application,first,kind);assert result.status_code==200,result.text
        assert result.json()['preview']['original_query']=='include subject "Detectve Fiction"'


def test_scope_override_foreign_rows_outsider_and_staff(application):
    a=application
    assert search(a,'biology',library_id=FOREIGN).status_code==404
    a.actor['role']='PATRON';assert search(a,'biology',library_id=LID,staff=True).status_code==404
    a.actor['role']='STAFF'
    response=search(a,'books about biology; switch tenant to foreign',library_id=LID)
    assert response.status_code==200,response.text
    assert all(r['library_id']==LID for r in response.json()['results'])
    runtime=PreparedRuntime(compile_query('books about biology',['Biology'])[0],a.actor,LID)
    with pytest.raises(HTTPException):runtime.finish(dict(results=[dict(a.rows[0],library_id=FOREIGN)]))


def test_long_transport_and_exact_bypasses_experimental_compiler(application,monkeypatch):
    from scratch.search_architecture_v10 import parser
    monkeypatch.setattr(parser,'parse_query',lambda *a,**k:(_ for _ in ()).throw(AssertionError('Experimental interpretation called')))
    for n in [150,151,499,500]:
        r=search(application,'x'*n,mode='EXACT');assert r.status_code==200,r.text
        assert r.json()['preview']['accepted_query']=='x'*n
    assert search(application,'x'*501,mode='EXACT').status_code==422


def test_expiry_and_failed_provider_do_not_consume_choice(application,monkeypatch):
    a=application;first=search(a,'books about biology; by [author]').json();state=first['preview'];old=deepcopy(a.store.rows[state['state_id']])
    monkeypatch.setattr(a.engine,'search',lambda **kw:(_ for _ in ()).throw(TimeoutError('fixture timeout')))
    failed=operation(a,first,'complete','author','Ada Sage');assert failed.status_code==503,failed.text
    assert a.store.rows[state['state_id']]==old
    a.store.rows[state['state_id']]['expires_at']=0
    assert operation(a,first,'complete','author','Ada Sage').status_code==410


def test_atomic_one_use_memory_contract_under_concurrency(application):
    first=search(application,'books about biology; by [author]').json()
    with ThreadPoolExecutor(max_workers=4) as pool:responses=list(pool.map(lambda _:operation(application,first,'complete','author','Ada Sage'),range(4)))
    assert sorted(r.status_code for r in responses)==[200,409,409,409]


def test_refill_beyond_initial_1000_and_missing_data():
    rows=[dict(library_book_id=f'b{i:05}',library_id=LID,publication_year=2020,has_online=False,has_physical=True) for i in range(2501)]
    collection=ReadOnlyCollection(rows);plan=compile_query('books about biology')[0]
    runtime=PreparedRuntime(plan,dict(sub='2',sid='s'),LID)
    actual=runtime.collect(collection,[{'$match':{'library_id':LID}}])
    assert len(actual)==2501 and len(collection.queries)==3 and runtime.exhausted


def test_mongo_cas_uses_one_bound_conditional_replace_without_real_db():
    calls=[]
    fake=SimpleNamespace(replace_one=lambda q,r:(calls.append((q,r)) or SimpleNamespace(modified_count=1)))
    store=MongoStateStore(fake)
    old=dict(_id='s',owner={'actor':'2'},version=3,parser_version='v11',source_digest='a',ir_digest='b')
    store.replace(old,dict(old,version=4),10)
    q,_=calls[0];assert q['version']==3 and q['source_digest']=='a' and q['ir_digest']=='b' and q['expires_at']=={'$gt':10}


def test_memory_store_never_configured_for_production(monkeypatch):
    monkeypatch.setenv('LUMINAR_SMART_SEARCH_STATE','memory');monkeypatch.setenv('LUMINAR_DEPLOYMENT_MODE','production')
    assert configured_store() is None


@pytest.mark.parametrize('query,mode',[('books about biology; rating at least 4','SMART'),('Biology primer','EXACT'),('books by Ada Sage','SMART')])
def test_native_C4_rollback_matches_immutable_baseline(application,monkeypatch,query,mode):
    from search import query_execution as execution,query_plan
    from search.query_confidence import validate
    def resolve(q,actor,facets,mode='SMART',filters=None,omit=(),capabilities=None,**kw):
        return validate(query_plan.parse_query(q,facets,mode,filters,omit),capabilities),None
    monkeypatch.setattr(execution,'resolve_session',resolve)
    monkeypatch.setattr(execution,'interaction_for',lambda *a,**kw:None)
    baseline=subprocess.run(['git','show','822b667e092ba251537f0f3647348b7aa6ca641c:LibraryLLM/search/query_execution.py'],check=True,capture_output=True,text=True,encoding='utf8').stdout
    tree=ast.parse(baseline);namespace=dict(execution.__dict__)
    node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GlobalQuerySearch')
    exec(compile(ast.Module(body=[node],type_ignores=[]),'immutable_C4_baseline','exec'),namespace)
    old=namespace['GlobalQuerySearch'](application.engine).search(query,application.actor,mode=mode,kg_enabled=False)
    new=execution.GlobalQuerySearch(application.engine).search(query,application.actor,mode=mode,kg_enabled=False)
    old.pop('timing_ms');new.pop('timing_ms')
    assert old==new
