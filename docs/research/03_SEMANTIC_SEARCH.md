# Semantic search, lexical retrieval, and catalogue HNSW

## Active query trace

`frontend/src/pages/SearchPage.tsx:232–331` obtains `q`, offset, library and availability from `lib/searchPaging.ts`; it invokes `lib/api.ts:507–530 searchBooks`. Vite strips `/search-api` and forwards POST `/search` to 8003. `search/api.py:195–323 search` validates bearer identity, nonempty query, 1–50 limit and offset bounds, and requires an ID for the optional availability filter. It calls `RankedSearchPages.search`, logs first-page history when enabled, and returns ranked results. The UI renders book cards, scores/metadata, and next/previous controls.

```text
SearchPage query + URL paging/filter values
→ POST /search (authenticated)
→ RankedSearchPages: generation-aware 50-result cache
→ LuminaRSearchEngine.search: strip query
→ IndexManager.encode([query]): local normalized MiniLM vector
→ capture one immutable Snapshot
→ base HNSW + delta HNSW search / merge / suppress overridden labels
→ current Mongo books validation; bounded overfetch
→ optional lexical title/author candidate merge
→ query/book CrossEncoder pairs
→ rerank, optional lexical tiers, author priority
→ live book/inventory hydration and revalidation
→ optional physical-availability filtering
→ slice 10-result display page from bounded ranked pool
→ SearchPage renders results
```

## Model, text, metric, ranking

`search/luminar_search.py:55–69,136–142,184–188` selects local cached `all-MiniLM-L6-v2`, 256-token max sequence, CPU or CUDA, and `cross-encoder/ms-marco-MiniLM-L-6-v2`. Embeddings are **384 float32 dimensions**. `IndexManager.encode:154–164` batches 64 texts, normalizes, validates finite/nonzero output, and applies L2 normalization. For unit vectors inner product equals cosine similarity. No embedding API is used in this path.

`search/catalogue.py:21–32 semantic_text` constructs labeled title, authors, subjects, description, first-publication text; lists use semicolon joining. The offline corpus builder uses equivalent labels. Normalization/hashing centralizes mutation detection. Ratings, stock and shelf changes do not themselves require semantic re-embedding. The sequence limit may truncate later fields; measure field coverage rather than claiming the full description is represented.

`luminar_search.py:448–469` searches both graph parts. Default overfetch factor is 2, maximum candidate budget 1000, target at least 50. Missing/inactive books are removed through Mongo `current_books`. The code increases ANN depth when too few current books survive; this is not tenant-conditioned retrieval. Dense candidates are cut to the target before optional lexical extras. Rerank pairs contain **title, authors, subjects**, excluding description/publication text (`507–514`). Scores are raw cross-encoder outputs and cosine ANN values, not relevance probabilities. Dense ranking uses descending cross-encoder score, ANN score, and stable work ID; author matching can prioritize exact whole structured authors.

`RankedSearchPages` caches 50 ranked IDs/scores for 180 seconds (128 entries by `RankedResultCache` defaults), keyed by query, library/filter and index/lexical generation. It rehydrates current facts per request and retries generation changes at most twice. Display depth is bounded to 50; it is not unbounded catalogue paging.

## Is it truly semantic?

Yes, **VERIFIED IMPLEMENTED** at source level: both book and query text enter compatible MiniLM space, `Snapshot.candidates` calls `index.search`, returned labels map to work IDs, and those matches form the reranker pool. Vectors are used, not merely stored. True relevance improvement for synonym/conceptual queries is **NOT YET MEASURED with independent current gold labels**.

Lexical/fuzzy integration exists behind `LEXICAL_SEARCH_ENABLED=false` by default. `LexicalSearchStore.exact/fuzzy`, `typo_assistance.best_bounded_match` (threshold 0.86, margin 0.05), and `merge_lexical_candidates` add bounded exact/fuzzy title/author evidence after live validation. Exact title gets tier 2; exact author tier 1; fuzzy title/author add 0.02/0.01 to score. `LUMINAR_LEXICAL_SYNC_ENABLED=false` separately gates mutation consumption. This is an implemented optional hybrid, **not BM25+dense reciprocal-rank fusion**. BM25 and RRF are proposed experiments; reranking already exists.

## HNSW creation, identity and lifecycle

`search/index_manager.py:53–57 new_index` creates `faiss.IndexHNSWFlat(384,32,METRIC_INNER_PRODUCT)`, `efConstruction=200`, runtime `efSearch=128`. No fixed `max_elements` capacity is configured; FAISS graphs grow on add. Historical offline builder default search breadth is 64; runtime resets it to 128. Do not confuse the builder manifest with serving configuration.

The global manager holds immutable base graph/mapping and an append-only delta graph/mapping. Labels are **zero-based row positions**, not Mongo ObjectIds and not an explicit global vector-ID counter. `Snapshot.candidates:92–110` maps labels through `work_ids` or `delta_ids`, ignores base IDs present in overrides, retains only the latest matching delta label, and merges best cosine values by `work_id`.

`_batch_sync` clones the smaller delta, loads current Mongo records, hashes searchable text, reuses compatible cached vectors, appends additions, and updates overrides. Deleted/missing/inactive works receive `label=None` tombstones. FAISS HNSW does not directly replace/delete graph nodes; this layer provides logical replacement/deletion. Old vectors consume memory until a full rebuild.

`book_service.create_book/update_book/delete_book` journal catalogue mutations after successful writes. `search/sync_queue.py:catalogue_mutation`, `MutationJournal`, `SyncQueue` and file locks support replay and one-writer coordination. Search startup starts worker polling; `IndexManager.process_once` drains events, retains pending events committed during a build, retries failed work, and reports STALE/SYNCING/REBUILDING/HEALTHY. This is eventual consistency across Mongo/files, not a cross-store ACID transaction.

`_persist` writes version directories with delta/index mappings and manifests, fsyncs, validates checksums and dimensions/counts, then atomically replaces `active_index.json`. Startup can recover a previous validated version and mark stale; search refuses unrecoverable startup unless an explicit recovery worker is chosen. `search.maintenance rebuild` queues a full rebuild. `_full_rebuild` stages current Mongo into SQLite, keeps the quality-ranked top 5M policy plus explicitly managed works, batches embeddings and builds a new base. It guards extra graph memory/disk and retains the old serving snapshot until publication. No measured production recovery-time guarantee exists.

Current artifact `datasets/ai/faiss/hnsw/active_index.json` points to `48febcfde9924d818fdfe2d3c759fae9`; its manifest reports 5,000,000 active vectors, 5,000,016 mappings, 16 deleted vectors, legacy base, about 9.04 GB persisted files, and `baseline_verified=false`. These are **manifest observations**, not a new binary integrity validation or live Mongo count. The offline manifest records 2058.11 seconds build time; its hardware/protocol is insufficient for an efficiency claim.

## Inventory filtering limitations

`library_id` is applied to `library_inventory` after global ANN/ranking; it is not an index partition or book ownership field. `RankedSearchPages.search:54–65` uses inventory presence for the selected library but available counts from the global book record. `luminar_search.py:758–771` also overwrites physical counts with book counts. Borrowing instead uses `availability_service.get_availability_context`, preferring the selected/default library inventory. Therefore search availability can disagree with circulation. This is a source-supported defect candidate; reproduce it with deliberately different book/inventory counts before fixing.

Even correct postfiltering cannot guarantee full library recall: relevant holdings outside the global 50-result pool cannot appear. If a shared ANN top-N has library fraction p, surviving results are roughly Np under an unrealistic uniform model; semantic clustering can make survival much worse. The current overfetch addresses missing Mongo records, not iterative library-conditioned completeness.

## Paper-ready explanation and experiments

HNSW organizes vectors into a hierarchy of proximity graphs. Upper layers guide navigation; lower-layer exploration produces approximate neighbors. M controls graph connectivity, construction breadth affects build quality/cost, and search breadth controls latency/recall tradeoffs. LuminaR uses the existing FAISS implementation; it does not introduce a new HNSW algorithm. See [original HNSW paper](https://arxiv.org/abs/1603.09320) and [FAISS index documentation](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes).

Compare identical normalized vectors with `IndexFlatIP` exact search and HNSW over controlled corpus sizes. Measure ANN Recall@5/@10 against exact neighbors separately from human relevance Recall@k; report build time, RSS, disk bytes, p50/p95, efSearch, M, concurrency and cache state. Existing benchmark helpers in `data_pipeline/ai/faiss/` and `search/evaluate_retrieval.py` enable work but are not sufficient evidence by themselves. Detailed protocol: [12](12_EXPERIMENT_PLAN.md).

## Proposed private-library trace

```text
Authorized user chooses library L
→ LibraryContext dependency verifies membership/resource permissions
→ query encoding with manifest-compatible E
→ registry resolves published H_L and generation
→ ANN only within L (or FlatIP for a small L)
→ map (L,generation,partition,label) to holding/work
→ Mongo hydration constrained to L and live version
→ scoped lexical candidates + reranking + availability
→ scoped cache/paging response
```

Required changes include catalogue holding identity, library-conditioned `current_books`, scoped mutation events/cache keys, library registry, resource ownership, frontend context, and failing closed when an authorized library index is unavailable. See [22](22_PRIVATE_LIBRARY_HNSW_PLAN.md). This pipeline is **PROPOSED**.
