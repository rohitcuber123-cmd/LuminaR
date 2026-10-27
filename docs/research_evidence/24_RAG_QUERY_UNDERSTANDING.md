# RAG Query Understanding & Multi-Turn Behavior Evidence

> **Audit Context**: LuminaR Research Evidence Audit — Part 5  
> **Source Files Verified**:
> - `rag/api.py` (Lines 110–140, 194–266)
> - `rag/qa.py` (Lines 540–640)
> - `frontend/src/lib/api.ts` (Lines 815–836)
> - `assistant/state.py` (Lines 12–57)
> - `assistant/orchestrator.py` (Lines 799–811)
> - `assistant/contextual.py` (Lines 1–17)

---

## 1. Multi-Turn Query Evaluation Matrix

To assess how LuminaR handles multi-turn conversational interactions, we trace five canonical sequential conversational turns against the codebase:

| User Turn | Chat History Sent to RAG? | Query Rewritten? | What Vector Retrieval Receives | Pronouns / Deictics Resolved? | Resource Scope Persists? | Outcome / Failure Mode |
| :--- | :---: | :---: | :--- | :---: | :---: | :--- |
| **1. "What is paging?"** | N/A (Turn 1) | No | `"What is paging?"` | None required | Yes (`doc_id` / `work_id`) | **SUCCESS**: Topical retrieval and grounded definition. |
| **2. "Explain it more simply."** | **NO** | **NO** | `"Explain it more simply."` | **NO** ("it" unresolved) | **YES** | **RETRIEVAL FAILURE**: FAISS searches for the literal words *"explain"*, *"simply"*. No mention of *paging*. |
| **3. "What are its disadvantages?"** | **NO** | **NO** | `"What are its disadvantages?"` | **NO** ("its" unresolved) | **YES** | **CONTEXT FAILURE**: Retrieves random chunks discussing *"disadvantages"* across unrelated chapters. |
| **4. "Compare it with segmentation."** | **NO** | **NO** | `"Compare it with segmentation."` | **NO** ("it" unresolved) | **YES** | **PARTIAL RETRIEVAL**: Retrieves *segmentation* chunks, but misses *paging* chunks unless co-occurring. |
| **5. "Explain the previous topic again."** | **NO** | **NO** | `"Explain the previous topic again."` | **NO** ("previous topic" unresolved)| **YES** | **TOTAL FAILURE**: FAISS searches for literal meta-phrases. Evidence check triggers refusal. |

---

## 2. Code Verification of Statelessness

### A. RAG API Request Schema Lacks History
In `rag/api.py:110-120`:
```python
class RAGRequest(BaseModel):
    query: str | None = None
    question: str | None = None
    depth: str = "normal"
    document_id: str | None = None
    work_id: str | None = None
```
- **Finding**: The `RAGRequest` schema contains **zero fields** for conversation turns, message history, previous QA pairs, or conversational context.
- **Frontend Invocation**: In `frontend/src/lib/api.ts:818-835`, `askRAG()` constructs only `{ query, depth, document_id/work_id }`. No past chat turns are serialized.

### B. Direct Message Forwarding in Assistant Orchestrator
Even when the user interacts through the top-level chat assistant (`POST /assistant/chat`), the orchestrator forwards the raw string verbatim to RAG:
```python
# assistant/orchestrator.py:802 & 809
elif intent == Intent.BOOK_CONTENT_QUESTION:
    response.rag = await tools.rag.ask(request.message, work_id=books[0].work_id)

elif intent == Intent.DOCUMENT_QUESTION:
    response.rag = await tools.rag.ask(request.message, document_id=request.page_context.document_id)
```
- **Finding**: While `ConversationStore` maintains two compact `semantic_turns` for structured catalog intents (borrowing, returning, fine inquiries), **RAG content questions are NOT rewritten**. `request.message` is passed directly and immutably into `tools.rag.ask()`.

### C. Resource Persistence
- **Finding**: While the linguistic query is stateless, the **selected resource scope does persist**:
  - In private document chat, `document_id` remains bound to the active tab.
  - In book chat, `work_id` remains stored in `state.selected_work_ids` or `request.page_context`.
  - All multi-turn queries remain strictly scoped to the same document/book index, preventing cross-document contamination even when pronoun resolution fails.

---

## 3. Query Preprocessing in the Retrieval Pipeline

When a query arrives at `rag/reranker.py:125-210`:

```python
def search(self, query, top_k=FINAL_K, document_id=None, work_id=None, intent_data=None):
    query = str(query).strip()
    if not query:
        return {"query": query, "work_id": work_id, "results": []}

    is_book_rag = bool(work_id and work_id != document_id)
    if work_id and not document_id:
        is_book_rag = True

    if is_book_rag:
        retrieval_queries = generate_expanded_queries(query)
    else:
        retrieval_queries = [query]
```

### Preprocessing Mechanisms Present:
1. **String Normalization**: Leading/trailing whitespace stripping (`query.strip()`).
2. **Intent Data Extraction**: `analyze_intent(question)` parses actors, targets, events, temporal markers, and negation for downstream filtering.
3. **Multi-Query Concept Expansion (Books only)**:
   - In `rag/evidence.py`, `generate_expanded_queries(query)` maps extracted keywords across morphological variants and synonym roots defined in `CONCEPT_MAP` (e.g. `create` $\to$ `creation`, `created`).
   - Private documents do **NOT** expand queries (`retrieval_queries = [query]`).

### Preprocessing Mechanisms ABSENT:
- **No Conversational Query Rewriting**: Does not reformulate conversational follow-ups into standalone search queries.
- **No Coreference / Pronoun Resolution**: Pronouns (`it`, `they`, `them`, `its`, `this`, `that`) are treated as literal query tokens or stopwords.
- **No Anaphora Resolution**: Deictic phrases (*"the previous topic"*, *"the above method"*, *"what we just discussed"*) are not resolved to previous message entities.
- **No Spelling / Typo Correction**: Queries with misspelled domain terms are encoded directly into vector space without correction.
