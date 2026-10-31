"""Read-only native-function and retrieval contract fixtures. No Mongo connection."""
import sys,json,re,time,ast
from pathlib import Path
from types import SimpleNamespace,ModuleType
from dataclasses import asdict
from fastapi import HTTPException

def forbid(event,args):
    if event in ['socket.connect','socket.bind','socket.getaddrinfo','subprocess.Popen']:raise RuntimeError('Offline qualification forbids network/process calls')
    if event=='import' and str(args[0]).split('.')[0]=='pymongo':raise RuntimeError('Mongo imports prohibited')
sys.addaudithook(forbid)
from scripts import search_v2c_c5er_offline_native as harness
from scratch.search_proof_recovery_v4 import parser
R=Path('reports');P='search_proof4_native_final_'

def main():
    harness.P=P+'final_';harness.plans=parser;harness.validate=parser.validate;harness.executable=parser.executable
    harness.main()
    original_report=R/(P+'final_offline_native_components.json')
    qualified_report=R/(P+'offline_native_components_final.json')
    original_report.rename(qualified_report)
    # Actual native global execution with an explicitly synthetic semantic
    # provider. This tests filter transport/hydration, not embedding relevance.
    books=[{'work_id':'OL1W','book_id':1,'title':'Harbor Primer','authors':['Aster Vale'],'subjects':'History|Navigation','average_rating':4.4,'rating_count':20},
        {'work_id':'OL2W','book_id':2,'title':'Harbor Workbook','authors':['Aster Vale'],'subjects':'History|Workbooks','average_rating':3.2,'rating_count':10},
        {'work_id':'OL3W','book_id':3,'title':'Advanced Harbors','authors':['Briar Moss'],'subjects':'History|Navigation','average_rating':4.8,'rating_count':10}]
    class Cursor(harness.Cursor):
        def max_time_ms(self,*a):return self
        def hint(self,*a):return self
        def sort(self,*a,**k):return self
        def limit(self,n):return Cursor(self[:n])
    def match(row,q):
        for k,v in q.items():
            if k=='$and':
                if not all(match(row,x) for x in v):return False
            elif k=='$or':
                if not any(match(row,x) for x in v):return False
            elif isinstance(v,dict):
                value=row.get(k)
                if '$type' in v and v['$type']=='number' and type(value) not in [int,float]:return False
                if '$in' in v and value not in v['$in']:return False
                if '$regex' in v and not re.search(v['$regex'],str(value or ''),re.I if v.get('$options')=='i' else 0):return False
                for op,predicate in [('$gte',lambda a,b:a>=b),('$gt',lambda a,b:a>b),('$lte',lambda a,b:a<=b),('$lt',lambda a,b:a<b)]:
                    if op in v and (value is None or not predicate(value,v[op])):return False
            elif row.get(k)!=v:return False
        return True
    class Collection:
        def __init__(self,rows):self.rows=rows;self.database=None;self.queries=[]
        def find(self,q,*a):self.queries.append(q);return Cursor([dict(x) for x in self.rows if match(x,q)])
        def index_information(self):return {}
    collection=Collection(books);categories=Collection([{'name':'History','count':3},{'name':'Navigation','count':2}]);collection.database=SimpleNamespace(book_categories=categories)
    recorded=[]
    def semantic(**kw):
        recorded.append({k:v for k,v in kw.items() if k!='metadata_predicate'})
        return {'results':[{'work_id':r['work_id'],'rerank_score':3-i} for i,r in enumerate(books)],'diagnostics':{'candidate_count':3}}
    engine=SimpleNamespace(books_collection=collection,lexical_store=None,search=semantic)
    def resolve(q,actor,facets,mode='SMART',filters=None,omit=(),capabilities=None,**kw):return parser.validate(parser.parse_query(q,facets,mode,filters,omit),capabilities),None
    env={'asdict':asdict,'perf_counter':time.perf_counter,'HTTPException':HTTPException,'re':re,'STRUCTURED_LIMIT':1000,
        'resolve_session':resolve,'executable':parser.executable,'matches':parser.matches,'normalize':parser.normalize,'sort_books':parser.sort_books,
        'active':lambda p:True,'interaction_for':lambda *a,**k:None,'apply_expansion':lambda *a:None,
        'current_books':lambda c,ids:{b['work_id']:b for b in books if b['work_id'] in ids},'primary_match':parser.primary_match,
        'personalization':SimpleNamespace(rerank=lambda rows,*a:(rows,{'enabled':False}))}
    # Class extraction is exact protected source, with only its dependencies
    # replaced; no backend module initialization or server health polling.
    source=Path('search/query_execution.py');pre=json.loads((R/(P+'preflight.json')).read_text(encoding='utf8'))
    expected=next(h for p,h in pre['protected_files'].items() if Path(p).resolve()==source.resolve());assert harness.sha(source)==expected
    tree=ast.parse(source.read_text(encoding='utf8'));names=['interpretation','guarded_response','global_facets']
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names or isinstance(n,ast.ClassDef) and n.name=='GlobalQuerySearch']
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),env)
    old={}
    def module(name,**kw):
        old[name]=sys.modules.get(name);m=ModuleType(name);m.__dict__.update(kw);sys.modules[name]=m;return m
    backend=module('backend');services=module('backend.services');backend.services=services
    capabilities=module('backend.services.book_capability_service',with_capabilities=lambda rows:rows,active_borrow_ids=lambda uid:[],catalog_capabilities=lambda ids:[])
    services.book_capability_service=capabilities
    observations=[]
    try:
        search=env['GlobalQuerySearch'](engine)
        cases=[('Topic: coastal navigation; include subject History; rated at least 4; exclude the searchable-text whole word "workbook"','SMART',2),
            ('beginner-friendly coastal navigation; rated at least 4','SMART',2),('advanced research about harbors; rated above 4','SMART',2),
            ('books by Aster Vale','SMART',2),('Harbor Primer','EXACT',1),('include subject History; rated above 4','SMART',2),
            ('include subject History; exclude the searchable-text whole word "Harbor"','SMART',1),('include subject Navigation; rated above 4.9','SMART',0)]
        for q,mode,count in cases:
            start=time.perf_counter();before=len(recorded);result=search.search(q,{'sub':'2'},mode=mode,diagnostics=True,kg_enabled=False,personalized=False,limit=1)
            assert result['total_ranked_candidates']==count,(q,result['diagnostics']['plan'],result['total_ranked_candidates'])
            assert result['returned']==min(count,1) and result['has_more']==(count>1)
            if count>1:
                nextpage=search.search(q,{'sub':'2'},mode=mode,diagnostics=True,kg_enabled=False,personalized=False,limit=1,offset=1)
                assert nextpage['results'][0]['work_id']!=result['results'][0]['work_id']
            if 'coastal navigation' in q:
                assert len(recorded)>before and 'coastal navigation' in recorded[-1]['query']
            json.dumps(result,default=str)
            observations.append({'query':q,'mode':mode,'expected_fixture_matches':count,'actual':result['total_ranked_candidates'],'provider':result['diagnostics']['provider'],'elapsed_ms':(time.perf_counter()-start)*1000})
    finally:
        for name,m in reversed(list(old.items())):
            if m is None:sys.modules.pop(name,None)
            else:sys.modules[name]=m
    report={'status':'PASS_COMPONENT_CONTRACTS_ONLY','global_cases':observations,'semantic_provider_inputs':recorded,'structured_queries':collection.queries,
        'semantic_constraint_correctness':'Mandatory/negative predicates verified against deterministic fixture metadata after native hydration; semantic topic reaches native provider.',
        'ranking_relevance':'N/A: fixed-ID semantic provider, no independent embedding/ranking relevance oracle or real vector service.',
        'scope_and_authority':'40 local-library native-function fixtures separate; mocked authority/collection execution is not full live Mongo/API qualification.',
        'Mongo_calls':0,'network_calls':0,'production_files_changed':0,'HNSW_KG_rebuilds':0,'full_end_to_end_qualified':False}
    with (R/(P+'retrieval_contracts_final.json')).open('x',encoding='utf8') as f:json.dump(report,f,indent=2)
    print(json.dumps({'global_fixture_cases':len(observations),'local_fixture_cases':40,'Mongo_calls':0,'real_embedding_relevance':'N/A'}))
if __name__=='__main__':main()
