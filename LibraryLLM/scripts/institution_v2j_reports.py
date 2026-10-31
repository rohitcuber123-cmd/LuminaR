"""Source-grounded Part 2J documentation; no app/database imports."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reports'
DOCS={
'architecture':'''# Part 2J diagnostic architecture

Project root: `D:\\SDC\\LibraryLLM`. Existing 2G–2I source is unchanged, including the uncommitted 2I `_target_observation` optimization. No route or Staff page is added.

| Layer | Actual implementation |
|---|---|
| Local interface | `scripts/diagnose_library_intelligence.py:main`, `readable`; bounded JSON/text stdout, sanitized errors, no output-file or action argument. |
| Independent operator boundary | `backend/services/library_operator_access.py:connect_operator`, `OperatorReader`; explicit loopback Mongo SCRAM credential and database-local built-in read role. No app JWT, role lookup or automatic grant. |
| Diagnostic projection | `backend/services/library_intelligence_diagnostics.py:inspect`, `job_view`, `worker_view`, cursor helpers; explicit UUID scope, bounded read operations and derived observations. |
| Artifact observation | `ArtifactInspector.content/generation/inventory`; per-tenant Search/KG namespaces, bounded manifests/stat inventory, opt-in shared checksum budget, no native/model/catalogue loading. |
| Existing authority | Staff APIs still use `library_inventory_access` current identity/exact membership. Manual builds still use `store.request_build` and `TenantIntelligence.run_one`. No operator integration into these handlers. |

Read flow: local process → explicit operator Mongo authentication → connectionStatus exact role check → bounded job page, pointers, scoped active jobs and database FIFO context → tenant-only artifact/manifest observations → batch unique-job-ID associations and source generation references → second pointer observation → redacted output. No locks, stale_since writes, job progress/lease updates, publishing, recovery or audits are performed by diagnostics.

Actual collections are `institution_intelligence_jobs`, `institution_intelligence_targets`, `institution_intelligence_generations`, `institution_locks`. No diagnostic query reads books, institution_library_books, memberships, users, private document stores or global HNSW/KG. The CLI does not import `backend.database.mongodb`, the native store/validator, backend.main, or the Search API: those imports can initialize indexes or workers.

Current durable schema is retained: job state/stage/counters/times/lease/fence/owner, generation identity/fingerprint/checksums and target active/previous/published-by pointer. Part 2G's 90s leases, 10s renewal, serial worker and created_at FIFO are not changed. There is no new collection, index, telemetry field, scheduler or worker.
''',
'operator_authorization':'''# Operator authorization and deployment boundary

Inspection found no infrastructure-operator application identity. `backend/platform_dependencies.py` grants installation Platform authority, not tenant authority or infrastructure access. `scripts/library_intelligence_cli.py` uses ordinary tenant JWTs for existing build/reconciliation/recovery routes; it is not suitable as a stronger operator boundary. `reconcile_inventory_v2a.py` is an administrative local script but assumes environment DB access, not an independently authenticated diagnostic operator. Neither is silently promoted.

The new surface is a local command, not a remotely reachable endpoint. `connect_operator` requires an explicit `LUMINAR_OPERATOR_MONGO_URI` (or explicitly named secret environment variable). It never falls back to MONGO_URI or .env. URI must use mongodb://, one loopback endpoint, explicit username/password, matching database/authSource and SCRAM-SHA-1/256. The authenticated server response must contain exactly one database-local user with only built-in `read` role on that same database. Anonymous, remote/SRV, mismatched database, app tokens and write/admin roles are rejected. Each invocation authenticates afresh. Output never contains URI, password, principal username, raw exceptions or credential-bearing arguments.

This is Mongo infrastructure authorization, not a new application/global superuser role. A person with a Platform role or tenant ADMIN role gets no access without a separately provisioned infrastructure credential. Conversely, the diagnostic credential does not mint an app token, change membership, or grant a build/recovery action. Trusted operator access intentionally includes database queue context across tenant UUIDs; jobs/artifacts requested for a library remain scoped.

Deployment prerequisites: operator-managed Mongo authorization enabled, loopback isolation, OS protection of credentials and code/artifact roots, separately approved database-local read account and credential rotation/revocation. The built-in read role is database-wide; the command itself restricts queries to four collections. It is not a per-tenant Mongo credential. An unauthenticated or compromised Mongo server cannot supply a meaningful authorization boundary; do not deploy this tool on such a setup as a security substitute. The command does not weaken or repair the existing database deployment.

No production operator account or secret was created/configured. At task time the operator URI was absent, so production command use fails closed. Authentication and server-enforced denial of writes were actually tested on separate task-owned mongod instances launched with --auth, using independently provisioned fixture read accounts. No existing Mongo service/configuration/user/role was changed. Production authorization deployment is unqualified until an operator provisions and reviews it.

## Usage

From the project root, with a valid secret environment variable already supplied by the approved operator secret mechanism:

```powershell
.venv\\Scripts\\python.exe scripts/diagnose_library_intelligence.py --library-id <canonical-library-uuid> --format text
.venv\\Scripts\\python.exe scripts/diagnose_library_intelligence.py --library-id <canonical-library-uuid> --job-id <canonical-job-uuid> --format json
.venv\\Scripts\\python.exe scripts/diagnose_library_intelligence.py --library-id <canonical-library-uuid> --state FAILED --limit 10 --format json
.venv\\Scripts\\python.exe scripts/diagnose_library_intelligence.py --library-id <canonical-library-uuid> --verify-checksums --checksum-budget-mib 16 --format json
```

Never put a URI/password on the command line or in a report. The command has no credential-provisioning, grant, recovery, cancellation or write mode. --database/--uri-env exist for explicit deployment/fixture binding, not privilege elevation. Default artifact root is the existing tenant root; --artifact-root cannot point to known global infrastructure or an escaping/reparsed namespace.
''',
'diagnostic_contract':'''# Read-only diagnostic contract

Schema `tenant-intelligence-diagnostics-v1`. Required canonical library UUID; optional explicit job UUID, state filters, keyset cursor and limits. Output separates observed facts, derived conditions and unavailable information. It never determines authoritative catalogue freshness or runtime READY.

| Output | Meaning |
|---|---|
| jobs / selected_job | Scoped durable job whitelist; enums, IDs, actual counters, times, lease evidence and safe failure categories. No raw error strings, fences or paths. |
| tenant_active_jobs | Up to two current effective-active target jobs for the requested tenant, independent of history filtering. |
| worker | Database-wide resident-worker job observations; process_alive/startup/shutdown/restart remain UNKNOWN/NOT_AVAILABLE. Canonical recorded worker IDs are one-way correlation references, not PIDs or proof of liveness. |
| queue | Explicitly authorized database queue context: exact count at query time, up to three oldest observations, age, executing-state count and selected job position range. Other tenant UUIDs here are intentional operator context, never ordinary Staff output. |
| targets | Separate stored state, active/previous references, bounded latest observed attempt, checksum evidence and manual-investigation flag. created_at ties are flagged; latest observed is not guaranteed complete history. |
| artifacts | Bounded namespace references, presence, manifests, associations, known-file sizes and verification level/coverage. Missing candidate may mean never created, renamed or lost; no guessed failure outcome. |
| resources | Actual local-volume disk observation if available; worker CPU/RAM/GPU NOT_AVAILABLE without a trustworthy PID mapping. |
| actions_available | Always empty. |

No durable health states are added. Zero work counters do not imply failure; full counters do not imply publication. Heartbeat, progress, state transition and publication acknowledgement are distinct. queued_at uses created_at with its basis stated. There is no existing last_updated or last_progress timestamp: output is NOT_AVAILABLE/UNKNOWN rather than an invented time.

Mongo reads are best effort on standalone Mongo, not a transactional snapshot. Observation start/end times are returned; pointers are read again and a change makes verification inconclusive. Job/counter/count observations can also change during the window. Repeat inspection rather than acting from a stale diagnostic. No read snapshot becomes authoritative over membership, jobs or generation state.

Default job page 20, max 50, one library and known state filters. Cursor is library/filter-bound, based on insertion ObjectId descending (not FIFO created_at); foreign/malformed cursors are rejected. Exact job lookup uses job_id_1. Default history uses the existing _id index and can examine extra foreign rows in sparse histories; one-second Mongo operation limits and a 1–30 second invocation budget fail closed. A future dedicated history index requires independent review; the command creates none.

Artifact enumeration default 20 entries per Search/KG directory, max 50, plus bounded prioritized references (max limit+2 candidates per target). Each manifest is at most 64 KiB; fixed expected filenames only. No global recursion. Default checksums OFF. Explicit verification uses a shared default 16 MiB, max 256 MiB byte budget and the same deadline. Reads never exceed the originally statted file length; growth/mtime/identity changes become inconclusive and partially read bytes count against the budget. OS calls on failing storage are not forcibly preemptible; deadlines are checked between bounded operations/chunks.
''',
'worker_liveness':'''# Evidence-based worker liveness

Existing source: `search/library_intelligence.py:TenantIntelligence.__init__/start/loop/close/run_one` and `library_intelligence_store.claim/heartbeat`. One configured local worker, 2s idle wait, 90s lease and 10s renewal. Job worker_id is recorded at claim; it is not a PID. No durable independent idle heartbeat, startup record, shutdown record or worker restart log exists.

| Classification | Evidence and limit |
|---|---|
| UNKNOWN | No executing observation, missing/future heartbeat, or only recent job renewal/lease. An idle live worker and an absent worker cannot be distinguished. |
| STALE_HEARTBEAT | An observed executing-state job has an old heartbeat or expired/missing lease. This is stale job renewal evidence, not proof that the process died. |
| DEGRADED | Unresolved recovery or competing executing-state observations in the configured serial architecture. It describes operational inconsistency, not process death. |
| HEALTHY | Deliberately never emitted: current data cannot prove live healthy execution. |

Recent means within 30 seconds (three existing renewal intervals), explicitly a diagnostic window, not a new lease rule/SLO. Valid lease alone never produces HEALTHY. Heartbeats ahead of observation time are CLOCK_SKEW, not recent healthy evidence. Observation end time is used after reads so a normal concurrent heartbeat is not mistaken for a future event.

Canonical `tenant-{UUID}` worker IDs are exposed only as stable hashed correlation references. Different recorded owners can be inspected, but restart time/process identity remains NOT_AVAILABLE. Legacy/arbitrary owner strings are not echoed. Real process CPU/RAM and startup/shutdown/restart require a separately approved independent telemetry mechanism; no worker or job field is changed in this phase.
''',
'job_inspection':'''# Durable job inspection

Actual fields: job_id/library_id/target, state, stage, progress_current/total, attempt, created_at, started_at, heartbeat_at, completed_at, lease_expires_at, effective_active, artifact_generation_id, requested_generation_id, worker_id and error_code. Fences, raw worker IDs/error messages and user/account data are not output. State/stage/failure values are whitelisted; malformed values become UNKNOWN/OTHER/BUILD_FAILED. Numeric counters must be bounded actual integers.

The command returns scoped history (20 default/50 maximum), an optional scoped selected job, and separately scoped effective-active jobs, so a FAILED history filter cannot hide a running/recovery attempt. Job_id lookup is bound to library UUID. A foreign job UUID produces SCOPED_JOB_NOT_FOUND. Insertion-ID keyset pagination avoids unbounded offset and does not pretend to be the worker's FIFO ordering.

Queued time is explicitly derived from created_at. Duration is a completed interval for known SUCCEEDED/FAILED jobs or an elapsed observation for other started jobs. Missing fields on old jobs stay readable and are NOT_AVAILABLE. There is no fabricated last updated/progress timestamp or percentage. State SUCCEEDED is an acknowledged durable fact; progress counters alone never imply success. Published target references remain separate from attempts and do not prove serving eligibility.

Only the bounded observed page/selected/current active jobs inform latest observed attempt. Timestamp ties are flagged rather than promising a unique latest identity. No complete history claim is made. No job is acquired, renewed, requeued, recovered, cancelled, edited or removed by inspection.
''',
'queue_observability':'''# Queue and head-of-line visibility

The actual worker chooses earliest created_at QUEUED/effective_active and has no tie-breaker. It completes run_one serially. Partial unique (library_id,target) suppresses duplicate effective builds for the same target, not one build per library. Existing tenant barriers can block the oldest queued library; long builds can delay later tenants.

The authenticated operator sees database queue counts grouped over indexed known active states, up to three oldest observations, age of the oldest and up to five bounded executing/recovery observations. These are durable states, not confirmed executing processes. Global queue context intentionally carries each job's own library UUID, separately from the requested tenant's job/artifact pages. No catalogue or library-name hydration is required.

For one explicit selected queued job, an indexed aggregate counts strictly earlier timestamps and equal timestamps. Position is `[earlier+1, earlier+ties]`, with FIFO/no-tie-breaker basis. It is approximate point-in-time evidence, not a deterministic ordering promise or ETA. General history uses insertion-ID order and is labelled separately.

Head-of-line diagnosis is POTENTIAL_TENANT_BARRIER_BLOCK if a current oldest tenant barrier is observed, POTENTIAL_WAIT_BEHIND_EXECUTION_STATE if durable executing observations exist, otherwise UNKNOWN or NO_QUEUED_JOBS. A short legitimate barrier can disappear immediately; this never proves an abandoned lock. Queue age is shown numerically but no prolonged-wait threshold/SLO is invented. Persistent observations require manual investigation, not forced release, reordering, fairness scheduling or preemption.
''',
'progress_observability':'''# Heartbeat versus progress

Existing heartbeat updates heartbeat_at/lease_expires_at every ten seconds while a valid job lease remains. Existing progress updates stage/state/counters but does not persist a last-progress timestamp. Existing audit events record request/outcome, not a durable intermediate progress history. None is sufficient to reconstruct progress recency.

The output therefore distinguishes recent/stale/missing/future job heartbeat from `progress.recency=UNKNOWN` and `last_progress_at=NOT_AVAILABLE`. Missing last_updated is not replaced with heartbeat time. Stage text/counters are real durable observations; a long embedding/native index call may make no counter update while renewal continues. A terminal counter is not acknowledgement of validated pointer publication.

No new timestamp field, stage history, worker heartbeat document or UI badge was added. Proving stalled progress would require a separately approved telemetry contract with fencing/backward compatibility and race tests. This phase reports the uncertainty rather than claiming stopped or healthy progress.
''',
'recovery_diagnostics':'''# Recovery evidence and decision table

| Condition | Outcome evidence | Published/last-good evidence | Safe retry / intervention |
|---|---|---|---|
| QUEUED | Known unclaimed state; no liveness proof | Pointer inspected separately | No new retry; inspect current worker/queue. |
| RUNNING/VALIDATING/PUBLISHING with valid lease | Nonterminal durable claim; process/progress unknown | Existing pointer may be retained | Do not retry/cancel from this surface. |
| Expired executing lease | Derived recovery condition while stored state stays unchanged | Check active/previous pointer and checksums explicitly | Existing explicit operator reconciliation required; never force lease expiry. |
| FAILED | Known handled failure category, safe generic summary | Last-good reference and integrity tier independent of latest attempt | Only existing manual API may recheck known retry eligibility and fresh ADMIN; CLI implements no retry. |
| RECOVERY_REQUIRED / acknowledgement uncertainty | Unknown publication outcome | Match manifest/pointer/job/dataset references; opt-in file checksums | Manual reconciliation; no blind retry/clear. |
| Missing final/temp candidate | Could be never created, renamed or missing | Presence only; no fabricated corruption diagnosis for a never-created queued artifact | Inspect job stage/outcome and other references. |
| Invalid/foreign manifest, missing expected file, checksum mismatch | Inconsistent artifact evidence | Existing pointer preserved; integrity not verified | Manual investigation, no artifact repair/promotion. |
| Pointer changes during read | Concurrent observation, not a consistent snapshot | Cannot bless old observation as current | Repeat read-only inspection. |

The current helper never calls `service.recover`, `reconcile`, `target_status`, `source_records` or artifact native validators that import write-on-import state. Existing explicit recovery semantics remain the 2I matrix: validate exact matching published-by-job/generation and reconcile SUCCEEDED versus FAILED; fence both matching owners before releasing only an eligible tagged barrier. Untagged locks and corrupt pointers without a safely recoverable job require independent operator action. No invented repair command is supplied.

Published checksum integrity is not an authoritative READY signal. Catalogue freshness, full dataset records, native FAISS equivalence and graph structure are not checked here. The tool can establish anchored file-integrity evidence within budget and show retained references; runtime usability remains NOT_DETERMINED. Last-good files/pointers are not switched or destroyed by diagnosis.
''',
'artifact_inventory':'''# Bounded private artifact inventory

Only `<tenant-root>/<requested-library-UUID>/search` and `/kg` are enumerated. Canonical generation UUID and `.building` candidates are accepted; unsafe/reparsed/escaping namespaces are refused. No recursive global, catalogue, RAG, private document or asset scan occurs.

Prioritize active and previous pointers, then selected/current/page job references, then bounded directory enumeration. Final and temporary candidates may both be shown for a job: missing means NOT_CREATED_OR_MISSING, not an invented lost-generation outcome. Output carries generation UUID, target, temporary/present flags, active/previous/job reference basis, manifest level, checksum status, associated same-tenant jobs and reconciliation category. Manifest job IDs and known pointer/page IDs are batch-resolved using unique job_id indexes; no unindexed artifact-ID scan across all job history and no N+1 lookup occurs. An unreferenced invalid/no-manifest directory may have unknown job ownership; it is not guessed.

Coverage is explicit. Default enumerate 20 entries per target, max 50; total candidates at most limit+2 per target. Filesystem order is not exhaustive history ordering. present_directory_count and unique present generation count are distinct from observed/missing candidate references. Known-file bytes include only the bounded fixed artifact filenames and manifest, not recursive disk usage or embedding-cache/dataset-root totals. Entire tenant retained-generation total/bytes can be NOT_AVAILABLE when coverage is partial.

Retained FAILED, RECOVERY_REQUIRED, incomplete temporary, previous and historical/unreferenced namespaces are distinguished. Byte/mtime and row digests before/after actual CLI calls prove read-only observation in fixtures. No failed/temporary/TEST/global artifact, directory, embedding cache or generation is deleted, renamed, repaired, promoted or expired by the command. Task-owned test servers/temporary fixtures are torn down only by their test harness after evidence checks.
''',
'artifact_validation':'''# Artifact verification levels and bounds

The existing immutable-generation protocol is authoritative. Directly importing native `library_intelligence_artifacts.validate` would import the write-on-import store and includes catalogue/native structure work; it is not a safe lightweight diagnostic dependency. The new helper mirrors a bounded subset, with explicit limits rather than claiming native validation.

Default checks: namespace containment, bounded manifest read, duplicate-key/nonfinite JSON rejection, schema/library/generation/target identity, canonical source generation/fingerprint, integer book count, exact expected filenames and checksum syntax, presence/stat of expected files. Search empty must be an actual bool. No arbitrary manifest file path can be selected. Active manifest hash and source/book/job identities must match the durable target pointer. Job references are resolved in the same tenant and source generation rows must be READY with the same fingerprint.

Default checksums are NOT_REQUESTED; no full vectors/graph/metadata bytes are read. Explicit --verify-checksums hashes fixed files in chunks within a shared byte/deadline budget (16 MiB default, 256 MiB maximum). Too little budget yields CHECKSUM_BUDGET_EXCEEDED, never verified. Actual bytes are counted even on partial failed reads. Files are bounded to their initial stat size and checked for size/mtime/inode change afterward; growth never permits budget overread. Manifests are at most 64 KiB and individual artifact file checks are capped at 256 MiB.

`POINTER_ANCHORED_MANIFEST` differs from unanchored `IDENTITY_VALID_MANIFEST`. `VERIFIED_WITHIN_BUDGET` requires active pointer anchor, expected-file checksum MATCH, same-tenant job/source linkage and unchanged pointer observation. Previous retained generations have no separately persisted old target manifest anchor, so checksum-to-manifest agreement is a lower evidence tier. Missing source/job evidence stays NOT_VERIFIED. Native index type/vector reconstruction, graph equivalence and metadata record ownership are NOT_CHECKED; the original worker performs these before publication. Catalogue freshness and serving usability remain NOT_DETERMINED.

There is no shared verification cache and no diagnostic endpoint polling. Every explicit invocation observes current facts; the Staff 2I checksum optimization remains byte-for-byte unchanged. No checksum result changes a generation/job state.
''',
'resource_diagnostics':'''# Resource diagnostics

The worker stores an opaque boot worker_id, not an OS PID or a trustworthy hardware identity. Existing infrastructure supplies no safe PID map, CPU/RAM sampler or GPU allocation record. Worker CPU utilization, process memory and GPU memory therefore return NOT_AVAILABLE. The diagnostic process's own memory is not mislabeled as the worker's.

For an existing validated local tenant root, shutil.disk_usage supplies an actual local-volume total/free byte observation. Missing/unreadable root yields NOT_AVAILABLE. The root path is not output. This is a read-only observation, not a build admission/reservation or retained-generation accounting guarantee. Bounded known artifact file sizes are reported separately from volume capacity. No GPU monitoring, resource daemon, worker telemetry, admission policy, new index or scheduler is introduced.

Performance fixtures measure diagnostic-process CPU/tracemalloc peaks and DB work; those are implementation benchmark costs, not production worker resource measurements. They are labelled as such in the performance report. No hardware/latency SLO is invented.
''',
'improvement_review':'''# Part 2J improvement review

The task adds a cohesive authenticated local diagnostic surface without editing existing runtime code. It avoids the mutation-lock/stale_since side effects and catalogue/checksum cost of ordinary status, yet keeps that status authoritative. It does not create a second dashboard or overload PLATFORM_ADMIN.

Review-driven safety improvements: require explicit database-local read identity rather than app JWT or anonymous environment defaults; redact raw exception/path/fence/owner strings; retain actual counters and unavailable timestamps; range FIFO positions across ties; distinguish current tenant jobs from intentional database queue context; preserve pointer and attempt separately; batch job identity associations using existing unique indexes instead of an unindexed artifact-history scan; bound manifests, candidates, outputs and shared checksum bytes; flag concurrent pointer/file changes; deny any action/grant/cleanup mode.

Known limits remain visible: no independent idle/process liveness or progress recency, no native/full catalogue validation, bounded non-exhaustive retained inventory, best-effort multi-query observation and sparse history scans bounded by timeout. Production infrastructure operator credential/authentication/OS-secret deployment is not provisioned by this task. The two existing backend failures remain enabled and are not rebased. These limits support a PARTIAL overall result rather than a clean production acceptance claim.
''',
'next_scope':'''# Recommended next phase

Part 2K: independently authenticated worker liveness and progress telemetry design/qualification. First review Part 2J, provision/review the production read-only operator credential through the existing infrastructure security process, and specify a trustworthy idle/process identity and progress-recency channel with bounded retention, fencing and backward compatibility. No automatic action should follow from that telemetry.

No next-phase code is implemented here. Automatic/scheduled maintenance, job cancellation, recovery automation, artifact deletion, incremental HNSW/KG, extra/distributed workers and global rebuild controls remain outside scope.
''',
}


def main():
    for name,text in DOCS.items():
        (R/f'institution_v2j_{name}.md').write_text(text,encoding='utf8')
    print('Source-grounded diagnostic reports:',len(DOCS))


if __name__=='__main__':main()
