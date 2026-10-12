# Private-library HNSW plan

**PROPOSED / FUTURE WORK.** Current code has a global catalogue namespace and versioned base/delta HNSW maintenance. It does not implement an authorized library index registry. This document preserves the distinction between current mechanism and a recommended extension. See [03](03_SEMANTIC_SEARCH.md) for the query trace, [21](21_PRIVATE_LIBRARY_ARCHITECTURE.md) for membership/data policy, and [23](23_PRIVATE_LIBRARY_IMPLEMENTATION_PHASES.md) for staged work. All code paths below are relative to `LibraryLLM/`.

## 1. Current graph and mapping — verified source behavior

| Concern | Evidence / current mechanism | Multi-library implication |
|---|---|---|
| Global engine | search/api.py:59 module engine; luminar_search.py:103 constructor | One chosen namespace per process; no authorized registry |
| FAISS constructor | search/index_manager.py:53 new_index | IndexHNSWFlat, d=384, M=32, inner product; efConstruction=200, efSearch=128 |
| Model | luminar_search.py:55,136; index_manager.py:154 encode | Local MiniLM normalized float32, finite/nonzero validation; query/index fingerprint compatibility matters |
| Snapshot | index_manager.py:82 Snapshot; candidates:92 | Base graph/work_ids and delta graph/delta_ids, overrides/tombstones; dedup by work ID |
| Labels | candidates translates zero-based search labels | Local partition positions, not Mongo IDs or a global numeric sequence |
| Persistence | index_manager.py:293 _persist | Versioned files/checksums/manifest then active pointer; legacy immutable base may be referenced |
| Updates | index_manager.py:386 _batch_sync | Clone delta, embed relevant changed text, append, override old base/delta label; delete uses tombstone |
| Rebuild | index_manager.py:433 _full_rebuild | Stream global Mongo through disk-backed staging/quality selection; build fresh base; extra resource guards |
| Queue / recovery | search/sync_queue.py, including catalogue_mutation | SQLite events/intents, worker retry/backoff, file writer lock, snapshot validation/fallback |
| Root scope | sync_queue.py:120 DB/root guard | Alternate Mongo DB requires explicit root; does not scope by library membership |
| Hydration | search/catalogue.py:49 current_books | Global work_id Mongo query; no library predicate |
| Paging/filter | search/ranked_pages.py + luminar_search.py | Bounded top-50 cache, live hydration, inventory availability; library value is not candidate isolation |
| RAG indexes | rag/embed.py:252 build_book_indexes; rag/retriever.py | Selected-book/global FlatIP and private-document FlatIP; a separate lifecycle from catalogue HNSW |

Historical on-disk metadata references approximately five million base vectors and a 9,040,742,251-byte index, with 5,000,016 mapping entries and 16 tombstoned entries in the inspected active manifest. These are artifact observations, not a freshly loaded/benchmarked production graph. Legacy baseline verification is false in the inspected manifest. Offline build metadata's efSearch=64 is not the current manager's runtime setting 128. Full details/qualifiers are in [03](03_SEMANTIC_SEARCH.md) and [17](17_CLAIMS_LEDGER.md).

There is no hnswlib capacity/resizing parameter here: FAISS is the active library. `add` appends nodes; HNSW graph removal is not used. The application suppresses obsolete IDs through mappings/overrides and reclaims graph storage by rebuild. The existing durability mechanisms are useful, but Mongo writes and graph publication are still not one transaction.

## 2. What does “filtering” mean here?

The active Snapshot calls plain `index.search(vector, k)` on base and delta. FAISS does not read Mongo library metadata or authorize users. Current post-retrieval physical inventory filtering does not change which graph is searched.

Modern FAISS exposes `SearchParametersHNSW` with inherited label-selection support; the installed faiss_cpu 1.14.3 wrapper also contains it. Therefore “FAISS HNSW cannot filter at all” would be inaccurate. An IDSelector must be constructed from a correct authorized label set and passed through supported search parameters. Its behavior/recall/cost is version and search-mode dependent; a current upstream issue reports a selector problem with bounded_queue=False. This proposal does not assume selector support alone proves safe or sufficiently selective multi-library retrieval. Primary references: [FAISS HNSW API](https://faiss.ai/cpp_api/struct/structfaiss_1_1SearchParametersHNSW.html), [implementation](https://github.com/facebookresearch/faiss/blob/main/faiss/IndexHNSW.cpp), [reported selector issue](https://github.com/facebookresearch/faiss/issues/5504).

Separate four concepts in experiments: authorized output suppression, selector-conditioned returned neighbors, graph traversal through shared vectors, and separate physical graph namespaces. They are not interchangeable guarantees. Benchmark selectors against exact authorized subsets with the *installed pinned version*, including empty/very selective scopes and deletion; revalidate scope in hydration regardless of architecture.

## 3. Architecture alternatives

| Option | Mechanism | Benefits | Risks / evidence needed |
|---|---|---|---|
| A: independent HNSW per library | Library owns graph bundle/base+delta/mapping; query selects only its namespace | Clear candidate isolation, independent rebuild/delete, no library post-filter recall loss | Many graph files/load costs; memory if all resident; tiny collections may not benefit from ANN |
| B: shared graph with library labels | Global vectors carry scope mapping; post-filter or validated selector | Fewer graph resources; potential shared operating efficiency | Plain post-filter can miss all relevant private neighbors; finite overfetch cannot guarantee k; selector version/recall tradeoffs; graph/cache/admin blast radius and shared-vector privacy concerns |
| C: scoped registry with mixed index types | Independent library partitions; exact FlatIP for small active sets, HNSW for large ones; lazy LRU graph loading | Preserves explicit scope while limiting small-graph overhead/resident memory | Registry leases/eviction/versioning are additional complexity; thresholds and cold-load behavior need measurement |

**Recommend C, implementing A's isolated namespaces first and adding an exact small-library path when measured.** Do not introduce shared private graph B merely because current graph is global. Keep an explicit global public catalogue namespace as a separately selected feature; never automatically fall back to it from a private request. If B is later investigated, treat it as an empirical alternative with authorization and selector validation, not a drop-in security guarantee.

The foundational [HNSW paper](https://arxiv.org/abs/1603.09320) and [FAISS index overview](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes) establish the algorithm/library background. They do not establish LuminaR's tenant capacity or private recall. No new index algorithm is proposed here.

## 4. Registry contract

```text
acquire(validated LibraryContext, published_generation, model_version)
    → pinned immutable LibraryIndexHandle
handle.search(query_vector, k) → local candidate labels + generation
resolve(handle, partition, label) → scoped record ID/hash
validate/hydrate(scope, published_generation, record IDs)
release(handle)
```

A registry entry records library_id, generation, index type, model/fingerprint/dimension, durable locator, checksums, base/delta mappings, tombstones, loaded bytes, last use, reader reference count and health. Its key includes generation; “library_id alone” can accidentally reuse old vectors after replacement. Model pool is shared across libraries with matching version; graphs/mappings are isolated. Track manifest memory and mapped file residency as well as Python object memory.

Acquire validates live authorization before loading, looks up the authoritative published generation, verifies compatibility and checksums, and pins a read handle. A per-entry load lock prevents duplicate cold loads. Loading is bounded by byte budget and concurrent load limits; evict only unused handles with no writer/reader references. Query captures a snapshot once, then uses its mapping throughout. A new version swaps registry visibility after durable publication; old reader handles finish before reclamation. If the required bundle cannot load, return a scoped unavailable/retry response; do not expose another generation without an explicit coherent rollback record.

The registry must not spawn one permanent busy worker and one separate model per library. Use a durable shared job scheduler with scoped leases/fairness and a bounded model pool. Each process can have a registry cache, but distributed publication/job ownership must be shared; local process locks do not coordinate multiple machines.

## 5. ID and mapping rules

```text
(library_id, generation_id, partition, vector_label)
  → {holding_id/private_record_id, optional public work_id,
     semantic_hash, dataset_id/version, model_fingerprint, active_state}
```

Base label 0 and delta label 0 legitimately coexist; library A label 0 and library B label 0 legitimately coexist. A rebuilt graph can assign a different book to label 0. Generation+partition is therefore essential. No global integer vector sequence is required for FAISS implicit labels. Stable holding/record IDs remain outside FAISS and globally unique. If a future wrapper offers explicit IDs, its add/search/reconstruct/delete behavior must be verified for HNSW; do not assume `IndexHNSWFlat.add_with_ids` is supported just because another FAISS index supports it.

Before publication assert dimension/count compatibility, every active label resolves to one valid scoped record, no foreign library IDs, duplicate policy is intentional, finite normalized vectors, and mappings/hashes match dataset coverage. Tombstoned physical vectors can remain in `ntotal`; live coverage metrics exclude them. Cache keys include scope/generation/hash/model. Cross-library deduplicated embedding computation may be possible for genuinely public identical text, but access metadata and vector ownership mappings must remain separate; private content reuse has privacy/provenance implications.

## 6. Directory and persistence proposal

```text
data/vector_indexes/
  libraries/<validated-opaque-library-id>/
    versions/<generation-id>/
      base.index
      base_ids.npy
      delta.index
      delta_ids.json
      overrides.json
      manifest.json
    staging/<job-id>/...
    queue.sqlite              # optional local prototype; shared durable jobs preferred
    registry_projection.json  # optional local cache of authoritative publication
```

The same namespace pattern applies to scoped lexical/graph sidecars and library book/document chunks, with distinct index kind in manifests. Never concatenate an unvalidated display slug/upload filename into filesystem paths. Resolve absolute targets and verify containment under the scoped root before load/delete. Use safe numeric/string arrays rather than pickle-based external uploads. Files are derived internal artifacts, never trusted merely because a client supplied them.

Manifest fields: format_version, library_id, generation_id, dataset_id/version/checksum, model ID/fingerprint/dimension, normalization/semantic-text/chunking versions, index_type/metric/M/efConstruction/default efSearch, live/physical/tombstone counts, per-file sizes/checksums, created_at, parent_generation, job/fencing_token and source coverage hash. No credentials, query text or private chunks belong in an operational health manifest.

Initial deployment can use a durable local volume compatible with the current Windows host. For multiple workers/hosts, immutable bundles in durable object/shared storage plus an authoritative generation record and verified local caches are a possible extension. Do not assume local `os.replace` semantics imply a distributed atomic commit. Durable bundle first, authoritative DB generation pointer last; use transactional DB metadata/outbox where supported or tested journal recovery. The current active-pointer protocol can become a local projection, not a competing publication authority.

## 7. Lifecycle operations

### Creation and first load

Authorize Library/Dataset owner; stage records; embed batches with compatible model; choose index type from a benchmarked policy; build base/mapping; validate; persist durably; publish generation; load lazily on first query. An empty authorized library returns an empty result, not global matches. Progress is job state, not a silently blocking upload HTTP request.

### Insertion

Commit scoped record plus durable indexing intent; enqueue idempotent `(library, record, semantic_hash, model_version)` job. Append only to that library's delta (or exact partition), update mapping and coverage, publish a coherent generation. Before indexing, record remains PENDING under the defined publication policy. Availability-only changes need live hydration/cache invalidation, not re-embedding.

### Semantic update

Compare canonical text hash. If changed, append the new vector and override its old label; do not mutate a graph already pinned by readers. Coalesce superseded jobs and verify latest hash before publication. Public work edits may affect many libraries: fan out scoped jobs under an explicit shared-metadata policy without copying another library's private description. Inventory-only fields do not trigger embeddings.

### Book/holding deletion

Authorize ownership and loan/history rules. Disable searchable/access status immediately in authoritative data, publish a tombstone/override, invalidate caches, retain necessary historical holding identity. Deleted source cannot remain a citation through a stale cache. HNSW nodes are reclaimed in a scoped rebuild. Deleting an institution disables membership/query/job acquisition first and performs bounded retention-aware namespace cleanup later; shared public works are not institution-owned files to delete.

### Rebuild and compaction

Trigger by a measured delta/tombstone ratio, compatibility changes, detected corruption or authorized repair. Stream only that library's intended dataset, build into a new generation, checkpoint and validate. Reserve enough disk/RAM for old+new generations and readers. Publish after durable completion under a scoped lease/fencing token; stale workers cannot overwrite a newer generation. Retain a previous valid version and reader references. Rebuild one library without rebuilding all others.

### Dataset replacement

Use explicit import mode, immutable version and staged set diff. Preserve holding IDs and active loans; omission retires search visibility only after publication. Do not apply uploaded available_copies blindly over active circulation. Validate records/graph together and switch the authoritative dataset/index tuple. Retry with the same idempotency key should not duplicate holdings/vectors; checksum duplicates can offer reuse only if schema/model/import semantics match.

### Model or representation upgrade

A model/dimension/tokenizer/text-rule change requires a compatible rebuilt generation. MiniLM default is 384 dimensions; a 768-dimensional model cannot search that graph. Dual generations may coexist while new bundles build; queries use their matching encoder. Switch coherently and retire old versions after readers finish. Chunking changes similarly rebuild affected QA indexes and invalidate prepared-document cache compatibility. Never mix vectors from different models or normalize zero/nonfinite output.

## 8. Failure, consistency and recovery

| Failure | Required response / recovery |
|---|---|
| Mongo record exists but vector missing | PENDING/FAILED with scoped intent; retry/checkpoint; no claim of complete coverage |
| Old vector remains after delete | Live DB scope/status check suppresses it; tombstone publication; rebuild reclaims node |
| Embedding batch crashes | Retry hash/model-specific batch, verify finite vectors, no duplicate append publication |
| Process dies before bundle persistence | Staging unreferenced; resume or garbage collect after lease expiry |
| Bundle durable but not published | Validate job/current dataset; publish idempotently or remove unreferenced version after retention |
| Manifest/mapping mismatch | Reject load, mark scoped health failure, restore verified referenced version or explicitly roll back coherent publication |
| Authoritative pointer references missing bundle | Fail closed; recovery restores bundle or atomically changes pointer to validated previous tuple; report incident |
| Stale lease writer finishes later | Fencing token/expected parent generation rejects its publication |
| New query reads old cache | Cache key/version check rejects entry; retry within bound with coherent new generation |
| Membership revoked during request | Revalidate before output/actions under documented revocation policy; discard unauthorized cached sources |
| Disk/RAM exhaustion | Bounded queue/load admission; preserve previous generation, report retryable scoped job failure |
| Library deleted during job | Cancellation/state check before publication; disable output; safe retention cleanup |

Provide a scoped reconciliation utility: enumerate authoritative searchable records/hashes, live mapped IDs, dataset/job generation and checksums; report missing/stale/extra/foreign counts; repair idempotently or rebuild; record actor and outcome. The existing catalogue intent/snapshot tests are precedents, not proof of this new protocol. Cross-store ACID is not claimed.

## 9. Concurrency and serving

Never concurrently mutate a graph queried by readers without an explicit supported synchronization policy. Prefer immutable read snapshots; serialize each library's writer with a durable lease; use copy/build-new for publication. Separate graph access locks from embedding model locks. Existing IndexManager model_lock and file writer lock can inform a local prototype; distributed jobs require leases/fencing beyond the filesystem lock.

Shared encoder/GPU batches should be bounded and scheduled fairly; otherwise one large import starves interactive query/QA. Search, cross-encoder and Qwen resources have different costs; instrument queue time separately. Multiple service processes may duplicate large graphs and model weights. Registry eviction must account for pinned readers and memory during rebuild/clone. A shared graph object is not presumed thread-safe for arbitrary simultaneous mutation/search; document pinned FAISS/BLAS thread settings and evaluate actual host behavior.

## 10. Capacity and experiment matrix

Vector payload lower bound is `4*d*N = 1,536*N` bytes at d=384, approximately 7.68 GB for five million vectors before graph/mappings/process/model overhead. This is a lower bound, not RAM sizing or the actual file size. HNSW neighbor and metadata overhead, obsolete nodes, two generations, cold loads and OS file cache are additional. Per-library top-k cost does not imply total system throughput.

| Workload | Principal concern | Measurements |
|---|---|---|
| 10 libraries, all large/active | Resident graph/model memory and rebuild overlap | RSS/peak RAM, disk, p95/p99, concurrent query/rebuild |
| 100 libraries, mixed size | Index-type policy and skew | exact/HNSW quality/cost, cold load, eviction hit rate |
| 1,000 libraries, small mostly cold | Bundle/registry overhead, repeated loads | metadata bytes, open files, cold p95, job fairness |
| 10,000 libraries, sparse activity | Storage namespace operations and burst admission | working-set budget, load storm latency, queue depth, recovery |

These are proposed scenarios, not verified supported capacities. Compare A/B/C with identical compatible vectors, candidate/rerank settings and authorized ground truth. For B vary library selectivity, duplicates, overfetch and supported selector modes; report authorized Recall@k and nDCG, leak count at every stage, graph load/search/rerank/e2e latency and memory. For A/C vary M/efSearch, exact threshold, cache budget, small/large/skewed sets, update/delete rates and generation publication delay. Include p50/p95/p99, cold/warm separation, repeats/seeds, hardware/version manifests and confidence intervals.

Isolation suites need equal titles/ISBNs in two libraries plus unique canaries; wrong-ID direct fetch; private chunk citations; stale chat/actions; switching races; membership revocation; mapping corruption; empty scopes; missing index; wrong model; failed replacement; concurrent delete/rebuild; restart and stale writer. “No observed leaks” is reported with suite size and attack cases, not as universal mathematical proof. See [12](12_EXPERIMENT_PLAN.md) E8/E9 and [23](23_PRIVATE_LIBRARY_IMPLEMENTATION_PHASES.md).

## 11. Research boundary

Library IDs, ACLs, upload jobs and mapping correctness are necessary engineering. A publication contribution could be a measured quality/cost/isolation comparison of scoped ANN policies, recovery under controlled mutation, or resource-bound QA evidence benefits. Separate such evidence from the ordinary use of MiniLM/FAISS/HNSW. The current application provides a useful starting mechanism; no results for A/B/C or the future registry are available from this audit.
