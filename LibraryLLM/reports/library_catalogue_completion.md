# Library Catalogue Experience V1 — completion

PASS for implementation and listed acceptance gates, with the documented live global Search service limitation. Backend **1632 passed / 10 skipped**, frontend **552 passed**, 48 layout checks and 15 final interaction checks. Build passes; lint has 0 errors and the same 19 pre-existing warnings.

## Exact source files changed

- [backend/main.py](D:/SDC/LibraryLLM/backend/main.py) — MODIFIED: Mount catalogue read routes and tenant read indexes.
- [backend/services/library_lending_service.py](D:/SDC/LibraryLLM/backend/services/library_lending_service.py) — MODIFIED: Narrow integration repair: extract unchanged pure availability projection, shared by existing individual and new bulk reads. Existing locking, database reads and all commands stay in Part 2B/C.
- [frontend/package.json](D:/SDC/LibraryLLM/frontend/package.json) — MODIFIED: Add test:catalogue and include it in npm test; no dependency changes.
- [frontend/src/App.tsx](D:/SDC/LibraryLLM/frontend/src/App.tsx) — MODIFIED: Mount scoped patron catalogue pages and local/global detail routes.
- [frontend/src/components/Header.tsx](D:/SDC/LibraryLLM/frontend/src/components/Header.tsx) — MODIFIED: Scope catalogue, arrivals and search navigation inside the current patron library.
- [frontend/src/components/LibraryShells.tsx](D:/SDC/LibraryLLM/frontend/src/components/LibraryShells.tsx) — MODIFIED: Scoped patron navigation; simple source/count card in existing staff overview.
- [frontend/src/pages/Institutions.tsx](D:/SDC/LibraryLLM/frontend/src/pages/Institutions.tsx) — MODIFIED: Remove unused generic LibraryHomePage export after routing to the real catalogue home.
- [frontend/tests/kg-product.test.tsx](D:/SDC/LibraryLLM/frontend/tests/kg-product.test.tsx) — MODIFIED: Test-only frozen integration repair: retired global BORROW assertion now verifies the accepted library-selection link, with no legacy borrow button. KG product remains unchanged.
- [backend/services/library_catalogue_availability.py](D:/SDC/LibraryLLM/backend/services/library_catalogue_availability.py) — ADDED: Shared pure canonical projection, no stock writer.
- [backend/services/library_catalogue_experience.py](D:/SDC/LibraryLLM/backend/services/library_catalogue_experience.py) — ADDED: Central source resolver, bounded bulk hydration, tenant discovery and activity ranking.
- [backend/routes/library_catalogue_experience.py](D:/SDC/LibraryLLM/backend/routes/library_catalogue_experience.py) — ADDED: Membership-guarded catalogue GET endpoints.
- [frontend/src/lib/libraryCatalogue.ts](D:/SDC/LibraryLLM/frontend/src/lib/libraryCatalogue.ts) — ADDED: Normalized local/global model and one fallback adapter.
- [frontend/src/hooks/useLibraryCatalogue.ts](D:/SDC/LibraryLLM/frontend/src/hooks/useLibraryCatalogue.ts) — ADDED: Scope/filter/token keys, abort and stale-response protection.
- [frontend/src/components/LibraryCatalogueBook.tsx](D:/SDC/LibraryLLM/frontend/src/components/LibraryCatalogueBook.tsx) — ADDED: Shared cards, covers, detail and canonical actions.
- [frontend/src/pages/LibraryCatalogue.tsx](D:/SDC/LibraryLLM/frontend/src/pages/LibraryCatalogue.tsx) — ADDED: Patron home, browse/search, arrivals, genres, popular and details.
- [frontend/src/pages/LibraryCatalogue.css](D:/SDC/LibraryLLM/frontend/src/pages/LibraryCatalogue.css) — ADDED: Existing paper/rust/ink system, responsive rails and visible focus.
- [frontend/tests/library-catalogue.test.tsx](D:/SDC/LibraryLLM/frontend/tests/library-catalogue.test.tsx) — ADDED: 41 new frontend checks, including three axe structural checks.
- [tests/library_catalogue_experience/conftest.py](D:/SDC/LibraryLLM/tests/library_catalogue_experience/conftest.py) — ADDED: Disposable Mongo/HTTP fixture.
- [tests/library_catalogue_experience/test_catalogue.py](D:/SDC/LibraryLLM/tests/library_catalogue_experience/test_catalogue.py) — ADDED: 41 canonical source, ownership, availability, scope and batching tests.
- [scripts/library_catalogue_experience_baseline.py](D:/SDC/LibraryLLM/scripts/library_catalogue_experience_baseline.py) — ADDED: Immutable read-only baseline; helper creation preceded baseline capture.
- [scripts/check_library_catalogue_live.py](D:/SDC/LibraryLLM/scripts/check_library_catalogue_live.py) — ADDED: Disposable live libraries, real JWT/membership APIs and read-only actual 5M global metadata.
- [scripts/test_library_catalogue_regressions.py](D:/SDC/LibraryLLM/scripts/test_library_catalogue_regressions.py) — ADDED: Frozen suites in isolated processes, with Router research excluded.
- [scripts/report_library_catalogue_experience.py](D:/SDC/LibraryLLM/scripts/report_library_catalogue_experience.py) — ADDED: Phase reports and preservation audit.

## Required reports

- [library_catalogue_experience_baseline.json](D:/SDC/LibraryLLM/reports/library_catalogue_experience_baseline.json)
- [library_catalogue_experience_architecture.md](D:/SDC/LibraryLLM/reports/library_catalogue_experience_architecture.md)
- [library_catalogue_source.json](D:/SDC/LibraryLLM/reports/library_catalogue_source.json)
- [library_catalogue_home.json](D:/SDC/LibraryLLM/reports/library_catalogue_home.json)
- [library_catalogue_browse.json](D:/SDC/LibraryLLM/reports/library_catalogue_browse.json)
- [library_catalogue_search.json](D:/SDC/LibraryLLM/reports/library_catalogue_search.json)
- [library_catalogue_new_arrivals.json](D:/SDC/LibraryLLM/reports/library_catalogue_new_arrivals.json)
- [library_catalogue_genres.json](D:/SDC/LibraryLLM/reports/library_catalogue_genres.json)
- [library_catalogue_popular.json](D:/SDC/LibraryLLM/reports/library_catalogue_popular.json)
- [library_catalogue_fallback.json](D:/SDC/LibraryLLM/reports/library_catalogue_fallback.json)
- [library_catalogue_security.json](D:/SDC/LibraryLLM/reports/library_catalogue_security.json)
- [library_catalogue_performance.json](D:/SDC/LibraryLLM/reports/library_catalogue_performance.json)
- [library_catalogue_live.json](D:/SDC/LibraryLLM/reports/library_catalogue_live.json)
- [library_catalogue_regression.json](D:/SDC/LibraryLLM/reports/library_catalogue_regression.json)
- [library_catalogue_improvement_review.md](D:/SDC/LibraryLLM/reports/library_catalogue_improvement_review.md)
- [library_catalogue_next_scope.md](D:/SDC/LibraryLLM/reports/library_catalogue_next_scope.md)

## Evidence and limits

Detailed source, home, browse/search, arrivals, genres, popularity, physical action, switching, staff/platform, batching, live and regression evidence is in the reports above. Preservation evidence: [library_catalogue_preservation.json](library_catalogue_preservation.json). All 41 requested named tests are covered; [acceptance matrix](library_catalogue_acceptance.json). Build retains the existing large-bundle warning. The global Search service on 8003 is offline; adapter routing and offline retry behavior pass, but live HNSW results are not claimed. Some requested viewports differ by one CSS pixel due to 125% Windows scaling. Large artifacts were compared by size/mtime, and production data by collection counts. No production migration/deployment or existing-service restart occurred.

Future tenant HNSW/KG architecture is review-only in the improvement report. Recommended next phase is Events + Notifications Tenancy V1, awaiting explicit approval. No build buttons/workers, Events/Notifications tenancy, analytics, digital tenancy or private vector routing was implemented.
