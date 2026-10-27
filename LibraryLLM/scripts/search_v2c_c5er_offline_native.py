"""Read-only native-function harness. Does not import backend/Mongo modules.

Compile exact named functions from protected source. Dependency doubles expose
read-only in-memory fixture collections. This is component evidence, NOT real
Mongo/API/authorization/commit qualification. The user prohibits all Mongo writes.
"""
from pathlib import Path
from types import ModuleType,SimpleNamespace
from contextlib import contextmanager
from datetime import datetime,timezone
from dataclasses import asdict
import ast,json,hashlib,re,sys,time,statistics,math
from fastapi import HTTPException
from scratch.search_v2c_c5er.candidate_search_v3 import query_plan as plans
from scratch.search_v2c_c5er.candidate_search_v3.query_confidence import validate,executable
R=Path('reports');P='search_v2c_c5er_'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def compile_functions(path,names,namespace):
    pre=json.loads((R/(P+'preflight.json')).read_text(encoding='utf8'))
    h=next(v for k,v in pre['protected_files'].items() if Path(k).resolve()==Path(path).resolve());assert sha(path)==h
    tree=ast.parse(Path(path).read_text(encoding='utf8'));selected=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names]
    assert {n.name for n in selected}==set(names)
    exec(compile(ast.Module(body=selected,type_ignores=[]),path,'exec'),namespace)
    return {n:namespace[n] for n in names}
def match(row,q):
    for k,v in q.items():
        if k=='$or':
            if not any(match(row,x) for x in v):return False
            continue
        got=row.get(k)
        if isinstance(v,dict):
            if '$in' in v and got not in v['$in']:return False
            if '$all' in v and not set(v['$all']).issubset(set(got or [])):return False
            if '$type' in v and v['$type']=='string' and not isinstance(got,str):return False
            if '$regex' in v and not re.search(v['$regex'],str(got or ''),re.I if v.get('$options')=='i' else 0):return False
        elif isinstance(got,list):
            if v not in got:return False
        elif got!=v:return False
    return True
class Cursor(list):
    def sort(self,*a,**k):return self
    def limit(self,n):return Cursor(self[:n])
class ReadOnly:
    def __init__(self,rows=(),inaccessible=False):self.rows=list(rows);self.inaccessible=inaccessible;self.reads=0;self.name='READ_ONLY_FIXTURE'
    def find(self,q,*a,**k):
        self.reads+=1
        if self.inaccessible:raise RuntimeError('Global catalogue deliberately inaccessible')
        return Cursor([dict(r) for r in self.rows if match(r,q)])
    def count_documents(self,q):return len(self.find(q))
    def aggregate(self,pipeline):
        result=Cursor([dict(r) for r in self.rows])
        for stage in pipeline:
            if '$match' in stage:result=Cursor([r for r in result if match(r,stage['$match'])])
            elif '$limit' in stage:result=Cursor(result[:stage['$limit']])
            elif '$count' in stage:result=Cursor([{stage['$count']:len(result)}]) if result else Cursor([])
            else:raise AssertionError('Unsupported fixture stage '+str(stage))
        return result
    def __getattr__(self,name):raise AssertionError('Mutation or unsupported fixture operation forbidden: '+name)

def main():
    records=[];timings=[];original_modules={};touched=[]
    def module(name,**attributes):
        if name not in original_modules:original_modules[name]=sys.modules.get(name)
        m=ModuleType(name);m.__dict__.update(attributes);sys.modules[name]=m;return m
    try:
        backend=module('backend');services=module('backend.services');backend.services=services
        format_module=module('backend.services.library_book_formats',format_pipeline=lambda *a,**k:[])
        services.library_book_formats=format_module
        for inaccessible in [False,True]:
            global_books=ReadOnly([],inaccessible=inaccessible)
            for role in ['PATRON','STAFF']:
                for visibility in ['PRIVATE','PUBLIC']:
                    lid='c5er-'+visibility.lower();staff=role=='STAFF';who={'sub':'2','sid':'offline'}
                    local=ReadOnly([{'library_id':lid,'library_book_id':'local-1','status':'ACTIVE','title':'C5ER Local Atlas','authors':['Local Author'],
                        'subjects':['History'],'description':'private owned reference','has_physical':True,'has_online':False,'global_work_id':None},
                        {'library_id':'other-library','library_book_id':'foreign-1','status':'ACTIVE','title':'Other private book','authors':['Other'],'subjects':['History'],'has_physical':True}])
                    def collection(name):return local if name=='library_books' else ReadOnly([])
                    def guard(requested,actor,**kw):
                        assert requested==lid
                        if actor.get('sub')!='2':raise HTTPException(404,'Library resource not found.')
                        return {'name':'Offline own-book library'},{'role':'LIBRARIAN' if staff else 'GENERAL_USER'}
                    ng={'contextmanager':contextmanager,'re':re,'actor_id':lambda a:int(a['sub']),'collection':collection,'books_collection':global_books,
                        'book_capabilities':lambda ids:{},'enabled':lambda lid:False,'UNAVAILABLE':[],'project':lambda *a,**k:None,
                        'require_library_staff':guard,'require_library_patron':guard,'require_library_membership':guard,'require_readable':lambda lid:None,
                        'lending':SimpleNamespace(journal=SimpleNamespace(state=lambda lid:'NONCANONICAL'))}
                    funcs=compile_functions('backend/services/library_catalogue_experience.py',['read_context','usable','source_locked','hydrate'],ng)
                    catalogue=module('backend.services.library_catalogue_experience',**funcs)
                    catalogue.subject_rows=lambda *a,**k:{'results':[{'subject':'History','count':1}]}
                    services.library_catalogue_experience=catalogue
                    store=module('backend.services.library_intelligence_store',collection=collection,books_collection=global_books)
                    services.library_intelligence_store=store
                    artifacts=module('backend.services.library_intelligence_artifacts',PARAMETERS={'reranking_count':60})
                    services.library_intelligence_artifacts=artifacts
                    module('backend.services.library_intelligence_service',target_status=lambda *a:{'status':'NOT_BUILT'})
                    def resolve(q,actor,facets,mode='SMART',capabilities=None,filters=None,omit=(),**kw):
                        return validate(plans.parse_query(q,facets,mode,filters,omit),capabilities),None
                    env={'asdict':asdict,'perf_counter':time.perf_counter,'HTTPException':HTTPException,'STRUCTURED_LIMIT':1000,
                        'resolve_session':resolve,'executable':executable,'matches':plans.matches,'normalize':plans.normalize,'sort_books':plans.sort_books,
                        'interaction_for':lambda *a,**k:None,'apply_expansion':lambda *a:None,
                        'personalization':SimpleNamespace(rerank=lambda rows,*a:(rows,{'enabled':False}))}
                    native=compile_functions('search/query_execution.py',['interpretation','guarded_response','_tenant_search'],env)
                    for query,mode,wanted in [('include History','SMART',1),('include History; exclude every record containing the text "Atlas"','SMART',0),
                        ('C5ER Local Atlas','EXACT',1),('books by Local Author','SMART',1),('include Fiction','SMART',0)]:
                        start=time.perf_counter();response=native['_tenant_search'](None,lid,who,query,staff=staff,mode=mode,kg_enabled=False,personalized=False,diagnostics=True)
                        duration=(time.perf_counter()-start)*1000;timings.append(duration)
                        assert len(response['results'])==wanted,(query,response)
                        assert response['source']['catalogue_source']=='LIBRARY_LOCAL' and response['source']['capabilities']['global_discovery'] is False
                        assert all(r['library_id']==lid and r['global_work_id'] is None for r in response['results'])
                        json.dumps(response,default=str)
                        records.append({'scope':visibility+'_'+role,'global_state':'INACCESSIBLE' if inaccessible else 'EMPTY','query':query,'mode':mode,'returned':wanted,'elapsed_ms':duration,'result':'PASS'})
                    assert global_books.reads==0,'Own-book private/local search unexpectedly read global catalogue'
                    # Native read-context guard is executed with fixture authority.
                    try:native['_tenant_search'](None,lid,{'sub':'outsider'},'include History',staff=staff,kg_enabled=False)
                    except HTTPException as e:assert e.status_code==404
                    else:raise AssertionError('Fixture guard not reached')
        choices=compile_functions('search/query_interaction.py',['choices_for'],{'normalize':plans.normalize,'executable':executable})['choices_for']
        choice_records=[]
        for q,kind,operation in [('Fiction 4','AMBIGUOUS','literal'),('rated above','INCOMPLETE','complete'),
            ('rated above 4; rated below 3','CONTRADICTORY','bound'),('include subject "Detectve Fiction"','EXECUTABLE_WITH_NOTICE','correction_apply')]:
            plan=plans.parse_query(q,['Fiction','Detective Fiction']);assert plan.decision['decision_type']==kind
            question,rows=choices(plan,{'rating':True,'year':True,'formats':['ONLINE','PHYSICAL','BOTH']})
            assert operation in {r['operation'] for r in rows}
            choice_records.append({'query':q,'kind':kind,'question':question,'operations':[r['operation'] for r in rows]})
    finally:
        for name,old in reversed(list(original_modules.items())):
            if old is None:sys.modules.pop(name,None)
            else:sys.modules[name]=old
    timings.sort()
    result={'status':'PASS_WITH_LIMITED_QUALIFICATION','component_search_checks':len(records),'records':records,'native_choice_projection_checks':choice_records,
        'private_library_independence':'Own local unlinked books searched with empty/inaccessible global fixture; zero global collection reads. Exact native functions, read-only in-memory dependencies.',
        'full_native_integration_validated':False,'Mongo_calls':0,'Mongo_writes':0,'network_calls':0,'inventory_or_borrow_commits':0,'HNSW_KG_builds':0,
        'limitations':['No real Mongo session durability, API token issuance, current membership lookup, canonical circulation locks or one-use commit tested in this phase.',
            'Authority, provider status, format rows and local pipeline execution are explicit fixture doubles; these checks cannot substitute for historical310 real native/security scenarios.',
            'Timing is offline native-function plus parser and in-memory fixtures, not comparable production full-search or real-Mongo fixture request latency.'],
        'latency':{'count':len(timings),'p50_ms':statistics.median(timings),'p95_ms':timings[math.ceil(.95*len(timings))-1],'max_ms':max(timings)},
        'source_hashes':{p:sha(p) for p in ['search/query_execution.py','search/query_interaction.py','backend/services/library_catalogue_experience.py']}}
    with (R/(P+'offline_native_components.json')).open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
    print(json.dumps({'component_search_checks':len(records),'choice_projection_checks':len(choice_records),'Mongo_writes':0,'full_native_qualification':False}))
if __name__=='__main__':main()
