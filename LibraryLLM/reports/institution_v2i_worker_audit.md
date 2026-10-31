# Resident worker audit

`search/library_intelligence_api.install` uses the existing resident embedding model and reranker. Startup registers `TenantIntelligence.start` only when both exist; degraded lexical-only service still serves local fallback but does not claim semantic builds. `start` initializes durable indexes and starts one daemon. `loop` calls run_one serially, immediately proceeds after work or waits two seconds when idle; outer exceptions are swallowed. `close` sets stop and clears cache but does not implement durable job cancellation or join an in-flight builder.

`store.claim` selects earliest created_at QUEUED/effective_active across tenants, enters that tenant's durable barrier and conditionally changes only the still-queued job. It creates a fresh worker fence and 90-second lease, increments attempt, sets RUNNING/DATASET/start/heartbeat, and puts the fence on the matching target. A renewal thread extends a valid lease every ten seconds. check_lease/progress/publication require unexpired job/fence/effective-active state; fenced writers cannot overwrite successor outcomes.

Dataset construction rechecks requester's current tenant ADMIN authority and canonical metadata under the tagged barrier; reuses a checksum-verified READY dataset only if its complete fingerprint/snapshot agrees. Builds run outside the catalogue barrier. Search uses tenant SQLite embedding cache, batches of 32, normalized 384-dimensional vectors and a model lock; KG builds deterministic metadata nodes/edges. Worker validation runs before rename/publication. Publication reacquires the barrier, checks lease, ADMIN and fingerprint, then atomically updates the fenced pointer and records deterministic audit/success. Acknowledgement uncertainty leaves RECOVERY_REQUIRED and the pointer intact.

Bounds: 50,000 records, 64 MiB dataset, 256 MiB per validated artifact file, 3 runtime cache entries/256 MiB estimated retention. These are format/cache limits, not a worker RAM/disk admission policy. There is no free-disk preflight, RAM reservation, GPU budget, build deadline, cancellation check in long native operations, per-tenant job quota or fleet scheduler. model_lock serializes this tenant service's encode/rerank calls; it does not prove freedom from contention with the global engine's other request paths.

Worker restarts do not reclaim running jobs automatically. Expired nonqueued jobs derive recovery and remain effective-active; explicit reconciliation/recovery owns them. A crash while holding the tagged tenant metadata barrier can block library reads until existing explicit fenced recovery. Untagged domain locks are never cleared by intelligence recovery. Known prepublication failures retain private artifacts and last-good pointer; uncertain failures retain active ownership. No concurrency/resource/state semantics were changed by 2I.

## Executed bounded workloads

| Target | Books | First build ms | Unchanged rebuild ms | New generation bytes |
|---|---:|---:|---:|---:|
| SEARCH_INDEX | 10 | 3972.797 | 200.295 | 40,253 |
| SEARCH_INDEX | 100 | 3108.232 | 293.255 | 390,649 |
| SEARCH_INDEX | 1000 | 29790.802 | 1537.511 | 3,895,107 |
| KNOWLEDGE_GRAPH | 10 | 129.993 | 141.036 | 16,388 |
| KNOWLEDGE_GRAPH | 100 | 111.036 | 103.554 | 153,281 |
| KNOWLEDGE_GRAPH | 1000 | 419.258 | 405.468 | 1,523,984 |

Actual cached MiniLM CPU and actual validated FAISS/KG artifacts, offline/no downloads. Two torch/FAISS threads for fixture measurements only. One sample per configuration; first 10-book run includes lazy inference warmup. Unchanged Search rebuilds encode zero books. Embedding, construction, validation, pointer publication, source extraction, sampled process RSS and disk/cache/retained sizes are all in `institution_v2i_workload_benchmark.json`; no GPU budget was qualified. Existing VectorCache SQLite handles can survive transaction contexts until GC; the initial harness cleanup encountered Windows file locking. The verified harness performs GC at fixture teardown; production cache lifecycle was not changed.
