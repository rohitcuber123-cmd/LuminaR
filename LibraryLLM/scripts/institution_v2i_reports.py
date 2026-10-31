"""Assemble Part 2I source findings and executed evidence; no application imports."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'reports'

DOCS = {
'architecture': '''# Actual tenant intelligence architecture

| Concern | Source and contract |
|---|---|
| Canonical input | `backend/services/library_intelligence_store.py:source_records`, `SOURCE_FIELDS`, `fingerprint`, `dataset`; no mutation-driven catalogue revision exists. `intelligence_sequences.sequence` numbers materialized datasets, not every mutation. |
| Status | `backend/services/library_intelligence_service.py:status`, `control_status`, `target_status`, `pointer_manifest`; staff status under per-library Mongo barrier, normalized current source fingerprint, current jobs and full checksum verification. |
| APIs | `backend/routes/library_intelligence.py`; GET `/libraries/{library_id}/intelligence`, POST `/builds`, GET `/jobs/{job_id}`, GET `/generations/{generation_id}`, GET `/reconciliation`, POST `/jobs/{job_id}/recover`, GET `/graph` under the same prefix. UUID validation and private,no-store. |
| Authority | `backend/dependencies.py:get_current_user` → JWT decode → `identity_service.current_identity` and login revocation; `library_inventory_access.require_library_staff` → exact active membership and circulation-readability checks. `store.build_guard` requires tenant ADMIN. |
| Durable queue | `store.request_build`, `claim`, `lease_query`, `check_lease`, `heartbeat`, `progress`, `build_audit`; no external broker. |
| Worker | `search/library_intelligence.py:TenantIntelligence.start/loop/run_one`; `search/library_intelligence_api.py:install` starts one daemon in a resident Search service only when both models exist. Two-second idle wait, serial jobs, ten-second renewal thread and ninety-second leases. |
| Artifacts | `backend/services/library_intelligence_artifacts.py:VectorCache`, `build_search`, `build_graph`, `validate`, `ArtifactCache`; root `local-data/library-intelligence` unless configured; canonical UUID namespace and symlink/path checks. |
| Publication | `run_one`: private `{generation}.building`, fsynced metadata/manifest, validation, `os.replace` to final generation, checksum, fresh lease/admin/source check under tenant barrier, fenced target pointer update, durable success and deterministic audit. |
| Search selection | `search/query_execution.py:tenant_search` and `TenantIntelligence.semantic`; only READY serves tenant semantic generation. Non-READY uses existing local catalogue fallback. Current hydration/eligibility is checked again. |
| Graph selection | `service.graph`; READY loads graph cache and intersects Book nodes with currently usable tenant records; other states return safe empty graph notice. Global Graph Lab stays separate. |
| UI | `frontend/src/pages/LibraryIntelligence.tsx`, `frontend/src/lib/libraryIntelligence.ts`, `frontend/src/components/LibraryShells.tsx`; canonical `/staff/libraries/{library_id}/intelligence`, shared Staff design and confirmations. |

All collection names below carry the actual `institution_` prefix: `library_books`, `libraries`, `memberships`, `locks`, `lending_config`, `intelligence_sequences`, `intelligence_generations`, `intelligence_jobs`, `intelligence_targets`, `audit`. Global `books` is read only for selected linked work IDs, at most 500 per enrichment query. Holdings/assets affect snapshot format counts, not the source fingerprint.

Dataset fields: generation_id, library_id, sequence, source_fingerprint, status PREPARING/READY/FAILED, book_count, schema_version, timestamps, creator, local/link/format counts and file checksums. Job fields: job_id/library_id/target, requested_generation_id, artifact_generation_id, state/stage/progress_current/progress_total, requested_by_user_id, created/started/heartbeat/completed timestamps, effective_active, attempt, worker_id, fence_token, lease_expires_at, require_nonempty and error_code/message. Target fields: state, active_job_id/fence_token, active_generation_id, previous_generation_id, published_by_job_id, source_generation_id/fingerprint, manifest_checksum, record_count, built_at, stale_since, artifact_bytes and graph counts.

Queue: QUEUED → RUNNING → VALIDATING → PUBLISHING → SUCCEEDED; known build errors → FAILED/effective_active false; uncertain outcomes → RECOVERY_REQUIRED/effective_active true. Target uses BUILDING for worker stages and may independently expose a retained READY/STALE published generation. Expired nonqueued effective jobs derive RECOVERY_REQUIRED without automatically editing the job. READY without a pointer also derives recovery. EMPTY is the existing internal zero-record generation state, not a new public empty-build permission.

`institution_repository.library_mutation` uses atomic unique `_id` lock insertion, waits twenty milliseconds between conflicts, and never expires unknown crashed owners automatically. Intelligence barriers use durable journaled lock writes and tag the job. Partial unique `(library_id,target)` index permits one effective-active job per target, not one per tenant. Target pointer and job updates require matching job identity/fence; lease checks also require unexpired time. No distributed workers or new locks were added.

The existing artifact LRU is runtime-only: max three entries, estimated 256 MiB, keyed library/generation/target, lock-protected, with checksums still checked on cache hits. VectorCache is tenant SQLite content-addressed by model/schema/embedding text. Neither cache authorizes a status READY. Known failed private artifacts and prior final generations are retained. Worker loop exceptions are suppressed; durable reconciliation, not restart loops, owns unknown outcomes.
''',
'freshness_audit': '''# Status call graph and cost audit

GET Staff status → authenticated actor → `service.status` → canonical UUID/current staff authority → `library_mutation(wait_seconds=30)` → current authority again → `store.source_records` → eligible catalogue count + projected/sorted/limited find → selected global enrichments in chunks of 500 → normalization + encoded-size bound → `fingerprint` (schema + complete normalized records) → latest dataset query → another locked membership check → independent Search and KG `control_status`.

Each target observation queries target pointer and effective-active job, derives lease-expired recovery, validates manifest namespace/identity/source identity/file set and every referenced file checksum, compares supplied current fingerprint, and optionally persists the first `stale_since` observation. Presentation separately queries latest attempt, published job and successful job count. Before 2I it also re-read the target and repeated all pointer/artifact verification. The narrow 2I change removes only that duplicate observation. Runtime `target_status` still performs its own verification per call.

Proven present: Mongo source count/find, projections, record normalization, full fingerprint/JSON encoding, selected global link reads, target/job/generation queries, filesystem resolution/stat/open and complete artifact checksums. A normal response has one complete source extraction shared by Search and KG. No model loading, embedding, FAISS index loading, graph deserialization, recursive directory walk or index rebuilding occurs in this status path. `pointer_manifest` hashes graph bytes but does not parse the graph structure; the worker's `validate` is the stronger publication validation.

Status is logically observational but not write-free: it acquires/releases a Mongo tenant barrier and can record stale_since. Production baseline observation therefore used direct read-only Mongo and files, never the status API or app database import (the latter creates a reading-list index). Benchmark fixtures use their own real Mongo database and filesystem roots.

Benchmark sizes: 0, 1, 10, 100, 1,000, 10,000 and 50,000 (the actual hard bound), plus a 1,000-record globally linked fixture. Published files are explicitly checksum-valid synthetic payloads with realistic vector/index byte growth, not loadable HNSW indexes. Separate workload measurements build and validate actual HNSW/KG. First-call figures are not cold disk: OS/Mongo caches were not flushed. Timed reads do not run the Mongo profiler; one separately profiled read supplies actual docsExamined. Instrumented per-read command counts, returned documents, BSON response bytes, checksum bytes/opens, CPU and tracemalloc peaks are disclosed. Physical storage I/O, server CPU and exact syscall counts are unmeasured.

One-browser polling is request-serialized by `institutionApi`. Several browsers can collide at the existing readability guard and receive retryable 503 before the expensive work. This is unavailable status, not coalescing or success. The helper makes up to two delayed GET retries (300/600 ms); failed page loads stop automatic polling and offer manual Retry. Multi-library requests use separate barriers. No cache of role or membership decisions exists.
''',
'freshness_contract': '''# Formal current freshness contract

Let R(L,t) be the canonical, library_book_id-sorted records returned by `source_records` at the status/publication serialization point. F(L,t)=SHA256(canonical JSON {schema:tenant-catalogue-v1,records:R}). A validated published pointer with READY/EMPTY target is fresh only when its persisted source_fingerprint equals F. Failed/running/recovery attempt state is retained separately; comparison cannot clear those states. No published pointer means NOT_BUILT unless the stored state incorrectly claims READY/EMPTY, which requires reconciliation. Artifacts must pass pointer/manifest/checksum checks on every request. This is an observation at a point in time, not a future mutation guarantee.

Eligibility is exact ACTIVE status and a nonblank string title, canonical tenant/book UUID, at most 50,000 records and 64 MiB encoded snapshot. Local title is used; absent/falsey authors, subjects, description and publication year may fall back to linked global work values, only if global active/is_active/searchable flags are not false. Global changes to such fallback values or flags are relevant even without a tenant metadata write.

Actual fingerprint fields are `library_book_id`, `library_id`, `global_work_id`, `status`, `title`, `authors`, `subjects`, `description`, `isbn_10`, `isbn_13`, `publication_year`, `edition`, `publisher`, `classification`. Whitespace/NFKC normalization and field truncation apply; authors and subjects are deduplicated/sorted with bounds. Reordering authors or normalization-equivalent edits may leave F unchanged. Classification/ISBN/edition/publisher normalized text remains in F. A change beyond truncation that does not change canonical R does not create a new fingerprint.

Search embedding input, from `artifacts.embedding_text → search.catalogue.semantic_text`, contains labeled title, authors, subjects, description and first-published value mapped from publication_year. ID/status/global link govern identity/eligibility and metadata integrity even when embedding text is unchanged. KG contains Book identity/label/global_work_id and canonical Author/Subject/Classification nodes/edges. KG has no description, year, publisher, edition or ISBN extraction rule.

Thus title/authors/subjects/add/remove/withdraw/ID changes affect both builders. Description/year can change embeddings without graph relationships; classification changes graph relationships without embedding text. global_work_id changes book graph provenance and may change enriched embedding/graph fields. Publisher/edition/ISBN change shared dataset metadata, although neither current ranking text nor graph relationships directly uses them. The accepted shared fingerprint conservatively marks BOTH targets STALE for ANY changed canonical source field. 2I preserves this deliberate over-invalidation instead of inventing narrower per-target fingerprints.

Neither builder's freshness depends on holdings availability, loans, reservations, fees, audit timestamps, accession display, shelf/call numbers, tags, acquisition notes, covers, ratings or language fields absent from SOURCE_FIELDS. Digital content/chunks, asset processing and visibility do not alter F. Snapshot format counts can change on a later dataset generation, but they are not freshness-authoritative. Membership/ownership changes affect current authority; they are not catalogue metadata. Build permission is rechecked before publication.

Mutation path audit: `library_catalogue_service.create_book/insert_locked` creates metadata, `update_book` updates fields, `link_book` changes selected global identity, `archive_book` withdraws eligible rows. `library_inventory_import.preview` does not change metadata; `apply` calls insert_locked per valid row and skips duplicates or only increases holdings according to policy. Partial imports make only successful metadata changes relevant; failed rows/duplicate no-ops do not force false STALE. `scripts/inventory_v2a_migration.py:apply_plan` also calls insert_locked under the tenant barrier. Canonical journal `library_lending_journal.commit/replay` and `library_v2c_plan` can apply book effects; stock management can change non-source location fields. TenantInventory.insert/update and supported administrative/script operations provide additional write surfaces. Global enrichment is a separate mutation surface. There is no universal authoritative metadata revision counter across these paths.

Concurrent supported catalogue changes serialize with snapshots/status/publication. The worker re-reads R and F before pointer publication and fails SOURCE_CHANGED if different from the snapshot. Changes after publication are detected by the next status/runtime read. Direct unsupported DB writers cannot be made atomic by this barrier, but the next complete source calculation detects changed content; 2I does not replace it with service-hook assumptions. New books alone never enqueue a build. A process restart never restores an authoritative status cache because none is introduced.
''',
'status_optimization': '''# Optimization decision

Implement only reuse of the verified target observation within a single `control_status` invocation. A private `_target_observation` returns `(existing_status, observed_pointer, verified)`. `target_status` retains its established dictionary contract; Staff presentation uses the same observed pointer and verification result instead of fetching/verifying again. There is no cache lifetime, shared map, tenant key ambiguity, extra lock, background thread or authorization reuse.

Correctness boundary: each request still fully hashes current source and each active immutable generation, queries current jobs, derives expired-lease recovery and checks current membership. One verified generation is presented with the row that named it. Last-good verification stays separate from latest-attempt status. Corruption before the next request is detected on that request. As previously, external filesystem tampering immediately after a checksum observation is outside a point-in-time READY guarantee; redundant same-request checks did not provide a durable integrity lease.

Rejected candidates: dataset sequence is not a mutation revision; counters/dirty markers lack complete mutation coverage including global enrichment and journal replay; TTL snapshots can mask metadata/job/authority changes; stat-only immutable metadata caches would miss same-size corruption; separating verification would weaken current READY semantics; coalescing under the existing readability/barrier behavior needs a new race/linearization proof and must still recheck each caller. No cross-request cache or coalescer is added. No frontend polling changes are needed for this backend-only optimization.

Use `institution_v2i_freshness_benchmark.json` for paired identical-fixture results, not the preliminary smoke run. Exact reductions in checksum work and target reads are distinguished from noisy wall-clock latency. Both the baseline and candidate are executed in one process against the same fixture state, with order alternated by size. First reads are reported separately and are not cold-disk claims. The archived original source hash is preserved in the frozen baseline. The focused checksum-call test demonstrably fails before the change and passes after it.
''',
'worker_audit': '''# Resident worker audit

`search/library_intelligence_api.install` uses the existing resident embedding model and reranker. Startup registers `TenantIntelligence.start` only when both exist; degraded lexical-only service still serves local fallback but does not claim semantic builds. `start` initializes durable indexes and starts one daemon. `loop` calls run_one serially, immediately proceeds after work or waits two seconds when idle; outer exceptions are swallowed. `close` sets stop and clears cache but does not implement durable job cancellation or join an in-flight builder.

`store.claim` selects earliest created_at QUEUED/effective_active across tenants, enters that tenant's durable barrier and conditionally changes only the still-queued job. It creates a fresh worker fence and 90-second lease, increments attempt, sets RUNNING/DATASET/start/heartbeat, and puts the fence on the matching target. A renewal thread extends a valid lease every ten seconds. check_lease/progress/publication require unexpired job/fence/effective-active state; fenced writers cannot overwrite successor outcomes.

Dataset construction rechecks requester's current tenant ADMIN authority and canonical metadata under the tagged barrier; reuses a checksum-verified READY dataset only if its complete fingerprint/snapshot agrees. Builds run outside the catalogue barrier. Search uses tenant SQLite embedding cache, batches of 32, normalized 384-dimensional vectors and a model lock; KG builds deterministic metadata nodes/edges. Worker validation runs before rename/publication. Publication reacquires the barrier, checks lease, ADMIN and fingerprint, then atomically updates the fenced pointer and records deterministic audit/success. Acknowledgement uncertainty leaves RECOVERY_REQUIRED and the pointer intact.

Bounds: 50,000 records, 64 MiB dataset, 256 MiB per validated artifact file, 3 runtime cache entries/256 MiB estimated retention. These are format/cache limits, not a worker RAM/disk admission policy. There is no free-disk preflight, RAM reservation, GPU budget, build deadline, cancellation check in long native operations, per-tenant job quota or fleet scheduler. model_lock serializes this tenant service's encode/rerank calls; it does not prove freedom from contention with the global engine's other request paths.

Worker restarts do not reclaim running jobs automatically. Expired nonqueued jobs derive recovery and remain effective-active; explicit reconciliation/recovery owns them. A crash while holding the tagged tenant metadata barrier can block library reads until existing explicit fenced recovery. Untagged domain locks are never cleared by intelligence recovery. Known prepublication failures retain private artifacts and last-good pointer; uncertain failures retain active ownership. No concurrency/resource/state semantics were changed by 2I.
''',
'workload_policy': '''# Future workload admission design — not implemented

Before starting a manual durable job, a future operator-approved admission layer would need current eligible count/encoded bytes, estimated missing embeddings for the exact model/schema/text hashes, measured CPU/GPU throughput, fresh available RAM/disk, existing retained artifacts/cache, worker occupancy and queued work. Estimate Search vectors as N×384×4 bytes plus measured HNSW overhead, metadata, validation copies and resident model/cache; measure Python JSON/dictionary expansion rather than treating serialized bytes as peak RAM. KG costs depend on extracted terms/unique nodes/edges, not N alone. Use upper prediction bounds calibrated on real representative tenants, not a claimed universal latency.

Disk reservation must cover snapshot + private new generation + embedding-cache growth + validation/rename overhead while preserving all last-good generations and a separately approved operator safety reserve. Never reclaim a last-good/unknown generation to admit new work. GPU contention must be measured against query latency if GPU use is later enabled. CPU-only measurements in this phase do not qualify GPU budgets.

Candidate *diagnostic/admission results*, not new durable states: CAN_START ('Resources checked; waiting for the current worker'), WAIT_WORKER ('Another library build is running; your request remains queued'), WAIT_RESOURCE ('Waiting for the approved resource budget'), OPERATOR_REVIEW ('Build cost or resource estimate needs review'), INSUFFICIENT_DISK ('Insufficient space to preserve the previous generation and build safely'), BLOCKED_RECOVERY ('An earlier outcome must be reconciled'). Current QUEUED remains the only durable waiting state until compatibility/migration is explicitly approved. Do not overload FAILED for a routine budget wait or clear recovery through admission.

Policy answers: start only after fresh authority, freshness/recovery and resource checks plus a serialized reservation; remain queued for ordinary worker occupancy; require intervention for uncertainty or unavailable estimates; reject resource-infeasible requests with a safe reason only under a separately approved API contract. A resource reading alone has a race, so a future design needs reservation ownership and release/restart proofs. Workload fixtures here demonstrate costs, not enforcement. No admission code, scheduler or resource check was added.
''',
'queue_fairness': '''# Queue fairness findings and future proposal

Current discovery is global oldest created_at QUEUED/effective_active; no explicit tie-breaker exists for equal timestamps. The single resident loop completes one job before looking again. A Search → B KG → C Search/rebuild normally runs in created order. A repeated active A Search returns the SAME job; A KG is a different independent target and may queue. Partial unique `(library_id,target)` protects duplicate effective work, not a per-tenant active limit.

Large A can hold the only worker for a long time, delaying B/C (head-of-line blocking). There is no preemption or duration estimate. In ordinary finite FIFO with a functioning worker, newer jobs cannot bypass older ones; equal timestamps, crashes/unknown outcomes, queue claim/barrier exceptions and blocked tenant locks limit a starvation-free claim. In particular, an oldest queued job whose tenant barrier is unreconciled can repeatedly fail acquisition before the worker considers later jobs. Claiming a new worker never reassigns an expired nonqueued job automatically. Stuck active jobs remain visible, but queue depth does not prove progress or health.

Isolation is by canonical UUID in predicates, barriers, artifact namespaces and fences. Resource contention is nevertheless shared by this process/disk/model. The current worker is serial because loop/run_one is called serially, not because the database forbids several externally started workers; deployment discipline matters. 2I did not start a second resident worker or change concurrency. Tests may claim isolated jobs to check ordering without enabling another production worker.

Recommended future progression: retain FIFO initially; propose bounded per-tenant pending depth and one tenant build at a time only after considering independent Search/KG requests and existing idempotency. Later evaluate fair tenant rotation with bounded aging, cost bands and resource admission, ensuring large jobs cannot starve forever. Any queue skipping, per-tenant limits, reservations or distributed scheduling needs separate approval and restart/fence tests. No scheduling policy was implemented.
''',
'observability': '''# Worker and diagnostics observability

Authoritative facts: queued/running/validating/publishing/succeeded/failed/recovery job state; job stage and progress counters; created/started/heartbeat/completed times; effective-active ownership; internal lease/fence and target pointer; published source/generation/checksums; audit outcomes. Completion requires validated fenced publication and durable acknowledgement, not progress_current==progress_total.

Derived diagnostics: queue wait/elapsed runtime from existing timestamps, heartbeat age and lease expiry (operator-only); last successful build duration already exposed by 2H; independently verified published generation may remain READY while the latest build FAILED or requires recovery. The existing stage values identify real work but have no separately persisted last-progress timestamp. heartbeat means the renewal thread recently renewed a valid lease, not that native embedding/index construction is making progress. No worker heartbeat document exists while idle; an empty queue cannot distinguish healthy-idle from offline. A job document never proves worker health.

Public Staff API already whitelists job fields via safe_job, maps errors to bounded BUILD_FAILED/RECOVERY_REQUIRED messages and keeps active generation/latest attempt distinct. UUIDs/counts/stage/progress/times/model parameters are appropriate scoped facts. No paths, raw exceptions, raw worker IDs, fences, credentials, lease internals or unrelated tenants should be exposed. `reconcile` returns bounded same-tenant codes and generation IDs, not raw directories/stacks. It is staff-readable today; recover is ADMIN-authorized.

Operator detail requires privileged access to the existing database/filesystem or explicit scoped reconciliation tooling: inspect worker deployment/process liveness, internal lease and tagged locks, job vs pointer identities, checksum/structural validation and retained generations. No new operator endpoint or global dashboard was introduced, and PLATFORM_ADMIN alone grants no tenant build permission. Record any future operator inspection through the approved access/audit policy, without persisting secrets in Staff responses.

Decision: improve efficiency using already verified facts; add no unmeasurable health badge or speculative durable diagnostic state. Gaps for a separately approved phase: idle worker liveness, last-progress time, structured internal failure categories, resource admission and bounded operator lifecycle view. Public presentation, polling and job state semantics remain unchanged.
''',
'recovery_matrix': '''# Explicit recovery decision matrix

| Interruption/fault | Known/unknown outcome and state | Last-good/artifact requirements | Existing action and retry |
|---|---|---|---|
| QUEUED before claim/process restart | Known unclaimed QUEUED unless a tagged/domain barrier is unresolved | Old pointer unchanged | Existing worker may claim queued job; no retry job needed. Never clear a domain barrier. |
| Hard crash after claim/before snapshot | Unknown nonqueued lease expiry → derived RECOVERY_REQUIRED | Old pointer retained, unless no prior generation | Operator inspect job/lock/pointer; existing scoped POST recover only when eligible; then explicit Admin retry if FAILED. |
| Crash during embedding/KG/validation | Unknown until lease expires; unfinished `.building` retained | Verify old generation, inspect private temporary payload; never promote it | Same explicit reconciliation/recovery. No auto restart/deletion. |
| Handled embedding/KG/validation/fs/checksum build failure before publication | Known FAILED if handled code is not an uncertainty code | Old pointer retained; temporary or renamed unpublished generation may remain | Admin may manually retry known failure; failed audit is deterministic. |
| Source/admin changes before publication | Known SOURCE_CHANGED/authority failure if handled; FAILED | Old generation kept; source may make it STALE | Correct authority/source, then explicit request. No stale snapshot publish. |
| Serialization/rename failure before pointer | Usually known FAILED; hard crash unknown | Inspect temp/final artifact and old pointer | Reconcile first if unknown. A renamed directory alone is not success. |
| WORKER_FENCED/HEARTBEAT_LOSS/WORKER_CRASH | Explicit RECOVERY_REQUIRED, effective-active remains true | Check lease, both fences, pointer, tagged barrier; never overwrite a newer owner | Existing recover fences known old owner; no blind retry or force-expiry. |
| Hard crash during fenced target update or after publish before acknowledgement | Unknown publication; lease expiry/recovery | Compare published_by_job_id and active_generation_id to job; full pointer + structural/dataset validation required | Existing recover reports SUCCEEDED only if pointer proves that exact job/generation; otherwise FAILED. Recovery emits idempotent outcome audit. |
| Acknowledgement-loss injection after pointer | RECOVERY_REQUIRED; old and new generation retained | Full validation of matching pointer needed | Explicit recover → SUCCEEDED, not an extra build. |
| Missing active directory/file/checksum mismatch/foreign manifest | Derived ARTIFACT_CORRUPT → RECOVERY_REQUIRED | Do not serve invalid generation; older files may exist but are NOT automatically selected | Read-only reconciliation; no generic artifact repair/promote API exists. If no eligible effective job can establish outcome, operator intervention is necessary. Do not claim recover repairs corrupt artifacts. |
| READY/EMPTY target missing pointer | Derived PUBLISH_POINTER_MISSING → RECOVERY_REQUIRED | Cannot infer publication from success counter/progress; inspect durable jobs/artifacts | Operator reconciliation; no invented restore/promote command. |
| Tagged intelligence barrier left by hard crash | Library reads may return 503 before status can derive recovery | Matching job, expired lease, old job+target fences and exact tagged holder must match | Existing recover can rotate BOTH fences and remove ONLY that tagged barrier after authority checks. Untagged/foreign locks are untouched. |
| Lease expiry/process restart | Original job is not automatically requeued/reassigned | Old valid pointer retained, no successor publisher permitted casually | Explicit recovery; safe retry only after known FAILED and fresh Admin authority. |

`service.reconcile` is dry-run; reads target status with observe_stale=False, validates active/succeeded artifacts, checks bounded `.building`/orphan directories and effective-active jobs. `service.recover` owns the existing explicit semantics, requires exact tenant ADMIN, distinguishes matching published pointer from unpublished job, validates matching published artifacts, resolves SUCCEEDED/FAILED and records idempotent outcome audit. No new recovery actions, cleanup, automatic lease expiry/reassignment or automatic retries were added. Hard power-loss durability/OS crash timing was not experimentally certified; controlled fixture failures and durable state/lease tests cover the stated software contract.
''',
'artifact_retention': '''# Retained artifact review and future policy

`run_one` creates `{tenantUUID}/{search|kg}/{artifactUUID}.building`. Successful rename creates an immutable final directory. Its job carries artifact_generation_id, target and library_id; manifest contains job_id, source_generation_id/fingerprint, creator, source metadata identity and checksums. Dataset directories have their own generation rows and manifest/records checksums. Embedding cache is a separate tenant SQLite file. No filesystem cleanup runs in worker exception/finally, so known failures deliberately preserve evidence, unfinished payload and occasionally renamed unpublished generations. previous_generation_id retains last-good lineage.

These files contain tenant catalogue metadata, authors/subjects/descriptions and derived vectors/relationships, and therefore may be sensitive even though they contain no private uploaded document chunks. Namespace UUID checks and symlink resolution prevent ordinary foreign path selection. Retention consumes snapshot/new generation/previous generation/cache bytes; repeated failures have no automatic age/count/disk quota. The baseline records the actual retained files, sizes and hashes without modifying them. Workload measurements separately report new-generation, cache and retained bytes.

Read-only reconciliation identifies bounded temporary generations and orphan final generations and relates each final artifact to same-tenant jobs. Up to 5,000 directory entries per target and 100 successful jobs are inspected by the existing routine; it is not an exhaustive unlimited garbage-collection inventory. Retention currently has no approved automatic cleanup rule.

Future proposal only: operator-reviewed inventory with exact tenant/job/generation ownership; legal/security retention requirements; minimum last-good/current/previous/unknown-publish protection; age and byte budgets for known terminal failures; dry-run manifest and explicit per-item approval; audit before/after deletion; atomic exclusion against active lease/publication/cache readers; bounded trash/quarantine and separately approved final deletion. Expired time alone is not ownership proof. Never delete RECOVERY_REQUIRED, active, referenced or ambiguous artifacts. No retained failed, TEST or unrelated artifacts were deleted in Part 2I; only task-owned disposable fixture roots are cleaned by TemporaryDirectory.
''',
'cancellation_design': '''# Future cancellation feasibility — no implementation

No cancellation endpoint/button was added. Existing UI label/constants mentioning CANCELLED do not establish a supported job transition or API. Current lease_query only accepts RUNNING/VALIDATING/PUBLISHING; introducing another state without compatibility/migration would risk losing renewal/publication ownership.

Queued cancellation could eventually use conditional state+effective ownership under the tenant barrier and an idempotent request/audit contract. Running Search/KG would need cooperative checkpoints between bounded embedding batches/graph chunks and a durable intent separate from acknowledged terminal outcome; a native FAISS add or model call is not safely interruptible by killing the thread. Validation can stop only before publication ownership is committed, while retaining private evidence. Cancellation during process restart must not create two owners.

The no-cancel boundary must begin before the publication critical section (rename/pointer/ack reconciliation protocol). After publication, success or RECOVERY_REQUIRED must be resolved from the actual pointer; a request cannot retroactively roll back a generation by declaring CANCELLED. Leases/fences and last-good protection continue to govern. New cancellation intent/state/index compatibility, restart/fault tests and artifact retention/audit are prerequisites requiring separate approval.
''',
'supervised_policy': '''# Supervised maintenance design — inactive

| Candidate policy | Correctness/cost/operational tradeoff |
|---|---|
| Manual only (current) | Exact Admin intent and existing durable infrastructure; no surprise load, but stale generations can persist unnoticed. |
| Admin-approved pending rebuild | Recommend next: explicitly review authoritative stale signal, exact source/target generation, cost/budget and authority before creating the existing manual job. Needs stale-intent versioning and clear approval invalidation; avoids silently scheduling work. |
| Scheduled window | Predictable contention period but requires approved timezone/window/missed-run semantics, budget reservation, authority rechecks and recovery suppression. Not implemented. |
| Debounced automatic | Quiet-period batching lowers repeated work; races with continuous changes, approval lifecycle, costs and expired ownership need proof. Not implemented. |
| Threshold based | Can protect small updates or large imports differently, but mutation count alone does not estimate embedding/cache/KG work or guarantee relevance/freshness. Not implemented. |
| Hybrid supervised | Admin approves a bounded target/source/budget intent with a later window; more flexible but more complex persistence/restart/permission semantics. Separate phase. |

For 100 indexed books → import 500 → 20 metadata edits → import 100, never create a job per mutation. Recommend a single target-scoped reviewable pending intention after a quiet period for presentation, with a maximum-wait alert during continuous mutation, explicit Admin approval and fresh admission before request. Search and KG remain independent; a changed source after approval invalidates or explicitly refreshes the approved intent. No intent persistence or timer was added here.

Required future facts: authoritative current vs published fingerprints/revisions, which fields changed, last relevant mutation time, count/volume and estimated missing embeddings/graph work, exact approval identity/scope/expiry, active/queued jobs, resource reservation and recovery flags. Existing dataset sequence is NOT a mutation revision. All mutation paths including imports/replay/global enrichment must participate before using revision-driven triggers. Large tenants/frequent mutations need aging and budgets; small tenants may finish before progress is observed. Any recovery-required outcome suppresses automatic creation until explicit reconciliation.

Before automation: complete mutation contract, freshness/race/restart proof, calibrated resource/admission and tenant fairness, operator liveness/recovery/retention observability, idempotent approvals/triggers/audits, security revocation tests, last-good crash consistency and workload/query-contention evidence. No automatic/scheduled policy is activated by this design.
''',
'hnsw_incremental_review': '''# Actual tenant HNSW incremental feasibility

The tenant builder uses `faiss.IndexHNSWFlat(384,16,METRIC_INNER_PRODUCT)`, normalized float32 vectors, efConstruction=80 and efSearch=64. It is not the global IndexManager base/delta/tombstone stack. HNSW labels are sequential row offsets into immutable metadata.json/vectors.npy, with canonical library_book_id carrying tenant identity. There is no IndexIDMap, tenant tombstone store, deletion API or persistent update journal.

FAISS HNSW supports adding vectors in memory; current generation semantics deliberately do not expose in-place append. A true delete/update cannot simply remove/replace arbitrary existing graph vectors in this flat HNSW contract. Keeping old labels plus append duplicates would need versioned ID resolution/tombstones, freshness/eligibility filters and validated generation metadata. Current canonical hydration filters visibility and source fingerprints force local fallback on stale input; this does not turn the generation into an incrementally maintained index.

New book: full new generation today, with tenant VectorCache reuse for unchanged embedding texts. Edit: recompute affected text cache entry but build a complete new HNSW; non-embedding field edits can reuse vectors yet still change shared snapshot. Delete: omission in the next snapshot, never in-place HNSW deletion. Reimport: canonical duplicate handling plus content-addressed cache may avoid encoding, but identity/metadata must be rebuilt consistently. Bulk/repeated changes amplify snapshot/build costs and should be coalesced before an explicitly approved full rebuild.

Validate checks model/dimension/parameters, finite normalized vectors, row identity/count, reconstruct_n equivalence and source dataset ownership; publication is private generation validation → atomic rename → fenced pointer. Incremental mutation would require a new generation/ID/deletion/recovery design and ranking regression evidence. Not safe as a narrow 2I change. No incremental HNSW implementation was added.
''',
'kg_incremental_review': '''# Actual tenant KG incremental feasibility

`artifacts.build_graph` creates Book `book:{library_book_id}` nodes with title/global_work_id and canonical shared feature nodes via `knowledge_graph.core.terms/feature_id`. Features are Author, Subject and Classification; relation names come from `knowledge_graph.relations.RELATIONS` or HAS_CLASSIFICATION. Canonical term deduplication is per book; feature nodes use deterministic IDs and first-seen labels. Edges are source Book → feature with relation, sorted deterministically, serialized as one graph.json next to metadata.json and the checksummed manifest.

Book source provenance is implicit in each edge's source ID and the complete metadata snapshot, not an incremental event/edge ownership journal. There is no per-record mutation ledger, shared-node reference count, tombstone/update API or orphan cleanup protocol. Validation reconstructs expected nodes/edges from the entire source records, checks duplicate node IDs/edge tuples, ownership/counts and graph equality. This is whole-generation consistency.

A single book edit could theoretically replace its outgoing relationships, but removing a shared author/subject/classification requires reference accounting and deterministic label selection when the first contributing book disappears. Book deletion, relationship removal, canonicalization collisions, duplicate imports, orphan removal and global provenance changes must agree with full reconstruction. Current graph has no cross-book extraction edges beyond shared feature nodes; future graph schemas may add more dependencies. Runtime traversals/filters must never see half-applied metadata/graph revisions.

Recommend full immutable generation rebuild with existing validation/publication until a separately reviewed provenance/reference-count or persistent graph design proves equivalence and rollback/restart safety. No incremental KG code, schema or extraction change was made.
''',
'recommendation_dependencies': '''# Real recommendation dependency graph

Global `recommendation/api.py` → `RankedRecommendationPages` → `recommendation/recommendation_service.get_recommendations`: user behavior from search_history/issues/reservations/feedback, profile construction, global Search HTTP `/search` with MACHINE query contract, canonical books, existing subject/author/behavior/rating/popularity/availability/diversity scoring. It has a transitive dependency on GLOBAL Search availability and its existing retrieval, not the tenant intelligence status endpoint or tenant KG. No independent tenant recommendation vector index is used by this path. The separate KG related-book tools are not the same recommendation formula.

Tenant UI `frontend/src/lib/libraryCatalogue.ts:libraryRecommendationPage` → recommendationCandidates (existing global candidates with eight-second abort timeout and safe empty fallback) → tenant POST `/libraries/{id}/catalogue/recommendations` → `backend/services/library_catalogue_experience.recommendations`. Backend checks current tenant membership/read context, intersects up to 200 supplied global work IDs with usable local records, then fills only with deterministic local recent acquisitions and canonical hydration. It requires neither tenant HNSW nor tenant KG READY. A global candidate failure can still produce local discovery; it never inserts foreign/global filler into a local collection. The frontend verifies source/library identity.

Assistant and global related-book/KG tools remain separate existing providers; no algorithm or ranking change is authorized. Isolated 2G private-library and catalogue suites plus 2I checks exercise allowed local recommendations while intelligence is NOT_BUILT, deny outsiders and exclude foreign records. Full live external provider uptime is not established by isolated tests. Only status-presentation efficiency changes, so dependency source hashes remain unchanged.
''',
'improvement_review': '''# Improvement review

The justified implementation is limited to eliminating redundant same-response artifact checks and target re-read. It does not claim O(1) status cost: catalogue extraction/fingerprint and artifact bytes still scale with the bounded tenant. Dataset sequences cannot safely substitute for metadata revisions. Full checksum verification continues after every new request, including after same-size corruption. No optimistic READY cache was deployed.

The review found operational limits worth preserving explicitly: lock-induced 503 under multi-browser reads; one serial worker and long-job head-of-line blocking; no idle worker liveness proof; renewal heartbeat does not imply progress; no separate last-progress timestamp; no RAM/disk admission/reservation; retained failed artifacts can grow; explicit recovery and no job cancellation. None justifies silently adding a scheduler or changing accepted durable states.

New tests target the actual duplication, relevant/irrelevant source fields, mutation bypass/enrichment, cross-request corruption, current authority, tenant separation, source changes during publication, real queue/progress and recommendation independence. Existing frozen suites and browser tests remain evidence with their precise limits. Preexisting regression failures are not hidden by deselection or expected-hash rebasing. Source/artifact/catalogue preservation is compared to the task-start baseline, not old 150-record assertions.
''',
'next_scope': '''# Recommended next phase

Part 2J: an operator-only, read-only worker liveness and recovery diagnostic surface, designed against current jobs/leases/tagged barriers, with no automatic action. First obtain review of this Part 2I evidence and baseline failures. Specify idle liveness, heartbeat-vs-progress semantics, bounded same-tenant lifecycle/reconciliation views, safe operational access and audit. Use it to qualify resource/admission estimates before considering an Admin-approved pending rebuild workflow.

Automatic/scheduled maintenance, cancellation, retention deletion, incremental HNSW/KG, multiple workers and global controls remain separately gated future proposals. No later-phase implementation begins in this task.
''',
}


def write_json(name, value):
    (R / f'institution_v2i_{name}.json').write_text(json.dumps(value, indent=2, default=str), encoding='utf8')


def main():
    for name, text in DOCS.items():
        text = text.replace('`link_book`', '`link_global`').replace('`archive_book`', '`withdraw`')
        text = text.replace('Source and contract |', 'Source and contract (all paths relative to D:\\SDC\\LibraryLLM) |')
        if name == 'freshness_contract':
            text += '\nGlobal enrichment write surface: `backend/services/book_service.py:create_book/update_book/delete_book` changes global books. Semantic/eligibility mutations use the existing global `catalogue_mutation` protocol and compare atomic pre-images, but that is not a tenant metadata revision and does not prove scoped invalidation for local overrides or linked fallback values. It cannot replace a tenant fingerprint in Part 2I. No global mutation method was invoked by this task.\n'
        (R/f'institution_v2i_{name}.md').write_text(text, encoding='utf8')
    print('Source audit/design reports:', len(DOCS))


if __name__ == '__main__':
    main()
