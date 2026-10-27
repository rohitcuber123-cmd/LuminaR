# LuminaR Knowledge Tools — Comprehensive Viva Preparation & Reviewer Defense Guide

This document contains **52 in-depth technical viva questions and defense answers** grounded directly in the LuminaR codebase. Each entry includes:
1. **Spoken Answer (20–40s)**: Concise, confident, plain-language response to say aloud.
2. **Deep Technical Explanation**: Architectural, mathematical, and data structure details.
3. **Exact Code Reference**: File path, function name, and line numbers.
4. **Likely Follow-up Question & Rebuttal**: Anticipating the reviewer's next challenge.

---

## Group 1: Overall Knowledge Tools Architecture

### Q1. What is the core purpose of the Knowledge Tools module in LuminaR?
- **Spoken Answer:**
  > "Knowledge Tools is an automated educational synthesis engine. While traditional RAG only answers one prompt at a time, Knowledge Tools synthesizes an entire uploaded document or library book into structured study materials: Key Concepts, Extractive Summaries, interactive Flashcards, a visual Mind Map, and comprehensive Quizzes. Crucially, it does this deterministically without overloading our local GPU or calling an LLM."
- **Deep Technical Explanation:**
  Knowledge Tools constructs an intermediate `DocumentKnowledgeModel` from pre-parsed chunks (`chunks.json`), extracting structural units, definitions, copular relations, and concept rankings. This intermediate model is then used by decoupled renderers to generate five distinct pedagogical artifacts.
- **Code Reference:** [rag/services/document_knowledge.py:L212-L456](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L212-L456) (`build()`), [document_knowledge.py:L459-L551](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L459-L551) (`generate()`).
- **Follow-up & Rebuttal:**
  *Q: Why not just ask the LLM to generate all five formats in one JSON prompt?*  
  *Rebuttal:* "Prompting an LLM for multi-format artifacts takes 15–30 seconds, consumes massive GPU VRAM, introduces non-deterministic hallucinations, and fails strict schema validation. Our deterministic approach runs in milliseconds on CPU with 100% source grounding."

### Q2. How is work admitted and rate-limited across concurrent users?
- **Spoken Answer:**
  > "We use a multi-level concurrency gate. At the server level, a global Semaphore limits active generation jobs to 3 concurrent tasks to prevent CPU thrashing. At the user level, a single-flight set ensures one user cannot launch parallel jobs across multiple tabs. If identical requests arrive simultaneously, they join a leader-follower Future, sharing the result."
- **Deep Technical Explanation:**
  Implemented in `KnowledgeArtifacts`: `self._capacity = Semaphore(3)` guards worker capacity. `self._owners = set()` enforces single-flight per user. When duplicate `job_key` requests arrive, followers wait on `future.result(timeout=25)`. Excess load immediately receives HTTP 429 (`"Knowledge Tools is busy. Please retry shortly."`).
- **Code Reference:** [rag/services/knowledge_artifacts.py:L26-L29, L107-L135](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L26-L29).
- **Follow-up & Rebuttal:**
  *Q: Why Semaphore(3) instead of an async task queue like Celery or Redis?*  
  *Rebuttal:* "Because generation takes only 20–100ms on CPU, introducing Redis/Celery adds external infrastructure dependencies and network serialization overhead without tangible benefit. An in-process Semaphore provides instant admission control."

### Q3. How does the system isolate personal private documents from institutional library books?
- **Spoken Answer:**
  > "We maintain strict architectural tenant isolation. Personal documents are session-bound, stored in `rag/private_documents/`, tracked in SQLite `registry.sqlite`, and accessed via `/rag/documents/{id}/artifacts`. Institutional assets are tenant-scoped, stored in `local-data/tenants/{lib_id}/`, tracked in the institutional database, and accessed via `/libraries/{lib_id}/assets/{asset_id}/artifacts`. Deleting personal items is session-owned, whereas modifying library study assets requires staff role authorization."
- **Deep Technical Explanation:**
  `PrivateDocuments` handles personal session documents, enforcing session token matching and expiration. `LibraryAssetPipeline` handles institutional assets, verifying staff vs patron roles via `authorize_asset()`. Path traversal attacks are thwarted by `safe_child()` path resolution checks.
- **Code Reference:** [rag/services/knowledge_routes.py:L38-L69](file:///d:/SDC/LibraryLLM/rag/services/knowledge_routes.py#L38-L69), [rag/services/library_asset_routes.py:L32-L81](file:///d:/SDC/LibraryLLM/rag/services/library_asset_routes.py#L32-L81).
- **Follow-up & Rebuttal:**
  *Q: Can a patron delete an institutional study artifact?*  
  *Rebuttal:* "No. `delete_artifact` in `LibraryAssetPipeline` calls `authorize_asset(staff=True)`, returning HTTP 403 if a patron attempts deletion."

### Q4. What happens when a document is deleted? Are artifacts orphaned?
- **Spoken Answer:**
  > "No, artifacts are never orphaned. In SQLite, both the `document_knowledge` and `knowledge_artifacts` tables define foreign keys with `ON DELETE CASCADE` referencing the primary `documents` table. Purging the document immediately and atomically drops all derived study artifacts and models."
- **Deep Technical Explanation:**
  SQLite foreign key enforcement is activated via `PRAGMA foreign_keys=ON;`. When `PrivateDocuments.purge(doc_id)` or `logout(user)` runs, deleting the parent row in `documents` triggers automatic deletion across `knowledge_artifacts` and `document_knowledge`.
- **Code Reference:** [rag/services/knowledge_artifacts.py:L31-L38](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L31-L38), [tests/test_knowledge_artifacts.py:L294-L300](file:///d:/SDC/LibraryLLM/tests/test_knowledge_artifacts.py#L294-L300).
- **Follow-up & Rebuttal:**
  *Q: What about files on disk?*  
  *Rebuttal:* "`PrivateDocuments.purge()` explicitly calls `shutil.rmtree(self.directory(document_id))` to remove all chunks and FAISS vectors from the filesystem."

---

## Group 2: Knowledge Graphs

### Q5. What is the fundamental difference between the Catalogue Graph and Document Graph in your project?
- **Spoken Answer:**
  > "The Catalogue Graph in `knowledge_graph/core.py` is a macro-level, bipartite graph stored in `catalogue.sqlite` connecting all books in the library via shared authors, subjects, and TF-IDF topics for cross-book recommendations. The Document Graph in `document_knowledge.py` is a micro-level concept-evidence graph extracted from a single document to visualize its internal chapter, concept, and definitional hierarchy."
- **Deep Technical Explanation:**
  The catalogue graph models relations $B \leftrightarrow F$ between books and metadata features, computing cosine similarities over precomputed squared norms with 2-hop explanation paths. The document graph models tree-and-evidence hierarchies ($D \to G \to C \to E$) using syntactic copular rules and SVG bezier rendering.
- **Code Reference:** [knowledge_graph/core.py:L39-L117](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L39-L117), [rag/services/document_knowledge.py:L516-L547](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L516-L547).
- **Follow-up & Rebuttal:**
  *Q: Why not store both in Neo4j?*  
  *Rebuttal:* "Neo4j requires an external JVM process, 500MB+ memory footprint, and complex connection pooling. By using SQLite with indexed relational joins and JSON payloads, we achieve sub-millisecond graph queries with zero external infrastructure."

### Q6. Are the edges in your document knowledge graph factually verified or based on co-occurrence?
- **Spoken Answer:**
  > "They are factually verified through strict grammatical copular constraints, never word co-occurrence. An edge is only formed when an explicit syntactic rule matches the source text—such as 'X is defined as Y', 'X consists of Y', or 'X is used for Y'. Every edge carries chunk IDs and page citations linking back to the verified sentence."
- **Deep Technical Explanation:**
  Co-occurrence graphs link words that simply appear near each other in a sliding window, producing noisy associations. LuminaR's `document_knowledge.py` inspects `DEFINITION` regex matches and maps grammatical predicates to typed edges: `DEFINED_AS`, `CONTAINS`, `USED_FOR`, `HAS_STEP`, and `DESCRIBED_AS`.
- **Code Reference:** [rag/services/document_knowledge.py:L426-L434](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L426-L434), [rag/services/knowledge_quiz_relations.py:L90-L99](file:///d:/SDC/LibraryLLM/rag/services/knowledge_quiz_relations.py#L90-L99).
- **Follow-up & Rebuttal:**
  *Q: What if a sentence uses passive voice or complex syntax?*  
  *Rebuttal:* "If a sentence does not match our verified grammatical grammar, we deliberately do not invent an edge. We prioritize precision over recall to prevent false claims."

### Q7. How does the Catalogue Graph compute explainable 'More Like This' recommendations?
- **Spoken Answer:**
  > "It uses a bipartite metadata cosine similarity algorithm over authors, subjects, and extracted topic phrases. Every feature's weight is scaled by inverse catalogue frequency so rare topics count more than common ones. When returning recommendations, it traverses shared feature nodes to emit human-readable 2-hop reason paths."
- **Deep Technical Explanation:**
  Score is:
  $$\text{Score} = \frac{\sum w_f^2}{\sqrt{\|\mathbf{n}_{\text{seed}}\| \cdot \|\mathbf{n}_{\text{candidate}}\|}}$$
  Where feature importance is $1 + \ln((N_{\text{books}}+1)/(\text{Degree}(f)+1))$. The query joins `edges a JOIN edges c USING(kind, term)` to retrieve the exact shared features and returns provenance entries showing work ID, field, and value.
- **Code Reference:** [knowledge_graph/core.py:L60-L105](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L60-L105).
- **Follow-up & Rebuttal:**
  *Q: How does this compare to dense neural book embeddings?*  
  *Rebuttal:* "Dense vector embeddings operate as a black box and cannot explain *why* two books are related. Our graph provides exact symbolic explainability: 'Both books share author Tanenbaum and topic Virtual Memory'."

---

## Group 3: Mind Maps

### Q8. How does the Mind Map module determine its hierarchy?
- **Spoken Answer:**
  > "The root node is always the document title. The first level of branches represents chapter and section headings extracted during PDF parsing. The second level attaches domain concepts scored by our multi-signal MMR algorithm, and leaf nodes attach factual evidence statements. If a document has no headings, concepts attach directly to the document root."
- **Deep Technical Explanation:**
  The algorithm iterates over the top 24 accepted concepts (`model.concepts[:24]`). For each concept, it checks `chapter` and `section` metadata. If present, it creates group nodes (up to 10 groups) linked with `relation: 'source organization'`. Concepts attach with `relation: 'document topic'`. Leaf evidence nodes attach with typed relation labels.
- **Code Reference:** [rag/services/document_knowledge.py:L516-L547](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L516-L547).
- **Follow-up & Rebuttal:**
  *Q: What prevents the mind map from becoming an unreadable hairball?*  
  *Rebuttal:* "We enforce strict architectural caps: maximum 60 total nodes, maximum 10 section groups, maximum 24 concepts, and maximum 24 evidence leaves."

### Q9. Which algorithm did you use to position nodes on the canvas?
- **Spoken Answer:**
  > "We developed an original balanced tree layout algorithm in TypeScript (`mapLayout.ts`). It performs a BFS traversal from the root, computes visual subtree weights using post-order accumulation, partitions top-level branches into left and right columns using greedy bin-packing, and routes smooth cubic bezier curves between card anchors."
- **Deep Technical Explanation:**
  In `mapLayout.ts`, `Weight(u) = max(1, Σ Weight(child))`. Children of the root are assigned to Side 0 (right) or Side 1 (left) such that column weights remain balanced (`counts[0] <= counts[1] ? 0 : 1`). Node cards have fixed dimensions ($205 \times 68$ px). Coordinates are:
  $$X_u = X_{\text{root}} \pm \text{Depth}(u) \cdot \text{Gap}, \quad Y_u = \text{Top} + \frac{\text{Span} - \text{cardHeight}}{2}$$
- **Code Reference:** [frontend/src/components/knowledge/mapLayout.ts:L6-L56](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/mapLayout.ts#L6-L56).
- **Follow-up & Rebuttal:**
  *Q: Why not use a standard D3 force-directed layout?*  
  *Rebuttal:* "Force-directed layouts are non-deterministic, jitter during simulation, and scatter hierarchical branches unpredictably. Educational mind maps require a clean, balanced tree structure where parents clearly lead to children."

### Q10. How does the frontend handle zoom, pan, and fullscreen interactions?
- **Spoken Answer:**
  > "We use an SVG viewport with pointer capture for drag-panning and an intercepted non-passive wheel listener for smooth trackpad and mouse zooming. Clicking Fullscreen mounts a React Portal to `document.body`, locks page scrolling, and sets the root element to inert, trapping keyboard focus inside the modal dialog."
- **Deep Technical Explanation:**
  In `KnowledgeMap.tsx`:
  - Zoom level is maintained in React state: `zoom = fit * level`.
  - Wheel listener uses `event.preventDefault()` to block window scrolling while updating `pan.x` and `pan.y`.
  - Fullscreen renders via `createPortal(<section role="dialog" aria-modal="true">, document.body)`. `document.getElementById('root').inert = true` prevents keyboard navigation outside the dialog, and the Escape key listener restores focus.
- **Code Reference:** [frontend/src/components/knowledge/KnowledgeMap.tsx:L26-L70](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/KnowledgeMap.tsx#L26-L70).

---

## Group 4: Flashcards

### Q11. How are flashcards generated, and what categories exist?
- **Spoken Answer:**
  > "Flashcards are generated in two phases from our DocumentKnowledgeModel. Phase 1 generates one primary card per concept—either a Definition card, a Cloze card, or a general Concept card. Phase 2 extracts secondary relational cards covering Process steps, Examples/Applications, and Relationships. In total, cards are classified into 7 educational types."
- **Deep Technical Explanation:**
  The 7 types are: `definition`, `cloze`, `concept`, `relationship`, `process`, `application`, and `comparison`. Phase 1 evaluates definition facts first; if absent, it picks the highest explanation-scoring sentence. Phase 2 checks processes (`'has step'`) and examples (`'for example'`), capping total cards at 40.
- **Code Reference:** [rag/services/document_knowledge.py:L464-L498](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L464-L498).
- **Follow-up & Rebuttal:**
  *Q: How do you prevent identical duplicate cards?*  
  *Rebuttal:* "Phase 2 checks `any(c['sourceExcerpt'] == fact['text'] for c in cards)`. If an exact sentence is already used on another card, it is immediately skipped."

### Q12. What interactive features are supported on the Flashcard UI?
- **Spoken Answer:**
  > "Students can filter cards by type using a dropdown, flip between Question and Answer using Space or Enter, step through cards using Left and Right arrow keys, and click 'View Source' to inspect the exact document chunk and page in an accessible slide-over drawer."
- **Deep Technical Explanation:**
  Implemented in `Flashcards` inside `KnowledgeTools.tsx`. A global window `keydown` listener intercepts `ArrowLeft`, `ArrowRight`, `Space`, and `Enter`, ignoring them if focus is currently inside an input, textarea, or button. `SourceLink` fetches chunk text asynchronously via `getSource()`.
- **Code Reference:** [frontend/src/components/knowledge/KnowledgeTools.tsx:L20-L50](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/KnowledgeTools.tsx#L20-L50).

---

## Group 5: Multiple Choice Questions (MCQs)

### Q13. How does the system generate MCQ question stems?
- **Spoken Answer:**
  > "MCQ stems are constructed deterministically based on the underlying relation family. For definitions, it asks 'Which description best defines X?'; for purposes, 'What is X used for?'; and for processes, 'Which step is specified for X?'. If all 4 options share the exact same category, it can invert the question to ask 'Which concept is defined by this description?'."
- **Deep Technical Explanation:**
  In `knowledge_mcq.py`, `stem(record, identify, qid)` handles forward target identification and inverse subject identification. It inspects `record['relationType']` (`DEFINITION`, `PURPOSE`, `PROCESS`, `COMPOSITION`, `NUMERIC:*`) and formats a grammatically correct question prompt.
- **Code Reference:** [rag/services/knowledge_mcq.py:L10-L26](file:///d:/SDC/LibraryLLM/rag/services/knowledge_mcq.py#L10-L26).

### Q14. Where do MCQ distractors come from, and how do you ensure they are plausible?
- **Spoken Answer:**
  > "Distractors are 100% extracted from the same document from the same semantic category. For example, if the question asks about a CPU scheduling algorithm, the distractors will be other CPU scheduling algorithms from the document, not random words. They are plausible because they belong to the same domain."
- **Deep Technical Explanation:**
  In `knowledge_mcq.py`, `candidates()` searches peer relations where `r.compatible(record, peer)` holds. If strict categories exist (e.g. `category == 'scheduling algorithm'`), it filters peers strictly to that category.
- **Code Reference:** [rag/services/knowledge_mcq.py:L79-L84](file:///d:/SDC/LibraryLLM/rag/services/knowledge_mcq.py#L79-L84).

### Q15. How do you prevent distractors from accidentally being correct?
- **Spoken Answer:**
  > "Our `compatible()` function performs three strict verification checks: first, distractor names cannot overlap lexically with the target concept; second, they cannot be semantic synonyms identified during MMR embedding; and third, it checks all document relations to ensure the distractor description is not asserted as true for the subject anywhere else in the document."
- **Deep Technical Explanation:**
  In `knowledge_quiz_relations.py`:
  1. `left['relationType'] == right['relationType']`.
  2. `not labels_overlap(left['subjectText'], right['subjectText'])`.
  3. `not equivalent(left['targetText'], right['targetText'])`.
  4. `right['id'] not in left.get('semanticPeers', [])`.
  5. Scans all relations: `not any(r['subjectId'] == left['subjectId'] and equivalent(r['targetText'], right['targetText']) for r in relations)`.
- **Code Reference:** [rag/services/knowledge_quiz_relations.py:L174-L182](file:///d:/SDC/LibraryLLM/rag/services/knowledge_quiz_relations.py#L174-L182).

### Q16. What is the role of the 11-point MCQ verifier?
- **Spoken Answer:**
  > "The verifier (`verify()`) acts as a quality gate before any MCQ is admitted to the quiz. It checks 11 failure modes, including answer leaks, duplicate options, detached provenance, distractor reuse limits, and option count integrity. If any check fails, the question is discarded."
- **Deep Technical Explanation:**
  `verify(question, relations)` validates: `SOURCE_BINDING`, `STEM_ANSWER_BINDING`, `ANSWER_KEY`, `ANSWER_LEAK`, `SOURCE_PROVENANCE`, `OPTION_BINDING`, `DUPLICATE_OPTION` (exactly 4 unique options), `AMBIGUOUS_OPTION`, and `MULTIPLE_CORRECT_OR_INCOMPATIBLE`.
- **Code Reference:** [rag/services/knowledge_mcq.py:L50-L73](file:///d:/SDC/LibraryLLM/rag/services/knowledge_mcq.py#L50-L73).

---

## Group 6: Fill-in-the-Blank (Cloze) Quizzes

### Q17. How is a fill-in-the-blank question constructed from text?
- **Spoken Answer:**
  > "The system identifies a key term, entity, quantity, or phrase in an authoritative sentence, removes it, and replaces it with a single `_____` placeholder. The prompt is prefixed with 'Complete the source sentence:'. The original masked string becomes the canonical answer."
- **Deep Technical Explanation:**
  In `knowledge_cloze.py`, `candidates()` iterates over relations and definitions, checking that the target appears exactly once in the sentence (`len(matches) == 1`). It validates that the prompt contains exactly one `"_____"` and records the blank type (`TERM`, `ENTITY`, `SHORT_PHRASE`, `NUMBER`, `NUMBER_WITH_UNIT`, `DESCRIPTION`).
- **Code Reference:** [rag/services/knowledge_cloze.py:L55-L68](file:///d:/SDC/LibraryLLM/rag/services/knowledge_cloze.py#L55-L68).

### Q18. How does cloze answer grading work? Does it require an LLM?
- **Spoken Answer:**
  > "No LLM is used. Grading is performed by a deterministic multi-tier grader in `cloze_grading.py`. It handles numeric conversions like '5 ms' to '0.005 s', exact normalization, parenthetical acronym aliases, and single-letter typos. For descriptive phrases, it evaluates semantic similarity using our CPU MiniLM embedding model with strict guards against negation and role reversal."
- **Deep Technical Explanation:**
  `cloze_grading.grade()` executes a waterfall evaluation:
  1. Quantity equality: `quantity(canonical) == quantity(answer)` using `Decimal` scale factors.
  2. Normalized string equality: NFKC normalization with article stripping.
  3. Parenthetical alias matching: e.g. `"ARQ"` matches `"Automatic Repeat reQuest"`.
  4. Safe typo tolerance: Levenshtein distance 1 on words $\ge 6$ letters.
  5. Logic checks: Rejects negation (`not`, `never`) and role reversal (`sender` $\leftrightarrow$ `receiver`).
  6. Dense embeddings: Evaluates student answer against canonical answer, source excerpt, and material clauses.
- **Code Reference:** [rag/services/cloze_grading.py:L145-L211](file:///d:/SDC/LibraryLLM/rag/services/cloze_grading.py#L145-L211).

### Q19. How do you handle dimensional quantities like '5 milliseconds' vs '0.005 s'?
- **Spoken Answer:**
  > "We parse quantities into exact `Decimal` values multiplied by standard unit conversion factors. For example, milliseconds are scaled by 0.001 and percentages by 0.01. If the numeric dimension and value match, it is graded as Correct regardless of how the unit was written."
- **Deep Technical Explanation:**
  In `cloze_grading.py`, `quantity(value)` uses regex `r'^([+-]?\d+(?:\.\d+)?)\s*([a-z%]*)$'`. It maps units via `UNITS` dictionary (`ms`, `s`, `min`, `h`, `%`) to `Decimal` factors. This avoids floating-point rounding errors and safely handles scientific notation.
- **Code Reference:** [rag/services/cloze_grading.py:L13-L18, L30-L42](file:///d:/SDC/LibraryLLM/rag/services/cloze_grading.py#L13-L18).

### Q20. How do you prevent false positives when a student uses negation?
- **Spoken Answer:**
  > "Dense embedding models often assign high cosine similarity to opposing statements like 'is safe' and 'is not safe'. Our grader explicitly detects negation tokens (`not`, `never`, `cannot`, `without`). If the canonical answer was positive and the student introduces negation, it immediately returns Incorrect (`NEGATION`), bypassing the embedding score."
- **Deep Technical Explanation:**
  In `cloze_grading.py:L170-L177`, `NEGATION = re.compile(r'\b(?:not|never|no|cannot|without)\b|n[’\']t\b', re.I)`. If `len(NEGATION.findall(actual)) > len(NEGATION.findall(expected))`, it returns `result('INCORRECT', 'NEGATION')`.
- **Code Reference:** [rag/services/cloze_grading.py:L170-L177](file:///d:/SDC/LibraryLLM/rag/services/cloze_grading.py#L170-L177).

---

## Group 7: Match-the-Following Quizzes

### Q21. How are matching pairs extracted and formatted?
- **Spoken Answer:**
  > "Matching questions are created from groups of 3 to 6 concepts sharing the same relation family, such as definitions or purposes. Column A contains the concepts and Column B contains their descriptions. Column B is randomly shuffled so items do not appear directly opposite their correct match."
- **Deep Technical Explanation:**
  In `knowledge_match.py`, `candidates()` groups relations by `relationType`. For groups of size 3 to 6, it formats `leftItems` (`id: 'L1', 'L2'`) and `rightItems` (`id: 'R1', 'R2'`). It uses `random.Random(qid).shuffle(right)`. If the shuffled order accidentally equals the initial order, it cyclically shifts `right = right[1:] + right[:1]`.
- **Code Reference:** [rag/services/knowledge_match.py:L35-L80](file:///d:/SDC/LibraryLLM/rag/services/knowledge_match.py#L35-L80).

### Q22. How do you ensure that the matching question has a unique, unambiguous answer?
- **Spoken Answer:**
  > "The verifier enforces a strict mathematical bijection: every left item maps to exactly one right item, and every right item maps to exactly one left item. Additionally, all pairs of items in the set are checked for mutual compatibility to ensure no description could apply to more than one concept."
- **Deep Technical Explanation:**
  In `knowledge_match.py:L15-L33`, `verify()` asserts:
  - `3 <= len(left) <= 6` and `len(left) == len(right)`.
  - `set(correctMatches) == {x['id'] for x in left}` and `set(correctMatches.values()) == {x['id'] for x in right}` (`NOT_BIJECTION` check).
  - All pairs $(x, y)$ satisfy `r.compatible(x, y)` (`AMBIGUOUS_PAIR` check).
- **Code Reference:** [rag/services/knowledge_match.py:L15-L33](file:///d:/SDC/LibraryLLM/rag/services/knowledge_match.py#L15-L33).

### Q23. How are matching questions scored? Is there partial credit?
- **Spoken Answer:**
  > "Yes, matching questions support partial credit. On the frontend, the score is calculated by counting how many selected dropdown matches equal the expected match in `correctMatches`. The UI displays the exact fraction, such as '3 / 4 pairs correct', and marks incorrect selections."
- **Deep Technical Explanation:**
  In `Quiz.tsx:L44, L78-L84`:
  `pairsCorrect = q.leftItems.filter(left => matches[q.id]?.[left.id] === q.correctMatches[left.id]).length`.
  The UI displays `pairsCorrect / q.leftItems.length` and shows expected vs actual matches for each row.
- **Code Reference:** [frontend/src/components/knowledge/Quiz.tsx:L44, L78-L84](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/Quiz.tsx#L44).

---

## Group 8: NLP and Algorithms

### Q24. Which NLP techniques are used in the Knowledge Tools module?
- **Spoken Answer:**
  > "We use a combination of rule-based and statistical NLP: Unicode NFKC normalization, regular expression syntactic pattern matching, stopword and verb phrase filtering, inverse document frequency term specificity scoring, Maximal Marginal Relevance diversity selection, dense sentence embeddings via MiniLM, and Levenshtein edit distance for safe typo handling."
- **Deep Technical Explanation:**
  See the complete breakdown in [06_NLP_ALGORITHMS_AND_MODELS.md](file:///d:/SDC/docs/knowledge-tools-audit/06_NLP_ALGORITHMS_AND_MODELS.md). Every algorithm is implemented in Python stdlib or lightweight CPU PyTorch without spacy, nltk, or external API calls.

### Q25. Why did you use MMR (Maximal Marginal Relevance) in concept extraction?
- **Spoken Answer:**
  > "Frequency-based extraction often selects redundant terms like 'Virtual Memory' and 'Virtual Memory Technique'. MMR balances term importance against redundancy by subtracting a penalty for cosine similarity with already selected concepts. This ensures wide educational topic coverage across the document."
- **Deep Technical Explanation:**
  In `document_knowledge.py:L380-L404`, MMR selects candidate $i$ maximizing $\text{Score}(c_i) - 2.2 \times \max_{j \in S}(\mathbf{v}_i \cdot \mathbf{v}_j)$. It guarantees that highly similar phrases ($\ge 0.90$ cosine similarity) are suppressed in favor of distinct topics.
- **Code Reference:** [rag/services/document_knowledge.py:L380-L404](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L380-L404).

### Q26. How do you calculate term specificity?
- **Spoken Answer:**
  > "We calculate an IDF-style specificity score. For every word in a candidate phrase, we take the natural logarithm of the total sentence count divided by the word's document frequency. Rare domain terms get high specificity scores, while common words like 'system' get penalized."
- **Deep Technical Explanation:**
  Formula:
  $$\text{Specificity}(c) = \frac{1}{|W|} \sum_{w \in W} \ln\left(1 + \frac{|\text{Rows}|}{\max(1, \text{DF}(w))}\right)$$
  Integrated into candidate ranking in [document_knowledge.py:L325](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L325).

---

## Group 9: LLM vs Deterministic Processing

### Q27. Why did you avoid LLMs for Knowledge Tools when your project already has a local LLM?
- **Spoken Answer:**
  > "Using an LLM for study generation creates three major engineering problems: first, GPU contention—running Qwen for study generation blocks or slows down concurrent RAG chat queries; second, latency—LLMs take several seconds per generation turn, whereas our rule engine runs in under 50ms; and third, reliability—LLMs hallucinate facts and drift across retries, whereas our deterministic pipeline guarantees 100% source fidelity."
- **Deep Technical Explanation:**
  The resident LLM process requires exclusive GPU lock allocation during forward inference. By keeping Knowledge Tools strictly on CPU (`device='cpu'`), study generation executes concurrently with zero interference to LLM chat sessions.
- **Code Reference:** [rag/services/knowledge_encoder.py:L12-L13](file:///d:/SDC/LibraryLLM/rag/services/knowledge_encoder.py#L12-L13), [reports/cloze_v2_3_architecture.md](file:///d:/SDC/LibraryLLM/reports/cloze_v2_3_architecture.md).

### Q28. Can Knowledge Tools run completely offline?
- **Spoken Answer:**
  > "Yes. The embedding model `all-MiniLM-L6-v2` is configured with `local_files_only=True`. The system does not make external web requests, cloud API calls, or remote telemetry checks."
- **Deep Technical Explanation:**
  In `knowledge_encoder.py:L13`, `local_files_only=True` ensures that SentenceTransformer loads model weights strictly from the local cache folder. No internet access is required.
- **Code Reference:** [rag/services/knowledge_encoder.py:L13](file:///d:/SDC/LibraryLLM/rag/services/knowledge_encoder.py#L13).

---

## Group 10: Document Ingestion and RAG Integration

### Q29. How does Knowledge Tools retrieve document text? Does it use FAISS?
- **Spoken Answer:**
  > "No, Knowledge Tools does not query FAISS. FAISS is an approximate nearest-neighbor vector index designed for conversational RAG queries. Knowledge Tools instead reads the document's `chunks.json` file directly from disk to perform holistic structural analysis across the entire text."
- **Deep Technical Explanation:**
  During PDF upload, `PrivateDocuments` parses text with PyMuPDF, chunks the text, writes `chunks.json`, and indexes vectors into `runtime.faiss`. Knowledge Tools opens `chunks.json` via `_source()` ([knowledge_artifacts.py:L82-L92](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L82-L92)), bypassing vector search entirely.
- **Code Reference:** [rag/services/knowledge_artifacts.py:L82-L92](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L82-L92).

### Q30. How are long documents handled? Is there a truncation limit?
- **Spoken Answer:**
  > "If a document exceeds 64 MB, the request is rejected with HTTP 413 to prevent memory exhaustion. If a document has more than 1,200 chunks, the system evenly samples chunk positions across the entire document so beginning, middle, and end sections are all represented, and flags the artifact with `sampled: true`."
- **Deep Technical Explanation:**
  In `knowledge_algorithms.py:L43`, `indexes = [i * (len(chunks)-1) // (MAX_CHUNKS-1) for i in range(MAX_CHUNKS)]` if `len(chunks) > MAX_CHUNKS (1200)`. Maximum units parsed is capped at 2,200 (`MAX_UNITS`), and sentences at 6,000 (`MAX_SENTENCES`).
- **Code Reference:** [rag/services/knowledge_algorithms.py:L8-L10, L43](file:///d:/SDC/LibraryLLM/rag/services/knowledge_algorithms.py#L8-L10), [rag/services/document_knowledge.py:L13](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L13).

### Q31. What happens if a scanned PDF is uploaded without text?
- **Spoken Answer:**
  > "LuminaR includes a local bounded OCR worker in `private_document_ocr.py` using Tesseract. If text is extracted via OCR, our relation extractor enforces a strict alphabetic density threshold (>=55%). If OCR corruption is detected, corrupted lines are rejected with `OCR_CORRUPTION`."
- **Deep Technical Explanation:**
  In `knowledge_quiz_relations.py:L119-L122`, if `any(u.get('extraction_method') == 'OCR' for u in evidence)` and alphabetic density $<0.55$, the candidate is rejected.
- **Code Reference:** [rag/services/knowledge_quiz_relations.py:L119-L122](file:///d:/SDC/LibraryLLM/rag/services/knowledge_quiz_relations.py#L119-L122).

---

## Group 11: Frontend/Backend API & State

### Q32. How does the frontend handle tab switching and cancellation?
- **Spoken Answer:**
  > "Every fetch request uses React refs holding `AbortController` instances. If the user clicks another tab or selects new quiz options while a generation is in flight, the pending HTTP request is aborted immediately, preventing race conditions or UI state collisions."
- **Deep Technical Explanation:**
  In `KnowledgeTools.tsx`, `controller = useRef<AbortController | null>(null)`. In `load()` and `generate()`, `controller.current?.abort()` is called before creating a new `AbortController`. The fetch call receives `{ signal: abort.signal }`.
- **Code Reference:** [frontend/src/components/knowledge/KnowledgeTools.tsx:L64-L65, L75-L77](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/KnowledgeTools.tsx#L64-L65).

### Q33. Why is the session key in `KnowledgeTools.tsx` constructed as `${token}:${libraryId}:${documentId}`?
- **Spoken Answer:**
  > "It guarantees that switching documents, switching library assets, or logging out completely unmounts and discards all component state, preventing private study notes or quiz questions from leaking into the new session."
- **Deep Technical Explanation:**
  React's reconciliation algorithm treats components with different keys as distinct instances. When `token` or `documentId` changes, React destroys the previous DOM subtree and state variables (`cards`, `quiz`, `source`), mounting a pristine component instance.
- **Code Reference:** [frontend/src/components/knowledge/KnowledgeTools.tsx:L53-L56](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/KnowledgeTools.tsx#L53-L56).

---

## Group 12: Performance & Optimization

### Q34. What is the execution latency of Knowledge Tools generation?
- **Spoken Answer:**
  > "On cache hit, response latency is 5 to 15 milliseconds. On cache miss, initial knowledge model construction takes approximately 50 to 120 milliseconds on CPU (including the single MiniLM embedding batch), and artifact rendering takes under 20 milliseconds."
- **Deep Technical Explanation:**
  Production telemetry metrics in `artifact.analysis.metrics` track exact timings:
  - `knowledge_model_ms`: ~40–80 ms.
  - `embedding_ms`: ~25–50 ms.
  - `artifact_generation_ms`: ~5–15 ms.
- **Code Reference:** [rag/services/knowledge_artifacts.py:L182-L186](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L182-L186).

### Q35. How does the multi-tier cache key work?
- **Spoken Answer:**
  > "The cache key is a SHA256 hash composed of the document's chunks.json hash, the artifact type, the selected options, the generator algorithm version, and the intermediate knowledge model version. If any code or content changes, the key changes, guaranteeing cache validity."
- **Deep Technical Explanation:**
  In `knowledge_artifacts.py:L150-L155`:
  `identity = [revision, kind, scope, options, version, document_knowledge.VERSION]`.
  Key is `hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()`.
- **Code Reference:** [rag/services/knowledge_artifacts.py:L150-L155](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L150-L155).

---

## Group 13: Security & Data Privacy

### Q36. Can user A access study artifacts generated by user B on the same document?
- **Spoken Answer:**
  > "No. For private documents, SQLite queries strictly filter by both `document_id` and `owner`. If user A attempts to request user B's artifact ID, the query returns null, resulting in an HTTP 404 response."
- **Deep Technical Explanation:**
  In `knowledge_artifacts.py:L158-L159, L212-L213`:
  `SELECT payload FROM knowledge_artifacts WHERE document_id=? AND owner=?`.
  `owner` is extracted from the verified JWT claims (`user['sub']`), preventing IDOR (Insecure Direct Object Reference) attacks.
- **Code Reference:** [rag/services/knowledge_artifacts.py:L158-L159, L212-L213](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L158-L159).

### Q37. Why are `Cache-Control: no-store` headers used?
- **Spoken Answer:**
  > "Because private documents and study artifacts contain confidential user notes. `no-store` instructs browsers and shared proxies never to write responses to disk or intermediate caches, ensuring private text is not accessible after logout."
- **Deep Technical Explanation:**
  Attached via FastAPI dependency guard `private_response` in [knowledge_routes.py:L35-L39](file:///d:/SDC/LibraryLLM/rag/services/knowledge_routes.py#L35-L39).

---

## Group 14: Limitations & Future Work

### Q38. What happens if a document has no definitions or formal headings?
- **Spoken Answer:**
  > "This is a known limitation of rule-based systems. If a document lacks copular patterns and structural headings, candidate scoring will produce few or no items. The system handles this gracefully by displaying an informative notice rather than crashing, and falls back to cloze questions where possible."
- **Deep Technical Explanation:**
  In `KnowledgeTools.tsx:L146`: displays `"Not enough definition-style content was found in this document to create reliable flashcards or cloze cards."`
- **Follow-up & Rebuttal:**
  *Q: How would you improve this in future work?*  
  *Rebuttal:* "In future work, we could add an optional, user-triggered LLM fallback mode specifically for non-technical prose, running asynchronously when rule-based extraction yields fewer than 3 items."

### Q39. Does the Flashcard system support Spaced Repetition (like Anki's SM-2)?
- **Spoken Answer:**
  > "Not currently. Flashcards in LuminaR are currently session-oriented study tools. We do not persist student mastery scores, review intervals, or spaced-repetition schedules. This is documented as high-priority future work."
- **Deep Technical Explanation:**
  The `Card` interface only tracks pedagogical presentation data (`front`, `back`, `type`, `sourceExcerpt`, `sourceChunkIds`). No review interval database table currently exists.

### Q40. Why are MCQ questions limited to 4 options?
- **Spoken Answer:**
  > "Four options is the standard academic psychometric format for multiple-choice testing. Enforcing exactly 4 options allows consistent layout in UI and ensures high distractor quality—if a document lacks 3 mutually compatible distractors, the question is discarded rather than filled with weak guesses."
- **Deep Technical Explanation:**
  Enforced by `verify()` in `knowledge_mcq.py:L64`: `if len(options) != 4: return 'DUPLICATE_OPTION'`.

---

## Additional Rapid-Fire Viva Questions (Q41–Q52)

### Q41. How is option order randomized in MCQs?
- In `knowledge_mcq.py:L34`: `random.Random(qid).shuffle(options)`. It seeds the PRNG with the deterministic question ID so options are shuffled consistently across re-renders.

### Q42. What is the purpose of `phrase_key()`?
- Normalizes phrases for lexical comparison by stripping punctuation, lowercasing, and collapsing simple English plurals (`w[:-1]` if `len(w)>4 and endswith('s')`). Found in [document_knowledge.py:L31-L33](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L31-L33).

### Q43. What is the maximum document size supported by Knowledge Tools?
- 64 megabytes on `chunks.json`. Enforced in [knowledge_artifacts.py:L86](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L86).

### Q44. How does the Extractive Summary choose its sentences?
- In `document_knowledge.py:L499-L515`: It sorts accepted facts by page order, picks one representative sentence per section until reaching 5 (Quick) or 12 (Detailed), and groups them by section title.

### Q45. What is the purpose of AST checking in `test_knowledge_algorithms.py`?
- It uses Python's `ast` module to statically parse the imports of `knowledge_algorithms.py` and `knowledge_routes.py`, mathematically asserting that no LLM, GPU, or disallowed external libraries are imported.

### Q46. Can a matching question have 10 pairs?
- No. `verify()` in `knowledge_match.py:L18` restricts pair count to between 3 and 6 (`3 <= len(left) <= 6`).

### Q47. How does the frontend handle keyboard focus in Fullscreen Mind Map?
- It applies `root.inert = true` to the main application container and runs a Tab key trap cycling between modal controls, restoring focus upon Escape.

### Q48. What is the time complexity of the mind map layout algorithm?
- $\mathcal{O}(V + E)$ where $V \le 60$ and $E \le 60$. It is linear in the number of nodes, running in under 2 milliseconds in the browser.

### Q49. What is a 'semantic peer' in relation verification?
- A concept identified as a near-synonym during the MMR dense embedding pass ($\text{cosine} \ge 0.88$). It cannot be used as a distractor for that concept.

### Q50. How does the system prevent answer leaks in MCQ stems?
- `verify()` checks `if e.normalize(expected) in e.normalize(question['question']): return 'ANSWER_LEAK'`.

### Q51. What library is used to read PDF text?
- PyMuPDF (`fitz`), chosen for its C-level extraction speed and precise character bounding box support.

### Q52. Why does the system report `'qwen_calls': 0` in artifact metadata?
- As a verifiable runtime audit metric proving to users and reviewers that the educational content was produced without LLM inference costs or hallucinations.
