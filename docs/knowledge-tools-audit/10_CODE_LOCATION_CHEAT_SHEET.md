# LuminaR Code Navigation Cheat Sheet: "IF THE REVIEWER ASKS, OPEN THIS FILE"

This navigation guide is your **live viva companion**. When an examiner or project reviewer asks a technical question and says *"Show me the code"*, look up the topic here, open the exact file and lines, highlight the indicated code block, and speak the provided script.

---

## 1. Knowledge Graph & Catalogue Graph

### Reviewer Question: "Where is your Knowledge Graph implementation?"
- **File:** `LibraryLLM/knowledge_graph/core.py`
- **Function:** `CatalogueGraph.more_like_this()`
- **Lines:** [knowledge_graph/core.py:L60-L100](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L60-L100)
- **What to show:**
  ```python
  score_query='''SELECT e.book_id,SUM(f.weight*f.weight) / SQRT(n.value*?) AS score
      FROM edges e JOIN features f USING(kind,term) JOIN norms n ON n.book_id=e.book_id
      WHERE (e.kind,e.term) IN (SELECT kind,term FROM edges WHERE book_id=?) AND e.book_id!=?
      GROUP BY e.book_id ORDER BY score DESC,e.book_id'''
  ```
- **What to say (25s):**
  > "Here is our library-wide knowledge graph in `core.py`. It's a typed bipartite graph on SQLite connecting books via shared authors, subjects, and extracted topic features. This SQL query computes exact cosine similarity over degree-normalized feature weights and generates explainable 2-hop reason paths showing exactly which shared nodes connect the books."

---

## 2. Document Concept Extraction & Scoring

### Reviewer Question: "Where is the algorithm that extracts domain concepts from a document?"
- **File:** `LibraryLLM/rag/services/document_knowledge.py`
- **Function:** `build()`
- **Lines:** [rag/services/document_knowledge.py:L320-L343](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L320-L343)
- **What to show:**
  ```python
  signals = {'heading': 2.8 * item['heading'], 'definition': 4.5 * item['defined'],
             'frequency': min(1.5, math.log1p(len(evidence)) * .6),
             'multi_page': min(1.2, len(pages) * .25), 'specificity': min(2, specificity),
             'relation': .8 * any(e['definitionEvidence'] or e['relation'] in
                                 {'has characteristic', 'consists of', 'is used for', 'has step'} for e in evidence),
             'multi_word': min(1, (len(words) - 1) * .35), 'genericity_penalty': genericity,
             'fragment_penalty': fragment}
  score = sum(v for k, v in signals.items() if not k.endswith('penalty')) - genericity - fragment
  if score < 4.1:
      metrics['genericity_rejections'] += 1
      continue
  ```
- **What to say (30s):**
  > "In `document_knowledge.py`, candidate concepts are scored using an information-theoretic formula. We award positive weights for definitional copulas (+4.5), structural section headings (+2.8), frequency, multi-page distribution, and IDF-like specificity, while heavily penalizing vague generic words and fragments. Candidates must achieve a score of at least 4.1 to be considered for dense embedding."

---

## 3. MMR Vector Diversity & Deduplication

### Reviewer Question: "Where do you prevent duplicate concepts from dominating the graph?"
- **File:** `LibraryLLM/rag/services/document_knowledge.py`
- **Function:** `build()` (MMR Loop)
- **Lines:** [rag/services/document_knowledge.py:L380-L404](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L380-L404)
- **What to show:**
  ```python
  similarity = max((float(vectors[index] @ vectors[i]) for i, _ in selected), default=0) if vectors is not None else 0
  choices.append((item['score'] - 2.2 * max(0, similarity), -index, index, item))
  ...
  semantic = vectors is not None and float(vectors[index] @ vectors[other_index]) >= .90
  if lexical or semantic and (same_explanation or not (item['defined'] and other['defined'])):
      duplicate = True
  ```
- **What to say (30s):**
  > "Here is our Maximal Marginal Relevance implementation. Top candidate concepts are embedded using CPU MiniLM. The selection loop greedily chooses the concept maximizing the score minus 2.2 times its maximum cosine similarity with already selected concepts. If a candidate has over 0.90 similarity with an existing concept, it is discarded as a duplicate."

---

## 4. Mind Map Hierarchical Generation

### Reviewer Question: "Where is the Mind Map hierarchy constructed?"
- **File:** `LibraryLLM/rag/services/document_knowledge.py`
- **Function:** `generate(kind='MIND_MAP')`
- **Lines:** [rag/services/document_knowledge.py:L516-L547](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L516-L547)
- **What to show:**
  ```python
  nodes = [{'id': 'document', 'label': title, 'type': 'document', 'sourceChunkIds': []}]
  ...
  nodes.append({'id': group, 'label': label, 'type': field, ...})
  edges.append({'source': parent, 'target': group, 'relation': 'source organization', ...})
  ...
  nodes.append({**concept, 'type': 'concept'})
  edges.append({'source': parent, 'target': concept['id'], 'relation': 'document topic', ...})
  ...
  nodes.append({'id': target, 'label': normalized(relation['targetText'])[:160], 'type': 'evidence', ...})
  edges.append({'source': relation['source'], 'target': target, 'relation': relation['type'], ...})
  ```
- **What to say (30s):**
  > "Here is the mind map transformation in `document_knowledge.py`. It creates a 4-tier tree: Tier 0 is the Document root; Tier 1 attaches chapters and sections as 'source organization'; Tier 2 attaches our top domain concepts as 'document topic'; and Tier 3 attaches verified copular relations as 'evidence' leaves with types like DEFINED_AS and CONTAINS."

---

## 5. Mind Map Layout Math (Radial / Tree Algorithm)

### Reviewer Question: "Where is the algorithm that computes node positions on the SVG canvas?"
- **File:** `LibraryLLM/frontend/src/components/knowledge/mapLayout.ts`
- **Function:** `layoutKnowledgeMap()`
- **Lines:** [frontend/src/components/knowledge/mapLayout.ts:L25-L55](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/mapLayout.ts#L25-L55)
- **What to show:**
  ```python
  for (const id of order.slice().reverse()) weight.set(id, Math.max(1, children.get(id)!.reduce((sum, child) => sum + (weight.get(child) || 1), 0)))
  const sides: string[][] = [[], []], counts = [0, 0]
  for (const branch of children.get(root)!) {
    const side = counts[0] <= counts[1] ? 0 : 1
    sides[side].push(branch); counts[side] += weight.get(branch) || 1
  }
  ...
  positions.set(id, { x: centerX + (side ? -1 : 1) * depths.get(id)! * gap, y: top + (span - mapCardHeight) / 2 })
  ```
- **What to say (35s):**
  > "In `mapLayout.ts`, we wrote an original balanced two-sided tree layout. It traverses the graph from the root, computes subtree weights from leaves up, and uses greedy bin-packing to distribute branches evenly between left and right columns. Node X coordinates are placed by depth times a dynamic gap, and Y coordinates are centered within proportionally weighted spans."

---

## 6. Flashcard Generation & Regex Extraction

### Reviewer Question: "Where is the flashcard generation code?"
- **File:** `LibraryLLM/rag/services/document_knowledge.py`
- **Function:** `generate(kind='FLASHCARDS')`
- **Lines:** [rag/services/document_knowledge.py:L464-L498](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L464-L498)
- **What to show:**
  ```python
  front = f'What does the document explain about {concept["label"]}?'
  back = normalized(fact['text'])
  if fact['relation'] == 'has characteristic':
      card_type = 'cloze'
      match = pattern.search(fact['text'])
      if match:
          front = fact['text'][:match.start()] + '_____' + fact['text'][match.end():]
          back = match.group()
  ```
- **What to say (25s):**
  > "Here is `generate('FLASHCARDS')`. In Phase 1, it pairs each accepted concept with its verified definition, formatting question prompts or creating masked cloze cards. In Phase 2, it loops through processes and examples to produce procedural step and application cards, capping the set at 40 cards with full source chunk provenance."

---

## 7. MCQ Generation & Stem Construction

### Reviewer Question: "Where are Multiple Choice Questions generated?"
- **File:** `LibraryLLM/rag/services/knowledge_mcq.py`
- **Function:** `stem()`, `candidate()`
- **Lines:** [rag/services/knowledge_mcq.py:L10-L48](file:///d:/SDC/LibraryLLM/rag/services/knowledge_mcq.py#L10-L48)
- **What to show:**
  ```python
  if identify:
      text = f'Which concept is defined by this source description: “{record["targetText"]}”?'
  elif record['relationType'] == 'DEFINITION':
      text = f'Which description best defines {record["subjectText"]}?'
  elif record['relationType'] == 'PURPOSE':
      text = f'What is {record["subjectText"]} used for according to the document?'
  ```
- **What to say (25s):**
  > "In `knowledge_mcq.py`, question stems are tailored to the relation family—such as definitions, purposes, or processes. It also supports inverse questions where the description is presented and the options are the domain concepts. Options are shuffled deterministically using the question ID hash."

---

## 8. Distractor Selection & Peer Compatibility

### Reviewer Question: "Where do you verify that MCQ distractors are not accidentally correct?"
- **File:** `LibraryLLM/rag/services/knowledge_quiz_relations.py`
- **Function:** `compatible()`
- **Lines:** [rag/services/knowledge_quiz_relations.py:L174-L182](file:///d:/SDC/LibraryLLM/rag/services/knowledge_quiz_relations.py#L174-L182)
- **What to show:**
  ```python
  def compatible(left, right, relations):
      if (left['relationType'] != right['relationType'] or e.labels_overlap(left['subjectText'], right['subjectText'])
              or equivalent(left['targetText'], right['targetText']) or peers(left, right)):
          return False
      return not any(r['subjectId'] == left['subjectId'] and r['relationType'] == left['relationType']
                     and equivalent(r['targetText'], right['targetText']) for r in relations)
  ```
- **What to say (30s):**
  > "This is `compatible()` in `knowledge_quiz_relations.py`. It requires distractors to come from the same relation family, ensures their labels don't overlap lexically, and excludes semantic peers identified by MiniLM. Crucially, line 180 scans all relations to verify that the distractor description is not asserted as true for the tested subject anywhere else in the document."

---

## 9. 11-Point MCQ Integrity Verifier

### Reviewer Question: "Where is the MCQ quality gate implemented?"
- **File:** `LibraryLLM/rag/services/knowledge_mcq.py`
- **Function:** `verify()`
- **Lines:** [rag/services/knowledge_mcq.py:L50-L74](file:///d:/SDC/LibraryLLM/rag/services/knowledge_mcq.py#L50-L74)
- **What to show:**
  ```python
  if question['correctAnswer'] != expected or question['options'].count(expected) != 1: return 'ANSWER_KEY'
  if e.normalize(expected) in e.normalize(question['question']): return 'ANSWER_LEAK'
  if len(options) != 4 or len(set(question['options'])) != 4: return 'DUPLICATE_OPTION'
  if any(not r.bound(x) or not r.compatible(x,y,relations) for x,y in combinations(options,2)): return 'MULTIPLE_CORRECT_OR_INCOMPATIBLE'
  ```
- **What to say (25s):**
  > "Here is `verify()` in `knowledge_mcq.py`. It tests 11 structural and semantic rules: checking that the answer appears in the options exactly once, ensuring the answer doesn't leak inside the stem, requiring exactly 4 unique options, and asserting that all option pairs are mutually compatible."

---

## 10. Fill-in-the-Blank Formatting & Blank Types

### Reviewer Question: "Where are Fill-in-the-Blank items bound and validated?"
- **File:** `LibraryLLM/rag/services/knowledge_cloze.py`
- **Function:** `validate()`, `bind()`
- **Lines:** [rag/services/knowledge_cloze.py:L15-L47](file:///d:/SDC/LibraryLLM/rag/services/knowledge_cloze.py#L15-L47)
- **What to show:**
  ```python
  prompt = item['question'].removeprefix('Complete the source sentence: ')
  if prompt.count('_____') != 1 or item['correctAnswer'] != canonical: return False
  if g.normalize(prompt.replace('_____', canonical)) != g.normalize(source): return False
  return item['blankType'] in {'TERM','ENTITY','SHORT_PHRASE','NUMBER','NUMBER_WITH_UNIT','DESCRIPTION'}
  ```
- **What to say (25s):**
  > "In `knowledge_cloze.py`, `validate()` ensures the prompt contains exactly one blank mask `_____`, confirms that substituting the canonical answer reproduces the exact source sentence, and categorizes blanks into 6 types, including bare numbers, dimensional units, and entities."

---

## 11. Cloze Semantic Grading & Logic Checks

### Reviewer Question: "Where is the cloze answer grading algorithm?"
- **File:** `LibraryLLM/rag/services/cloze_grading.py`
- **Function:** `grade()`
- **Lines:** [rag/services/cloze_grading.py:L145-L211](file:///d:/SDC/LibraryLLM/rag/services/cloze_grading.py#L145-L211)
- **What to show:**
  ```python
  if kind in {'NUMBER','NUMBER_WITH_UNIT'}:
      return result('CORRECT' if quantity(canonical)==quantity(answer) else 'INCORRECT','QUANTITY')
  if expected==actual: return result('CORRECT','NORMALIZED_IDENTITY')
  if NEGATION.search(actual) and not NEGATION.search(expected): return result('INCORRECT','NEGATION')
  ...
  sims=CACHE.similarities([actual,expected,normalize(item['sourceExcerpt']),*parts],encoder)
  if semantic>=.75 and evidence>=.55 and all(s>=.66 for s in clauses) and has_predicate:
      return result('CORRECT','SOURCE_PHRASE')
  ```
- **What to say (35s):**
  > "Here is `grade()` in `cloze_grading.py`. It starts with Decimal quantity evaluation for dimensional units, checks string normalization and parenthetical aliases, and allows 1-letter typos. Line 170 explicitly blocks negation. For descriptive phrases, lines 198–205 embed the student answer against the canonical answer, source excerpt, and sub-clauses, requiring at least 0.75 semantic similarity."

---

## 12. Match-the-Following Bijective Matrix & Beam Search

### Reviewer Question: "Where is the matching question generation and bijection check?"
- **File:** `LibraryLLM/rag/services/knowledge_match.py`
- **Function:** `verify()`, `select()`
- **Lines:** [rag/services/knowledge_match.py:L15-L33, L83-L105](file:///d:/SDC/LibraryLLM/rag/services/knowledge_match.py#L15-L33)
- **What to show:**
  ```python
  if not 3<=len(left)<=6 or len(left)!=len(right): return 'PAIR_COUNT'
  if set(question['correctMatches'])!={x['id'] for x in left} or set(question['correctMatches'].values())!={x['id'] for x in right}: return 'NOT_BIJECTION'
  ...
  # Beam search pair allocation (select)
  beam=[initial];best=initial
  for _ in range(min(10,requested_pairs//3)):
  ```
- **What to say (30s):**
  > "In `knowledge_match.py`, `verify()` asserts that matching sets contain between 3 and 6 pairs and verifies a strict mathematical bijection where every left item maps to a unique right item. In `select()`, a beam search with width 80 optimizes the combination of 3-pair and 4-pair sets to match the user's requested pair allocation without starving other quiz formats."

---

## 13. Concurrency Semaphore & Leader-Follower Futures

### Reviewer Question: "Where do you control concurrency and rate-limiting?"
- **File:** `LibraryLLM/rag/services/knowledge_artifacts.py`
- **Function:** `generate()`
- **Lines:** [rag/services/knowledge_artifacts.py:L107-L135](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L107-L135)
- **What to show:**
  ```python
  with self._lock:
      future = self._jobs.get(job_key)
      if future is None:
          if owner in self._owners or not self._capacity.acquire(blocking=False):
              raise HTTPException(429, 'Knowledge Tools is busy. Please retry shortly.')
          future = Future()
          self._jobs[job_key] = future
          self._owners.add(owner)
          leader = True
  if not leader:
      result = future.result(timeout=25)
  ```
- **What to say (30s):**
  > "In `knowledge_artifacts.py`, `self._capacity = Semaphore(3)` limits the entire server to 3 concurrent generation jobs. `self._owners` enforces a single-flight per user. If duplicate requests arrive for the same job, subsequent calls join the leader's Future, waiting up to 25 seconds for the result instead of duplicating work."

---

## 14. CPU Embedding Singleton (Zero GPU/LLM Dependency)

### Reviewer Question: "Where is the embedding model initialized, and how do you ensure it doesn't use the GPU?"
- **File:** `LibraryLLM/rag/services/knowledge_encoder.py`
- **Function:** `_load()`, `encode()`
- **Lines:** [rag/services/knowledge_encoder.py:L8-L27](file:///d:/SDC/LibraryLLM/rag/services/knowledge_encoder.py#L8-L27)
- **What to show:**
  ```python
  def _load():
      global _model
      if _model is None:
          from sentence_transformers import SentenceTransformer
          _model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2',
                                       device='cpu', local_files_only=True)
  ```
- **What to say (25s):**
  > "Here is `knowledge_encoder.py`. We load `all-MiniLM-L6-v2` explicitly with `device='cpu'` and `local_files_only=True`. It runs in a separate CPU singleton protected by a thread lock, guaranteeing that study tools never contend for GPU VRAM with our Qwen LLM."

---

## 15. Frontend React State & Session Cleanup

### Reviewer Question: "Where is the main frontend component, and how do you prevent data leaks on signout?"
- **File:** `LibraryLLM/frontend/src/components/knowledge/KnowledgeTools.tsx`
- **Function:** `KnowledgeTools()`, `KnowledgeToolsSession()`
- **Lines:** [frontend/src/components/knowledge/KnowledgeTools.tsx:L53-L85](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/KnowledgeTools.tsx#L53-L85)
- **What to show:**
  ```tsx
  export function KnowledgeTools({ documentId, title, libraryAsset }: { documentId: string; title: string; libraryAsset?: LibraryAssetTarget }) {
    const token = useAuthStore(state => state.token)
    return <KnowledgeToolsSession key={`${token}:${libraryAsset?.libraryId || 'personal'}:${documentId}`} documentId={documentId} title={title} libraryAsset={libraryAsset} />
  }
  ```
- **What to say (25s):**
  > "In `KnowledgeTools.tsx`, the parent component keys `KnowledgeToolsSession` by token, library ID, and document ID. If a user logs out, switches accounts, or opens another document, React automatically destroys the previous DOM subtree and wipes all cards, questions, and excerpts from browser memory."
