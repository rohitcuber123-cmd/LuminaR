# 02 — COMPLETE TECHNOLOGY STACK

## 1. Verified Technology Stack Inventory

This inventory documents every technology used specifically across LuminaR's three Knowledge Graph subsystems. It rigorously distinguishes libraries declared in package manifests from those **actually executed in production code**.

| Layer | Technology | Version | Purpose in Graph Subsystem | Where Used | Production Evidence |
|---|---|---|---|---|---|
| **Frontend Framework** | React | `^18.2.0` | Component lifecycle, state binding, reconciliation | All graph views | [`frontend/package.json`](file:///d:/SDC/LibraryLLM/frontend/package.json) |
| **Frontend Language** | TypeScript | `^5.2.2` | Strong type definitions for graph nodes, edges, reason paths | Entire frontend graph client | [`frontend/src/lib/knowledgeGraph.ts`](file:///d:/SDC/LibraryLLM/frontend/src/lib/knowledgeGraph.ts) |
| **Graph Visualization Engine** | Custom React SVG Canvas | Native SVG | Renders nodes as styled rectangles/pills and edges as cubic Bezier curves | Graph Lab, Library Graph, Book Details | [`MetadataGraphCanvas.tsx:L8-L11`](file:///d:/SDC/LibraryLLM/frontend/src/components/MetadataGraphCanvas.tsx#L8-L11) |
| **Graph Layout Engine** | Custom Coordinate Mapper | Pure TypeScript | Calculates deterministic 3-column coordinate positioning without physics simulation | Bipartite SVG canvas | [`MetadataGraphCanvas.tsx:L6`](file:///d:/SDC/LibraryLLM/frontend/src/components/MetadataGraphCanvas.tsx#L6) |
| **Frontend Icons** | `lucide-react` | `^0.344.0` | UI icons: `Network`, `ZoomIn`, `ZoomOut`, `Search`, `ArrowRight` | Graph Lab toolbar & empty states | [`KnowledgeGraphPage.tsx:L7`](file:///d:/SDC/LibraryLLM/frontend/src/pages/KnowledgeGraphPage.tsx#L7) |
| **CSS Styling** | TailwindCSS | `^3.4.1` | Layout styling, glassmorphism, responsive grid containers | Graph page containers | [`KnowledgeGraphPage.tsx:L74-L101`](file:///d:/SDC/LibraryLLM/frontend/src/pages/KnowledgeGraphPage.tsx#L74-L101) |
| **Backend Runtime** | Python | `3.11+` | Core execution runtime for graph algorithms, extraction, and API | All backend graph services | [`pyproject.toml`](file:///d:/SDC/LibraryLLM/pyproject.toml) |
| **Backend Framework** | FastAPI | `^0.110.0` | REST routing, dependency injection, query validation, HTTP error codes | Graph API endpoints | [`backend/routes/knowledge_graph.py:L5-L18`](file:///d:/SDC/LibraryLLM/backend/routes/knowledge_graph.py#L5-L18) |
| **Request Validation** | Pydantic v2 | `^2.6.0` | Schema validation, regex constraints on work IDs, input limits | API input models (`SeedRequest`) | [`backend/routes/knowledge_graph.py:L27-L30`](file:///d:/SDC/LibraryLLM/backend/routes/knowledge_graph.py#L27-L30) |
| **Graph Database (Subsystem A)** | SQLite3 | Native C/Python | Read-only indexed relational storage for bipartite nodes, edges, features, and norms | Global catalogue graph storage | [`knowledge_graph/core.py:L30-L38`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L30-L38) |
| **Catalogue Source Store** | MongoDB | `^4.6.0` (`pymongo`) | Master bibliographic document store streamed to build SQLite graph | Build scripts & live consistency check | [`scripts/build_catalogue_graph.py:L78-L81`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L78-L81) |
| **NLP Stopword Filtering** | `scikit-learn` | `^1.4.0` | Curated English stopword set (`ENGLISH_STOP_WORDS`) | Topic n-gram filtering | [`knowledge_graph/topics.py:L6`](file:///d:/SDC/LibraryLLM/knowledge_graph/topics.py#L6) |
| **Text Normalization** | Python `unicodedata` | Standard Library | Unicode NFKC normalization and casefolding | Canonical key creation | [`knowledge_graph/core.py:L15`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L15) |
| **Cryptographic Hashing** | Python `hashlib` | Standard Library | Deterministic feature node IDs (`sha256`), content digests | Graph node identification & build manifests | [`knowledge_graph/core.py:L24`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L24) |
| **Sentence Embeddings (Subsystem B)** | `SentenceTransformer` | `^2.5.0` (`all-MiniLM-L6-v2`) | Dense representation for Maximal Marginal Relevance concept deduplication | Document knowledge build pipeline | [`rag/services/document_knowledge.py:L345-L356`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L345-L356) |
| **Vector Math (Subsystem B)** | NumPy | `^1.26.0` | Cosine similarity matrix multiplication (`vectors[index] @ vectors[other]`) | MMR diversity calculation | [`rag/services/document_knowledge.py:L385`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L385) |
| **Graph Storage (Subsystem C)** | Atomic Disk JSON | Native OS/JSON | Durable, content-addressed JSON graph artifacts (`graph.json`) | Tenant library knowledge graph | [`backend/services/library_intelligence_artifacts.py:L75-L76`](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py#L75-L76) |

---

## 2. Detailed Layer Analysis

### 2.1 Frontend Visualization Layer

A major architectural finding is that LuminaR **does not rely on heavy external graph visualization frameworks** such as D3.js, Cytoscape.js, React Flow, vis-network, or Sigma.js.

#### Architectural Rationale:
1. **Zero External Dependency Overhead:** Traditional graph visualization bundles (e.g., Cytoscape, D3-force) introduce 150KB–500KB of minified JavaScript, require Canvas/WebGL setup, and suffer from non-deterministic force-directed layout instability (where nodes bounce around unpredictably).
2. **Deterministic 3-Column Geometry:** Because the global graph represents a 2-hop bipartite recommendation path ($\text{Seed} \to \text{Shared Features} \to \text{Recommended Books}$), a fixed 3-column SVG coordinate mapping is mathematically and visually superior:
   - Left column ($x = 135$): Starting/Seed Book node.
   - Middle column ($x = 450$): Shared Author, Subject, and Topic bridge nodes.
   - Right column ($x = 765$): Connected candidate book nodes.
3. **Smooth Cubic Bezier Trajectories:** Edges are rendered using standard SVG `<path>` elements with cubic Bezier curves:
   ```typescript
   // frontend/src/components/MetadataGraphCanvas.tsx:L9
   d={`M ${a.x} ${a.y} C ${(a.x+b.x)/2} ${a.y}, ${(a.x+b.x)/2} ${b.y}, ${b.x} ${b.y}`}
   ```
   This gives an elegant, circuit-like visual flow from left to right without expensive physics simulations.

---

### 2.2 Backend & Storage Layer

#### Why SQLite was Chosen over Neo4j:
1. **Zero Network Latency & Read-Only Safety:** Neo4j requires a dedicated JVM service, network roundtrips, Cypher parsing, and connection pooling. For LuminaR's static 2-hop catalogue traversal, SQLite operating with `PRAGMA query_only=ON` in memory-mapped read-only mode (`?mode=ro`) provides microsecond-level query execution.
2. **Portability & Determinism:** The entire global graph compiles into a single file (`catalogue.sqlite`). It can be versioned, copied, backed up, and atomically swapped via OS filesystem renames (`os.replace`).
3. **Relational Indexing for Graph Queries:** In bipartite graphs where edge traversals are fixed to 2 hops, relational indexes on `(book_id, kind, term)` and `(kind, term, book_id)` outperform general-purpose property graph traversers in raw throughput.

---

### 2.3 NLP & AI Stack

#### What is Actually Used:
1. **Rule-Based Morphology & Regex Parsing:** Multi-word term normalization uses `unicodedata.normalize('NFKC')` combined with strict regular expressions (`WORD = re.compile(r'\b[^\W\d_]{3,40}\b')`).
2. **TF-IDF Statistical Topic Extraction:** Extracts adjacent bigrams and trigrams from book descriptions, filters generic stopwords using scikit-learn's dictionary, and scores terms against corpus inverse document frequency.
3. **CPU-Bounded MiniLM Embeddings (Subsystem B Only):** In the document study module, `all-MiniLM-L6-v2` encodes candidate concepts into 384-dimensional vectors. This is strictly executed on CPU with a hard cap of 192 candidate embeddings to prevent latency spikes.

#### What is NOT Used (Debunking Common Assumptions):
- **NO LLM Extraction:** Qwen, GPT-4, or other LLMs are **NOT** invoked to discover graph nodes or relationships. Telemetry explicitly logs `qwen_calls: 0`.
- **NO spaCy / NLTK:** Part-of-speech tagging and dependency parsing rely on regex copula patterns rather than bulky neural NLP pipelines.
- **NO GraphRAG:** Graph structures do not participate in vector retrieval or LLM context generation during document Q&A.
