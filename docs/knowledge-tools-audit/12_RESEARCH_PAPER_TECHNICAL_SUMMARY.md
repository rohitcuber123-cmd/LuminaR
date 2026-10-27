# Architectural Design and Algorithmic Framework of the LuminaR Knowledge Tools Subsystem

## Abstract
This paper presents the architectural design, algorithmic pipeline, and implementation methodology of the Knowledge Tools subsystem within LuminaR, an intelligent digital library and document analysis platform. While modern retrieval-augmented generation (RAG) architectures primarily address interactive point-query question answering, they exhibit significant resource contention and non-deterministic behavior when repurposed for comprehensive document synthesis and pedagogical artifact generation. The LuminaR Knowledge Tools subsystem resolves this limitation through a decoupled, multi-tiered architecture that bypasses the primary large language model (LLM) and graphics processing unit (GPU) inference runtime. By combining syntactic copular extraction, information-theoretic heuristic scoring, dense embedding-based Maximal Marginal Relevance (MMR) diversity selection, and formal verification gates, the subsystem deterministically extracts structured study models and renders five distinct educational modalities: Key Concepts, Extractive Summaries, Pedagogical Flashcards, Balanced Mind Maps, and Multi-Format Quizzes. We document the mathematical foundations, system boundaries, concurrency controls, and verification mechanisms governing this implementation.

---

## 1. Introduction and Subsystem Objectives
Contemporary intelligent library systems increasingly integrate neural Retrieval-Augmented Generation (RAG) to facilitate natural language search across digitized document collections. In a typical RAG workflow, user queries are matched against pre-indexed vector embeddings, and retrieved textual chunks are provided as context to an autoregressive Large Language Model (LLM) to synthesize a conversational response. 

However, relying exclusively on autoregressive LLMs for holistic pedagogical synthesis—such as constructing comprehensive concept hierarchies, flashcard decks, and multi-format quizzes—introduces several systemic drawbacks:
1. **Resource Contention**: In multi-user and self-hosted environments, executing long-context generative synthesis on shared GPU accelerators creates significant latency spikes and blocks high-priority conversational query turns.
2. **Generative Hallucination**: Generative models frequently introduce external world knowledge, unverified assertions, or subtle factual distortions that diverge from the verified source text.
3. **Format and Schema Instability**: Prompting LLMs for complex, nested JSON artifacts often results in parsing failures, non-deterministic key ordering, and missing citation references.

To mitigate these challenges, the LuminaR Knowledge Tools subsystem was developed with the following primary objectives:
- **Architectural Decoupling**: Isolate document-wide educational artifact synthesis from the resident generative inference runtime (Qwen-2.5-7B) and GPU hardware.
- **Deterministic Source Grounding**: Ensure that 100% of generated concepts, flashcard answers, mind map nodes, and quiz items are anchored to explicit, verifiable textual spans with exact page and chunk metadata.
- **Multi-Format Synthesis**: Support five distinct educational modalities from a unified, intermediate document knowledge representation.
- **Rigorous Verification Gates**: Implement rule-based and semantic validation filters to guarantee distractor incompatibility in multiple-choice questions and mathematical bijection in matching matrices.

---

## 2. Architectural Design and System Boundaries

```
+-------------------------------------------------------------------------------+
|                             CLIENT APPLICATION                                |
|  React 18 + Vite + TypeScript (KnowledgeTools.tsx, KnowledgeMap.tsx, Quiz.tsx)|
+-------------------------------------------------------------------------------+
                                      | HTTP (Bearer Auth, no-store)
+-------------------------------------------------------------------------------+
|                       API ROUTING & ADMISSION CONTROL                         |
|  FastAPI (knowledge_routes.py, library_asset_routes.py)                       |
|  - Concurrency Gate: Semaphore(3) Global Limit                                |
|  - User Isolation: Single-Flight Future Collapsing per Owner                  |
+-------------------------------------------------------------------------------+
                                      |
+-------------------------------------------------------------------------------+
|                        KNOWLEDGE ARTIFACTS ORCHESTRATION                      |
|  KnowledgeArtifacts Service / LibraryAssetPipeline Service                   |
|  - Cache Layer 1: SQLite knowledge_artifacts (SHA256 Revision/Options Key)    |
|  - Cache Layer 2: SQLite document_knowledge (DocumentKnowledgeModel)          |
+-------------------------------------------------------------------------------+
                                      | (On Cache Miss)
+-------------------------------------------------------------------------------+
|                     INTERMEDIATE DOCUMENT KNOWLEDGE BUILDER                   |
|  document_knowledge.py                                                        |
|  - Structural Unit Extraction & Header Parsing (PyMuPDF chunks.json)          |
|  - Multi-Signal Concept Scoring (Definitional copulas, Specificity, Headings) |
|  - Dense MMR Diversity Selection (all-MiniLM-L6-v2 CPU Singleton)             |
|  - Evidence Framing (knowledge_quiz_evidence.py)                              |
|  - Typed Relation Extraction (knowledge_quiz_relations.py)                    |
+-------------------------------------------------------------------------------+
                                      |
         +----------------------------+----------------------------+
         |                            |                            |
+-------------------+        +-------------------+        +-------------------+
| CONCEPTS/SUMMARY  |        |    FLASHCARDS     |        |    QUIZ ENGINE    |
| - Key Concepts    |        | - Definition Cards|        | - knowledge_mcq   |
| - Extractive Sum. |        | - Cloze Cards     |        | - knowledge_match |
|   (Quick/Detailed)|        | - Process Cards   |        | - knowledge_cloze |
+-------------------+        +-------------------+        +-------------------+
                                                                   |
                                                          +-------------------+
                                                          |  CLOZE GRADING    |
                                                          | - cloze_grading   |
                                                          | - SemanticCache   |
                                                          +-------------------+
```

### 2.1 The Two-Tier Processing Pipeline
The subsystem segregates processing into two distinct execution phases:
1. **Representation Phase (`DocumentKnowledgeModel`)**: Evaluated once per document content revision. Parses structural units from pre-extracted chunks, identifies grammatical definitions, extracts domain concepts, computes dense vector representations, and models typed relational frames. The resulting model is serialized and cached in the session database (`registry.sqlite`) or tenant directory.
2. **Rendering Phase (`generate`)**: Deterministic functions consume the cached `DocumentKnowledgeModel` to emit specific presentation formats. The renderers read exclusively from the in-memory representation, bypassing disk chunk reading, token parsing, and vector embedding.

### 2.2 Hardware and Runtime Isolation
The Knowledge Tools pipeline maintains complete isolation from the RAG conversational engine:
- **LLM Invocations**: Exactly zero autoregressive model calls are made (`qwen_calls = 0`).
- **Accelerator Target**: Embedding operations execute strictly on CPU (`device = 'cpu'`) using a dedicated singleton wrapper (`knowledge_encoder.py`) around `sentence-transformers/all-MiniLM-L6-v2`.
- **Retrieval Index**: The FAISS index (`runtime.faiss`) utilized by RAG is never queried; Knowledge Tools inspects the primary extracted text partitions (`chunks.json`) directly.

---

## 3. Algorithmic Pipeline & Mathematical Formulations

### 3.1 Structural Unit Cleansing & Segmentation
Given raw textual chunks $\mathcal{C} = \{c_1, \dots, c_m\}$ extracted via PyMuPDF (`fitz`), text is canonicalized using Unicode NFKC normalization and filtered for recurring running headers and page numbers. Lines are classified into three structural kinds:
$$\text{Kind}(l) \in \{\text{HEADING}, \text{LIST\_ITEM}, \text{PARAGRAPH}\}$$
Sentences within paragraph units are partitioned using boundary regular expressions requiring terminal punctuation, an alphabetic character density $\ge 0.52$, and the presence of verified verbal predicates.

### 3.2 Multi-Signal Concept Scoring
Candidate domain concepts $c$ harvested from grammatical definitions, section headings, and recurring noun phrases are scored across seven structural signals and two penalties:

$$\text{Score}(c) = S_{\text{def}} + S_{\text{head}} + S_{\text{freq}} + S_{\text{pages}} + S_{\text{spec}} + S_{\text{rel}} + S_{\text{len}} - P_{\text{gen}} - P_{\text{frag}}$$

Where:
- $S_{\text{def}} = 4.5 \times \mathbb{I}(\text{defined})$ represents explicit copular definition matching (`is defined as`, `refers to`, `means`, `consists of`).
- $S_{\text{head}} = 2.8 \times \mathbb{I}(\text{heading})$ captures structural section titles.
- $S_{\text{freq}} = \min(1.5, 0.6 \ln(1 + |\text{evidence}|))$ reflects sublinear occurrence frequency.
- $S_{\text{pages}} = \min(1.2, 0.25 |\text{pages}|)$ rewards concepts distributed across multiple pages.
- $S_{\text{spec}} = \min\left(2.0, \frac{1}{|W|} \sum_{w \in W} \ln\left(1 + \frac{N}{\text{DF}(w)}\right)\right)$ measures inverse document frequency term specificity.
- $S_{\text{rel}} = 0.8 \times \mathbb{I}(\text{typed relation exists})$ denotes relational verbs (`is used for`, `consists of`).
- $S_{\text{len}} = \min(1.0, 0.35 (|W| - 1))$ favors multi-word compounds over ambiguous unigrams.
- $P_{\text{gen}}$ and $P_{\text{frag}}$ penalize generic context words (`system`, `process`, `idea`) and procedural fragments (`step 1`).

Candidates satisfying $\text{Score}(c) \ge 4.1$ advance to dense vector diversity selection.

### 3.3 Maximal Marginal Relevance (MMR) Dense Diversity Selection
To prevent lexical and semantic redundancy across selected concepts, the top $K \le 192$ candidate phrases are embedded into unit-normalized dense vectors $\mathbf{v}_i \in \mathbb{R}^{384}$ using `all-MiniLM-L6-v2`. The selection set $S$ is expanded greedily:
$$c^* = \arg\max_{i \notin S} \left( \text{Score}(c_i) - \lambda \max_{j \in S} (\mathbf{v}_i \cdot \mathbf{v}_j) \right)$$
Where $\lambda = 2.2$. Candidates exhibiting cosine similarity $\mathbf{v}_i \cdot \mathbf{v}_j \ge 0.90$ alongside high sequence similarity ($\ge 0.90$) with an existing selection are suppressed as duplicates.

---

## 4. Synthesis and Validation of Pedagogical Modalities

### 4.1 Pedagogical Flashcards
Flashcard synthesis generates items in two phases:
- **Primary Concepts**: Maps each accepted concept to its primary definition sentence or generates a cloze card by masking the concept label (`"_____"`) within an authoritative explanatory statement.
- **Secondary Relational Items**: Scans remaining verified facts to generate procedural cards (for `'has step'` predicates), application cards (for `'for example'` patterns), and functional relationship cards, capping total output at 40 items.

### 4.2 Balanced Tree Mind Map Layout
Mind map graphs model hierarchical document organization:
$$\text{Document Root} \xrightarrow{\text{source organization}} \text{Chapter/Section Groups} \xrightarrow{\text{document topic}} \text{Concepts} \xrightarrow{\text{typed relation}} \text{Evidence Leaves}$$
Visual node positioning is determined by an original two-sided tree layout algorithm implemented in TypeScript (`mapLayout.ts`):
1. **Subtree Weighting**: Post-order traversal assigns $\text{Weight}(u) = \max(1, \sum_{v \in \text{Children}(u)} \text{Weight}(v))$.
2. **Column Bin-Packing**: Root child branches are greedily partitioned into Left and Right columns to balance aggregate visual weight.
3. **Coordinate Calculation**: Node $X$-positions are placed symmetrically relative to the center based on tree depth and column gap, while $Y$-positions are centered within allocated vertical spans. Smooth cubic bezier curves connect card anchors on an SVG canvas.

### 4.3 Multi-Format Assessment Generation

#### Multiple Choice Questions (MCQs)
- **Stem Formulation**: Constructs forward target prompts (`"Which description best defines X?"`) or inverse subject identification prompts (`"Which concept is defined by this description?"`).
- **Distractor Selection**: Identifies candidate distractors sharing the exact same relation family (`DEFINITION`, `PURPOSE`, `PROCESS`).
- **Incompatibility Verification**: Enforces that distractors do not overlap lexically, do not represent semantic peers, and are not asserted as true for the tested concept anywhere in the source document.
- **Quality Gate**: The `verify()` function enforces 11 criteria, ensuring exactly 4 unique options, absence of answer leakage, and valid source excerpts.

#### Fill-in-the-Blank Semantic Grading
Cloze answers submitted by students are evaluated through a tiered grading architecture (`cloze_grading.py`):
1. **Quantity Conversion**: Evaluates scalar and dimensional numbers (`Decimal` normalization across metric and time units).
2. **Normalization & Safe Typos**: Evaluates NFKC equality, parenthetical acronym aliases (e.g., `TCP` $\leftrightarrow$ `Transmission Control Protocol`), and Levenshtein edit distance $D_{\text{edit}} = 1$ on words $\ge 6$ letters.
3. **Semantic Verification with Clause Decomposition**: Employs MiniLM embeddings within a thread-safe debounced cache (`SemanticCache`), requiring semantic similarity $\ge 0.75$ against the canonical answer, evidence similarity $\ge 0.55$, and coverage $\ge 0.66$ across all material sub-clauses, while strictly rejecting negations and role reversals (`sender` $\leftrightarrow$ `receiver`).

#### Match-the-Following Bijective Matrix
Matching exercises group 3 to 6 concepts and descriptions from a common relation family:
- **Bijective Validation**: Proves that the correct matches define a mathematical bijection ($f: A \to B$ is one-to-one and onto).
- **Beam Search Optimization**: Applies beam search (width 80) over candidate matching sets to allocate pairs without duplicating concepts claimed by MCQs.
- **Anti-Alignment Shuffling**: Shuffles Column B using deterministic PRNG, cyclically shifting if the shuffled order matches Column A identically.

---

## 5. Resource Efficiency, Concurrency, and Security

### 5.1 Concurrency Admission Control
In-process concurrency is governed by a two-tier admission control gate:
- **Global Capacity Semaphore**: A `threading.Semaphore(3)` bounds total concurrent artifact generation tasks, returning HTTP 429 when saturated.
- **Single-Flight Per-Owner Collapsing**: A synchronized active jobs dictionary registers a `concurrent.futures.Future` for each unique `(owner, session, document_id, kind, options)` tuple. Duplicate concurrent requests join the leader Future, eliminating redundant computation.

### 5.2 Cryptographic Caching and Invalidation
Artifacts are cached in SQLite (`knowledge_artifacts`) using a deterministic SHA-256 composite key:
$$\text{Key} = \text{SHA256}\Big(\text{revision} \,\|\, \text{kind} \,\|\, \text{scope} \,\|\, \text{options} \,\|\, \text{generator\_version} \,\|\, \text{knowledge\_version}\Big)$$
Where $\text{revision} = \text{SHA256}(\text{chunks.json})$. Any modification to source document text or subsystem algorithm versions immediately causes a cache miss, preventing stale data delivery.

### 5.3 Privacy and Client Session Boundary
- **Transport Security**: All artifact endpoints emit `Cache-Control: no-store` headers, preventing intermediate proxy and browser disk caching of private notes.
- **Frontend Reconciliation Cleansing**: The React container keys the session component by `${token}:${libraryId}:${documentId}`. Authenticated session termination or document switching triggers complete component unmounting and memory purging.

---

## 6. Subsystem Limitations

While the deterministic architecture delivers high efficiency and factual grounding, several inherent limitations must be acknowledged:
1. **Dependency on Copular and Heading Structure**: Documents lacking explicit definitional copulas (`is`, `means`, `refers to`) or structural headings yield sparse concept sets.
2. **Absence of Longitudinal Spaced Repetition**: The flashcard subsystem currently operates on a per-session study model, lacking persistent Leitner or SuperMemo-2 (SM-2) spaced repetition review scheduling.
3. **Fixed Four-Option MCQ Format**: Multiple-choice generation is constrained strictly to 4 options. If a document yields only 2 compatible distractors for a concept, the question is discarded entirely.
4. **Unilingual Optimization**: Algorithmic rules, stopword lists, and regex grammars are tailored specifically to English technical and academic prose.

---

## 7. Conclusion

The LuminaR Knowledge Tools subsystem demonstrates that automated educational synthesis can be achieved with high precision, complete source grounding, and minimal latency without relying on generative LLM inference. By leveraging structural parsing, information-theoretic heuristic scoring, dense vector diversity selection, and formal verification gates, the platform provides a scalable, resource-efficient foundation for intelligent digital library systems.
