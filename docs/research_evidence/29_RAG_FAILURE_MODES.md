# RAG Failure Modes Taxonomy & Evidence

> **Audit Context**: LuminaR Research Evidence Audit — Part 5  
> **Source Files Verified**:
> - `rag/qa.py`
> - `rag/reranker.py`
> - `rag/retriever.py`
> - `rag/fast_filter.py`
> - `rag/llm.py`
> - `rag/services/private_documents.py`

---

## 1. The 10 Primary RAG Failure Modes

A comprehensive audit of active code and runtime constraints reveals ten distinct operational failure modes in LuminaR:

```
[ User Query ]
      |
 (1) QUERY FAILURE ------------> Intent misunderstood / Coreference unresolved
      |
 (2) RETRIEVAL FAILURE --------> Nearest-neighbor search misses relevant passage
      |
 (3) CHUNKING FAILURE ---------> Definition / proof fractured across 3000-char boundary
      |
 (4) RANKING FAILURE ----------> Correct passage ranked outside top-k context window
      |
 (5) CONTEXT FAILURE ----------> Irrelevant distractor chunks crowd out the target claim
      |
 (6) GENERATION FAILURE -------> Evidence present, but LLM inverts or misreads claim
      |
 (7) CROSS-LIBRARY FAILURE ----> Tenant barriers block legitimate multi-branch discovery
      |
 (8) CROSS-DOCUMENT FAILURE ---> System refuses multi-document synthesis
      |
 (9) OUT-OF-CORPUS HALLUCINATION Parametric memory leaks for famous domain entities
      |
(10) MULTI-TURN FAILURE -------> Sequential conversational turns lose contextual referents
```

---

## 2. Detailed Failure Mode Analysis

### 1. Query Failure
- **Description**: The retrieval engine receives a query that does not reflect the user's actual informational need.
- **Root Cause**:
  - Conversational follow-ups (*"Explain it more simply"*, *"What are its disadvantages?"*) are dispatched verbatim without pronoun resolution or topic re-injection.
  - Figurative, metaphorical, or highly colloquial queries degrade embedding quality.
- **Code Reference**: `rag/api.py:200-204` forwards raw `request.query` directly without conversational rewriting.

### 2. Retrieval Failure
- **Description**: The authoritative chunk exists in the document/book, but FAISS does not return it in the candidate set (`CANDIDATE_K = 10` to `20`).
- **Root Cause**:
  - The bi-encoder (`all-MiniLM-L6-v2`) fails to capture semantic equivalence when user terminology diverges heavily from author terminology (lexical mismatch).
  - Truncation gap: MiniLM only encodes the first 256 tokens of each 3,000-character chunk. If the relevant claim appears at character offset 2,200, its vector representation is missing from the index.
- **Code Reference**: `rag/retriever.py:165-175`.

### 3. Chunking Failure
- **Description**: Vital contextual relationships, multi-step procedures, or definitions are fractured across arbitrary chunk boundaries.
- **Root Cause**:
  - Fixed character sliding window (3,000 chars, 400 overlap) slices text without regard for paragraph semantics, Markdown tables, or mathematical proofs.
  - Strict page boundaries prevent chunks from spanning across pages ($P \to P+1$), cutting sentences that flow across page breaks.
- **Code Reference**: `rag/services/document_service.py:85-124`.

### 4. Ranking Failure
- **Description**: The correct chunk is retrieved in the initial 20–40 candidates, but is scored poorly by the Cross-Encoder or Evidence scorer, falling below the final context cutoff (`context_chunks`).
- **Root Cause**:
  - Hybrid scoring weights (`0.30 CE + 0.55 EV + 0.15 FAISS`) heavily prioritize structural evidence signals (`EVIDENCE_WEIGHT = 0.55`). If a relevant passage lacks explicit lexical keywords or headings matching the query, it is outranked by high-frequency lexical matches.
- **Code Reference**: `rag/reranker.py:415-422`.

### 5. Context Failure
- **Description**: The prompt is filled with irrelevant or distractor passages that dilute attention or mislead the generator.
- **Root Cause**:
  - When searching for common terms (*"architecture"*, *"security"*, *"performance"*), multiple chapters contain matching vocabulary.
  - Even with Jaccard diversity selection (`select_diverse_context`), passages describing different components are injected together, increasing distraction.
- **Code Reference**: `rag/qa.py:204-261`.

### 6. Generation Failure
- **Description**: The correct passage is present in the prompt context, but Qwen generates an inaccurate, contradictory, or unsupported answer.
- **Root Cause**:
  - Complex syntactic constructions (double negatives, subtle conditionals, passive voice) are misinterpreted by the 3B parameter model.
  - Causal leaps: Qwen infers unstated motivations or causes despite prompt Rule 15.
- **Code Reference**: `rag/llm.py:433-435`.

### 7. Cross-Library Failure
- **Description**: Institutional users belonging to a library system cannot perform RAG across multiple branch collections simultaneously.
- **Root Cause**:
  - Tenant isolation strictly scopes vector indices to individual library tenants or generation IDs. Federated multi-tenant RAG is unsupported by design.
- **Code Reference**: `rag/services/library_asset_pipeline.py:108-120`.

### 8. Cross-Document Failure
- **Description**: A user cannot ask comparative questions across two separate uploaded documents (e.g. comparing two research papers or lecture slide decks).
- **Root Cause**:
  - The API schema and retriever mandate a single active scope:
    ```python
    if request.document_id and request.work_id and request.document_id != request.work_id:
        raise HTTPException(400, "document_id and work_id must identify the same source.")
    ```
  - Cross-document synthesis is rejected at the API validation layer.
- **Code Reference**: `rag/api.py:234-236`.

### 9. Out-of-Corpus Hallucination
- **Description**: For questions regarding well-known canonical subjects (e.g. *Frankenstein*, *Dracula*, *TCP/IP*), the model bypasses prompt constraints and generates facts from pretrained parametric memory.
- **Root Cause**:
  - Instruction-following attenuation: Strong parametric weights for famous cultural entities overpower soft prompt instructions when retrieved passages provide weak evidence.
- **Code Reference**: `rag/llm.py:310-315`.

### 10. Multi-Turn Context Failure
- **Description**: Sequential chat degrades into nonsense or unrelated retrievals after Turn 1.
- **Root Cause**:
  - Complete architectural absence of chat history in the RAG request pipeline.
  - Every turn is evaluated in total isolation from previous queries and answers.
- **Code Reference**: `rag/api.py:110-120`, `frontend/src/lib/api.ts:818-835`.
