# Knowledge Graph Architecture & Implementation Audit

## 1. Executive Summary & Reality Check

LuminaR contains a module named `knowledge_graph/` and an interactive user-facing route at `/experimental/kg` ("Graph Lab").

### Critical Scientific Qualification
**What the LuminaR "Knowledge Graph" Actually Is**:
The implementation is **NOT** a formal semantic web knowledge base, RDF triple store, OWL ontology, or Graph Neural Network (GNN). There is no SPARQL endpoint, no entity resolution linking authors to external knowledge bases (such as Wikidata or VIAF), no taxonomy reasoning (`subClassOf`), and no dense graph embeddings (such as TransE, RotatE, or ComplEx).

Instead, the actual implementation is a **Bipartite Entity-Feature Graph with SQLite Persistence and Exact Cosine-TFIDF 2-Hop Path Retrieval**:
- Bipartite structure: Books connect exclusively to Feature Nodes (Authors, Subjects, Topics); books never connect directly to other books.
- Recommendation mechanism: 2-hop meta-path traversal (`Book → Feature → Book`) weighted by Inverse Document Frequency (IDF) and cosine vector normalization.
- Visualization: Dynamic client-side SVG ego-network rendering with cubic Bezier edges and provenance disclosures.

---

## 2. Graph Schema & Structural Components

```
                ┌───────────────────────────────────────┐
                │             FEATURE NODES             │
                ├───────────────────────────────────────┤
                │  Author (NFKC Normalized String)     │
                │  Subject (NFKC Normalized Label)     │
                │  Topic (Adjacent 2/3-gram Phrase)     │
                └───────▲───────────────────────▲───────┘
                        │                       │
      predicate:        │                       │ predicate:
      AUTHORED_BY /     │                       │ AUTHORED_BY /
      HAS_SUBJECT /     │                       │ HAS_SUBJECT /
      HAS_TOPIC         │                       │ HAS_TOPIC
                        │                       │
                ┌───────┴──────┐        ┌───────┴──────┐
                │  SEED BOOK   │        │CANDIDATE BOOK│
                │  (work_id)   │        │  (work_id)   │
                └──────────────┘        └──────────────┘
                       2-Hop Meta-Path Traversal
```

### 2.1 Node Types

| Node Type | Internal Identifier | Source Field | Example | Identity Resolution |
|---|---|---|---|---|
| **`book`** | `work_id` (string) | MongoDB `work_id` | `"OL19545719W"` | OpenLibrary Work ID |
| **`author`** | `author:<sha256(canonical_name)>` | Book `authors` field | `"Arthur Conan Doyle"` | **None**. Surface text matching only |
| **`subject`** | `subject:<sha256(canonical_label)>` | Book `subjects` field | `"Detective and mystery stories"` | **None**. Surface text matching only |
| **`topic`** | `topic:<sha256(canonical_phrase)>` | Book `description` field | `"machine learning"` | Corpus-filtered 2/3-gram phrases |

### 2.2 Edge Types & Predicates
Defined in [`knowledge_graph/relations.py`](file:///d:/SDC/LibraryLLM/knowledge_graph/relations.py#L1-L9):

| Edge Kind | Predicate String | Target Book Field | Relation Weight $w_{\text{rel}}$ |
|---|---|---|---|
| `author` | `AUTHORED_BY` | `authors` | **2.0** |
| `subject` | `HAS_SUBJECT` | `subjects` | **1.0** |
| `topic` | `HAS_TOPIC` | `description` | **0.5** |

---

## 3. Storage & Persistence Architecture

The graph is persisted as a single read-only relational SQLite database located at:
`d:\SDC\LibraryLLM\knowledge_graph\data\catalogue.sqlite` (File Size: **5.87 GB**).

### 3.1 Relational Schema

```sql
-- 1. Book Entities
CREATE TABLE books (
    id INTEGER PRIMARY KEY,
    work_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    title_key TEXT NOT NULL, -- Normalized prefix for fast B-tree range queries
    authors TEXT NOT NULL,   -- JSON array
    subjects TEXT NOT NULL,  -- JSON array
    description_hash TEXT    -- SHA256 of canonical description
);
CREATE INDEX idx_books_title_key ON books(title_key);

-- 2. Feature Dictionary
CREATE TABLE features (
    kind TEXT NOT NULL,      -- 'author' | 'subject' | 'topic'
    term TEXT NOT NULL,      -- Canonical NFKC term string
    degree INTEGER NOT NULL, -- Global catalogue frequency d
    weight REAL NOT NULL,    -- w(f) = w_rel * (1 + ln((N+1)/(d+1)))
    PRIMARY KEY (kind, term)
);

-- 3. Bipartite Edges
CREATE TABLE edges (
    book_id INTEGER NOT NULL REFERENCES books(id),
    kind TEXT NOT NULL,
    term TEXT NOT NULL,
    label TEXT NOT NULL,     -- Raw presentation label
    source_hash TEXT,        -- SHA256 of source text (for topics)
    FOREIGN KEY (kind, term) REFERENCES features(kind, term)
);
CREATE INDEX idx_edges_book ON edges(book_id);
CREATE INDEX idx_edges_feature ON edges(kind, term);

-- 4. Precomputed Book Euclidean Norms
CREATE TABLE norms (
    book_id INTEGER PRIMARY KEY REFERENCES books(id),
    value REAL NOT NULL      -- \sum_{f \in F_u} w(f)^2
);

-- 5. Build Metadata
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL      -- JSON string containing summary counts & version
);
```

### 3.2 Concurrency & Runtime Safety
In [`knowledge_graph/core.py:connect()`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L30-L38):
- SQLite is opened strictly with URI read-only flag: `?mode=ro`.
- Connection enforces `PRAGMA query_only = ON`.
- No writes, locks, or schema mutations occur during runtime API execution.

---

## 4. Construction & Topic Extraction Algorithms

Built offline via [`scripts/build_catalogue_graph.py`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py) across 5,000,000 catalog documents:

### 4.1 Canonicalization Rules
1. Unicode NFKC normalization: `unicodedata.normalize('NFKC', value)`.
2. Case folding: `.casefold()`.
3. Whitespace collapse: `' '.join(...split())`.
4. Delimiter splitting: Only pipe (`|`) splits multiple authors or subjects; internal commas (e.g. `"Doyle, Arthur Conan"`) are strictly preserved.

### 4.2 Description Topic Extraction (`knowledge_graph/topics.py`)
Deterministic phrase extraction policy (`TOPIC_POLICY`):
- Token matching: `\b[^\W\d_]{3,40}\b` across up to 512 description tokens.
- Stop words: English stop words + 23 library-specific stop words (`book`, `edition`, `publisher`, `isbn`, etc.).
- Candidate n-grams: Contiguous 2-grams and 3-grams with no intervening punctuation.
- TF-IDF Scoring Formula:
  $$\text{Score}(p) = \left(1 + \ln(\text{tf}(p))\right) \cdot \left(1 + \ln\frac{N + 1}{\text{df}(p) + 1}\right)$$
- Frequency bounds:
  $$\text{min\_degree} = 3 \le \text{df}(p) \le \max\left(3, \lfloor N \times 0.001 \rfloor\right)$$
- Substring non-redundancy: If phrase $A$ is a substring of phrase $B$, the lower-ranked phrase is discarded.
- Maximum topics per book: **5**.

---

## 5. Scoring & Traversal Mathematics

### 5.1 Exact Cosine Similarity over TF-IDF Feature Vectors
Feature importance weight:
$$w(f) = w_{\text{rel}}(\text{kind}) \cdot \left(1 + \ln\frac{N + 1}{\text{degree}(f) + 1}\right)$$

Book feature vector Euclidean norm:
$$\text{Norm}(u) = \sum_{f \in F_u} w(f)^2$$

Cosine similarity between Seed Book $u$ and Candidate Book $v$:
$$\text{Score}(u, v) = \frac{\sum_{f \in F_u \cap F_v} w(f)^2}{\sqrt{\text{Norm}(u) \cdot \text{Norm}(v)}}$$

Implemented directly in SQLite SQL ([`knowledge_graph/core.py:70-75`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L70-L75)):
```sql
SELECT e.book_id, SUM(f.weight * f.weight) / SQRT(n.value * :seed_norm) AS score
FROM edges e
JOIN features f USING(kind, term)
JOIN norms n ON n.book_id = e.book_id
WHERE (e.kind, e.term) IN (SELECT kind, term FROM edges WHERE book_id = :seed_id)
  AND e.book_id != :seed_id
GROUP BY e.book_id
ORDER BY score DESC, e.book_id;
```

### 5.2 Deterministic 2-Hop Reason Paths
For every candidate in the top-$k$, the system retrieves all shared intermediate feature nodes:
$$\text{Path: } \text{Seed } (u) \xrightarrow{\text{pred}} \text{Feature } (f) \xrightarrow{\text{pred}} \text{Candidate } (v)$$

Each path includes an exact mathematical contribution:
$$\text{Contribution}(f) = \frac{w(f)^2}{\sqrt{\text{Norm}(u) \cdot \text{Norm}(v)}}$$
$$\sum_{f \in F_u \cap F_v} \text{Contribution}(f) = \text{Score}(u, v)$$

---

## 6. Frontend Graph Rendering & Exploration Subgraph

### 6.1 Subgraph Generation (`graph.exploration()`)
The backend packages an ego-network containing:
- Seed node: `kind: 'book'`, `seed: true`.
- Recommendation nodes: `kind: 'book'`, `seed: false`.
- Bridge feature nodes: `kind: 'author' | 'subject' | 'topic'`, `label: f.label`.
- Edge list: Linking endpoints to bridge features with predicates.
- Display limit: Strongest **3 reason paths** per book displayed on the map; remaining paths available in expandable details.

### 6.2 SVG Visualization (`KnowledgeGraphPage.tsx`)
Rendered in pure React SVG without heavyweight graph layout libraries (e.g. D3-force or Cytoscape):
- **3-Column Coordinate Layout**:
  - Seed Book: $x = 135, y = \text{height} / 2$ (Dark Green `#235344`)
  - Intermediate Features: $x = 450, y = 45 + i \times \Delta y$
    - Authors: Orange `#ad663b`
    - Subjects: Purple `#67628c`
    - Topics: Blue `#59789b`
  - Candidate Books: $x = 765, y = 45 + j \times \Delta y$ (Dark Green `#235344`)
- **Cubic Bezier Curves**:
  $$d = \text{"M } a.x\ a.y \text{ C } \frac{a.x+b.x}{2}\ a.y,\ \frac{a.x+b.x}{2}\ b.y,\ b.x\ b.y\text{"}$$
- **Interactivity**:
  - Node selection highlights connected paths and dims irrelevant edges.
  - Inspection aside panel displays catalogue provenance and degree counts.
  - Zoom controls ($0.7\times$ to $1.8\times$).
  - Category toggles for Authors, Subjects, and Topics.

---

## 7. Knowledge Graph Empirical Metrics (5M Book Snapshot)

From official build metadata (`knowledge_graph/README.md` and `reports/knowledge_graph_final.md`):

| Metric | Measured Value |
|---|---|
| Total Books in Graph | **5,000,000** |
| Author Feature Nodes | **2,454,492** |
| Subject Feature Nodes | **975,785** |
| Total Bipartite Edges | **29,406,707** |
| Books Missing Authors | 60,151 (1.20%) |
| Books Missing Subjects | 257,541 (5.15%) |
| Isolated Books (Zero Links) | 1,211 (0.024%) |
| Snapshot File Size | 5.87 GB (SQLite) |
| Offline Build Time | 882.81 seconds (~14.7 minutes) |
| Warm Per-Seed Latency (Median) | 289.25 ms |
| Status of Hybrid KG4 Integration | **Deferred** (due to -0.0572 subject diversity delta) |
