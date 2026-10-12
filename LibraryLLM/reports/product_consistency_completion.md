# Product consistency + canonical defaults + TEST QA completion

PASS. TEST UUID e6d1e5b4-c48f-4b47-b96a-656a676fb8ae is preserved with 150 canonical ACTIVE records and holdings. The owner remains Staff Workspace only; a separate normal GENERAL_USER validated Patron Workspace. All 91 acceptance gates and required scenario mappings are in product_consistency_acceptance.json and product_consistency_required_tests.json.

| Item | Requested topic | Result |
|---|---|---|
| A | FINAL | PASS — all 91 gates have evidence. |
| B | UI before/after | Unequal header centering and fragmented empty states replaced by shared geometry and honest canonical states. |
| C | Centered header | Equal grid side tracks; desktop center error below 0.02 CSS px. |
| D | Staff consistency | Nine headings aligned; common cards/sidebar/buttons/44px filters. |
| E | Legacy root cause | Missing subsystem config after registration defaulted to LEGACY. |
| F | New defaults | Durable CANONICAL lending/reservations/fees before ACTIVE. |
| G | Empty legacy promotion | Explicit ADMIN preflight/idempotent promotion; TEST proven safe. |
| H | Historical preservation | Association/history/state blockers keep existing cutover paths. |
| I | Catalogue architecture | Accepted V1 authoritative resolver and normalized display path reused. |
| J | Global fallback | Actual empty-library discovery and existing Search, no ownership. |
| K | Local switch | Positive canonical usable-record count switches automatically. |
| L | Add Book | Real first Add UI and invalidation test pass. |
| M | Import | Preview zero effects; confirmed Apply switches without rebuild/restart. |
| N | Patron Home | TEST identity and 150 local books. |
| O | Rails | Tenant-only deterministic rails; mobile keyboard scrolling verified. |
| P | Arrivals | Local additions; includes four new local-only books. |
| Q | Genres | Actual TEST subjects and scoped counts. |
| R | Popular | One genuine QA borrowing signal; no fabricated seed history. |
| S | Browse | Local paginated collection. |
| T | Search | Local Physics query; accepted global Search only in fallback. |
| U | Header links | Patron Browse/Arrivals/My Library scoped; global Catalog remains global. |
| V | Presentation | Same DisplayBook/card/detail and branded missing-cover fallback. |
| W | Shelf/availability | Local shelf and canonical bulk projection only. |
| X | Actions | Pending request, staff approval, physical receipt, waitlist/cancel verified. |
| Y | TEST before | Existing TEST, 0 books, GLOBAL_FALLBACK. |
| Z | Seed | 150 canonical books/holdings retained. |
| AA | Global-linked | 146 actual global metadata records linked. |
| AB | Local-only | 4 local-only records. |
| AC | Holdings/status | Small 1–3 copy holdings; 145/3/2 circulation status split. |
| AD | Separate patron | Verified user_id 6 normal login/public join. |
| AE | TEST after | ACTIVE, CANONICAL, LIBRARY_LOCAL; no QA pending allocation. |
| AF | Global 5M | 5,000,000 before/after; 146 sampled full document hashes unchanged. |
| AG | Global HNSW | No rebuild or protected artifact change. |
| AH | Global KG | No rebuild or protected artifact change. |
| AI | Performance | Inventory N+1 removed using existing bulk projection; bounded reads measured. |
| AJ | Security | Membership/platform separation and stale-scope guards pass. |
| AK | Responsive/accessibility | 144 loaded checks across six CSS sizes; keyboard/focus/modal checks. |
| AL | Live | Normal owner/patron UI plus real Search; disposable fixtures cleaned. |
| AM | Backend | 1659 passed, 10 accepted skips; 18 groups. |
| AN | Frontend | 413 standard + 148 extended = 561 passed. |
| AO | Regression | Frozen areas pass; Router research excluded. |
| AP | Build/lint | Build passes; 0 errors, unchanged 19 warnings. |
| AQ | Files | Exact phase manifest: product_consistency_changed_files.json. |
| AR | Reports | Required reports plus acceptance, preservation, logs and screenshots created. |
| AS | Limits | Local sequential timings, structural/accessibility audit limits, DPI rounding, sampled preservation; build size warning retained. |
| AT | Review | Operator recovery/read-model/accessibility/bundle recommendations only. |
| AU | Future HNSW | Durable snapshot job → isolated build/checksum → atomic publish/reload; review only. |
| AV | Future KG | Same generation/job/publication protocol with tenant graph IDs; review only. |
| AW | Next phase | Events + Notifications Tenancy V1 recommended; not implemented. |

## Exact phase source files

Compared against the 899-file phase baseline, preserving previous accepted work. The baseline helper itself was created immediately before capture. Hashes, absolute paths and purposes are in product_consistency_changed_files.json.

- MODIFIED `backend/routes/library_lending.py`
- MODIFIED `backend/services/institution_service.py`
- MODIFIED `backend/services/library_catalogue_service.py`
- MODIFIED `frontend/package.json`
- MODIFIED `frontend/src/App.tsx`
- MODIFIED `frontend/src/components/LibraryShells.tsx`
- MODIFIED `frontend/src/hooks/useLibraryCatalogue.ts`
- MODIFIED `frontend/src/lib/institutions.ts`
- MODIFIED `frontend/src/lib/libraryInventory.ts`
- MODIFIED `frontend/src/pages/InstitutionPanel.tsx`
- MODIFIED `frontend/src/pages/LibraryCirculation.tsx`
- MODIFIED `frontend/src/pages/LibraryInventory.tsx`
- MODIFIED `frontend/src/pages/LibraryReservationsFees.tsx`
- MODIFIED `frontend/src/styles/workspaces.css`
- MODIFIED `frontend/tests/institution-inventory.test.tsx`
- MODIFIED `scripts/run_isolated_search_api_lexical.py`
- MODIFIED `tests/dashboard_convergence/conftest.py`
- MODIFIED `tests/frontend_workspace/conftest.py`
- MODIFIED `tests/institution_v2a/conftest.py`
- MODIFIED `tests/institution_v2b/conftest.py`
- MODIFIED `tests/institution_v2c/conftest.py`
- MODIFIED `tests/library_catalogue_experience/test_catalogue.py`
- ADDED `backend/services/library_canonical_defaults.py`
- ADDED `frontend/src/lib/catalogueInvalidation.ts`
- ADDED `frontend/tests/product-consistency.test.tsx`
- ADDED `scripts/check_product_consistency_live.py`
- ADDED `scripts/cleanup_product_consistency_fixtures.py`
- ADDED `scripts/prepare_product_consistency_tests.py`
- ADDED `scripts/product_consistency_inspect.py`
- ADDED `scripts/product_consistency_live_fixture.py`
- ADDED `scripts/product_consistency_waitlist_stock.py`
- ADDED `scripts/recover_library_initialization.py`
- ADDED `scripts/report_product_consistency.py`
- ADDED `scripts/seed_test_library_collection.py`
- ADDED `scripts/test_product_consistency_frontend.py`
- ADDED `scripts/test_product_consistency_regressions.py`
- ADDED `tests/product_consistency/conftest.py`
- ADDED `tests/product_consistency/test_defaults.py`
- ADDED `tests/product_consistency/test_seed.py`

## Report evidence

- product_consistency_baseline.json
- product_consistency_ui.md
- product_consistency_header.json
- canonical_new_library_defaults.md
- canonical_empty_library_promotion.json
- library_catalogue_experience_architecture.md
- library_catalogue_source.json
- library_catalogue_home.json
- library_catalogue_browse.json
- library_catalogue_search.json
- library_catalogue_new_arrivals.json
- library_catalogue_genres.json
- library_catalogue_popular.json
- library_catalogue_fallback.json
- library_catalogue_performance.json
- library_catalogue_actions.json
- test_library_seed.json
- test_library_manual_validation.md
- product_consistency_browser.json
- product_consistency_security.json
- product_consistency_regression.json
- product_consistency_improvement_review.md
- product_consistency_next_scope.md

Prior requested catalogue reports are archived byte-for-byte under .scratch/product_consistency_prior_reports. All other 4084 baseline report hashes remain unchanged. Global/AI source hashes and all 196 recorded artifacts pass preservation. Early audit/harness failures remain explained in browser/regression evidence; final successful results are recorded separately.

## Runtime and limits

Review frontend: http://127.0.0.1:5182; review core: 8088. These phase-owned review services are left running intentionally. Existing services 8002, 8080 and Search 8003 were not stopped. Disposable QA core/frontend and database were stopped/dropped; only their reports remain. TEST collection, membership and actual QA history remain for manual review. No temporary fallback library remains. No Git reset, commit, index rebuild or next-phase implementation occurred.

Ten regression skips are existing explicitly unavailable legacy digital-fixture cases; exact reasons are retained in the regression JSON. The global Search lexical harness uses explicit unused-model substitutes, while real accepted production Search was also queried successfully. Development p50/p95 uses five sequential requests per route and is not a concurrency/SLO benchmark. Preservation checks all sampled seeded source documents, global counts, protected code and artifact size/mtime, without claiming a full global/index content checksum. Browser actual CSS dimensions, DPI-backed PNG pixels, structural accessibility limits and existing build size warning are reported honestly.

## Final test data summary

```json
{
  "TEST_ACCOUNT_USED": "YES",
  "TEST_LIBRARY_NAME": "TEST",
  "TEST_LIBRARY_UUID": "e6d1e5b4-c48f-4b47-b96a-656a676fb8ae",
  "TEST_LIBRARY_PRESERVED": "YES",
  "TEST_BOOKS_BEFORE": 0,
  "TEST_BOOKS_AFTER": 150,
  "GLOBAL_LINKED_TEST_BOOKS_ADDED": 146,
  "LOCAL_ONLY_TEST_BOOKS_ADDED": 4,
  "TEST_HOLDINGS_CREATED": 150,
  "CIRCULATING_COUNT": 145,
  "REFERENCE_ONLY_COUNT": 3,
  "TEMPORARILY_UNAVAILABLE_COUNT": 2,
  "CATALOGUE_SOURCE_BEFORE": "GLOBAL_FALLBACK",
  "CATALOGUE_SOURCE_AFTER": "LIBRARY_LOCAL",
  "GLOBAL_BOOK_COUNT_BEFORE": 5000000,
  "GLOBAL_BOOK_COUNT_AFTER": 5000000,
  "GLOBAL_BOOKS_DELETED": 0,
  "GLOBAL_CATALOGUE_MUTATED": "NO",
  "GLOBAL_HNSW_REBUILT": "NO",
  "GLOBAL_KG_REBUILT": "NO",
  "SEPARATE_GENERAL_USER_VALIDATED": "YES",
  "TEST_OWNER_ADMIN_REMAINS_STAFF_ONLY": "YES",
  "TEST_COLLECTION_PRESERVED_FOR_MANUAL_REVIEW": "YES"
}
```
