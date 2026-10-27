# Institution Part 2G completion — PASS

**A. FINAL** — PASS

**B. GLOBAL SEARCH AUDIT** — Existing semantic text/checksum concepts reused; global builders/default paths never executed.

**C. GLOBAL KG AUDIT** — Existing term/feature/relationship primitives reused; global SQLite/artifacts and ranking remain frozen.

**D. TENANT DATASET GENERATION MODEL** — Immutable UUID generations, per-library sequence, metadata fingerprint, counts/schema/time and checksums.

**E. DATASET ELIGIBILITY RULES** — Canonical ACTIVE nonblank metadata, local/global-linked/Physical/Online/Both; no document/member activity.

**F. SOURCE FINGERPRINT** — Deterministic sorted normalized indexed metadata + schema SHA-256.

**G. STALE DETECTION** — Indexed metadata changes mark stale; circulation/stock do not. First observed time, local fallback.

**H. BUILD JOB ARCHITECTURE** — Independent durable Search/KG targets; partial unique effective-active job, lease and publication fences.

**I. BUILD AUTHORIZATION** — Fresh ADMIN LibraryMembership; Librarian status-only, platform/legacy-only denied.

**J. ARTIFACT STORAGE** — Canonical UUID namespaces under separate local-data/library-intelligence root; no raw HTTP downloads.

**K. SEARCH INDEX ARCHITECTURE** — Resident all-MiniLM-L6-v2 384 normalized vectors + same resident cross-encoder reranker; canonical hydration.

**L. HNSW PARAMETERS** — M16, efConstruction80, efSearch64, 120 neighbors, 60 reranked candidates.

**M. EMBEDDING INPUT / CACHE** — Metadata-only semantic_text; separate per-tenant model/schema/input-hash cache with vector checksum.

**N. SEARCH VALIDATION** — Namespace, manifest/source/checksum, dimension/norm, exact IDs, HNSW vector reconstruction and parameters.

**O. SEARCH ATOMIC PUBLISH** — Private directory, validation, rename and single guarded Mongo CAS pointer; acknowledgement recovery.

**P. SEARCH ROUTING** — Global stays global; authorized READY library route uses tenant vectors.

**Q. STALE SEARCH BEHAVIOR** — Current role-permitted local canonical lexical catalogue; no global filler from missing/stale index.

**R. TENANT KG ARCHITECTURE** — Canonical Book/Author/Subject/Classification metadata graph; deterministic existing relations.

**S. KG VALIDATION** — Complete node/edge rederivation and checksums; no private content.

**T. KG ATOMIC PUBLISH** — Same guarded target publication mechanism, independent KG job/pointer.

**U. KG ROUTING** — Read-only scoped Patron/Staff graph, truthful not-ready state, separate global Graph Lab.

**V. LAZY LOADING** — Zero tenant startup loading; only authorized current validated generation loads.

**W. MEMORY / CACHE** — Per target cache max3 entries/256 MiB estimated retained bytes; A/B/C/A eviction and RSS measured.

**X. FAILURE INJECTION** — Snapshot, encoding/cache, FAISS/KG serialization, checksum/manifest/validation/publish, ack loss, crash/heartbeat.

**Y. RECOVERY** — Exact Admin job repair fences old publisher and clears only expired intelligence-tagged barrier.

**Z. RECONCILIATION** — Dry-run corruption/orphan/temporary/missing-pointer/source mismatch/unknown job checks; no deletion.

**AA. TEST SEARCH BUILD** — READY, 150 vectors, generation 1d12b814-fb98-465d-89c8-3f6194a14fd0

**AB. TEST KG BUILD** — READY, 1093 nodes/1111 edges, generation 1ea21ff2-af3c-4092-b81e-f1a4dda6a98c

**AC. LOCAL-ONLY SUPPORT** — PASS; TEST/local QA metadata does not require global work ID.

**AD. ONLINE-ONLY SUPPORT** — PASS using accepted disposable format library; no chunks in catalogue embeddings/graph.

**AE. MULTI-LIBRARY ISOLATION** — Real A/B/C/A builds/queries; same global work has distinct canonical local IDs, zero foreign results.

**AF. SECURITY** — Fresh guards, UUID containment, private artifact/status boundaries, valid platform-only denial.

**AG. PERFORMANCE** — Real 1000-book Search+KG 9.36s; median query 1114.7ms.

**AH. REAL-BROWSER VALIDATION** — Chromium151: 11 flows, 36 workspace +78 controls +18 badge viewport cases.

**AI. BACKEND TESTS** — 2130 passed, 10 skipped, 0 failed; 82 Part 2G.

**AJ. FRONTEND TESTS** — 857 passed (687+22+148); final affected 90 also pass.

**AK. REGRESSION** — 22 frozen product/backend groups; no Router research rerun. Global/Patron/Staff UI preserved.

**AL. PRESERVATION** — TEST books/holdings/assets exact SHA; personal registry logical snapshot unchanged; global count5M.

**AM. GLOBAL HNSW PRESERVATION** — 196 protected artifacts exact size/mtime unchanged; global builder never invoked.

**AN. GLOBAL KG PRESERVATION** — Protected artifacts and global KG/ranking source SHA unchanged.

**AO. EXACT FILES CHANGED** — See institution_v2g_changed_files.json; excludes unrelated pre-existing work.

**AP. REPORTS CREATED** — All 29 requested named reports plus browser matrices, logs, XML, fixtures and completion manifest.

**AQ. KNOWN LIMITATIONS** — See limitations below; no unsupported large-scale throughput claim.

**AR. IMPROVEMENT REVIEW** — Twenty review recommendations only; none starts another phase.

**AS. EXACT PART 2H RECOMMENDATION** — Explicit Admin-only Search/KG Build/Rebuild status/progress UI reusing durable backend; wait for user approval.

## Final QA summary

| Field | Result |
|---|---|
| TEST_LIBRARY_BOOK_COUNT | 150 |
| TEST_HOLDING_COUNT | 150 |
| TEST_DATASET_GENERATION_ID | 8ea9f568-22ce-4bf1-8e8b-69a98ba21509 |
| TEST_DATASET_BOOK_COUNT | 150 |
| TEST_SEARCH_STATUS | READY |
| TEST_SEARCH_GENERATION_ID | 1d12b814-fb98-465d-89c8-3f6194a14fd0 |
| TEST_SEARCH_VECTOR_COUNT | 150 |
| TEST_SEARCH_HNSW_M | 16 |
| TEST_SEARCH_EF_CONSTRUCTION | 80 |
| TEST_SEARCH_EF_SEARCH | 64 |
| TEST_SEARCH_ARTIFACT_SIZE | 585890 |
| TEST_SEARCH_LOCAL_ONLY_PASS | YES |
| TEST_SEARCH_ONLINE_ONLY_PASS | YES — real dedicated format fixture; no TEST mutation |
| TEST_SEARCH_GLOBAL_FILLER_COUNT | 0 |
| TEST_KG_STATUS | READY |
| TEST_KG_GENERATION_ID | 1ea21ff2-af3c-4092-b81e-f1a4dda6a98c |
| TEST_KG_NODE_COUNT | 1093 |
| TEST_KG_EDGE_COUNT | 1111 |
| TENANT_ARTIFACT_LAZY_LOADING | YES |
| CROSS_LIBRARY_SEARCH_LEAK | NO |
| CROSS_LIBRARY_KG_LEAK | NO |
| GLOBAL_BOOK_COUNT | 5000000 |
| GLOBAL_HNSW_REBUILT | NO |
| GLOBAL_KG_REBUILT | NO |
| ADMIN_BUILD_BUTTONS_IMPLEMENTED | NO |
| LIBRARY_FOR_YOU_LEFT_RIGHT_ARROWS | YES |
| LIBRARY_FOR_YOU_PREVIOUS_NEXT | YES |
| LIBRARY_RECOMMENDATIONS_TENANT_SCOPED | YES |
| LIBRARY_VIEW_ALL_PRESERVES_CONTEXT | YES |
| GLOBAL_LIBRARY_RAIL_COMPONENTS_CONVERGED | YES |
| NOTIFICATION_BADGE_ALIGNED | YES |
| SAVED_BADGE_ALIGNED | YES |
| HEADER_BADGES_MOBILE_PASS | YES |
| PATRON_DROPDOWNS_THEMED | YES |
| STAFF_DROPDOWNS_THEMED | YES |
| CATALOGUE_FILTERS_THEMED | YES |
| SHARED_FORM_CONTROL_SYSTEM | YES |

## Known limitations

- 50,000 records / 64 MiB dataset maximum; 150 and 1000 measured, no 100k build or automatic tuning.
- Metadata-only deterministic KG; bounded per-request Book-node slice, no private document/member graph.
- Serialized HNSW storage plus measured Python retained object size bounds each cache; native allocator high-water RSS can persist.
- Reconciliation is dry-run by default; recover only explicit jobs. No orphan retention deletion, schedules or distributed workers.
- Badges use display-only count fixtures; the saved header icon retains its accepted mobile-hidden behavior.
- Platform closed-control styling audited against existing Platform workspace wrappers and shared primitive; this phase creates no new platform authority or control flow.
- Windows memory pressure required serialized regression/model runs and a user restart of the original MongoDB service. The final database preservation recheck passed.

## Exact source/test files changed

- `backend/main.py`
- `backend/routes/library_intelligence.py`
- `backend/services/library_intelligence_artifacts.py`
- `backend/services/library_intelligence_service.py`
- `backend/services/library_intelligence_store.py`
- `frontend/package.json`
- `frontend/src/App.tsx`
- `frontend/src/components/CatalogueSurface.tsx`
- `frontend/src/components/ForYou.tsx`
- `frontend/src/components/Header.tsx`
- `frontend/src/components/MetadataGraphCanvas.tsx`
- `frontend/src/components/Notifications.css`
- `frontend/src/lib/institutions.ts`
- `frontend/src/lib/libraryCatalogue.ts`
- `frontend/src/pages/KnowledgeGraphPage.tsx`
- `frontend/src/pages/LibraryCatalogue.tsx`
- `frontend/src/pages/LibraryGraph.tsx`
- `frontend/src/styles/workspaces.css`
- `frontend/tests/institution-intelligence.test.tsx`
- `frontend/tests/library-catalogue.test.tsx`
- `frontend/tests/search-depth.test.tsx`
- `scripts/build_library_kg_v2g.py`
- `scripts/build_library_search_v2g.py`
- `scripts/institution_v2g_artifact_review.py`
- `scripts/institution_v2g_baseline.py`
- `scripts/institution_v2g_browser.py`
- `scripts/institution_v2g_browser_finish.py`
- `scripts/institution_v2g_completion.py`
- `scripts/institution_v2g_final_smoke.py`
- `scripts/institution_v2g_frontend_checks.py`
- `scripts/institution_v2g_live_build.py`
- `scripts/institution_v2g_live_validation.py`
- `scripts/institution_v2g_regressions.py`
- `scripts/institution_v2g_reports.py`
- `scripts/library_intelligence_cli.py`
- `scripts/reconcile_library_intelligence_v2g.py`
- `scripts/recover_library_intelligence_v2g.py`
- `search/api.py`
- `search/library_intelligence.py`
- `search/library_intelligence_api.py`
- `tests/institution_v2g/conftest.py`
- `tests/institution_v2g/test_intelligence.py`
- `tests/institution_v2g/test_validation_recovery.py`
- `tests/test_document_rag_latency.py`

## Reports

- `reports/institution_v2g_artifact_audit.md`
- `reports/institution_v2g_artifact_storage.md`
- `reports/institution_v2g_atomic_publish.json`
- `reports/institution_v2g_backend.xml`
- `reports/institution_v2g_baseline.json`
- `reports/institution_v2g_benchmark.json`
- `reports/institution_v2g_browser.json`
- `reports/institution_v2g_build_jobs.json`
- `reports/institution_v2g_cache.json`
- `reports/institution_v2g_changed_files.json`
- `reports/institution_v2g_completion.json`
- `reports/institution_v2g_completion.md`
- `reports/institution_v2g_completion_progress.json`
- `reports/institution_v2g_contract_repairs.xml`
- `reports/institution_v2g_cross_tenant.json`
- `reports/institution_v2g_dataset_architecture.md`
- `reports/institution_v2g_dataset_generation.json`
- `reports/institution_v2g_embedding_cache.md`
- `reports/institution_v2g_final_smoke.json`
- `reports/institution_v2g_fixtures.json`
- `reports/institution_v2g_frontend_results.json`
- `reports/institution_v2g_hnsw_parameters.md`
- `reports/institution_v2g_improvement_review.md`
- `reports/institution_v2g_job_reuse_audit.md`
- `reports/institution_v2g_kg_architecture.md`
- `reports/institution_v2g_kg_builder_audit.md`
- `reports/institution_v2g_kg_routing.json`
- `reports/institution_v2g_lazy_loading.json`
- `reports/institution_v2g_memory.json`
- `reports/institution_v2g_online_only.json`
- `reports/institution_v2g_part2h_scope.md`
- `reports/institution_v2g_patron_graph_1024.png`
- `reports/institution_v2g_patron_graph_1366.png`
- `reports/institution_v2g_patron_graph_1440.png`
- `reports/institution_v2g_patron_graph_375.png`
- `reports/institution_v2g_patron_graph_390.png`
- `reports/institution_v2g_patron_graph_768.png`
- `reports/institution_v2g_patron_home_1024.png`
- `reports/institution_v2g_patron_home_1366.png`
- `reports/institution_v2g_patron_home_1440.png`
- `reports/institution_v2g_patron_home_375.png`
- `reports/institution_v2g_patron_home_390.png`
- `reports/institution_v2g_patron_home_768.png`
- `reports/institution_v2g_patron_search_1024.png`
- `reports/institution_v2g_patron_search_1366.png`
- `reports/institution_v2g_patron_search_1440.png`
- `reports/institution_v2g_patron_search_375.png`
- `reports/institution_v2g_patron_search_390.png`
- `reports/institution_v2g_patron_search_768.png`
- `reports/institution_v2g_performance.json`
- `reports/institution_v2g_preservation.json`
- `reports/institution_v2g_reconciliation.json`
- `reports/institution_v2g_recovery.json`
- `reports/institution_v2g_regression.json`
- `reports/institution_v2g_regression_assistant.xml`
- `reports/institution_v2g_regression_catalogue_experience.xml`
- `reports/institution_v2g_regression_circulation.xml`
- `reports/institution_v2g_regression_dashboard_authority.xml`
- `reports/institution_v2g_regression_events.xml`
- `reports/institution_v2g_regression_institution_v1.xml`
- `reports/institution_v2g_regression_institution_v2a.xml`
- `reports/institution_v2g_regression_institution_v2b.xml`
- `reports/institution_v2g_regression_institution_v2c.xml`
- `reports/institution_v2g_regression_institution_v2d.xml`
- `reports/institution_v2g_regression_institution_v2e.xml`
- `reports/institution_v2g_regression_institution_v2f.xml`
- `reports/institution_v2g_regression_institution_v2g.xml`
- `reports/institution_v2g_regression_kg.xml`
- `reports/institution_v2g_regression_notifications.xml`
- `reports/institution_v2g_regression_private_knowledge_ocr.xml`
- `reports/institution_v2g_regression_product_consistency.xml`
- `reports/institution_v2g_regression_search.xml`
- `reports/institution_v2g_regression_security.xml`
- `reports/institution_v2g_regression_staff.xml`
- `reports/institution_v2g_regression_unit.xml`
- `reports/institution_v2g_regression_workspace_authorization.xml`
- `reports/institution_v2g_search_architecture.md`
- `reports/institution_v2g_search_builder_audit.md`
- `reports/institution_v2g_search_routing.json`
- `reports/institution_v2g_security.json`
- `reports/institution_v2g_staff_graph_1024.png`
- `reports/institution_v2g_staff_graph_1366.png`
- `reports/institution_v2g_staff_graph_1440.png`
- `reports/institution_v2g_staff_graph_375.png`
- `reports/institution_v2g_staff_graph_390.png`
- `reports/institution_v2g_staff_graph_768.png`
- `reports/institution_v2g_staff_home_1024.png`
- `reports/institution_v2g_staff_home_1366.png`
- `reports/institution_v2g_staff_home_1440.png`
- `reports/institution_v2g_staff_home_375.png`
- `reports/institution_v2g_staff_home_390.png`
- `reports/institution_v2g_staff_home_768.png`
- `reports/institution_v2g_staff_search_1024.png`
- `reports/institution_v2g_staff_search_1366.png`
- `reports/institution_v2g_staff_search_1440.png`
- `reports/institution_v2g_staff_search_375.png`
- `reports/institution_v2g_staff_search_390.png`
- `reports/institution_v2g_staff_search_768.png`
- `reports/institution_v2g_stale_detection.json`
- `reports/institution_v2g_validation.json`

Part 2G only. No Build/Rebuild frontend buttons, automatic schedules, incremental HNSW/KG mutation, distributed workers or later phase implemented. No commit.
