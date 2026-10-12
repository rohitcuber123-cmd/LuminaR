# Recommended next scope after Part 2F

Recommendation: after Part 2F closure and explicit user approval, scope **Tenant Catalogue Intelligence Infrastructure**. This is a proposal derived from the current repository, not an implementation or claim that tenant catalogue HNSW/KG already exists. No build, rebuild, migration, tenant index directory or catalogue intelligence control was created by preparing this report.

## Repository boundary

Canonical library books, holdings and copies already live behind a tenant-required repository. `backend/services/library_catalogue_repository.py` requires a canonical library UUID on every operation and rejects an attempt to change it. Book records have their own library_book_id and may optionally reference a global work. `library_catalogue_experience.py` currently reads ACTIVE library records with the existing inventory metadata search semantics and explicitly performs no global index routing or dataset build. It hydrates current holdings and tenant lending capabilities through accepted guards.

The accepted global Search service has existing HNSW/lexical generations, manifests, validation, a durable synchronization queue, publication/reload and STALE handling in `search/index_manager.py`, `search/sync_queue.py`, `search/lexical_store.py` and related modules. Its optional library availability filter is not a canonical local-book tenant intelligence generation. Global IDs and artifacts must remain global. `knowledge_graph/core.py` implements the accepted metadata SQLite graph keyed by global work ID; `backend/routes/knowledge_graph.py` refreshes global facts and provenance for product related-book output. Those are useful design references rather than a grant to write tenant data into their current files.

Part 2F's document artifacts are a separate per-asset PDF/RAG concern. Their FAISS runtime index, extraction, private text and Knowledge Tools caches must not become catalogue HNSW or graph input merely because a PDF is linked to a library book.

## Proposed exact first scope

| Deliverable | Proposed boundary and evidence |
| --- | --- |
| Canonical dataset generations | Snapshot only eligible ACTIVE canonical books for one library UUID. Use library_book_id as tenant row identity, retaining global_work_id only as optional reference. Include local-only books, deterministic metadata normalization, source revision/checkpoint, row count and SHA-256 manifest. Snapshot identity must not depend on title or legacy library aliases. |
| Tenant artifact registry | Explicit library UUID + immutable generation UUID + artifact kind. Isolate tenant directories from global HNSW/KG, document assets and personal data. Store source/algorithm/model versions and checksums; reject path escapes and incompatible identities. |
| Durable build jobs | Bounded jobs with current library staff authority, lifecycle checks, states, attempts, safe errors, restart recovery and lease/generation fencing. Define standalone-Mongo unknown-commit behaviour consistently with existing durable institution locks. Platform authority alone cannot request a tenant build. |
| Catalogue HNSW build | Build an index and exact row-ID mapping from that tenant snapshot, using accepted embedding configuration. Validate dimension, finite vectors, row identity/count, checksums and retrieval isolation before publication. Do not append tenant rows to the global 5M index. |
| Catalogue Knowledge Graph build | Build metadata-only tenant graph artifacts with canonical tenant book IDs, accepted relation semantics and source provenance. No private PDFs, personal documents, private loans/fees or membership records become graph features. |
| Atomic publication | Publish one validated generation pointer only after the complete required artifact set succeeds. A failed/interrupted/stale worker cannot replace a newer generation. Keep a recoverable previous validated generation under an explicit retention policy. |
| STALE detection | Capture relevant book metadata create/update/withdraw/link/import revisions; compare current source revision with the published manifest. Define which fields require rebuild and which live fields, such as availability, are hydrated from canonical services. Do not mark a stale artifact current after a source mutation during build. |
| Explicit Search/KG routing | Resolve GLOBAL versus a canonical requested library from explicit route/request context. Authorize the tenant before reading its artifacts and hydrate/recheck canonical current book state before returning results. No first-membership guess, silent global fallback for a private scope, or cross-library candidate sharing. |
| Safe fallback | Keep authorized canonical metadata Browse/search usable while a tenant artifact is absent, stale or unavailable. Expose a clear bounded status. Decide whether any previous validated generation can be read and with what current-record filtering; never return another library's or global corpus as if it were the requested tenant. |
| Operator and product status | Supply truthful generation/job readiness, error and last-source revision information after APIs are stable. Staff actions use separate explicit LibraryMembership. Add Build/Rebuild controls only in an approved phase; none are included in Part 2F. |
| Isolation and recovery acceptance | Use disposable A/B libraries containing local-only records and the same globally linked work. Prove IDs, directories, candidates, graph paths and cache keys remain separate, along with membership/lifecycle denial, failed build recovery and stale-worker rejection. Preserve TEST 150 records/holdings and global artifacts. |

## Order and limits

Begin with a focused audit of mutation checkpoints, actual global index/graph publication mechanisms, canonical tenant identity and expected scale. Make the artifact/job schema, source mutation coverage, authorization and fallback behaviour reviewable before building. Then implement and test isolated generation creation, validation and publication; integrate explicit tenant Search/KG routing only after those boundaries pass. Measure build memory/time and query latency against representative isolated tenants without changing the accepted global ranking formula or Assistant router.

This proposed first scope excludes cross-document library RAG/semantic document search, public document publishing, personal-to-library sharing, Events/Notifications/Analytics redesign, new recommendation ranking, Qwen/router research, and unrelated domain phases. Library document RAG, existing Book RAG and personal RAG remain distinct from catalogue intelligence.

Approval must identify the intended build authority, expected library scale, artifact retention and stale fallback policy. This report requests no immediate grant or build action; the current work stops at Institution Part 2F.
