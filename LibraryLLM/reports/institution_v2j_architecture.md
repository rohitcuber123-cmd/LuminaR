# Part 2J diagnostic architecture

Project root: `D:\SDC\LibraryLLM`. Existing 2G–2I source is unchanged, including the uncommitted 2I `_target_observation` optimization. No route or Staff page is added.

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
