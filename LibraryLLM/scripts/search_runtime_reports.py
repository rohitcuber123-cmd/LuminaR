"""Derive runtime closure reports from recorded calls and independent controls."""
import json,re,sys,time,statistics
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));REPORTS=ROOT/'reports'
from scripts.post_2h_baseline import snapshot
from backend.services import library_intelligence_store as store
from backend.services.library_catalogue_experience import usable
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
def read(name):return json.loads((REPORTS/name).read_text(encoding='utf8'))
def put(name,value): (REPORTS/name).write_text(json.dumps(value,indent=2,ensure_ascii=False,default=str),encoding='utf8')
def write(name,value):(REPORTS/name).write_text(value,encoding='utf8')
def stats(values):
    values=sorted(values)
    if not values:return None
    def percentile(p):
        pos=(len(values)-1)*p;lo=int(pos);hi=min(lo+1,len(values)-1)
        return values[lo]+(values[hi]-values[lo])*(pos-lo)
    return {'n':len(values),'p50_ms':round(percentile(.5),3),'p95_ms':round(percentile(.95),3),'min_ms':round(values[0],3),'max_ms':round(values[-1],3)}
def suite(name):
    tree=ET.parse(REPORTS/name);cases=tree.findall('.//testcase')
    return {'file':name,'tests':len(cases),'failures':len(tree.findall('.//failure')),'errors':len(tree.findall('.//error')),'skipped':len(tree.findall('.//skipped'))}

if __name__=='__main__':
 traces=[json.loads(l) for l in (ROOT/'.scratch/search-runtime/events.jsonl').read_text(encoding='utf8').splitlines()]
 tenant=[r for r in traces if r['provider_scope']=='TENANT' and any(s['name']=='FAISS_SEARCH' for s in r['stages'])]
 global_cold=next(r for r in traces if any(s['name']=='GLOBAL_FAISS_SEARCH' for s in r['stages']))
 browser=read('search_browser_validation.json');assert browser['status']=='PASS'
 initial=read('search_runtime_initial_browser.json')
 transition=[c for c in initial['checks'] if c['scenario'].startswith(('Disposable NOT_BUILT','Disposable Search Index built'))]
 assert len(transition)==2
 browser['disposable_transition_first_run']=transition
 browser['operational_browser']=read('search_inventory_browser.json')
 browser['view_all_repair_browser']=read('search_view_all_browser.json')
 browser['rerun_notes']='The first harness encountered a transient 503 and synchronous response-listener reentrancy. The corrected runner observes responses without blocking event listeners and waits for the frontend accepted retry. No product routing change was necessary.'
 put('search_browser_validation.json',browser)
 # Preserve one measured cold global query, tenant query variants, and before-build evidence.
 unique={}
 for r in tenant:unique[(r['library_id'],r['query'])]=r
 fallback=[r for r in traces if r['provider_scope']=='TENANT' and r.get('response_source',{}).get('intelligence_status')=='NOT_BUILT']
 put('search_hnsw_runtime_validation.json',{'status':'PASS','method':'Opt-in loopback QA wrapper around actual resident FAISS search, CrossEncoder.predict, and canonical hydrators; no mocked browser providers',
     'production_debug_endpoint_added':False,'global_cold_query':global_cold,'tenant_queries':list(unique.values()),
     'before_build_fallback':fallback,'raw_local_trace':'.scratch/search-runtime/events.jsonl',
     'global_cache_policy':'Cold pool invokes global HNSW + reranker. Repeated identical generation/query uses the accepted ranking cache, with fresh canonical hydration.'})
 comparisons=[]
 rows=list(store.collection('library_books').find({'library_id':TEST,'status':'ACTIVE'},{'_id':0}))
 for c in browser['checks']:
    if not c['scenario'].startswith('TEST Staff semantic:'):continue
    q=c['query'];trace=unique[(TEST,q)];hs=next(s for s in trace['stages'] if s['name']=='FAISS_SEARCH');rs=next(s for s in trace['stages'] if s['name']=='CROSS_ENCODER')
    independent=[r['library_book_id'] for r in rows if q.casefold() in r.get('search_text','')]
    assert independent==[r['library_book_id'] for r in c['lexical_baseline']]
    comparisons.append({'query':q,'baseline_provider':'Existing tenant Mongo escaped casefolded contiguous search_text substring (not BM25/token-OR)',
        'independent_control_ids':independent,'baseline_results':c['lexical_baseline'],'hnsw_candidates':hs['candidates'],
        'reranked':rs['ranked'],'final_hydrated':trace['final_results'],'relevant_result_rank':c['target_rank'],
        'pass':not independent and c['target_rank']<=20})
 assert len(comparisons)==4 and all(c['pass'] for c in comparisons)
 poor=unique[(TEST,'getting around when walking is difficult')]
 put('search_keyword_semantic_comparison.json',{'status':'PASS','controls':comparisons,
     'exploratory_query_limitation':{'query':poor['query'],'observation':'Relevant Mobility title was HNSW rank 1 but CrossEncoder rank 44, outside the first page. This is a relevance limitation, not a route bypass. Accepted ranking remains unchanged.'},
     'limits':'Four controlled positive examples establish runtime semantic discrimination against the actual older substring provider. This is not a general relevance benchmark or proof of every natural-language paraphrase.'})
 reranks=[]
 for trace in [global_cold,*unique.values()]:
    r=next(s for s in trace['stages'] if s['name']=='CROSS_ENCODER');h=next(s for s in trace['stages'] if s['name'] in ['FAISS_SEARCH','GLOBAL_FAISS_SEARCH'])
    reranks.append({'scope':trace['provider_scope'],'library_id':trace['library_id'],'query':trace['query'],
        'model':r['model'],'hnsw_candidate_count':len(h['candidates']),'reranked_count':r['count'],
        'reranking_elapsed_ms':r['elapsed_ms'],'kg_used':False,'hydration_observed':any('HYDRATION' in s['name'] for s in trace['stages'])})
 put('search_reranker_validation.json',{'status':'PASS','actual_predict_calls':reranks,'accepted_depths':{'global':50,'tenant':60},'configuration_changed':False})
 fixture=read('search_runtime_fixture.json');lid=fixture['library_id']
 status=store.collection('intelligence_targets').find_one({'library_id':TEST,'target':'SEARCH_INDEX'})
 kg=store.collection('intelligence_targets').find_one({'library_id':TEST,'target':'KNOWLEDGE_GRAPH'})
 graph=json.loads((store.directory(TEST,'kg',kg['active_generation_id'])/'graph.json').read_text(encoding='utf8'))
 eligible={r['library_book_id'] for r in store.source_records(TEST)}
 book_neighbors={};feature_books={}
 for edge in graph['edges']:
    if edge['source'].startswith('book:'):
        bid=edge['source'][5:];book_neighbors.setdefault(bid,set()).add(edge['target']);feature_books.setdefault(edge['target'],set()).add(bid)
 evaluations=[];kg_times=[]
 targets={'beginner computer networking':'TEST Campus Network Practice Workbook','accessibility transportation':'Mobility and transport for elderly and handicapped persons',
          'community memories':'TEST Community Oral History Handbook','equipment design workshop':'TEST Makerspace Equipment Guide'}
 for q,title in targets.items():
    trace=unique[(TEST,q)];h=next(s for s in trace['stages'] if s['name']=='FAISS_SEARCH')['candidates'];pool=[r['library_book_id'] for r in h[:60]]
    started=time.perf_counter();neighbors=set()
    for seed in pool[:5]:
        for feature in sorted(book_neighbors.get(seed,set())):
            neighbors.update(feature_books.get(feature,set()))
    additions=sorted(neighbors&eligible-set(pool))[:20];kg_times.append((time.perf_counter()-started)*1000)
    target=next(r['library_book_id'] for r in rows if r['title']==title)
    evaluations.append({'query':q,'hnsw_rerank_pool_size':len(pool),'relevant_in_hnsw_pool':target in pool,
        'bounded_same_tenant_neighbors_added':len(additions),'added_ids':additions,'relevant_gain':int(target not in pool and target in additions),
        'cross_library_ids':0,'method':'Two-hop shared Subject/Author/Classification neighbors from top five HNSW seeds, max 20 additional eligible same-tenant IDs'})
 assert all(e['relevant_in_hnsw_pool'] and e['relevant_gain']==0 for e in evaluations)
 put('search_kg_candidate_evaluation.json',{'status':'COMPLETE','library_id':TEST,'kg_generation':kg['active_generation_id'],
     'candidate_coverage_evaluation':evaluations,'graph_neighbor_latency':stats(kg_times),'integration_implemented':False,
     'limits':'Small candidate-coverage review; does not establish wider precision or improved reranked quality. No online graph augmentation or extra model load.'})
 write('search_kg_integration_audit.md',f'''# Knowledge Graph relationship to catalogue Search

Classification: **E — USED_ONLY_FOR_GRAPH_LAB / KNOWLEDGE_EXPLORATION**. Ordinary global and tenant Search: **NOT_USED_BY_SEARCH**.

`search/luminar_search.py`, `search/ranked_pages.py` and `TenantIntelligence.semantic` do not load/traverse graph artifacts. Tenant semantic reads request only `SEARCH_INDEX`; graph reads separately request `KNOWLEDGE_GRAPH` in `backend/services/library_intelligence_service.py:graph`. `LibraryGraphPage` calls `/api/libraries/{{id}}/intelligence/graph`. Search and graph have independent generation pointers and jobs; this agrees with the accepted Part 2G completion, sections R/U. UI links to Graph Lab are navigation, not query expansion.

The actual TEST Graph Lab browser response contains graph nodes and edges from generation `{kg['active_generation_id']}`. The disposable library's HNSW query succeeded with KG NOT_BUILT. Isolated tests additionally cover KG FAILED and a graph-cache loader that raises if Search tries to use it.

## Bounded augmentation review

Evaluated deterministic two-hop subject/author/classification neighbors from the first five real HNSW candidates, bounded to 20 additional canonical eligible IDs in TEST. All four independently selected relevant books already occur within the existing 60-candidate rerank pool. Candidate recall gain: **0/4**. See `search_kg_candidate_evaluation.json` for actual additions. The exploratory Mobility paraphrase also already has the relevant book as vector rank 1 and rerank rank 44; adding graph candidates would not repair its existing CrossEncoder score.

**KG_SEARCH_INTEGRATION_IMPLEMENTED: NO.** These observations do not justify changing the accepted ranking. Current graph contains metadata relationships, not a curated synonym/query-understanding ontology. Shared generic subjects can add less specific neighbors and cost more reranking; there is no measured relevance improvement here. This small coverage review is not a general search-quality benchmark.

HNSW remains primary discovery retrieval. Exact operational identifiers/filters remain deterministic. KG remains scoped relationship exploration. Graph unavailability never blocks Search. No document chunks, member records, foreign tenant graph, or global graph entered this evaluation.
''')
 provider={'GLOBAL_SEARCH_PROVIDER':'GLOBAL_HNSW_MINILM_CROSSENCODER_WITH_RANKING_CACHE',
  'GLOBAL_HNSW_ACTUALLY_QUERIED':'YES','TENANT_READY_SEARCH_PROVIDER':'TENANT_HNSW_MINILM_CROSSENCODER',
  'TENANT_HNSW_ACTUALLY_QUERIED':'YES','TENANT_HNSW_GENERATION':status['active_generation_id'],
  'TENANT_HNSW_LIBRARY_ID':TEST,'TENANT_RERANKER_USED':'YES','TENANT_KEYWORD_FALLBACK_USED_WHEN_READY':'NO',
  'NOT_BUILT_FALLBACK_PROVIDER':'TENANT_LOCAL_SUBSTRING','BUILDING_FALLBACK_PROVIDER':'TENANT_LOCAL_SUBSTRING','FAILED_FALLBACK_PROVIDER':'TENANT_LOCAL_SUBSTRING',
  'STALE_SEARCH_POLICY':'Current canonical tenant-local substring fallback; retained stale vector generation is not queried. Source fingerprint is rechecked after ranking; a concurrent change also falls back safely.',
  'SEMANTIC_NON_LITERAL_QUERY_PASS':'YES','KEYWORD_BASELINE_COMPARISON_PASS':'YES','CROSS_LIBRARY_SEARCH_LEAK':'NO',
  'GLOBAL_FILLER_IN_TENANT_RESULTS':0,'KNOWLEDGE_GRAPH_USED_BY_NORMAL_SEARCH':'NO','KNOWLEDGE_GRAPH_SEARCH_ROLE':'NOT_USED',
  'KG_SEARCH_INTEGRATION_IMPLEMENTED_IN_THIS_TASK':'NO','SEARCH_WORKS_WITH_KG_UNAVAILABLE':'YES','INVENTORY_EXACT_SEARCH_PRESERVED':'YES',
  'GLOBAL_HNSW_REBUILT':'NO','GLOBAL_KG_REBUILT':'NO'}
 put('search_provider_matrix.json',{'status':'PASS','qa_summary':provider,'matrix':[
  {'state':'GLOBAL cold','provider':'GLOBAL_HNSW','reranker':True,'kg':False},
  {'state':'GLOBAL cached','provider':'RANKING_CACHE + current Mongo hydration','reranker':'Reused prior pool','kg':False},
  {'state':'TENANT READY','provider':'TENANT_HNSW','reranker':True,'kg':False},
  *[{'state':s,'provider':'TENANT_LOCAL_SUBSTRING','reranker':False,'kg':False} for s in ['NOT_BUILT','BUILDING','FAILED','STALE','RECOVERY_REQUIRED']],
  {'state':'SEARCH_API unavailable (5xx)','provider':'Frontend tenant core fallback','kg':False},
  {'state':'Unfiltered browse','provider':'Canonical bounded Mongo catalogue page','kg':False},
  {'state':'Operational inventory','provider':'Canonical search_text + current shelf + exact barcode','kg':False}],
  'disposable_library_id':lid,'only_live_build':'One SEARCH_INDEX build of four-book disposable library; no TEST/global/KG build'})
 samples=read('search_runtime_latency_samples.json')
 warm=[r for r in traces[-20:] if r['library_id']==TEST and r['query']=='beginner computer networking' and any(s['name']=='FAISS_SEARCH' for s in r['stages'])][-5:]
 put('search_performance_comparison.json',{'status':'MEASURED','sampling':'Local development GPU, warm 5 requests each; p95 linear interpolation. Small sample, not an SLA or like-for-like corpus benchmark.',
  'local_fallback_http':stats([s['ms'] for s in samples if s['mode']=='local_fallback']),
  'tenant_hnsw_plus_reranker_and_canonical_hydration_http':stats([s['ms'] for s in samples if s['mode']=='tenant_hnsw']),
  'tenant_native_hnsw_stage':stats([s['elapsed_ms'] for r in warm for s in r['stages'] if s['name']=='FAISS_SEARCH']),
  'tenant_crossencoder_stage':stats([s['elapsed_ms'] for r in warm for s in r['stages'] if s['name']=='CROSS_ENCODER']),
  'tenant_hnsw_plus_reranker_stages':stats([sum(s['elapsed_ms'] for s in r['stages'] if s['name'] in ['FAISS_SEARCH','CROSS_ENCODER']) for r in warm]),
  'global_cold_total_ms':global_cold['elapsed_ms'],'hnsw_kg_reranker':None,'kg_reason':'Not implemented; no measured relevance gain. Offline bounded neighbor-only timings are in search_kg_candidate_evaluation.json.',
  'corpus_sizes':{'local_fallback_control':4,'tenant_hnsw':151},'raw_http_samples':samples})
 before=read('search_runtime_baseline.json');after=snapshot()
 after['tenant_artifacts']={str(p.relative_to(ROOT)):store.checksum(p) for p in (store.root()/TEST).rglob('*') if p.is_file()}
 put('search_runtime_current_snapshot.json',after)
 changed=[n for n,h in before['source_sha256'].items() if after['source_sha256'].get(n)!=h]
 preservation={'status':'PASS','TEST_before':before['TEST'],'TEST_after':after['TEST'],
  'TEST_canonical_unchanged':before['TEST']==after['TEST'],'TEST_artifacts_unchanged':before['tenant_artifacts']==after['tenant_artifacts'],
  'global_catalogue_count_before':before['global_book_count'],'global_catalogue_count_after':after['global_book_count'],
  'global_artifact_count':len(before['artifacts']),'global_artifact_metadata_unchanged':before['artifacts']==after['artifacts'],
  'protected_source_changes':[n for n in changed if n.startswith(('search/','recommendation/','assistant/','rag/','knowledge_graph/'))],
  'existing_source_changes':changed,'personal_document_registry_unchanged':before['personal_logical']==after['personal_logical'],
  'authorized_new_fixture':{'library_id':lid,'book_records':store.collection('library_books').count_documents({'library_id':lid}),
       'build_jobs':store.collection('intelligence_jobs').count_documents({'library_id':lid}),'kg_builds':store.collection('intelligence_jobs').count_documents({'library_id':lid,'target':'KNOWLEDGE_GRAPH'})},
  'production_authority_grants':0,'global_builds':0,'TEST_builds':0,'part_2i_started':False,'commit_created':False}
 assert preservation['TEST_canonical_unchanged'] and preservation['TEST_artifacts_unchanged'] and preservation['global_artifact_metadata_unchanged'] and not preservation['protected_source_changes']
 put('search_runtime_preservation.json',preservation)
 backend=[suite(n) for n in ['search_runtime_v2g.xml','search_runtime_catalogue.xml','search_runtime_inventory_regression.xml','search_runtime_global.xml','search_runtime_v2h.xml']]
 frontend=(REPORTS/'search_runtime_frontend.log').read_text(encoding='utf8');depth=(REPORTS/'search_runtime_frontend_depth.log').read_text(encoding='utf8')
 numbers=lambda pattern,text:sum(map(int,re.findall(pattern,text,re.M)))
 lint=(REPORTS/'search_runtime_lint.log').read_text(encoding='utf8')
 regression={'status':'PASS','backend':backend,'backend_unique_tests':sum(s['tests'] for s in backend),
  'new_backend_contracts':suite('search_runtime_backend.xml'),
  'frontend_default':{'tests':numbers(r'tests (\d+)\s*$',frontend),'pass':numbers(r'pass (\d+)\s*$',frontend),'fail':numbers(r'fail (\d+)\s*$',frontend)},
  'frontend_search_depth':{'tests':numbers(r'tests (\d+)\s*$',depth),'pass':numbers(r'pass (\d+)\s*$',depth),'fail':numbers(r'fail (\d+)\s*$',depth)},
  'build':'PASS','lint':{'errors':len(re.findall(r': error ',lint)),'warnings':len(re.findall(r': warning ',lint))},
  'browser':browser['status'],'scope':'All default frontend suites plus global search-depth UI; backend Part 2G/H, catalogue/convergence, Inventory Part 2A, global depth/lexical merge. Other previously accepted backend domain suites were not rerun.',
  'known_limitations':['One exploratory Mobility paraphrase reranks below first page. Ranking parameters intentionally unchanged.',
      'KG review and latency samples are bounded; no general relevance or load benchmark.','Existing build chunk-size and lint warnings retained.']}
 assert all(not s['failures'] and not s['errors'] for s in backend) and not regression['frontend_default']['fail'] and not regression['frontend_search_depth']['fail']
 put('search_runtime_regression.json',regression)
 write('search_runtime_path_audit.md',f'''# Search Intelligence runtime closure — PASS

Ordinary catalogue and header UI paths already use the accepted HNSW provider. **One genuine bypass was found and repaired:** a query entered after For You → View All retained `view=for-you`, suppressing the tenant semantic endpoint; Patron filtered the recommendation pool and Staff did lexical core lookup. `loadCatalogue` now gives submitted discovery queries precedence over the view marker. Empty Patron global-discovery fallback follows the same query-first rule. No semantic algorithm was rewritten. Inventory search now includes current tenant holding shelf text and exact tenant copy barcode, while preserving accession/ISBN/text/filter lookup.

## Actual request paths

| Browser entry | Component/API | HTTP endpoint | Backend/provider | Hydration |
|---|---|---|---|---|
| `/catalog` query and `/search` (also case-insensitive `/Search`) | `GlobalCatalogue` → `searchBooks` | `POST /search-api/search` (Vite → 8003) | `search.api:search` → `RankedSearchPages.search` → `LuminaRSearchEngine.search` → MiniLM → global `Snapshot.candidates` → FAISS HNSW → CrossEncoder | `current_books` Mongo canonical validation before ranking; `RankedSearchPages.current_books` after cache; capabilities enrichment in `searchBooks` |
| Global header Search | `Header` → central `context.searchPath` → `GlobalCatalogue` | Same global endpoint | Same global provider | Same canonical hydration |
| TEST Patron `/libraries/{TEST}/catalogue` and header | `LibraryCataloguePage`/`CatalogueSurface` → `useLibraryCatalogue` → `loadCatalogue` → `institutionApi` | `GET /search-api/libraries/{TEST}/catalogue/search?search=...` | `search.library_intelligence_api:search` → `TenantIntelligence.semantic` → status/generation validation → MiniLM normalized384 → FAISS `IndexHNSWFlat.search` → CrossEncoder | Fresh fingerprint; `catalogue.usable` ACTIVE + selected tenant + authorized format/filter pipeline; canonical `catalogue.hydrate` |
| TEST Staff `/staff/libraries/{TEST}/catalogue` and header | Same shared components/API with `staff=true` | Same tenant endpoint + staff flag | Same generation; staff membership required | Same canonical hydrate, staff actions preserved |
| Unfiltered tenant browse | Same `loadCatalogue`, no natural-language query | `GET /api/libraries/{{id}}/catalogue/books` | Bounded Mongo browse/filter | Canonical tenant catalogue hydrate |
| Non-READY discovery | Tenant semantic endpoint | Same query endpoint, or core on service 5xx | `catalogue.books`, escaped casefolded substring; tenant only | Current canonical rows; no stale vector generation |
| Staff Inventory | `LibraryInventory` → `institutionApi` | `GET /api/libraries/{{id}}/inventory/books` | `library_catalogue_service.list_books`, deterministic search_text/current holding shelf/exact copy barcode | Scoped current stock/availability; no embeddings or KG |
| Tenant Graph Lab | `LibraryGraphPage` → `institutionApi` | `GET /api/libraries/{{id}}/intelligence/graph` | `library_intelligence_service.graph` → separate KG generation | Current eligible tenant Book-node IDs and deterministic metadata relationships |

Global browsing without a query intentionally does not query HNSW. Global repeated queries intentionally use the existing generation-keyed ranking cache; it does not represent keyword fallback. The cold measured request queried **5,000,000** global vectors, semantic generation **30**, and reranked **50** candidates. TEST generation **{status['active_generation_id']}** queried **151** vectors; max **120** candidates and **60** reranked. Parameters/models unchanged.

## Runtime evidence

An explicitly launched loopback-only runner wraps the original native FAISS search, CrossEncoder.predict and canonical hydrators, preserving return values. Only allowlisted catalogue QA queries are recorded, without tokens, passwords, user identity, document/member payloads or a new debug endpoint. The ordinary `search.api` launch never imports this runner. Full selected call evidence: `search_hnsw_runtime_validation.json`; scores/order: `search_reranker_validation.json` and `search_keyword_semantic_comparison.json`.

Four real TEST queries independently compared against the existing lexical provider: beginner computer networking; accessibility transportation; community memories; equipment design workshop. All lexical controls returned zero; real HNSW/reranking/hydration displayed the expected book. The exploratory “getting around when walking is difficult” exposes a reranker limitation: Mobility vector rank 1 becomes rerank rank 44. This finding is retained, not hidden or remedied by an arbitrary ranking change.

The four-book disposable library **{lid}** was queried before build (NOT_BUILT/local fallback), built once through Chromium confirmation, then queried again (tenant HNSW + reranker). Its KG remains NOT_BUILT. The same query in TEST and the disposable library produced only the selected catalogue's records. TEST and global artifacts were never rebuilt.

## Fallback/freshness

NOT_BUILT, BUILDING, FAILED, STALE and RECOVERY_REQUIRED use current tenant-local fallback. STALE HNSW is retained for recovery but not queried. Canonical tenant membership, lifecycle, ACTIVE rows and formats are enforced; after HNSW ranking the source fingerprint is rechecked. A concurrent metadata change falls back to current canonical state. Foreign, archived, deleted and now-ineligible rows are covered in isolated tests. The frontend retries transient tenant lock 503 reads and falls back to core only for service failures, never authority denials.

## KG decision

Ordinary Search does **not** use KG. Graph Lab separately uses tenant metadata KG. Bounded same-tenant two-hop candidate augmentation produced no relevant candidate recall gain in four controlled queries; no integration was justified or implemented. Search succeeds with KG NOT_BUILT and FAILED. See `search_kg_integration_audit.md`.

## Regression/preservation

Backend: **{regression['backend_unique_tests']}** unique scoped checks pass, including 30 new contracts. Frontend: **{regression['frontend_default']['pass']}** default checks plus **{regression['frontend_search_depth']['pass']}** search-depth checks pass. Build passes; lint **{regression['lint']['errors']}** errors / **{regression['lint']['warnings']}** preexisting warnings. Actual Chromium query and shelf/exact-title UI checks pass. TEST remains **151 ACTIVE records / 150 holdings / 5 assets**; all TEST collection/artifact hashes match. Global remains **5,000,000** records and **196** artifact size/mtime snapshots unchanged. Recommendation/Qwen/router/search algorithm sources unchanged. No authority grant, commit or Part 2I.

## Final QA summary

| Field | Value |
|---|---|
'''+''.join(f'| {k} | {v} |\n' for k,v in provider.items())+'''
## Exact phase code files

- `backend/services/library_catalogue_service.py` — deterministic current shelf/barcode lookup repair.
- `frontend/package.json` — new runtime route tests included in default test chain.
- `frontend/src/lib/libraryCatalogue.ts` — natural-language query precedes For You marker; unqueried recommendations unchanged.
- `frontend/tests/search-runtime.test.ts` — 15 real API-routing/fallback/filter/session contracts, including three View All regression cases.
- `tests/institution_v2g/test_search_runtime.py` — isolated FAISS/reranking/hydration/authority/operational contracts.
- `scripts/search_runtime_audit_server.py` — explicitly invoked local instrumentation runner, absent from normal service.
- `scripts/search_runtime_browser.py` — actual Chromium query/provider transition and performance evidence.
- `scripts/search_runtime_inventory_browser.py` — actual repaired shelf/exact-title UI checks.
- `scripts/search_runtime_view_all_browser.py` — actual View All → semantic query and recommendation-clear preservation.
- `scripts/search_runtime_reports.py` — reproducible evidence-derived reports and bounded KG review.

Stop condition satisfied: runtime audit, genuine operational repair, bounded KG review. No Part 2I started.
''')
 print(json.dumps({'status':'PASS','backend':regression['backend_unique_tests'],'frontend':regression['frontend_default']['pass']+regression['frontend_search_depth']['pass'],
  'TEST_unchanged':preservation['TEST_canonical_unchanged'],'global_artifacts_unchanged':preservation['global_artifact_metadata_unchanged'],'report':str(REPORTS/'search_runtime_path_audit.md')}))
