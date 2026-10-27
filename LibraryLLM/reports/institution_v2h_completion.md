# Institution Part 2H completion

## A. FINAL RESULT

PASS

## B. INTELLIGENCE PAGE ARCHITECTURE

One scoped page over the accepted Part 2G durable infrastructure.

## C. STAFF ROUTE

/staff/libraries/{library_id}/intelligence

## D. AUTHORIZATION MATRIX

ADMIN view/build; LIBRARIAN view only; GENERAL_USER and Platform-only denied.

## E. NEW LIBRARY BEHAVIOR

NOT_BUILT before and after adding books; usable local fallback; explicit builds only.

## F. SEARCH STATUS UI

Independent card; all specified states; safe diagnostics and readonly HNSW details.

## G. KG STATUS UI

Independent card; books, nodes, edges and generation details.

## H. SEARCH BUILD FLOW

Confirmation → existing build-job API → durable worker → validated publication.

## I. KG BUILD FLOW

Independent target using the same accepted durable control architecture.

## J. SEARCH REBUILD FLOW

TEST rebuilt through actual Chromium; new target generation and same 150 eligible records.

## K. KG REBUILD FLOW

TEST rebuilt through actual Chromium; new generation, 1093 nodes and 1111 edges.

## L. CONFIRMATION UX

Build/Rebuild and known Retry use shared keyboard-accessible dialog; current validated generation is retained until publication.

## M. PROGRESS / POLLING

Real durable fields; three-second active polling, abort and sequence guards; terminal stop.

## N. STALE UX

Backend fingerprint is authoritative; disposable indexed metadata change made both targets STALE without a job.

## O. FAILED UX

Bounded safe message; previous validated pointer retained; known outcome permits Retry.

## P. RECOVERY_REQUIRED UX

Distinct text and no blind Retry; existing explicit operator recovery verified.

## Q. LAST-GOOD GENERATION BEHAVIOR

Retained and verified independently of latest attempt. Existing reader fallback policy is unchanged.

## R. GENERATION DETAILS

Successful generation number and timestamp; advanced UUIDs, source dataset, verification and fixed model/settings.

## S. EMPTY LIBRARY

UI disables controls; public API refuses zero eligible books; worker rechecks snapshot.

## T. LIBRARIAN READ-ONLY

Verified with actual dedicated local QA Librarian and API denials.

## U. MULTI-LIBRARY ISOLATION

Actual old HTTP response held during switch; ignored/cancelled completion did not replace TEST data.

## V. AUDIT

Canonical request/success/failure/recovery events with hydrated email actors and idempotent event IDs.

## W. RESPONSIVE

All six requested sizes; ready/advanced details, active progress and both target dialogs.

## X. ACCESSIBILITY

Native text/progress; focus trap, Enter/Escape/focus restoration; axe WCAG/contrast checks with zero violations.

## Y. TEST SEARCH REBUILD

1d12b814-fb98-465d-89c8-3f6194a14fd0 → 850e3618-3f58-43b7-9770-8bb4de33c805

## Z. TEST KG REBUILD

1ea21ff2-af3c-4092-b81e-f1a4dda6a98c → 91bf71b8-ebcf-4ab2-84df-412760b10bcd

## AA. NEW LIBRARY BUILD VALIDATION

Zero-book NOT_BUILT, add three local books, explicit Search/KG builds, metadata staleness, explicit rebuilds.

## AB. BACKEND TESTS

2160 passed; 10 existing skips; 23 independent groups.

## AC. FRONTEND TESTS

891 unique passed: full default run plus final affected recheck and extended files.

## AD. BROWSER VALIDATION

Actual Chromium; normal login; no persisted credentials, auth states or frontend-build shell execution.

## AE. REGRESSION

Frozen V1 and 2A–2G plus workspace, Platform, catalogue, Search, graph, assets, RAG, Knowledge Tools, Assistant, Events, Notifications and Analytics; no router research.

## AF. PRESERVATION

TEST books/holdings/assets exact baseline hashes and personal logical registry unchanged; 5M global records.

## AG. GLOBAL HNSW PRESERVATION

No global rebuild; protected artifact byte lengths and nanosecond mtimes unchanged.

## AH. GLOBAL KG PRESERVATION

No global rebuild; protected graph artifacts and semantic source code unchanged.

## AI. EXACT FILES CHANGED

See institution_v2h_changed_files.json. Existing unrelated uncommitted work preserved; no commit.

## AJ. REPORTS CREATED

All requested Part 2H reports plus detailed logs, XML and screenshots.

## AK. KNOWN LIMITATIONS

Existing local worker and checksum costs; no cancellation/automatic build. Explicit operator recovery. Existing fallback policy remains authoritative.

## AL. IMPROVEMENT REVIEW

See institution_v2h_improvement_review.md.

## AM. RECOMMENDED NEXT PHASE

Review Part 2H first; any Part 2I design or implementation requires explicit approval.

## Final QA summary

```text
INTELLIGENCE_ROUTE: /staff/libraries/{library_id}/intelligence
NEW_LIBRARY_SEARCH_INITIAL_STATE: NOT_BUILT
NEW_LIBRARY_KG_INITIAL_STATE: NOT_BUILT
ADMIN_CAN_BUILD_SEARCH: YES
ADMIN_CAN_REBUILD_SEARCH: YES
ADMIN_CAN_BUILD_KG: YES
ADMIN_CAN_REBUILD_KG: YES
LIBRARIAN_CAN_VIEW_STATUS: YES
LIBRARIAN_CAN_BUILD: NO
GENERAL_USER_ACCESS: NO
PLATFORM_ONLY_BUILD_ACCESS: NO
TEST_SEARCH_BEFORE_GENERATION: 1d12b814-fb98-465d-89c8-3f6194a14fd0
TEST_SEARCH_AFTER_GENERATION: 850e3618-3f58-43b7-9770-8bb4de33c805
TEST_SEARCH_REBUILD_PASS: YES
TEST_KG_BEFORE_GENERATION: 1ea21ff2-af3c-4092-b81e-f1a4dda6a98c
TEST_KG_AFTER_GENERATION: 91bf71b8-ebcf-4ab2-84df-412760b10bcd
TEST_KG_REBUILD_PASS: YES
NEW_LIBRARY_SEARCH_BUILD_PASS: YES
NEW_LIBRARY_KG_BUILD_PASS: YES
SEARCH_PROGRESS_PASS: YES
KG_PROGRESS_PASS: YES
SEARCH_STALE_PASS: YES
KG_STALE_PASS: YES
FAILED_RETRY_PASS: YES
RECOVERY_REQUIRED_SAFE: YES
DUPLICATE_BUILD_PROTECTED: YES
LAST_GOOD_GENERATION_PRESERVED: YES
AUTOMATIC_BUILD_AFTER_BOOK_ADD: NO
GLOBAL_BUILD_CONTROLS_PRESENT: NO
TEST_LIBRARY_BOOK_COUNT: 150
TEST_HOLDING_COUNT: 150
GLOBAL_BOOK_COUNT: 5000000
GLOBAL_HNSW_REBUILT: NO
GLOBAL_KG_REBUILT: NO
```

## Exact changed files

- `backend/routes/library_intelligence.py`
- `backend/services/institution_service.py`
- `backend/services/library_intelligence_service.py`
- `backend/services/library_intelligence_store.py`
- `frontend/package.json`
- `frontend/src/App.tsx`
- `frontend/src/components/LibraryShells.tsx`
- `frontend/src/lib/libraryIntelligence.ts`
- `frontend/src/pages/LibraryIntelligence.css`
- `frontend/src/pages/LibraryIntelligence.tsx`
- `frontend/tests/institution-intelligence-controls.test.tsx`
- `scripts/institution_v2h_accessibility_browser.py`
- `scripts/institution_v2h_baseline.py`
- `scripts/institution_v2h_browser.py`
- `scripts/institution_v2h_extended_frontend.py`
- `scripts/institution_v2h_failure_browser.py`
- `scripts/institution_v2h_final_browser.py`
- `scripts/institution_v2h_page_recheck.py`
- `scripts/institution_v2h_regressions.py`
- `scripts/institution_v2h_reports.py`
- `scripts/institution_v2h_switch_browser.py`
- `search/library_intelligence.py`
- `tests/institution_v2h/conftest.py`
- `tests/institution_v2h/test_controls.py`

## Reports

- `institution_v2h_accessibility.json`
- `institution_v2h_architecture.md`
- `institution_v2h_audit.json`
- `institution_v2h_authorization.json`
- `institution_v2h_baseline.json`
- `institution_v2h_browser.json`
- `institution_v2h_build_flow.json`
- `institution_v2h_changed_files.json`
- `institution_v2h_completion.json`
- `institution_v2h_completion.md`
- `institution_v2h_failure_ui.json`
- `institution_v2h_final_browser.json`
- `institution_v2h_fixtures.json`
- `institution_v2h_generation_ui.json`
- `institution_v2h_improvement_review.md`
- `institution_v2h_kg_ui.json`
- `institution_v2h_new_library_flow.json`
- `institution_v2h_next_scope.md`
- `institution_v2h_page_recheck.json`
- `institution_v2h_preservation.json`
- `institution_v2h_progress.json`
- `institution_v2h_regression.json`
- `institution_v2h_responsive.json`
- `institution_v2h_search_ui.json`
- `institution_v2h_security.json`
- `institution_v2h_stale_ui.json`
- `institution_v2h_status_contract.json`
