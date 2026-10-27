# Knowledge Artifacts Generation Engine Audit

> **Audit Context**: LuminaR Research Evidence Audit — Part 6  
> **Source Files Verified**:
> - `rag/services/document_knowledge.py` (Lines 1–552)
> - `rag/services/knowledge_algorithms.py` (Lines 1–239)
> - `rag/services/knowledge_quiz.py` (Lines 1–303)
> - `rag/services/knowledge_mcq.py` (Lines 1–132)
> - `rag/services/knowledge_match.py` (Lines 1–105)
> - `rag/services/knowledge_cloze.py` (Lines 1–76)
> - `rag/services/cloze_grading.py` (Lines 1–211)

---

## 1. Executive Model Usage Finding

> [!IMPORTANT]
> **CRITICAL VERIFICATION FINDING: ZERO QWEN LLM INVOCATIONS.**  
> Across all six knowledge artifact pipelines (Key Concepts, Extractive Summary, Definition Flashcards, Cloze Flashcards, Mind Maps, and Quiz), **Qwen is NEVER called**.  
> In fact, the backend explicitly sets and asserts:
> - `'qwen_calls': 0` (`rag/services/document_knowledge.py:445`)
> - `'qwenCalls': 0` (`rag/services/knowledge_quiz.py:302`)
> 
> **Knowledge Artifacts are deterministic and/or embedding-assisted rather than LLM-generated.**

---

## 2. Model & Technique Attribution Matrix

| Artifact Type | Qwen LLM | Embedding Model (`MiniLM`) | TF-IDF / IDF | Word Frequency | Regex Patterns | Document Hierarchy | Cosine Similarity | Graph / Combinatorics |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Key Concepts** | **NO** (0 calls) | **YES** (Bounded MMR) | **YES** (Specificity) | **YES** (`Counter`) | **YES** (Heading/Verbal) | **YES** (Sections/Units) | **YES** ($\ge 0.90$) | Greedy MMR |
| **Extractive Summary** | **NO** (0 calls) | **NO** | **YES** (Legacy ranking) | **YES** (Word scoring) | **YES** (Sentence bounds) | **YES** (Section partition) | **NO** | Section-stratified greedy pick |
| **Definition Flashcards**| **NO** (0 calls) | **NO** | **NO** | **NO** | **YES** (`DEFINITION` regex)| **YES** (Unit provenance) | **NO** | Deterministic rule template |
| **Cloze Flashcards** | **NO** (0 calls) | **NO** (Gen) / **YES** (Grading) | **NO** | **NO** | **YES** (Blanking/Aliases)| **YES** (Unit provenance) | **YES** (Grading only) | Regex single-blank substitution |
| **Mind Map** | **NO** (0 calls) | **NO** (Gen) | **NO** | **NO** | **YES** (Relation types) | **YES** (Doc $\to$ Ch $\to$ Sec)| **NO** | Two-sided balanced tree layout |
| **Quiz (MCQ/Match/Cloze)**| **NO** (0 calls) | **YES** (Ambiguity check) | **NO** | **NO** | **YES** (Stem/Prompt/Alias)| **YES** (Section coverage) | **YES** ($\ge 0.88$) | Bijective pairing & beam search |

---

## 3. Deep-Dive Audit by Knowledge Artifact Type

### A. Key Concepts
- **Implementation**: `rag/services/document_knowledge.py:212-420` (`build()`).
- **Input**: Extracted text chunks.
- **Processing Flow**:
  1. *Structural Units*: Chunks parsed into `source_units` (headings, lists, paragraphs).
  2. *Candidate Mining*:
     - Regex definitional statements (`legacy.DEFINITION`).
     - Headings followed by complete explanatory sentences (`heading()`, `explanation_score()`).
     - High-frequency 2-to-4-word phrases appearing on $\ge 2$ pages and $\ge 3$ times.
  3. *Candidate Scoring*: Multi-signal additive heuristic:
     $$\text{Score} = 2.8 \times \text{heading} + 4.5 \times \text{defined} + 0.6 \log(1+\text{freq}) + 0.25 \times \text{pages} + \text{specificity} - \text{penalties}$$
  4. *Embedding Diversification*: Top 192 candidates embedded via `all-MiniLM-L6-v2` (`encoder`).
  5. *Bounded MMR*: Selects 12 (if $\le 4$ pages), 20 (if $\le 20$ pages), or up to 30 concepts. Prunes candidates with cosine similarity $\ge 0.90$.

### B. Extractive Summary
- **Implementation**: `rag/services/document_knowledge.py:499-515`.
- **Modes**:
  - `quick`: Up to 5 sentences.
  - `detailed`: Up to 12 sentences.
- **Algorithm**:
  - Sorts accepted document facts by page order (`pageStart`) and appearance order (`order`).
  - Iterates through distinct sections (`seen_sections`).
  - Picks exactly one high-scoring representative fact sentence per distinct section until the limit (5 or 12) is reached.
  - Output is strictly extractive: original verbatim sentences directly from the document. Zero abstractive synthesis.

### C. Definition Flashcards
- **Implementation**: `rag/services/document_knowledge.py:464-486`.
- **Pattern Matching**: Matches sentences against `DEFINITION` regex:
  ```python
  r'^((?:[A-Za-z][A-Za-z0-9-]*\s+){0,5}[A-Za-z][A-Za-z0-9-]*)\s+'
  r'(is defined as|refers to|consists of|is used for|means|is|are)\s+(.+?[.!?])$'
  ```
- **Template Generation**:
  - Front: `"What does the document explain about {concept}?"`
  - Back: Full verbatim source sentence (`normalized(fact['text'])`).
- **Secondary Cards**: If definitions are scarce, extends to process steps (`"According to the source, what does {concept} involve in this step?"`) and examples (`"what does {concept} illustrate in this example?"`).

### D. Cloze Flashcards
- **Implementation**: `rag/services/document_knowledge.py:475-481` & `knowledge_cloze.py`.
- **Mechanism**:
  - Targets key concept phrases or explicit characteristic phrases (`explicit_cloze_phrases`).
  - Verifies the target phrase occurs **exactly once** in the sentence.
  - Generates:
    - Front: Sentence with target phrase masked as `_____`.
    - Back: Target phrase.
- **Quality Gates**: Rejects if remaining unmasked context has $<6$ words; rejects OCR sentences with digit-letter corruptions.

### E. Mind Maps
- **Implementation**: `rag/services/document_knowledge.py:516-547`.
- **Node Hierarchy**:
  - Root: `document` (title).
  - Sub-roots: `chapter` or `section` (from heading units).
  - Core: `concept` (up to 24 key concepts).
  - Leaves: `evidence` (up to 24 target relation texts, capped at 60 total nodes).
- **Edge Semantic Typology**:
  - Structural: `'source organization'` and `'document topic'`.
  - Semantic: `'DEFINED_AS'`, `'CONTAINS'`, `'USED_FOR'`, `'HAS_STEP'`, `'DESCRIBED_AS'`.
- **Rendering**: Rendered client-side in SVG via `layoutKnowledgeMap` (`frontend/src/components/knowledge/mapLayout.ts`).

### F. Quiz Generation (MCQ, Fill in the Blank, Matching)
- **Implementation**: `rag/services/knowledge_quiz.py`, `knowledge_mcq.py`, `knowledge_match.py`, `knowledge_cloze.py`.
- **Algorithms**:
  - *MCQ*: 1 correct answer + 3 distractors sharing the same semantic `category` or `relationType`. Distractor ambiguity checked using MiniLM embeddings (`float(vectors[i] @ vectors[j]) >= 0.88`).
  - *Fill in the Blank*: Single-blank cloze sentences with alias detection (e.g. acronyms).
  - *Match the Following*: 3 to 6 pairs partitioned by relation family. Right side shuffled with identity-order prevention rotation.
  - *Grading*: Deterministic short-answer grading via `cloze_grading.py` (typo tolerance, numeric parsing, unit conversion, semantic caching).

---

## 4. Architectural Summary

| Dimension | Architectural Reality |
| :--- | :--- |
| **Generative LLM Dependency** | **None (0% Qwen)** |
| **Embedding Model Dependency** | **Assisted (Sentence-Transformers MiniLM used for MMR & Ambiguity Filtering)** |
| **Factual Accuracy** | **100% Extractive Grounding** (cannot hallucinate facts not present in text) |
| **Execution Latency** | **Fast (CPU/GPU-light, milliseconds to seconds)** |
| **Deterministic Consistency** | **High** (identical PDF yields identical artifacts given identical options) |
