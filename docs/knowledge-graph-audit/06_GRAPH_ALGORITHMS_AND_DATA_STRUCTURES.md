# 06 — GRAPH ALGORITHMS & DATA STRUCTURES

## 1. Graph Data Structures in Memory & Storage

LuminaR employs purpose-built, indexed graph data structures optimized for read-only traversal and sub-millisecond execution.

### 1.1 Relational Bipartite Adjacency Tables (Subsystem A)

Rather than storing an in-memory pointer graph or an expensive graph DBMS, the global catalogue graph is structured across four normalized tables in SQLite ([`scripts/build_catalogue_graph.py:L25-L62`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L25-L62)):

```sql
-- 1. Entity Nodes Table
CREATE TABLE books(
    id INTEGER PRIMARY KEY,
    work_id TEXT NOT NULL,
    title TEXT NOT NULL,
    title_key TEXT NOT NULL,
    authors TEXT NOT NULL,
    subjects TEXT NOT NULL
);

-- 2. Adjacency Edges Table (Forward & Inverted Graph)
CREATE TABLE edges(
    book_id INTEGER NOT NULL,
    kind TEXT NOT NULL,
    term TEXT NOT NULL,
    label TEXT NOT NULL
);

-- 3. Feature Nodes & Precomputed Degree/Weights
CREATE TABLE features(
    kind TEXT,
    term TEXT,
    degree INTEGER,
    weight REAL,
    PRIMARY KEY(kind, term)
);

-- 4. Precomputed Euclidean Vector Norms
CREATE TABLE norms(
    book_id INTEGER PRIMARY KEY,
    value REAL NOT NULL
);
```

#### Indexing Strategy:
- `CREATE UNIQUE INDEX books_work_id ON books(work_id);` $\to O(1)$ seed book lookup.
- `CREATE INDEX books_title ON books(title_key, work_id);` $\to O(\log B)$ prefix search.
- `CREATE INDEX edges_book ON edges(book_id, kind, term);` $\to O(\text{deg}(b))$ 1-hop forward traversal from a book to its features.
- `CREATE INDEX edges_feature ON edges(kind, term, book_id);` $\to O(\text{deg}(f))$ 1-hop backward traversal from a feature to candidate books.

---

## 2. Core Graph Algorithms

### 2.1 Two-Hop Weighted Cosine Traversal Algorithm

The core discovery engine in `CatalogueGraph.more_like_this()` executes a deterministic 2-hop path traversal over the bipartite network:

$$\text{Seed Book } (s) \xrightarrow{1\text{-hop forward}} \text{Features } (F_s) \xrightarrow{1\text{-hop backward}} \text{Candidate Books } (C)$$

#### Exact SQL Execution Implementation:
```python
# knowledge_graph/core.py:L70-L75
score_query = '''
    SELECT e.book_id, SUM(f.weight * f.weight) / SQRT(n.value * ?) AS score
    FROM edges e
    JOIN features f USING(kind, term)
    JOIN norms n ON n.book_id = e.book_id
    WHERE (e.kind, e.term) IN (
        SELECT kind, term FROM edges WHERE book_id = ?
    ) AND e.book_id != ?
    GROUP BY e.book_id
    ORDER BY score DESC, e.book_id
'''
norm = db.execute('SELECT value FROM norms WHERE book_id=?', (seed['id'],)).fetchone()[0]
cursor = db.execute(score_query, (norm, seed['id'], seed['id']))
```

#### Pseudocode:
```text
Algorithm: TwoHopWeightedCosineRecommendation
Input: seed_id, limit, excluded_set
Output: ranked_recommendations, reason_paths

1. Retrieve seed_norm = norms[seed_id]
2. seed_features = SELECT kind, term FROM edges WHERE book_id = seed_id
3. If seed_features is empty: return []
4. Execute SQL join:
     For every candidate c != seed sharing feature f in seed_features:
         shared_weight_sum[c] += weight[f]^2
5. For each candidate c in descending order of (shared_weight_sum[c] / sqrt(seed_norm * norms[c])):
     If c.work_id in excluded_set: continue
     If len(recommendations) >= limit: break
     
     // Retrieve exact multi-hop evidence
     paths = SELECT kind, term, weight, degree FROM edges(seed) JOIN edges(c) USING (kind, term)
     For path in paths:
         contribution = path.weight^2 / sqrt(seed_norm * norms[c])
         reason_paths.append(path with provenance and contribution)
         
     recommendations.append(candidate with score and reason_paths)
6. Return recommendations
```

---

### 2.2 Subgraph Construction Algorithm (`exploration`)

To avoid generating dense, unreadable "hairballs", `CatalogueGraph.exploration()` extracts a clean, bounded subgraph containing only the seed, top recommended books, and their strongest 3 bridge nodes ([`knowledge_graph/core.py:L108-L116`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L108-L116)):

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

### 2.3 Maximal Marginal Relevance (MMR) Concept Selection (Subsystem B)

In Subsystem B ([`rag/services/document_knowledge.py:L380-L404`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L380-L404)), concept diversity is maximized using a bounded MMR greedy selection:

$$\text{next\_concept} = \arg\max_{c_i \in \text{Candidates} \setminus S} \left[ \text{Score}(c_i) - 2.2 \cdot \max_{c_j \in S} \text{Sim}(\mathbf{v}_i, \mathbf{v}_j) \right]$$

- **Candidate Pool:** Top 192 scored concepts (`MAX_EMBEDDINGS = 192`).
- **Target Selection:** Bounded between 12 and 30 concepts based on document page count ($N_{\text{pages}} \le 4 \implies 12; \le 20 \implies 20; > 20 \implies 30$).
- **Suppression Condition:** If $\text{Sim}(\mathbf{v}_i, \mathbf{v}_j) \ge 0.90$ and explanation texts match with $\ge 90\%$ string similarity, candidate $c_i$ is suppressed.

---

## 3. Computational Complexity Analysis

| Stage / Algorithm | Operation | Time Complexity | Space Complexity | Notes |
|---|---|---|---|---|
| **Graph Construction** | Streaming books & edges | $O(B \cdot F_b)$ | $O(B \cdot F_b)$ | $B$: book count, $F_b$: features per book ($\approx 4$) |
| **Feature Degree & Norms** | SQL Group By & Analyze | $O(E \log E)$ | $O(E)$ | $E$: total edges in catalogue |
| **Topic Phrase Extraction** | N-gram scanning & TF-IDF | $O(B \cdot L_d)$ | $O(V_{\text{topics}})$ | $L_d$: description length ($\le 512$ tokens) |
| **2-Hop Online Traversal** | SQL join on indexed features | $O(|F_{\text{seed}}| \cdot \overline{\text{deg}}(f))$ | $O(|C_{\text{candidates}}|)$ | Explores only connected candidates; skips full matrix |
| **Reason Path Generation** | Path joins for top-$K$ books | $O(K \cdot |F_{\text{seed}} \cap F_{\text{candidate}}|)$ | $O(K \cdot M)$ | $K \le 50$, $M \le 3$ reason paths |
| **Frontend Layout** | 3-Column Coordinate Mapping | $O(V_{\text{subgraph}} + E_{\text{subgraph}})$ | $O(V_{\text{subgraph}})$ | Linear pass over bounded nodes ($< 40$ nodes) |

### Proof of Scalability:
Because the query joins `edges` against `edges` on indexed `(kind, term)` columns, it examines **only** the neighbors of the seed book's features. The runtime is proportional to the degree of shared features, **completely avoiding $O(B^2)$ full-catalogue pairwise comparisons**.
