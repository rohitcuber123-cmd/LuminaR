# 03 — COMPLETE SYSTEM ARCHITECTURE & END-TO-END PIPELINES

## 1. High-Level Architectural Architecture

LuminaR's Knowledge Graph subsystem is structured across three execution pipelines. Below is the verified architectural component diagram:

```mermaid
flowchart TB
    subgraph StorageLayer ["Storage & Database Layer"]
        Mongo[("MongoDB: books_collection")]
        SQLite[("SQLite: catalogue.sqlite (Read-Only)")]
        DiskArtifacts[("Local Disk: JSON Graph Artifacts")]
    end

    subgraph OfflinePipeline ["Subsystem A: Offline Graph Build Pipeline"]
        ScriptBuild["scripts/build_catalogue_graph.py"]
        ScriptTopics["scripts/build_kg_topics.py"]
        ExtractorNLP["knowledge_graph/topics.py (TF-IDF Phrases)"]
        
        Mongo -->|Stream public books| ScriptBuild
        ScriptBuild -->|Generate tables & norms| SQLite
        ScriptTopics -->|Enrich description topics| ExtractorNLP
        ExtractorNLP -->|Two-pass topic edges| SQLite
    end

    subgraph OnlineRuntime ["Subsystem A: Online Recommendation & Exploration Engine"]
        APIRoute["backend/routes/knowledge_graph.py"]
        CoreEngine["knowledge_graph/core.py: CatalogueGraph"]
        MetricsModule["knowledge_graph/metrics.py"]
        
        SQLite -->|PRAGMA query_only=ON| CoreEngine
        APIRoute -->|Invoke 2-hop traversal| CoreEngine
        APIRoute -->|Compare diversity| MetricsModule
    end

    subgraph FrontendApp ["Frontend Presentation Layer"]
        WebPage["frontend/src/pages/KnowledgeGraphPage.tsx"]
        CanvasSVG["frontend/src/components/MetadataGraphCanvas.tsx"]
        DetailBridge["frontend/src/components/BookConnectionGraph.tsx"]
        
        APIRoute -->|JSON Response| WebPage
        WebPage -->|Render bipartite graph| CanvasSVG
        WebPage -->|Inspect node details| WebPage
    end

    subgraph SubsystemB ["Subsystem B: Document Knowledge Tools"]
        PDFUpload["Uploaded PDF Chunks"]
        DocExtractor["rag/services/document_knowledge.py"]
        EmbeddingMMR["all-MiniLM-L6-v2 (CPU Embeddings)"]
        MindMapGen["generate('MIND_MAP')"]
        
        PDFUpload --> DocExtractor
        DocExtractor --> EmbeddingMMR
        DocExtractor --> MindMapGen
    end

    subgraph SubsystemC ["Subsystem C: Tenant Scoped Intelligence"]
        TenantWorker["search/library_intelligence.py"]
        TenantBuilder["backend/services/library_intelligence_artifacts.py"]
        TenantUI["frontend/src/pages/LibraryGraph.tsx"]
        
        TenantWorker --> TenantBuilder
        TenantBuilder -->|Durable JSON| DiskArtifacts
        DiskArtifacts --> TenantUI
    end
```

---

## 2. End-to-End Execution Pipeline (Subsystem A: Catalogue Graph)

Below is the verified end-to-end processing pipeline tracing a user request from the browser to the database and back to SVG rendering:

```mermaid
sequenceDiagram
    autonumber
    actor User as Reader / Researcher
    participant UI as KnowledgeGraphPage.tsx
    participant Canvas as MetadataGraphCanvas.tsx
    participant API as backend/routes/knowledge_graph.py
    participant DBGuard as Live MongoDB Check
    participant Engine as knowledge_graph/core.py
    participant SQLite as catalogue.sqlite

    User->>UI: Selects Starting Book ("OL12345W")
    UI->>API: POST /api/experimental/kg/more-like-this {work_id: "OL12345W", limit: 10}
    
    Note over API: Security & Stale Snapshot Verification
    API->>DBGuard: current_books(books_collection, ["OL12345W"])
    DBGuard-->>API: Live metadata (title, authors, subjects)
    API->>Engine: graph.book("OL12345W")
    Engine->>SQLite: SELECT * FROM books WHERE work_id=?
    SQLite-->>Engine: Snapshot row
    
    alt Metadata Changed Since Build
        API-->>UI: 409 Conflict ("Metadata changed. Rebuild graph.")
    end

    Note over API,Engine: 2-Hop Deterministic Traversal
    API->>Engine: more_like_this(work_id, limit, excluded_loans)
    Engine->>SQLite: Query seed features & norm
    Engine->>SQLite: Score candidates via SUM(weight^2) / SQRT(norm_seed * norm_candidate)
    SQLite-->>Engine: Ranked candidate books & shared bridge edges
    Engine->>Engine: exploration(result, max_reasons=3)
    Engine-->>API: Response payload (seed, recommendations, exploration subgraph)
    
    API-->>UI: HTTP 200 OK (JSON payload)
    UI->>Canvas: Passes visible nodes & edges
    Canvas->>Canvas: Calculates 3-column coordinate geometry
    Canvas-->>User: Renders interactive SVG map with Bezier bridges
```

---

## 3. Stage-by-Stage Processing Pipeline Specification

### Stage 1: Document / Catalogue Streaming & Ingestion
- **Input:** Raw bibliographic documents from MongoDB `books_collection` (`work_id`, `title`, `authors`, `subjects`, `description`, `active`).
- **Processing:** Filters out inactive/non-searchable records (`searchable(row)`). Normalizes text via Unicode NFKC case-folding. Pipe-delimited author and subject fields are parsed into deduplicated dictionaries.
- **Output:** Memory batch of book tuples and typed edge records.
- **Algorithm:** Deterministic string canonicalization:
  $$\text{canonical}(v) = \text{join}(\text{NFKC}(v).\text{casefold}().\text{split}())$$
- **File / Function:** [`scripts/build_catalogue_graph.py:L35-L45`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L35-L45) in `build()`.
- **Error Handling:** Skipped books increment `skipped` metric; missing authors/subjects increment `isolates` metric.

---

### Stage 2: SQLite Relational Indexing & Feature Extraction
- **Input:** Flushed batch inserts into temporary SQLite database (`books`, `edges`).
- **Processing:** Creates uniqueness constraints and indexes on `books(work_id)`, `books(title_key, work_id)`, `edges(book_id, kind, term)`, and `edges(kind, term, book_id)`. Populates `features` table by grouping edges by `(kind, term)` to compute degrees.
- **Output:** Populated relational schema with initial degree distribution.
- **Algorithm:** SQL aggregation: `INSERT INTO features SELECT kind, term, COUNT(*), 0.0 FROM edges GROUP BY kind, term;`.
- **File / Function:** [`scripts/build_catalogue_graph.py:L46-L51`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L46-L51).

---

### Stage 3: Feature Weighting & Vector Norm Calculation
- **Input:** Degree counts from `features` table and total catalogue book count $N$.
- **Processing:** Computes inverse-degree logarithmic feature weights, assigning higher importance to rare authors and specialized subjects. Computes squared vector Euclidean norm for every book.
- **Output:** Populated `features.weight` and `norms` table.
- **Algorithm:**
  $$\text{weight}(k, t) = W_k \cdot \left(1 + \ln\left(\frac{N + 1}{\text{degree}(k, t) + 1}\right)\right)$$
  $$\text{Norm}(b) = \sum_{(k, t) \in \text{edges}(b)} \text{weight}(k, t)^2$$
- **File / Function:** [`scripts/build_catalogue_graph.py:L54-L62`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L54-L62).

---

### Stage 4: Description Topic NLP Mining (V2 Enrichment)
- **Input:** Book descriptions from catalogue.
- **Processing:** Adjacent n-gram generation (bigrams, trigrams). Stopword filtering via `scikit-learn`. TF-IDF scoring bounded by degree limits ($3 \le \text{degree} \le 0.001 \times N$). Capped at 5 topics per book.
- **Output:** Additional `HAS_TOPIC` edges and enriched feature weights ($W_{\text{topic}} = 0.5$).
- **Algorithm:** Corpus degree-bounded phrase selection:
  $$\text{score}(p) = (1 + \ln(\text{tf}(p))) \cdot \left(1 + \ln\left(\frac{N + 1}{\text{degree}(p) + 1}\right)\right)$$
- **File / Function:** [`knowledge_graph/topics.py:L40-L52`](file:///d:/SDC/LibraryLLM/knowledge_graph/topics.py#L40-L52) and [`scripts/build_kg_topics.py:L60-L83`](file:///d:/SDC/LibraryLLM/scripts/build_kg_topics.py#L60-L83).

---

### Stage 5: Online 2-Hop Traversal & Scoring
- **Input:** Target `work_id`, `limit` (1–50), and authenticated reader exclusion list (borrowed/reserved books).
- **Processing:** Executes SQL query to match candidate books sharing at least one feature with the seed book. Computes cosine similarity scores without sampled neighbor caps. Retrieves exact reason paths between seed and candidate.
- **Output:** Ranked list of recommended books with mathematical reason paths.
- **Algorithm:**
  $$\text{score}(s, c) = \frac{\sum_{f \in \text{shared}} \text{weight}(f)^2}{\sqrt{\text{Norm}(s) \cdot \text{Norm}(c)}}$$
- **File / Function:** [`knowledge_graph/core.py:L60-L107`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L60-L107) in `more_like_this()`.
- **Error Handling:** Raises `KeyError` (404) if book not in graph; raises `HTTPException(409)` if live metadata diverges from snapshot.

---

### Stage 6: Subgraph Transformation & SVG Layout
- **Input:** Backend recommendation and reason paths payload.
- **Processing:** Extracts unique nodes (`seed`, `recommended books`, and intermediate `features`). Computes 3-column coordinate mapping:
  - Seed: $(x=135, y=\text{height}/2)$
  - Features: $(x=450, y=45 + i \cdot \Delta y_{\text{features}})$
  - Books: $(x=765, y=45 + j \cdot \Delta y_{\text{books}})$
- **Output:** Interactive SVG markup with cubic Bezier paths and clickable node pills.
- **File / Function:** [`knowledge_graph/core.py:L108-L116`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L108-L116) and [`frontend/src/components/MetadataGraphCanvas.tsx:L3-L12`](file:///d:/SDC/LibraryLLM/frontend/src/components/MetadataGraphCanvas.tsx#L3-L12).
