# Part 2K architecture — isolated prototype only

Decision: no production runtime integration. The native worker has no per-instance lifecycle observer seam, its `close()` does not join an in-flight build, and deployment writer ownership/supervisor proof is unqualified. Process-global laboratory wrapping is unsuitable for production. Existing Part 2G–2J files, routes, indexes, job schemas and privileges stay byte-for-byte preserved; see preservation.json.

## Actual call graph

`search/api.py → search.library_intelligence_api.install(app, engine) → TenantIntelligence(encoder, reranker, model_version)`. Install registers startup `service.start` only when resident embedding model and reranker both exist; shutdown calls `service.close`. No lexical-only build capability is added. `TenantIntelligence.start → store.initialize → daemon loop → run_one → store.claim(worker_id)`. Claim chooses oldest effective-active QUEUED job, enters `intelligence_barrier → institution_repository.library_mutation`, atomically sets RUNNING/DATASET, worker_id, fresh fence, started/heartbeat and 90-second lease, then target fence.

`run_one → separate renewal thread → store.heartbeat(lease_query)` every ten seconds. `store.dataset → native Library Admin guard + lease + canonical local/enriched source + immutable source fingerprint/snapshot/generation`. Search uses model lock, bounded32 embedding batches, tenant SQLite vector cache, normalized384 vectors and FAISS HNSW; KG uses canonical metadata terms and deterministic nodes/edges. Native `store.progress` checks lease and acknowledges job stage/state/counters before target display update.

`run_one → checksums → manifest durable write → progress VALIDATING/VALIDATION → artifacts.validate → rename .building to immutable final → heartbeat-loss check → progress PUBLISHING/PUBLISH → intelligence_barrier → lease/Admin/source-fingerprint recheck → fenced target pointer → ACKNOWLEDGEMENT_LOSS hook → audit → SUCCEEDED acknowledgement → clear target active job/fence`. Known failed/unpublished errors yield FAILED; publication uncertainty, fencing/crash/heartbeat-loss yield RECOVERY_REQUIRED. Unknown crash may leave RUNNING/VALIDATING/PUBLISHING durable state until existing status/reconciliation/explicit recovery handles it. Telemetry does not rewrite these states.

`close → stop.set + cache.clear`; no native join. Loop is serial with two-second idle waits and swallowed outer errors; no scheduler or automatic recovery. `backend.routes.library_intelligence` retains JWT/member authorization and explicit Admin build/recovery controls. Native status may record source staleness; it is not used by the read-only telemetry writer/CLI.

## Prototype path

Only `scripts/institution_v2k_native_child.py` enables `scratch/institution_v2k_telemetry/adapter.py`, after fixture prefix/explicit child guards. The adapter wraps claim AFTER native acknowledgement and run_one completion, queues canonical internal claim context, and starts a separate Agent thread. No callback performs network I/O. Agent uses its own restricted Actor Mongo connection. Actor reads native claim-bound durable state and writes only a preallocated auxiliary singleton. No production module imports this prototype.

The new fixture-only diagnostic supplement imports unchanged Part 2J authentication. It reads exactly one named auxiliary collection and reuses bounded native job/target reads. Original J CLI/allowlist remain unchanged. No HTTP endpoint, Staff card, frontend polling, process health animation or supervisor implementation is added.
