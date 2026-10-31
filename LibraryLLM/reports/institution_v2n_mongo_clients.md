# Mongo clients and connection behavior

Baseline scan parsed 1308 Python files, found 66 constructor sites; no parse failures. Current scan and symbols are in client_inventory.json. All client arguments are recorded as names/options, never URI values.

| Source | Function | Classification |
|---|---|---|
| `tests/institution_v2j/test_diagnostics.py:93` | test_mongo_reader_server_enforces_no_job_write | tests |
| `tests/institution_v2k/test_telemetry.py:88` | test_operator_read_only_credential_preserved | tests |
| `backend/database/mongodb.py:16` | <module> | runtime |
| `search/maintenance.py:44` | main | runtime |
| `search/luminar_search.py:250` | __init__ | runtime |
| `backend/scripts/migrate_inventory.py:38` | migrate_inventory | operator/script |
| `backend/scripts/migrate_5m_books.py:34` | connect_mongodb | operator/script |
| `backend/services/library_worker_telemetry.py:71` | __init__ | runtime |
| `backend/services/library_operator_access.py:96` | connect_operator | runtime |
| `tests/institution_v2l/test_writer_security.py:95` | test_unauthorized_read_and_writer_denied | tests |
| `scripts/build_lexical_sidecar.py:46` | main | operator/script |
| `scripts/benchmark_semantic_sync.py:126` | main | operator/script |
| `scripts/check_dashboard_convergence_live.py:26` | main | operator/script |
| `scripts/check_frontend_workspace_live.py:26` | main | operator/script |
| `scripts/check_institution_v1_live.py:32` | main | operator/script |
| `scripts/check_institution_v2a_live.py:38` | main | operator/script |
| `scripts/check_institution_v2b_live.py:31` | main | operator/script |
| `scripts/check_patron_home_unification_live.py:24` | main | operator/script |
| `scripts/check_library_workspaces.py:26` | main | operator/script |
| `scripts/check_institution_v2c_live.py:32` | main | operator/script |
| `scripts/check_library_catalogue_live.py:26` | main | operator/script |
| `scripts/check_product_consistency_live.py:24` | main | operator/script |
| `scripts/cleanup_product_consistency_fixtures.py:14` | main | operator/script |
| `scripts/evaluate_lexical_expanded.py:70` | main | operator/script |
| `scripts/evaluate_full_lexical.py:234` | main | operator/script |
| `scripts/institution_v2d_migration.py:72` | run | operator/script |
| `scripts/institution_v2d_baseline.py:33` | capture | operator/script |
| `scripts/full_product_inventory.py:34` | baseline | operator/script |
| `scripts/full_product_browser_closure_reports.py:71` | preservation | operator/script |
| `scripts/full_product_browser_baseline.py:34` | capture | operator/script |
| `scripts/finalize_full_product_evidence.py:21` | main | operator/script |
| `scripts/full_product_correct_baseline.py:11` | <module> | operator/script |
| `scripts/institution_v2i_baseline.py:41` | capture_state | operator/script |
| `scripts/institution_v2j_fixture.py:25` | __enter__ | operator/script |
| `scripts/institution_v2j_fixture.py:36` | __enter__ | operator/script |
| `scripts/institution_v2k_native.py:44` | main | operator/script |
| `scripts/institution_v2l_baseline.py:13` | capture_indexes | operator/script |
| `scripts/institution_v2l_native.py:39` | main | operator/script |
| `scripts/institution_v2m_host_audit.py:16` | mongo_audit | operator/script |
| `scripts/institution_v2m_host_audit.py:17` | mongo_audit | operator/script |
| `scripts/institution_v2m_rollout.py:87` | main | operator/script |
| `scripts/migrate_institution_v1.py:120` | main | operator/script |
| `scripts/measure_lexical_schemas.py:131` | main | operator/script |
| `scripts/library_catalogue_experience_baseline.py:25` | <module> | operator/script |
| `scripts/lexical_worker.py:39` | main | operator/script |
| `scripts/lexical_maintenance.py:53` | main | operator/script |
| `scripts/inventory_v2a_migration.py:198` | main | operator/script |
| `scripts/product_consistency_waitlist_stock.py:19` | main | operator/script |
| `scripts/product_consistency_live_fixture.py:29` | main | operator/script |
| `scripts/product_consistency_inspect.py:7` | <module> | operator/script |
| `scripts/report_institution_v2b.py:115` | main | operator/script |
| `scripts/report_institution_v2a.py:64` | main | operator/script |
| `scripts/report_dashboard_convergence.py:148` | main | operator/script |
| `scripts/reconcile_inventory_v2a.py:87` | main | operator/script |
| `scripts/run_isolated_worker_lexical.py:100` | main | operator/script |
| `scripts/run_isolated_search_api_lexical.py:51` | run | operator/script |
| `scripts/run_isolated_core_lexical.py:40` | run | operator/script |
| `scripts/report_product_consistency.py:90` | main | operator/script |
| `scripts/report_patron_home_unification.py:69` | main | operator/script |
| `scripts/report_navigation_context.py:70` | main | operator/script |
| `scripts/report_library_catalogue_experience.py:61` | main | operator/script |
| `scripts/report_institution_v2c.py:100` | main | operator/script |
| `scripts/patron_home_unification_baseline.py:25` | <module> | operator/script |
| `scripts/navigation_context_baseline.py:25` | <module> | operator/script |
| `scripts/platform_completion_baseline.py:32` | main | operator/script |
| `scripts/seed_test_library_collection.py:90` | main | operator/script |

Five baseline runtime client sites are backend/database/mongodb.py, search/luminar_search.py, search/maintenance.py, library_worker_telemetry.py and library_operator_access.py. N consolidates the first three constructors behind backend/database/mongo_configuration.py. Multiple helper constructors in the current inventory include the authenticated connection and short-lived deny-only probe; they do not create another resident worker.

Core/RAG/Recommendation/native credential source: MONGO_URI/MONGO_DB_NAME after dotenv load; Search formerly used equivalent defaults with a separate pool. Legacy development permits MongoClient(None) or localhost default. Explicit authenticated mode now requires username/password, URI database equal to explicit selected DB, explicit authSource, supported SCRAM and bounded qualification. Invalid login never reaches the anonymous deny probe or an application fallback. Pool and steady-state retry semantics stay with PyMongo defaults/callers; only authenticated startup gains 3s selection/connect bounds and a10s qualification deadline.

Backend imports create the reading_list unique index immediately. Core lifespan creates more indexes and starts existing due/outbox workers unless explicitly disabled in a fixture. Search initializes IndexManager and resident tenant builds after model startup. Manual maintenance is an operator action, never executed globally here. Telemetry remains exact flag1 plus dedicated URI, pool2, acknowledged journaled writes and500ms bounds. Operator requires explicit loopback SCRAM URI and one DB-local builtin-read role; it imports no application index initializer.

Tests and historical/controlled scripts also connect directly. Their full line/function records appear above and in the machine inventory. Migration/seed/import scripts can write, index or drop their owned databases; none is automatically production-approved by the new application mode. They require individual approved maintenance wrappers and the appropriate explicit DB. Existing historical test fixtures retain anonymous loopback test configuration and are unchanged. Exec-generated prior harnesses are identified by their source templates; runtime trace supplements static scanning.

INVENTORY COMPLETENESS: repository constructor/config/import sites audited; exact deployed process graph and all dynamically selected collection/action edges are NOT fully qualified. MONGO_CLIENT_INVENTORY_COMPLETE remains NO under the request's exact minimum-per-process standard. Supplementary scan limitations and unresolved dynamic paths remain explicit. No Motor runtime constructor found.
