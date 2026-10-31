# LuminaR Institutions Part 2I — final report

Generated 2026-10-29T19:15:52.506953+00:00. Project root `D:\SDC\LibraryLLM`. All measurements are local fixture evidence unless explicitly described as read-only current production observation.

## A. FINAL RESULT

PARTIAL. Two preexisting frozen regression failures (protected RAG hash drift and global lexical API fixture HTTP 500); no new regression failures.

## B. PART 2I EXECUTIVE SUMMARY

Review-first source/baseline/performance audit, one production-file efficiency change, full policy/recovery/incremental reviews and isolated native/browser regressions. No commit or activation.

## C. EXISTING ARCHITECTURE

Actual paths/classes/routes/collections/fields/barriers/fences/ownership: [architecture](institution_v2i_architecture.md).

## D. FRESHNESS DETECTION CALL GRAPH

Staff status → fresh scoped authority → tenant barrier → complete source records/fingerprint → dataset/jobs → independent verified target observations. [Call graph](institution_v2i_freshness_audit.md).

## E. FRESHNESS PERFORMANCE BASELINE

Seven sizes through the real 50,000 bound, plus global-enrichment fixture; median/p90/p95/CPU/memory/DB/profile/checksum work measured. Three fresh application processes per size/version measure first status and startup separately; OS/Mongo caches are not flushed, so these are not cold-disk/server results.

## F. SEARCH FRESHNESS DEPENDENCIES

Embedding text: title/authors/subjects/description/year. Shared source identity and conservative full dataset fingerprint govern freshness. [Exact contract](institution_v2i_freshness_contract.md).

## G. KG FRESHNESS DEPENDENCIES

Book identity/title/global link; canonical author/subject/classification relationships. Shared fingerprint intentionally also invalidates on non-graph source metadata changes.

## H. STATUS OPTIMIZATION DECISION

Reuse verified pointer only within the current response. Reject shared caches/revision shortcuts/coalescing without complete mutation/ownership proofs.

## I. IMPLEMENTED STATUS IMPROVEMENTS

Private _target_observation returns existing response/row/verification. target_status response contract, authorization, fresh fingerprints, full checksums, runtime selection and job state semantics preserved.

## J. STATUS BEFORE/AFTER MEASUREMENTS

| Eligible books | Before median ms | After median ms | Before p95 ms | After p95 ms | Checksum bytes before / after |
|---:|---:|---:|---:|---:|---:|
| 0 | 23.339 | 20.103 | 41.197 | 21.401 | 0 / 0 |
| 1 | 78.429 | 50.409 | 88.137 | 54.179 | 11,964 / 5,982 |
| 10 | 78.196 | 53.144 | 89.863 | 61.832 | 95,650 / 47,825 |
| 100 | 88.079 | 64.154 | 100.105 | 73.781 | 933,014 / 466,507 |
| 1,000 | 152.611 | 110.518 | 186.361 | 123.076 | 9,312,018 / 4,656,009 |
| 10,000 | 796.993 | 725.935 | 837.629 | 758.495 | 93,156,022 / 46,578,011 |
| 50,000 | 3969.336 | 3490.119 | 4564.188 | 3562.193 | 466,036,022 / 233,018,011 |

## K. CONCURRENT STATUS SAFETY

One Admin, multiple Admin browsers, Admin+Librarian and three libraries tested. Same-tenant 503 remains fail-closed; no shared authorization/cache/global lock added. [Measurements](institution_v2i_concurrency.json).

## L. WORKER ARCHITECTURE

One resident daemon, serial oldest-queued job, 90s leases/10s renewal, fenced validation/rename/pointer/ack and exact publication authority. [Worker audit](institution_v2i_worker_audit.md).

## M. BUILD RESOURCE MEASUREMENTS

| Target | Books | First build ms | Unchanged rebuild ms | New generation bytes |
|---|---:|---:|---:|---:|
| SEARCH_INDEX | 10 | 3972.797 | 200.295 | 40,253 |
| SEARCH_INDEX | 100 | 3108.232 | 293.255 | 390,649 |
| SEARCH_INDEX | 1000 | 29790.802 | 1537.511 | 3,895,107 |
| KNOWLEDGE_GRAPH | 10 | 129.993 | 141.036 | 16,388 |
| KNOWLEDGE_GRAPH | 100 | 111.036 | 103.554 | 153,281 |
| KNOWLEDGE_GRAPH | 1000 | 419.258 | 405.468 | 1,523,984 |

Actual cached CPU MiniLM; no downloads. One sample/configuration, real builds at 10/100/1000 records; no GPU or production workload qualification.

## N. WORKLOAD BUDGET POLICY

Future resource estimates/reservations must preserve last-good disk/RAM headroom, inspect worker/queue and block recovery. Candidate diagnostic outcomes only. [Design](institution_v2i_workload_policy.md).

## O. QUEUE FAIRNESS FINDINGS

FIFO created_at, no tie-breaker/preemption/size budget; one large or barrier-blocked oldest tenant can delay others. Same-target duplication returns same job; other target may queue. [Proposal](institution_v2i_queue_fairness.md).

## P. WORKER OBSERVABILITY

Heartbeat is not progress; job presence is not idle liveness; no separate last-progress time. Public whitelist retained, no invented health badge. [Audit](institution_v2i_observability.md).

## Q. RECOVERY DECISION MATRIX

Known prepublish failure vs unknown publication/lease/crash/corrupt pointer covered; explicit existing recovery only. No hardware power-loss certification. [Matrix](institution_v2i_recovery_matrix.md).

## R. FAILED ARTIFACT RETENTION

Private failed generations retained for ownership/outcome reconciliation; no deletion of retained production artifacts. Future operator-approved protected inventory/retention only. [Review](institution_v2i_artifact_retention.md).

## S. CANCELLATION FEASIBILITY

Queued CAS/cooperative prepublication checkpoints would need new durable intent, ownership and audit; no safe cancellation across atomic publication. No endpoint/button added. [Design](institution_v2i_cancellation_design.md).

## T. SUPERVISED REBUILD POLICY DESIGN

Recommend eventual Admin-approved bounded pending intent after authoritative stale/cost review; debounce/window/threshold designs inactive. [Comparison](institution_v2i_supervised_policy.md).

## U. HNSW INCREMENTAL FEASIBILITY

IndexHNSWFlat normalized384, ordinal metadata IDs; add exists but current remove_ids raises not-implemented in actual fixture. No tenant delete/update/tombstone journal. Full generation rebuild retained. [Review](institution_v2i_hnsw_incremental_review.md).

## V. KG INCREMENTAL FEASIBILITY

Shared canonical features need provenance/reference accounting, deterministic labels/orphan removal and whole-generation equivalence. Full rebuild retained. [Review](institution_v2i_kg_incremental_review.md).

## W. SEARCH RUNTIME PRESERVATION

Unchanged query/ranking/model/reranking/hydration source; READY semantic vs non-READY tenant-local fallback verified. Archived/current target responses compared across states.

## X. KG RUNTIME PRESERVATION

Unchanged schema/extraction/traversal; failed rebuild leaves last-good generation; READY graph intersects current usable tenant books, non-READY safe empty notice.

## Y. RECOMMENDATION DEPENDENCIES

Global recommendations call global Search with MACHINE contract; tenant recommendations intersect global candidates and fill canonical local records, independent of tenant HNSW/KG READY. [Dependency graph](institution_v2i_recommendation_dependencies.md).

## Z. AUTHORIZATION

Fresh identity/JWT and exact current membership. ADMIN controls, Librarian reads, General User Staff denial, Platform-only no tenant bypass. No decisions cached. [Security evidence](institution_v2i_security.json).

## AA. MULTI-LIBRARY ISOLATION

UUID predicates/artifact namespace/barriers preserved. Actual delayed browser A response cannot replace B; foreign status/build/job/artifact visibility tests retained.

## AB. FRONTEND VALIDATION

Existing page/design/polling unchanged. Abort, token/library keying, terminal-stop/focus/manual refresh and serialized tenant helpers retained. Hidden tabs are not specially paused; no visibility optimization was introduced.

## AC. BACKEND TESTS

2320 passed / 2 failed (preexisting) / 20 skipped; new focused 60/60. Baseline failures persist openly; no historical hashes/tests rebased.

## AD. FRONTEND TESTS

943 passed / 0 failed / 0 skipped in 32 subprocess groups. Production build PASS; lint PASS with preexisting warnings.

## AE. BROWSER QA

Actual Chromium PASS, 22 steps, zero JS page errors, focused axe zero violations, 1440/1024/390/375 widths. Real ASGI/JWT/Mongo/native worker via bridged HTTP; unrelated services/decorative external assets stubbed, not deployed-network qualification. Four expected 404 console resource messages correspond to explicit denial/revocation tests.

## AF. REGRESSION

Frozen V1/2A–2H operational product suites, Staff/Platform/catalogue/Search/KG/recommendations/assets/RAG/knowledge/Assistant/events/notifications/analytics, frontend/build/lint executed. No Router research/training.

## AG. GLOBAL PRESERVATION

Preservation PASS; TEST 151 eligible / 150 holdings / 5 assets. Indexed generation counts remain 151. Global count 5,000,000; no global rebuild. Tenant hashes, institution row digests and protected file metadata/logical registries checked. [Evidence](institution_v2i_preservation.json).

## AH. EXACT FILES CHANGED

Only production file: `D:\SDC\LibraryLLM\backend\services\library_intelligence_service.py`. Exact added tests/scripts/reports, hashes and historical generated-report restoration are in [changed files](institution_v2i_changed_files.json). Existing user work and HEAD preserved; no commit.

## AI. REPORTS CREATED

All 29 requested reports plus bounded implementation plan, raw before/paired/concurrency/workload evidence, final QA, logs/XML/screenshots and package. Exact inventory below and in changed-files report.

## AJ. KNOWN LIMITATIONS

Two preexisting frozen regression failures (protected RAG hash drift and global lexical API fixture HTTP 500); no new regression failures. Status remains O(catalogue+artifact bytes); exact physical disk/cold-server costs unmeasured. Real build benchmarks limited to 1000 CPU records, one sample/configuration; no GPU/large-tenant SLO. Existing barrier 503, serial queue, idle-liveness/admission/cancellation/retention gaps remain. SQLite handle teardown is GC-dependent in existing VectorCache; production code unchanged. One task-created temporary benchmark folder remains: C:\Users\balak\AppData\Local\Temp\luminar-v2i-build-pf4vn_p3. Automatic approval review rejected recursive cleanup (blocked by policy).

## AK. IMPROVEMENT REVIEW

Measured duplicate work removed without replacing authority/freshness/runtime semantics. More ambitious optimization/policy work stays documented, inactive and separately scoped. [Review](institution_v2i_improvement_review.md).

## AL. RECOMMENDED NEXT PHASE

Part 2J: operator-only read-only worker liveness and recovery diagnostics; no automatic actions. Stop after Part 2I and review this report; no next-phase code started.

## Final QA summary

```text
PART_2I_RESULT: PARTIAL
PART_2H_PRESERVED: YES
FRESHNESS_COST_MEASURED: YES
SEARCH_FRESHNESS_CONTRACT_VERIFIED: YES
KG_FRESHNESS_CONTRACT_VERIFIED: YES
STATUS_OPTIMIZATION_IMPLEMENTED: YES
STATUS_OPTIMIZATION_SAFE: YES
STATUS_MEDIAN_BEFORE_MS: 3969.336
STATUS_MEDIAN_AFTER_MS: 3490.119
STATUS_P95_BEFORE_MS: 4564.188
STATUS_P95_AFTER_MS: 3562.193
FALSE_READY_CASES: 0
WORKER_LIFECYCLE_VERIFIED: YES
WORKLOAD_BUDGET_DESIGNED: YES
QUEUE_FAIRNESS_REVIEWED: YES
RECOVERY_MATRIX_COMPLETE: YES
LAST_GOOD_GENERATION_PRESERVED: YES
SUPERVISED_POLICY_DESIGNED: YES
AUTOMATIC_REBUILD_IMPLEMENTED: NO
SCHEDULED_REBUILD_IMPLEMENTED: NO
INCREMENTAL_HNSW_IMPLEMENTED: NO
INCREMENTAL_KG_IMPLEMENTED: NO
DISTRIBUTED_WORKERS_IMPLEMENTED: NO
JOB_CANCELLATION_IMPLEMENTED: NO
AUTOMATIC_RECOVERY_IMPLEMENTED: NO
GLOBAL_HNSW_REBUILT: NO
GLOBAL_KG_REBUILT: NO
SEARCH_RANKING_CHANGED: NO
RECOMMENDATION_RANKING_CHANGED: NO
QWEN_CHANGED: NO
ASSISTANT_ROUTER_CHANGED: NO
BACKEND_TESTS: 2320 passed / 2 failed (preexisting) / 20 skipped
FRONTEND_TESTS: 943 passed / 0 failed / 0 skipped
BROWSER_QA: PASS
PRODUCTION_BUILD: PASS
FINAL_RECOMMENDED_NEXT_PHASE: Part 2J: operator-only read-only worker liveness and recovery diagnostics; no automatic actions.
```

Performance summary fields use the 50,000-record paired fixture; zero false READY applies only to executed correctness fixtures. Worker verification means isolated native lifecycle/fault tests, not live production process liveness.

## Evidence inventory

- reports/institution_v2i_acceptance.json
- reports/institution_v2i_architecture.md
- reports/institution_v2i_artifact_retention.md
- reports/institution_v2i_backend_tests.json
- reports/institution_v2i_baseline.json
- reports/institution_v2i_baseline_backend.json
- reports/institution_v2i_baseline_frontend.json
- reports/institution_v2i_browser.json
- reports/institution_v2i_cancellation_design.md
- reports/institution_v2i_cold_process.json
- reports/institution_v2i_concurrency.json
- reports/institution_v2i_executed_institution_v2e_backend_benchmark.json
- reports/institution_v2i_final_backend.json
- reports/institution_v2i_final_frontend.json
- reports/institution_v2i_final_qa.json
- reports/institution_v2i_freshness_audit.md
- reports/institution_v2i_freshness_benchmark.json
- reports/institution_v2i_freshness_benchmark_before.json
- reports/institution_v2i_freshness_benchmark_concurrency.json
- reports/institution_v2i_freshness_benchmark_empty.json
- reports/institution_v2i_freshness_benchmark_paired.json
- reports/institution_v2i_freshness_benchmark_smoke.json
- reports/institution_v2i_freshness_contract.md
- reports/institution_v2i_frontend_tests.json
- reports/institution_v2i_hnsw_incremental_review.md
- reports/institution_v2i_implementation_plan.md
- reports/institution_v2i_improvement_review.md
- reports/institution_v2i_kg_incremental_review.md
- reports/institution_v2i_next_scope.md
- reports/institution_v2i_observability.md
- reports/institution_v2i_preservation.json
- reports/institution_v2i_queue_fairness.md
- reports/institution_v2i_recommendation_dependencies.md
- reports/institution_v2i_recovery_matrix.md
- reports/institution_v2i_regression.json
- reports/institution_v2i_security.json
- reports/institution_v2i_status_optimization.md
- reports/institution_v2i_supervised_policy.md
- reports/institution_v2i_worker_audit.md
- reports/institution_v2i_workload_benchmark.json
- reports/institution_v2i_workload_policy.md
