# Quiz Generation Algorithms Evidence

> **Audit Context**: LuminaR Research Evidence Audit — Part 6  
> **Source Files Verified**:
> - `rag/services/knowledge_quiz.py` (Lines 1–303)
> - `rag/services/knowledge_mcq.py` (Lines 1–132)
> - `rag/services/knowledge_match.py` (Lines 1–105)
> - `rag/services/knowledge_cloze.py` (Lines 1–76)
> - `rag/services/cloze_grading.py` (Lines 1–211)
> - `frontend/src/components/knowledge/Quiz.tsx` (Lines 1–110)

---

## 1. Multiple Choice Questions (MCQ) Algorithm

### A. Source Fact & Stem Formulation
In `rag/services/knowledge_mcq.py:10-27`, question stems are dynamically synthesized from relation metadata:
```python
def stem(record, identify, qid):
    if identify:
        return f'Which concept is defined by this source description: “{record["targetText"]}”?'
    elif record['relationType'] == 'DEFINITION':
        return (f'Which description best defines {record["subjectText"]}?' if int(qid[-1], 16) % 2
                else f'According to the document, how is {record["subjectText"]} defined?')
    elif record['relationType'] == 'PURPOSE':
        return f'What is {record["subjectText"]} used for according to the document?'
    elif record['relationType'] == 'PROCESS':
        return f'Which step is specified for {record["subjectText"]}?'
    elif record['relationType'] == 'COMPOSITION':
        return f'What does {record["subjectText"]} consist of according to the document?'
```

### B. Distractor Selection & Category Grouping
To ensure pedagogically sound distractors that do not produce absurd or obvious eliminations:
1. **Peer Distractor Pool**: Mined exclusively from peers in the same document sharing the exact same relation family and category:
   ```python
   peers = [x for x in relations if x is not record and r.compatible(record, x, relations)]
   strict = [x for x in peers if record.get('category') and x.get('category') == record['category']]
   if len(strict) >= 3:
       peers = strict
   ```
2. **Category Extraction**: Extracts explicit domain categories (e.g. `"a scheduling algorithm that..."` $\to$ category: `'scheduling algorithm'`).
3. **Rotation**: Peer pool is shuffled per record ID (`record['id'] + str(seed)`) to prevent the same 3 distractors from dominating the entire quiz.

### C. Rigorous Correctness Verification (`verify()`)
Every generated candidate MCQ must pass a multi-point verification suite (`knowledge_mcq.py:50-73`):
- `SOURCE_BINDING`: Relation record exists and is bound to source text.
- `STEM_ANSWER_BINDING`: Stem matches record subject and relation type.
- `ANSWER_KEY`: Expected answer appears exactly once in choices.
- `ANSWER_LEAK`: The answer string cannot appear inside the question stem.
- `SOURCE_PROVENANCE`: Excerpt and page numbers match active relations.
- `OPTION_BINDING`: Every option maps 1:1 to an entry in `optionSources`.
- `DUPLICATE_OPTION`: Options must contain 4 distinct strings.
- `AMBIGUOUS_OPTION`: Options cannot have acronym or label overlaps.
- `MULTIPLE_CORRECT_OR_INCOMPATIBLE`: Distractor relations cannot conflict or overlap with the target relation.

### D. Option Shuffling & Grounding
- **Shuffling**: Options are shuffled deterministically using a seeded pseudo-random generator: `random.Random(qid).shuffle(options)`.
- **Option Provenance**: Every choice (both correct and distractors) includes full source citation in `optionSources`:
  ```json
  "optionSources": {
    "Go-Back-N ARQ": { "sourceExcerpt": "Go-Back-N ARQ uses sliding window...", "pageStart": 14 },
    "Selective Repeat ARQ": { "sourceExcerpt": "Selective Repeat retransmits only...", "pageStart": 15 }
  }
  ```

---

## 2. Match the Following Algorithm

### A. Pair Extraction & Partitioning
In `rag/services/knowledge_match.py`:
- **Relation Families**: Pairs are partitioned by `relationType`:
  - `DEFINITION`: *"Match each concept to its definition."*
  - `PURPOSE`: *"Match each mechanism to its purpose."*
  - `PROPERTY`: *"Match each concept to its characteristic."*
  - `FUNCTION`: *"Match each component to its function."*
  - `COMPOSITION`: *"Match each item to its composition."*
  - `PROCESS`: *"Match each process to its specified step."*
- **Block Size**: Questions contain between 3 and 6 pairs (`3 <= len(leftItems) <= 6`).

### B. Ambiguity & Bijection Filtering
In `knowledge_match.py:15-32` (`verify()`):
- **Bijection Guarantee**: Requires a strict 1-to-1 bijective mapping between Left items and Right items (`NOT_BIJECTION` check).
- **No Duplicate IDs or Texts**: Left and right keys must be completely unique.
- **Pairwise Compatibility**: Evaluates all combinations of selected pairs with `r.compatible(x, y, relations)`. If two concepts share similar descriptions (similarity $\ge 0.72$), the set is rejected (`AMBIGUOUS_PAIR`).

### C. Right-Side Shuffling & Identity Prevention
Right items (Column B) are shuffled with seed `qid`.
Crucially, LuminaR protects against accidental non-shuffled orders:
```python
random.Random(qid).shuffle(right)
# If random shuffling happened to land in the original 1:1 order, rotate by 1:
if [x['id'] for x in right] == list(mapping.values()):
    right = right[1:] + right[:1]
```
Column B is guaranteed to **never** match Column A's straight across row order.

---

## 3. Fill in the Blank Algorithm

### A. Extraction & Formatting
In `rag/services/knowledge_cloze.py`:
- Mines validated single-sentence fact statements.
- Finds canonical answer terms and replaces them with a single `_____` placeholder.
- Classifies blank type: `TERM`, `ENTITY`, `SHORT_PHRASE`, `NUMBER`, `NUMBER_WITH_UNIT`, `DESCRIPTION`.

### B. Alias & OCR Filtering
- **Alias Resolution**: Automatically detects parenthetical abbreviations:
  ```python
  aliases("Transmission Control Protocol", "Transmission Control Protocol (TCP) provides...")
  # acceptedAliases: ["TCP"]
  ```
- **OCR Quality Guard**: Rejects sentences if OCR resulted in merged digits/letters (e.g. `l1` or `O0`).

### C. Automated Short-Answer Grading (`cloze_grading.py`)
User responses are evaluated through a layered deterministic grading pipeline:
1. **Exact Match**: Case-insensitive, article-stripped match.
2. **Accepted Aliases**: Direct match against pre-extracted aliases.
3. **Numeric & Unit Equivalence**: Parses numbers and dimensions (e.g., `1000 ms` $\equiv$ `1 s`; `50%` $\equiv$ `0.5`).
4. **Typo Tolerance**: Allows 1 edit distance typo for words with $\ge 6$ letters; short words and acronyms must remain exact.
5. **Negation Check**: Rejects any answer containing negated words (`not`, `never`, `cannot`).
6. **Semantic Description Grading**: For descriptive answers, queries `SemanticCache` using `MiniLM` cosine similarity with a high confidence threshold ($\ge 0.85$).

---

## 4. Multi-Select UI & Question Distribution

### A. Multi-Select UI Handling
In `frontend/src/components/knowledge/KnowledgeTools.tsx:125-137`:
- Renders independent checkboxes for each question format:
  - `[x] Multiple Choice` (`mcq`)
  - `[x] Fill in the Blanks` (`fill_blank`)
  - `[x] Match the Following` (`matching`)
- User can select any combination (e.g., MCQ only, Matching only, or all three).
- If none are selected, "Generate Quiz" is disabled.

### B. Fair Distribution & Balanced Allocation
In `rag/services/knowledge_quiz.py:257-288`:
1. **Balanced Budget**: Computes target allocation per format:
   $$\text{balanced\_limit} = \max\left(1, \frac{\text{questionCount} + |\text{types}| - 1}{|\text{types}|}\right)$$
2. **Matching Pair Allocation**:
   - Matching is allocated by **individual pairs**, not by whole question blocks. A 4-pair matching question counts as 4 learning items.
3. **Beam Search & Round-Robin**:
   - Reserves validated matching pairs first.
   - Selects MCQs and Fill-in-the-Blank questions in round-robin fashion.
   - Enforces disjoint fact sets: no two questions can test the exact same source fact or concept.

### C. Cache Identity
Quiz artifacts are cached under an exact options identity:
```json
{
  "questionCount": 12,
  "questionTypes": ["fill_blank", "matching", "mcq"]
}
```
Changing the checkbox selection or question count prompts a new targeted generation or loads the corresponding cached variant.
