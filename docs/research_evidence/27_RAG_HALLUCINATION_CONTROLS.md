# RAG Hallucination Controls Audit

> **Audit Context**: LuminaR Research Evidence Audit — Part 5  
> **Source Files Verified**:
> - `rag/qa.py` (Lines 712–840)
> - `rag/fast_filter.py` (Lines 1–250)
> - `rag/llm.py` (Lines 35–39, 415–430, 647–730)
> - `rag/reranker.py` (Lines 293–306, 406–432)
> - `rag/services/private_documents.py` (Lines 70–76, 221–234)
> - `backend/services/library_asset_service.py` (Lines 102–118)

---

## 1. Mechanism Inventory & Audit

LuminaR employs a defense-in-depth architecture to mitigate model hallucinations. **RAG does not eliminate hallucinations**, but LuminaR uses deterministic gates, reranking, and constrained verification to reduce unsupported generation.

---

### Mechanism 1: Retrieved Grounding Context Injection
- **Implementation**: The top $K$ passages (4 to 15 chunks depending on depth) are formatted under `[Source N]` headers and placed directly in the prompt before the user query.
- **Code Path**: `rag/qa.py:197-261` (`build_context`)
- **Why It Helps**: Gives the LLM direct access to authoritative source text, reducing reliance on parameterized parametric memory.
- **Limitations**: If irrelevant chunks are retrieved, the LLM may attend to distractor passages or synthesize unsupported conclusions.
- **How to Test**: Ask a fact-specific question; verify that facts in the answer map directly to text inside the injected passages.

---

### Mechanism 2: "Context-Only" Negative Prompt Constraints
- **Implementation**: Injects 18 numbered rules explicitly forbidding world knowledge (*"Use ONLY the supplied context as evidence. Do not use pretrained knowledge or world knowledge to fill gaps where the context is silent"*).
- **Code Path**: `rag/qa.py:349-436` (`build_prompt`) & `rag/llm.py:71-80` (`SYSTEM_MESSAGE`)
- **Why It Helps**: Strongly discourages instruction-tuned LLMs from answering out-of-context queries using pretrained knowledge.
- **Limitations**: Soft prompt steering cannot guarantee 100% adherence. Under ambiguous prompts or strong internal priors, small models (3B parameters) can still leak external facts.
- **How to Test**: Ask: *"Who was the president of the United States in 2020?"* using a computer science PDF. The model should refuse rather than answer.

---

### Mechanism 3: Fast-Filter Gate (V7)
- **Implementation**: Deterministic pre-validation stage evaluating 6 semantic dimensions (actor, target, event, polarity/negation, temporal order, subject-object directionality).
- **Code Path**: `rag/fast_filter.py:1-120` & `rag/qa.py:718-750`
- **Why It Helps**: Catches obvious mismatches (e.g. inverted actions, opposite polarities, missing entities) in Python before invoking the expensive LLM. Returns `FAST_REJECT` or `FAST_ACCEPT`.
- **Limitations**: Relies on surface lexical tokens, dependency indicators, and regex patterns; complex idiomatic or indirect assertions may bypass the filter.
- **How to Test**: Query an inverted causal claim: *"Did Alice kill Bob?"* when the text states *"Bob killed Alice"*. Fast filter detects directionality inversion and issues `FAST_REJECT`.

---

### Mechanism 4: LLM-as-a-Judge Evidence Validation (`validate_evidence`)
- **Implementation**: When the fast filter is ambiguous (`NEEDS_LLM_VALIDATION`), Qwen is prompted to act as an independent evidence validator. It outputs structured JSON conforming to `ValidatorSchema(supported: bool, confidence: float)` enforced via constrained token decoding (`prefix_allowed_tokens_fn`).
- **Code Path**: `rag/llm.py:647-730` & `rag/qa.py:772-790`
- **Why It Helps**: Separates evidence validation from answer generation. The validator assesses whether the evidence establishes the claim without attempting to compose an answer.
- **Limitations**: Uses the same underlying Qwen-2.5-3B model; correlated reasoning errors between the validator and generator are possible.
- **How to Test**: Ask a question with an unmentioned premise (e.g. *"Did Dracula regret his actions?"*). The validator returns `{"supported": false, "confidence": 0.95}`.

---

### Mechanism 5: Deterministic Prompt Rewriting on Refusal
- **Implementation**: If evidence validation yields `NOT_SUPPORTED`, the generator prompt is discarded and replaced with a strict refusal prompt instructing Qwen to state that the passages do not establish the information.
- **Code Path**: `rag/qa.py:802-820`
- **Why It Helps**: Prevents Qwen from attempting to "answer" when evidence is lacking. The task is transformed into communicating an evidence limitation.
- **Limitations**: If the validator makes a false-negative error, valid questions receive an unnecessary refusal.
- **How to Test**: Submit an unanswerable query. Observe that the returned text is an exact 1-sentence limitation notice.

---

### Mechanism 6: Repetition & Logit Processor Suppression
- **Implementation**: Custom logits processor (`AnswerRepetitionControl`) bans 3-gram repetitions in the generated answer while leaving prompt tokens copyable. Greedy decoding is enforced (`temperature = 0.0`, `do_sample = False`).
- **Code Path**: `rag/llm.py:424-427`, `rag/decoding.py`
- **Why It Helps**: Eliminates repetitive looping hallucinations, degenerate runaway completions, and non-deterministic variability across identical requests.
- **Limitations**: Does not prevent factually incorrect single-shot claims.
- **How to Test**: Generate answers with high `max_tokens`; observe zero phrase cycling or repetition loops.

---

### Mechanism 7: Cross-Encoder Reranking
- **Implementation**: Reranks top 10–20 candidates with `cross-encoder/ms-marco-MiniLM-L-6-v2`. Computes query-passage cross-attention, fusing it into a hybrid score:
  $$\text{Score} = 0.30 \times \text{CE} + 0.55 \times \text{Evidence} + 0.15 \times \text{FAISS}$$
- **Code Path**: `rag/reranker.py:293-306, 406-432`
- **Why It Helps**: Replaces crude bi-encoder vector cosine similarity with deep cross-attention, filtering out vector false positives that share vocabulary but lack semantic relevance.
- **Limitations**: Cross-encoder context is limited (512 tokens); chunks longer than 512 tokens are truncated during scoring.
- **How to Test**: Inspect `timing_ms` and candidate ranks in `diagnose_retrieval.py`; verify that relevant passages jump from rank 12 to rank 1.

---

### Mechanism 8: Metadata & Tenant Scope Filtering
- **Implementation**: Strict physical index isolation. Queries for private documents mount only that document's private index (`runtime.faiss`). Institutional book queries are filtered by `work_id`.
- **Code Path**: `rag/services/private_documents.py:221-234`, `rag/retriever.py:175-210`
- **Why It Helps**: Eliminates cross-document and cross-library contamination. The vector search cannot return passages from another user's document or another book.
- **Limitations**: Does not prevent intra-document confusion (e.g. confusing Chapter 1 with Chapter 12 of the same document).
- **How to Test**: Select Document A and ask a question about Document B. System returns: *"I couldn't find enough information in the uploaded documents to answer this question."*

---

### Mechanism 9: Post-Generation Verdict Reconciliation
- **Implementation**: If a book is selected and the generated answer text contains refusal phrases (*"no information provided"*, *"not enough information"*, *"cannot answer"*), the API forces `result["verdict"] = "NOT_SUPPORTED"`.
- **Code Path**: `rag/api.py:258-266`
- **Why It Helps**: Guarantees consistency between generation text and API response metadata, ensuring client UIs do not display green "Supported" badges next to refusal text.
- **Limitations**: String matching heuristics can miss atypical refusal phrasing.
- **How to Test**: Trigger an unanswerable query in book QA; verify `result["verdict"] == "NOT_SUPPORTED"`.
