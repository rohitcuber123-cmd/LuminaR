# 05 — NODE & RELATIONSHIP GENERATION

## 1. Node Generation & Data Schemas

LuminaR defines formal, strongly-typed node representations across each of its graph implementations.

### 1.1 Subsystem A: Catalogue Graph Node Model

In Subsystem A ([`knowledge_graph/core.py:L108-L116`](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L108-L116)), the exploration subgraph constructs two categories of nodes:

1. **Book Nodes:** Represent bibliographic volumes in the catalogue.
   - **ID Generation:** Native work ID (`work_id`, e.g., `"OL100234W"`).
   - **Fields:** `id`, `kind: "book"`, `label: title`, `seed: boolean`.
2. **Feature Bridge Nodes:** Represent shared metadata attributes connecting books.
   - **ID Generation:** Deterministic SHA-256 hash prefix:
     ```python
     # knowledge_graph/core.py:L24
     def feature_id(kind, term):
         return kind + ':' + hashlib.sha256(term.encode('utf-8')).hexdigest()
     ```
   - **Kinds:** `"author"`, `"subject"`, `"topic"`.
   - **Fields:** `id`, `kind: "author" | "subject" | "topic"`, `label: string`, `seed: false`.

#### Verified JSON Payload Example (Subsystem A):
```json
{
  "nodes": [
    {
      "id": "OL100234W",
      "kind": "book",
      "label": "The Art of Computer Programming",
      "seed": true
    },
    {
      "id": "author:9f83c18b76e10b14...",
      "kind": "author",
      "label": "Knuth, Donald E.",
      "seed": false
    },
    {
      "id": "subject:3c88a4e1d6b081fa...",
      "kind": "subject",
      "label": "Algorithms",
      "seed": false
    },
    {
      "id": "OL892110W",
      "kind": "book",
      "label": "Introduction to Algorithms",
      "seed": false
    }
  ]
}
```

---

### 1.2 Subsystem B: Document Knowledge Model Nodes

In the document study graph ([`rag/services/document_knowledge.py:L516-L547`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L516-L547)), nodes form a 4-tier pedagogical hierarchy:

| Node Type | ID Format | Label Content | Provenance Retained |
|---|---|---|---|
| `document` | `"document"` | Title of uploaded document | Root anchor |
| `chapter` / `section` | `group_{sha256[:16]}` | Chapter or section title | Chunk IDs, page range |
| `concept` | `concept_{sha256[:16]}` | Cleaned concept label (e.g., "Virtual Memory") | Source chunks, pages, explanation snippet |
| `evidence` | `relation_{sha256[:16]}` | Target answer text (e.g., "a memory management technique") | Source excerpt, unit ID |

---

### 1.3 Subsystem C: Tenant Intelligence Graph Nodes

In the tenant-scoped graph ([`backend/services/library_intelligence_artifacts.py:L64-L77`](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py#L64-L77)):
- **Book Node:** `id: "book:" + library_book_id`, `type: "Book"`, `label: title`.
- **Author Node:** `id: "author:" + sha256(canonical(author))`, `type: "Author"`.
- **Subject Node:** `id: "subject:" + sha256(canonical(subject))`, `type: "Subject"`.
- **Classification Node:** `id: "classification:" + sha256(canonical(code))`, `type: "Classification"`.

---

## 2. Relationship & Edge Extraction

### 2.1 Subsystem A: 2-Hop Deterministic Bibliographic Relations

In the global catalogue, edges connect books directly to feature nodes. Two books become related if they co-connect through a common feature node ($\text{Book}_A \to \text{Feature} \leftarrow \text{Book}_B$).

| Relation Predicate | Source Node | Target Node | Weight Multiplier ($W_k$) | Inverse Rarity Formulation |
|---|---|---|---|---|
| `AUTHORED_BY` | `Book` | `Author` | $2.0$ | $2.0 \cdot \left(1 + \ln\left(\frac{N + 1}{\text{degree} + 1}\right)\right)$ |
| `HAS_SUBJECT` | `Book` | `Subject` | $1.0$ | $1.0 \cdot \left(1 + \ln\left(\frac{N + 1}{\text{degree} + 1}\right)\right)$ |
| `HAS_TOPIC` | `Book` | `Topic` | $0.5$ | $0.5 \cdot \left(1 + \ln\left(\frac{N + 1}{\text{degree} + 1}\right)\right)$ |

#### Mathematical Contribution of Reason Paths:
Every recommendation is accompanied by an array of verifiable `reason_paths`. Each reason path represents a 2-hop bridge:
$$\text{Path} = [s, f, c]$$
Where $s$ is the seed book, $f$ is the bridge feature, and $c$ is the candidate book. The exact numerical contribution of path $p$ to the cosine similarity score is:
$$\text{contribution}(p) = \frac{\text{weight}(f)^2}{\sqrt{\text{Norm}(s) \cdot \text{Norm}(c)}}$$

Crucially, **the sum of all reason path contributions equals the overall book recommendation score exactly**:
$$\sum_{p \in \text{Paths}(s, c)} \text{contribution}(p) = \text{score}(s, c)$$
Verified in unit tests: [`tests/test_knowledge_graph.py:L41`](file:///d:/SDC/LibraryLLM/tests/test_knowledge_graph.py#L41).

---

### 2.2 Subsystem B: Syntactic Copula Edge Extraction

In the document knowledge module ([`rag/services/document_knowledge.py:L426-L434`](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L426-L434)), edges represent syntactic relations extracted from text chunks:

```python
relation_type = {
    'is used for': 'USED_FOR',
    'consists of': 'CONTAINS',
    'means': 'DEFINED_AS',
    'refers to': 'DEFINED_AS',
    'is defined as': 'DEFINED_AS',
    'is': 'DEFINED_AS',
    'are': 'DEFINED_AS',
    'has step': 'HAS_STEP'
}.get(fact['relation'])
if fact['relation'] in {'is', 'are'} and not fact['definitionEvidence']:
    relation_type = 'DESCRIBED_AS'
```

- **Direction:** Directed edge from `concept.id` $\to$ `evidence.id`.
- **Confidence:** $0.95$ for verified definitional statements; $0.78$ for contextual descriptive statements.
- **Structural Edges:** `source organization` (`document` $\to$ `group`) and `document topic` (`group` $\to$ `concept`).

---

## 3. Scientific Classification: Knowledge Graph vs Concept Network

During project reviews and university viva examinations, examiners frequently ask:
> *"Is this a true Knowledge Graph or simply a concept co-occurrence network?"*

### 3.1 Precise Technical Classification

LuminaR's graph subsystems must be scientifically classified as follows:

1. **Subsystem A is a Typed Bipartite Entity-Association Graph with Deterministic 2-Hop Reason Paths.**
   - It is **not** an open-domain Subject-Predicate-Object (SPO) knowledge base (like DBpedia or Freebase), because books are not linked by arbitrary semantic predicates (such as `bornIn`, `marriedTo`, or `inventedBy`).
   - Instead, it operates over a closed schema of typed metadata entities (`Book`, `Author`, `Subject`, `Topic`) connected by formal predicates (`AUTHORED_BY`, `HAS_SUBJECT`, `HAS_TOPIC`).
   - It is **far superior to an unweighted co-occurrence graph** because edges are weighted by logarithmic feature rarity and cosine-normalized to produce mathematically explainable reasoning paths.

2. **Subsystem B is a Syntactic Copula Concept Network.**
   - Nodes represent extracted domain concepts and evidence spans.
   - Edges represent typed copula predicates (`DEFINED_AS`, `CONTAINS`, `USED_FOR`, `HAS_STEP`).
   - It provides structural provenance directly to PDF chunks and page numbers.

### 3.2 Reviewer-Ready Defense Answer
> *"LuminaR does not claim to implement an open-world factual RDF triple store. In Subsystem A, we implement a typed bipartite metadata knowledge graph on SQLite where books and metadata entities form a heterogeneous network. Recommendations are computed via 2-hop traversals where every path provides an exact, mathematically additive contribution to the cosine similarity score. In Subsystem B, we construct a closed-world concept network from uploaded documents using rule-based syntactic copula extraction and MMR embedding deduplication. Both systems are 100% deterministic, explainable, and run without LLM hallucination."*
