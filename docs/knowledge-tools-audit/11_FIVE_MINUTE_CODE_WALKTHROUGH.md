# LuminaR 5-Minute Live Code Walkthrough Script

## Presentation Objective
Demonstrate the complete end-to-end lifecycle of the **Knowledge Tools** module in 5 minutes:
$$\text{Document Ingestion} \longrightarrow \text{Knowledge Model Extraction} \longrightarrow \text{Artifact Generation} \longrightarrow \text{API Routing} \longrightarrow \text{Interactive Frontend}$$

---

## Walkthrough Timeline Overview (300 Seconds)

| Stage | Duration | Primary File | Core Technical Focus |
|---|---|---|---|
| **1. The Entry Point** | 40s | `KnowledgeTools.tsx` | Component keying, session isolation, tab architecture |
| **2. API & Concurrency** | 45s | `knowledge_routes.py` & `knowledge_artifacts.py` | Route guards, Semaphore admission, single-flight futures |
| **3. The Knowledge Model** | 60s | `document_knowledge.py` | Multi-signal concept scoring, MMR vector deduplication |
| **4. Quiz Distractors & Verifier**| 55s | `knowledge_mcq.py` & `knowledge_quiz_relations.py` | Category matching, peer compatibility, 11-point verifier |
| **5. Cloze Semantic Grader** | 45s | `cloze_grading.py` | Dimensional numbers, safe typos, role reversal & embeddings |
| **6. Mind Map Radial Layout** | 35s | `mapLayout.ts` | Two-sided balanced tree math, cubic bezier curves |
| **7. Catalogue Graph Traversal** | 20s | `knowledge_graph/core.py` | Bipartite SQL cosine similarity, 2-hop reason paths |

---

## Detailed Step-by-Step Walkthrough

### Stop 1: The Frontend Container (0:00 – 0:40)
- **File:** `LibraryLLM/frontend/src/components/knowledge/KnowledgeTools.tsx`
- **Component / Lines:** `KnowledgeTools`, [KnowledgeTools.tsx:L53-L56](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/KnowledgeTools.tsx#L53-L56)
- **What to highlight on screen:**
  ```tsx
  export function KnowledgeTools({ documentId, title, libraryAsset }: { documentId: string; title: string; libraryAsset?: LibraryAssetTarget }) {
    const token = useAuthStore(state => state.token)
    return <KnowledgeToolsSession key={`${token}:${libraryAsset?.libraryId || 'personal'}:${documentId}`} documentId={documentId} title={title} libraryAsset={libraryAsset} />
  }
  ```
- **Spoken Script (40s):**
  > *"We begin in `KnowledgeTools.tsx`. Notice lines 53 through 56: we wrap the active session with a dynamic React key composed of the auth token, library ID, and document ID. This is our state isolation guard—if a user switches documents or logs out, React instantly unmounts the component and purges all sensitive study notes and quiz questions from browser memory. Below, `KnowledgeToolsSession` coordinates our five study tools using dedicated AbortControllers to cancel in-flight requests on tab changes."*

---

### Stop 2: API Routing & Concurrency Gate (0:40 – 1:25)
- **File:** `LibraryLLM/rag/services/knowledge_artifacts.py`
- **Class / Method / Lines:** `KnowledgeArtifacts.generate()`, [knowledge_artifacts.py:L107-L135](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L107-L135)
- **What to highlight on screen:**
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
- **Spoken Script (45s):**
  > *"When the frontend makes a request, it hits `knowledge_artifacts.py`. Here at line 110, we implement our admission control gate: a global Semaphore limits simultaneous generation to 3 jobs across the server, while `self._owners` enforces a single-flight policy per user. If duplicate requests arrive for the exact same document and settings, lines 118–120 collapse them into a single-flight Future, waiting up to 25 seconds for the leader's result rather than doing duplicate work."*

---

### Stop 3: The Intermediate Study Model & MMR (1:25 – 2:25)
- **File:** `LibraryLLM/rag/services/document_knowledge.py`
- **Function / Lines:** `build()`, [document_knowledge.py:L330-L343, L380-L399](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L330-L343)
- **What to highlight on screen:**
  ```python
  score = sum(v for k, v in signals.items() if not k.endswith('penalty')) - genericity - fragment
  if score < 4.1:
      continue
  ...
  # MMR Diversity Loop
  similarity = max((float(vectors[index] @ vectors[i]) for i, _ in selected), default=0) if vectors is not None else 0
  choices.append((item['score'] - 2.2 * max(0, similarity), -index, index, item))
  ```
- **Spoken Script (60s):**
  > *"This is the core intelligence of the subsystem: `document_knowledge.py`. It extracts structural units directly from `chunks.json`. Lines 331 through 339 score candidate concepts using a multi-signal heuristic rewarding definitions (+4.5) and headings (+2.8) while penalizing generic vocabulary. Top candidates are embedded in a single batch using our CPU MiniLM model. Lines 380 through 399 run a Maximal Marginal Relevance loop: it greedily selects concepts while penalizing cosine similarity with already chosen ones. Any candidate with over 0.90 similarity is pruned, preventing near-duplicate terms from cluttering the study materials."*

---

### Stop 4: Quiz Distractor Compatibility & Verifier (2:25 – 3:20)
- **File:** `LibraryLLM/rag/services/knowledge_mcq.py`
- **Functions / Lines:** `compatible()` and `verify()`, [knowledge_mcq.py:L50-L73](file:///d:/SDC/LibraryLLM/rag/services/knowledge_mcq.py#L50-L73), [knowledge_quiz_relations.py:L174-L182](file:///d:/SDC/LibraryLLM/rag/services/knowledge_quiz_relations.py#L174-L182)
- **What to highlight on screen:**
  ```python
  # In knowledge_quiz_relations.py
  return not any(r['subjectId'] == left['subjectId'] and r['relationType'] == left['relationType']
                 and equivalent(r['targetText'], right['targetText']) for r in relations)

  # In knowledge_mcq.py
  if question['correctAnswer'] != expected or question['options'].count(expected) != 1: return 'ANSWER_KEY'
  if e.normalize(expected) in e.normalize(question['question']): return 'ANSWER_LEAK'
  if len(options) != 4 or len(set(question['options'])) != 4: return 'DUPLICATE_OPTION'
  ```
- **Spoken Script (55s):**
  > *"Next, let's look at how we guarantee quiz accuracy in `knowledge_mcq.py` and `knowledge_quiz_relations.py`. In `compatible()`, line 180 performs a crucial sanity check: it verifies that a distractor description is not asserted as true for the tested concept anywhere else in the document! Then in `verify()`, we run an 11-point quality gate: asserting exactly 4 unique options, verifying that the correct answer never leaks inside the question stem, and checking that every option links to verified source excerpt text."*

---

### Stop 5: Fill-in-the-Blank Semantic Grading (3:20 – 4:05)
- **File:** `LibraryLLM/rag/services/cloze_grading.py`
- **Function / Lines:** `grade()`, [cloze_grading.py:L161-L205](file:///d:/SDC/LibraryLLM/rag/services/cloze_grading.py#L161-L205)
- **What to highlight on screen:**
  ```python
  if kind in {'NUMBER','NUMBER_WITH_UNIT'}:
      return result('CORRECT' if quantity(canonical)==quantity(answer) else 'INCORRECT','QUANTITY')
  if NEGATION.search(actual) and not NEGATION.search(expected): return result('INCORRECT','NEGATION')
  ...
  sims=CACHE.similarities([actual,expected,normalize(item['sourceExcerpt']),*parts],encoder)
  if semantic>=.75 and evidence>=.55 and all(s>=.66 for s in clauses) and has_predicate:
      return result('CORRECT','SOURCE_PHRASE')
  ```
- **Spoken Script (45s):**
  > *"For fill-in-the-blank questions, grading is handled in `cloze_grading.py`. Line 161 handles dimensional numbers using Decimal scale conversion so '5 ms' equals '0.005 s'. Line 170 explicitly blocks false positives from negation words like 'not' or 'never'. For descriptive phrases, lines 198–205 embed the student's answer against the canonical answer, the source context, and every material clause, requiring at least 0.75 semantic similarity before marking it correct. Production telemetry explicitly logs zero Qwen calls and zero CUDA calls."*

---

### Stop 6: Interactive Mind Map Layout (4:05 – 4:40)
- **File:** `LibraryLLM/frontend/src/components/knowledge/mapLayout.ts`
- **Function / Lines:** `layoutKnowledgeMap()`, [frontend/src/components/knowledge/mapLayout.ts:L27-L47](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/mapLayout.ts#L27-L47)
- **What to highlight on screen:**
  ```typescript
  const sides: string[][] = [[], []], counts = [0, 0]
  for (const branch of children.get(root)!) {
    const side = counts[0] <= counts[1] ? 0 : 1
    sides[side].push(branch); counts[side] += weight.get(branch) || 1
  }
  ...
  positions.set(id, { x: centerX + (side ? -1 : 1) * depths.get(id)! * gap, y: top + (span - mapCardHeight) / 2 })
  ```
- **Spoken Script (35s):**
  > *"Finally, on the frontend in `mapLayout.ts`, we implemented an original balanced two-sided tree layout. Notice lines 27 through 31: root branches are partitioned into left and right columns using greedy bin-packing based on their cumulative subtree weights. This positions the document root directly in the center, opens up branches symmetrically on both sides, and routes smooth cubic bezier curves between card anchors on an interactive SVG canvas."*

---

### Stop 7: Catalogue Graph Explainability (4:40 – 5:00)
- **File:** `LibraryLLM/knowledge_graph/core.py`
- **Method / Lines:** `CatalogueGraph.more_like_this()`, [knowledge_graph/core.py:L70-L75](file:///d:/SDC/LibraryLLM/knowledge_graph/core.py#L70-L75)
- **Spoken Script (20s):**
  > *"To conclude, at the macro catalogue level, `core.py` uses SQLite relational joins to calculate bipartite TF-IDF cosine similarities, returning explainable 2-hop reason paths. That completes our tour of the LuminaR Knowledge Tools architecture."*
