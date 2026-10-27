# RAG Grounding & Abstention Behavior Evidence

> **Audit Context**: LuminaR Research Evidence Audit — Part 5  
> **Source Files Verified**:
> - `rag/qa.py` (Lines 648–690, 755–790, 802–824)
> - `rag/fast_filter.py` (Lines 1–120)
> - `rag/llm.py` (Lines 647–730)
> - `rag/api.py` (Lines 254–266)

---

## 1. What Happens When an Answer Is Not Present?

When a user submits an out-of-corpus question (e.g. asking about quantum computing using an Operating Systems textbook, or asking about a fictional event not in the text), LuminaR follows a multi-tiered abstention flow:

```
User Asks Out-of-Corpus Question
                |
                v
       Vector Search (FAISS)
                |
      +---------+---------+
      |                   |
No Chunks Found    Chunks Retrieved (Irrelevant)
      |                   |
      v                   v
Immediate Abstention   Fast Filter Gate
(qa.py:651)               |
"I couldn't find..."      +---------+---------+
                          |                   |
                     FAST_REJECT     NEEDS_LLM_VALIDATION
                          |                   |
                          |                   v
                          |          LLM-as-a-Judge Validator
                          |          {"supported": false}
                          |                   |
                          +---------+---------+
                                    |
                                    v
                           verdict = NOT_SUPPORTED
                                    |
                                    v
                         Refusal Prompt Activated
                                    |
                                    v
                   Qwen Generates Single-Sentence Refusal:
        "The supplied passages do not establish the requested information."
                                    |
                                    v
                   API Post-Processor Reconciliation:
                       verdict = "NOT_SUPPORTED"
```

---

## 2. Behavioral Verification Against the Five Audited Questions

| System Action | Does LuminaR Do This? | Code Mechanism / Exact String |
| :--- | :---: | :--- |
| **Still Answer / Guess?** | **NO** (Suppressed) | Blocked by `FAST_REJECT`, `validate_evidence()`, and prompt rules. |
| **Use Qwen Internal Knowledge?** | **NO** (Prohibited) | Explicitly forbidden by System Message & Rule 1 (*"Never fill gaps with world knowledge"*). |
| **Abstain / Refuse?** | **YES** | Primary design pattern: emits structured evidence limitation statements. |
| **Ask Clarification?** | **Conditional** | In the top-level Assistant (`/assistant/chat`), raises `NeedsClarification` if multiple books are active (`orchestrator.py:801`). In direct `/rag/ask`, it abstains rather than asking clarification. |
| **Say Insufficient Context?** | **YES** | Standard phrasing: *"The provided context does not contain enough information to answer this reliably"* or *"I couldn't find enough information in this book to answer this question."* |

---

## 3. The Four Abstention Gates in Active Code

### Gate 1: Empty Retrieval Abstention
When vector search finds no matching chunks in the scoped index:
```python
# rag/qa.py:651-667
if not results:
    if work_id:
        message = "I couldn't find enough information in this book to answer this question."
    else:
        message = "I couldn't find enough information in the uploaded documents to answer this question."
    return {
        "question": question,
        "answer": message,
        "sources": [],
        "depth": depth,
        "work_id": work_id
    }
```
- **Execution**: Terminates synchronously before invoking the cross-encoder, fast filter, validator, or generation model. GPU inference is completely bypassed.

### Gate 2: Deterministic Fast Filter Rejection
When retrieved chunks are present but fail core entity/polarity/temporal alignment:
```python
# rag/qa.py:757-763
if fast_filter_decision_val == "FAST_REJECT":
    verdict = "NOT_SUPPORTED"
    validation_result = {
        "verdict": "NOT_SUPPORTED",
        "details": {},
        "fast_filter": "FAST_REJECT"
    }
```
- **Execution**: Flags the query as `NOT_SUPPORTED` deterministically in Python without calling Qwen as a validator.

### Gate 3: LLM Validator Refusal Gate
When the fast filter is ambiguous, Qwen validates evidence sufficiency using constrained schema decoding:
```python
# rag/llm.py:717-720
"Rules:\n"
"- For unsupported premises, prefer false over speculative inference.\n"
"- supported=true requires evidence to fully answer the query, accounting for any negations or specific conditions.\n\n"
"Does the provided evidence support the structured query?"
```
- If Qwen outputs `{"supported": false, "confidence": ...}`, `qa.py:802-820` catches the verdict:
```python
if verdict == "NOT_SUPPORTED":
    refusal_context = used_items[0].get('text', '') if used_items else context
    prompt = f'''The evidence check found insufficient support for the requested claim.
Your task is to communicate this evidence limitation in one brief sentence.
Do not answer the original question, speculate, or list possible facts.
Absence from these passages does not prove absence from the whole document.

ONE OF THE CHECKED PASSAGES:
{refusal_context}

ORIGINAL QUESTION: {question}
Write only a sentence saying that the supplied passages do not establish the requested information.
LIMITATION: '''
```

### Gate 4: API Response Verdict Reconciliation
In `rag/api.py:258-266`, as a final safeguard against subtle model non-compliance:
```python
answer = str(result.get("answer") or "").casefold()
if selected_book and (
    "no information provided" in answer
    or "not enough information" in answer
    or "cannot answer" in answer
):
    result["verdict"] = "NOT_SUPPORTED"
```
- Even if upstream flags did not mark the query as unsupported, the presence of standard refusal substrings overrides the verdict to `"NOT_SUPPORTED"`.
