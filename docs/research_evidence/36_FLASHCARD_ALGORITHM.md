# Flashcard Generation Algorithm Evidence

> **Audit Context**: LuminaR Research Evidence Audit — Part 6  
> **Source Files Verified**:
> - `rag/services/document_knowledge.py` (Lines 1–89, 464–498)
> - `rag/services/knowledge_algorithms.py` (Lines 11–22, 70–89, 167–191)
> - `rag/services/knowledge_cloze.py` (Lines 1–76)
> - `frontend/src/components/knowledge/KnowledgeTools.tsx` (Lines 20–50)

---

## 1. Algorithm Overview

Flashcard generation in LuminaR is completely deterministic, rule-governed, and extractive. No generative LLM is used. The engine mines high-confidence definitions, processes, applications, and cloze statements directly from document sentences.

```
Raw Document Chunks
       |
       v
Sentence Splitting & Quality Filtering (length, alpha ratio, verbal predicate)
       |
       +-----------------------+-----------------------+
       |                                               |
       v                                               v
Definition Extraction (Regex)                Cloze Extraction (Regex)
  "X is defined as Y"                          "X _____ Y" (single-blank)
       |                                               |
       +-----------------------+-----------------------+
                               |
                               v
               Deduplication & Quality Gates
           (No duplicate fronts, no OCR noise)
                               |
                               v
                     Final Flashcards (Max 40)
       [Definition: 20] + [Cloze / Relation / Process: 20]
```

---

## 2. Definition Patterns & Extraction Rules

### A. Core Definition Regex
In `rag/services/knowledge_algorithms.py:14`:
```python
DEFINITION = re.compile(
    r'^((?:[A-Za-z][A-Za-z0-9-]*\s+){0,5}[A-Za-z][A-Za-z0-9-]*)\s+'
    r'(is defined as|refers to|consists of|is used for|means|is|are)\s+'
    r'(.+?[.!?])$',
    re.I | re.S
)
```

### B. Syntactic & Semantic Constraints
To qualify as an accepted definitional fact:
1. **Subject Constraints**:
   - Strips leading determiners (`The`, `A`, `An`).
   - Word count: 1 to 5 words (`valid_phrase()`, lines 32–38).
   - Character count: 3 to 65 characters.
   - Stop words: First and last word cannot be stop words (`words[0] not in STOP and words[-1] not in STOP`).
   - Verbs: Cannot contain structural verbs (`VERBS = {'allows', 'provides', 'enables', 'uses', ...}`).
2. **Predicate / Relation Constraints**:
   - Relation must match: `"is defined as"`, `"refers to"`, `"consists of"`, `"is used for"`, `"means"`, `"is"`, `"are"`.
   - If relation is `"is"` or `"are"`, the predicate answer must begin with an indefinite/definite noun phrase (`a`, `an`, `the`, `both`) to distinguish true identity definitions from descriptive assertions (`document_knowledge.py:273`).
3. **Answer Constraints**:
   - Word count: Between 4 and 45 words (`4 <= len(WORD.findall(answer)) <= 45`).
   - Character count: $\le 320$ characters.
   - Circularity filter: The subject cannot be contained verbatim in the answer text (`key not in answer_key`).
   - Non-qualifier filter: Cannot begin with vague adverbs (`not`, `also`, `often`, `sometimes`, `usually`, `one`, `another`, `important`, `useful`).

---

## 3. Cloze Algorithm

In `rag/services/document_knowledge.py:475-481` and `rag/services/knowledge_algorithms.py:174-189`:

### A. Candidate Selection
- Candidates are mined from:
  1. Key concept labels (`key_concepts`).
  2. Extracted definitional subjects (`definitions(rows)`).
  3. Narrow factual phrases (`explicit_cloze_phrases`, e.g., `"uses a fixed time quantum"`).

### B. Masking & Context Verification
1. **Exact Word Boundary Matching**:
   ```python
   pattern = re.compile(r'(?<!\w)' + r'\s+'.join(re.escape(w) for w in label.split()) + r'(?!\w)', re.I)
   matches = list(pattern.finditer(row['text']))
   ```
2. **Single Occurrence Rule**:
   - The phrase must appear **exactly once** in the sentence (`len(matches) == 1`). If a phrase appears multiple times, the sentence is rejected to avoid ambiguous blanking.
3. **Substantial Context Rule**:
   - The remaining context must have $\ge 6$ words after subtracting the label:
     $$\text{len}(\text{words in sentence}) - \text{len}(\text{words in label}) \ge 6$$
4. **Substitution**:
   - Front: `row['text'][:match.start()] + '_____' + row['text'][match.end():]`
   - Back: `match.group()` (the verbatim original phrase).

---

## 4. Quality Filtering & Gatekeeping

Sentences must pass the strict `quality_text()` validator (`document_knowledge.py:69-78`):
- **Length**: $30 \le \text{character count} \le 650$.
- **Word Count**: $6 \le \text{word count} \le 90$.
- **Terminal Punctuation**: Must end with `.`, `!`, or `?` followed by optional quotes; cannot end with a colon (`:`).
- **Alphabetic Ratio**: $\ge 0.52$ of characters must be letters.
- **Corrupt Character Check**: Rejects Unicode replacement characters (`\ufffd`), HTTP/HTTPS URLs, curly braces, ellipsis runs (`(?:\.\s*){4}`), or repetitive character runs (`(.)\1{5,}`).
- **Deictic / Relative Reference Filter**: Rejects sentences containing `"above figure"`, `"below diagram"`, `"since then"`, `"here"`, or procedural lead-ins (`"steps performed as follows:"`).
- **Verbal Requirement**: Must contain at least one recognized verb from the `VERBAL` lexicon.

---

## 5. Deduplication & Conflict Rejection

1. **Front Normalization**: Every candidate front is normalized to lowercase alphanumeric tokens.
2. **Conflicting Template Filter**:
   ```python
   templates = Counter()
   for card in candidates:
       templates[normalize(card['front'])] += 1
   cards.extend(c for c in candidates if templates[normalize(c['front'])] == 1)
   ```
   If two different sentences or concepts yield identical cloze prompts, **both are discarded**.
3. **Duplicate Evidence Suppression**: If an accepted fact is already used as a definition card, it cannot be reused as a process or application card.

---

## 6. Limits, Source Grounding, and Cache

| Attribute | Specification |
| :--- | :--- |
| **Maximum Total Cards** | **40 cards** (`cards[:40]` in `document_knowledge.py:498`) |
| **Maximum Definition Cards**| **20 cards** (`definitions(rows)[:20]`) |
| **Source Grounding** | Every card carries: `id`, `concept`, `front`, `back`, `sourceExcerpt`, `knowledgeItemId`, `sources: [{chunkId, page}]`, `pageStart`, `pageEnd` |
| **Card Types Supported** | `definition`, `cloze`, `concept`, `relationship`, `process`, `application` |
| **Storage & Caching** | Serialized to JSON (`artifacts/flashcards.json` or `generation/<id>/artifacts/flashcards.json`). Re-read on subsequent loads (`cached: true`). |
| **Frontend UI Interaction** | Rendered in `Flashcards` component (`KnowledgeTools.tsx:20-50`) with type dropdown filter, keyboard shortcuts (`Space`/`Enter` to flip, `ArrowLeft`/`ArrowRight` to navigate), and `SourceLink` modal. |
