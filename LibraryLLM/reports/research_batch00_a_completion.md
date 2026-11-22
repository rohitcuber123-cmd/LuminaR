# LuminaR research remediation, Batch 00 / Prompt A

**Disposition** PASS. **Production MongoDB qualification** NOT_QUALIFIED.

## Checkpoint and evidence

The branch was `codex/search-v11-finalization` at `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`. HEAD happens to match the October 31 research snapshot. The working tree does not. The current-tree preflight recorded the dirty status, 1,678 fingerprints, selected dotenv gate presence, and installed FastAPI 0.139.2, Starlette 1.3.1, PyMongo 4.17.0 and Uvicorn 0.51.0, under Python 3.11.9 and Node v26.5.0. Current Assistant, notification and recommendation sources were carried forward byte-for-byte. The earlier Part 2N central Mongo gate and Parts 2P–2Q authority and behavior fixes were treated as existing implementation. The six named research files were reconciled with current traces and their hashes are in the preservation record.

Evidence classes used here are SOURCE_OBSERVATION for traced code, FRESH_TEST for current isolated execution, REAL_RUNTIME for the five existing loopback HTTP listeners, FIXED_IN_LATER_PHASE for the earlier central Mongo gate, and PRODUCTION_UNVERIFIED for deployment behavior.

## 00-A-LIFECYCLE — REAL BUG

- **Initial evidence.** October 31 technical evidence and open questions flagged Core's custom lifespan and legacy startup callback. Current `backend/main.py` still had both. `backend/services/library_intelligence_store.py:initialize` creates sequence, generation, job and target indexes, including the partial unique active-job constraint. `search/library_intelligence.py` separately initializes the store inside the native worker.
- **Reproduction and cause.** An isolated FastAPI application with the same registration pattern recorded only custom lifespan enter and exit under the installed versions. Its legacy callback never ran. Search worker startup could mask the missing Core initialization depending on service order. Core can accept tenant traffic independently, so worker initialization did not establish Core readiness.
- **Repair.** Core's `lifespan` now awaits the existing initializer in a thread before starting either notification worker. The legacy registration was removed. Initializer contents, both worker start/stop sequences, and native Search startup are preserved. The store's identical index definitions remain idempotent.
- **After and security impact.** Authenticated disposable Core starts with the sequence uniqueness and active-job partial index in place at the first health response. Repeated and concurrent lifespan entry succeeded. A separate barrier-synchronized probe started Core and the actual tenant worker against fresh index namespaces. Both succeeded, the unique partial job index existed, and the idle worker shut down with zero jobs and zero artifacts. The worker used a stub encoder. An injected initialization failure prevented serving and prevented both workers from starting. Invalid authenticated Mongo configuration prevented importing Core before its reading-list index operation. Existing Core workers remain flag-gated in the fixture. The live Core process was left running on its resident code.
- **Remaining limits.** This qualifies application lifecycle with isolated Mongo and controlled failure. Live process rollout and production worker readiness remain unverified.

## 00-A-LISTENER — FOREIGN LISTENER MISCLASSIFICATION

- **Initial evidence and cause.** `scripts/start_local.py:launch` previously treated a successful TCP connect as an existing service. Any listener on one of the expected ports could satisfy that condition.
- **Repair.** `scripts/local_service_identity.py:matches_service` performs a bounded-size, timed, unauthenticated loopback HTTP read. FastAPI checks advertised OpenAPI title and version. Vite checks LuminaR, its development client, and the expected entrypoint markers. Foreign, wrong-version, redirected and malformed responses fail the check. The launcher stops on an occupied unverified HTTP port and retains ownership-only cleanup. Matching listeners remain running with an explicit warning that checkout, readiness and ownership are unverified. For an already-running Mongo listener it still reports TCP occupancy only. A Mongo port race during an owned start raises rather than adopting that listener.
- **Fresh tests and runtime.** Seven disposable HTTP listener cases passed. All five existing listeners separately matched their public fingerprints. Existing Core and RAG reported healthy and Search reported degraded. Probes used GET requests without cookies or credentials. The launcher was not run against the shared stack and no process was stopped or started there.
- **Remaining limits.** A public service can advertise matching metadata. The check distinguishes typical foreign listeners and stale advertised versions. It cannot attest a checkout, dependencies, authorized process ownership or end-to-end readiness. The existing Core/RAG health status is not a dependency attestation. Search health can express index degradation independently. Recommendation has no equivalent dedicated health endpoint.

## 00-A-MONGO — CONNECTION PATH COVERAGE

The central guard requires an explicit matching database, SCRAM credentials and authSource, verifies the authenticated identity and authorized database, then performs a deny-only anonymous probe. It rejects a configured authenticated target that still permits the probe. Core and Recommendation import `backend.database.mongodb`, which qualifies first and creates the reading-list index later. Importing that module against a resident database is therefore unsuitable as a read-only check. This work made no Mongo policy or deployment changes.

| Connection path | Current policy | Authenticated-mode qualification in this batch |
|---|---|---|
| Core and its due/outbox workers, shared application DB | `backend/database/mongodb.py` → `mongo_configuration.settings/connect` | Core real disposable startup and import failure. Fixture principal read, write, index creation and prohibited admin actions exercised. Notification startup flags disabled for disposable probes. Worker behavior also covered by product regressions. |
| Recommendation API | Same shared client from `recommendation/api.py` | Disposable authenticated import and HTTP OpenAPI success. Invalid credentials rejected before startup. Recommendation request behavior covered by product regressions. |
| Search server and its native tenant worker | `search/luminar_search.py:LuminaRSearchEngine.__init__` uses central settings/connect for the global pool. Tenant store shares the application DB. | Common connection gate and native protocol tests exercised. A new model-backed Search server was not started. Standalone native worker credential fixture operations qualify the exercised DB actions only. |
| Search maintenance worker and lexical sidecar CLI | `search/maintenance.py:main` worker branch and `scripts/build_lexical_sidecar.py` use the central gate. Maintenance status/sync/rebuild commands operate on the local queue and do not open a Mongo connection in those branches. | Worker with invalid credentials stopped before model construction. Positive long-running maintenance and sidecar build NOT_RUN. |
| RAG, Assistant and private asset paths | Shared Mongo through application services where required. Assistant also uses Core/Search HTTP and separate application authorization. | Shared client and scoped product tests apply. No fresh model-backed authenticated RAG startup. Protected code unchanged. |
| Local operator read diagnostics | `backend/services/library_operator_access.py:connect_operator` deliberately uses a dedicated loopback authenticated principal and verifies its scoped read role. | Real disposable reader read succeeded and write was denied. Separate credentials kept backend-side. |
| Optional worker telemetry | `backend/services/library_worker_telemetry.py:Actor` uses a dedicated gated client and checks authenticated privileges. | Disposable restricted principal operation tests passed within the focused suite. Production enablement and deployment actor exercise NOT_RUN. |
| Shared-client offline CLI and migration paths | Local seed, catalogue graph, book/category/user migration, library asset/lending/management migration, and RAG mapping clients import the central shared DB. | Source classification only for these commands. No CLI mutations, builds or migrations executed. |
| Direct legacy/offline clients | `backend/scripts/migrate_5m_books.py:connect_mongodb`, `backend/scripts/migrate_inventory.py`, `scripts/inventory_v2a_migration.py`, `scripts/institution_v2d_migration.py`, `scripts/migrate_institution_v1.py`, `scripts/reconcile_inventory_v2a.py` and `scripts/seed_test_library_collection.py` construct their own clients. | Not covered by the central application gate on those direct branches. Source-only. None is a resident server/worker entry point. Execution ownership, current supported use and least privilege were not established, so the historical/offline commands were left unchanged. |
| Audit/fixture clients | Explicit direct clients under test, lab, preservation and evaluation tooling, including the `check_*_live.py` validation scripts and lexical evaluation utilities. Core session DB uses SQLite. | Disposable fixture authentication and read-only local observation only. |

The focused authentication suite exercised anonymous denial, bad credentials, wrong auth source and database, valid login with an unrelated role, authorized read/write, and absence of unrestricted fallback. A trusted fixture admin was used for provision and teardown. Tenant JWT and membership were checked independently. The protected production endpoint, network, TLS/certificate, proxy, deployed identity, principal coverage and least-privilege grant set remain **NOT_QUALIFIED**.

## Authority and preservation

`backend/dependencies.py` authenticates the application JWT and refuses legacy account roles as authority. `backend/institution_dependencies.py` resolves active membership and accepted invitation proof before role gates. Staff requires active ADMIN or LIBRARIAN membership, member actions use the patron boundary, and nonmembers receive concealment on protected resources. `backend/platform_dependencies.py` requires a current account and a valid, approved platform assignment. That assignment is separate from tenant access. Role, canonical context, private RAG and native protocol assertions were exercised by the existing backend inventory. The disposable Mongo application credential did not confer a valid application JWT.

Source reconciliation found exactly five source/test paths changed, listed with before/after hashes in the preservation record. Read-only checks compared observed global and tenant artifacts, index metadata and tenant data to the previously verified reference. No production Mongo authorization or telemetry changes, no live restart, no index rebuild, no model replacement, no protected RAG edit, no deployment, commit or rollback.

## Regression and cleanup

| Suite | Current actual tree | November 5 reference |
|---|---:|---:|
| Backend, 38 groups | 3,162 passed, 0 failed, 20 skipped | 3,151 passed, 0 failed, 20 skipped |
| Frontend | 1,032 passed, 0 failed, 0 skipped | 1,032 passed, 0 failed, 0 skipped |
| Build | PASS | PASS |
| Lint | PASS, 16 warnings | PASS, 16 warnings |

Independent protected-contract suite passed all 75 tests. No new backend failures. No new frontend failures. 

Focused suite **35 passed**, with one dependency deprecation warning. Separate connection probes recorded three passes and no credential output. Full backend tests used a dedicated loopback MongoDB 8.3.4 and redirected only legacy test fixture transport defaults to that process. The independent authenticated fixture retained its own principals and process. Test bodies and guard assertions were not suppressed. The existing 2O suite also replays the two new Core tests through its own authenticated fixture.

The full regression mongod stopped and its temporary filesystem root was removed. Separate connection probe fixtures also stopped and removed their roots. No credential-bearing Mongo URI was found in 51 captured logs.

- [Preflight and source fingerprints](research_batch00_a_preflight.json)
- [Changed files, research hashes and preservation](research_batch00_a_preservation.json)
- [Resident listener observation](research_batch00_a_listener_observation.json)
- [Focused Mongo and lifecycle test log](research_batch00_a_focused.log)
- [Concurrent Core and native worker probe](research_batch00_a_concurrent_startup.json)
- [Disposable connection-path probes](research_batch00_a_connection_probes.json)
- [Backend results](institution_v2q_research_batch00_a_backend.json)
- [Frontend results](institution_v2q_research_batch00_a_front_frontend.json)
