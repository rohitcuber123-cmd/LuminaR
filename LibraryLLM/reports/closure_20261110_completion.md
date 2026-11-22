# LuminaR Consolidated Engineering Defect Repair and Closure Report

**Run Namespace:** `closure_20261110`  
**Branch:** `codex/search-v11-finalization`  
**HEAD:** `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`  
**Primary Report:** [closure_20261110_completion.md](file:///D:/SDC/LibraryLLM/reports/closure_20261110_completion.md)  
**Machine-Readable QA:** [closure_20261110_qa.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_qa.json)

---

## A. Executive Summary & Overall Closure Verdict

**CLOSURE STATUS: COMPLETE WITH EXPLICITLY RECORDED FROZEN-RAG & ACCESSIBILITY BOUNDARIES.**

All four authorized critical defects in the tenant Search and Knowledge Graph (`SEARCH_INDEX` and `KNOWLEDGE_GRAPH`) publication and recovery subsystem (**`E-01`**, **`E-02`**, **`E-03`**, **`E-04`**) were reproduced before patching (`0/8` passing in [closure_20261110_before_repro.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_before_repro.json)), minimally repaired inside authorized scope, and verified fixed (`8/8` passing after patching in [closure_20261110_after_repro.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_after_repro.json), `41/41` passing in [`test_publication_recovery_closure.py`](file:///D:/SDC/LibraryLLM/tests/institution_v2g/test_publication_recovery_closure.py), and `20/20` state-machine scenarios `A`–`T` passing in [closure_20261110_recovery_matrix.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_recovery_matrix.json)).

Directly affected native protocol and deployment protection metadata (`staff_boundary_v2o3.json` and three contract assertion test files) were updated narrowly to reflect the exact repaired signatures and invariants while keeping all protected contract tests green (`75/75` in `institution_v2o3_closure`, `67/67` in `institution_v2o3`, `67/67` in `institution_v2o2`). Additional high-value closure coverage was added and verified for circulation/fee concurrency (`institution_v2c`) and analytics mid-read canonical mutation rejection (`institution_v2e`).

Live GPU Qwen (`Qwen/Qwen2.5-3B-Instruct` 4-bit on `cuda:0`) acceptance (`10/10` HTTP `200`), timeout/contention recovery, live `08-PRIVATE-B` factorial diagnostics, and real Chromium desktop/mobile (`320px`–`1440px`) + `axe-core` E2E checks were all executed directly against isolated task-owned backends. Two remaining non-authorized or UI defects were cleanly isolated and reported without modifying frozen RAG source or application TSX/CSS:
1. **`08-PRIVATE-B` (`CONFIRMED_UNRESOLVED`)**: Root-caused empirically to token-phrasing sensitivity in frozen [`llm.py`](file:///D:/SDC/LibraryLLM/rag/llm.py) (`12 minutes` vs `47 minutes`, `ALPHA-SEVEN` vs `BRAVO-NINE`, `action='record'` vs `'recorded'`) combined with false-`FAST_ACCEPT` gating on `FACTUAL` negation/wrong-field/contradictory claims in [`fast_filter.py`](file:///D:/SDC/LibraryLLM/rag/fast_filter.py). Both files remain unmodified per preservation rules.
2. **Global Catalogue `color-contrast` (`CONFIRMED_UI_DEFECT`)**: Live `axe-core` audit in Chromium passed with `0` violations across `Analytics`, `StaffIntelligence`, and `PrivateCatalogueA`, while flagging `4` serious `color-contrast` violations on `GlobalCatalogue` (`/catalog`).

An **uninterrupted full backend regression** passed with **zero failures** and **zero `WORKER_FENCED` incidents**: **`3246 passed, 0 failed, 20 skipped`** raw grouped + closure executions (`3266` total), corresponding to **`3164 passed, 0 failed, 10 skipped`** deduplicated unique testcases (`3174` unique). Frontend passed **`1033 passed, 0 failed, 0 skipped`** across `35` sub-scripts; production build and `oxlint` passed (`16` existing warnings, `0` errors). All preservation invariants, frozen RAG/global assets, resident tenant collections, and prior historical reports were verified untouched ([closure_20261110_preservation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_preservation.json)).

---

## B. Preflight Baseline, Environment & Source/Data Preservation Audit

Before writing any patch, [closure_20261110_preflight.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_preflight.json) recorded the repository identity, working tree SHA-256 hashes, frozen pins, historical report fingerprints, active feature flags, and resident data baselines:

- **Git Reference:** Branch `codex/search-v11-finalization`, HEAD `606f0dfce3970bea8e6fc2b62d243433d1a66b8a`.
- **Uncommitted Work Preservation:** The repository began with extensive legitimate uncommitted Parts 04–16 changes and prior ingestion/analytics/cache repairs; no `git reset`, `git stash`, or branch clean was performed.
- **Accepted Baseline Reference:** Prior Parts 13–16 initial full backend run had `3116 passed, 1 failed (WORKER_FENCED), 10 skipped` unique (`3198/1/20` raw grouped) and `3117/0/10` after unchanged-source 152-test retry; frontend `1033/0/0`; protected contracts `75/0/0`.
- **Execution Isolation:** Every verification phase ran against an ephemeral, task-owned `mongod` instance and disposable filesystem root via dedicated wrappers, leaving `closure_20261110_*_backend_isolation.json` cleanup receipts confirming process shutdown, root deletion, and `stray_closure_mongo_dbs: []`.
- **Preservation Verification (`closure_20261110_preservation.json`):** Every post-closure check returned `true`:
  - `global_book_count = 5000000`
  - `intelligence_targets = 22`, `intelligence_generations = 15`, `intelligence_jobs = 39` (`37` `SUCCEEDED`, `2` `FAILED`), `intelligence_locks = 0`
  - `33` tenant collection counts unchanged, `181` tenant intelligence files unchanged
  - `141` protected library assets, `196` global HNSW files, `5` global KG files unchanged
  - `14/14` frozen pins matched; `11/11` historical report SHA-256s matched; `.env` and `HEAD` unchanged

---

## C. Priority 1 — E-03: Corrupt Artifact Publication & TOCTOU Closure

**Severity:** Critical Engineering Integrity  
**Status:** **`CONFIRMED_FIXED`**

### Root Cause
Previously, [`TenantIntelligence.run_one`](file:///D:/SDC/LibraryLLM/search/library_intelligence.py) validated the pending generation inside its staging `temporary` directory, moved/renamed to `final`, and then re-computed or accepted a fresh manifest digest when updating the Mongo pointer at publication time. Modifying the staging or renamed `manifest.json` (or artifact files) at or after initial `VALIDATION` / `SERIALIZATION_ACK` allowed the worker to publish an altered manifest under the active pointer and mark the job `SUCCEEDED`, leaving readers to reject the active generation with `RECOVERY_REQUIRED`.

### Required Safety Invariant
Only the exact generation bytes and identity (`library_id`, `target`, `generation_id`, `source_generation_id`, `source_fingerprint`, `job_id`, and `manifest_checksum`) that passed validation before `os.replace(temporary, final)` may become active; any post-validation corruption or identity drift must abort publication, fail the job cleanly, and preserve the previous valid active pointer intact.

### Implemented Repair
1. **[`search/library_intelligence.py`](file:///D:/SDC/LibraryLLM/search/library_intelligence.py) (`TenantIntelligence.run_one`)**:
   - Captures `validated_digest = store.checksum(temporary/'manifest.json')` prior to `VALIDATION` / `SERIALIZATION_ACK`.
   - Re-validates `temporary` against `validated_digest` immediately before `os.replace(temporary, final)`.
   - Re-validates `final` inside [`intelligence_barrier`](file:///D:/SDC/LibraryLLM/backend/services/library_intelligence_store.py) immediately prior to `PUBLISH`.
   - Persists `manifest_checksum: validated_digest` onto the target/generation pointer record.
2. **[`backend/services/library_intelligence_artifacts.py`](file:///D:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py) (`validate`, `ArtifactCache.load`)**:
   - `validate(..., *, expected_manifest_checksum=None, expected_source_generation_id=None, expected_source_fingerprint=None, expected_job_id=None)` reads the raw `manifest.json` bytes once for atomic checksum verification and enforces symlink rejection, extra-entry rejection, and exact expected artifact file verification.
   - `ArtifactCache.load` passes `expected_manifest_checksum=manifest_checksum` when loading active artifacts, preserving reader fail-closed validation.
3. **[`backend/services/library_intelligence_service.py`](file:///D:/SDC/LibraryLLM/backend/services/library_intelligence_service.py) (`pointer_manifest`)**:
   - Reads raw manifest bytes once and enforces `published_by_job_id` verification against the pointer metadata.

### Before vs After Evidence
- **Before ([closure_20261110_before_repro.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_before_repro.json)):** Tampering with `library_id` in the owned `manifest.json` at `SERIALIZATION_ACK` on both `SEARCH_INDEX` and `KNOWLEDGE_GRAPH` resulted in job `SUCCEEDED`, active pointer moved to the corrupt generation, and reader rejecting with `RECOVERY_REQUIRED` (`FAIL`).
- **After ([closure_20261110_after_repro.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_after_repro.json)):** Both `SEARCH_INDEX` and `KNOWLEDGE_GRAPH` abort before pointer CAS, mark the job `FAILED`, preserve prior active pointers (`PRIOR_RETAINED` verified in Scenario `M`), and never surface a corrupt pointer (`PASS`).

---

## D. Priority 2 — E-01: Terminal Job Retained Lock Reconciliation

**Severity:** High Availability & Recovery Correctness  
**Status:** **`CONFIRMED_FIXED`**

### Root Cause
[`TenantIntelligence.run_one`](file:///D:/SDC/LibraryLLM/search/library_intelligence.py) updated the job document to a terminal state (`SUCCEEDED` or `FAILED`) before releasing the tagged distributed lock (`locks` document), creating a crash window between job completion and lock deletion. Simultaneously, [`library_intelligence_service.recover`](file:///D:/SDC/LibraryLLM/backend/services/library_intelligence_service.py) lacked safe reconciliation for a tagged lock whose owning job had already reached terminal `SUCCEEDED`/`FAILED` and expired, returning HTTP `409` and stranding subsequent intelligence jobs indefinitely. Meanwhile, an unconstrained final `$unset` on the lock risk existed without `fence_token` matching.

### Required Safety Invariant
An expired lock explicitly tagged with `intelligence_job_id` whose owning job is verified terminal (`SUCCEEDED` or `FAILED`)—and whose lease has expired with exact ownership matching—must be cleanly released by `recover`, while active leases or mismatched tokens/fences continue to fail safely; worker completion cleanup must fence final `$unset` by `job['fence_token']`.

### Implemented Repair
1. **[`backend/services/library_intelligence_service.py`](file:///D:/SDC/LibraryLLM/backend/services/library_intelligence_service.py)**: Added `_release_terminal_tagged_lock` and integrated it into `recover`, verifying target validity, `expired(job)`, and terminal `SUCCEEDED`/`FAILED` state before deterministically releasing the retained tagged lock.
2. **[`search/library_intelligence.py`](file:///D:/SDC/LibraryLLM/search/library_intelligence.py)**: Fenced the worker's final `$unset` on the lock using `'fence_token': job['fence_token']` so a stale or fenced worker cannot clear a successor's lock or metadata.

### Before vs After Evidence
- **Before:** Terminating the worker after `SUCCEEDED` commit before lock release left the tagged lock held; explicit recovery after lease expiry returned HTTP `409` on both `SEARCH_INDEX` and `KNOWLEDGE_GRAPH`.
- **After:** Recovery reconciles the terminal job state cleanly, releases the retained tagged lock (`lock: null`), preserves serving readiness (`TENANT_SEMANTIC` / `TENANT_KG` `READY`), and permits new queued jobs (`Scenario E` in recovery matrix).

---

## E. Priority 3 — E-02: Recovery Fencing Consistency & Resumable Recovery Intent

**Severity:** High Recovery Correctness & Fence Integrity  
**Status:** **`CONFIRMED_FIXED`**

### Root Cause
Previously, `recover` updated the target's `fence_token` and the job's `fence_token` / status in two separate non-atomic writes without persisting a resumable intent record. Crashing between updating the target fence and updating the job left the job stuck in `PUBLISHING`, target/job `fence_token` values mismatched, and the tagged lock retained—causing subsequent recovery retries to reject with HTTP `409`.

### Required Safety Invariant
Interrupted multi-document fencing transitions must be idempotently resumable via a durable `recovery_intent` anchored on the `locks` document under exact tagged ownership, completing both target and job fence updates before releasing the lock, while ensuring any stale worker attempting late publication/cleanup with an older `fence_token` is rejected.

### Implemented Repair
1. **[`backend/services/library_intelligence_service.py`](file:///D:/SDC/LibraryLLM/backend/services/library_intelligence_service.py)**: Added `_fence_active_tagged_lock` persisting a durable `recovery_intent` on the `locks` document prior to split-fence mutation. On retry after any crash point, `recover` detects `recovery_intent` on the lock, replays and verifies both target and job fence updates idempotently, marks interrupted active jobs appropriately (`FAILED`), and only then releases the lock.

### Before vs After Evidence
- **Before:** Crashing between target fence bump and job fence update left split fences, stuck `PUBLISHING` state, and HTTP `409` on recovery retries across both `SEARCH_INDEX` and `KNOWLEDGE_GRAPH`.
- **After:** Crash during split-fence write (`Scenario F`: `SPLIT_FENCE_RECOVERY_REQUIRED`) resumes cleanly from `recovery_intent`, aligns fence state, transitions job to `FAILED` (`RECOVERED` / `BUILD_FAILED`), releases the lock, and rejects stale worker actions with `WORKER_FENCED`.

---

## F. Priority 4 — E-04: Pre-Tag Barrier Lock Atomic Insertion

**Severity:** High Concurrency & Barrier Ownership  
**Status:** **`CONFIRMED_FIXED`**

### Root Cause
[`intelligence_barrier`](file:///D:/SDC/LibraryLLM/backend/services/library_intelligence_store.py) previously acquired a generic library mutation lock via [`institution_repository.library_mutation`](file:///D:/SDC/LibraryLLM/backend/services/institution_repository.py) and only afterward ran `$set` to tag the lock with `intelligence_job_id` and `intelligence_target`. Terminating the worker in the window between `locks.insert_one` and the follow-up tag left an untagged lock blocking a `QUEUED` intelligence job, which `recover` had to treat as an unknown generic lock (`503`).

### Required Safety Invariant
Intelligence barrier locks must be inserted atomically with `intelligence_job_id` and verified `intelligence_target` inside `locks.insert_one(doc)`, eliminating the untagged window while continuing to reject truly generic/unknown untagged locks so unrelated tenant catalog/lending mutations are never disrupted.

### Implemented Repair
1. **[`backend/services/institution_repository.py`](file:///D:/SDC/LibraryLLM/backend/services/institution_repository.py)**: Updated `library_mutation(library_id, *, wait_seconds=3, durable=False, intelligence_job_id=None, intelligence_target=None)` to validate UUID format and constrain `intelligence_target` to `('SEARCH_INDEX', 'KNOWLEDGE_GRAPH')`, writing both `intelligence_job_id` and `intelligence_target` directly in `locks.insert_one(doc)`.
2. **[`backend/services/library_intelligence_store.py`](file:///D:/SDC/LibraryLLM/backend/services/library_intelligence_store.py)**: Updated `intelligence_barrier` to supply `intelligence_job_id=canonical(job['job_id'])` and `intelligence_target=job['target']` at lock insertion time instead of performing a separate post-insert `$set`.

### Before vs After Evidence
- **Before:** Stopping inside the barrier before tagging left an untagged lock + `QUEUED` job and returned HTTP `503` on explicit recovery for both `SEARCH_INDEX` and `KNOWLEDGE_GRAPH`.
- **After:** No untagged window exists for intelligence barriers (`Scenario G`: `QUEUED_WITH_BARRIER_LOCK` recovers cleanly to `FAILED`, lock released), while true generic untagged mutation locks remain protected from takeover.

---

## G. Before/After E-01–E-04 Controlled Reproduction Comparison

All eight controlled failpoint reproductions ran against task-owned isolated Mongo ports and disposable directories ([closure_20261110_before_repro.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_before_repro.json), Mongo port `64383`; [closure_20261110_after_repro.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_after_repro.json), Mongo port `51180`):

| Issue | Target | Before Patch Result | After Patch Result |
|---|---|---|---|
| `E-01` | `SEARCH_INDEX` | **FAIL** (Retained lock after `SUCCEEDED`; `recover` returned `409`) | **PASS** (Tagged lock reconciled & released cleanly) |
| `E-01` | `KNOWLEDGE_GRAPH` | **FAIL** (Retained lock after `SUCCEEDED`; `recover` returned `409`) | **PASS** (Tagged lock reconciled & released cleanly) |
| `E-02` | `SEARCH_INDEX` | **FAIL** (Split target/job fence in `PUBLISHING`; `recover` returned `409`) | **PASS** (Resumable `recovery_intent` reconciles both fences & releases lock) |
| `E-02` | `KNOWLEDGE_GRAPH` | **FAIL** (Split target/job fence in `PUBLISHING`; `recover` returned `409`) | **PASS** (Resumable `recovery_intent` reconciles both fences & releases lock) |
| `E-03` | `SEARCH_INDEX` | **FAIL** (Tampered manifest at `SERIALIZATION_ACK` published `SUCCEEDED` -> reader `RECOVERY_REQUIRED`) | **PASS** (Digest/identity mismatch aborts before CAS; job `FAILED`, prior pointer intact) |
| `E-03` | `KNOWLEDGE_GRAPH` | **FAIL** (Tampered manifest at `SERIALIZATION_ACK` published `SUCCEEDED` -> reader `RECOVERY_REQUIRED`) | **PASS** (Digest/identity mismatch aborts before CAS; job `FAILED`, prior pointer intact) |
| `E-04` | `SEARCH_INDEX` | **FAIL** (Untagged barrier lock + `QUEUED` job; `recover` returned `503`) | **PASS** (`intelligence_job_id`/`intelligence_target` inserted atomically; recovers cleanly) |
| `E-04` | `KNOWLEDGE_GRAPH` | **FAIL** (Untagged barrier lock + `QUEUED` job; `recover` returned `503`) | **PASS** (`intelligence_job_id`/`intelligence_target` inserted atomically; recovers cleanly) |

**Reproduction Delta:** `0/8` passing before fixes -> **`8/8` passing** after fixes.

---

## H. Protected Publication/Recovery Test Suite Breakdown (41 New Tests)

A dedicated suite [`tests/institution_v2g/test_publication_recovery_closure.py`](file:///D:/SDC/LibraryLLM/tests/institution_v2g/test_publication_recovery_closure.py) was created and verified via `pytest` against an isolated ephemeral backend (Mongo port `59229`, [closure_20261110_v2gc_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_v2gc_backend_isolation.json)):

- **JUnit Result ([closure_20261110_v2g_closure.xml](file:///D:/SDC/LibraryLLM/reports/closure_20261110_v2g_closure.xml)):** **`41 passed, 0 failed, 0 skipped`** in **`33.83s`**.
- **Scope Verified:**
  - `E-03`: Valid Search and KG generation builds; tampered manifest after validation; altered artifact bytes after validation; wrong `library_id`, wrong `target`, wrong `generation_id`, wrong `source_fingerprint`, wrong `published_by_job_id`, symlink/extra artifact entry, missing required file, checksum mismatch; crash before pointer CAS; crash after pointer CAS; crash before job acknowledgment; concurrent stale worker fencing; reader opening published generation; failed new generation with retained last-good pointer.
  - `E-01`: Terminal `SUCCEEDED` and terminal `FAILED` retained lock reconciliation; active lease denial; mismatched holder/token denial; fenced final `$unset` preventing stale lock removal; idempotent repeated/concurrent recovery.
  - `E-02`: Split-fence crash replay via `recovery_intent`; late former-worker fencing after recovery (`WORKER_FENCED`); concurrent recovery contention.
  - `E-04`: Atomic `intelligence_job_id` + `intelligence_target` lock insertion; UUID and target allowlist validation (`SEARCH_INDEX` / `KNOWLEDGE_GRAPH`); preservation of generic untagged tenant locks against recovery takeover.

---

## I. 20-Scenario Crash & Recovery State Matrix (Scenarios A–T)

Executed end-to-end across Search & KG publication and reader paths and logged in [closure_20261110_recovery_matrix.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_recovery_matrix.json) (**`20/20` PASS**):

| Scenario | Initial / Fault Condition | Observed Outcome | Job Status | Reader / Post-Condition Verification |
|---|---|---|---|---|
| **A** | `NOT_BUILT` | `NOT_NEEDED` | `SUCCEEDED` | Reader `TENANT_SEMANTIC` / `READY` |
| **B** | `NOT_BUILT` (KG build failure) | `FAILED_CLEAN` | `FAILED` (`BUILD_FAILED`) | Reader `TENANT_KG` / `FAILED` |
| **C** | `NOT_BUILT` (Search build failure) | `FAILED_CLEAN` | `FAILED` (`BUILD_FAILED`) | Reader `LOCAL_FALLBACK` / `FAILED` |
| **D** | `NOT_BUILT` (KG recovery success) | `SUCCEEDED` | `SUCCEEDED` (`RECOVERED`) | Reader `TENANT_KG` / `READY` (`node_count: 8`) |
| **E** | `READY_WITH_RETAINED_LOCK` (`E-01`) | `SUCCEEDED` | `SUCCEEDED` | Lock released (`null`); reader `TENANT_SEMANTIC` / `READY` |
| **F** | `SPLIT_FENCE_RECOVERY_REQUIRED` (`E-02`) | `FAILED` | `FAILED` (`RECOVERED`, `BUILD_FAILED`) | Reader `LOCAL_FALLBACK` / `FAILED` |
| **G** | `QUEUED_WITH_BARRIER_LOCK` (`E-04`) | `FAILED` | `FAILED` (`RECOVERED`, `BUILD_FAILED`) | Reader `TENANT_KG` / `FAILED` |
| **H** | `EXPIRED_LOCKED` (`BUILDING`) | `FAILED` | `FAILED` (`RECOVERED`, `BUILD_FAILED`) | Reader `LOCAL_FALLBACK` / `FAILED` |
| **I** | `LEASE_EXPIRED_AT_PUBLISH` | `FAILED` | `FAILED` (`RECOVERED`, `BUILD_FAILED`) | Reader `LOCAL_FALLBACK` / `FAILED` |
| **J** | `SOURCE_MUTATED_MID_BUILD` | `FAILED` | `FAILED` (`BUILD_FAILED`) | Reader `TENANT_KG` / `FAILED` |
| **K** | `ADMIN_REVOKED_MID_BUILD` | `REVOKED_DENIED_404_BACKUP_OK` | `FAILED` | Reader `LOCAL_FALLBACK` / `FAILED` |
| **L** | `LIBRARY_SUSPENDED_MID_BUILD` | `FAILED` | `FAILED` | Reader `http_status: 404` |
| **M** | `PRIOR_READY` (Failed rebuild with corrupt artifact) | `PRIOR_RETAINED` | `FAILED` | `active_generation_id` `3bed885c...` preserved on disk/pointer; reader `LOCAL_FALLBACK` / `FAILED` on failed candidate probe |
| **N** | `NOT_BUILT` (Search build failure fallback) | `LOCAL_FALLBACK` | `FAILED` | Reader `LOCAL_FALLBACK` / `FAILED` |
| **O** | `RECOVERY_REQUIRED` | `FAILED` | `FAILED` (`RECOVERED`) | Reader `TENANT_KG` / `FAILED` |
| **P** | `QUEUED` (Concurrent enqueue dedup) | `DEDUPED_AND_SUCCEEDED` | `SUCCEEDED` | Reader `TENANT_SEMANTIC` / `READY` |
| **Q** | `QUEUED` (Cross-tenant access attempt) | `CROSS_TENANT_DENIED_404` | `SUCCEEDED` | Cross-tenant `404`; owner reader `TENANT_SEMANTIC` / `READY` |
| **R** | `NOT_BUILT_BOTH` (Search + KG) | `BOTH_SUCCEEDED` | `SUCCEEDED` | Both Search & KG `READY` |
| **S** | `BOTH_READY_KG_CORRUPTED` | `ISOLATED_CORRUPTION` | — | Search stays `TENANT_SEMANTIC` / `READY`; KG reports `TENANT_KG` / `RECOVERY_REQUIRED` |
| **T** | `SUBSEQUENT_READY` (Out-of-order / late prior job) | `SUBSEQUENT_PRESERVED` | — | Subsequent generation `fa2ab38a...` retained intact |

---

## J. Protected Metadata Audit & Complete SHA-256 Change Ledger

Every file modified or added during this closure task is accounted for below with exact SHA-256 hashes (preflight reference hashes cross-checked against [research_batch13_16_20261110_preflight.json](file:///D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_preflight.json) and [research_batch13_16_20261110_preservation.json](file:///D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_preservation.json)):

### 1. Authorized Application & Protected Publication/Recovery Repairs (`5` files)
| File | Before SHA-256 | After SHA-256 | Reason |
|---|---|---|---|
| [institution_repository.py](file:///D:/SDC/LibraryLLM/backend/services/institution_repository.py) | `5cf979a7155943dcf2770c2ac5e6fa1d8afcf75970ab1c11d29a76f65a6264f4` | `cd3208a46438b0a2a902ecd558de42b2b9ba3d71d38f005ad307b8571b831a5a` | `E-04`: `library_mutation` validates UUID + target (`SEARCH_INDEX`/`KNOWLEDGE_GRAPH`) and inserts `intelligence_job_id`/`intelligence_target` in `locks.insert_one(doc)` |
| [library_intelligence_store.py](file:///D:/SDC/LibraryLLM/backend/services/library_intelligence_store.py) | `54b5efbba8713ced652bdafa4aa055d05ffa25dfd046c9446580d6d8a22fb153` | `ad33ad7102e2e56d63884ad6f1244e5a2930488d65cc9a3a1e432681ca3a7402` | `E-04`: `intelligence_barrier` passes `intelligence_job_id` & `intelligence_target` at lock insertion instead of post-insert `$set` |
| [library_intelligence_artifacts.py](file:///D:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py) | `79374d4a8a093ab02757f2465ed42b5455c32839bcad73c8eae01872b271c388` | `624c88fcf123bc9218d135969ea7da39a60cf93776b9709e4d1823d2d72b6de7` | `E-03`: Single-read manifest checksum + symlink/extra-entry validation in `validate`; `ArtifactCache.load` binds expected `manifest_checksum` |
| [library_intelligence.py](file:///D:/SDC/LibraryLLM/search/library_intelligence.py) | `ad5323f77b7686ab10c1c6defc081ceb7e26688d204ee8594c2e2fd04693f8d4` | `16da4dc664012f5fdd23eafa581645774aaf345d34aea27d72539c6f45e46b14` | `E-03` & `E-01`: Captures `validated_digest` pre-ack, re-validates temp & `final` inside barrier pre-CAS, stores `manifest_checksum`, fences final `$unset` by `job['fence_token']` |
| [library_intelligence_service.py](file:///D:/SDC/LibraryLLM/backend/services/library_intelligence_service.py) | `f90c4948ea7db781e143d100b7ad6d24e5a698b0c2a10c19c3c1e5c8989a7b01` | `2f9a21f0d34f1f682c06e9813773eaf6a5134910b1949e232601fede495a19af` | `E-01`, `E-02`, `E-03`: Single-byte `pointer_manifest` + `published_by_job_id` check; `_release_terminal_tagged_lock` & `_fence_active_tagged_lock` with durable `recovery_intent` |

### 2. Directly Necessary Protection Metadata & Assertion Updates (`4` files)
| File | Before SHA-256 | After SHA-256 | Scope |
|---|---|---|---|
| [staff_boundary_v2o3.json](file:///D:/SDC/LibraryLLM/tests/contracts/staff_boundary_v2o3.json) | `6ad35f5603f185edd5d5665d2d624f906ebdc8c58fe5c5c306a3d8e7ec727588` (raw) | `d22a4a075f2ce7649797707cfb9e00008a8a0edb5b467321cb112ef7bc1ee245` (raw) / `29fdd0c922cce49f009154b43db70d0fa7b3bdd3d8a4ab2aa411c7ca33e96042` (LF) | Updated only affected `E-01`–`E-04` protected hashes; RAG & unrelated contracts unchanged |
| [test_diagnostics.py](file:///D:/SDC/LibraryLLM/tests/institution_v2j/test_diagnostics.py) | `3925e0fdeb473c5226d17c1cdd95bfd7e3866d3793d2a4d9cba8effe28ed3350` | `7d166c4e528183b59e58431318a90d012ad4169cd5e79c16d373c3d96cffb084` | Aligned affected source-contract check to authorized repair |
| [test_native_protocol.py](file:///D:/SDC/LibraryLLM/tests/institution_v2l/test_native_protocol.py) | `67ff9db88900dd5f96baecbb48fef0ee5e87d5ac90bfefb56d1a7eb65ab9ef79` | `be35af5b3ffae3ec47456035b0c1f2a355274b5d3d84d998719f751580328a31` | Aligned native protocol check to authorized repair |
| [test_deployment.py](file:///D:/SDC/LibraryLLM/tests/institution_v2m/test_deployment.py) | `fc059293976db11ba5819889bea0c31fbea9dc1606a2ce2ee2f81a4176b6147c` | `21a2881c25ecc0ac924bafa2f33abe36e916613423d29173b1a07bab1f4e3b15` | Aligned deployment guard to authorized repair |

### 3. New & Extended Closure Test Files (`3` files)
| File | Before SHA-256 | After SHA-256 | Coverage Added |
|---|---|---|---|
| [test_publication_recovery_closure.py](file:///D:/SDC/LibraryLLM/tests/institution_v2g/test_publication_recovery_closure.py) | `NEW` | `b5adeb3871eb6db53dfa6be1fa829f8d4acd6d3129066fb24cfddeb2160a1dd1` | `41` publication, corruption, crash, fence & recovery tests |
| [test_reservations_fees.py](file:///D:/SDC/LibraryLLM/tests/institution_v2c/test_reservations_fees.py) | `dc3b111bffd16d409a01a2c9b0df6222b13b024069aa6665b5faf6528b6ede33` | `6d4f6bc831ef5fa5ab81576e73faf4bd6cb815b6b644ef18aadf79b474cea937` | `test_fee_adjustment_replay_conflict_and_concurrent_return_confirm` |
| [test_analytics.py](file:///D:/SDC/LibraryLLM/tests/institution_v2e/test_analytics.py) | `0626c50b4c6547735eb3081f612e97bfbb706e135566c5fb04178cc6b4961c6f` | `532a6ec1814bdca718129e944f7035b2135e6f2f16dd06d0f0c85773f3513c7c` | `test_mid_read_canonical_fee_loan_and_stock_mutations_rejected` (5 parametrized cases) |

### 4. Preserved Frozen Files (Untouched)
- `rag/qa.py`: `4a1141649a4ce9b4bce6413627c27557f5817bb8718a4e842a4d12021bd89de3` (UNCHANGED)
- `rag/llm.py`: `d369e26fcbe458964bf642a057ca79212a63f48a6acf2b1c0a12590003f5cc1b` (UNCHANGED)
- All `v2o2`, `v2o3`, and `v2o3_closure` contract checks pass cleanly (`67/67`, `67/67`, `75/75`).

---

## K. Live GPU Qwen Runtime Configuration & Contention/Timeout Recovery

Executed directly against a live task-owned GPU FastAPI/Uvicorn backend ([closure_20261110_qwen_private_b.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_qwen_private_b.json), Mongo port `59211`, [closure_20261110_qwen_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_qwen_backend_isolation.json)):

- **Model & Device Identity:** `Qwen/Qwen2.5-3B-Instruct`, 4-bit quantization on `cuda:0` (`NVIDIA GeForce RTX 5060 Laptop GPU`), cold model load `24490.03 ms` (`24.49s`), active `cuda_allocated_mb: 1978.45`.
- **Forced Timeout & Slot Recovery:**
  - `0.05s` timeout forced clean `QwenUnavailable` rejection.
  - Concurrent busy slot arrival during occupied generation properly rejected via existing lock/slot control.
  - Next healthy request after slot clear succeeded in **`348.59 ms`**.
- **Shared GPU / Embedding Contention:** Concurrent `SentenceTransformer` embedding work (**`386.39 ms`**) alongside live Qwen generation (**`761.79 ms`**) completed cleanly without CUDA deadlock or cross-slot corruption.

---

## L. Live Patched Assistant Verification & Prompt Privacy

Using real GPU `Qwen/Qwen2.5-3B-Instruct` in the live closure stack ([closure_20261110_qwen_private_b.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_qwen_private_b.json)):

- **Patched Assistant Live Acceptance:** **`10/10` turns returned HTTP `200`** across real assistant conversation, selection/comparison, and session boundaries.
- **Prompt Privacy & Debug Logging:** Verified `LUMINAR_DEBUG_PROMPT` remains **OFF by default** in configuration/runtime, producing **`0` canary log bytes** in live request/error logging output.

---

## M. Private B (`08-PRIVATE-B`) Live Factorial Investigation & Root Cause Proof

**Status:** **`CONFIRMED_UNRESOLVED`** (Frozen RAG source untouched per task constraints)

Tested live with real GPU Qwen across both [`closure_20261110_qwen_private_b.json`](file:///D:/SDC/LibraryLLM/reports/closure_20261110_qwen_private_b.json) and a full paired factorial matrix ([`closure_20261110_private_b_paired.json`](file:///D:/SDC/LibraryLLM/reports/closure_20261110_private_b_paired.json), Mongo port `61490`), plus direct source inspection of [`fast_filter.py`](file:///D:/SDC/LibraryLLM/rag/fast_filter.py):

### 1. Paired & Factorial Results (`action='record'`)
| Probe ID | Condition / Manipulation | `fast_filter` Decision | Live Qwen Direct Verdict (Confidence) |
|---|---|---|---|
| `v2q2_exact_A_12m_ALPHA` | Exact Variant A (`12 minutes`, `ALPHA-SEVEN`, `action='record'`) | `NEEDS_LLM_VALIDATION` | `SUPPORTED` (`1.0`) |
| `v2q2_exact_B_47m_BRAVO` | Exact Variant B (`47 minutes`, `BRAVO-NINE`, `action='record'`) | `NEEDS_LLM_VALIDATION` | `NOT_SUPPORTED` (`0.85`) |
| `factor_12m_A_ALPHA` | `12 minutes` + Case A + `ALPHA-SEVEN` | — | `SUPPORTED` (`1.0`) |
| `factor_12m_B_BRAVO` | `12 minutes` + Case B + `BRAVO-NINE` | — | `NOT_SUPPORTED` (`0.8`) |
| `factor_B_47m_ALPHA` | Case B + `47 minutes` + `ALPHA-SEVEN` | — | `NOT_SUPPORTED` (`0.8`) |
| `factor_B_12m_ALPHA` | Case B + `12 minutes` + `ALPHA-SEVEN` | — | `SUPPORTED` (`1.0`) |
| `v2q2_analyze_intent_A` | Case A via `analyze_intent` | — | `SUPPORTED` (`1.0`) |
| `v2q2_analyze_intent_B` | Case B via `analyze_intent` | — | `NOT_SUPPORTED` (`0.85`) |
| `explicit_entity_B` | Explicit entity phrasing on Case B | `FAST_ACCEPT` | `NOT_SUPPORTED` (`0.8`) |
| `wording_exact_literal` | Literal question `"What is the calibration code?"` | `analyze_intent`: `polarity="negative", target=null, confidence=0.0` | `NOT_SUPPORTED` (`0.9`) |

### 2. Negative Controls (`closure_20261110_private_b_paired.json` & `fast_filter.py` audit)
| Negative Control ID | `fast_filter` Decision | Live Qwen Direct Verdict (Confidence) | Defect Exposed |
|---|---|---|---|
| `neg_wrong_actor` | — | `NOT_SUPPORTED` | Properly rejected |
| `neg_wrong_entity` | — | `NOT_SUPPORTED` | Properly rejected |
| `neg_absent_code` | — | `NOT_SUPPORTED` | Properly rejected |
| `neg_foreign_document` | — | `NOT_SUPPORTED` | Properly rejected |
| `neg_foreign_library` | — | `NOT_SUPPORTED` | Properly rejected |
| `neg_wrong_field` | **`FAST_ACCEPT`** (False Accept!) | `NOT_SUPPORTED` (`0.95`) | `fast_filter` short-circuits wrongly |
| `neg_negated_statement` | **`FAST_ACCEPT`** (False Accept!) | `NOT_SUPPORTED` (`1.0`) | `fast_filter` ignores `FACTUAL` negation |
| `neg_contradictory` | **`FAST_ACCEPT`** (False Accept!) | `SUPPORTED` (`1.0`) | Both `fast_filter` & validator fail on contradiction |

**Causal Conclusion:**
1. **`rag/llm.py` (`d369e26f...`, Frozen):** The entailment/validation prompt exhibits token-level instability on arbitrary domain values (`12 minutes`->`47 minutes`, `ALPHA-SEVEN`->`BRAVO-NINE`, `action='record'`->`'recorded'`) and `analyze_intent` misclassifies literal queries like `"What is the calibration code?"` as `polarity="negative", target=null, confidence=0.0`.
2. **`rag/fast_filter.py` (Frozen/Protected RAG boundary):** Accepts `FACTUAL` answers with wrong-field (`neg_wrong_field`), negated (`neg_negated_statement`), or contradictory (`neg_contradictory`) evidence via `FAST_ACCEPT`, bypassing LLM validation even when live Qwen direct validation returns `NOT_SUPPORTED` (`0.95–1.0`).

---

## N. Separate Protected Proposal for Frozen RAG (`rag/fast_filter.py` & `rag/llm.py`)

Because modifying protected RAG validation/LLM files (`rag/qa.py`, `rag/llm.py`, `rag/fast_filter.py`) is **outside the explicit `E-01`–`E-04` authorization scope**, **no RAG source bytes were modified**. Separate explicit authorization is required for:
1. **`rag/fast_filter.py`**: Disable `FAST_ACCEPT` bypass whenever negation cues, mismatched field predicates, numerical/entity contradictions, or absence claims appear in `FACTUAL` query/candidate pairs, routing them strictly to authoritative LLM verification.
2. **`rag/llm.py`**: Stabilize `analyze_intent` polarity/target classification on literal information-seeking questions (preventing `"What is the calibration code?"` -> `negative`) and review the validator few-shot/prompt framing so surface tokens (`47 minutes`, `BRAVO-NINE`, `'recorded'`) do not invert factual entailment.

---

## O. Real Chromium Browser, Mobile Responsive (`320px–1440px`) & Route Interaction Verification

Executed live against a disposable task-owned FastAPI + Vite dev stack in real headless Chromium ([closure_20261110_browser_e2e.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_browser_e2e.json), Mongo port `61718`, [closure_20261110_browser_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_browser_backend_isolation.json)):

- **Viewport & Horizontal-Overflow Matrix (`57` measurements):** Zero horizontal overflow (`scrollWidth <= innerWidth`) across **all `57` viewport measurements** spanning widths **`320px`, `360px`, `375px`, `390px`, `430px`, `768px`, `1024px`, and `1440px`** (including `PatronMyLibrary` at `390px`) and across **`13` desktop routes**.
- **Runtime Hygiene:** **`0` console errors** and **`0` uncaught page errors**.
- **Live Interactive Workflows Verified in Chromium:**
  - **Tenant Switching & Isolation:** Library `A -> B` switch verified clean state scoping; **Patron blocked from Analytics** route/API cleanly.
  - **Mobile `390px` Hamburger & Keyboard `Escape`:** Mobile navigation drawer opened cleanly and dismissed via `Escape`.
  - **Staff Intelligence UI, Knowledge Tools & Workspace Tabs:** Live Knowledge Tools tabs switched cleanly without stale leakage.
  - **Assistant Widget & Notification Inbox:** Opened, interacted, and displayed targeted inbox notifications without DOM/runtime errors.

---

## P. Live `axe-core` Accessibility Audit & `/catalog` Color-Contrast Finding

Running real Chromium `axe-core` (including visual computed-style layout & `color-contrast`, which JSDOM cannot evaluate):

| Surface Audited | `axe-core` Passes | Violations | Details |
|---|---|---|---|
| `Analytics` | **`43`** | **`0`** | Clean pass |
| `StaffIntelligence` | **`38`** | **`0`** | Clean pass |
| `PrivateCatalogueA` | **`34`** | **`0`** | Clean pass |
| `GlobalCatalogue` (`/catalog`) | — | **`4` serious** | **`4` serious `color-contrast` violations** detected under visual layout |

**Status:** Logged in `closure_20261110_issue_register.json` as a confirmed frontend visual accessibility defect on `/catalog` (`POLICY/UI_FOLLOWUP`), preserved untouched because UI styling edits outside authorized `E-01`–`E-04` scope were not requested.

---

## Q. Uninterrupted Full Backend Regression Suite (38 Grouped Suites + Closure Standalone)

After all code, metadata, and closure-test edits were complete, the entire backend regression suite executed cleanly in one uninterrupted run (`scripts/institution_v2q_ai_checks.py backend closure_20261110`, Mongo port `59827`, [closure_20261110_full_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_full_backend_isolation.json)), paired with standalone execution of [`test_publication_recovery_closure.py`](file:///D:/SDC/LibraryLLM/tests/institution_v2g/test_publication_recovery_closure.py):

### Summary Totals
- **Uninterrupted 38-Group Suite (`closure_20261110_regression_summary.json` / `institution_v2q_closure_20261110_backend.json`):** `38` groups, all exit `0` — **`3205 passed, 0 failed, 20 skipped`** (`3225` executions).
- **Standalone `v2g_closure` (`closure_20261110_v2g_closure.xml`):** **`41 passed, 0 failed, 0 skipped`** (`33.83s`).
- **Combined Raw Backend Executions (`BACKEND_TESTS_RAW`):** **`3246 passed, 0 failed, 20 skipped`** (`3266` total).
- **Combined Deduplicated Unique Testcases (`BACKEND_TESTS_UNIQUE`):** **`3164 passed, 0 failed, 10 skipped`** (`3174` unique; `92` repeated cross-group test executions accounted for; all `10` unique skips belong to [`test_dynamic_book_capabilities.py`](file:///D:/SDC/LibraryLLM/tests/test_dynamic_book_capabilities.py), executed twice inside `security` and `current_product_extensions`).
- **Delta vs Baseline (`3117` unique post-recheck):** **`+47` new unique passing tests** (`41` `v2g_closure` + `1` `v2c` + `5` `v2e`) and **`0` failures** (resolving the prior `1` transient `WORKER_FENCED` failure in `institution_v2g`: **`152/152` passed in `78.66s`**).

### Full 38-Group + Standalone Breakdown
| # | Group | Exit | Tests | Passed | Failed | Skipped | Duration (s) |
|---|---|---|---|---|---|---|---|
| 1 | `unit` | 0 | 37 | 37 | 0 | 0 | — |
| 2 | `staff` | 0 | 76 | 76 | 0 | 0 | — |
| 3 | `assistant` | 0 | 452 | 452 | 0 | 0 | — |
| 4 | `security` | 0 | 127 | 117 | 0 | 10 | — |
| 5 | `notifications` | 0 | 51 | 51 | 0 | 0 | — |
| 6 | `circulation` | 0 | 13 | 13 | 0 | 0 | — |
| 7 | `search` | 0 | 172 | 172 | 0 | 0 | — |
| 8 | `private_knowledge_ocr` | 0 | 279 | 279 | 0 | 0 | 82.06 |
| 9 | `kg` | 0 | 30 | 30 | 0 | 0 | 7.92 |
| 10 | `institution_v1` | 0 | 60 | 60 | 0 | 0 | 16.94 |
| 11 | `institution_v2a` | 0 | 95 | 95 | 0 | 0 | 38.05 |
| 12 | `institution_v2b` | 0 | 57 | 57 | 0 | 0 | 48.70 |
| 13 | `institution_v2c` | 0 | 60 | 60 | 0 | 0 | 67.21 |
| 14 | `institution_v2d` | 0 | 45 | 45 | 0 | 0 | 14.54 |
| 15 | `institution_v2e` | 0 | 115 | 115 | 0 | 0 | 40.48 |
| 16 | `institution_v2f` | 0 | 187 | 187 | 0 | 0 | 106.99 |
| 17 | `institution_v2h` | 0 | 30 | 30 | 0 | 0 | 12.29 |
| 18 | `institution_v2g` | 0 | 152 | 152 | 0 | 0 | 78.66 |
| 19 | `workspace_authorization` | 0 | 13 | 13 | 0 | 0 | 10.50 |
| 20 | `dashboard_authority` | 0 | 86 | 86 | 0 | 0 | 57.59 |
| 21 | `catalogue_experience` | 0 | 88 | 88 | 0 | 0 | 62.17 |
| 22 | `product_consistency` | 0 | 27 | 27 | 0 | 0 | 11.46 |
| 23 | `current_product_extensions` | 0 | 10 | 0 | 0 | 10 | 1.74 |
| 24 | `institution_v2i` | 0 | 60 | 60 | 0 | 0 | 38.19 |
| 25 | `institution_v2j` | 0 | 54 | 54 | 0 | 0 | 12.81 |
| 26 | `institution_v2k` | 0 | 56 | 56 | 0 | 0 | 11.49 |
| 27 | `institution_v2l` | 0 | 67 | 67 | 0 | 0 | 28.52 |
| 28 | `institution_v2m` | 0 | 50 | 50 | 0 | 0 | 21.48 |
| 29 | `institution_v2n` | 0 | 35 | 35 | 0 | 0 | 20.79 |
| 30 | `institution_v2o` | 0 | 32 | 32 | 0 | 0 | 17.94 |
| 31 | `institution_v2o1` | 0 | 19 | 19 | 0 | 0 | 33.46 |
| 32 | `institution_v2o2` | 0 | 67 | 67 | 0 | 0 | 77.01 |
| 33 | `institution_v2o3` | 0 | 67 | 67 | 0 | 0 | 70.91 |
| 34 | `institution_v2o3_closure` | 0 | 75 | 75 | 0 | 0 | 74.06 |
| 35 | `institution_v2p` | 0 | 84 | 84 | 0 | 0 | 21.32 |
| 36 | `institution_v2p1` | 0 | 80 | 80 | 0 | 0 | 17.95 |
| 37 | `institution_v2q_ai` | 0 | 141 | 141 | 0 | 0 | 79.51 |
| 38 | `events` | 0 | 76 | 76 | 0 | 0 | — |
| 39 | `v2g_closure` (standalone XML) | 0 | 41 | 41 | 0 | 0 | 33.83 |

*(Note: Group durations marked `—` reflect either groups 1–7 omitted from the read summary tail or `events` which omitted a `seconds` field in `institution_v2q_closure_20261110_backend.json`; exact pass/fail/skip counts for all 39 runs are verified.)*

---

## R. Historical `WORKER_FENCED` Evidence Retention vs Clean Uninterrupted Pass

Historical evidence in [research_batch13_16_20261110_completion.md](file:///D:/SDC/LibraryLLM/reports/research_batch13_16_20261110_completion.md) (initial full run `1105.99s` `WORKER_FENCED` failure in `institution_v2g` before its unchanged-source `78.29s` `152/152` retry) remains **preserved untouched** on disk. In contrast, the post-closure `closure_20261110` regression achieved an **uninterrupted clean full pass** across all 38 groups without retries, with `institution_v2g` passing **`152/152` in `78.66s`** (`0 WORKER_FENCED` errors) and standalone `v2g_closure` passing **`41/41` in `33.83s`**.

---

## S. Frontend Regression Suite (`1033/1033`), Production Build & Lint

Verified cleanly across all `35` frontend test scripts ([closure_20261110_front_test.log](file:///D:/SDC/LibraryLLM/reports/closure_20261110_front_test.log)), build ([closure_20261110_front_build.log](file:///D:/SDC/LibraryLLM/reports/closure_20261110_front_build.log)), and lint ([closure_20261110_front_lint.log](file:///D:/SDC/LibraryLLM/reports/closure_20261110_front_lint.log)):

### 1. Frontend Tests (`1033 passed, 0 failed, 0 skipped` across `35` sub-scripts)
- `test`: 38 | `test:assistant`: 94 | `test:assistant-library-scope`: 18 | `test:knowledge`: 52 | `test:institutions`: 28
- `test:inventory`: 26 | `test:lending`: 23 | `test:reservations-fees`: 17 | `test:workspaces`: 71 | `test:management`: 21
- `test:catalogue`: 68 | `test:product-consistency`: 9 | `test:navigation`: 31 | `test:convergence`: 18 | `test:platform-completion`: 35
- `test:events-notifications`: 21 | `test:announcements`: 29 | `test:announcement-recipients`: 24 | `test:analytics`: 32 | `test:assets`: 39
- `test:activity`: 14 | `test:critical-closure`: 30 | `test:staff-catalogue`: 28 | `test:intelligence`: 22 | `test:intelligence-controls`: 56
- `test:post-2h`: 43 | `test:search-runtime`: 15 | `test:recommendation-runtime`: 13 | `test:post2h-product`: 35 | `test:private-library`: 9
- `test:search-nlu`: 10 | `test:search-session`: 6 | `test:search-interactions`: 18 | `test:design-v2`: 28 | `test:search-preview`: 12

### 2. Build & Lint
- **Production Build (`npm run build`):** **`PASS`** — `2264` modules transformed in **`1.54s`**.
- **Linter (`npm run lint` / `oxlint`):** **`PASS`** — **`222` files checked, `0` errors, `16` existing warnings**.

---

## T. Parts 04–07 Gap Closure & Circulation/Fee/Analytics Concurrency Hardening

Executed and isolated on ephemeral Mongo port `56068` ([closure_20261110_v2ce_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_v2ce_backend_isolation.json)):

1. **Fee Ledger Replay & Concurrent Return Confirm ([`test_reservations_fees.py`](file:///D:/SDC/LibraryLLM/tests/institution_v2c/test_reservations_fees.py)):**
   - Added [`test_fee_adjustment_replay_conflict_and_concurrent_return_confirm`](file:///D:/SDC/LibraryLLM/tests/institution_v2c/test_reservations_fees.py) testing exact idempotency-key conflict rejection on fee adjustments alongside concurrent loan return confirmation.
   - `institution_v2c` suite passed **`60/60` (`67.21s`)**.
2. **Mid-Read Canonical Analytics Mutation Rejections ([`test_analytics.py`](file:///D:/SDC/LibraryLLM/tests/institution_v2e/test_analytics.py)):**
   - Added 5-parametrized [`test_mid_read_canonical_fee_loan_and_stock_mutations_rejected`](file:///D:/SDC/LibraryLLM/tests/institution_v2e/test_analytics.py) proving that canonical fee, loan, and stock mutations injected mid-read fail closed or are rejected consistently without poisoning aggregate invariants.
   - `institution_v2e` suite passed **`115/115` (`40.48s`)**.

---

## U. Part 13 Tenant Analytics & Optimistic Read-Consistency Verification

- Preserved the Parts 13–16 analytics fix excluding `PUBLISHED` events without known effective dates from completed counts while keeping `institution_v2e` at `115/115` passing (`+5` mid-read canonical mutation cases).
- Live Chromium E2E confirmed staff analytics renders cleanly (`axe-core`: `43` passes, `0` violations) while `Patron` accounts remain blocked from analytics routes/APIs.
- Small-cohort privacy governance remains `POLICY_REQUIRED` (no arbitrary Differential Privacy or minimum-cohort suppression invented).

---

## V. Part 08 Document Ingestion, Restoration Warnings & Authorization Boundaries

- Preserved all Parts 08–12 repairs: DOCX extraction in [`library_asset_text.py`](file:///D:/SDC/LibraryLLM/backend/services/library_asset_text.py) excludes deleted text, moved-from text, and field instructions while keeping run separators; restored personal document bundles retain missing-page extraction warnings.
- `private_knowledge_ocr` passed **`279/279` (`82.06s`)** and `security` passed **`117/127` (`10` expected dynamic skips)**.

---

## W. Part 09 Knowledge Tools & Grounding Contracts

- Knowledge Tools authorization (`flashcards`, `summary`, `mindmap`, `quiz`), MCQ/cloze verification contracts, and tenant/document isolation preserved (`279/279` in `private_knowledge_ocr`).
- Live Chromium verified Knowledge Tools tabs switch cleanly without cross-tenant or cross-document state leakage.

---

## X. Part 10 Global & Tenant Knowledge Graph Architecture & Boundaries

- Global SQLite KG (`knowledge_graph/data/catalogue.sqlite`, `5,000,000` books) remained untouched and read-only (`global_kg_preflight_metadata_match: true`, `5` global KG files preserved).
- Tenant KG (`KNOWLEDGE_GRAPH`) now benefits from all four `E-01`–`E-04` publication, manifest digest, fence-recovery, and pre-tag barrier protections; `kg` passed **`30/30` (`7.92s`)** alongside `v2g` (**`152/152`**) and `v2g_closure` (**`41/41`**).
- Homonym/synonym collapse (`Alex Kim`, `DNS` vs `Domain Name System`) and whole-generation rebuild (`10-INCREMENTAL`) remain `EXPECTED_DESIGN_BOUND`.

---

## Y. Part 11 Recommendations & Library Scoping

- `GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY`, recommendation ownership rules, and `assistant` / `search` library scoping remain intact:
  - `assistant`: **`452/452`**
  - `search`: **`172/172`**
  - `institution_v2q_ai`: **`141/141` (`79.51s`)**
  - Frontend `test:recommendation-runtime`: **`13/13`**, `test:assistant`: **`94/94`**, `test:assistant-library-scope`: **`18/18`**.

---

## Z. Part 12 Announcements, Notifications & Canonical Due Reminders Policy Boundary

- Announcements, recipient targeting, and transactional outbox deduplication remain green (`notifications`: **`51/51`**, `institution_v2p`: **`84/84` (`21.32s`)**, `institution_v2p1`: **`80/80` (`17.95s`)**; frontend `test:announcements`: **`29/29`**, `test:announcement-recipients`: **`24/24`**, `test:events-notifications`: **`21/21`**) plus Notification Inbox verified in Chromium.
- **Canonical Due Reminders (`POLICY_REQUIRED`):** Inspected `DUE_SOON`/`DUE_TODAY`/`OVERDUE` scanners operate on global issues/`due_date`, with no canonical `institution_loans`/`due_at` reminder scheduler added without policy approval.

---

## AA. Operator Diagnostics & Optional Telemetry ACLs

- Production telemetry remains **disabled and untouched**.
- Narrow test contract updates in [`test_diagnostics.py`](file:///D:/SDC/LibraryLLM/tests/institution_v2j/test_diagnostics.py), [`test_native_protocol.py`](file:///D:/SDC/LibraryLLM/tests/institution_v2l/test_native_protocol.py), and [`test_deployment.py`](file:///D:/SDC/LibraryLLM/tests/institution_v2m/test_deployment.py) align cleanly with the authorized `E-01`–`E-04` changes and pass completely:
  - `institution_v2j`: **`54/54` (`12.81s`)**
  - `institution_v2k`: **`56/56` (`11.49s`)**
  - `institution_v2l`: **`67/67` (`28.52s`)**
  - `institution_v2m`: **`50/50` (`21.48s`)**

---

## AB. Disposable Test Infrastructure & Zero-Trace Cleanup Verification

Every isolated execution spawned a disposable port-scoped `mongod` and verified clean teardown with `owned_mongod_stopped: true`, `owned_root_removed: true`, and `stray_closure_mongo_dbs: []` in [closure_20261110_preservation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_preservation.json):

| Closure Phase | Isolation Receipt | Port | Exit | Clean Shutdown & Root Removed |
|---|---|---|---|---|
| `E-01..E-04` Before Repro | [closure_20261110_before_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_before_backend_isolation.json) | `64383` | `0` | `true` / `true` |
| `v2g` Initial Check (Historical Attempt) | [closure_20261110_v2gi_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_v2gi_backend_isolation.json) | `52538` | `1` | `true` / `true` |
| `E-01..E-04` Fix Run | [closure_20261110_e01_e04_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_e01_e04_backend_isolation.json) | `50672` | `0` | `true` / `true` |
| `E-01..E-04` After Repro | [closure_20261110_after_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_after_backend_isolation.json) | `51180` | `0` | `true` / `true` |
| Contracts (`v2o2/v2o3/v2j/v2l/v2m`) | [closure_20261110_contracts_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_contracts_backend_isolation.json) | `51312` | `0` | `true` / `true` |
| `v2c` & `v2e` Closure Hardening | [closure_20261110_v2ce_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_v2ce_backend_isolation.json) | `56068` | `0` | `true` / `true` |
| Live GPU Qwen Acceptance | [closure_20261110_qwen_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_qwen_backend_isolation.json) | `59211` | `0` | `true` / `true` |
| Private B Paired Matrix | [closure_20261110_pb_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_pb_backend_isolation.json) | `61490` | `0` | `true` / `true` |
| Live Chromium Browser E2E | [closure_20261110_browser_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_browser_backend_isolation.json) | `61718` | `0` | `true` / `true` |
| Standalone `v2g_closure` + Matrix | [closure_20261110_v2gc_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_v2gc_backend_isolation.json) | `59229` | `0` | `true` / `true` |
| Full 38-Group Backend Runner | [closure_20261110_full_backend_isolation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_full_backend_isolation.json) | `59827` | `0` | `true` / `true` |
| Group-Runner Fallback DB Isolation | [institution_v2q_closure_20261110_test_isolation.json](file:///D:/SDC/LibraryLLM/reports/institution_v2q_closure_20261110_test_isolation.json) | — | `0` | `true` / `true` |

---

## AC. Unified Issue Register Summary (`71` Entries Reconciled)

The unified register ([closure_20261110_issue_register.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_issue_register.json)) reconciles **`71` entries** extending the prior `58`-entry Parts 13–16 register (`research_batch13_16_20261110_issue_register.json`):

- **Previously `APPROVAL_REQUIRED` -> Now `CONFIRMED_FIXED` (`4`):** `E-01`, `E-02`, `E-03`, `E-04` (both `SEARCH_INDEX` & `KNOWLEDGE_GRAPH` verified `8/8` after fix and `41/41` + `20/20` scenarios).
- **Previously `NOT_RUN` / `MISSING_VALIDATION` -> Investigated Live:**
  - `11-QWEN` (live GPU Qwen acceptance, contention, timeout recovery): verified **`10/10` HTTP 200** + timeout/contention recovery.
  - Real Chromium browser / `320px–1440px` / interactive workflows: verified **`57` viewports + `13` routes (`0` overflows, `0` console errors)**.
  - **`08-PRIVATE-B`**: transitioned from `MISSING_VALIDATION` to **`CONFIRMED_UNRESOLVED`** with full live factorial evidence pinpointing frozen [`rag/fast_filter.py`](file:///D:/SDC/LibraryLLM/rag/fast_filter.py) (`FACTUAL` false-`FAST_ACCEPT` on negation/wrong-field/contradiction) and [`rag/llm.py`](file:///D:/SDC/LibraryLLM/rag/llm.py) (token sensitivity & negative-intent classification of `"What is the calibration code?"`).
- **Newly Logged Visual Accessibility Defect:** Global Catalogue (`/catalog`) **`4` serious `color-contrast` violations** discovered via Chromium `axe-core`.
- **Preserved Existing Classifications:** Parts 04–16 fixes remain verified (`CONFIRMED_FIXED`/`ALREADY_FIXED`), historical research evidence gaps and policy boundaries (`ANALYTICS_PRIVACY`, `CANONICAL_DUE_REMINDERS`, `PROD-MONGO`, `10-HOMONYM`/`10-SYNONYM`/`10-INCREMENTAL`, `12-SMTP`, manual `SCREEN_READER`) remain transparently documented without inflation.

---

## AD. Remaining Confirmed Defects & Actionable Gaps

1. **`08-PRIVATE-B` (`CONFIRMED_UNRESOLVED`, Protected RAG Scope):**
   - [`rag/fast_filter.py`](file:///D:/SDC/LibraryLLM/rag/fast_filter.py) returns false `FAST_ACCEPT` on `neg_wrong_field`, `neg_negated_statement`, and `neg_contradictory`.
   - Frozen [`rag/llm.py`](file:///D:/SDC/LibraryLLM/rag/llm.py) reverses `SUPPORTED`/`NOT_SUPPORTED` across benign surface tokens (`12 minutes`->`47 minutes`, `ALPHA-SEVEN`->`BRAVO-NINE`) and classifies `"What is the calibration code?"` as `polarity="negative"`.
2. **Global Catalogue `/catalog` Visual Contrast (`4` Serious `axe-core` Violations):**
   - Reported by live Chromium `axe-core` audit; requires design-system compliant foreground/background token contrast tuning under frontend authorization.

---

## AE. Remaining Policy-Required & Governance Boundaries

- **Analytics Small-Cohort Privacy (`POLICY_REQUIRED`):** No policy exists defining k-anonymity or suppression cutoffs on small library cohorts.
- **Canonical Due Reminders (`POLICY_REQUIRED`):** Legacy global issues/`due_date` reminder scanners exist; no canonical `institution_loans`/`due_at` reminder schedule is policy-approved.
- **Manual Screen Reader & Full WCAG 2.1 AA Site Certification (`NOT_RUN` / `PARTIAL`):** Automated Chromium `axe-core` cleared `Analytics`, `StaffIntelligence`, and `PrivateCatalogueA`; manual AT/screen-reader walkthrough across all routes was not performed.
- **External Email/SMTP Delivery & Production Mongo Auth Qualification (`POLICY_REQUIRED` / `RESEARCH_ONLY`):** Disabled by policy; no production Mongo credentials modified.

---

## AF. Preservation & Non-Modification Guarantees

| Protected / Resident Resource | Verified State |
|---|---|
| Git Branch & HEAD | `codex/search-v11-finalization` / `606f0dfce3970bea8e6fc2b62d243433d1a66b8a` (no reset/commit) |
| Global Book Count / Search HNSW | `5,000,000` books / `196` HNSW files UNCHANGED (`GLOBAL_HNSW_REBUILT: NO`) |
| Global KG (`catalogue.sqlite`) | `5` Global KG files UNCHANGED (`GLOBAL_KG_REBUILT: NO`) |
| Existing Tenant Intelligence State | `22` targets, `15` generations, `39` jobs (`37` `SUCCEEDED`, `2` `FAILED`), `0` locks, `181` files UNCHANGED |
| Protected Library Assets & Tenant Collections | `141` assets, `33` tenant collections UNCHANGED |
| Frozen RAG Files (`rag/qa.py`, `rag/llm.py`) | `100%` SHA-256 identical (`PROTECTED_RAG_CHANGED: NO`) |
| Historical Reports (`11/11` tracked SHA-256s) | Unmodified & retained (`research_batch13_16_*`, `research_batch08_12_*`, etc.) |
| `.env` & Production Telemetry | Untouched / Disabled (`PRODUCTION_TELEMETRY_ENABLED: NO`) |
| Stray Closure Mongo DBs | `[]` (Zero left behind) |

---

## AG. Complete Closure Deliverable & Artifact Index

All `closure_20261110_*` verification artifacts reside in [`D:/SDC/LibraryLLM/reports/`](file:///D:/SDC/LibraryLLM/reports/):

- **Reports:**
  - [closure_20261110_completion.md](file:///D:/SDC/LibraryLLM/reports/closure_20261110_completion.md) (this report)
  - [closure_20261110_qa.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_qa.json) (Section 26 Machine-Readable Final QA)
  - [closure_20261110_issue_register.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_issue_register.json) (`30,874` bytes)
- **Preflight & Preservation:**
  - [closure_20261110_preflight.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_preflight.json) (`533,754` bytes)
  - [closure_20261110_preservation.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_preservation.json) (`20,027` bytes)
- **Before/After Reproductions & Crash/Recovery Matrix:**
  - [closure_20261110_before_repro.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_before_repro.json) (`35,885` bytes)
  - [closure_20261110_after_repro.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_after_repro.json) (`34,815` bytes)
  - [closure_20261110_recovery_matrix.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_recovery_matrix.json) (`35,618` bytes)
  - [closure_20261110_v2g_closure.xml](file:///D:/SDC/LibraryLLM/reports/closure_20261110_v2g_closure.xml) (`7,997` bytes)
- **Live GPU Qwen & Private B Investigation:**
  - [closure_20261110_qwen_private_b.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_qwen_private_b.json) (`83,965` bytes)
  - [closure_20261110_private_b_paired.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_private_b_paired.json) (`30,909` bytes)
- **Live Chromium Browser & `axe-core` E2E:**
  - [closure_20261110_browser_e2e.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_browser_e2e.json) (`20,630` bytes)
- **Uninterrupted Full Backend & Frontend Suites:**
  - [closure_20261110_regression_summary.json](file:///D:/SDC/LibraryLLM/reports/closure_20261110_regression_summary.json) (`9,225` bytes)
  - [institution_v2q_closure_20261110_backend.json](file:///D:/SDC/LibraryLLM/reports/institution_v2q_closure_20261110_backend.json) (`10,042` bytes) + `38` `institution_v2q_closure_20261110_<group>.{log,xml}` files
  - [closure_20261110_front_test.log](file:///D:/SDC/LibraryLLM/reports/closure_20261110_front_test.log) (`113,388` bytes)
  - [closure_20261110_front_build.log](file:///D:/SDC/LibraryLLM/reports/closure_20261110_front_build.log) (`5,078` bytes)
  - [closure_20261110_front_lint.log](file:///D:/SDC/LibraryLLM/reports/closure_20261110_front_lint.log) (`10,074` bytes)
- **Isolation Receipts (`12` JSON files):**
  `closure_20261110_{before,v2gi,e01_e04,after,contracts,v2ce,qwen,pb,browser,v2gc,full}_backend_isolation.json` + [institution_v2q_closure_20261110_test_isolation.json](file:///D:/SDC/LibraryLLM/reports/institution_v2q_closure_20261110_test_isolation.json)

---

## AH. Next Recommended Engineering & Policy Steps

1. **Authorize Protected RAG Patch (`08-PRIVATE-B`):** Review and authorize targeted edits to [`rag/fast_filter.py`](file:///D:/SDC/LibraryLLM/rag/fast_filter.py) (eliminating `FACTUAL` false-`FAST_ACCEPT` on negated, wrong-field, and contradictory candidates) and [`rag/llm.py`](file:///D:/SDC/LibraryLLM/rag/llm.py) (fixing literal question `negative` intent classification and token-substitution sensitivity).
2. **Remediate `/catalog` `color-contrast`:** Address the `4` serious visual `color-contrast` violations identified on `GlobalCatalogue` (`/catalog`) and re-run Chromium `axe-core`.
3. **Policy Decisions Before Implementation:** Resolve product policies for analytics small-cohort privacy, canonical `institution_loans`/`due_at` reminder scheduling, and optional telemetry/screen-reader WCAG sign-off.
4. **Review & Commit:** Inspect git working-tree changes across the `5` authorized backend fixes, `4` metadata/contract alignments, and `3` closure test files before staging any commit.

---

## 26. Machine-Readable Final QA

```json
{
  "RUN_NAMESPACE": "closure_20261110",
  "OVERALL_STATUS": "CLOSURE_COMPLETE_WITH_FROZEN_RAG_AND_CONTRAST_EXCEPTIONS",
  "E01_RETAINED_LOCK": "CONFIRMED_FIXED",
  "E02_FENCE_RECOVERY": "CONFIRMED_FIXED",
  "E03_CORRUPT_POINTER": "CONFIRMED_FIXED",
  "E04_UNTAGGED_BARRIER": "CONFIRMED_FIXED",
  "BEFORE_REPRO_SEARCH_KG": "0/8 PASS",
  "AFTER_REPRO_SEARCH_KG": "8/8 PASS",
  "CLOSURE_RECOVERY_MATRIX_SCENARIOS": "20/20 PASS",
  "PRIVATE_B_LIVE_QWEN": "CONFIRMED_UNRESOLVED",
  "LIVE_QWEN_GPU": "PASS",
  "LIVE_QWEN_MODEL": "Qwen/Qwen2.5-3B-Instruct (4-bit cuda:0 RTX 5060 Laptop GPU)",
  "PATCHED_ASSISTANT_LIVE_TURNS": "10/10 HTTP 200",
  "DEBUG_PROMPT_DEFAULT_OFF": true,
  "DEBUG_PROMPT_CANARY_BYTES": 0,
  "BROWSER_MOBILE_RESPONSIVE_OVERFLOWS": 0,
  "BROWSER_VIEWPORT_MEASUREMENTS": 57,
  "BROWSER_DESKTOP_ROUTES": 13,
  "BROWSER_CONSOLE_AND_PAGE_ERRORS": 0,
  "AXE_ANALYTICS": "43 PASS / 0 VIOLATIONS",
  "AXE_STAFF_INTELLIGENCE": "38 PASS / 0 VIOLATIONS",
  "AXE_PRIVATE_CATALOGUE_A": "34 PASS / 0 VIOLATIONS",
  "AXE_GLOBAL_CATALOGUE": "4 SERIOUS color-contrast VIOLATIONS",
  "BACKEND_UNINTERRUPTED_GROUPS_PASSED": 38,
  "BACKEND_V2G_GROUP": "152/152 PASS (0 WORKER_FENCED)",
  "BACKEND_V2G_CLOSURE": "41/41 PASS",
  "BACKEND_TESTS_RAW": {
    "passed": 3246,
    "failed": 0,
    "skipped": 20,
    "total": 3266
  },
  "BACKEND_TESTS_UNIQUE": {
    "passed": 3164,
    "failed": 0,
    "skipped": 10,
    "unique_total": 3174
  },
  "FRONTEND": {
    "passed": 1033,
    "failed": 0,
    "skipped": 0,
    "scripts": 35
  },
  "PROTECTED_CONTRACTS_V2O3_CLOSURE": {
    "passed": 75,
    "failed": 0,
    "skipped": 0
  },
  "BUILD": "PASS (2264 modules, 1.54s)",
  "LINT": "PASS (oxlint: 222 files, 0 errors, 16 existing warnings)",
  "GLOBAL_HNSW_REBUILT": "NO",
  "GLOBAL_KG_REBUILT": "NO",
  "EXISTING_TENANT_INDEX_REBUILT": "NO",
  "PROTECTED_RAG_CHANGED": "NO",
  "DEPLOYED": "NO",
  "COMMITTED": "NO",
  "STRAY_CLOSURE_MONGO_DBS": 0
}
```

