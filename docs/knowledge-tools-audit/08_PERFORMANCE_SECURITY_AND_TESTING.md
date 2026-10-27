# LuminaR Performance, Security, Persistence, and Testing Audit

## 1. Executive Summary

This report analyzes the non-functional architecture of the LuminaR Knowledge Tools module, focusing on **persistence schemas, multi-tier caching, concurrency controls, security guards, and automated test coverage**.

---

## 2. Database & Persistence Architecture

### 2.1 SQLite Schema (`registry.sqlite`)
For personal uploads, knowledge data is persisted in the session database (`registry.sqlite`) managed by `PrivateDocuments` and `KnowledgeArtifacts` ([knowledge_artifacts.py:L31-L38](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L31-L38)):

```sql
-- 1. Rendered Artifacts Table
CREATE TABLE IF NOT EXISTS knowledge_artifacts (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    owner TEXT NOT NULL,
    type TEXT NOT NULL,
    cache_key TEXT NOT NULL,
    payload TEXT NOT NULL,
    updated REAL NOT NULL,
    UNIQUE(document_id, owner, type, cache_key)
);

-- 2. Shared Intermediate Study Model Table
CREATE TABLE IF NOT EXISTS document_knowledge (
    document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
    owner TEXT NOT NULL,
    revision TEXT NOT NULL,
    version TEXT NOT NULL,
    payload TEXT NOT NULL
);
```

### 2.2 Filesystem Persistence for Institutional Assets
For library assets, artifacts and models are saved in the asset directory under `knowledge/` ([library_asset_pipeline.py:L348-L370](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L348-L370)):
- Intermediate Model: `knowledge/{model_key}.model.json`
- Rendered Artifact: `knowledge/{cache_key}.json`
- Writes use atomic POSIX replacement (`atomic_json()` with `.tmp` staging and `os.fsync`) to prevent corrupted reads during power cuts or crashes ([library_asset_pipeline.py:L46-L65](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L46-L65)).

### 2.3 Deletion & Cascade Behavior
- **Document Purge**: When `PrivateDocuments.purge(document_id)` is invoked, the SQLite foreign key cascade (`PRAGMA foreign_keys=ON;`) automatically drops all associated rows from both `document_knowledge` and `knowledge_artifacts`.
- **User Logout**: Calling `PrivateDocuments.logout(user)` clears the session documents and cascades to delete all cached models and study artifacts ([test_knowledge_artifacts.py:L302-L309](file:///d:/SDC/LibraryLLM/tests/test_knowledge_artifacts.py#L302-L309)).
- **Library Asset Deletion**: Restricted strictly to staff accounts (`staff=True`); patrons attempting to call `DELETE` receive HTTP 403 ([library_asset_pipeline.py:L426](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L426)).

---

## 3. Caching Mechanics & Invalidation Strategy

LuminaR implements a multi-tier caching hierarchy to eliminate duplicate computation:

```
[Incoming Request]
        |
        v
1. Artifact Cache Check (SQLite knowledge_artifacts)
   Key = SHA256(revision, kind, scope, options, generator_version, knowledge_version)
        |
   +----+----+
   |         |
 [HIT]     [MISS]
   |         |
Return     2. DocumentKnowledgeModel Cache Check (SQLite document_knowledge)
JSON       Key = (document_id, owner, revision, VERSION)
             |
        +----+----+
        |         |
      [HIT]     [MISS]
        |         |
     Return     Build Model (Extract units, score concepts, 1 CPU embed batch)
     Memory     Store in document_knowledge
     Model        |
        +---------+
        |
3. Render Requested Artifact (Zero chunks read, Zero embeddings)
   Store in knowledge_artifacts
```

### 3.1 Content Revision Integrity
The document revision is computed directly from the byte-level hash of the extracted chunks file:
$$\text{revision} = \text{SHA256}(\text{chunks.json})$$
If the source PDF is re-uploaded or edited, `revision` changes, immediately invalidating all previous artifact and model cache entries.

### 3.2 Generator Version Invalidation
If the algorithm code is updated (e.g., `knowledge_quiz.VERSION` changes from `'3.2.1'` to `'3.2.2'`), the cache key changes, forcing the system to regenerate the artifact without serving stale formats ([test_knowledge_artifacts.py:L245-L248](file:///d:/SDC/LibraryLLM/tests/test_knowledge_artifacts.py#L245-L248)).

---

## 4. Concurrency & Rate Limiting Controls

To prevent resource exhaustion on local machines, the service implements four distinct concurrency safeguards:

1. **Global Concurrency Semaphore**:
   - `self._capacity = Semaphore(3)` in [knowledge_artifacts.py:L29](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L29).
   - At most 3 artifact generation jobs can execute simultaneously across the entire server.
   - Additional requests immediately fail with HTTP 429 (`"Knowledge Tools is busy. Please retry shortly."`).
2. **Per-Owner Single-Flight Lock**:
   - `self._owners = set()` in [knowledge_artifacts.py:L28](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L28).
   - A single user session cannot launch multiple parallel generation jobs across tabs.
3. **Leader / Follower Job Collapsing**:
   - If two identical requests arrive for the same job parameters, subsequent requests join the leader's `concurrent.futures.Future` and await completion with a 25-second timeout ([knowledge_artifacts.py:L108-L122](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L108-L122)).
4. **Debounced Semantic Cache (`SemanticCache`)**:
   - Cloze phrase grading requests collect in a 5-millisecond window thread-safe queue (`time.sleep(0.005)`).
   - Common phrases share embedding computations, bounded to 64 concurrent jobs and 512 cached vectors ([cloze_grading.py:L90-L143](file:///d:/SDC/LibraryLLM/rag/services/cloze_grading.py#L90-L143)).

---

## 5. Security & Authorization Architecture

### 5.1 Authentication & Session Lifetimes
- Every request validates the Bearer token via `get_current_user` ([backend/dependencies.py](file:///d:/SDC/LibraryLLM/backend/dependencies.py)).
- Checks `time.time() < user['exp']`.
- Validates that the session ID has not been revoked: `is_revoked(user['sid'])` in SQLite `sessions.sqlite`.

### 5.2 Path Traversal Defense
In institutional asset operations, path traversals (e.g. `../../etc/passwd`) are strictly blocked by `safe_child()` ([library_asset_pipeline.py:L68-L74](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L68-L74)):
```python
def safe_child(directory, *parts):
    directory = Path(directory)
    target = directory.joinpath(*parts)
    if target.resolve() != target or directory not in target.parents:
        raise HTTPException(404, 'Document not found.')
    return target
```

### 5.3 Memory & Cache Header Protections
- `response.headers['Cache-Control'] = 'no-store'` is attached to all artifact endpoints to prevent shared browser caches from storing private document notes.
- Private document IDs use 128-bit cryptographically secure UUIDs (`'doc_' + uuid4().hex`).

---

## 6. Automated Testing Suite Audit

The repository contains an extensive automated test suite covering all knowledge algorithms, contracts, and edge cases:

| Test File | Test Focus & Verification Scope | Lines | Status |
|---|---|---|---|
| [test_knowledge_algorithms.py](file:///d:/SDC/LibraryLLM/tests/test_knowledge_algorithms.py) | Verifies concept extraction, summaries, definition filters, mind map cycles, safe quiz fallback, and AST import restrictions. | 120 lines | **PASS** |
| [test_document_knowledge.py](file:///d:/SDC/LibraryLLM/tests/test_document_knowledge.py) | Tests educational quality contracts, hyphen normalization, boilerplate rejection, multi-page provenance, MMR vector deduplication. | 132 lines | **PASS** |
| [test_knowledge_artifacts.py](file:///d:/SDC/LibraryLLM/tests/test_knowledge_artifacts.py) | Tests FastAPI routes, SQLite persistence, cache invalidation, logout purging, semaphore admission, and concurrent jobs. | 357 lines | **PASS** |
| [test_quiz_v2_2.py](file:///d:/SDC/LibraryLLM/tests/test_quiz_v2_2.py) | Tests MCQ stem-answer binding, option uniqueness, peer compatibility, and verifier rejections. | 225 lines | **PASS** |
| [test_cloze_v2_3.py](file:///d:/SDC/LibraryLLM/tests/test_cloze_v2_3.py) | Tests Cloze normalization, safe typos, dimensional numbers (`5 ms` $\leftrightarrow$ `0.005 s`), acronym aliases, and semantic grading. | 172 lines | **PASS** |
| [mind-map.test.tsx](file:///d:/SDC/LibraryLLM/frontend/tests/mind-map.test.tsx) | Frontend JSDOM tests verifying balanced two-sided tree layout, wheel delta panning, pointer capture, and fullscreen focus trapping. | 83 lines | **PASS** |
| [knowledge-artifacts.test.tsx](file:///d:/SDC/LibraryLLM/frontend/tests/knowledge-artifacts.test.tsx) | Comprehensive React testing-library suite for `KnowledgeTools.tsx`, flashcards, quiz steppers, and source link drawers. | 510 lines | **PASS** |

---

## 7. Edge Case Behavior Matrix

| Edge Case Scenario | System Response & Safeguard in Code |
|---|---|
| **Empty Document** | Returns clean empty responses: `{"questions": [], "messages": [...]}`. No crashes or division by zero ([test_knowledge_algorithms.py:L100-L104](file:///d:/SDC/LibraryLLM/tests/test_knowledge_algorithms.py#L100-L104)). |
| **Very Large PDF (>64 MB)** | `_source()` checks file size and raises `HTTP 413: This document is too large for Knowledge Tools` ([knowledge_artifacts.py:L86-L87](file:///d:/SDC/LibraryLLM/rag/services/knowledge_artifacts.py#L86-L87)). |
| **Document with >1,200 Chunks** | Samples chunks evenly across document using `indexes = [i * (N-1) // (MAX-1)]` and flags `artifact.analysis.sampled = True` ([knowledge_algorithms.py:L43](file:///d:/SDC/LibraryLLM/rag/services/knowledge_algorithms.py#L43)). |
| **Scanned / OCR PDF** | Verified by `private_document_ocr.py`. If OCR text is corrupted ($<55\%$ alphabetic density), relation records are rejected with `OCR_CORRUPTION` ([knowledge_quiz_relations.py:L119-L122](file:///d:/SDC/LibraryLLM/rag/services/knowledge_quiz_relations.py#L119-L122)). |
| **Document Lacks Definitions** | Quiz falls back gracefully to Clozes and Section topic MCQs. If insufficient items exist, displays explicit explanatory notice in UI ([KnowledgeTools.tsx:L146](file:///d:/SDC/LibraryLLM/frontend/src/components/knowledge/KnowledgeTools.tsx#L146)). |
| **Simultaneous Users** | Enforced by `Semaphore(3)` and per-user lock. User 1 and User 2 generate in parallel up to capacity; extra requests receive HTTP 429 ([test_knowledge_artifacts.py:L333-L357](file:///d:/SDC/LibraryLLM/tests/test_knowledge_artifacts.py#L333-L357)). |
