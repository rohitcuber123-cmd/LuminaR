# Post-2H product regression completion — PASS

Analytics, authorized online-book actions, mixed-format independence, shared controls, current TEST count and metric definitions are repaired/verified. All 30 acceptance gates pass. Actual Chromium completed 39 flow checks and 60 layout/control/viewer checks across all six requested sizes.

| Final QA field | Result |
|---|---|
| FINAL_STATUS | PASS |
| ANALYTICS_ROOT_CAUSE | Intentional online-only CN has no physical holding; old allocation guard incorrectly treated that as corruption. Creation-provenance-aware validation now preserves physical reconciliation checks. |
| ANALYTICS_HTTP_STATUS_AFTER | 200 |
| ANALYTICS_TEST_LIBRARY_PASS | YES |
| ANALYTICS_EMPTY_ACTIVITY_PASS | YES |
| ONLINE_ONLY_TITLE_TESTED | CN |
| ONLINE_ONLY_READ_ACTION | YES |
| ONLINE_ONLY_REQUEST_ACTION | NO |
| ONLINE_ONLY_VIEWER_PASS | YES |
| PHYSICAL_ONLINE_TITLE_TESTED | TEST Reading Circle Discussion Notes |
| PHYSICAL_ONLINE_REQUEST_ACTION | YES |
| PHYSICAL_ONLINE_READ_ACTION | YES |
| ONLINE_ACCESS_INDEPENDENT_OF_PHYSICAL_STOCK | YES |
| SHARED_BOOK_CAPABILITY_RESOLVER | YES |
| STAFF_CATALOGUE_DROPDOWN_THEMED | YES |
| ANALYTICS_RANGE_DROPDOWN_THEMED | YES |
| TEST_CANONICAL_BOOK_COUNT | 151 |
| TEST_EXTRA_RECORD_ID | e5ad68eb-efc2-446f-8132-ab2db9ce12bd |
| TEST_EXTRA_RECORD_TITLE | CN |
| TEST_EXTRA_RECORD_CLASSIFICATION | INTENDED_TEST_RECORD |
| TEST_ACCEPTED_BASELINE_AFTER_REVIEW | 151 |
| INTELLIGENCE_SEARCH_STATUS | READY |
| INTELLIGENCE_SEARCH_ELIGIBLE_COUNT | 151 |
| INTELLIGENCE_SEARCH_INDEXED_COUNT | 151 |
| GLOBAL_HNSW_REBUILT | NO |
| GLOBAL_KG_REBUILT | NO |
| BACKEND_TESTS_PASS | 521 |
| FRONTEND_TESTS_PASS | 842 |
| RESPONSIVE_CHECKS_PASS | 60 |
| BUILD | PASS |
| LINT_ERRORS | 0 |
| PART_2I_STARTED | NO |

Evidence is in the twelve requested `post2h_*` reports, the canonical TEST accepted baseline, XML/logs, before/after screenshots and `post2h_product_final_qa.json`. Backend total covers the five complete scoped suites; the full frontend default suite passes 842, followed by 51 focused checks after final test-fixture updates. Build passes, lint has zero errors and 14 pre-existing warnings.

All TEST canonical record/holding/asset/intelligence collection hashes remain identical. TEST intelligence file SHA-256 checks, 196 global artifact file metadata checks, 5M global catalogue, personal RAG logical snapshot and protected model/router/build sources remain unchanged. CN was preserved; no TEST rebuild was needed because Search and KG already index 151 from the current dataset. QA stock/resources belong to a separate disposable library and its newly created account is disabled.

Limitations: generated global personal saves retain their accepted GLOBAL_WORK identity; they do not invent a tenant holding in explicit global Reading List context. Multi-resource selection is bounded/paginated. Existing unrelated lint/bundle-size advisories remain. No new product domain or Part 2I was started; no git commit was made.
