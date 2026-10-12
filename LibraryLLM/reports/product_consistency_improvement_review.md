# Product consistency improvement review

Delivered: centered Header, consistent Staff geometry and controls, clear audit purpose, compact workspace assistant, durable fresh defaults and strict empty-legacy promotion, automatic Add/Import invalidation, existing bulk inventory read projection, and persistent 150-book TEST QA collection. Measured five sequential development reads per catalogue route; timings are in library_catalogue_performance.json. Larger collections and concurrent lock contention still need dedicated measurement before adding materialized aggregates.

Next improvements within a separately approved scope: revision-bound bounded read models only if measurements justify them; registration recovery visibility for operators; audited acquisition-date editing; broader real-device/contrast/screen-reader QA; dynamic bundle splitting for the existing main-bundle size warning. Canonical single-writer commands and fresh role checks must remain intact.

Future intelligence is REVIEW ONLY. Proposed UI states: NOT_BUILT / READY / BUILDING / FAILED / STALE. Build/Rebuild controls, if later approved, enqueue durable jobs only. Required path: ADMIN click → durable job → background worker → immutable local catalogue generation snapshot → isolated build → validate → SHA-256 checksum → atomic publish → service reload → READY. No synchronous Python builder in an HTTP handler.

## Future tenant catalogue generations — REVIEW ONLY

Create immutable per-library dataset generations from canonical active metadata and holdings, with generation ID, sorted stable library_book_id mapping, catalogue revision/watermark, schema/pipeline version, row count, snapshot digest and snapshot time. Include only fields allowed by that library's privacy policy. A public OpenLibrary work ID is optional metadata, never the tenant identity. Snapshot membership or patron borrowing history is not input to a metadata search/graph build. Record later mutations as staleness against the generation watermark rather than modifying ready artifacts in place.

## Durable jobs and authority

A future Admin click must only validate fresh LibraryMembership, write an idempotent durable job and return its ID. It must not synchronously run a Python builder inside an HTTP request. Proposed path: click → durable job → background worker → immutable catalogue snapshot → isolated artifact build → validation → atomic publication → READY. Jobs carry library ID, requested generation, build kind, pipeline/model fingerprint, actor, idempotency key, state, lease/heartbeat, attempts, cancellation flag, stage progress, error code and artifact manifest. Use bounded QUEUED/RUNNING/VALIDATING/PUBLISHING/READY/FAILED/CANCELLED states and an append-only audit trail.

Default authority: active library ADMIN may enqueue/cancel/retry. LIBRARIAN can inspect readiness/staleness; build authority requires a separately reviewed explicit policy, not legacy User.role. PlatformRoleAssignment permits global oversight of resource/job health and separately audited operational intervention; it does not grant access to private catalogue contents or tenant operations. Revocation is checked at enqueue and publication. A worker's service identity is restricted to its leased tenant job, with no tenant authority inferred from a platform role.

## Worker, concurrency and recovery

Run dedicated background processes outside core/search HTTP workers. Permit one build/publication per library and impose global concurrency plus per-library quotas. Budget CPU threads, RAM, GPU time, disk bytes, maximum records, queue length, duration and retained generations. Lease fencing prevents an expired worker from publishing after takeover. Progress reports durable phase/count totals, not guessed percentage. Cancellation is checked at chunk boundaries and before publication; it keeps the last ready generation. Retry uses bounded backoff and stable snapshot identity. A crash leaves a recoverable staged manifest; expired leases are reclaimed, completed validated artifacts can be reused, and partial files are quarantined/removed under the job's own path. No runaway background loop or request-time builder.

## Future tenant HNSW — REVIEW ONLY

Use a per-library artifact root and stable scoped book UUID labels. Model/tokenizer/preprocessing fingerprints, dimensions, normalization and snapshot checksums belong in the manifest. Encode bounded batches with privacy-safe local model execution, then build an isolated HNSW artifact; never insert tenant records into global 5M HNSW. Build means first validated generation; Rebuild means a new complete generation, retaining the current ready one until publish. Validate vector count, finite vectors, label uniqueness/mapping cardinality, tenant isolation, sample retrieval and file SHA-256 digests. Use fsync plus an atomic generation pointer update guarded by lease fencing and generation compare-and-set.

Search loaders use library_id + source + generation, validate manifests/checksums, and keep a ready snapshot reference for each request. Swap loaded generations atomically; drain old references before releasing memory. Loading failure keeps the previous ready snapshot or the ordinary tenant-local search. A populated library without a tenant index continues its canonical local lexical catalogue; it must never present global books as owned. Global discovery remains explicitly separate, and zero-local-record libraries continue the existing global fallback. This review does not implement tenant routing/private vectors.

## Future tenant Knowledge Graph — REVIEW ONLY

Build deterministic metadata edges from the same immutable catalogue snapshot: scoped book UUID to normalized author/subject/publisher concepts with explicit provenance. Namespace nodes by library; optional public global_work_id links do not join private graphs across tenants. Record schema, normalization version, snapshot fingerprint, node/edge counts, ID mapping, build resource use and artifact checksums. Validate that every book node belongs to that generation/library, edge endpoints exist, duplicate/self edges meet policy, and no private metadata enters the global KG. Missing ISBN/work IDs remain valid local graph nodes.

A separate KG worker job uses the same durable queue, cancellation, retry, lease fencing and publication protocol. Publish a validated immutable graph plus manifest by atomic generation pointer; graph loaders select only the current authorized library generation. Keep the last ready graph while rebuilding; a missing graph yields an honest no-graph/local discovery state, with separately labelled global discovery where permitted. There is no synchronous graph builder, ordinary staff technical dashboard, or Build/Rebuild UI in this delivery.



READY means the service loaded and validated the published generation, not merely that a process exited. STALE compares current catalogue revision with the snapshot watermark. Build/Rebuild always retains the last ready generation until validated publication/reload succeeds. Artifact directories are tenant-scoped, e.g. tenant_artifacts/{library_id}/{kind}/{generation}; workers validate resolved paths and never mutate global HNSW/KG roots.

The existing Search/KG global services are preserved. A populated library without a tenant artifact continues canonical local lexical discovery with an explicit optional global discovery link; an actually empty library uses the accepted global fallback. Missing/building/failed artifacts never imply global ownership. Platform oversight is resource/job health only unless separate LibraryMembership authorizes private contents. Active ADMIN is the proposed default enqueue/cancel/retry authority; LIBRARIAN builds require an explicitly reviewed policy.

This phase deployed local review processes and intentionally seeded TEST; earlier prior-phase statements about zero production-count changes do not describe this phase. Current preservation covers sampled global-document hashes, protected code and 196 artifact size/mtime records, not full global/index hashes. No future intelligence implementation or Build/Rebuild UI was added.
