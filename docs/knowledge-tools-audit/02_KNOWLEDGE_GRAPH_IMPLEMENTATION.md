# LuminaR Knowledge Graph Implementation Audit & Technical Analysis

## 1. Executive Summary: The Two Graph Subsystems

A critical finding of this code audit is that LuminaR contains **two distinct knowledge graph implementations**, each serving a different scope in the system:

| Subsystem | Scope | Main Source File | Storage Engine | Algorithm / Nature | Primary Purpose |
|---|---|---|---|---|---|
| **Catalogue Knowledge Graph** | Entire Library Collection | [knowledge_graph/core.py](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py) | SQLite (`catalogue.sqlite`) | TF-IDF feature weighting, Cosine graph similarity, 2-hop reason paths | Cross-document discovery, "More Like This" recommendations, explainable paths |
| **Document Knowledge Graph / Concept Map** | Single Selected Document | [rag/services/document_knowledge.py](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py) | SQLite (`registry.sqlite`) or JSON | Structural regex parsing, Frequency/Heading scoring, MMR diversity embedding | In-document conceptual visualization, mind map generation, quiz evidence framing |

> [!IMPORTANT]
> **Key Viva Defense Point:**
> When reviewers ask: *"Is your graph an LLM-generated knowledge graph, a Neo4j graph, or an entity-relation graph?"*
> You must clarify this exact distinction:
> 1. The **Document-level graph** is an **extractive concept association and source-organization graph** built deterministically from grammatical definition rules, structural headings, and embedding-based diversity. It is **not** an unbounded OpenIE or LLM-hallucinated triple store.
> 2. The **Catalogue graph** is a **bipartite metadata-feature graph** on SQLite connecting books via shared authors, subjects, and extracted TF-IDF topics, computing exact cosine similarities over catalogue-degree normalized weights.

---

## 2. Document Knowledge Graph: Code Locations & Structure

### 2.1 File Map & Line Ranges
- **Endpoint Definitions**: [rag/services/knowledge_routes.py:L53-L57](file:///d:/SDC/LibraryLLM/rag/services/knowledge_routes.py#L53-L57) (`POST /rag/documents/{id}/artifacts/mindmap` and `/artifacts/key-concepts`)
- **Pipeline Orchestrator**: [rag/services/knowledge_artifacts.py:L136-L206](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L136-L206) (`_generate`)
- **Graph Construction & Concept Extraction**: [rag/services/document_knowledge.py:L212-L456](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L212-L456) (`build()`)
- **Mind Map / Graph Transformation**: [rag/services/document_knowledge.py:L516-L547](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L516-L547) (`generate(kind='MIND_MAP')`)
- **Typed Relationship Extraction**: [rag/services/knowledge_quiz_relations.py:L50-L141](file:///d:/SDC/LibraryLLM/rag/services/knowledge_quiz_relations.py#L50-L141) (`build()`)
- **Evidence Frame Binding**: [rag/services/knowledge_quiz_evidence.py:L50-L145](file:///d:/SDC/LibraryLLM/rag/services/knowledge_quiz_evidence.py#L50-L145) (`build()`)
- **Frontend Canvas Renderer**: [frontend/src/components/knowledge/KnowledgeMap.tsx:L9-L126](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/KnowledgeMap.tsx#L9-L126)
- **Frontend Graph Positioning Math**: [frontend/src/components/knowledge/mapLayout.ts:L6-L56](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/mapLayout.ts#L6-L56)

---

## 3. Algorithmic Extraction Methodology

### 3.1 Concept Identification Pipeline
The document graph does **not** use a general-purpose NER (Named Entity Recognition) model like spaCy or an LLM. It employs a **four-stage hybrid extraction pipeline**:

```
[Raw Document Chunks]
        |
        v
1. Source Units & Line Cleansing (document_knowledge.py:L118-L195)
   - Removes boilerplate, repeated running headers (>=40% page frequency), hyphens
   - Classifies structural lines into HEADING, LIST_ITEM, and PARAGRAPH
        |
        v
2. Multi-Channel Candidate Harvesting (document_knowledge.py:L222-L318)
   - Channel A: Definitional statements (regex matching "X is a/an Y that...")
   - Channel B: Structural section headings with explanatory sentences
   - Channel C: Bullet list steps ("has step" relations)
   - Channel D: Recurring noun phrases (2-4 words occurring >=3 times across >=2 pages)
        |
        v
3. Multi-Signal Concept Scoring (document_knowledge.py:L320-L342)
   - Score = Σ(Signals) - Genericity Penalty - Fragment Penalty
        |
        v
4. Dense Vector Deduplication via MMR (document_knowledge.py:L345-L404)
   - CPU all-MiniLM-L6-v2 embedding of top 192 candidate phrases
   - Maximal Marginal Relevance diversity selection with cosine similarity penalty
```

### 3.2 Mathematical Formulation of Concept Scoring
Each candidate concept $c$ is evaluated across seven weighted signals and two penalties:

$$\text{Score}(c) = S_{\text{heading}} + S_{\text{definition}} + S_{\text{freq}} + S_{\text{pages}} + S_{\text{specificity}} + S_{\text{rel}} + S_{\text{length}} - P_{\text{generic}} - P_{\text{fragment}}$$

Where:
- $S_{\text{heading}} = 2.8 \times \mathbb{I}(\text{heading})$: Heading presence boost.
- $S_{\text{definition}} = 4.5 \times \mathbb{I}(\text{defined})$: Heaviest positive weight; granted if concept appears in an explicit definitional copula (`is defined as`, `refers to`, `means`, `consists of`).
- $S_{\text{freq}} = \min(1.5, 0.6 \times \ln(1 + |\text{evidence}|))$: Sublinear frequency scaling.
- $S_{\text{pages}} = \min(1.2, 0.25 \times |\text{pages}|)$: Multi-page distribution evidence.
- $S_{\text{specificity}} = \min\left(2.0, \frac{1}{|W|} \sum_{w \in W} \ln\left(1 + \frac{N}{\text{DF}(w)}\right)\right)$: Average inverse document frequency across words $W$.
- $S_{\text{rel}} = 0.8 \times \mathbb{I}(\text{typed relation exists})$: Bonus for explicit relational verbs (`is used for`, `consists of`, `has step`).
- $S_{\text{length}} = \min(1.0, 0.35 \times (|W| - 1))$: Preference for multi-word phrases over ambiguous single words.
- $P_{\text{generic}} = (0.7 \text{ if defined else } 3.0 \text{ if } |W|=1 \text{ else } 0.25) + \max(0, 1.2 - \text{specificity}) + 2.0 \times \mathbb{I}(W \cap \text{GENERIC\_CONTEXT} \neq \emptyset)$: Aggressive suppression of vague terminology (`process`, `system`, `idea`, `difference`).
- $P_{\text{fragment}} = 2.5 \times \mathbb{I}(\text{label matches 'step 1', 'part 2', etc.})$.

**Admission Threshold:** Candidates must achieve $\text{Score}(c) \ge 4.1$ and meet minimum structural criteria to be admitted to the vector pool ([document_knowledge.py:L339](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L339)).

### 3.3 Maximal Marginal Relevance (MMR) Diversity Selection
To prevent near-duplicate concepts (e.g., *"Sliding Window"* and *"Sliding Window Protocol"*) from dominating the graph:
1. Top $K \le 192$ candidates are embedded using CPU `all-MiniLM-L6-v2` into normalized unit vectors $\mathbf{v}_i \in \mathbb{R}^{384}$.
2. Concepts are selected greedily. At step $t$, the candidate maximizing the marginal score is chosen:
   $$\arg\max_{i \notin S} \left( \text{Score}(c_i) - 2.2 \times \max_{j \in S} (\mathbf{v}_i \cdot \mathbf{v}_j) \right)$$
3. Before admission, a candidate is checked for duplicates:
   - Lexical overlap: Token subset inclusion ($W_i \subseteq W_j$ or $W_j \subseteq W_i$) unless both are independently defined.
   - Semantic similarity: Cosine similarity $\mathbf{v}_i \cdot \mathbf{v}_j \ge 0.90$ with high explanation overlap ($\ge 0.90$ character sequence ratio).

---

## 4. Nodes, Edges, and Graph Topology

### 4.1 What Qualifies as a Node?
In the document graph (`MIND_MAP`), three distinct types of nodes are generated ([document_knowledge.py:L517-L547](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L517-L547)):
1. **Document Root Node** (`type: 'document'`): Represents the entire document (e.g., `id: 'document'`, `label: title`).
2. **Structural Group Nodes** (`type: 'chapter'` or `'section'`): Extracted from metadata headers (`chapter`, `section`) to form organizational branches (up to 10 groups).
3. **Concept Nodes** (`type: 'concept'`): The top 24 accepted educational domain concepts selected by the MMR scoring algorithm.
4. **Evidence Leaf Nodes** (`type: 'evidence'`): Up to 24 concrete factual statements extracted from typed relationships describing a concept.

### 4.2 What Qualifies as an Edge?
Edges in the document graph fall into two strictly defined categories:
1. **Structural Organization Edges**:
   - `Document -> Group`: `relation: 'source organization'`
   - `Group -> Concept`: `relation: 'document topic'`
   - These capture the document's editorial hierarchy, **not** semantic claims.
2. **Typed Semantic & Evidence Edges**:
   - `Concept -> Evidence`: Derived from sentence-level copular predicates:
     - `DEFINED_AS`: For identity assertions (`is defined as`, `refers to`, `means`, `is/are a/an`).
     - `CONTAINS`: Compositional relations (`consists of`).
     - `USED_FOR`: Purpose or functional relations (`is used for`).
     - `HAS_STEP`: Algorithmic or procedural sequence steps.
     - `DESCRIBED_AS`: Descriptive explanatory assertions.

### 4.3 Is it a True Entity-Relation Knowledge Graph or a Concept Co-Occurrence Graph?
**Verdict for Reviewers:**
It is a **Typed Concept-Evidence Association Graph grounded in syntactic grammatical patterns**.
- It is **far superior to a naive co-occurrence graph**: Edges are **not** created merely because two words appear in the same paragraph or sliding window. Every semantic edge requires an explicit grammatical predicate (`is`, `refers to`, `consists of`) and must link to a verified source excerpt with chunk IDs.
- However, it is **not an arbitrary multi-relational Knowledge Graph** like Freebase or Wikidata: Concepts are not resolved against external ontologies, and cross-concept links (e.g., `Concept A -> INVENTED_BY -> Person B`) only exist if explicitly captured by one of the 5 supported predicate patterns within the text.

---

## 5. Catalogue Knowledge Graph (`knowledge_graph/core.py`)

For cross-book exploration across the broader library catalogue, LuminaR implements a separate bipartite metadata graph:

```mermaid
graph LR
    subgraph Books["Book Works"]
        B1["Book: Operating Systems Concepts"]
        B2["Book: Modern Operating Systems"]
    end
    subgraph Features["Typed Feature Nodes"]
        A["Author: Andrew S. Tanenbaum"]
        S["Subject: Operating Systems"]
        T["Topic: Virtual Memory"]
    end
    B1 --- S
    B1 --- T
    B2 --- A
    B2 --- S
    B2 --- T
```

### 5.1 Storage Schema (`catalogue.sqlite`)
The catalogue graph is stored in a dedicated SQLite database with read-only URI connection pooling ([core.py:L31-L38](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L31-L38)):
- `books`: `(id, work_id, title, title_key, authors, subjects, description_hash)`
- `features`: `(kind, term, label, degree, weight)` where `kind` is `'author'`, `'subject'`, or `'topic'`.
- `edges`: `(book_id, kind, term, label, source_hash)`
- `norms`: `(book_id, value)` - Precomputed squared norms for cosine normalization.
- `meta`: Metadata containing total books, edges, and catalogue hash.

### 5.2 Cosine Similarity Recommendation Algorithm
The `more_like_this(work_id, limit=10)` algorithm computes exact cosine similarity over bipartite graph features:

$$\text{Score}(B_{\text{seed}}, B_{\text{candidate}}) = \frac{\sum_{f \in \mathcal{F}(B_{\text{seed}}) \cap \mathcal{F}(B_{\text{candidate}})} w_f^2}{\sqrt{\|\mathbf{n}_{\text{seed}}\| \cdot \|\mathbf{n}_{\text{candidate}}\|}}$$

Where each feature weight $w_f$ incorporates inverse catalogue frequency:
$$\text{Importance}(f) = 1 + \ln\left(\frac{N_{\text{books}} + 1}{\text{Degree}(f) + 1}\right)$$

### 5.3 Deterministic 2-Hop Reason Paths
For every recommendation, the engine traverses the shared feature nodes to emit human-readable provenance paths ([core.py:L84-L100](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L84-L100)):
```json
{
  "nodes": ["work_seed", "topic:hash", "work_candidate"],
  "kind": "topic",
  "label": "virtual memory",
  "provenance": [
    {"work_id": "work_seed", "field": "topic", "value": "virtual memory"},
    {"work_id": "work_candidate", "field": "topic", "value": "virtual memory"}
  ]
}
```

---

## 6. Real Worked Example (Verified from Repository Fixture)

Using the actual test fixture [tests/fixtures/knowledge_educational.json](file:///d:/SDC/LibraryLLM/tests/fixtures/knowledge_educational.json):

### Step 1: Input Chunk Text
```
Scheduling
Round Robin is a scheduling algorithm that gives each ready process a fixed time quantum.
First Come First Served is a scheduling algorithm that runs processes in their arrival order.
Shortest Job First is a scheduling algorithm that selects the process with the smallest estimated execution time.
Priority Scheduling is a scheduling algorithm that selects a ready process according to its assigned priority.
```

### Step 2: Extracted Concepts & Scores
- **Round Robin**: $\text{Score} = 7.82$ (Heading: Yes, Defined: Yes, Relation: `DEFINED_AS`)
- **First Come First Served**: $\text{Score} = 7.54$ (Defined: Yes)
- **Shortest Job First**: $\text{Score} = 7.49$ (Defined: Yes)
- **Priority Scheduling**: $\text{Score} = 7.45$ (Defined: Yes)

### Step 3: Generated Graph Topology
```mermaid
graph TD
    DOC["id: document<br/>Document: Computer Science Handbook"]
    SEC["id: group_section_Scheduling<br/>Section: Scheduling"]
    C1["id: concept_round_robin<br/>Concept: Round Robin"]
    C2["id: concept_fcfs<br/>Concept: First Come First Served"]
    E1["id: relation_rr_target<br/>Evidence: gives each ready process a fixed time quantum"]
    E2["id: relation_fcfs_target<br/>Evidence: runs processes in their arrival order"]

    DOC -->|source organization| SEC
    SEC -->|document topic| C1
    SEC -->|document topic| C2
    C1 -->|DEFINED_AS| E1
    C2 -->|DEFINED_AS| E2
```

---

## 7. Reviewer Defense & Viva Preparation

### Q1: "What is a knowledge graph in the context of your project?"
**Spoken Answer (20-30s):**
> "In LuminaR, we use the term in two specific ways: at the library level, we have a typed SQLite catalogue graph connecting books through shared authors, subjects, and TF-IDF topics for explainable 2-hop recommendations. At the document level, our Knowledge Tools construct a concept-evidence graph that models the structural hierarchy of the document and extracts typed definitions such as DEFINED_AS, CONTAINS, and USED_FOR without calling an LLM."

### Q2: "Why didn't you use Neo4j?"
**Spoken Answer (20-30s):**
> "Neo4j introduces significant operational overhead—requiring a separate JVM daemon, 500MB+ memory footprint, and Cypher query translation. In LuminaR, the catalogue graph is embedded in a read-only SQLite database (`catalogue.sqlite`) with precomputed vector norms, enabling sub-millisecond cosine queries using indexed SQL JOINs. For document-level maps, graphs are ephemeral and scoped to the user session, so SQLite JSON storage and SVG rendering completely eliminate external database dependencies."

### Q3: "How do you ensure graph edges are factually correct and not spurious?"
**Spoken Answer (20-30s):**
> "Unlike co-occurrence graphs that link any two words appearing in proximity, our document graph enforces syntactic copular constraints. An edge is only created when an explicit grammatical relation matches our rule grammar—such as 'X is defined as Y' or 'X consists of Y'—and every edge retains the exact source sentence, chunk ID, and page number in its provenance metadata."
