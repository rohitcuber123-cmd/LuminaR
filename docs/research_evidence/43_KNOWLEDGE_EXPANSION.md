# Knowledge Expansion Architecture & Traversal Trace

## 1. Executive Summary

In LuminaR, **Knowledge Expansion** refers to the user-driven workflow where a reader explores connections from a starting book, inspects shared metadata attributes, and pivots to related books across the catalog.

### Technical Classification
When evaluated against formal information retrieval and graph theory taxonomies:
- **It is NOT Semantic Search**: No embedding model (such as BGE or Sentence-BERT) is executed.
- **It is NOT Dense Vector Retrieval**: No vector database, HNSW graph, or dot-product index is queried during graph expansion.
- **It is NOT an Ontological Taxonomy Reasoner**: No RDF reasoning, OWL transitive closure, or subclass inference is performed.
- **It IS Deterministic 2-Hop Meta-Path Traversal with Exact Cosine-TFIDF Scoring**: The expansion executes a 2-hop traversal over an inverted bipartite index (`Book → Feature → Candidate Books`), scores candidates using TF-IDF feature weights, and projects an ego-network subgraph to the client.

---

## 2. End-to-End Knowledge Expansion Trace

```
Reader Interaction (Clicks "Explore full graph", Node, or "Use as starting book")
  │
  ▼
[API Route Dispatch] ────────── POST /api/experimental/kg/more-like-this
  │                             or GET /api/kg/books/{work_id}/more-like-this
  ▼
[Security & Identity] ───────── Validates active JWT; resolves patron user ID
  │
  ▼
[Catalog Freshness Guard] ───── Verifies author/subject/description SHA256 against live MongoDB.
  │                             Raises 409 Conflict if catalog metadata mutated since snapshot.
  ▼
[Inverted Index Traversal] ──── Hop 1: Seed Book (u) ──► Shared Features F_u (edges table)
  │                             Hop 2: Shared Features F_u ──► Candidate Books {v} (edges table)
  ▼
[Cosine-TFIDF Score Compute] ── Score(u,v) = Σ [w(f)²] / sqrt(Norm(u) × Norm(v))
  │                             (Evaluates ALL connected candidates in SQLite)
  ▼
[Hard Exclusions Filter] ────── Filters out books currently ISSUED or RESERVED by caller
  │
  ▼
[Reason Path Assembly] ──────── Extracts exact 2-hop evidence paths with predicates & contributions:
  │                             [Seed Book] ──(AUTHORED_BY/HAS_SUBJECT/HAS_TOPIC)──► [Feature]
  │                             [Feature]   ──(AUTHORED_BY/HAS_SUBJECT/HAS_TOPIC)──► [Candidate Book]
  ▼
[Ego-Network Subgraph] ──────── Builds exploration payload: {nodes, edges, max_reasons=3}
  │
  ▼
[Live Availability Hydration] ─ Enriches candidate cards with live copy counts & shelf locations
  │
  ▼
[Frontend Layout & Render] ──── SVG 3-column coordinate layout with interactive Bezier paths
```

---

## 3. Detailed Step-by-Step Traversal Mechanics

### Step 1: User Entry & Expansion Triggers
Knowledge expansion is initiated from three distinct user touchpoints:
1. **Book Detail Page (`BookDetailPage.tsx`)**:
   - The reader inspects a book and views the `MoreLikeThisSection`.
   - Clicking `"Explore full graph →"` navigates to `/experimental/kg?seed={work_id}`.
2. **Graph Lab Search (`KnowledgeGraphPage.tsx`)**:
   - The reader types a title prefix or enters an exact OpenLibrary `work_id` (e.g. `OL19545719W`).
   - Clicking `"Explore connections"` executes graph expansion for that seed.
3. **In-Graph Reseeding / Pivoting ("Use as starting book")**:
   - While viewing the interactive connection map, the reader clicks any candidate book node.
   - The inspection panel provides a button: `"Use as starting book"`.
   - Clicking this sets `seed = candidate.work_id` and triggers an immediate re-expansion from the new seed book.

### Step 2: Freshness Verification (`features_current`)
Implemented in [`backend/routes/knowledge_graph.py:43-47`](file:///d:/SDC/LibraryLLM/backend/routes/knowledge_graph.py#L43-L47):
- The backend checks if the seed book in MongoDB `books_collection` matches the SQLite snapshot:
  ```python
  def features_current(snapshot, live):
      if any(set(terms(snapshot[f])) != set(terms(live.get(f))) for f in ['authors', 'subjects']):
          return False
      if 'description_hash' in snapshot:
          return snapshot['description_hash'] == hashlib.sha256(canonical(live.get('description') or '').encode()).hexdigest()
      return True
  ```
- If metadata has changed, the API raises `HTTP 409 Conflict: "This book’s metadata changed. Rebuild the graph before comparing it."`. This prevents stale graph recommendations from misrepresenting live catalog facts.

### Step 3: Two-Hop SQL Graph Traversal
Implemented in [`knowledge_graph/core.py:more_like_this()`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L60-L107):
1. **Hop 1 (Seed to Features)**:
   - Retrieves all features linked to the seed book:
     ```sql
     SELECT e.kind, e.term, e.label, f.degree, f.weight
     FROM edges e
     JOIN features f USING(kind, term)
     WHERE e.book_id = :seed_id
     ORDER BY f.degree, e.kind, e.term;
     ```
   - If the seed book has zero author or subject edges, expansion terminates gracefully:
     `{"candidate_count": 0, "reason": "No author or subject links for this book."}`
2. **Hop 2 (Features to Candidate Books)**:
   - Queries the inverted index for all books sharing at least one feature with the seed:
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
   - Notice: **All connected candidates across the 5,000,000-book catalog are evaluated**. There is no truncated random-walk or neighborhood sampling.

### Step 4: Reason Path Construction
For each top candidate $v$, the engine retrieves the exact connecting features and builds verifiable provenance:
```python
paths = db.execute('''
    SELECT a.kind, a.term, a.label AS seed_label, c.label AS candidate_label, f.degree, f.weight
    FROM edges a
    JOIN edges c USING(kind, term)
    JOIN features f USING(kind, term)
    WHERE a.book_id = :seed_id AND c.book_id = :candidate_id
    ORDER BY f.weight DESC, a.kind, a.term
''').fetchall()
```
For each connecting path, it records:
- `nodes`: `[seed_work_id, feature_id, candidate_work_id]`
- `predicates`: `[predicate, predicate]` (e.g. `["AUTHORED_BY", "AUTHORED_BY"]`)
- `catalogue_degree`: Global frequency of that feature
- `importance`: $1 + \ln((N+1)/(d+1))$
- `feature_weight`: $w(f)$
- `contribution`: $\frac{w(f)^2}{\sqrt{\text{Norm}(u) \cdot \text{Norm}(v)}}$
- `provenance`: Exact field name and string value from both books.

### Step 5: Subgraph Ego-Network Generation (`exploration()`)
In [`knowledge_graph/core.py:108-116`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L108-L116):
- Assembles a compact subgraph representation:
  ```python
  def exploration(self, response, max_reasons=3):
      seed = response['seed']
      nodes = {seed['work_id']: dict(id=seed['work_id'], kind='book', label=seed['title'], seed=True)}
      edges = {}
      for book in response['recommendations']:
          nodes[book['work_id']] = dict(id=book['work_id'], kind='book', label=book['title'], seed=False)
          for path in book['reason_paths'][:max_reasons]:
              bridge = path['nodes'][1]
              nodes[bridge] = dict(id=bridge, kind=path['kind'], label=path['label'], seed=False)
              for endpoint in [seed['work_id'], book['work_id']]:
                  edges[endpoint, bridge] = dict(source=endpoint, target=bridge, predicate=path['predicates'][0])
      return {'nodes': list(nodes.values()), 'edges': list(edges.values()), 'reason_paths_per_book_shown': max_reasons}
  ```

---

## 4. Frontend Rendering & Interactive Exploration

Implemented in [`frontend/src/pages/KnowledgeGraphPage.tsx`](file:///d:/SDC/LibraryLLM/frontend/src/pages/KnowledgeGraphPage.tsx):

### 4.1 Visual Graph Layout
The visualization renders an interactive SVG canvas with a 3-column topology:
- **Left Column ($x = 135$)**: Starting Seed Book (Highlighted in forest green `#235344`).
- **Center Column ($x = 450$)**: Bridging Feature Nodes:
  - Authors (`#ad663b`, Terra Cotta)
  - Subjects (`#67628c`, Slate Purple)
  - Topics (`#59789b`, Steel Blue)
- **Right Column ($x = 765$)**: Recommended Candidate Books (`#235344`, Forest Green).

### 4.2 Edge Curvature & Interaction
- Edges are rendered using smooth cubic Bezier curves (`M a.x a.y C ...`).
- **Node Click**:
  - Highlights all incident edges with the node's category color (stroke width 3px).
  - Dims all non-incident edges to opacity $0.25$.
  - Updates the right-hand aside panel with detailed catalogue metadata, link counts, and reason paths.
- **Node Filter Toggles**:
  - Patron can toggle "Authors", "Subjects", and "Other relationships" (Topics) on and off.
  - Toggling recalculates the SVG canvas layout height and vertical node distribution dynamically.

---

## 5. Expansion Traversal vs. Alternative Methods

| Paradigm | Used in LuminaR Expansion? | Evidence / Mechanism |
|---|---|---|
| **Graph Traversal** | **YES** | 2-Hop meta-path traversal across SQLite bipartite edges |
| **TF-IDF Weighting** | **YES** | Rarity weighting $1 + \ln((N+1)/(d+1))$ on each shared feature |
| **Cosine Normalization** | **YES** | Exact vector normalization $\sqrt{\text{Norm}(u) \cdot \text{Norm}(v)}$ |
| **Category Lookup** | **YES (Structured)** | Inverted index lookup on normalized subject labels |
| **Semantic / Vector Search** | **NO** | No sentence-transformers or embeddings used during KG expansion |
| **Graph Neural Networks (GNN)** | **NO** | No node embeddings or message-passing neural networks |
| **Knowledge Base Reasoning** | **NO** | No OWL/RDFS ontology reasoning or SPARQL queries |
| **Collaborative Filtering** | **NO** | User loan/reservation history is only used for exclusion, not scoring |
