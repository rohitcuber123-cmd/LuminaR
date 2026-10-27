# Recommendation runtime addendum — PASS

The real global recommender is **Search-HNSW candidate dependent + user/profile hybrid scoring + diversity**. Tenant For You **does not use tenant HNSW**: it intersects global preference candidates with canonical owned records, then fills with local acquisitions. This is the accepted Home convergence architecture, not an obsolete keyword routing mistake. READY/NOT_BUILT tenant HNSW comparison preserves the same recommendation provider. Algorithms, weights, HNSW parameters and KG dependencies remain unchanged.

One genuine product defect was fixed: global cold-start Popular fallback's View All previously navigated to empty personalized recommendations. `ForYou` now delegates to the existing centralized `homeCataloguePath(...,'popular')`, opening `/catalog?sort=popular`. Personalized and tenant View All retain their existing destinations. A failing regression test reproduced the old route; real Chromium verifies the corrected route and Popular results.

## End-to-end traces

| Surface | Frontend/API | HTTP route | Candidate/ranking provider | Canonical boundary |
|---|---|---|---|---|
| Global Home For You | `ForYou` → `getRecommendations(10,offset)` | `GET /recommendation-api/recommendations` → 8004 `recommendation.api.recommendations` | `RankedRecommendationPages` → `get_recommendations` → actual recency-selected search history → `generate_semantic_candidates` → `POST 8003/search` → global MiniLM/HNSW + CrossEncoder → hybrid score → diversity | Recommender current global Mongo enrichment; ranked pages refresh `current_books`, exclusions, facts on each page |
| Global Next/Previous | Same ForYou/provider | Same endpoint, offsets 10/20 etc | Frozen user/session/seed/global-generation 50-identity pool, 180-second TTL | Fresh canonical hydration on every page; no Popular switch on a later page |
| Global View All | `GlobalCatalogue` → `getRecommendations` | Same recommendation endpoint | Same ranked pool | Same canonical global hydration |
| Global cold start | ForYou empty recommendation response | `/api/books/popular` | Read-log/rating aggregate ordering, explicitly labelled Popular books | Core catalogue display; View All retains `/catalog?sort=popular` after repair |
| TEST Home For You | `loadCatalogue(home)` and shared `ForYou` → `libraryRecommendationPage` | Global `/recommendation-api/recommendations?limit=50&offset=0`, then `POST /api/libraries/{id}/catalogue/recommendations` | Core `library_catalogue_experience.recommendations`: ordered global work-ID intersection + recent acquisition fill, max50 for paging; no tenant index/graph load | Explicit GENERAL_USER membership, usable ACTIVE selected-library records; canonical `hydrate`; only local `library_book_id` cards |
| TEST Next/Previous/carousel | Same libraryRecommendationPage; global pool fetched at offset0 then scoped local slicing | Same global/core endpoints | Same scoped 50-result pool sliced in 10s; carousel only changes scroll position | Token + selected tenant + offset state, abort old requests on switch; source/each result validated |
| TEST View All | `LibraryCataloguePage` → `loadCatalogue(view=for-you)` | Same upstream candidates and canonical projection | Same intersection/local fill | Library-owned grid/paging. Submitted queries intentionally switch to Search (previous runtime repair); unqueried recommendations remain unchanged |
| Empty library Home | source=GLOBAL_FALLBACK; global discovery candidates or Popular if cold | Global recommendation/Core discovery endpoints | Explicitly labelled global discovery | No global card represented as library-owned |
| Staff discovery | `LibraryCataloguePage(staff)` | `/api/libraries/{id}/catalogue/books?staff=true` | Canonical Staff browse/discovery; no claim that this is Patron recommendation | Staff membership and Staff book destinations; no Admin-as-patron |
| New Arrivals | Shared Home catalogue / arrivals page | Core books or tenant home/books sort=new_arrivals | Tenant acquisition-date/created-date ordering; global created_at ordering | Current canonical data |
| Popular | Shared Home catalogue / popular page | Core popular or tenant home/books sort=popular | Tenant 90-day activity weights: loans8, approved BORROW requests2, reservations1; global reading-log/rating aggregates | Current tenant or global scope as explicitly selected |
| More Like This | `useMoreLikeThis` → `relatedBooks` | `/api/kg/books/{work_id}/more-like-this` | Separate global metadata KG relationships, **not For You** | Canonical global refresh/stale-feature suppression; labelled related graph discovery |
| Assistant Recommend Similar | Assistant explicit seed action | `/recommendations/from-book` | Existing recommender with single global metadata seed; same Search candidate source/hybrid/diversity | Current global records and seed/currently-active exclusions |

## Runtime proof

Actual Chromium Global Home supplied a genuine persisted nonliteral Search preference: **beginner computer networking**. The Recommendation call's private QA correlation ID `5e80dd5b-336d-4bf4-95f2-cfee8263ec91` matches the Search worker trace: native **IndexHNSWFlat, 5,000,000 vectors, global generation 30**, CrossEncoder **50** predictions, canonical hydration. Recommendation then executes its own weighted score/diversity and refreshes facts per page. The service has no separately trained recommender model and no second direct CrossEncoder invocation.

Instrumentation runs only through explicitly launched local QA runners, only for allowlisted QA users/queries; no diagnostic endpoint or response field was added. Authorization/passwords/raw private histories are not recorded. Existing QA profile counts are aggregate only. Normal service launch never imports these runners.

Actual personalization sources and limits are detailed in `recommendation_cold_start.json`. Ordinary semantic candidates require search-history queries; borrowing/reservation/feedback author/subject signals affect scoring but do not independently create a query. Reading List, AI selection, tenant loans and tenant indexes are not silently claimed as inputs. Global session/generation cache policy remains unchanged; the controlled preference test uses a fresh login after the genuine Search interaction.

## Tenant/cold-start/provider checks

Clean local QA account: no history → global Popular fallback; empty library → labelled global discovery; adding 25 local records → tenant acquisition discovery. Disposable A was then explicitly built once: Search became READY while KG remained NOT_BUILT, and recommendation identities/order/provider were unchanged. A later globally preferred linked record was added solely to A; B does not own it. A's Search generation then becomes STALE without a rebuild; recommendation scope remains valid.

Same GENERAL_USER A→B switch, two Next pages and Previous, carousel traversal, View All, browser Back/Forward, unavailable global recommendation fixture and existing TEST three Next pages pass. TEST results are exclusively TEST-owned. Canonical hydration/filter tests suppress withdrawn/deleted/foreign/no-format local rows and deleted cached global works. Global/local duplicate representations are absent; distinct canonical editions keep their local identity.

KG role for **For You: NOT_USED**. Recommendation works with tenant KG NOT_BUILT/FAILED. More Like This is independently traced to its graph endpoint (HTTP 200); no assertion that this separate KG feature powers Home recommendations. No KG integration was introduced.

## Results and preservation

**224 scoped backend checks pass**, including 19 new recommendation contracts. **819 default frontend checks pass**, including 12 new recommendation tests; **49 overlapping focused checks** also pass on the final component. Build passes; lint **0 errors / 14 existing warnings**. **16 unique Chromium scenarios pass**. Performance is measured separately for cold personalized pipeline, global HNSW/reranker stages, cached global pools and TEST projection; bounded local samples are not an SLA.

TEST remains **151 local records / 150 holdings / 5 assets**, with identical canonical collection/artifact hashes. Global remains **5,000,000** records and all **196** global artifact snapshots unchanged. Recommendation/Search backend algorithms, Qwen/router and document systems unchanged. Temporary QA accounts are disabled, credentials never persisted. Only one disposable Search build; no TEST/global rebuild and no KG build. No commit. No Part 2I.

## Final QA summary

| Field | Value |
|---|---|
| GLOBAL_RECOMMENDATION_PROVIDER | GLOBAL_HNSW_CANDIDATES + EXISTING_HYBRID_PROFILE_SCORE + DIVERSITY |
| TENANT_RECOMMENDATION_PROVIDER | GLOBAL_CANDIDATE_INTERSECTION_AND_CANONICAL_LOCAL_ACQUISITION_FILL |
| RECOMMENDATION_USES_SEARCH | YES |
| RECOMMENDATION_SEARCH_PROVIDER | GLOBAL_HNSW_MINILM_CROSSENCODER (or accepted ranking cache) |
| RECOMMENDATION_USES_TENANT_HNSW | NO |
| RECOMMENDATION_HNSW_ACTUALLY_QUERIED | YES (global) |
| RECOMMENDATION_SEARCH_GENERATION | 30 |
| RECOMMENDATION_USES_KEYWORD_FALLBACK_WHEN_HNSW_READY | N/A — tenant HNSW is not a recommender dependency; acquisition fill is not keyword Search |
| RECOMMENDATION_USES_KG | NO |
| RECOMMENDATION_KG_ROLE | NOT_USED_BY_FOR_YOU |
| TENANT_RECOMMENDATION_GLOBAL_FILLER_COUNT | 0 |
| TENANT_RECOMMENDATION_CROSS_LIBRARY_LEAK | NO |
| RECOMMENDATION_CANONICAL_HYDRATION | YES |
| RECOMMENDATION_COLD_START_PASS | YES |
| RECOMMENDATION_PAGING_TENANT_SAFE | YES |
| RECOMMENDATION_MULTI_LIBRARY_CACHE_SAFE | YES |
| NEW_ARRIVALS_PROVIDER | TENANT acquisition/created date ordering; GLOBAL created_at ordering |
| POPULAR_PROVIDER | TENANT weighted 90-day loans/approved BORROW requests/reservations; GLOBAL reading_log_count/rating aggregates |

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
