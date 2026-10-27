# 21_SEARCH_FAILURE_MODES.md: Search Failure Taxonomy & Vulnerability Audit

## Executive Summary

This document establishes a rigorous taxonomy of search failure modes within LuminaR's hybrid retrieval system. Every identified vulnerability is grounded in concrete repository architecture, mathematical characteristics of approximate nearest-neighbor search, or empirical data quality deficiencies.

To maintain strict scientific integrity, theoretical failure modes whose precise error rates have not been empirically benchmarked are marked with **NOT MEASURED**.

---

## 1. Master Search Failure Taxonomy

| Failure Mode ID | Category | Root Cause in Repository | Observed / Modeled Impact | Empirical Status |
| :--- | :--- | :--- | :--- | :--- |
| **FAIL-01** | **Post-Filter Elimination** | Global HNSW retrieves top 50 globally before checking `library_inventory` (`search/luminar_search.py:770`) | Returns 0 results for a library that owns relevant books ranked 51–200 globally | **ARCHITECTURAL CERTAINTY (NOT MEASURED)** |
| **FAIL-02** | **Author Exact-Match Miss** | `_author_match_ids` requires `_norm_text(query) == _norm_text(author)` (`search/luminar_search.py:99`) | Query `"books by Andrew Ng"` fails author equality; author boost never fires | **VERIFIED BY CODE TRACE** |
| **FAIL-03** | **Missing Description Collapse** | ~30% of OpenLibrary works have empty descriptions; vector collapses to title/author | Concept-based queries fail to retrieve books whose titles do not contain keywords | **VERIFIED BY DATA AUDIT** |
| **FAIL-04** | **Typo Embedding Distortion** | Subword tokenization on misspelled words (`LEXICAL_SEARCH_ENABLED=false`) | Query vector drifts in dense space; relevant books score below unrelated candidates | **OBSERVED IN CODE** |
| **FAIL-05** | **Polysemy & Ambiguity Drift**| Unsupervised bi-encoder maps ambiguous words (*"apple"*, *"networking"*, *"python"*) to centroid | Retrieves an unranked mixture of computer science and biology/cooking titles | **ARCHITECTURAL LIMITATION** |
| **FAIL-06** | **256-Token Truncation Gap** | `all-MiniLM-L6-v2` truncates after token 256 (`search/index_manager.py:35`) | Technical terms in long abstracts (paragraphs 3+) are discarded during indexing | **VERIFIED BY CODE AUDIT** |
| **FAIL-07** | **HNSW Graph ANN Miss** | Approximate search graph traversal at $efSearch = 128$ can terminate in local minimum | Mathematically optimal nearest neighbors in vector space are bypassed | **NOT MEASURED** |
| **FAIL-08** | **Cross-Encoder Context Cap** | Cross-encoder sequence length capped at 512 tokens (`[CLS] query [SEP] title+authors+subjects [SEP]`) | Excess subject strings or descriptions truncated during cross-attention pass | **VERIFIED BY MODEL SPEC** |
| **FAIL-09** | **Small-Model Capacity Limit**| 22.7M parameter encoder possesses lower semantic representation resolution than 330M/7B models | High collision rate in dense embedding space for nuanced domain concepts | **NOT MEASURED** |
| **FAIL-10** | **Database-Index Divergence** | `hnsw.index` contains vector labels for works subsequently deleted in MongoDB | Triggers dynamic while-loop overfetching (`fetch_k * factor`); increases query latency | **VERIFIED IN CODE** |

---

## 2. In-Depth Failure Mode Analysis

### FAIL-01: Post-Filter Elimination (The Multi-Library Recall Trap)
* **Mechanism:**
  1. Patron queries: *"advanced machine learning deep learning"* with `available_at_library=True`.
  2. HNSW queries 5,000,000 global books and selects the top 50 global matches.
  3. The local participating library has 30 relevant textbooks on deep learning, but all 30 were ranked between position 51 and 180 in the global ranking.
  4. Cross-encoder scores the top 50 global books.
  5. The post-filter checks whether the local library holds any of the 50 books:
     ```python
     results = [r for r in results if r["library_available"] and r["available_physical_copies"] > 0]
     ```
  6. **Result:** All 50 books are dropped. The patron receives an empty screen (`results = []`), despite the library holding dozens of relevant titles.

---

### FAIL-02: Author Exact-Match String Inequality
* **Mechanism:**
  ```python
  # LibraryLLM/search/luminar_search.py:91-100
  q = self._norm_text(query)
  if not q or len(q.split()) < 2:
      return set()
  for wid, book in metadata.items():
      if any(self._norm_text(a) == q for a in (authors or [])):
          ids.add(wid)
  ```
* **Failure Trigger:**
  * When a user searches `"books by J.K. Rowling"`, `q` becomes `"books by j k rowling"`.
  * The author metadata is `"J.K. Rowling"` $\to$ `"j k rowling"`.
  * Because `"books by j k rowling" != "j k rowling"`, the check evaluates to `False`.
* **Consequence:** The dedicated author boost tier (`author_ids`) does **not** engage for natural language author queries unless the user types *exclusively* the author's exact name without the words *"books by"*.

---

### FAIL-03: Missing Description Semantic Collapse
* **Mechanism:**
  * In `search/index_manager.py:85`, book text is assembled as:
    `f"Title: {title}. Authors: {authors}. Subjects: {subjects}. Description: {description or ''}"`
  * When `description` is absent, the SentenceTransformer encoder can only extract semantic meaning from the title and subject tags.
* **Failure Trigger:**
  * User query: *"novel about a totalitarian surveillance state where history is rewritten"*.
  * Target book: *"Nineteen Eighty-Four"* by George Orwell.
  * If the description is missing, the indexed text contains only *"Title: Nineteen Eighty-Four. Authors: George Orwell. Subjects: Fiction, Classics"*.
  * None of the words *"totalitarian"*, *"surveillance"*, or *"history rewritten"* exist in the vector.
* **Consequence:** Dense cosine similarity is low; the book fails to appear in the top-50 candidate pool.

---

### FAIL-04: Typo-Induced Embedding Drift
* **Mechanism:**
  * In the default configuration (`LEXICAL_SEARCH_ENABLED=false`), queries bypass fuzzy matching.
  * Input: `"artifical inteligence"`.
  * WordPiece tokenizer splits the unrecognized token `"artifical"` into subwords: `['art', '##ific', '##al']`.
  * The vector representation formed from `['art', '##ific', '##al']` is semantically distinct from `['artificial']`.
* **Consequence:** Nearest-neighbor search is pulled toward books containing words related to *"art"* rather than computing/AI, causing irrelevant recommendations.

---

### FAIL-07: HNSW Approximate Nearest Neighbor Deficit
* **Mechanism:**
  * HNSW is a heuristic graph search. At each layer, greedy routing navigates toward the nearest neighbor until a local minimum is reached.
  * With `efSearch = 128` over a dense graph of 5,000,000 nodes ($M = 32$), the search exploration beam can terminate in a disconnected neighborhood, missing the global true nearest neighbors.
* **Status:** **NOT MEASURED**. Exact Recall@K degradation compared to an exact brute-force flat inner-product scan (`IndexFlatIP`) has not been benchmarked on the 5M corpus.
