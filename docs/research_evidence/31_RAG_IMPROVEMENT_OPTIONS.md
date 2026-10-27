# RAG Architectural Comparison: Implemented vs. Potential Future Work

> **Audit Context**: LuminaR Research Evidence Audit — Part 5  
> **Source Files Verified**:
> - `rag/qa.py`
> - `rag/reranker.py`
> - `rag/retriever.py`
> - `rag/llm.py`
> - `rag/fast_filter.py`
> - `rag/evidence.py`

---

## 1. Implementation Status Matrix

| RAG Technique | Status in LuminaR | Exact Implementation Details |
| :--- | :---: | :--- |
| **Dense Vector Retrieval** | **CURRENTLY IMPLEMENTED** | `SentenceTransformer(all-MiniLM-L6-v2)` + FAISS `IndexFlatIP`. |
| **Sparse Inverted Index (BM25 in RAG)**| **POTENTIAL FUTURE WORK** | Tantivy BM25 exists in the catalog search engine (`/search`), but **NOT** in the document/book RAG pipeline. |
| **Cross-Encoder Reranking** | **CURRENTLY IMPLEMENTED** | `CrossEncoder(ms-marco-MiniLM-L-6-v2)` reranks top 10–20 candidates. |
| **Hybrid Scoring Fusion** | **CURRENTLY IMPLEMENTED** | `0.30 CE + 0.55 Evidence + 0.15 FAISS` linear combination. |
| **Diversity Selection (MMR)** | **CURRENTLY IMPLEMENTED** | Lexical Jaccard MMR in `select_diverse_context()` ($0.30 \times \text{redundancy}$ penalty). |
| **Dynamic Top-K** | **CURRENTLY IMPLEMENTED** | Static discrete profiles by `depth` (4, 7, 10, 15 context chunks). |
| **Absolute Similarity Threshold**| **POTENTIAL FUTURE WORK** | FAISS retrieval has **no** cosine floor; retrieves top-k unconditionally. |
| **Neighboring Chunk Retrieval** | **POTENTIAL FUTURE WORK** | Does **not** retrieve parent chunks or adjacent chunks ($c-1, c+1$). |
| **Conversational Query Rewriting**| **POTENTIAL FUTURE WORK** | Queries are stateless; no coreference or pronoun resolution. |
| **Evidence Pre-Validation** | **CURRENTLY IMPLEMENTED** | Deterministic Fast Filter Gate + Qwen LLM-as-a-judge (`ValidatorSchema`). |
| **Post-Generation Citation Verifier**| **POTENTIAL FUTURE WORK** | Does not run an NLI check on generated output sentences against cited sources. |
| **Multi-Tier Abstention Logic** | **CURRENTLY IMPLEMENTED** | 4-tier abstention (Empty retrieval, Fast-Reject, Validator refusal, API reconciliation). |
| **Indirect Injection Fencing** | **POTENTIAL FUTURE WORK** | Plain text delimiters (`[Source N]`); lacks XML/CDATA boundary fencing. |

---

## 2. In-Depth Evaluation of Potential Future Work

### 1. Hybrid Search (BM25 + Dense Vectors in RAG)
- **Current State**: Initial vector candidate retrieval relies solely on dense bi-encoder embeddings (`all-MiniLM-L6-v2`).
- **Limitation**: Suffers from "out-of-vocabulary" failures on specialized alphanumeric codes, theorem names, function signatures, or rare terms.
- **Evaluation**: Integrating BM25/Tantivy alongside FAISS with Reciprocal Rank Fusion (RRF) would significantly increase candidate recall on technical textbooks.

### 2. Conversational Query Rewriting & Coreference Resolution
- **Current State**: Each user question is evaluated as an isolated standalone string.
- **Limitation**: Follow-up questions (*"Explain it simply"*, *"What are its disadvantages?"*) fail completely.
- **Evaluation**: Adding a lightweight query-rewriting model (or structured prompt pass over the last 2 conversation turns) to expand pronouns into explicit noun phrases before vector retrieval is the single highest-impact conversational improvement.

### 3. Hierarchical / Neighboring Chunk Retrieval (Small-to-Big Windowing)
- **Current State**: Retrieval fetches standalone 3,000-character chunks with fixed 400-character overlap.
- **Limitation**: Sentences split across page boundaries or adjacent paragraphs lose context.
- **Evaluation**: Index small chunks (e.g. 100 words) for high-precision vector matching, but inject the parent context window (surrounding $\pm 1$ chunks or full section) into the prompt.

### 4. Absolute Vector Similarity Floor
- **Current State**: FAISS retrieves candidates regardless of how distant they are in vector space.
- **Limitation**: Completely off-topic queries still retrieve the "least irrelevant" chunks, wasting cross-encoder computation.
- **Evaluation**: Enforcing a strict minimum cosine similarity cutoff (e.g. $\text{IP} \ge 0.45$) would trigger early abstention before running the reranker or fast filter.

### 5. Automated Post-Generation Citation & Groundedness Checker
- **Current State**: Evidence validation runs *before* answer generation. No post-hoc check verifies that the output sentence strictly adheres to the cited chunks.
- **Limitation**: Qwen can occasionally introduce minor hallucinations or unstated inferences even when passing the pre-check.
- **Evaluation**: Implementing a sentence-level Natural Language Inference (NLI) entailment model (or MiniCheck pass) verifying $\text{Premise}(\text{Chunk}) \implies \text{Hypothesis}(\text{Answer Sentence})$ would guarantee complete factual verification.

### 6. Robust Prompt Fencing (XML Delimiters)
- **Current State**: Plain-text interpolation (`CONTEXT:\n{context}\n\nQUESTION:`).
- **Limitation**: Vulnerable to Indirect Prompt Injection embedded in uploaded PDFs.
- **Evaluation**: Wrapping source passages in `<untrusted_source id="...">...</untrusted_source>` tags with explicit model instructions to ignore instructions inside untrusted tags.
