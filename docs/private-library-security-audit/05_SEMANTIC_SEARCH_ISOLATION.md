# 05 — SEMANTIC SEARCH & VECTOR INDEX ISOLATION

## 1. The Core Multi-Tenant Search Security Problem

In vector search systems, multi-tenancy presents a classic security vulnerability known as **Post-Retrieval Data Contamination & Recall Starvation**:
- **The Naive Approach (Global Index + Post-Filter)**: All tenants' embeddings are stored in a single monolithic vector index (e.g., FAISS / HNSW). A query retrieves the global top-$K$ candidates, and the application filters out candidates whose `library_id` does not match the querying tenant.
- **Vulnerabilities of the Naive Approach**:
  1. **Recall Starvation**: If Tenant B has 50 documents closely matching a query, all top-$K$ candidates retrieved by FAISS will belong to Tenant B. When filtered for Tenant A, the result list becomes empty, even if Tenant A had relevant documents ranked 51st.
  2. **Information Leakage via Timing / Reranking**: If reranking models (e.g., CrossEncoder) receive global candidates before filtering, unauthorized tenant text passes through the model runtime.
  3. **Score Leakage**: Internal similarity scores or result counts can reveal the presence of documents in other tenants.

---

## 2. Code-Verified Architecture: Dedicated Per-Tenant Vector Indexes

LuminaR completely avoids the vulnerabilities of global shared vector search by implementing **Dedicated Per-Library FAISS Indexes**.

### 2.1 Technical Investigation

| Architecture Layer | Implementation in LuminaR | Code Reference | Security Verification |
|---|---|---|---|
| **Index Namespace** | Dedicated directory per library and generation: `local-data/library-intelligence/{library_id}/search/{generation_id}/index.faiss` | [library_intelligence_store.py:L46-50](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_store.py#L46-L50) | **VERIFIED**: Path contains canonical `library_id` UUID; path traversal strictly rejected. |
| **Index Population** | Vector index contains **exclusively** the books belonging to that specific `library_id`. | [library_intelligence_store.py:L66-86](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_store.py#L66-L86), [library_intelligence_artifacts.py:build_search](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py) | **VERIFIED**: `source_records(library_id)` queries MongoDB strictly with `{'library_id': library_id, 'status': 'ACTIVE'}`. |
| **Vector Dimension** | 384-dimensional normalized vectors from `all-MiniLM-L6-v2` | [library_intelligence_store.py:L30-31](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_store.py#L30-L31) | **VERIFIED**: Dimension verified on load (`index.d == 384`, `index.ntotal == len(records)`). |
| **Candidate Retrieval** | Queries **only** the tenant's loaded FAISS index | [search/library_intelligence.py:L101-102](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L101-L102) | **VERIFIED**: Candidate space is $100\%$ scoped to the querying library. |
| **Reranking Scope** | CrossEncoder reranker scores **only** candidates from that library | [search/library_intelligence.py:L103-107](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L103-L107) | **VERIFIED**: Zero foreign document text enters the CrossEncoder input buffer. |
| **Canonical Hydration** | Database verification against MongoDB `institution_library_books` | [search/library_intelligence.py:L109-114](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L109-L114) | **VERIFIED**: Re-checks tenant ownership and active status; withdrawn books are discarded. |
| **Index Cache Isolation** | `ArtifactCache` keyed by `(library_id, generation_id, target)` | [library_intelligence_artifacts.py:ArtifactCache](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py) | **VERIFIED**: Zero cross-tenant cache sharing; LRU eviction with max 2 resident tenants. |

---

## 3. End-to-End Execution Trace: `TenantIntelligence.semantic()`

Code reference: [search/library_intelligence.py:L87-121](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L87-L121):

```python
def semantic(self, library_id, actor, query, *, staff=False, offset=0, limit=20,
             subject='', author='', circulation_status='', sort='title'):
    from backend.services.library_intelligence_service import target_status
    
    # 1. Authorize tenant caller
    with catalogue.read_context(library_id, actor, staff=staff):
        status = target_status(library_id, 'SEARCH_INDEX')
    
    # 2. Check if tenant index is ready; fallback safely if not built/building
    if status['status'] != 'READY':
        page = catalogue.books(library_id, actor, search=query, ...)
        page['source'].update(search_source='LOCAL_FALLBACK', intelligence_status=status['status'])
        return page

    try:
        # 3. Load isolated tenant index from cache or disk
        manifest, records, index = self.cache.load(
            library_id, 'SEARCH_INDEX', status['active_generation_id'], status['manifest_checksum']
        )
        if manifest['model_version'] != self.model_version:
            raise HTTPException(409, 'MODEL_VERSION_CHANGED')

        # 4. Encode search query
        with self.model_lock:
            vector = np.asarray(self.encoder([query]), dtype=np.float32)
            vector /= np.linalg.norm(vector, axis=1, keepdims=True)

            # 5. Search strictly within tenant's FAISS index
            scores, labels = index.search(vector, min(artifacts.PARAMETERS['candidate_count'], len(records)))
            candidates = [(records[int(label)], float(score)) for label, score in zip(labels[0], scores[0])
                          if 0 <= label < len(records)][:artifacts.PARAMETERS['reranking_count']]

            # 6. Rerank only tenant candidates with CrossEncoder
            if self.reranker and candidates:
                ranked = self.reranker([[query, artifacts.embedding_text(r)] for r, _ in candidates])
                candidates = [(r, float(score)) for (r, _), score in zip(candidates, ranked)]
            candidates = sorted(candidates, key=lambda pair: (-pair[1], pair[0]['library_book_id']))

        ids = [r['library_book_id'] for r, _ in candidates]

        # 7. Hydrate from canonical MongoDB state under read context
        with catalogue.read_context(library_id, actor, staff=staff) as (library, membership, canonical):
            # Verify dataset fingerprint hasn't drifted
            if store.fingerprint(store.source_records(library_id)) != manifest['source_fingerprint']:
                raise HTTPException(409, 'SOURCE_CHANGED')
            
            # Scoped aggregate pipeline filters only books belonging to library_id
            pipeline = [
                *catalogue.usable(library_id, subject=subject, author=author, circulation_status=circulation_status, staff=staff),
                {'$match': {'library_book_id': {'$in': ids}}}
            ]
            rows = {r['library_book_id']: r for r in store.collection('library_books').aggregate(pipeline)}
            selected = [rows[i] for i in ids if i in rows]
            
            source = catalogue.source_locked(library_id, library, membership, canonical, staff=staff)
            source.update(search_source='TENANT_SEMANTIC', intelligence_status='READY', search_generation_id=status['active_generation_id'])
            
            return {
                'source': source,
                'results': catalogue.hydrate(library_id, actor, selected[offset:offset+limit], canonical, staff=staff),
                'total': len(selected), 'offset': offset, 'limit': limit, 'has_more': offset+limit < len(selected)
            }
    except (HTTPException, OSError, ValueError):
        # Graceful fallback to scoped lexical search
        page = catalogue.books(library_id, actor, search=query, ...)
        page['source'].update(search_source='LOCAL_FALLBACK', intelligence_status='RECOVERY_REQUIRED')
        return page
```

---

## 4. Key Security Proofs and Safeguards

### 4.1 Zero Candidate Contamination
Because `index` is loaded from `local-data/library-intelligence/{library_id}/search/{generation_id}/index.faiss`:
- The total number of vectors in `index.ntotal` equals exactly `len(records)` for that library.
- It is mathematically impossible for `index.search()` to return a vector index corresponding to another library's book.

### 4.2 Handling Real-Time Catalog Changes (Fingerprint & Stale Protection)
What happens if Library Staff withdraws or deletes a book after the search index was built?
1. The FAISS index is not modified in real-time (to avoid fragmentation and lock contention).
2. However, line 112 performs MongoDB hydration:
   ```python
   pipeline = [*catalogue.usable(library_id, ...), {'$match': {'library_book_id': {'$in': ids}}}]
   ```
   Because `catalogue.usable()` enforces `{'status': 'ACTIVE'}`, the withdrawn book is omitted from `rows`.
3. Furthermore, line 111 checks `store.fingerprint(store.source_records(library_id)) != manifest['source_fingerprint']`. If any bibliographic metadata has mutated since build, the service detects drift, raises `SOURCE_CHANGED`, and falls back to real-time database lexical search (`LOCAL_FALLBACK`).
4. Verified by test: [tests/institution_v2g/test_intelligence.py:L148-151](file:///d:/SDC/LibraryLLM/tests/institution_v2g/test_intelligence.py#L148-L151) (`test_archived_book_never_returned_from_stale_index`).

### 4.3 Multi-Tenant Cache Isolation (`ArtifactCache`)
In `backend/services/library_intelligence_artifacts.py`:
- `self.entries`: A Python dictionary keyed by tuple: `(library_id, target, generation_id)`.
- When Library A queries semantic search, its index is cached under `(lib_A, 'SEARCH_INDEX', gen_1)`.
- When Library B queries semantic search, it looks up `(lib_B, 'SEARCH_INDEX', gen_2)`.
- **Zero Cache Overlap**: Library A's cached index cannot be returned to Library B.
- **Memory Bounding**: The cache maintains a strict cap (`max_entries = 2`), evicting the least-recently-used tenant index when a third tenant issues a search query.

---

## 5. Security Defense Q&A for Project Review

**Reviewer Question**: *Where does vector filtering happen in your system? Before or after vector search?*
> **Answer**: "Neither. We do not use post-filtering over a shared index, nor pre-filtering within a shared index. Instead, LuminaR uses **dedicated per-library vector indexes**. Each library has its own physical FAISS index file containing only its books. Therefore, 100% of the candidate vector space belongs strictly to that library. This completely eliminates recall starvation and prevents foreign data from ever reaching the CrossEncoder reranker."

**Reviewer Question**: *What prevents one library's search results from leaking book titles of another library?*
> **Answer**: "Three independent boundaries: First, the search endpoint requires an authorized library membership. Second, the FAISS index loaded contains only that library's books. Third, every retrieved candidate ID is hydrated through a MongoDB aggregation pipeline strictly matching `library_id` and `status: ACTIVE`. Even if an invalid ID were injected into the vector index, the MongoDB pipeline would reject it."
