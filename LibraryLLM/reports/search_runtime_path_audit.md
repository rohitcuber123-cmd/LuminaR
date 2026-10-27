# Search Intelligence runtime closure — PASS

Ordinary catalogue and header UI paths already use the accepted HNSW provider. **One genuine bypass was found and repaired:** a query entered after For You → View All retained `view=for-you`, suppressing the tenant semantic endpoint; Patron filtered the recommendation pool and Staff did lexical core lookup. `loadCatalogue` now gives submitted discovery queries precedence over the view marker. Empty Patron global-discovery fallback follows the same query-first rule. No semantic algorithm was rewritten. Inventory search now includes current tenant holding shelf text and exact tenant copy barcode, while preserving accession/ISBN/text/filter lookup.

## Actual request paths

| Browser entry | Component/API | HTTP endpoint | Backend/provider | Hydration |
|---|---|---|---|---|
| `/catalog` query and `/search` (also case-insensitive `/Search`) | `GlobalCatalogue` → `searchBooks` | `POST /search-api/search` (Vite → 8003) | `search.api:search` → `RankedSearchPages.search` → `LuminaRSearchEngine.search` → MiniLM → global `Snapshot.candidates` → FAISS HNSW → CrossEncoder | `current_books` Mongo canonical validation before ranking; `RankedSearchPages.current_books` after cache; capabilities enrichment in `searchBooks` |
| Global header Search | `Header` → central `context.searchPath` → `GlobalCatalogue` | Same global endpoint | Same global provider | Same canonical hydration |
| TEST Patron `/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/catalogue` and header | `LibraryCataloguePage`/`CatalogueSurface` → `useLibraryCatalogue` → `loadCatalogue` → `institutionApi` | `GET /search-api/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/catalogue/search?search=...` | `search.library_intelligence_api:search` → `TenantIntelligence.semantic` → status/generation validation → MiniLM normalized384 → FAISS `IndexHNSWFlat.search` → CrossEncoder | Fresh fingerprint; `catalogue.usable` ACTIVE + selected tenant + authorized format/filter pipeline; canonical `catalogue.hydrate` |
| TEST Staff `/staff/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae/catalogue` and header | Same shared components/API with `staff=true` | Same tenant endpoint + staff flag | Same generation; staff membership required | Same canonical hydrate, staff actions preserved |
| Unfiltered tenant browse | Same `loadCatalogue`, no natural-language query | `GET /api/libraries/{id}/catalogue/books` | Bounded Mongo browse/filter | Canonical tenant catalogue hydrate |
| Non-READY discovery | Tenant semantic endpoint | Same query endpoint, or core on service 5xx | `catalogue.books`, escaped casefolded substring; tenant only | Current canonical rows; no stale vector generation |
| Staff Inventory | `LibraryInventory` → `institutionApi` | `GET /api/libraries/{id}/inventory/books` | `library_catalogue_service.list_books`, deterministic search_text/current holding shelf/exact copy barcode | Scoped current stock/availability; no embeddings or KG |
| Tenant Graph Lab | `LibraryGraphPage` → `institutionApi` | `GET /api/libraries/{id}/intelligence/graph` | `library_intelligence_service.graph` → separate KG generation | Current eligible tenant Book-node IDs and deterministic metadata relationships |

Global browsing without a query intentionally does not query HNSW. Global repeated queries intentionally use the existing generation-keyed ranking cache; it does not represent keyword fallback. The cold measured request queried **5,000,000** global vectors, semantic generation **30**, and reranked **50** candidates. TEST generation **dc974c19-a2b5-457c-af50-0b2e0446c2ed** queried **151** vectors; max **120** candidates and **60** reranked. Parameters/models unchanged.

## Runtime evidence

An explicitly launched loopback-only runner wraps the original native FAISS search, CrossEncoder.predict and canonical hydrators, preserving return values. Only allowlisted catalogue QA queries are recorded, without tokens, passwords, user identity, document/member payloads or a new debug endpoint. The ordinary `search.api` launch never imports this runner. Full selected call evidence: `search_hnsw_runtime_validation.json`; scores/order: `search_reranker_validation.json` and `search_keyword_semantic_comparison.json`.

Four real TEST queries independently compared against the existing lexical provider: beginner computer networking; accessibility transportation; community memories; equipment design workshop. All lexical controls returned zero; real HNSW/reranking/hydration displayed the expected book. The exploratory “getting around when walking is difficult” exposes a reranker limitation: Mobility vector rank 1 becomes rerank rank 44. This finding is retained, not hidden or remedied by an arbitrary ranking change.

The four-book disposable library **eb973eea-366e-4f5a-8853-8abeabcf7c40** was queried before build (NOT_BUILT/local fallback), built once through Chromium confirmation, then queried again (tenant HNSW + reranker). Its KG remains NOT_BUILT. The same query in TEST and the disposable library produced only the selected catalogue's records. TEST and global artifacts were never rebuilt.

## Fallback/freshness

NOT_BUILT, BUILDING, FAILED, STALE and RECOVERY_REQUIRED use current tenant-local fallback. STALE HNSW is retained for recovery but not queried. Canonical tenant membership, lifecycle, ACTIVE rows and formats are enforced; after HNSW ranking the source fingerprint is rechecked. A concurrent metadata change falls back to current canonical state. Foreign, archived, deleted and now-ineligible rows are covered in isolated tests. The frontend retries transient tenant lock 503 reads and falls back to core only for service failures, never authority denials.

## KG decision

Ordinary Search does **not** use KG. Graph Lab separately uses tenant metadata KG. Bounded same-tenant two-hop candidate augmentation produced no relevant candidate recall gain in four controlled queries; no integration was justified or implemented. Search succeeds with KG NOT_BUILT and FAILED. See `search_kg_integration_audit.md`.

## Regression/preservation

Backend: **330** unique scoped checks pass, including 30 new contracts. Frontend: **807** default checks plus **7** search-depth checks pass. Build passes; lint **0** errors / **14** preexisting warnings. Actual Chromium query and shelf/exact-title UI checks pass. TEST remains **151 ACTIVE records / 150 holdings / 5 assets**; all TEST collection/artifact hashes match. Global remains **5,000,000** records and **196** artifact size/mtime snapshots unchanged. Recommendation/Qwen/router/search algorithm sources unchanged. No authority grant, commit or Part 2I.

## Final QA summary

| Field | Value |
|---|---|
| GLOBAL_SEARCH_PROVIDER | GLOBAL_HNSW_MINILM_CROSSENCODER_WITH_RANKING_CACHE |
| GLOBAL_HNSW_ACTUALLY_QUERIED | YES |
| TENANT_READY_SEARCH_PROVIDER | TENANT_HNSW_MINILM_CROSSENCODER |
| TENANT_HNSW_ACTUALLY_QUERIED | YES |
| TENANT_HNSW_GENERATION | dc974c19-a2b5-457c-af50-0b2e0446c2ed |
| TENANT_HNSW_LIBRARY_ID | e6d1e5b4-c48f-4b47-b96a-656a676fb8ae |
| TENANT_RERANKER_USED | YES |
| TENANT_KEYWORD_FALLBACK_USED_WHEN_READY | NO |
| NOT_BUILT_FALLBACK_PROVIDER | TENANT_LOCAL_SUBSTRING |
| BUILDING_FALLBACK_PROVIDER | TENANT_LOCAL_SUBSTRING |
| FAILED_FALLBACK_PROVIDER | TENANT_LOCAL_SUBSTRING |
| STALE_SEARCH_POLICY | Current canonical tenant-local substring fallback; retained stale vector generation is not queried. Source fingerprint is rechecked after ranking; a concurrent change also falls back safely. |
| SEMANTIC_NON_LITERAL_QUERY_PASS | YES |
| KEYWORD_BASELINE_COMPARISON_PASS | YES |
| CROSS_LIBRARY_SEARCH_LEAK | NO |
| GLOBAL_FILLER_IN_TENANT_RESULTS | 0 |
| KNOWLEDGE_GRAPH_USED_BY_NORMAL_SEARCH | NO |
| KNOWLEDGE_GRAPH_SEARCH_ROLE | NOT_USED |
| KG_SEARCH_INTEGRATION_IMPLEMENTED_IN_THIS_TASK | NO |
| SEARCH_WORKS_WITH_KG_UNAVAILABLE | YES |
| INVENTORY_EXACT_SEARCH_PRESERVED | YES |
| GLOBAL_HNSW_REBUILT | NO |
| GLOBAL_KG_REBUILT | NO |

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

## Recommendation runtime addendum closure

Recommendation runtime is also closed: see recommendation_runtime_path_audit.md. Real correlated calls prove global HNSW plus CrossEncoder candidate generation, followed by separate hybrid recommender scoring/diversity. Tenant For You uses canonical global-candidate intersection/local acquisition fill and does not use tenant HNSW or KG. Tenant paging/cold start/isolation and final hydration pass. The global Popular cold-fallback View All destination was repaired without ranking changes. No Part 2I.
