# Patron Home unification — PASS

Global and library contexts now render the same original LuminaR Home composition. The separate Explore TEST hero, compact Home rails and full Patron navigation row are retired. App.tsx mounts Home with a library context; no copied LibraryHome page or alternate flag remains.

HomeCatalogueContext injects canonical catalogue data into the original six sections. The global branch retains its existing APIs, recommendation algorithm, section geometry, typography, covers and actions. GLOBAL_HOME_CHANGED=NO refers to visuals and behavior; shared component source was refactored.

In an empty library, authoritative GLOBAL_FALLBACK uses the existing global catalogue/recommender and strips physical ownership fields/actions. Once any usable ACTIVE canonical record with a holding exists, all primary sections use local records. The resolver remains authoritative; no has_dataset switch, index build or application restart is required.

For You scopes up to 200 existing global work candidates against canonical holdings, retains their order, and fills only from deterministic local acquisition discovery. The request is read-only and bounded to 50 results. Local-only titles are eligible. TEST's four local-only titles appeared in its ten-item recommendation rail.

Arrivals use valid acquisition_date, otherwise LibraryBookRecord.created_at. Popular uses only tenant canonical activity; fewer than four activity titles produce a truthful Discover More section using local acquisitions. Categories use local subjects/counts and owned preview books. Browse, Search and every View All link retain the selected library. A zero-result search explicitly separates global discovery.

The shared recommendation card frame and original Popular card geometry use LuminaR's branded BookCover. Home cards keep concise availability, shelf and canonical request/waitlist actions. Accession, copy counts, full subjects, request status and queue metadata live in details. Existing Part 2B/C writers, membership authorization and platform assignments remain unchanged.

Validation: 1667 backend tests passed, 10 accepted existing skips; 588 frontend tests passed. All 30 requested named tests passed. Build passed; lint has zero errors and 19 existing warnings. All 23 browser acceptance gates passed. The final report links retained logs and XML evidence. Earlier transient/outdated-test failures were resolved and the complete final checks passed.

Browser comparison: global and TEST have the same six section classes, 190px desktop showcase covers and 180px recommendation cards. Mobile/tablet/desktop widths were verified with no document overflow. Windows 125% scaling produces a 767px actual tablet width for a 768px target; CSS and screenshot backing dimensions are distinct. The carousel advanced from 0 to 576.25 CSS pixels. Dynamic marquee positions and random category choices prevent a pixel-identical screenshot comparison.

TEST has 150 ACTIVE books. All 60 rendered book instances (25 distinct IDs) checked against canonical TEST records are local: 100%, zero global filler. The sole genuine activity title is not represented as fabricated global popularity. A live Home request created PENDING with no loan, was cancelled, and left zero pending requests.

The disposable private library rendered full global fallback, then switched automatically to a single local-only book with the same UI. A browser reload observed the API-side Add; no application process was restarted during that transition. Existing Add/import invalidation and browser-focus tests validate refresh of an already-open page. The exact disposable library and its book were cleaned up; TEST remains available.

Preservation: global count 5,000,000, all 146 full sampled global documents unchanged, 173 protected global source files unchanged, all 196 artifact size/mtime records unchanged, all 4204 previous reports byte-identical. No claim is made of hashing all five million documents or multi-gigabyte artifacts. No HNSW or KG rebuild, production platform grant, tenant indexing or next-phase work occurred.

Review: http://127.0.0.1:5182/libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae. Frontend 5182 and review core 8088 remain running. The review core was restarted only to load development code before switchover validation; original services 8002/8080 and Search 8003 were untouched.

Evidence: patron_home_unification_acceptance.json, patron_home_unification_required_tests.json, patron_home_unification_tests.json, patron_home_unification_browser.json, patron_home_unification_live.json, patron_home_unification_request_receipt.json, patron_home_unification_cleanup.json, patron_home_unification_preservation.json and patron_home_unification_changed_files.json. Screenshots are in patron_home_unification_screenshots, including global_before, global_after, global_home_viewport, test_home_viewport, test_for_you, empty_fallback and one_local_book.

```
GLOBAL_HOME_COMPONENTS_REUSED: YES
SEPARATE_LIBRARY_HOME_REMOVED: YES
TEST_HOME_USES_SHARED_HOME: YES
GLOBAL_HOME_CHANGED: NO
TEST_LOCAL_BOOK_COUNT: 150
TEST_PRIMARY_RAIL_LOCAL_BOOK_PERCENT: 100
TEST_GLOBAL_FILLER_IN_PRIMARY_RAILS: 0
EMPTY_LIBRARY_FALLBACK_VALIDATED: YES
LOCAL_SWITCHOVER_VALIDATED: YES
FOR_YOU_LIBRARY_SCOPED: YES
NEW_ARRIVALS_LIBRARY_SCOPED: YES
POPULAR_LIBRARY_SCOPED: YES
GENRES_LIBRARY_SCOPED: YES
BROWSE_LIBRARY_SCOPED: YES
SEARCH_LIBRARY_SCOPED: YES
GLOBAL_5M_PRESERVED: YES
GLOBAL_HNSW_REBUILT: NO
GLOBAL_KG_REBUILT: NO
```
