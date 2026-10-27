# 18_SEMANTIC_SEARCH_PIPELINE.md: End-to-End Semantic Search Pipeline Trace

## Executive Summary

This document traces the complete execution flow of a dense semantic search request in LuminaR, from raw query input to final ranked JSON delivery. Every mathematical operation, batch size, search depth, filtering logic, and fallback rule is referenced to concrete source lines in `LibraryLLM/search/luminar_search.py:415-810`.

---

## 1. Step-by-Step Pipeline Trace

```mermaid
sequenceDiagram
    autonumber
    participant Client as Client HTTP Request
    participant Search as LuminaRSearchEngine
    participant Cache as SQLite Vector Cache
    participant MiniLM as all-MiniLM-L6-v2 Embedder
    participant HNSW as FAISS Index Snapshot
    participant Mongo as MongoDB (books & inventory)
    participant CrossEnc as ms-marco-MiniLM Reranker

    Client->>Search: search(query="machine learning", top_k=10, library_id="LIB1", available_at_library=True)
    
    rect rgb(240, 248, 255)
    Note over Search, MiniLM: Phase 1: Query Embedding
    Search->>Cache: SELECT vector FROM embedding_cache WHERE hash = sha256(query)
    alt Cache Miss
        Search->>MiniLM: embedding_model.encode([query]) (batch_size=1)
        MiniLM-->>Search: Raw FP32 384-D vector
        Search->>Cache: INSERT INTO embedding_cache (hash, vector)
    else Cache Hit
        Cache-->>Search: Deserialized FP32 384-D vector
    end
    Search->>Search: faiss.normalize_L2(query_vector) (Unit Euclidean norm)
    end

    rect rgb(255, 250, 240)
    Note over Search, HNSW: Phase 2: Approximate Nearest Neighbor (ANN) Retrieval
    Search->>HNSW: snapshot.candidates(query_vector, fetch_k=50..100)
    HNSW->>HNSW: Traverse base HNSW (5M vectors) + delta HNSW
    HNSW->>HNSW: Map vector indices -> work_id via index_work_ids.npy
    HNSW-->>Search: List of {work_id, hnsw_score}
    end

    rect rgb(240, 255, 240)
    Note over Search, Mongo: Phase 3: Metadata Validation & Dynamic Expansion
    Search->>Mongo: current_books(books_collection, [work_ids])
    Mongo-->>Search: Hydrated title, authors, subjects metadata
    Search->>Search: Discard deleted books; dynamically expand fetch_k if valid < 50
    end

    rect rgb(255, 245, 245)
    Note over Search, CrossEnc: Phase 4: Cross-Encoder Reranking
    Search->>Search: Assemble pairs: [query, "Title: ... Authors: ... Subjects: ..."]
    Search->>CrossEnc: reranker.predict(pairs, batch_size=16)
    CrossEnc-->>Search: Unbounded scalar relevance logits
    Search->>Search: Sort by: rerank_score desc, hnsw_score desc
    end

    rect rgb(245, 240, 255)
    Note over Search, Mongo: Phase 5: Author Match & Inventory Filtering
    Search->>Search: Check _author_match_ids(); elevate exact author matches
    Search->>Mongo: _get_library_inventory(top 50 work_ids, library_id)
    Mongo-->>Search: total_copies, available_copies
    Search->>Search: Filter: r["library_available"] and r["available_physical_copies"] > 0
    Search->>Search: Slice results[:10]; assign ranks 1..10
    end

    Search-->>Client: 200 OK (Results JSON + Execution Timing Profiling)
```

---

## 2. Mathematical Parameters & Operational Constants

### 2.1 Metric Space & Score Formulation
* **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2` ($d = 384$).
* **Vector Normalization:** Explicit Euclidean unit normalization:
  $$\hat{\mathbf{q}} = \frac{\mathbf{q}}{\|\mathbf{q}\|_2}, \quad \hat{\mathbf{d}}_i = \frac{\mathbf{d}_i}{\|\mathbf{d}_i\|_2}$$
* **HNSW Distance Metric:** Inner Product (`faiss.METRIC_INNER_PRODUCT`). Because vectors are L2-normalized, inner product equals Cosine Similarity:
  $$\text{Score}_{\text{HNSW}}(\mathbf{q}, \mathbf{d}_i) = \langle \hat{\mathbf{q}}, \hat{\mathbf{d}}_i \rangle = \cos(\theta) \in [-1.0, 1.0]$$
* **Cross-Encoder Metric:** Real unbounded scalar logit $s_{\text{CE}} \in (-\infty, \infty)$ output by the classification head of `cross-encoder/ms-marco-MiniLM-L-6-v2`. Higher values denote higher relevance.

---

### 2.2 Depth, Thresholds & Overfetching Policies

| Parameter | Configuration Value | Source File & Line | Rationale & Impact |
| :--- | :--- | :--- | :--- |
| **Final User Return ($K$)** | `10` (default, up to `50`) | `search/api.py:92` | Bounded slice returned to frontend client |
| **Minimum Candidate Target** | `50` | `search/luminar_search.py:61` | Minimum pool required before reranking |
| **Rerank Depth** | `50` | `search/luminar_search.py:63` | `CROSSENCODER_RERANK_DEPTH = 50` |
| **Overfetch Factor** | `2` | `search/luminar_search.py:449` | `LUMINAR_SEARCH_OVERFETCH_FACTOR = 2` |
| **Max Candidate Ceiling** | `1,000` | `search/luminar_search.py:450` | `LUMINAR_SEARCH_MAX_CANDIDATES = 1000` |
| **Rerank Batch Size** | `16` | `search/luminar_search.py:69` | Forward-pass batch size for cross-encoder |
| **Score Threshold** | **None (No cutoff)** | N/A | Engine relies on relative rank ordering; does not discard low-scoring results |

---

### 2.3 Dynamic Candidate Expansion Loop
To protect against database-index divergence (e.g. books tombstoned or removed from MongoDB after the index was compiled), `search/luminar_search.py:455-468` implements a dynamic while-loop:

```python
while True:
    candidates = snapshot.candidates(query_vector, fetch_k)
    candidate_metadata = current_books(self.books_collection, [c["work_id"] for c in candidates])
    candidates = [c for c in candidates if c["work_id"] in candidate_metadata]
    if (len(candidates) >= target or fetch_k >= limit 
            or fetch_k >= max(snapshot.base.ntotal, snapshot.delta.ntotal)):
        break
    fetch_k = min(limit, fetch_k * factor)
```
If 10 of the initial 50 candidates are missing from MongoDB, the engine doubles `fetch_k` to 100, searches again, and extracts fresh valid candidates until 50 active books are secured.

---

### 2.4 Duplicate & Conflict Handling
* **Deduplication:** FAISS HNSW searches both the immutable 5-million `base` index and the dynamic `delta` index.
* **Tombstone Resolution:**
  ```python
  # LibraryLLM/search/index_manager.py:102-107
  override = self.overrides.get(wid)
  if is_delta:
      if override is None or override["label"] != int(label):
          continue
  elif override is not None:
      continue  # Tombstoned in base index; ignore base vector
  ```
  If a book's metadata changed, its old vector in the base index is masked out by `override`, and only its updated delta vector is retained.

---

### 2.5 Multi-Library Availability Filtering Architecture
* **Critical Finding:** Inventory filtering occurs **after** the top 50 candidates have been retrieved and reranked:
  ```python
  # LibraryLLM/search/luminar_search.py:770-771
  if library_id and available_at_library:
      results = [r for r in results if r["library_available"] and r["available_physical_copies"] > 0]
  results = results[:final_k]
  ```
* **Consequence:** If a participating library holds 2,000 unique specialized books that are not in the top-50 global semantic matches for a general query, those books will **never** appear in the results, because the HNSW retrieval pool is drawn globally before library filtering occurs.
