# Recommendation & Knowledge Graph Limitations and Safe Terminology

## 1. Executive Summary

This document establishes the **authoritative scientific terminology and empirical limitations** for the recommendation and graph modules in LuminaR. To maintain research integrity, academic papers, technical reports, and documentation must avoid inflated terminology (such as "Knowledge Graph" or "Collaborative Filtering Engine") when the actual implementation consists of heuristic content scoring, vector retrieval, and a SQLite bipartite metadata index.

---

## 2. Safe Research Terminology Guide

| Marketing / UI Label | Implementation Reality | ❌ Disallowed Academic Term | ✅ Safe Scientific Term |
|---|---|---|---|
| **"Knowledge Graph"** | SQLite bipartite graph linking books to author, subject, and topic terms with cosine-TFIDF scoring | "Formal Knowledge Graph", "Ontology", "RDF Triple Store", "Semantic Web KB", "SPARQL Endpoint", "Graph Neural Network (GNN)" | **Bipartite Entity-Feature Graph**, **Inverted Metadata Similarity Network**, **2-Hop Meta-Path Recommendation Graph** |
| **"Graph Lab"** | Interactive SVG visualization of 2-hop reason paths and bridge feature nodes | "Graph Neural Visualization", "3D Knowledge Exploration Engine", "Ontological Navigator" | **Bipartite Ego-Network Subgraph Visualization**, **SVG Connection Map** |
| **"Recommendation Engine"** | 8-factor linear combination of vector retrieval, subject overlap, loan history, and feedback | "Collaborative Filtering Engine", "Deep Recommender System", "Two-Tower Neural Recommender", "Matrix Factorization" | **Hybrid Heuristic Content Recommender**, **Multi-Signal Content-and-Behavior Scorer** |
| **"AI Topics"** | N-gram token scanning of book descriptions filtered by corpus frequency | "LLM-Extracted Ontology", "Neural Topic Modeling (LDA/BERTopic)", "Semantic Entity Linking" | **Corpus-Filtered N-gram Source Phrases**, **TF-IDF Keyword Extraction** |
| **"Personalized Feed"** | Recency-weighted search queries concatenated into HNSW vector search | "Reinforcement Learning Feed", "Bandit-Optimized Recsys", "Recurrent User Modeling" | **Recency-Decayed Search History Vector Retrieval** |

---

## 3. Recommendation System Limitations

### 3.1 Absence of Collaborative Filtering (CF)
- LuminaR contains **no collaborative filtering models**:
  - No matrix factorization (SVD, SVD++, NMF, PMF).
  - No Alternating Least Squares (ALS) or implicit feedback factorization.
  - No user-user or item-item collaborative nearest neighbors.
  - No two-tower neural networks or graph convolutional recommenders (LightGCN, PinSage).
- **Impact**: Recommendations cannot discover unexpected cross-domain affinities (e.g. "readers who enjoyed Douglas Adams also borrow Terry Pratchett") unless those books already share explicit author names, subject strings, or semantic embeddings.

### 3.2 User Cold-Start Drop in Standalone Service
- In the global recommendation microservice (`:8004`), an unauthenticated or newly registered user with zero search queries receives an **empty candidate list** (`results: []`).
- Personalization relies entirely on the tenant library fallback (`arrival_sort()` recent acquisitions) to prevent displaying a blank screen.

### 3.3 Semantic Dominance & Query Concatenation Heuristic
- The combined query mechanism simply joins the user's top 10 recency-weighted queries with whitespace:
  `combined_query = " ".join(recent_queries)`.
- If a user previously searched for `"organic chemistry"` and `"medieval European history"`, the search service receives the concatenated string `"organic chemistry medieval European history"`.
- This causes the BGE embedding model to produce an unnatural centroid vector that may retrieve irrelevant books located in the arithmetic midpoint of semantic space.

### 3.4 Heuristic Diversity Re-ranking vs. Formal Optimization
- Diversity re-ranking uses a greedy pass with fixed thresholds (`MAX_BOOKS_PER_AUTHOR = 2`, Jaccard subject $\ge 0.80$, title token $\ge 0.80$).
- It does not optimize a formal diversity-relevance objective function (such as Determinantal Point Processes - DPP, Maximum Marginal Relevance - MMR, or Submodular Maximization).

### 3.5 Linear Additive Feedback Loop
- User feedback (`VIEWED`, `CLICKED`, `RESERVED`, `ISSUED`, `DISMISSED`) is aggregated into a simple linear adjustment ($+0.10 \times \text{FeedbackScore}$).
- There is no exploration-exploitation balance (e.g., LinUCB, Thompson Sampling, or Upper Confidence Bound bandits), meaning repeatedly viewed topics can create a self-reinforcing preference bubble.

---

## 4. Knowledge Graph Limitations

### 4.1 Lack of Formal Knowledge Representation
- **No RDF / OWL / RDFS Standards**: Data is stored in standard relational SQLite tables (`books`, `features`, `edges`), not RDF triples (`<subject, predicate, object>`).
- **No Taxonomic Hierarchy**: There is no parent-child relationship between subjects. For example, `"Machine Learning"` is treated as completely disjoint from `"Artificial Intelligence"`; the graph cannot infer that a book classified under the former is also related to the latter unless they share a textual link.
- **No Reasoning / Inference**: Graph traversal is strictly 2 hops. There is no multi-hop path reasoning or logical deduction.

### 4.2 Entity Ambiguity & Lack of Authority Control
- Author nodes are indexed by raw surface strings normalized with Unicode NFKC and lowercase casefolding.
- **Homonym Conflation**: Distinct real-world authors sharing a common name (e.g. `"David Smith"`) are merged into a single high-degree feature node, creating spurious 2-hop bridges between unrelated books.
- **Synonym Fragmentation**: A single author whose name appears in multiple formats (e.g. `"J.K. Rowling"`, `"Joanne Rowling"`, `"Rowling, J. K."`) forms distinct, unconnected nodes because there is no authority control (VIAF, ISNI, or Wikidata integration).

### 4.3 Static Snapshot & Invalidation Bottleneck
- The graph is a static **5.87 GB SQLite file** generated offline from an initial snapshot of 5,000,000 books.
- It does **not** dynamically synchronize with MongoDB mutations.
- If a book's metadata is updated in the library catalog, the API returns `HTTP 409 Conflict: "This book’s metadata changed. Rebuild the graph before comparing it."`.
- Rebuilding the graph requires streaming 5M books and takes **882.81 seconds (~14.7 minutes)** of offline execution.

### 4.4 Empirically Failed KG4 Hybrid Reranking Experiment
As documented in [`reports/knowledge_graph_final.md`](file:///d:/SDC/LibraryLLM/reports/knowledge_graph_final.md#L43-L48):
- A proposed KG4 hybrid re-ranking experiment (combining graph recommendations with existing vector recommendations) was **formally deferred**.
- Across a frozen 40-seed evaluation protocol:
  - While list novelty passed (92.5% of seeds returned KG-only candidates),
  - **Subject diversity dropped by $-0.05720$**, violating the pre-declared maximum permissible decline of $0.05$.
- Furthermore, because LuminaR lacks ground-truth relevance labels (CTR, human editorial relevance judgements, or NDCG benchmarks), the engineering team correctly concluded that different candidates alone do not justify replacing or hybridizing the production recommender.

---

## 5. Summary Table: Claim vs. Verified Reality

| Proposed Paper Claim | Verified Code Reality | Recommendation for Paper |
|---|---|---|
| *"LuminaR features an enterprise Knowledge Graph for book discovery"* | Persisted SQLite bipartite graph with TF-IDF cosine similarity and 2-hop explanations | Refactor to: *"LuminaR implements a bipartite entity-feature metadata graph with explainable 2-hop meta-paths"* |
| *"The graph performs deep ontological reasoning"* | Surface text string matching over author and subject tags | Refactor to: *"The graph utilizes normalized lexical matching over catalog metadata"* |
| *"Personalized recommendations combine collaborative and content-based filtering"* | Purely content-based hybrid scoring using vector embeddings, loan/hold overlap, and feedback adjustment | Refactor to: *"Personalization utilizes a multi-signal content-and-behavior heuristic without collaborative filtering"* |
| *"Knowledge expansion enables open-ended semantic discovery"* | Inverted SQL index query over shared features returning a 2-hop ego-network | Refactor to: *"Knowledge expansion executes deterministic 2-hop meta-path traversal across bridging features"* |
