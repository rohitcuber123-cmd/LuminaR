# 20_MULTI_LIBRARY_VECTOR_STRATEGY.md: Multi-Library Vector Retrieval Strategy & Post-Filtering Analysis

## Executive Summary

This document analyzes how multi-library tenancy interacts with vector retrieval in LuminaR. Through direct inspection of `LibraryLLM/search/luminar_search.py` and `LibraryLLM/search/index_manager.py`, this audit conclusively determines the vector retrieval topology and provides an architectural analysis of the **Post-Filtering Recall Collapse** phenomenon.

---

## 1. Architectural Strategy Classification

LuminaR employs a **Global Shared Index + Post-Filter** architecture for book search:

| Strategy Candidate | Implemented in LuminaR Book Search? | Evidence / Code Behavior |
| :--- | :---: | :--- |
| **One Index per Library** | **NO** | Only one master `hnsw.index` (9.04 GB) exists in `datasets/ai/faiss/hnsw/`. There are no tenant index directories. |
| **Sharded Vector Clusters** | **NO** | Vectors are not partitioned across nodes or inverted lists by `library_id`. |
| **Filtered Vector Index (Pre-Filtering)**| **NO** | FAISS HNSW does not use custom ID selectors or pre-filtered graphs based on institutional membership. |
| **Global Shared Index + Post-Filter** | **YES (ACTIVE IMPLEMENTATION)** | A single 5-million-vector HNSW index is searched globally; library availability is filtered in Python memory after retrieval. |
| *(Contrast: Private Document RAG)* | *(Isolated per Document)* | Uploaded user PDFs in `rag/private_documents/` use isolated individual FAISS files (`<doc_id>_index.faiss`). |

---

## 2. Post-Filtering Mechanics in Code

In `search/luminar_search.py:448-772`, the search sequence executes in the following strict order:

```
Step 1: Embed query into 384-D vector
Step 2: Query Global HNSW (5,000,000 vectors) -> Top 50 Global Candidates
Step 3: Rerank Top 50 Candidates using Cross-Encoder
Step 4: Execute Post-Filter on Reranked Pool:
        [r for r in results if r["library_available"] and r["available_physical_copies"] > 0]
Step 5: Slice to top 10 results
```

```python
# Extracted from LibraryLLM/search/luminar_search.py:770-772
if library_id and available_at_library:
    results = [r for r in results if r["library_available"] and r["available_physical_copies"] > 0]
results = results[:final_k]
```

Notice that the library availability check is applied **after** the top 50 candidates have already been locked by the global cross-encoder reranker.

---

## 3. Post-Filter Recall Collapse: Architectural Analysis

> [!WARNING]
> **CLASSIFICATION: ARCHITECTURAL ANALYSIS (NOT MEASURED)**  
> The following analysis is derived from structural code inspection and mathematical properties of vector post-filtering. The exact quantitative drop in Recall@K across specific institutional catalog sizes has not yet been benchmarked on live hardware (`NOT MEASURED`).

### The Mathematical Dilemma of Post-Filtering
Consider a participating library $L_i$ with an inventory size $S = 2{,}500$ physical books out of the $N = 5{,}000{,}000$ books indexed in the global HNSW graph (an inventory fraction of $\rho = 0.05\%$).

Suppose a patron at Library $L_i$ searches for a broad academic topic: *"principles of quantum mechanics"*:
1. Across the 5,000,000-book global corpus, there are approximately 1,500 books related to quantum mechanics.
2. Library $L_i$ physically owns 20 relevant quantum mechanics books.
3. However, none of the 20 books owned by Library $L_i$ happen to be in the **Top 50 global semantic matches** returned by the HNSW index (for example, the library owns solid introductory textbooks, while the top 50 global spots are occupied by famous treatises, historical biographies, or multi-volume editions).
4. The global HNSW returns the top 50 candidates, none of which are held by Library $L_i$.
5. The post-filter executes:
   $$\text{Available Pool} = \text{Top50}_{\text{Global}} \cap \text{Holdings}_{L_i} = \emptyset$$
6. **The user receives 0 results** (*"No books found available at this library"*), even though the library has 20 highly relevant books sitting on its shelves!

### Visualizing the Flaw

```
Global Corpus (5,000,000 books)
┌────────────────────────────────────────────────────────────────────────┐
│  All Quantum Books in World (1,500 books)                               │
│  ┌───────────────────────┐                                             │
│  │ Top 50 Global Matches │  ◄── HNSW ONLY RETRIEVES THIS BOX           │
│  │ (Library owns 0 of 50)│                                             │
│  └───────────────────────┘                                             │
│                                                                        │
│        Library Holdings on Quantum (20 books owned by Library X)        │
│        [Rank 65, Rank 112, Rank 140, Rank 210, ...]                    │
│        ▲                                                               │
│        └── NEVER SEEN BY POST-FILTER (Excluded before reranking!)      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Alternative Architectural Pathways for True Multi-Tenancy

To eliminate post-filter recall collapse in future development, three viable architectural alternatives exist:

1. **Filtered HNSW (Pre-Filtering via FAISS IDSelector):**
   * Pass a boolean bitmap or `faiss.IDSelectorArray` representing Library $L_i$'s holdings directly into `index.search()`.
   * HNSW only considers nodes held by that library during graph traversal.
2. **Dedicated Per-Library HNSW Indices:**
   * Maintain a separate small `IndexHNSWFlat` per participating institution (e.g., 2,500 vectors = ~4.5 MB RAM).
   * Search queries are routed directly to the tenant's dedicated index, guaranteeing 100% recall over owned stock.
3. **Two-Stage Hybrid Fallback (Partially Present in LuminaR):**
   * If post-filtered results $< K$, fall back to MongoDB lexical text search (`usable` in `backend/services/library_catalogue_experience.py:45`), directly querying the library's local catalogue table.
