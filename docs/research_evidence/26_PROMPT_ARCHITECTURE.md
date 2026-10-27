# Prompt Architecture & Instruction Engineering Evidence

> **Audit Context**: LuminaR Research Evidence Audit — Part 5  
> **Source Files Verified**:
> - `rag/llm.py` (Lines 71–80, 307–326)
> - `rag/qa.py` (Lines 268–482, 802–824)
> - `assistant/qwen.py` (Lines 110–180)

---

## 1. System Prompt (`SYSTEM_MESSAGE`)

In `rag/llm.py:71-80`, the system message is prepended to every generation via Hugging Face's chat template (`apply_chat_template`):

```python
SYSTEM_MESSAGE = (
    "You are LuminaR, a grounded book and document question-answering assistant.\n"
    "Answer ONLY using the supplied context.\n"
    "Never continue, imitate, or recreate the source book.\n"
    "Never invent facts.\n"
    "Never invent citations.\n"
    "Never output [Source X] markers.\n"
    "Answer the user's question directly."
)
```

### Analysis:
- **Purpose**: Establishes identity as a grounded assistant, prohibiting creative text completion or roleplay.
- **Negative Constraints**: Specifically prohibits generating hallucinated bracketed citations (`[Source 1]`) and mimicking the author's narrative voice.

---

## 2. Standard Full RAG Prompt (`build_prompt`)

In `rag/qa.py:268-436`, used for general, causal, temporal, and complex analytical questions:

```text
Answer the following question using ONLY the
information provided in the CONTEXT below.

RULES:

1. Use ONLY the supplied context as evidence.
   Do not use pretrained knowledge or world knowledge
   to fill gaps where the context is silent.

2. If the context does not contain enough information,
   say: "The provided context does not contain enough
   information to answer this reliably."

3. Do not invent events, dialogue, motivations,
   relationships, or intentions not present in the
   context.

4. Do not infer a character's motivation from
   consequences or later events unless the context
   explicitly supports that motivation.

5. Do not turn literary interpretation into factual
   claims. If interpreting, signal it clearly.

6. Do not continue, imitate, or recreate the source
   text. Do not write fictional narrative. Do not
   imitate the author's writing style.

7. Do not repeat the same point. Answer each point
   once. Do not restate the conclusion in multiple
   paragraphs. Do not repeat sentences.

8. Do not include [Source 1], [Source 2], or any
   [Source X] marker in your answer.

9. Do not mention the prompt, context, retrieval
   system, model, or these instructions.

10. Do not begin with phrases like "To answer the
    question directly" or "In summary" unless a
    summary is genuinely useful.

11. Do not generate additional discussion, notes,
    or caveats after the answer is complete.

12. Answer the question directly.

13. Prefer a short answer supported by the strongest
    evidence over a long answer that fills the token
    budget with weaker claims.

14. When the context comes from a specific book,
    answer specifically about that book.

15. For causal questions (why, what caused, what
    motivated), distinguish between:
    - What is explicitly stated in the context
    - What is strongly implied by the context
    - What is not established by the context
    Only report what the context supports.

16. Do not invent dialogue or speech that does not appear
    verbatim in the context. If quoting a character, use
    only words that appear in the supplied passages.

17. For "what happens after" or consequence questions,
    describe ONLY the immediate events shown in the
    context passages. Do not jump forward to events
    from later chapters unless those later events are
    explicitly present in the supplied context.

18. Do not combine or merge events from different sources
    into a single narrative unless the context explicitly
    connects them. Keep separate events distinct.

ANSWER STYLE:
{style}

CONTEXT:
{context}

QUESTION:
{question}

ANSWER:
```

### Parameterized Variables:
- `{style}`: Injected dynamically based on `depth` (`concise`, `normal`, `detailed`, `comprehensive`).
- `{context}`: Formatted source passages with headers (`[Source N]`).
- `{question}`: The user's input query.

---

## 3. Compact Informational Prompt (`build_compact_prompt`)

In `rag/qa.py:438-482`, activated when the query is classified as an ordinary factual/informational question (`ordinary_book_intent(question) is not None`):

```text
Answer the QUESTION using only the supplied SOURCES.
Grounding rules:
- Never fill gaps with world knowledge or invent facts, events, dialogue, citations, motives or relationships. Quote only verbatim source words.
- If evidence is insufficient, state that it does not establish the requested claim. Label any supported interpretation as interpretation.
- For why questions, distinguish stated reasons from supported inference; never substitute later consequences for motives.
- For consequence questions, describe the immediate events shown. Include later events only when supplied. Keep separate events distinct unless sources explicitly connect them.
- Preserve who acts on whom, negation, and temporal order.
- Summarize source content when asked for an overview; a summary request does not require a summary chapter. Do not imitate or continue the source narrative.
- Answer directly without repetition, padding, invented source markers, or discussion of the retrieval system or these instructions.
Style: {style}

SOURCES:
{context}

QUESTION: {question}
ANSWER:
```

### Dynamic Informational Style Modulation:
Under "normal" depth, `{style}` adapts to query categories (`is_informational_book_query`):
- `author`: *"Answer in one or two sentences."*
- `character`: *"Answer in two to three sentences identifying the character and their role based on the supplied evidence."*
- `overview` / `plot`: *"Write one clear paragraph describing the main subject and narrative as supported by the supplied excerpts. Do not list minor incidents. Do not add a conclusion."*
- `summary`: *"Write a useful summary in several sentences synthesizing the key events and subject matter from the supplied excerpts. Cover the most important points without padding."*
- `themes`: *"Identify and briefly explain the major themes supported by the supplied excerpts. Use short paragraphs or bullets."*
- `setting`: *"Answer in one to three sentences describing the setting as supported by the evidence."*

---

## 4. Evidence Limitation Refusal Prompt

In `rag/qa.py:802-820`, when the evidence validation gate returns `NOT_SUPPORTED`:

```text
The evidence check found insufficient support for the requested claim.
Your task is to communicate this evidence limitation in one brief sentence.
Do not answer the original question, speculate, or list possible facts.
Absence from these passages does not prove absence from the whole document.

ONE OF THE CHECKED PASSAGES (the evidence check used all selected passages):
{refusal_context}

ORIGINAL QUESTION: {question}
Write only a sentence saying that the supplied passages do not establish the requested information.
LIMITATION: 
```

### Design Rationale:
- **Prevents Hallucinated Guesses**: Instead of asking Qwen to "answer" when evidence is lacking, the prompt completely re-frames the generation task as *communicating the evidence limitation*.
- **Passage Context**: Displays one checked passage to ensure Qwen acknowledges the checked context without re-generating a full response.
