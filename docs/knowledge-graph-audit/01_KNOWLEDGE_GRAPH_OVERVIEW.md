# 01 — KNOWLEDGE GRAPH FEATURE DISCOVERY & TAXONOMY OVERVIEW

## 1. Executive Summary & Repository Discovery

A code-level investigation of the complete LuminaR codebase reveals that **there is not a single, monolithic "Knowledge Graph"**. Instead, LuminaR implements **three distinct, production-reachable graph subsystems**, each designed for a different domain, operating on different data structures, using distinct persistence mechanisms, and fulfilling distinct user experiences:

1. **Subsystem A: The Global Catalogue Bipartite Knowledge Graph (Graph Lab / Recommender)**
   - **Primary Entry Points:** `knowledge_graph/core.py`, `backend/routes/knowledge_graph.py`, `scripts/build_catalogue_graph.py`, `scripts/build_kg_topics.py`.
   - **Domain:** Global bibliographic discovery and explainable recommendation across the public library catalogue.
   - **Data Model:** Typed bipartite/tripartite entity association graph stored in SQLite (`catalogue.sqlite`). Links `Book` nodes to `Author`, `Subject`, and TF-IDF `Topic` nodes.
   - **Core Engine:** 2-hop graph traversal with weighted cosine similarity scoring over shared features.
   - **Frontend Interface:** `frontend/src/pages/KnowledgeGraphPage.tsx`, `frontend/src/components/MetadataGraphCanvas.tsx`, `frontend/src/components/BookConnectionGraph.tsx`.

2. **Subsystem B: The Document Concept Map / Document Knowledge Graph (Knowledge Tools)**
   - **Primary Entry Points:** `rag/services/document_knowledge.py`, `rag/services/knowledge_algorithms.py`.
   - **Domain:** Single-document study aids and educational concept exploration generated on-the-fly from uploaded PDF documents.
   - **Data Model:** Syntactic copula and noun-phrase concept graph. Connects document sections, educational concepts, and textual evidence definitions.
   - **Core Engine:** Deterministic rule-based NLP extraction (copula patterns like `DEFINED_AS`, `CONTAINS`, `USED_FOR`, `HAS_STEP`), noun-phrase candidate ranking, and MMR (Maximal Marginal Relevance) deduplication via CPU sentence embeddings.
   - **Frontend Interface:** Integrated within the Document Study / Mind Map workspace.

3. **Subsystem C: The Tenant Intelligence Knowledge Graph (Multi-Tenant Library Subsystem)**
   - **Primary Entry Points:** `search/library_intelligence.py`, `backend/services/library_intelligence_artifacts.py`, `backend/services/library_intelligence_store.py`, `backend/routes/library_intelligence.py`.
   - **Domain:** Private, tenant-scoped bibliographic relationship mapping for institutional library workspaces.
   - **Data Model:** Scoped JSON graph artifact (`graph.json`) validated with SHA-256 manifests and lease-fenced build workers.
   - **Core Engine:** In-memory graph builder linking tenant books to author, subject, and Dewey/classification nodes with role-based visibility filtering.
   - **Frontend Interface:** `frontend/src/pages/LibraryGraph.tsx`.

---

## 2. Comprehensive Inventory of Graph Components

The following inventory details every production-reachable component discovered across the repository:

| Subsystem | Component | File Path | Function / Class | Purpose | Implementation Status |
|---|---|---|---|---|---|
| **Subsystem A** | Graph Core Engine | [`knowledge_graph/core.py`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L39-L116) | `CatalogueGraph` | In-memory query engine over SQLite graph: prefix search, 2-hop recommendations, exploration subgraph generation | **VERIFIED** |
| **Subsystem A** | Feature Normalization | [`knowledge_graph/core.py`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L15-L25) | `canonical()`, `terms()`, `feature_id()` | NFKC normalization, pipe delimiter parsing, deterministic SHA-256 feature IDs | **VERIFIED** |
| **Subsystem A** | Relation Policies | [`knowledge_graph/relations.py`](file:///d:/SDC/LibraryLLM/knowledge_graph/relations.py#L1-L9) | `RELATION_WEIGHTS`, `RELATIONS`, `TOPIC_POLICY` | Constant configuration for relation weights ($W_{\text{author}}=2.0, W_{\text{sub}}=1.0, W_{\text{top}}=0.5$) and topic degree limits | **VERIFIED** |
| **Subsystem A** | Topic NLP Extractor | [`knowledge_graph/topics.py`](file:///d:/SDC/LibraryLLM/knowledge_graph/topics.py#L20-L53) | `phrases()`, `choose_topics()` | N-gram candidate generation (bigrams/trigrams), stopword filtering, corpus TF-IDF topic ranking | **VERIFIED** |
| **Subsystem A** | Graph Evaluation Metrics | [`knowledge_graph/metrics.py`](file:///d:/SDC/LibraryLLM/knowledge_graph/metrics.py#L6-L22) | `diversity()`, `compare()` | Set overlap ($Overlap@K$, Jaccard) and subject pairwise distance metrics comparing KG against baseline recommender | **VERIFIED** |
| **Subsystem A** | Graph Builder Script | [`scripts/build_catalogue_graph.py`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L18-L75) | `build()` | Streams MongoDB public books into SQLite tables: `books`, `edges`, `features`, `norms`, `meta` | **VERIFIED** |
| **Subsystem A** | Topic Enrichment Script | [`scripts/build_kg_topics.py`](file:///d:/SDC/LibraryLLM/scripts/build_kg_topics.py#L19-L107) | `enrich()` | Two-pass topic mining over book descriptions, degrees calculation, norm recalculation, SQLite vacuum | **VERIFIED** |
| **Subsystem A** | Backend API Endpoints | [`backend/routes/knowledge_graph.py`](file:///d:/SDC/LibraryLLM/backend/routes/knowledge_graph.py#L16-L117) | `more_like_this()`, `books()`, `comparison()`, `product_more_like_this()` | Fast-API authenticated routes exposing Graph Lab, related books, and baseline comparisons | **VERIFIED** |
| **Subsystem A** | Frontend Graph Lab | [`frontend/src/pages/KnowledgeGraphPage.tsx`](file:///d:/SDC/LibraryLLM/frontend/src/pages/KnowledgeGraphPage.tsx#L14-L102) | `KnowledgeGraphPage()` | Interactive visualization page: book search, node selection, side panel inspector, recommendation comparison | **VERIFIED** |
| **Subsystem A** | SVG Bipartite Canvas | [`frontend/src/components/MetadataGraphCanvas.tsx`](file:///d:/SDC/LibraryLLM/frontend/src/components/MetadataGraphCanvas.tsx#L3-L12) | `MetadataGraphCanvas()` | 3-column SVG layout rendering Seed (left), Features (center), and Recommended Books (right) with cubic Bezier curves | **VERIFIED** |
| **Subsystem A** | Book Detail Bridge | [`frontend/src/components/BookConnectionGraph.tsx`](file:///d:/SDC/LibraryLLM/frontend/src/components/BookConnectionGraph.tsx#L9-L52) | `BookConnectionGraph()` | Vertical 2-hop bridge widget rendered on book detail page showing shared author/subject pills | **VERIFIED** |
| **Subsystem A** | TypeScript Client API | [`frontend/src/lib/knowledgeGraph.ts`](file:///d:/SDC/LibraryLLM/frontend/src/lib/knowledgeGraph.ts#L1-L27) | `graphMeta()`, `graphBooks()`, `graphRecommend()` | Typed API fetch wrappers and TypeScript interfaces (`KGBook`, `KGNode`, `KGEdge`, `ReasonPath`) | **VERIFIED** |
| **Subsystem B** | Document Study Model | [`rag/services/document_knowledge.py`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L90-L457) | `build()`, `DocumentKnowledgeModel` | Rule-based concept extraction, copula relation mining, MMR semantic diversity selection | **VERIFIED** |
| **Subsystem B** | Document Graph Generator | [`rag/services/document_knowledge.py`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L516-L547) | `generate('MIND_MAP')` | Generates document hierarchical concept graph: `document -> group -> concept -> evidence` | **VERIFIED** |
| **Subsystem B** | Compatibility Parsers | [`rag/services/knowledge_algorithms.py`](file:///d:/SDC/LibraryLLM/rag/services/knowledge_algorithms.py#L70-L214) | `definitions()`, `concepts()`, `mind_map()` | POS/regex pattern matching for copulas and heading hierarchy | **VERIFIED** |
| **Subsystem C** | Tenant Graph Builder | [`backend/services/library_intelligence_artifacts.py`](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py#L63-L77) | `build_graph()` | Compiles tenant catalogue into `graph.json` artifact with cryptographic validation | **VERIFIED** |
| **Subsystem C** | Tenant Worker Daemon | [`search/library_intelligence.py`](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L10-L60) | `TenantIntelligence.run_one()` | Lease-fenced background build worker executing atomic artifact creation and validation | **VERIFIED** |
| **Subsystem C** | Scoped Graph Route | [`backend/routes/library_intelligence.py`](file:///d:/SDC/LibraryLLM/backend/routes/library_intelligence.py#L26-L28) | `graph()` | Scoped API endpoint: validates actor library membership and returns authorized subgraphs | **VERIFIED** |
| **Subsystem C** | Tenant Graph UI | [`frontend/src/pages/LibraryGraph.tsx`](file:///d:/SDC/LibraryLLM/frontend/src/pages/LibraryGraph.tsx#L11-L24) | `LibraryGraphPage()` | React page for institutional library graph exploration filtered by active tenant catalogue | **VERIFIED** |

---

## 3. High-Level Taxonomy & Critical Distinctions

A central requirement for university project reviews and IEEE research documentation is establishing the **exact formal nature of the graph**:

```
+---------------------------------------------------------------------------------------------------+
|                                  LUMINAR GRAPH FEATURE TAXONOMY                                    |
+---------------------------------------------------------------------------------------------------+
|                                                                                                   |
|  [SUBSYSTEM A: GLOBAL CATALOGUE GRAPH]    [SUBSYSTEM B: DOCUMENT CONCEPT MAP]                     |
|  * Type: Weighted Bipartite Metadata Net  * Type: Syntactic Copula Concept Network                |
|  * Nodes: Books + Metadata Entities       * Nodes: Document Sections, Concepts, Evidence Texts    |
|  * Edges: AUTHORED_BY, HAS_SUBJECT,       * Edges: DEFINED_AS, CONTAINS, USED_FOR, HAS_STEP       |
|          HAS_TOPIC                        * Storage: In-memory transient (Study Tools)            |
|  * Storage: SQLite (Read-Only URI)        * Goal: Single-document pedagogical study & quiz gen    |
|  * Goal: Explainable Recommendation                                                              |
|                                           [SUBSYSTEM C: TENANT INTELLIGENCE GRAPH]                |
|                                           * Type: Multi-Tenant Scoped Bibliographic Graph         |
|                                           * Nodes: Tenant Books, Authors, Subjects, Dewey Class   |
|                                           * Edges: AUTHORED_BY, HAS_SUBJECT, HAS_CLASSIFICATION   |
|                                           * Storage: SHA-256 Verified Disk JSON Artifacts         |
|                                           * Goal: Private institutional collection discovery      |
|                                                                                                   |
+---------------------------------------------------------------------------------------------------+
```

### Critical Reviewer Takeaways:
1. **Is this a factual Subject-Predicate-Object (SPO) knowledge base like Wikidata or DBpedia?**
   - **NO.** Subsystem A is a **typed bipartite concept network** linking books through shared descriptive metadata. Subsystem B is a **syntactic copula concept network** extracted from document sentences.
2. **Does it use Neo4j or an external graph database?**
   - **NO.** Subsystem A runs on **SQLite** (`PRAGMA query_only=ON`). Subsystem C runs on **content-addressed JSON files** validated by SHA-256 manifests. Subsystem B runs purely **in-memory**.
3. **Does it use an LLM or GraphRAG for graph generation or traversal?**
   - **NO.** LLM generation calls are explicitly set to zero (`qwen_calls: 0`). The graph construction is 100% deterministic, reproducible, and rule-based. Graph traversal does **NOT** feed into LLM prompt synthesis for RAG questions.
