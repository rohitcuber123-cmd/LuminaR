# 49_FAILURE_AND_RECOVERY.md: Failure Handling & Recovery Architecture

> **Audit Report:** Part 8 Research Evidence Audit  
> **Repository:** LuminaR (`d:\SDC\LibraryLLM`)  
> **Scope:** Resilience, Fault Modes, Error Propagation, Self-Healing, and Recovery Protocols Across Services  
> **Status:** Ground-Truth Code Verification  

---

## 1. System Failure Matrix

| Component / Failure Mode | Detection Point | Immediate System Reaction | HTTP Code | Rollback & Recovery Mechanism |
| :--- | :--- | :--- | :--- | :--- |
| **MongoDB Unavailable** | Startup lifespan (`main.py:37-48`) or driver query | PyMongo `ServerSelectionTimeoutError` / `ConnectionFailure`. App boot fails; runtime queries abort. | **500** | Fail-closed. Mutex locks cannot be acquired (`institution_locks`); no partial mutations succeed. |
| **Qwen Model Unavailable** | RAG boot (`rag/api.py:69`) or inference execution | CUDA OOM / `RuntimeError`. Service crashes at boot or request fails. Knowledge tools unaffected. | **500** / **503** | RAG API catches exception and returns 503 (`Document questions temporarily unavailable`). Study tools continue working. |
| **Embedding Model Unavailable** | Search / RAG startup (`luminar_search.py:136`) | `SentenceTransformer` fails with `OSError` (missing local weights). Model boot aborts. | **500** | Service refuses startup. No corrupted or zero-vector queries are emitted. |
| **HNSW Index Missing** | `IndexManager._startup_snapshot` (`index_manager.py:134`) | `FileNotFoundError` / `OSError`. Normal search service immediately halts startup. | **N/A (Crash)** | Refuses traffic unless started with `--recover`. Recovery worker rebuilds index from SQLite/Mongo corpus. |
| **HNSW Index Corrupted** | Graph validation (`index_manager.py:171`) | Dimension mismatch, count mismatch, or NaN vector detected. Raises `ValueError`. | **N/A (Crash)** | Rejects index load. Atomic version pointer (`active_index.json`) remains on last valid snapshot. |
| **PDF Extraction Fails** | Ingestion pipeline (`private_documents.py:129`) | `pymupdf` parser error, page count $> 10,000$, or zero usable text. | **400** / **413** | Immediate exception handler triggers `self.purge()`: deletes temporary disk folder and registry row. Zero orphans. |
| **Dataset Upload Fails Midway** | Multipart upload or batch import apply | Connection reset or parser error midway through stream. | **400** / **413** | Two-stage preview with TTL index (`expireAfterSeconds: 0`) purges ephemeral staging. Job marked `FAILED`. |
| **Document Deleted** | Document lookup (`private_documents.py:73`) | SQLite query `SELECT ... state='ACTIVE'` returns None. | **404** | Immediate HTTP 404. Vector files and disk directory are zeroed out via `PRAGMA secure_delete=ON`. |
| **Library Deleted / Suspended** | Tenant guard (`resolve_library_membership`) | Library query `status == 'ACTIVE'` fails. | **404** | Soft state transition (`REMOVED`). Resources concealed via HTTP 404. Restoration requires strict audit preflight. |

---

## 2. In-Depth Failure Mode Tracing

### 2.1 MongoDB Unavailable

#### A. Startup Failure
In `backend/main.py:35-48`, the FastAPI `lifespan` context manager calls index validation helpers on dedicated threads:
```python
await to_thread(ensure_asset_indexes)
await to_thread(ensure_catalogue_experience_indexes)
await to_thread(ensure_institution_indexes)
...
```
If MongoDB is unreachable, PyMongo throws `pymongo.errors.ServerSelectionTimeoutError`. The FastAPI server fails to complete initialization and terminates process execution immediately.

#### B. Runtime Read Failures
If MongoDB crashes while the API is running:
- All database queries (`find()`, `find_one()`, `aggregate()`) block until the driver timeout expires, then raise `ServerSelectionTimeoutError`.
- FastAPI returns an unhandled **HTTP 500 Internal Server Error**.

#### C. Runtime Mutation Failures (Fail-Closed Guarantees)
- Tenant write operations rely on `library_mutation(library_id)` in `backend/services/institution_repository.py:55-86`.
- The lock insertion `locks.insert_one({'_id': library_id, ...})` fails immediately if MongoDB is unavailable.
- **Guarantee:** No circulation state, holding count, copy assignment, or fee calculation is performed in memory without a durable database lock. Operations fail closed.

#### D. Semantic Search Fallback Behavior
In `search/catalogue.py:49-58`, candidate metadata resolution enforces strict database coupling:
```python
def current_books(collection, work_ids):
    """Fail closed on Mongo errors; never fall back to cached catalogue metadata."""
    ids = list(dict.fromkeys(wid for wid in work_ids if isinstance(wid, str) and wid))
    if not ids:
        return {}
    books = {book["work_id"]: book for book in collection.find(
        {"work_id": {"$in": ids}}, {"_id": 0}) if searchable(book)}
    ...
```
If MongoDB is down, `collection.find()` throws an error. The search API **refuses to serve stale or cached results** without MongoDB confirmation, preventing checkout of phantom books.

---

### 2.2 Qwen Generative Model Unavailable

#### A. Boot & Resource Failure
- Model: `Qwen/Qwen2.5-3B-Instruct` loaded in 4-bit NF4 (`bitsandbytes`) on GPU, or float32 on CPU.
- If CUDA VRAM is exhausted or model weights are missing:
  - Hugging Face transformers throws `torch.cuda.OutOfMemoryError` or `OSError`.
  - The RAG service (`rag/api.py`, Port 8005) terminates startup.
  - *Testing Bypass:* Setting `LUMINAR_MOCK_LLM=1` enables mock mode for testing retrieval pipelines without GPU hardware.

#### B. Runtime Inference Failure
- If an inference call times out or encounters a CUDA crash:
  - In `rag/services/library_asset_routes.py:41-48`:
    ```python
    try:
        return service.ask(str(library_id), str(asset_id), actor, request.query, request.depth)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Document questions are temporarily unavailable. Please retry.')
    ```
    The endpoint intercepts model failures and returns a clean **HTTP 503 Service Unavailable**.

#### C. Study Intelligence Tool Resilience
- **Crucial Architectural Decoupling:** Knowledge artifacts (extractive summaries, key concepts, hierarchical mind maps, flashcards, quizzes) generated in `rag/services/document_knowledge.py` **do not invoke Qwen**.
- They use deterministic frequency scoring, regex pattern extractors, and sentence boundary chunkers.
- **Result:** Even if the Qwen model is completely offline, crashes, or runs out of GPU memory, **all Knowledge Tools continue to generate study artifacts flawlessly**.

---

### 2.3 Embedding Model Unavailable

- Model: `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional Bi-Encoder).
- Loaded with `local_files_only=True` in `search/luminar_search.py:139`.
- If model cache directory is missing or corrupted:
  - `SentenceTransformer` throws `OSError`.
  - Search API (Port 8003) and RAG API (Port 8005) fail startup immediately.
- At runtime, `index_manager.py:159-163` validates generated embeddings:
  ```python
  if vectors.shape != (len(texts), self.dimension) or not np.isfinite(vectors).all():
      raise ValueError("Invalid generated embeddings")
  if np.any(np.linalg.norm(vectors, axis=1) < 1e-8):
      raise ValueError("Zero embedding")
  ```
  Any corrupted vector raises `ValueError` before reaching FAISS, preventing index pollution.

---

### 2.4 HNSW Vector Index Missing or Corrupted

#### A. Missing Index File
- In `search/index_manager.py:132-145`:
  ```python
  try:
      self.snapshot = self._startup_snapshot()
  except (ValueError, OSError, RuntimeError, KeyError):
      if not recover:
          raise
      self.snapshot = Snapshot(new_index(dimension), np.array([], dtype=str), ...)
      self.queue.request(kind="rebuild")
  ```
- If `hnsw.index` or `active_index.json` is missing:
  - The production search API crashes immediately on startup.
  - An operator must launch the recovery supervisor (`--recover`), which initializes an empty temporary graph and enqueues a full background catalogue rebuild.

#### B. Corrupted Index File
- `IndexManager._validate_graph()` enforces rigorous consistency invariants:
  1. `index.d == 384` (Exact vector dimensionality).
  2. `index.metric_type == METRIC_INNER_PRODUCT`.
  3. `index.ntotal == len(ids)` (Exact correspondence between vector count and mapping array).
  4. Work IDs array contains zero empty, null, or duplicate elements.
- If any invariant fails, `ValueError("Index/mapping/dimension mismatch")` is raised.

#### C. Atomic Snapshot Protection
- LuminaR never mutates the base HNSW graph in place.
- Updates write delta vectors to an isolated directory (`versions/<uuid>/`).
- Once validated, it atomically updates `active_index.json`.
- If an update crashes midway, `active_index.json` remains pointed at the last known valid snapshot.

---

### 2.5 PDF Extraction & Ingestion Failures

- **Source:** `rag/services/private_documents.py:124-159` (`_ingest`)
- **Failure Workflow:**
  ```python
  try:
      raw.write_bytes(content)
      pages = self.processor.extract_pdf(raw)
      if not 0 < len(pages) <= 10000:
          raise HTTPException(413, 'Document has too many pages.')
      ...
  except Exception:
      self.purge(meta['document_id'])
      raise
  ```
- If the PDF is password-protected, truncated, corrupt, or exceeds 10,000 pages:
  1. The exception block triggers `self.purge(meta['document_id'])`.
  2. The disk folder `rag/private_documents/doc_<uuid>/` is completely deleted.
  3. The SQLite registry entry is purged.
  4. Returns **HTTP 400 Bad Request** or **HTTP 413 Payload Too Large**.
  5. Leaves zero orphan files or incomplete vectors on disk.

---

### 2.6 Bulk Dataset Import Failures Midway

- **Source:** `backend/services/library_inventory_import.py`
- **Two-Stage Failure Isolation:**
  1. **Stage 1: Preview:** `POST .../inventory/imports/preview`
     - Reads CSV/XLSX into memory (max 5 MiB / 2,000 rows).
     - Inserts staged preview rows into `institution_inventory_previews`.
     - Staged rows have a MongoDB TTL index (`expires_at`, `expireAfterSeconds: 0`). If the user disconnects or abandons the preview, MongoDB automatically purges the data within minutes.
  2. **Stage 2: Application:** `POST .../imports/{id}/apply`
     - Runs under `library_mutation(library_id)` lock.
     - Tracks row-by-row imports using `institution_inventory_migrations` for idempotency.
     - If the worker process is killed midway, the import status remains `RECOVERY_REQUIRED`.
     - Re-running the import skips already committed rows (`source_key` unique index), preventing duplicate catalog entries.

---

### 2.7 Document & Library Deletion Cascades

#### A. Document Deletion
- Private document deletion (`rag/services/private_documents.py:purge`):
  - SQLite row status updated/deleted.
  - Disk directory purged.
  - Any subsequent query to `/rag/ask` or `/artifacts` calls `owned()`, which fails to find an active record and immediately returns **HTTP 404 Not Found**.

#### B. Library Deletion (Soft Removal & Recovery Preflight)
- **Source:** `backend/services/platform_library_service.py:13-16, 76-100`
- **Soft Delete State Machine:**
  Libraries are **never dropped physically from MongoDB**.
  $$\text{ACTIVE} \xrightarrow{\text{suspend}} \text{SUSPENDED} \xrightarrow{\text{remove}} \text{REMOVED}$$
- **Immediate Effect:**
  When a library is marked `REMOVED`:
  - `resolve_library_membership` checks `status: 'ACTIVE'`, which fails.
  - All tenant routes for that library immediately return **HTTP 404 Concealment**.
- **Restoration Preflight (`validate_restore`):**
  A removed library cannot be restored unless:
  1. Library owner account is active and verified.
  2. All operations in `institution_lending_operations` are `COMMITTED` (no dangling transactions).
  3. No imports are stuck in `APPLYING` or `RECOVERY_REQUIRED`.
  4. Circulation journal integrity audit (`reconcile()`) reports 100% mathematical consistency.
