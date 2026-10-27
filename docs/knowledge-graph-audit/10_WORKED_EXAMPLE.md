# 10 — COMPLETE WORKED END-TO-END EXAMPLE

## 1. Concrete End-to-End Walkthrough

To demonstrate the exact algorithmic behavior of LuminaR's Knowledge Graph, we trace a concrete worked example from raw bibliographic input to final SVG visualization.

---

### Step 1: Raw Input Bibliographic Records
Suppose MongoDB contains the following three books in `books_collection`:

```json
[
  {
    "work_id": "OL100W",
    "title": "Introduction to Algorithms",
    "authors": "Cormen, Thomas H. | Leiserson, Charles E. | Rivest, Ronald L.",
    "subjects": "Algorithms | Computer Science | Data Structures",
    "description": "Comprehensive introduction to the modern study of computer algorithms."
  },
  {
    "work_id": "OL200W",
    "title": "Algorithms in C++",
    "authors": "Sedgewick, Robert",
    "subjects": "Algorithms | C++ (Computer program language) | Data Structures",
    "description": "Practical guide to data structures and algorithms in modern programming."
  },
  {
    "work_id": "OL300W",
    "title": "Cryptography and Network Security",
    "authors": "Stallings, William",
    "subjects": "Computer Networks | Cryptography | Computer Science",
    "description": "Principles and practice of cryptography and network protocol security."
  }
]
```

---

### Step 2: Metadata Preprocessing & Canonicalization
**Executed Function:** [`scripts/build_catalogue_graph.py:L35-L42`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L35-L42) invoking `canonical()` and `terms()` in `knowledge_graph/core.py`.

- Pipe strings are parsed and mapped to normalized keys:
  - `"Cormen, Thomas H."` $\to$ `canonical: "cormen, thomas h."`, `label: "Cormen, Thomas H."`
  - `"Algorithms"` $\to$ `canonical: "algorithms"`, `label: "Algorithms"`
  - `"Data Structures"` $\to$ `canonical: "data structures"`, `label: "Data Structures"`
  - `"Computer Science"` $\to$ `canonical: "computer science"`, `label: "Computer Science"`

---

### Step 3: Feature Table & Degree Calculation
**Executed Function:** [`scripts/build_catalogue_graph.py:L48-L51`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L48-L51).

Assume a total catalogue size of $N = 1,000$ books:

| Feature Kind | Normalized Term | In-Catalogue Degree | Base Weight Multiplier ($W_k$) |
|---|---|---|---|
| `subject` | `algorithms` | $15$ | $1.0$ |
| `subject` | `data structures` | $10$ | $1.0$ |
| `subject` | `computer science` | $120$ | $1.0$ |
| `author` | `cormen, thomas h.` | $3$ | $2.0$ |

---

### Step 4: Weighting & Euclidean Norm Computation
**Executed Function:** [`scripts/build_catalogue_graph.py:L54-L62`](file:///d:/SDC/LibraryLLM/scripts/build_catalogue_graph.py#L54-L62).

Formula: $\text{weight} = W_k \cdot \left(1 + \ln\left(\frac{N + 1}{\text{degree} + 1}\right)\right)$

1. **Feature Weights:**
   - $\text{weight}(\text{algorithms}) = 1.0 \cdot (1 + \ln(1001 / 16)) = 1.0 \cdot (1 + 4.136) = \mathbf{5.136}$
   - $\text{weight}(\text{data structures}) = 1.0 \cdot (1 + \ln(1001 / 11)) = 1.0 \cdot (1 + 4.511) = \mathbf{5.511}$
   - $\text{weight}(\text{computer science}) = 1.0 \cdot (1 + \ln(1001 / 121)) = 1.0 \cdot (1 + 2.113) = \mathbf{3.113}$

2. **Euclidean Vector Norms:**
   Formula: $\text{Norm}(b) = \sum \text{weight}(f)^2$
   - $\text{Norm}(\text{OL100W}) = 5.136^2 + 5.511^2 + 3.113^2 + \dots = 26.379 + 30.371 + 9.691 + 40.0 = \mathbf{106.441}$
   - $\text{Norm}(\text{OL200W}) = 5.136^2 + 5.511^2 + \dots = 26.379 + 30.371 + 25.0 = \mathbf{81.750}$

---

### Step 5: Online 2-Hop Traversal Query
**Executed Function:** [`knowledge_graph/core.py:L60-L107`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L60-L107) in `CatalogueGraph.more_like_this("OL100W", limit=10)`.

1. **Shared Features between OL100W and OL200W:**
   - `subject:algorithms` (weight = 5.136)
   - `subject:data structures` (weight = 5.511)
2. **Numerator (Dot Product of Shared Weights):**
   $$\sum_{f \in \text{shared}} \text{weight}(f)^2 = 5.136^2 + 5.511^2 = 26.379 + 30.371 = \mathbf{56.750}$$
3. **Denominator:**
   $$\sqrt{\text{Norm}(\text{OL100W}) \cdot \text{Norm}(\text{OL200W})} = \sqrt{106.441 \cdot 81.750} = \sqrt{8701.55} = \mathbf{93.282}$$
4. **Final Cosine Similarity Score:**
   $$\text{score}(\text{OL100W}, \text{OL200W}) = \frac{56.750}{93.282} = \mathbf{0.608}$$

5. **Exact Path Contributions:**
   - Contribution of `Algorithms`: $\frac{26.379}{93.282} = \mathbf{0.2827}$
   - Contribution of `Data Structures`: $\frac{30.371}{93.282} = \mathbf{0.3255}$
   - Sum of contributions: $0.2827 + 0.3255 = \mathbf{0.6082}$ (Matches score exactly!)

---

### Step 6: Serialized API Response Payload
**Returned from:** [`backend/routes/knowledge_graph.py:L78`](file:///d:/SDC/LibraryLLM/backend/routes/knowledge_graph.py#L78).

```json
{
  "seed": {
    "work_id": "OL100W",
    "title": "Introduction to Algorithms",
    "authors": ["Cormen, Thomas H.", "Leiserson, Charles E.", "Rivest, Ronald L."],
    "subjects": ["Algorithms", "Computer Science", "Data Structures"]
  },
  "recommendations": [
    {
      "work_id": "OL200W",
      "title": "Algorithms in C++",
      "authors": ["Sedgewick, Robert"],
      "subjects": ["Algorithms", "C++ (Computer program language)", "Data Structures"],
      "score": 0.6082,
      "reason_paths": [
        {
          "nodes": ["OL100W", "subject:e3b0c442...", "OL200W"],
          "kind": "subject",
          "label": "Data Structures",
          "predicates": ["HAS_SUBJECT", "HAS_SUBJECT"],
          "catalogue_degree": 10,
          "contribution": 0.3255,
          "provenance": [
            {"work_id": "OL100W", "field": "subjects", "value": "Data Structures"},
            {"work_id": "OL200W", "field": "subjects", "value": "Data Structures"}
          ]
        },
        {
          "nodes": ["OL100W", "subject:a2f1b88c...", "OL200W"],
          "kind": "subject",
          "label": "Algorithms",
          "predicates": ["HAS_SUBJECT", "HAS_SUBJECT"],
          "catalogue_degree": 15,
          "contribution": 0.2827,
          "provenance": [
            {"work_id": "OL100W", "field": "subjects", "value": "Algorithms"},
            {"work_id": "OL200W", "field": "subjects", "value": "Algorithms"}
          ]
        }
      ]
    }
  ],
  "exploration": {
    "nodes": [
      {"id": "OL100W", "kind": "book", "label": "Introduction to Algorithms", "seed": true},
      {"id": "OL200W", "kind": "book", "label": "Algorithms in C++", "seed": false},
      {"id": "subject:e3b0c442...", "kind": "subject", "label": "Data Structures", "seed": false},
      {"id": "subject:a2f1b88c...", "kind": "subject", "label": "Algorithms", "seed": false}
    ],
    "edges": [
      {"source": "OL100W", "target": "subject:e3b0c442...", "predicate": "HAS_SUBJECT"},
      {"source": "OL200W", "target": "subject:e3b0c442...", "predicate": "HAS_SUBJECT"},
      {"source": "OL100W", "target": "subject:a2f1b88c...", "predicate": "HAS_SUBJECT"},
      {"source": "OL200W", "target": "subject:a2f1b88c...", "predicate": "HAS_SUBJECT"}
    ],
    "reason_paths_per_book_shown": 3
  }
}
```

---

### Step 7: Frontend SVG Coordinate Calculation & Rendering
**Executed Function:** [`frontend/src/components/MetadataGraphCanvas.tsx:L3-L12`](file:///d:/SDC/LibraryLLM/frontend/src/components/MetadataGraphCanvas.tsx#L3-L12).

1. **Canvas Dimension:** $\text{height} = \max(460, 2 \cdot 45 + 70, 1 \cdot 55 + 70) = \mathbf{460\text{ px}}$.
2. **Node Positions:**
   - Seed `OL100W`: $(x = 135, y = 230)$
   - Feature `Data Structures`: $(x = 450, y = 45)$
   - Feature `Algorithms`: $(x = 450, y = 45 + 370 = 415)$
   - Candidate `OL200W`: $(x = 765, y = 45)$
3. **Cubic Bezier Path (Seed $\to$ Data Structures):**
   - Source: $(135, 230)$, Target: $(450, 45)$
   - Control points: $((135+450)/2, 230) = (292.5, 230)$ and $(292.5, 45)$
   - SVG Path: `M 135 230 C 292.5 230, 292.5 45, 450 45`
