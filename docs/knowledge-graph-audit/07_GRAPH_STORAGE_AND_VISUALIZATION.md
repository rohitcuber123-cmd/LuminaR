# 07 — GRAPH STORAGE & FRONTEND VISUALIZATION

## 1. Graph Storage Architecture & Database Integration

LuminaR employs a multi-tiered storage architecture, deliberately separating transient document study graphs, immutable catalogue graphs, and tenant-isolated disk artifacts.

```
+----------------------------------------------------------------------------------------------------+
|                                    LUMINAR GRAPH STORAGE ARCHITECTURE                              |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [SUBSYSTEM A: GLOBAL CATALOGUE GRAPH]                                                             |
|  * Storage Engine: SQLite 3 Database File (`knowledge_graph/data/catalogue.sqlite`)                |
|  * Mode: Strict Read-Only URI (`sqlite3.connect('...?mode=ro', uri=True)`)                         |
|  * Safety Pragma: `PRAGMA query_only=ON; PRAGMA cache_size=-131072;`                               |
|  * Invalidation: MD5/SHA-256 metadata verification against live MongoDB collections                |
|                                                                                                    |
|  [SUBSYSTEM B: DOCUMENT STUDY MODEL]                                                               |
|  * Storage Engine: In-Memory Python Dataclass (`DocumentKnowledgeModel`)                           |
|  * Lifecycle: Ephemeral per user session / RAG document analysis request                           |
|                                                                                                    |
|  [SUBSYSTEM C: TENANT INTELLIGENCE GRAPH]                                                          |
|  * Storage Engine: Content-Addressed JSON Disk Artifacts (`graph.json`)                           |
|  * Location: `local-data/library-intelligence/{library_id}/kg/{generation_id}/`                    |
|  * Validation: Cryptographic `manifest.json` containing SHA-256 checksums of every file           |
|  * In-Memory Caching: LRU `ArtifactCache` retaining at most 3 tenants / 256 MB RAM                 |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

### 1.1 Live Consistency & Stale Cache Detection (Subsystem A)

A common flaw in offline graph recommender systems is serving stale metadata after a book has been updated or removed from the live database. LuminaR implements a strict **fail-closed cache validation guard**:

```python
# backend/routes/knowledge_graph.py:L43-L47
def features_current(snapshot, live):
    if any(set(terms(snapshot[field])) != set(terms(live.get(field))) for field in ['authors', 'subjects']):
        return False
    if 'description_hash' in snapshot:
        return snapshot['description_hash'] == hashlib.sha256(canonical(live.get('description') or '').encode()).hexdigest()
    return True
```

When `/api/experimental/kg/more-like-this` is called:
1. It queries MongoDB for the live book record (`current_books(books_collection, [request.work_id])`).
2. If the book was deleted, it returns `HTTPException(404)`.
3. If the author, subject, or description changed since the graph was built, it returns `HTTPException(409, "This book’s metadata changed. Rebuild the graph before comparing it.")`.
4. It filters the returned recommendations so that **no stale recommendation is ever displayed to the user**.

---

## 2. Frontend Graph Visualization Engine

LuminaR visualizes its graphs using a **pure React + Native SVG engine** (`MetadataGraphCanvas.tsx`), completely eliminating the overhead, bundle size, and layout instability of external libraries like D3 or Cytoscape.

### 2.1 Deterministic Coordinate Calculation

The canvas maps nodes into three distinct vertical columns:
- **Left Column ($x = 135$):** The seed book.
- **Center Column ($x = 450$):** Shared author, subject, and topic features.
- **Right Column ($x = 765$):** Recommended books.

```typescript
// frontend/src/components/MetadataGraphCanvas.tsx:L4-L6
const features = nodes.filter(node => node.kind !== 'book');
const books = nodes.filter(node => node.kind === 'book' && !node.seed);
const height = Math.max(460, features.length * 45 + 70, books.length * 55 + 70);

const position = (node: KGNode) => 
  node.seed 
    ? { x: 135, y: height / 2 }
    : node.kind === 'book' 
      ? { x: 765, y: 45 + books.indexOf(node) * (height - 90) / Math.max(1, books.length - 1) }
      : { x: 450, y: 45 + features.indexOf(node) * (height - 90) / Math.max(1, features.length - 1) };
```

---

### 2.2 Cubic Bezier Edge Rendering

Edges represent the reason bridges connecting books to metadata entities. Rather than straight lines (which overlap and look cluttered), edges are rendered as smooth cubic Bezier curves:

```typescript
// frontend/src/components/MetadataGraphCanvas.tsx:L9
<path 
  key={`${edge.source}:${edge.target}`} 
  d={`M ${a.x} ${a.y} C ${(a.x + b.x) / 2} ${a.y}, ${(a.x + b.x) / 2} ${b.y}, ${b.x} ${b.y}`} 
  fill="none" 
  stroke={focus ? nodeColour(target.kind) : '#d5ddd5'} 
  strokeWidth={focus ? 3 : 1.3} 
  opacity={selected && !focus ? 0.25 : 1}
/>
```

- Control points are set to the horizontal midpoint `(a.x + b.x) / 2`, producing horizontal tangents at both the source and target pins.
- **Focus Highlighting:** When a node is selected, connected edges thicken to `3px` and take on the entity's distinct color, while unrelated edges fade to `25%` opacity.

---

### 2.3 Curated Color Palette & Node Styling

LuminaR adheres to a curated, high-contrast academic palette:

| Node Kind | Hex Color | Visual Meaning | Node Shape |
|---|---|---|---|
| `book` | `#235344` | Deep forest moss green (Library identity) | Rounded rectangle (`rx = 8`) |
| `author` | `#ad663b` | Warm terracotta brown | Pill / capsule (`rx = 17`) |
| `subject` | `#67628c` | Muted slate purple | Pill / capsule (`rx = 17`) |
| `topic` | `#59789b` | Steel blue (Description n-gram) | Pill / capsule (`rx = 17`) |

---

## 3. Interactive Knowledge Exploration Features

The Graph Lab frontend provides rich, interactive exploration capabilities ([`frontend/src/pages/KnowledgeGraphPage.tsx:L74-L101`](file:///d:/SDC/LibraryLLM/frontend/src/pages/KnowledgeGraphPage.tsx#L74-L101)):

1. **Interactive Node Inspector (Side Panel):** Clicking any node highlights its connected reason paths and renders node details in the side panel:
   - For books: Author metadata, direct link to product page, and "Use as starting book" button.
   - For features: Degree in catalogue and all connected titles.
2. **Dynamic Zoom Controls:** Smooth zooming from $0.7\times$ to $1.8\times$ (`ZoomIn`, `ZoomOut` buttons) scaling the SVG viewBox.
3. **Relationship Filtering Toggles:** Checkboxes to dynamically show/hide Authors, Subjects, or Topics.
4. **Instant Traversal Pivot:** Clicking "Use as starting book" on any recommendation instantly pivots the graph, making that book the new seed and re-executing the 2-hop traversal.
5. **Recommender Comparison Mode:** Clicking "Compare with existing recommender" executes a side-by-side benchmark against LuminaR's vector/content recommender, displaying:
   - **List Overlap ($Overlap@K$):** Percentage of common recommendations.
   - **New Graph Candidates:** Number of relevant titles surfaced exclusively by the graph.
   - **Subject Diversity:** Jaccard pairwise distance across subject sets.
