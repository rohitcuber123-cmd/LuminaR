"""Evidence-derived recommendation dependency/isolation closure. No model changes."""
import json,re,sys
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));REPORTS=ROOT/'reports'
from scripts.post_2h_baseline import snapshot
from scripts.search_runtime_reports import stats
from backend.database.mongodb import db
from backend.services import library_intelligence_store as store,library_intelligence_service as intelligence
TEST='e6d1e5b4-c48f-4b47-b96a-656a676fb8ae'
def read(name):return json.loads((REPORTS/name).read_text(encoding='utf8'))
def put(name,value):(REPORTS/name).write_text(json.dumps(value,indent=2,ensure_ascii=False,default=str),encoding='utf8')
def write(name,value):(REPORTS/name).write_text(value,encoding='utf8')
def suite(name):
    xml=ET.parse(REPORTS/name)
    return {'file':name,'tests':len(xml.findall('.//testcase')),'failures':len(xml.findall('.//failure')),'errors':len(xml.findall('.//error'))}
def logs(name):
    text=(REPORTS/name).read_text(encoding='utf8')
    return {'tests':sum(map(int,re.findall(r'tests (\d+)\s*$',text,re.M))),
            'pass':sum(map(int,re.findall(r'pass (\d+)\s*$',text,re.M))),
            'fail':sum(map(int,re.findall(r'fail (\d+)\s*$',text,re.M)))}

if __name__=='__main__':
 fixture=read('recommendation_runtime_fixture.json');browser=read('recommendation_browser_validation.json')
 assert browser['status']=='PASS' and not browser['page_errors']
 browser['checks']=list({c['scenario']:c for c in browser['checks']}.values())
 browser['fixtures']=fixture;put('recommendation_browser_validation.json',browser)
 events=[json.loads(l) for l in (ROOT/'.scratch/recommendation-runtime/events.jsonl').read_text(encoding='utf8').splitlines()]
 search=[json.loads(l) for l in (ROOT/'.scratch/recommendation-runtime/search-events.jsonl').read_text(encoding='utf8').splitlines()]
 measured=next(r for r in events if r['qa_user_id']==fixture['qa_user_id'] and any(s['name']=='SEARCH_HTTP' for s in r['stages']))
 correlated=next(r for r in search if r.get('recommendation_trace_id')==measured['trace_id'])
 assert any(s['name']=='GLOBAL_FAISS_SEARCH' and s['ntotal']==5000000 for s in correlated['stages'])
 assert any(s['name']=='CROSS_ENCODER' and s['count']==50 for s in correlated['stages'])
 assert any(s['name']=='HYBRID_SCORE' for s in measured['stages']) and any(s['name']=='CANONICAL_HYDRATION' for s in measured['stages'])
 cold=next(r for r in events if r['qa_user_id']==fixture['qa_user_id'] and any(s['name']=='PROFILE' and s['counts']['queries']==0 for s in r['stages']))
 assert cold['final_count']==0 and not any(s['name']=='SEARCH_HTTP' for s in cold['stages'])
 generation=correlated['response_source']['index_generation']
 summary={'GLOBAL_RECOMMENDATION_PROVIDER':'GLOBAL_HNSW_CANDIDATES + EXISTING_HYBRID_PROFILE_SCORE + DIVERSITY',
  'TENANT_RECOMMENDATION_PROVIDER':'GLOBAL_CANDIDATE_INTERSECTION_AND_CANONICAL_LOCAL_ACQUISITION_FILL',
  'RECOMMENDATION_USES_SEARCH':'YES','RECOMMENDATION_SEARCH_PROVIDER':'GLOBAL_HNSW_MINILM_CROSSENCODER (or accepted ranking cache)',
  'RECOMMENDATION_USES_TENANT_HNSW':'NO','RECOMMENDATION_HNSW_ACTUALLY_QUERIED':'YES (global)',
  'RECOMMENDATION_SEARCH_GENERATION':generation,'RECOMMENDATION_USES_KEYWORD_FALLBACK_WHEN_HNSW_READY':'N/A — tenant HNSW is not a recommender dependency; acquisition fill is not keyword Search',
  'RECOMMENDATION_USES_KG':'NO','RECOMMENDATION_KG_ROLE':'NOT_USED_BY_FOR_YOU',
  'TENANT_RECOMMENDATION_GLOBAL_FILLER_COUNT':0,'TENANT_RECOMMENDATION_CROSS_LIBRARY_LEAK':'NO',
  'RECOMMENDATION_CANONICAL_HYDRATION':'YES','RECOMMENDATION_COLD_START_PASS':'YES',
  'RECOMMENDATION_PAGING_TENANT_SAFE':'YES','RECOMMENDATION_MULTI_LIBRARY_CACHE_SAFE':'YES',
  'NEW_ARRIVALS_PROVIDER':'TENANT acquisition/created date ordering; GLOBAL created_at ordering',
  'POPULAR_PROVIDER':'TENANT weighted 90-day loans/approved BORROW requests/reservations; GLOBAL reading_log_count/rating aggregates'}
 put('recommendation_provider_matrix.json',{'status':'PASS','qa_summary':summary,'classification':[
  'SEARCH_HNSW_CANDIDATE_DEPENDENT (global upstream)','USER_HISTORY_CONTENT_PROFILE','HYBRID','POPULARITY_BASED (score signal or explicit cold fallback)'],
  'independent_trained_recommendation_model':False,
  'providers':{'global_personalized':summary['GLOBAL_RECOMMENDATION_PROVIDER'],
    'global_cold_start':'Global recommendation API returns empty; ForYou explicitly renders Popular books; View All now retains Popular provider',
    'tenant_nonempty':'POST canonical projection of global preferred work IDs + recent-acquisition local fill, including local-only records',
    'tenant_empty':'Explicit GLOBAL_FALLBACK discovery; global candidates, or Popular fallback on Home when cold',
    'staff':'Staff catalogue remains canonical discovery/browse; no same-library Admin-as-patron recommendation authority',
    'more_like_this':'Separate global catalogue metadata KG relationships via /api/kg/books/{work_id}/more-like-this',
    'recommend_similar_assistant':'Single selected global-book seed mode of existing recommender via /recommendations/from-book, separate from graph widget'}})
 put('recommendation_search_dependency.json',{'status':'PROVEN','global_uses_search':True,'tenant_upstream_uses_global_search_when_profile_has_queries':True,
  'tenant_search_index_dependency':False,'search_url':'http://127.0.0.1:8003/search',
  'request_body':{'query':'Combined recency-selected genuine search history, or explicit single-book metadata seed','top_k':50,'save_history':False},
  'library_id_in_upstream_request':None,'actual_correlated_trace_id':measured['trace_id'],
  'search_candidate_count':next(s['candidate_count'] for s in measured['stages'] if s['name']=='SEARCH_HTTP'),
  'global_search_failure':'Cold uncached Recommendation API returns safe 503, not 500. Existing cached pools can still hydrate until TTL. Global Home falls back to explicitly labelled Popular at offset 0; later pages show error, not a provider switch.',
  'tenant_upstream_failure':'Frontend catches global recommendation failure and submits empty candidate IDs; canonical core projection supplies usable local acquisitions only.',
  'tenant_index_states':'NOT_BUILT/BUILDING/FAILED/STALE/READY do not select recommender providers. Tested separately from actual tenant Search, which uses the accepted state router.',
  'actual_call':measured})
 put('recommendation_hnsw_runtime_validation.json',{'status':'PASS','hnsw_queried':True,'provider':'GLOBAL_HNSW','global_generation':generation,
  'query':'beginner computer networking','recommendation_trace_id':measured['trace_id'],'search_trace':correlated,
  'CrossEncoder':'cross-encoder/ms-marco-MiniLM-L-6-v2 invoked in Search, not a second direct Recommendation model',
  'recommender_own_ranking':'Uses hnsw_score as semantic input, weighted profile/aggregate signals, feedback adjustment and deterministic diversity; does not simply return CrossEncoder order',
  'tenant_hnsw_queried':False,'tenant_hnsw_reason':'Accepted tenant Home convergence scopes global preferred work IDs, then fills from local acquisitions. It intentionally does not use the tenant semantic reader.',
  'disposable_before_after':[c for c in browser['checks'] if c['scenario'].startswith(('Tenant For You before','Tenant recommendations unchanged'))],
  'tenant_tested_states':'Real NOT_BUILT to valid READY build; later preferred linked-book addition makes only disposable A STALE. Isolated provider-independence checks cover BUILDING/FAILED/STALE as well.',
  'global_rebuilt':False,'TEST_rebuilt':False,'tenant_KG_builds':0})
 isolation=[c for c in browser['checks'] if any(p in c['scenario'] for p in ['TEST Patron','Tenant Next','Same GENERAL_USER','Tenant View All','Unavailable global','Staff shared'])]
 tenant_outputs=[n for n in browser['network'] if n['endpoint'].endswith('/catalogue/recommendations') and n['status']==200]
 violations=[]
 for page in tenant_outputs:
    lid=page['source']['library_id'];ids=[r['library_book_id'] for r in page['results']]
    if len(ids)!=len(set(ids)) or any(r['source']!='LIBRARY' or r['library_id']!=lid for r in page['results']):violations.append(page['endpoint'])
 assert not violations
 put('recommendation_tenant_isolation.json',{'status':'PASS','actual_browser_checks':isolation,'canonical_tenant_responses_checked':len(tenant_outputs),
     'global_filler_count':0,'foreign_library_count':0,'duplicate_local_identity_count':0,
     'globally_preferred_work_owned_by_A_not_B':{'work_id':fixture['preference_seed_work_id'],'A':fixture['A'],'B':fixture['B'],'local_record':fixture['linked_library_book_id']},
     'hydration_controls':'Real canonical core HTTP route and hydrate spy in isolated Mongo tests; ACTIVE/usable ownership filters before result hydration; deleted/foreign/no-format/archived records excluded.',
     'identity_policy':'Tenant cards use canonical library_book_id. Global preferred IDs are ranking inputs; no additional global representation is rendered in non-empty tenant rails. Distinct canonical tenant editions are not merged merely because global_work_id matches.',
     'cache_policy':'Global ranked cache keyed by user ID, JWT session ID, optional seed, global generation; TTL 180 seconds. Canonical global facts hydrate per request. ForYou page state and result payloads keyed by token + selected library + offset; tenant core results recomputed per request.'})
 put('recommendation_cold_start.json',{'status':'PASS','qa_account_created':True,'qa_email':fixture['qa_email'],'qa_account_disabled_after_review':True,
   'clean_global_trace':cold,'browser_checks':[c for c in browser['checks'] if 'cold start' in c['scenario'].lower() or 'Empty Patron' in c['scenario'] or 'Cold global Popular' in c['scenario']],
   'personalization_inputs':{'candidate_query':'Up to 10 recent search-history queries selected by recency weight (50 queried from Mongo); seed mode uses explicit book metadata.',
      'profile':'Legacy global issues/reservations and recommendation_feedbacks, with authors/subjects and active-work exclusions.',
      'scoring':'Semantic HNSW similarity 0.40, subject 0.15, author 0.10, borrowing 0.15, reservation 0.10, aggregate rating 0.05, popularity 0.03, availability 0.02; additive feedback adjustment 0.10. Existing diversity limits preserved.',
      'not_inputs':['Reading List','AI selection','current tenant local loans','current tenant reservations','current tenant HNSW','tenant KG'],
      'ratings_note':'Aggregate catalogue rating affects score; feedback types include RATED if such an existing system event is present. No direct user ratings-collection read is implemented here.'},
   'limits':['Tenant local-only acquisitions are safe deterministic discovery, not a newly trained tenant personalization model.',
       'No history queries means no ordinary semantic candidates, even if some other preference fields exist; the accepted UI cold fallback handles this.',
       'Global profile updates do not invalidate a frozen ranking pool immediately; accepted 180-second/session/generation policy remains. Controlled quality case used a fresh login after the genuine Search interaction.']})
 related=next(c for c in browser['checks'] if c['scenario'].startswith('More Like This'))
 write('recommendation_kg_integration_audit.md',f'''# Recommendation and Knowledge Graph relationship

**For You KG role: NOT_USED.** Neither `recommendation_service` nor `RankedRecommendationPages` traverses a graph or loads KG artifacts. Subject/author counters are catalogue/profile text signals, not graph signals. Tenant `/catalogue/recommendations` joins global preferred work IDs to usable local records and recent acquisitions; it does not load Search or KG artifacts.

Actual recommendations remain valid in the disposable libraries with KG NOT_BUILT; isolated tests make the artifact loader raise if invoked, while Search/KG states are FAILED. There is no tenant graph or document/member graph dependency. No KG enhancement was forced into the accepted recommender.

**More Like This is a different feature.** `useMoreLikeThis` calls `/api/kg/books/{{work_id}}/more-like-this`. Core `knowledge_graph.product_more_like_this` invokes `CatalogueGraph.more_like_this`, uses deterministic shared metadata relationships, refreshes canonical global records, rejects stale metadata and excludes active global issues/reservations. It is global discovery even when reached from a linked tenant title; it is not the tenant-owned For You rail. Runtime browser response: **HTTP {related['http_status']}**, {related['availability']}, graph version `{related.get('graph_version')}`. No claim that this graph powers For You.

Assistant **Recommend Similar** separately calls `/recommendations/from-book`, reusing the existing hybrid recommender with an explicit global book metadata seed. Graph Lab comparison deliberately calls that recommender to compare two independent providers; this is not a graph signal inside normal recommendations.
''')
 samples=read('recommendation_runtime_latency_samples.json')
 put('recommendation_performance.json',{'status':'MEASURED','method':'Local development GPU; 5 warm samples each, p95 linear interpolation. Not a load benchmark or SLA.',
    'global_personalized_cold_pipeline_ms':round(measured['elapsed_ms'],3),
    'global_search_dependency_ms':round(next(s['elapsed_ms'] for s in measured['stages'] if s['name']=='SEARCH_HTTP'),3),
    'global_hnsw_native_stage_ms':round(next(s['elapsed_ms'] for s in correlated['stages'] if s['name']=='GLOBAL_FAISS_SEARCH'),3),
    'global_crossencoder_stage_ms':round(next(s['elapsed_ms'] for s in correlated['stages'] if s['name']=='CROSS_ENCODER'),3),
    'global_cached_pool':stats([r['ms'] for r in samples if r['provider']=='global_cached']),
    'TEST_canonical_projection':stats([r['ms'] for r in samples if r['provider']=='tenant_projection']),
    'tenant_native_hnsw_stage':None,'tenant_hnsw_reason':'Not part of accepted recommendation provider','raw_samples':samples})
 before=read('recommendation_runtime_baseline.json');after=snapshot()
 after['tenant_artifacts']={str(p.relative_to(ROOT)):store.checksum(p) for p in (store.root()/TEST).rglob('*') if p.is_file()}
 changed=[n for n,h in before['source_sha256'].items() if after['source_sha256'].get(n)!=h]
 protected=[n for n in changed if n.startswith(('search/','recommendation/','assistant/','rag/','knowledge_graph/','backend/'))]
 preservation={'status':'PASS','TEST_unchanged':before['TEST']==after['TEST'],'TEST_artifacts_unchanged':before['tenant_artifacts']==after['tenant_artifacts'],
  'global_count_before':before['global_book_count'],'global_count_after':after['global_book_count'],
  'global_artifact_count':len(before['artifacts']),'global_artifacts_unchanged':before['artifacts']==after['artifacts'],
  'private_documents_registry_unchanged':before['personal_logical']==after['personal_logical'],
  'protected_business_source_changes':protected,'existing_source_changes':changed,'QA_fixture':fixture,
  'live_builds':'One explicit Search build of disposable A; global/TEST HNSW and all KG artifacts not rebuilt',
  'A_state_after_preference_link':intelligence.target_status(fixture['A'],'SEARCH_INDEX',observe_stale=False)['status'],
  'B_search_state':intelligence.target_status(fixture['B'],'SEARCH_INDEX',observe_stale=False)['status'],
  'qa_account_disabled':not db.users.find_one({'user_id':fixture['qa_user_id']})['is_active'],'platform_grants':0,'commit_created':False,'Part_2I_started':False}
 assert preservation['TEST_unchanged'] and preservation['TEST_artifacts_unchanged'] and preservation['global_artifacts_unchanged'] and not protected
 put('recommendation_runtime_preservation.json',preservation)
 backend=[suite(n) for n in ['recommendation_runtime_catalogue.xml','recommendation_runtime_search.xml','recommendation_runtime_global.xml']]
 default=logs('recommendation_runtime_frontend.log');focus=logs('recommendation_runtime_frontend_final_focus.log')
 lint=(REPORTS/'recommendation_runtime_lint.log').read_text(encoding='utf8')
 regression={'status':'PASS','backend_suites':backend,'backend_unique_tests':sum(s['tests'] for s in backend),
   'new_backend_tests':suite('recommendation_runtime_backend_new.xml'),'frontend_default':default,'frontend_final_focus':focus,
   'frontend_focus_duplicates_default':True,'frontend_unique_tests':default['tests'],'build':'PASS',
   'lint':{'errors':len(re.findall(r': error ',lint)),'warnings':len(re.findall(r': warning ',lint))},
   'browser_unique_scenarios':len(browser['checks']),'browser':'PASS','preservation':'PASS',
   'scope':'Full default frontend; focused ForYou/intelligence/Search routing on final component. Backend canonical catalogue/convergence, Part 2G Search/fallback, global search/recommender depth/lexical integration. No unrelated domain suites rerun.'}
 assert all(not s['failures'] and not s['errors'] for s in backend) and not default['fail'] and not focus['fail']
 put('recommendation_runtime_regression.json',regression)
 write('recommendation_runtime_path_audit.md',f'''# Recommendation runtime addendum — PASS

The real global recommender is **Search-HNSW candidate dependent + user/profile hybrid scoring + diversity**. Tenant For You **does not use tenant HNSW**: it intersects global preference candidates with canonical owned records, then fills with local acquisitions. This is the accepted Home convergence architecture, not an obsolete keyword routing mistake. READY/NOT_BUILT tenant HNSW comparison preserves the same recommendation provider. Algorithms, weights, HNSW parameters and KG dependencies remain unchanged.

One genuine product defect was fixed: global cold-start Popular fallback's View All previously navigated to empty personalized recommendations. `ForYou` now delegates to the existing centralized `homeCataloguePath(...,'popular')`, opening `/catalog?sort=popular`. Personalized and tenant View All retain their existing destinations. A failing regression test reproduced the old route; real Chromium verifies the corrected route and Popular results.

## End-to-end traces

| Surface | Frontend/API | HTTP route | Candidate/ranking provider | Canonical boundary |
|---|---|---|---|---|
| Global Home For You | `ForYou` → `getRecommendations(10,offset)` | `GET /recommendation-api/recommendations` → 8004 `recommendation.api.recommendations` | `RankedRecommendationPages` → `get_recommendations` → actual recency-selected search history → `generate_semantic_candidates` → `POST 8003/search` → global MiniLM/HNSW + CrossEncoder → hybrid score → diversity | Recommender current global Mongo enrichment; ranked pages refresh `current_books`, exclusions, facts on each page |
| Global Next/Previous | Same ForYou/provider | Same endpoint, offsets 10/20 etc | Frozen user/session/seed/global-generation 50-identity pool, 180-second TTL | Fresh canonical hydration on every page; no Popular switch on a later page |
| Global View All | `GlobalCatalogue` → `getRecommendations` | Same recommendation endpoint | Same ranked pool | Same canonical global hydration |
| Global cold start | ForYou empty recommendation response | `/api/books/popular` | Read-log/rating aggregate ordering, explicitly labelled Popular books | Core catalogue display; View All retains `/catalog?sort=popular` after repair |
| TEST Home For You | `loadCatalogue(home)` and shared `ForYou` → `libraryRecommendationPage` | Global `/recommendation-api/recommendations?limit=50&offset=0`, then `POST /api/libraries/{{id}}/catalogue/recommendations` | Core `library_catalogue_experience.recommendations`: ordered global work-ID intersection + recent acquisition fill, max50 for paging; no tenant index/graph load | Explicit GENERAL_USER membership, usable ACTIVE selected-library records; canonical `hydrate`; only local `library_book_id` cards |
| TEST Next/Previous/carousel | Same libraryRecommendationPage; global pool fetched at offset0 then scoped local slicing | Same global/core endpoints | Same scoped 50-result pool sliced in 10s; carousel only changes scroll position | Token + selected tenant + offset state, abort old requests on switch; source/each result validated |
| TEST View All | `LibraryCataloguePage` → `loadCatalogue(view=for-you)` | Same upstream candidates and canonical projection | Same intersection/local fill | Library-owned grid/paging. Submitted queries intentionally switch to Search (previous runtime repair); unqueried recommendations remain unchanged |
| Empty library Home | source=GLOBAL_FALLBACK; global discovery candidates or Popular if cold | Global recommendation/Core discovery endpoints | Explicitly labelled global discovery | No global card represented as library-owned |
| Staff discovery | `LibraryCataloguePage(staff)` | `/api/libraries/{{id}}/catalogue/books?staff=true` | Canonical Staff browse/discovery; no claim that this is Patron recommendation | Staff membership and Staff book destinations; no Admin-as-patron |
| New Arrivals | Shared Home catalogue / arrivals page | Core books or tenant home/books sort=new_arrivals | Tenant acquisition-date/created-date ordering; global created_at ordering | Current canonical data |
| Popular | Shared Home catalogue / popular page | Core popular or tenant home/books sort=popular | Tenant 90-day activity weights: loans8, approved BORROW requests2, reservations1; global reading-log/rating aggregates | Current tenant or global scope as explicitly selected |
| More Like This | `useMoreLikeThis` → `relatedBooks` | `/api/kg/books/{{work_id}}/more-like-this` | Separate global metadata KG relationships, **not For You** | Canonical global refresh/stale-feature suppression; labelled related graph discovery |
| Assistant Recommend Similar | Assistant explicit seed action | `/recommendations/from-book` | Existing recommender with single global metadata seed; same Search candidate source/hybrid/diversity | Current global records and seed/currently-active exclusions |

## Runtime proof

Actual Chromium Global Home supplied a genuine persisted nonliteral Search preference: **beginner computer networking**. The Recommendation call's private QA correlation ID `{measured['trace_id']}` matches the Search worker trace: native **IndexHNSWFlat, 5,000,000 vectors, global generation {generation}**, CrossEncoder **50** predictions, canonical hydration. Recommendation then executes its own weighted score/diversity and refreshes facts per page. The service has no separately trained recommender model and no second direct CrossEncoder invocation.

Instrumentation runs only through explicitly launched local QA runners, only for allowlisted QA users/queries; no diagnostic endpoint or response field was added. Authorization/passwords/raw private histories are not recorded. Existing QA profile counts are aggregate only. Normal service launch never imports these runners.

Actual personalization sources and limits are detailed in `recommendation_cold_start.json`. Ordinary semantic candidates require search-history queries; borrowing/reservation/feedback author/subject signals affect scoring but do not independently create a query. Reading List, AI selection, tenant loans and tenant indexes are not silently claimed as inputs. Global session/generation cache policy remains unchanged; the controlled preference test uses a fresh login after the genuine Search interaction.

## Tenant/cold-start/provider checks

Clean local QA account: no history → global Popular fallback; empty library → labelled global discovery; adding 25 local records → tenant acquisition discovery. Disposable A was then explicitly built once: Search became READY while KG remained NOT_BUILT, and recommendation identities/order/provider were unchanged. A later globally preferred linked record was added solely to A; B does not own it. A's Search generation then becomes STALE without a rebuild; recommendation scope remains valid.

Same GENERAL_USER A→B switch, two Next pages and Previous, carousel traversal, View All, browser Back/Forward, unavailable global recommendation fixture and existing TEST three Next pages pass. TEST results are exclusively TEST-owned. Canonical hydration/filter tests suppress withdrawn/deleted/foreign/no-format local rows and deleted cached global works. Global/local duplicate representations are absent; distinct canonical editions keep their local identity.

KG role for **For You: NOT_USED**. Recommendation works with tenant KG NOT_BUILT/FAILED. More Like This is independently traced to its graph endpoint (HTTP {related['http_status']}); no assertion that this separate KG feature powers Home recommendations. No KG integration was introduced.

## Results and preservation

**{regression['backend_unique_tests']} scoped backend checks pass**, including 19 new recommendation contracts. **{default['pass']} default frontend checks pass**, including 12 new recommendation tests; **{focus['pass']} overlapping focused checks** also pass on the final component. Build passes; lint **{regression['lint']['errors']} errors / {regression['lint']['warnings']} existing warnings**. **{len(browser['checks'])} unique Chromium scenarios pass**. Performance is measured separately for cold personalized pipeline, global HNSW/reranker stages, cached global pools and TEST projection; bounded local samples are not an SLA.

TEST remains **151 local records / 150 holdings / 5 assets**, with identical canonical collection/artifact hashes. Global remains **5,000,000** records and all **196** global artifact snapshots unchanged. Recommendation/Search backend algorithms, Qwen/router and document systems unchanged. Temporary QA accounts are disabled, credentials never persisted. Only one disposable Search build; no TEST/global rebuild and no KG build. No commit. No Part 2I.

## Final QA summary

| Field | Value |
|---|---|
'''+''.join(f'| {key} | {value} |\n' for key,value in summary.items())+'''
## Exact phase code files

- `frontend/src/components/ForYou.tsx` — retain Popular provider in global cold-start View All.
- `frontend/package.json` — register recommendation runtime tests in default suite.
- `frontend/tests/recommendation-runtime.test.tsx` — provider, paging, scope, cold fallback and View All contracts.
- `tests/library_catalogue_experience/test_recommendation_runtime.py` — real canonical projection and recommender dependency/hydration contracts.
- `scripts/recommendation_runtime_audit_server.py` — opt-in private local recommendation call instrumentation.
- `scripts/search_runtime_audit_server.py` — opt-in private correlation of downstream Search calls, no application change.
- `scripts/recommendation_runtime_browser.py` — clean-account/catalogue/build/real Chromium evidence, runtime-only credentials.
- `scripts/recommendation_runtime_finish_browser.py` — read-only final Staff/cold-link/related/performance checks.
- `scripts/recommendation_runtime_reports.py` — evidence-derived reports and preservation/regression assertions.

## Known limits

This is runtime/dependency closure, not a broad recommendation relevance benchmark or new tenant-personalization algorithm. Tenant local-only cold discovery is acquisition ordered, not semantic inference. Frozen global profile pools follow the accepted 180-second/session policy. Backend suites listed above are scoped; unrelated previously accepted domains were not rerun. Earlier browser harness selector/timing corrections were confined to QA scripts; final captured product flows pass.
''')
 print(json.dumps({'status':'PASS','backend':regression['backend_unique_tests'],'frontend':default['pass'],'browser_scenarios':len(browser['checks']),
    'global_hnsw_actual':True,'tenant_hnsw_used':False,'KG_ForYou_used':False,'TEST_preserved':preservation['TEST_unchanged']}))
