# 08 — KNOWLEDGE TOOLS & LIBRARY TRANSACTION ISOLATION

## 1. Knowledge Tools Privacy Architecture

Knowledge tools (Flashcards, Quizzes, Mind Maps, Summaries, Key Concepts) are generated from uploaded digital documents. In a multi-tenant platform, these tools must not leak confidential document concepts or questions across institutional boundaries.

### 1.1 Tenant & Asset Scoped Endpoints

In LuminaR, knowledge tools for library documents are exposed exclusively through tenant-bound URL paths:
- `GET /libraries/{library_id}/assets/{asset_id}/artifacts`
- `POST /libraries/{library_id}/assets/{asset_id}/artifacts/quiz`
- `POST /libraries/{library_id}/assets/{asset_id}/artifacts/{kind}` (`key-concepts`, `summary`, `flashcards`, `mindmap`)
- `GET /libraries/{library_id}/assets/{asset_id}/artifacts/{artifact_id}`
- `DELETE /libraries/{library_id}/assets/{asset_id}/artifacts/{artifact_id}`
- `POST /libraries/{library_id}/assets/{asset_id}/artifacts/{artifact_id}/cloze/{item_id}/grade`

Code reference: [rag/services/library_asset_routes.py:L49-79](file:///d:/SDC/LibraryLLM/rag/services/library_asset_routes.py#L49-L79).

### 1.2 Tenant-Partitioned Cache Hashing

Generated knowledge tools are cached on disk to avoid redundant CPU execution. The cache key is computed with strict tenant binding:
- Code reference: [rag/services/library_asset_pipeline.py:L312-317](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L312-L317):
  ```python
  def _cache_identity(self, row, manifest, kind, options):
      return hashlib.sha256(json.dumps([
          row['library_id'],
          row['asset_id'],
          row['active_generation_id'],
          row['checksum'],
          manifest['files']['chunks.json'],
          kind,
          options,
          document_knowledge.VERSION,
          knowledge_algorithms.VERSION,
          knowledge_quiz.VERSION,
          knowledge_quiz_evidence.VERSION,
          knowledge_quiz_relations.VERSION,
          knowledge_cloze.VERSION
      ], sort_keys=True).encode()).hexdigest()
  ```
- **Guaranteed Separation**: The SHA-256 digest incorporates `library_id` and `asset_id`. Even if two separate libraries upload identical PDF textbooks, their cache keys and cache file locations are physically distinct.
- **Physical Storage Location**:
  `local-data/library-assets/{library_id}/{asset_id}/generation/{generation_id}/knowledge/{cache_key}.json`
- **Cascade Deletion**: When an asset or library is deleted, removing the asset directory automatically eradicates all generated flashcards, quizzes, and mind maps.

### 1.3 Artifact Output Validation (`valid_artifact`)
Before returning any cached artifact to the caller:
- Code reference: [rag/services/library_asset_pipeline.py:L320-331](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L320-L331):
  ```python
  @staticmethod
  def valid_artifact(artifact, row, manifest, kind, options):
      return (artifact.get('libraryId') == row['library_id'] 
          and artifact.get('assetId') == row['asset_id']
          and artifact.get('documentId') == row['asset_id'] 
          and artifact.get('type') == kind
          and artifact.get('options') == options 
          and artifact.get('sourceRevision') == manifest['files']['chunks.json']
          and isinstance(artifact.get('sourceChunkIds'), list)
          and all(isinstance(source, str) and source.startswith(manifest['document_id'] + '_')
                  for source in artifact['sourceChunkIds']))
  ```
- The validator ensures that every source chunk cited in the generated tool belongs strictly to the authorized document manifest.

---

## 2. Physical Circulation & Transaction Isolation

Circulation operations (borrowing, returning, renewals) alter physical book availability and involve financial ledger adjustments (fines and fees). Cross-library transaction manipulation could allow a patron in Library A to borrow or alter holdings in Library B.

### 2.1 Complete Circulation State Machine

```
   [ Patron Submits Borrow Request ]
                 │
   POST /libraries/{library_id}/lending/borrow-requests
                 │
                 ├── Checks active GENERAL_USER membership in library_id
                 ├── Serializes under library_mutation(library_id, durable=True)
                 ├── Verifies book belongs to library_id (status: ACTIVE)
                 ├── Verifies holding available_copies >= 1
                 └── Creates record in institution_lending_requests {status: 'PENDING'}
                 │
                 ▼
   [ Staff Review: Approve or Reject ]
                 │
   POST /libraries/{library_id}/staff/lending/borrow-requests/{req_id}/approve
                 │
                 ├── Checks ADMIN or LIBRARIAN role in library_id
                 ├── Serializes under library_mutation
                 ├── Decrements holding.available_copies
                 ├── Inserts into institution_loans {status: 'ACTIVE', due_at: now + 14d}
                 └── Appends to durable journal & institution_audit
                 │
                 ▼
   [ Book Return Lifecycle ]
                 │
   POST /libraries/{library_id}/loans/{loan_id}/return-request
   POST /libraries/{library_id}/staff/lending/return-requests/{req_id}/confirm
                 │
                 ├── Increments holding.available_copies
                 ├── Marks loan status = 'RETURNED'
                 └── Calculates overdue fees (if returned past due_at)
```

### 2.2 Cross-Library Transaction Defense

Could a malicious user pass a `library_book_id` or `loan_id` belonging to Library B in a request to Library A?
- Code reference: [backend/services/library_lending_service.py:scoped](file:///d:/SDC/LibraryLLM/backend/services/library_lending_service.py):
  ```python
  def scoped(library_id, **kwargs):
      return {'library_id': canonical_id(library_id), **kwargs}
  ```
- In all circulation queries, the lookup filter explicitly enforces `library_id`:
  - `collection('loans').find_one({'library_id': library_id, 'loan_id': loan_id})`
  - `collection('holdings').find_one({'library_id': library_id, 'library_book_id': book_id})`
- If an attacker provides a `loan_id` from Library B to Library A's endpoint, the database query returns `None`, resulting in HTTP 404.

### 2.3 Atomic Concurrency & Mutual Exclusion (`library_mutation`)

To prevent race conditions where two simultaneous borrow requests over-allocate the last remaining copy of a book:
- Code reference: [backend/services/institution_repository.py:L55-86](file:///d:/SDC/LibraryLLM/backend/services/institution_repository.py#L55-L86):
  ```python
  @contextmanager
  def library_mutation(library_id, *, wait_seconds=3, durable=False):
      locks = collection('locks')
      if durable:
          from pymongo.write_concern import WriteConcern
          locks = locks.with_options(write_concern=WriteConcern(w=1, j=True))
      holder = str(uuid4())
      deadline = monotonic() + wait_seconds
      while True:
          try:
              locks.insert_one({'_id': library_id, 'holder': holder, 'created_at': now()})
              break
          except DuplicateKeyError:
              if monotonic() >= deadline:
                  raise HTTPException(503, 'Library update in progress. Please retry.', headers={'Retry-After': '3'})
              sleep(0.02)
      try:
          yield
      finally:
          locks.delete_one({'_id': library_id, 'holder': holder})
  ```
- **Cross-Worker Mutual Exclusion**: Backed by a MongoDB unique index on `_id` in `institution_locks`.
- **Durable Write Concern**: Uses `w=1, j=True` ensuring journal sync before releasing the lock.
- **Fail-Closed on Unhandled Crash**: If an unhandled exception crashes a worker mid-mutation, the lock is retained to prevent inconsistent state, and reading endpoints return HTTP 503 (`require_readable`) until an operator reconciles the journal.

---

## 3. Reservations & Fee Management Isolation

### 3.1 Reservation Queuing Isolation
- Code reference: [backend/services/library_reservation_service.py:create](file:///d:/SDC/LibraryLLM/backend/services/library_reservation_service.py):
  - Max active reservations per patron: 5 (`max_active_reservations = 5`).
  - Patrons can only reserve books if all physical copies are currently on loan.
  - Queue sequence is assigned atomically per book holding:
    `queue_scope = {'library_id': library_id, 'library_book_id': book_id, 'status': 'WAITING'}`.
  - Position calculation and queue advancement are strictly bounded to that library.

### 3.2 Fee Calculations & Waiver Controls
- Code reference: [backend/services/library_fee_service.py](file:///d:/SDC/LibraryLLM/backend/services/library_fee_service.py):
  - Overdue fees are automatically generated when loans are returned late.
  - Fee types: `OVERDUE`, `DAMAGE`, `LOST`, `MANUAL_ADJUSTMENT`.
  - Fee mutations (`waive`, `adjust`) require `require_library_staff` (`ADMIN` or `LIBRARIAN`).
  - All waivers record `waived_by_user_id`, `reason`, and timestamp in `institution_fees` and append an immutable event to `institution_audit`.

---

## 4. Summary for Viva Defense

1. **Knowledge Tools Scoping**: All tool generation and caching is strictly partitioned by `library_id` and `asset_id`. Cache identity incorporates tenant identifiers in the SHA-256 hash.
2. **Transaction Integrity**: Circulation operations are protected against race conditions via `library_mutation` locks and durable journaling.
3. **No Cross-Tenant Lending**: Every loan, holding, and copy query enforces `library_id` matching, preventing cross-tenant borrowing or inventory manipulation.
