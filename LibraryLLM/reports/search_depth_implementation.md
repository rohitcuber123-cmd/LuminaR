# Search / Recommendation depth implementation

Status: PARTIAL solely because one existing BookRAG regression still fails; Search/recommendation acceptance checks pass. No KG4, broad mode, model replacement, index rebuild or recommendation weight changes.

## Original architecture and bottleneck

Pre-edit audit and source hashes were captured in search_depth_audit.md and search_depth_baseline/. SearchPage -> searchBooks -> authenticated POST /search -> normalized384D MiniLM -> immutable HNSW base/delta -> Mongo-valid candidate pool -> existing L6 CrossEncoder -> existing author-intent priority / optional lexical tier -> final hydration/availability -> API slice. Recommender -> existing user/seed queries -> Search50 -> existing exclusions, weighted scoring and greedy diversity -> API slice. Assistant has an existing retained result context and multi-seed RRF.

There was no active10-result Search truncation: API top_k50 already returned50. The unused FINAL_TOP_K10 did nothing. SearchPage and ForYou requested12 and lacked offset continuation; ForYou's refresh repeated the first list. Personalized assistant SHOW_MORE progressively recomputed prefixes. The recommendation candidate-depth issue suspected in the request did not reproduce; the exact missing continuation locations were frontend/src/pages/SearchPage.tsx, frontend/src/components/ForYou.tsx, search/api.py and recommendation/api.py.

## Caps and depths

| Location | Before | After | Meaning |
|---|---|---|---|
| search/api.py SearchRequest.top_k, search/luminar_search.py search default | 10 | 10 | API output default; maximum50, no10 truncation |
| search/luminar_search.py FINAL_TOP_K | 10 | removed unused constant | unused; not bottleneck |
| frontend/src/lib/api.ts searchBooks default | 10 | 10 | UI/API output default |
| frontend/src/pages/SearchPage.tsx | 12 | 10 | visible page size; new offset continuation |
| recommendation/api.py GET and seeded POST | 10 | 10 | default page output; max50 |
| frontend/src/components/ForYou.tsx RECOMMENDATION_LIMIT | 12 | 10 | visible page size; new continuation |
| assistant/orchestrator.py DEFAULT_PAGE_SIZE; assistant/state.py; assistant/schemas.py requested_result_count | 10 | 10 | assistant display default; schema maximum20 |
| recommendation/recommendation_service.py CANDIDATE_COUNT | 50 | 50 | internal Search candidate request |
| assistant/orchestrator.py result_page Search | 50 | 50 | retained Search pool |
| assistant/orchestrator.py personalized continuation | offset+page_size+1, up to50 | one request50 then retained IDs | stable pool for SHOW_MORE |
| assistant/orchestrator.py seed fusion | 50 per seed; fused cap200 | unchanged | existing RRF, k60; no new algorithm |
| recommendation/recommendation_service.py profile query limit10 | 10 | 10 | interest text inputs; not result depth |
| search/api.py history and recommendation/api.py feedback | 50 default,100/200 max | unchanged | history/feedback records; not result depth |

Semantic overfetch previously max(50, top_k*2), retries up to1000 after invalid/missing Mongo rows; CE keeps50 viable candidates at supported depths. New public paging ranks the same fixed50 pool (initial100 semantic fetch), then returns10 by default. Recommendation calls already requested50 before, and still request50. The baseline finance10/20/50 requests all reranked50; returned10/20/50. Named SEMANTIC_MIN_VALID_CANDIDATES, CROSSENCODER_RERANK_DEPTH, SEARCH_MAX_RETURN_RESULTS, SEARCH_RANKED_POOL_SIZE, SEARCH_DISPLAY_PAGE_SIZE separate the four meanings. No unbounded candidate expansion was added.

## Contracts

POST /search body {query, limit:10, offset:10, library_id, available_at_library, save_history:false}. Legacy top_k remains accepted; explicit limit wins. Limit1–50, offset>=0, offset+limit<=50; invalid bounds400 and unauthenticated401. Existing response fields remain; offset, limit, returned, has_more, next_offset, total_ranked_candidates and rank are additive. total_ranked_candidates is the current surviving bounded pool size, never the total matching catalogue. Save history only for offset0. Library filtering requires library_id.

GET /recommendations?limit=10&offset=10 and POST /recommendations/from-book {work_id,limit:10,offset:10} use the same bounds. Mode and seed IDs stay in the response. The existing assistant owns multi-seed handling; no duplicate multi-seed API or new fusion algorithm.

Cache: process-local LRU,128 entries,180-second TTL, RLock coalesces a miss. Search key=trimmed query/library/availability filter/semantic snapshot version+generation/optional lexical availability+versions. Recommendation key=authenticated user+session/seed/published semantic index version. Cache only ordered identities/scores and diagnostic timing/counts, no JWT or book metadata. Every page reads Mongo metadata/availability; recommendations also read current active issue/reservation exclusions. Semantic generation changes invalidate; optional lexical unavailability changes invalidate and retains existing semantic fallback. Search retries a generation race twice, then errors rather than mislabeling results. Scoring/availability components remain a ranking snapshot while fresh facts are displayed.

## UI and assistant

Search starts1–10; Next Results replaces cards with11–20 and onward, Previous restores earlier pages. URL retains q/library/available/offset, query/filter changes resetoffset0. Local loading/error states, actual rank-range labels, first-page Previous disabled, final Next disabled. A failed request disables Next and permits Previous recovery. No concatenation, random reshuffle, forced route reload or Qwen calls.

ForYou starts10; Next Recommendations replaces the carousel with the next slice, preserves personalized mode and backend profile, Previous restores the initial slice. Account change resets offset. Removed the repeating five-minute prefix refresh. Popular fallback remains for cold/unauthenticated initial view with no fake continuation. Continuation errors clear old cards and offer Previous; stale cards cannot masquerade as the next rank range.

Assistant Search remains one request50 with retained IDs. Personalized recommendation now also requests50 once and retains IDs. Existing single/multi-seed RRF retains all seeds, exclusions, filters, page size, offset and delivered IDs; fusion k60/max200 unchanged. Explicit SHOW_MORE is deterministic and calls no Qwen. Facts/availability are rehydrated on every continuation; filter changes create the existing updated result context.

## Actual catalogue evaluation

Eight queries: manage money for finances; beginner artificial intelligence; gothic horror; database systems; time travel science fiction; machine learning; personal finance; investing for beginners. All eight Top10 sequences unchanged, including all eight original top_k=10 engine requests replayed from the exact pre-edit source snapshot against the unchanged catalogue/index. The original_top10_replay report confirms10/10 overlap and identical order for every query. Personalized and single-seed original APIlimit10 sequences unchanged. Finance Top50 unchanged. Only AI ranks31/32 and33/34 swap among equal CE-score pairs after explicit (-CE,-semantic,work_id) tie ordering. Models and embeddings unchanged.

The finance Top50 dump and title/author/subject/CE/semantic scores are in search_manage_money_ranking.json. Lower results include budgeting, saving, credit/debt, retirement/planning, student finances and literacy. Distinct authors14->54 and subjects28->68 across10->50; mean subject Jaccard distance0.8374->0.7857 and title repetition0.5902->0.6439: the broader pool still repeats money terms and is not uniformly more diverse by every metric. These metrics are metadata proxies without human relevance labels. Pagination exposes useful broader existing choices; no Broad/MMR mode was implemented. Eight-query diagnostics are in search_depth_regression.json.

Search warm uncached page2: embedding12.49ms, HNSW2.94ms, Mongo candidate3.81ms, CE63.12ms, page hydration3.61ms, total93.17ms (HTTP123.35ms). Cached repeat: total3.80ms, hydration3.76ms, HTTP11.98ms; embedding/HNSW/CE0. Baseline warm depth20/50 totals78.79/117.01ms with CE57.78/54.54ms. Startup totals1123.27ms before /971.82ms after include independent GPU initialization and are not a controlled speedup. See search_pagination_performance.json for all stages, Top10/20/50, page2 miss/repeat and API rejection checks.

Personalized recommendation warm miss85.31ms/server94.32ms/HTTP; cached page2 3.63/11.96ms. Single seed miss166.09/195.64ms; cached page2 5.89/25.73ms. Existing50 request returned50 personalized and49 seeded after seed exclusion. Real paging0/10/20/30/40 has no duplicates, final has_morefalse and Previous matches. Actual instrumentation of the unchanged recommendation function confirms personalized50requested/50received, single-seed50/50, and both multi-seed Search calls50/50, with49post-exclusion results per seed. A real HTTP AssistantTools/orchestrator continuation test verifies personalized, single-seed and multi-seed modes, original seeds despite changed client tray, zero overlap and zero Qwen calls; SHOW_MORE adds no recommendation calls. recommendation_candidate_depth.md and recommendation_pagination.json include counts, modes, seeds, IDs and before/after timings.

Live browser verification used a disposable verified account on isolated origin5174 to preserve the user's5173 login: Search1–10 ->11–20, zero overlap, Previous restored; ForYou1–10 ->11–20, zero overlap, Previous restored. Screenshots: search_depth_browser_search.png and search_depth_browser_recommendations.png. Test account/history/temporary credentials are removed after evaluation.

## Validation

- Relevant backend regression run:231passed,10warnings (search_depth_regression_tests.log).
- Final depth/assistant/semantic/lexical/BookRAG run:300passed,1existing failure,1warning (search_depth_final_regression.log). The earlier optional lexical cache fallback failure was fixed and its isolated real-API test now passes. Assistant old prefix-lookahead test now asserts one retained50 request and no Qwen.
- The remaining failure is tests/test_rag_query_types.py::test_overview_rule_never_accepts_added_premises[What are the major themes of this book?]. The same failure is recorded in pre-existing reports/dynamic_existing_tests.log and reports/know_more_cache_book_kg_tests.log; BookRAG source/test were not edited by this pass. Do not silently count the suite as fully passing.
- Frontend final paging+assistant+Part3+KG+document-cache checks:129passed. Standard npm test:31 read-now/routing plus81 assistant tests passed; see search_depth_frontend_final.log and search_depth_standard_frontend_tests.log.
- Production TypeScript/Vite build passes (search_depth_build.log). Lint exits0 with19existing warnings (search_depth_lint.log).
- Real HTTP auth/bounds checks pass; unit tests cover20/50 output, CEdepth50, semantic headroom, disjoint pages, deterministic ties, short-pool exhaustion, query/generation/TTL invalidation, current metadata/availability/exclusions, recommendation modes/seeds and error recovery.

## Start commands

Run each service command in a separate terminal, from D:\SDC\LibraryLLM:

```powershell
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --workers 1
.\.venv\Scripts\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003 --workers 1
.\.venv\Scripts\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004 --workers 1
.\.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1
Set-Location D:\SDC\LibraryLLM\frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

## Limits and changed files

A50-result ranked pool bounds navigation and cost; availability filters, missing metadata or recommendation exclusions can leave fewer results. A catalogue deletion/current-exclusion change can compact ranks between pages; TTL/profile changes or an index publication can recompute ordering. No opaque durable cursor is promised across those mutations. Cache is per worker, not shared; cold workers recompute. Broadness observations are catalogue metadata, not judged book-content relevance. The pre-existing index health is STALE (generation30,5million vectors, baseline_verifiedfalse); not repaired/rebuilt in this task. Startup/client capability requests can add wall time beyond measured Search server time.

Changed/new application files: backend/services/ranked_result_cache.py; search/ranked_pages.py; search/api.py; search/luminar_search.py; recommendation/ranked_pages.py; recommendation/api.py; assistant/orchestrator.py; frontend/src/lib/api.ts; frontend/src/lib/searchPaging.ts; frontend/src/pages/SearchPage.tsx; frontend/src/components/ForYou.tsx. Test/script files: tests/test_search_depth.py; tests/test_assistant_backend.py; tests/test_assistant_part3_repair.py; frontend/tests/search-depth.test.tsx; scripts/benchmark_search_depth.py; scripts/trace_search_depth.py; scripts/replay_search_depth_baseline.py. .gitignore excludes disposable credential file. recommendation/recommendation_service.py and assistant/tools.py are byte-identical to audit snapshots. Repository has no .git checkout; source snapshots/hashes supply the baseline.
