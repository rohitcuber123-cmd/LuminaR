# 15 — VERIFIED LIMITATIONS & FUTURE RESEARCH ROADMAP

## 1. Ranked Verified Limitations by Severity

To maintain academic integrity during project evaluations and viva voce examinations, every known architectural limitation in LuminaR's Knowledge Graph subsystem is documented and ranked below by technical severity.

---

### Severity 1 (High): Lack of Canonical Author Entity Disambiguation
- **Present Implementation:** Author nodes are identified by deterministic hashes of their normalized string representations:
  `canonical(term) = unicodedata.normalize('NFKC', term).casefold().split()`
- **Vulnerability / Problem:** Shared names represent identical string matches, not resolved real-world human identities. If two distinct authors share the name "John Smith" or "David Miller", they are merged into a single author node in SQLite. Conversely, slight name variations (e.g., *"Cormen, Thomas H."* vs *"T. H. Cormen"*) produce two disconnected author nodes.
- **Root Cause in Code:** [`scripts/build_catalogue_graph.py:L68`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L68) explicitly acknowledges: *"Names are metadata strings, not resolved human identities."*
- **Recommended Future Improvement:** Integrate entity resolution against external authority files (Wikidata QIDs, Library of Congress Name Authority, or ORCID) during ingestion.

---

### Severity 2 (High): Absence of GraphRAG Retrieval Augmentation
- **Present Implementation:** The Knowledge Graph exists purely for visual navigation, explainable recommendations, and study tool mind maps. When a reader asks a question in Document Chat, retrieval is handled exclusively by dense vector search (Chroma/FAISS) and BM25 sparse matching.
- **Vulnerability / Problem:** The platform cannot answer global, multi-document synthesis queries that require aggregating knowledge across interconnected communities of documents (e.g., *"Summarize how data structures evolved across our 1980s algorithm collection"*).
- **Recommended Future Improvement:** Implement true GraphRAG: execute Leiden or Louvain community detection over the bipartite graph, generate hierarchical cluster summaries with LLMs, and index community summaries alongside text chunks for holistic multi-hop retrieval.

---

### Severity 3 (Medium): Rule-Based Syntactic Copula Fragility (Subsystem B)
- **Present Implementation:** Document relationships are extracted using compiled regular expressions matching explicit copulas (`is defined as`, `refers to`, `consists of`, `is used for`).
- **Vulnerability / Problem:** Real-world academic textbooks and scientific papers frequently express relationships using passive voice, non-adjacent clauses, or implicit syntax:
  - *"Virtual memory, which enables uniform address spaces, constitutes an essential OS abstraction."* $\to$ May be missed by the linear `DEFINITION` regex.
  - Complex causal, temporal, or hierarchical relations are collapsed into generic `DESCRIBED_AS` edges.
- **Recommended Future Improvement:** Incorporate open-source neural dependency parsers (e.g., spaCy or Stanza) or small open-weights instruction models (e.g., Qwen-2.5-Coder-1.5B) for open information extraction (OpenIE).

---

### Severity 4 (Medium): Monolithic Offline Rebuild Requirement
- **Present Implementation:** The global catalogue graph is stored in a single immutable SQLite database (`catalogue.sqlite`). When new books are catalogued in MongoDB, the entire database must be rebuilt from scratch via `scripts/build_catalogue_graph.py`.
- **Vulnerability / Problem:** Rebuilding the entire graph takes proportional time to catalogue size ($O(B \log B)$). If live metadata changes, the API fails closed with HTTP 409 Conflict until a rebuild occurs.
- **Recommended Future Improvement:** Implement incremental delta updates using write-ahead logging (WAL) and online feature degree updates.

---

### Severity 5 (Low): English-Centric NLP Topic Dictionaries
- **Present Implementation:** Topic mining in book descriptions utilizes `scikit-learn`'s `ENGLISH_STOP_WORDS` and English bibliographic domain terms.
- **Vulnerability / Problem:** While Unicode NFKC normalization correctly handles non-ASCII characters, documents in French, German, Spanish, or Hindi will not have their stopwords filtered, producing noisy topic bridges.
- **Recommended Future Improvement:** Integrate language detection (e.g., `fasttext` or `langdetect`) and dynamically load language-specific stopword lexicons.

---

### Severity 6 (Low): Lack of Human-Annotated Gold-Standard Evaluation
- **Present Implementation:** Graph evaluation is currently measured through statistical metrics: List Overlap ($Overlap@K$), Jaccard similarity, and Subject Pairwise Distance.
- **Vulnerability / Problem:** These metrics measure divergence between recommender systems, not absolute human relevance or perceived accuracy.
- **Recommended Future Improvement:** Execute a formal double-blind user study with 50 domain-annotated seed books, measuring Precision@10, Mean Reciprocal Rank (MRR), and Reason Plausibility.

---

## 2. Summary Comparison: Present Verified Implementation vs. Future Roadmap

| Capability Dimension | Current Verified Implementation (Status: VERIFIED) | Proposed Future Roadmap (Status: NOT IMPLEMENTED) |
|---|---|---|
| **Graph Model** | Typed Bipartite Entity Association Graph | Formal RDF / OWL Property Graph |
| **Storage Engine** | Read-Only SQLite (`PRAGMA query_only=ON`) | Hybrid SQLite + Neo4j / Memgraph for multi-hop queries |
| **Author Resolution** | String canonicalization (NFKC + casefold) | Authority ID Linking (Wikidata QIDs / ORCID) |
| **Relation Extraction** | Regex copula patterns (`DEFINED_AS`, `CONTAINS`) | Neural Open Information Extraction (OpenIE / Spacy) |
| **Topic Modeling** | Degree-bounded bigrams/trigrams via TF-IDF | Embedding-based topic clustering (BERTopic) |
| **RAG Integration** | Visual & recommendation coexistence | GraphRAG with hierarchical community summaries |
| **Graph Rebuilds** | Offline full streaming rebuild + atomic rename | Incremental online streaming updates |
| **Language Support** | English stopwords and rules | Multilingual tokenization and stopword lexicons |
