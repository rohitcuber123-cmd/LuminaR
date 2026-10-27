# Knowledge Artifact Limitations & Architectural Constraints

> **Audit Context**: LuminaR Research Evidence Audit — Part 6  
> **Source Files Verified**:
> - `rag/services/document_knowledge.py`
> - `rag/services/knowledge_quiz.py`
> - `rag/services/knowledge_algorithms.py`
> - `rag/services/cloze_grading.py`
> - `rag/services/document_service.py`
> - `rag/services/private_document_ocr.py`

---

## 1. Core Paradigm: Deterministic Extraction vs. Generative Synthesis

> [!IMPORTANT]
> **EXPLICIT DECLARATION ON MODEL USAGE**  
> Across all knowledge artifact paths in LuminaR (Key Concepts, Extractive Summary, Definition Flashcards, Cloze Flashcards, Mind Maps, and Quizzes), **Qwen is NOT used**.  
> **Knowledge Artifacts are deterministic and/or embedding-assisted rather than LLM-generated.**

While this design guarantees **zero hallucinations**, **100% source grounding**, and **instantaneous execution**, it introduces several fundamental limitations:

1. **Zero Abstractive Synthesis**:
   - The system cannot synthesize ideas, bridge conceptual gaps, or explain complex relationships that are not explicitly stated within a single sentence or contiguous source block.
   - Summaries cannot create fluid narrative overviews; they are collections of top-ranked verbatim sentences.
2. **Literal Formulation Lock-In**:
   - If an author expresses a vital definition poorly, with convoluted grammar or archaic phrasing, the flashcard or quiz question inherits that exact phrasing verbatim.
3. **Absence of Pedagogical Scaffolding**:
   - The engine cannot simplify explanations for beginners or generate analogies, as an LLM could.

---

## 2. Tokenizer & Context Window Discrepancy

A critical architectural tension exists between the chunker and the embedding model:

```
Chunk Size: 3,000 characters (~600–750 tokens)
================================================================================
| First 256 tokens (Indexed in FAISS) | Truncated (~350–500 tokens, NOT in Vector Index) |
================================================================================
```

- **Mechanism**: `DocumentService.chunk_text()` cuts text at 3,000 characters. `SentenceTransformer("all-MiniLM-L6-v2")` enforces a hard limit of `max_seq_length = 256` WordPiece tokens (~1,000 characters).
- **Consequence**:
  - The vector index only represents the first ~35% of each chunk.
  - If a concept or definition appears in the latter 1,800 characters of a chunk, dense vector retrieval will not index it.
  - While rule-based knowledge extractors parse the entire text in memory, any vector-based semantic fallback or similarity comparison operates on truncated representations.

---

## 3. Stylistic & Syntactic Vulnerabilities

Because extraction relies on explicit syntactic patterns (`is defined as`, `refers to`, `means`, `consists of`), artifact quality depends heavily on document authoring style:

| Authoring Style | Extraction Outcome | Failure Mode |
| :--- | :--- | :--- |
| **Formal Academic Textbook** (heavy copulas: "X is defined as...") | High volume of flashcards and MCQ distractor sets | Optimal operation |
| **Conversational / Narrative Prose** ("Imagine a world where packets fly...") | Severe distractor and definition scarcity | Rejection: *"Not enough reliable source content was found for this artifact."* |
| **Tabular / Bulleted Specifications** | Bullets without terminal punctuation are rejected by `quality_text()` | Procedural steps and parameters are omitted |
| **Mathematical / Formulaic Documents** | Rejection due to alpha ratio $< 0.52$ and character run checks | Equations and formal proofs cannot generate flashcards or quizzes |

---

## 4. Distractor Scarcity in Specialized Documents

To maintain strict pedagogical integrity, LuminaR forbids fabricating fake distractors:
- An MCQ requires 3 distractors from the same document sharing the exact same relation family and category.
- **Scarcity Failure Mode**:
  - In short documents ($\le 5$ pages) or niche technical papers where an author introduces only one algorithm or technique, the system cannot find 3 compatible peers.
  - The backend will reject the question rather than generate plausible hallucinations:
    ```
    "Not enough reliable source material was available for Multiple Choice."
    ```

---

## 5. Scanned PDF & OCR Bottlenecks

1. **Hardware & Dependency Requirements**:
   - OCR requires a local Tesseract installation (`tesseract.exe`) and English trained data (`eng.traineddata`). If absent, scanned documents produce zero usable text.
2. **Page & Time Caps**:
   - Maximum 80 OCR attempts per document (`page_limit = 80`).
   - 20-second timeout per page (`page_timeout = 20`).
   - Documents with $>80$ scanned pages will have subsequent pages marked blank.
3. **Digit-Letter OCR Corruption**:
   - In `knowledge_cloze.py:33`, if a sentence originated from OCR and exhibits digit-letter merges (e.g. `1` merged into `l`), the entire cloze candidate is dropped to protect against corrupted study materials.

---

## 6. Cloze Grading Edge Cases

The automated short-answer grading engine (`rag/services/cloze_grading.py`) balances flexibility and conservative correctness:
- **Typo Limits**: Only 1 edit distance typo is tolerated, and only in words with $\ge 6$ letters. Short words (e.g., `UDP`, `TCP`, `hop`) allow **zero** typos.
- **Complex Paraphrasing**: While `SemanticCache` performs cosine similarity checks for descriptive answers, colloquial paraphrases that diverge from MiniLM's semantic neighborhood may be marked incorrect despite factual accuracy.

---

## 7. Cache Invalidation & Re-Ingestion Sensitivities

- **Strict Identity Hashing**:
  - Artifact manifests store exact SHA-256 hashes of `chunks.json`, `vectors.npy`, and `runtime.faiss`.
  - Re-extracting a document with an updated chunker version or altered preprocessing immediately invalidates all previously generated study artifacts.
- **Session Ephemerality**:
  - For personal private documents (`/rag/upload`), all generated artifacts exist only in the temporary session directory and are permanently purged upon session expiration or logout.
