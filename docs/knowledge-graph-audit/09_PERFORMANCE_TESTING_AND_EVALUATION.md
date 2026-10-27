# 09 — PERFORMANCE, TESTING & QUALITY EVALUATION

## 1. Performance Characteristics & Complexity Analysis

LuminaR’s graph architecture is designed to avoid the quadratic bottlenecks ($O(V^2)$) typical of naive pairwise similarity graphs.

### 1.1 Computational Breakdown Across Stages

| Pipeline Stage | Algorithm / Operation | Theoretical Complexity | Bounded Scale in LuminaR | Typical Execution Latency |
|---|---|---|---|---|
| **Text Ingestion** | PDF text chunk scanning & unit parsing | $O(U \cdot L_{\text{avg}})$ | $U \le 2,200$ units, $L \le 650$ chars | $15 - 45\text{ ms}$ (CPU) |
| **Concept Scoring** | Multi-signal heuristic scoring | $O(C_{\text{cand}} \cdot |W|)$ | $C_{\text{cand}} \le 3,500$ candidates | $8 - 20\text{ ms}$ (CPU) |
| **Embedding Generation** | MiniLM CPU sentence encoding | $O(K \cdot D)$ | $K \le 192$ candidates, $D = 384$ | $35 - 80\text{ ms}$ (CPU) |
| **MMR Selection** | Greedy argmax with cosine suppression | $O(K \cdot T)$ | $K \le 192, T \le 30$ concepts | $< 5\text{ ms}$ (NumPy) |
| **2-Hop SQLite Traversal** | Indexed relational join on shared features | $O(|F_s| \cdot \overline{\text{deg}}(f))$ | Explores only connected candidates | $4 - 12\text{ ms}$ (SQLite) |
| **Reason Path Assembly** | Bridge edge extraction for top-$K$ books | $O(K \cdot |F_s \cap F_c|)$ | $K \le 50, M \le 3$ reasons | $2 - 5\text{ ms}$ (SQLite) |
| **Frontend SVG Layout** | Deterministic 3-column coordinate mapping | $O(V + E)$ | $V \le 40$ nodes, $E \le 60$ edges | $< 2\text{ ms}$ (Browser V8) |

---

## 2. Unit & Integration Test Suite Audit

LuminaR includes an automated pytest test suite verifying graph generation, mathematical properties, and API guards.

### 2.1 Test Suite Inventory

#### 1. Core Graph Tests: [`tests/test_knowledge_graph.py`](file:///d:/SDC/LibraryLLM/tests/test_knowledge_graph.py) (120 lines)
- `test_full_graph_has_typed_deduplicated_edges_and_no_private_fields`: Validates edge deduplication, isolate counts, and confirms private librarian notes do not enter SQLite.
- `test_normalization_preserves_comma_names_and_separates_feature_types`: Confirms NFKC casefolding and pipe parsing.
- `test_more_like_this_paths_are_real_and_contributions_sum_to_score`: **Critical mathematical proof** that individual reason path contributions sum exactly to the final cosine score ($0 < \text{score} \le 1$).
- `test_rarity_weighting_and_fair_exclusions`: Confirms inverse-logarithmic rarity weighting ($W_{\text{rare}} > W_{\text{generic}}$) and verifies active loan exclusions.
- `test_isolated_unknown_invalid_and_empty_graph`: Tests edge cases: books with no features return empty recommendations; invalid IDs raise `KeyError`.
- `test_exploration_keeps_only_returned_books_and_real_paths`: Confirms exploration subgraphs contain only returned books and valid bridge paths.
- `test_metrics_handle_sparse_metadata_and_report_exact_sets`: Validates Overlap@K, Jaccard, and subject pairwise diversity calculations.
- `test_authenticated_routes_validate_seed_and_preserve_reason_paths`: FastAPI test client testing authentication, regex work ID validation, and 422 error boundaries.
- `test_stale_seed_fails_closed`: Verifies that if live metadata diverges from the snapshot, the API fails closed with HTTP 409.

#### 2. Topic Graph Tests: [`tests/test_kg_topics.py`](file:///d:/SDC/LibraryLLM/tests/test_kg_topics.py) (73 lines)
- `test_topic_extraction_deterministic`: Verifies phrase generation idempotence.
- `test_topic_stopwords`: Asserts stopword exclusion from description phrases.
- `test_topic_limit_and_degree`: Verifies that topics obey degree limits ($3 \le \text{deg} \le \text{maximum}$) and per-book caps ($\le 5$).
- `test_topic_source_traceability_and_relation_contribution_sum`: Validates description SHA-256 provenance hashes.
- `test_weak_relation_cannot_qualify_alone`: Confirms that publisher or language overlap alone cannot trigger a recommendation.

---

## 3. Graph Quality Evaluation Framework

LuminaR implements programmatic evaluation metrics in [`knowledge_graph/metrics.py`](file:///d:/SDC/LibraryLLM/knowledge_graph/metrics.py):

### 3.1 Implemented Comparative Metrics
To evaluate the Knowledge Graph recommender against baseline collaborative/content filtering, LuminaR computes:

1. **List Overlap ($Overlap@K$):**
   $$\text{Overlap}@K = \frac{|A \cap B|}{\min(|A|, |B|)}$$
   Measures the fraction of top-$K$ recommendations shared between the graph recommender and the baseline recommender.
2. **Jaccard Similarity:**
   $$J(A, B) = \frac{|A \cap B|}{|A \cup B|}$$
3. **Subject Pairwise Diversity:**
   $$\text{Div}(S) = \frac{1}{\binom{|B|}{2}} \sum_{i < j} \left(1 - \frac{|S_i \cap S_j|}{|S_i \cup S_j|}\right)$$
   Measures the semantic dispersion of recommended books across subjects. A higher score indicates broader, less repetitive recommendations.

---

### 3.2 Recommended Gold-Standard Evaluation Methodology

For viva defense and research publications, the following evaluation methodology is recommended:

```
+---------------------------------------------------------------------------------------------------+
|                              RECOMMENDED KG QUALITY EVALUATION PROTOCOL                           |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  1. Annotation Protocol:                                                                          |
|     * Sample 50 seed books across 5 diverse disciplines (Computer Science, History, Literature,   |
|       Physics, Economics).                                                                        |
|     * For each seed, pool top-10 candidates from Graph Recommender and Vector Recommender.        |
|     * Blind evaluation by 3 human domain judges scoring relevance on a 3-point scale:             |
|       0 = Irrelevant, 1 = Weakly Related, 2 = Highly Relevant.                                    |
|                                                                                                   |
|  2. Quantitative Evaluation Metrics:                                                              |
|     * Precision@10: Fraction of recommended items judged relevant.                                |
|     * Mean Reciprocal Rank (MRR): Position of the first highly relevant book.                     |
|     * Reason Plausibility (%): Fraction of reason paths judged factually sound by evaluators.     |
|                                                                                                   |
|  3. Diversity & Serendipity:                                                                      |
|     * Intra-List Distance (ILD) across subject taxonomies.                                        |
|     * Serendipity: Relevant recommendations surprising to the reader (absent from top vectors).   |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```
