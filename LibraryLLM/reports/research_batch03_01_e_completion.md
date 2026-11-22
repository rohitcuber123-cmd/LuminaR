# LuminaR Batch 03/01 / Prompt E — Tenant publication safety

## A. Result

**PARTIAL.** The isolated suite published and served both targets. Four correctness defects remain in protected recovery or publication code. No application, test or protected-contract source was changed.

## B. Current source baseline

The starting working tree at `606f0dfce3970bea8e6fc2b62d243433d1a66b8a` included Prompt A, C, D and Part 2Q changes. Preflight recorded 1,719 hashes and dirty status. Parts 01 and 03 supplied the historical questions and experimental criteria. Current source and actual execution supersede their source-only observations.

## C. Isolation

All writes used task-owned MongoDB 8.3 loopback ports different from 27017, a unique OS temporary root and run ID, and synthetic catalogue identities. Search and KG live under separate kind directories inside that root. Child workers checked the run marker, port, database and artifact root before loading application code. The harness used Windows process termination only on the verified worker PID. Setup and fault logs have run-specific names. Test-run databases, directories and subprocesses were cleaned up. The regression suite used its own MongoDB process with legacy fixture defaults remapped to that process.

## D. Search job state machine

`backend/services/library_intelligence_store.py:request_build` checks current verified account and tenant ADMIN both outside and inside the barrier. It deduplicates effective jobs per tenant and target. The job and target become QUEUED. `claim` serializes on the tenant barrier and CASes the job to RUNNING/DATASET with a new fence and a 90-second lease. The target becomes BUILDING. `heartbeat` renews under the same live fence, every 10 seconds in `TenantIntelligence.run_one`.

`dataset` checks authority and lease, collects and fingerprints eligible records and reuses or persists a matching dataset. Dataset states include PREPARING, READY and FAILED. The Search worker produces normalized 384-dimensional embeddings and a FAISS HNSW index in a tenant Search temporary directory. The manifest records identity, source generation, model parameters and file hashes. The job becomes VALIDATING, the files are checked, and `os.replace` publishes the directory name. The job becomes PUBLISHING. Inside the tagged tenant barrier, the worker rechecks lease, requester authority and current fingerprint before CASing the target pointer. It records `published_by_job_id`, previous pointer and digest. The job then persists SUCCEEDED/COMPLETE with `effective_active=false`, removes target job/fence fields, and releases the barrier.

Serving depends on a current, authorized target observation, the published pointer and artifact identity, and canonical hydration. A temporary or renamed directory alone has no serving authority. An active durable lock blocks tenant reads during the pointer/acknowledgement window. Status can report NOT_BUILT, QUEUED, BUILDING, VALIDATING, READY, EMPTY, STALE, FAILED or RECOVERY_REQUIRED. A retained prior pointer can remain valid without being eligible for native serving after a failed attempt. Prompt D tenant-local fallback remains in place.

## E. KG job state machine

KG shares the job, lease, fingerprint, validation, barrier and recovery protocol. It produces `graph.json` with typed book and metadata nodes and edges under the KG kind. Its target and active pointer are separate from Search. `library_intelligence_service.graph` checks current membership, validates the KG target and filters graph book nodes against the current eligible library catalogue. Non-READY KG returns an empty scoped response. Global Graph Lab is separate.

## F. Clean native publication

One synthetic owned book produced one Search and one KG generation. The same source fingerprint was used, and the target, job, generation and manifest identities were distinct. Both jobs completed and both pointers were READY. `artifacts.validate` accepted both outputs. Scoped native Search returned the owned book and scoped KG returned its node. The raw record includes library UUID, job and generation IDs, lease fields, manifest and source digests, publication timestamps and before/after pointers.

## G. Concurrent claims and request retries

Both targets produced exactly one winning claimant under two threads. Concurrent Search requests returned 202 and 503 and the retry returned the original job. KG returned 202 and 202 with the same job ID. A restart did not reclaim the still-leased job. The same request header with two target payloads produced two distinct target jobs. The build endpoint does not implement an Idempotency-Key contract. Observed deduplication is active job per tenant/target, rather than replay protection after completion.

## H. Crash injection

The completed worker matrix records 28 scenarios, 24 pass and four fail. Successful boundaries included before claim, after claim, enumeration, dataset snapshot, embedding or KG construction hooks, before manifest write, validation after manifest write, before rename, after rename, pre-pointer publication, and post-pointer/pre-acknowledgement. Early queued work could be claimed after restart. Claimed failures remained owned until expiry and explicit recovery. Unpublished candidates stayed inactive. A valid pointer committed before acknowledgement was retained and reconciled to SUCCEEDED.

Four follow-up HTTP trials reproduced two status/recovery failures per target. A terminal success with the tagged lock retained caused Staff status 503 and recover 409. Killing the worker after the barrier insert and before tagging caused Staff status 503 and recover 503. The first mixed-target HTTP run also observed that the older locked QUEUED job prevented the later job from reaching its failpoint. KG HTTP trials were completed in a separate fresh lab. The failed first PID-harness run and initial concurrent-request harness run are retained as execution errors, rather than counted as completed fault scenarios.

Controlled lease expiry was applied in the disposable database for recovery tests. The process-kill results describe abrupt Windows worker termination, rather than OS power loss or Mongo process failure. The fault workers used the deterministic fixture encoder and real native artifact writers. The clean build alone used real MiniLM.

## I. Lease and fencing

A held lease rejected explicit recovery with 409. A former worker paused before publication and resumed after explicit recovery and a successor publication. It failed its fence and the successor pointer hash matched after resumption for both targets. The real renewal thread reached an injected renewal exception for both targets after approximately 10.1 seconds, marked HEARTBEAT_LOSS, and reconciled to FAILED without moving last-good. The two-write recovery crash below remains unresolved.

## J. Source fingerprints

Both targets published the updated snapshot when a title changed before capture. Local and linked acquisitions, title, author, subject, global enrichment, and withdrawal during the build stopped publication with the prior pointer intact. A change after pointer persistence made the next observation STALE despite the successful build receipt. Prompt D independently demonstrated current local-only acquisition visibility and withdrawal from actual fallback. These are boundary observations, rather than event latency guarantees.

## K. Revoked ADMIN publication

Revocation before claim, downgrade during the build, disabled account at validation, suspension before publication, and forged or foreign requester IDs all failed without moving the old pointer on both targets. Targeted role and full regression fixtures cover private invitation proof, outsider denial and platform/tenant separation. HTTP fixtures inject the test identity and use the real membership and account checks.

## L. Artifact validation

Seventeen owned corruption trials covered missing and truncated manifests, wrong library or generation, source fingerprint, checksum, model, dimensions, missing/corrupt FAISS, and malformed graph. Every direct validator rejected the input and status observed RECOVERY_REQUIRED with the pointer unchanged. The raw records retain each boundary and pointer hash. Incomplete temporary directories and namespace/traversal checks are also in the regression inventory. A distinct post-validation injection demonstrated that a corrupted new manifest can still displace the pointer before serving rejects it.

## M. Last-good preservation

Known encoder, construction, write, validation, source-conflict, lease-loss and pre-pointer process-kill failures preserved the prior pointer and/or directory as applicable. The post-validation corruption counterexample moved the pointer and marked the new job SUCCEEDED. Its prior directory remained on disk and was referenced as previous. The corrupt candidate was not reported READY by target observation. Retention does not prove continued native serving.

## N. Search/KG isolation

Clean builds used the same canonical source snapshot with distinct target pointers and artifact kinds. Cross-target generation validation rejected the Search UUID as KG. Different target requests and failed-target tests preserved independent state. Existing cross-tenant status, metadata and path tests passed. No global generation or existing tenant generation was rebuilt.

## O. Status and Staff UI

The `PUBLISH` crash snapshots contain 100% stage progress while the prior pointer still owns serving state. Staff UI labels that percentage as stage progress and distinguishes latest attempt, active artifact and source status. Its focused regression groups are part of the full frontend run. The catalogue badge uses `search_source` to describe effective retrieval. Source review found no use of the earlier `intelligence_status` field to claim a native result in the Prompt D race. Live browser polling against the protected production-like stack was not run.

## P. Performance

One book, one build per target on the AMD Ryzen 7 260. MiniLM revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, CPU, two Torch threads, Torch 2.11.0+cu128 and FAISS 1.14.3. Cache-local model initialization took 511.125 ms. The Search job took 683.403 ms, including 503.110 ms in the Search builder and 473.455 ms in build encoding. A subsequent query encoding took 17.953 ms. The KG job took 125.337 ms with 5.530 ms in the graph builder. First build-time validations took 32.913 ms Search and 29.141 ms KG. Artifacts totaled 4,978 and 1,848 bytes respectively. The raw process tests record time to termination and recovery per trial. Publication time is recorded in pointer timestamps. Isolated publication duration, peak memory, repeated warm/cold loads, and latency percentiles were not measured.

## Q. Confirmed defects

| ID | Exact failure | Source |
|---|---|---|
| E-01 | Terminal SUCCEEDED and inactive job leaves a tagged lock. Status is blocked and recover claims a live lease even after controlled expiry. | `search/library_intelligence.py:TenantIntelligence.run_one`, success CAS then lock release. `backend/services/library_intelligence_service.py:recover` only considers effective active jobs in the tagged-lock branch. |
| E-02 | Recovery dies after rotating the target fence and before rotating the job fence. A retry using the old job fence cannot update the target and keeps returning 409. | `backend/services/library_intelligence_service.py:recover`, consecutive target and job fence writes without a persisted resumable intent. |
| E-03 | Post-validation manifest identity corruption passes through rename, gets a new digest, moves the active pointer and marks SUCCEEDED. The read side then rejects it. | `search/library_intelligence.py:TenantIntelligence.run_one`, validation before rename and a fresh digest after rename without final identity validation before CAS. |
| E-04 | A crash after the durable barrier is inserted but before the separate intelligence tag write leaves an untagged lock. Recover correctly refuses unsafe takeover, while the job and tenant remain blocked. | `backend/services/library_intelligence_store.py:intelligence_barrier` and `backend/services/institution_repository.py:library_mutation`. |

## R. Exact repair approval required

Approve review of the following narrow changes before any protected edit. The current service and store are frozen by `tests/contracts/staff_boundary_v2o3.json`. The worker AST and store hash are protected by `tests/institution_v2l/test_native_protocol.py`. No manifest was regenerated and no candidate source was applied.

1. **E-01** Permit idempotent cleanup of a terminal tagged intelligence lock in `recover`. Require current tenant ADMIN, matching job, holder and target, completed receipt, elapsed lease, matching published generation and full artifact validation. Clear only matching job/fence metadata and release only the exact tagged holder. Preserve the pointer. Test crashes both before and after target-job cleanup.
2. **E-02** Persist a recovery intent with the original and next fence on the exact tagged lock under CAS. Make the two fence writes replayable for the exact job, target and holder. Release only after both writes are verified. Prove concurrent recovery and late-worker behavior. An unrelated token, untagged lock or unknown holder still blocks.
3. **E-03** At the protected publication boundary, compare against the validated manifest digest and validate the finalized file set and generation identity before pointer CAS. Preserve authority, lease, source and fence checks. Add corruption cases around rename and publication. A hostile local writer with arbitrary artifact access remains a separate trust-boundary question.
4. **E-04** Add a narrowly scoped insertion-time intelligence job tag to the generic durable barrier and use it only from the worker claim/dataset/publication paths with known job identity. Keep non-intelligence lock behavior intact. Existing untagged locks remain ineligible for automatic removal. Test a crash after the insert but before the next operation, plus queued-job recovery and unrelated tenant work.

Review and hash only the approved changes and affected contract entries before application. Preserve both frozen suites and their mutation coverage. There is no approval request to recover real tenant jobs.

## S. Before/after invariants

The recorded before/after snapshots are **fault-injection states**, not repaired-source results. They preserve starting pointer, fingerprint, job/fence and lock, observed failure, explicit recovery and final pointer. No post-repair invariant claim is made.

## T–V. Regression, build and lint

| Check | Actual result |
|---|---|
| Full backend, 38 groups | 3,191 passed / 0 failed / 20 skipped |
| Full frontend | 1,032 passed / 0 failed / 0 skipped |
| Protected contracts | 75 passed / 0 failed / 0 skipped |
| Production build | PASS |
| Lint | PASS, 16 warnings |
| Isolated experiment scenarios | 86 pass / 10 fail across 96 completed scenarios |
| Disposable cleanup | 9 runs recorded stopped Mongo and removed temporary root |

## W. Preservation and cleanup

All 1,719 starting source fingerprints matched after the run. Prompt A, C, D and Part 2Q source was retained. The read-only comparison matched existing tenant target/job/generation digests, Mongo indexes and communications, Global HNSW pointers, and Global KG artifact metadata. Only task-owned native fixtures were built or recovered. Production Mongo remains NOT_QUALIFIED. No production auth or telemetry changes, resident service restarts, existing generation rebuilds, deployments or commits occurred.

## X. Research claim limitations

One small native build per target and synthetic failures establish only the tested invariants. No large-scale throughput, production reliability, universal fault tolerance or data-isolation guarantee is supported. No Mongo server crash, power loss, hardware-storage failure or real model crash was exercised. Corpus size and production behavior remain outside this evaluation.

## Y. Unresolved risks

Four defects remain open pending protected-contract review. Untagged locks cannot be safely recovered through the existing intelligence endpoint. A stuck oldest queued job can delay other claim attempts. Pending datasets and orphan generation directories may remain after termination. Their existence gives no serving authority.

## Z. Next engineering step

Review E-01 and E-02 together against the raw recovery reproductions. Qualify the idempotent recovery protocol on both targets before approving implementation. Keep E-03 and E-04 as independently reviewable protected changes.

## Raw evidence

- [Current working-tree baseline](research_batch03_01_e_preflight.json)
- [Clean native Search and KG](research_batch03_01_e_native_20261106_01_scenarios.jsonl)
- [Worker and recovery process kills](research_batch03_01_e_crash_20261106_02_scenarios.jsonl)
- [Concurrency, authority, fingerprints and publication faults](research_batch03_01_e_matrix_20261106_02_scenarios.jsonl)
- [Artifact corruption and renewal](research_batch03_01_e_integrity_20261106_01_scenarios.jsonl)
- [Search HTTP status and recovery](research_batch03_01_e_status_20261106_01_scenarios.jsonl)
- [KG HTTP status and recovery](research_batch03_01_e_status_20261106_02_scenarios.jsonl)
- [Preservation hashes](research_batch03_01_e_preservation.json)
- [Full backend](institution_v2q_research_batch03_01_e_backend.json)
- [Full frontend, build and lint](institution_v2q_research_batch03_01_e_front_frontend.json)

## Final QA

```json
{
  "BATCH03_01_PROMPT_E": "PARTIAL",
  "NATIVE_SEARCH_BUILD": "PASS",
  "NATIVE_KG_BUILD": "PASS",
  "CONCURRENT_CLAIMS": "PASS",
  "CRASH_RECOVERY": "PARTIAL",
  "LEASE_FENCING": "PARTIAL",
  "SOURCE_FINGERPRINT": "PASS",
  "REVOKED_ADMIN_PUBLICATION": "PASS",
  "MANIFEST_INTEGRITY": "FAIL",
  "LAST_GOOD_PRESERVATION": "FAIL",
  "SEARCH_KG_TARGET_ISOLATION": "PASS",
  "STAFF_STATUS": "PARTIAL",
  "CROSS_TENANT_SECURITY": "PASS",
  "EXISTING_GENERATION_POINTERS": "UNCHANGED",
  "GLOBAL_HNSW_REBUILT": "NO",
  "GLOBAL_KG_REBUILT": "NO",
  "EXISTING_TENANT_INDEX_REBUILT": "NO",
  "PROTECTED_RAG_CHANGED": "NO",
  "PRODUCTION_AUTH_CHANGED": "NO",
  "PRODUCTION_TELEMETRY_ENABLED": "NO",
  "BACKEND": {
    "passed": 3191,
    "failed": 0,
    "skipped": 20
  },
  "FRONTEND": {
    "passed": 1032,
    "failed": 0,
    "skipped": 0
  },
  "BUILD": "PASS",
  "LINT": "PASS",
  "NEW_REGRESSIONS": 0,
  "DEPLOYED": "NO",
  "COMMITTED": "NO",
  "production_mongo": "NOT_QUALIFIED",
  "protected_contracts": {
    "passed": 75,
    "failed": 0,
    "skipped": 0
  },
  "lint_warnings": 16,
  "backend_group_errors": [],
  "frontend_check_errors": [],
  "scenario_counts": {
    "native_20261106_01": {
      "PASS": 1
    },
    "crash_20261106_02": {
      "PASS": 24,
      "FAIL": 4
    },
    "matrix_20261106_02": {
      "PASS": 41,
      "FAIL": 2
    },
    "integrity_20261106_01": {
      "PASS": 20
    },
    "status_20261106_01": {
      "FAIL": 2
    },
    "status_20261106_02": {
      "FAIL": 2
    }
  },
  "owned_cleanup_runs": 9,
  "scenario_totals": {
    "PASS": 86,
    "FAIL": 10
  },
  "confirmed_defects": [
    "E-01",
    "E-02",
    "E-03",
    "E-04"
  ]
}
```
