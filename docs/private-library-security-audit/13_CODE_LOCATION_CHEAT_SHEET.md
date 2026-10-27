# 13 — REVIEWER CODE LOCATION GUIDE: "IF THE REVIEWER ASKS X, OPEN Y"

This cheat sheet provides instant, line-precise navigation instructions for live source-code demonstrations during your project review or viva examination.

---

## 1. Quick Navigation Master Table

| When the Reviewer Asks | Open File | Function / Class | Lines |
|---|---|---|---|
| **1. Where is a library created and owner assigned?** | `backend/services/institution_service.py` | `register_library` | [L58-86](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L58-L86) |
| **2. How are private library access codes hashed?** | `backend/services/institution_security.py` | `hash_code`, `verify_code` | [L10-27](file:///d:/SDC/LibraryLLM/backend/services/institution_security.py#L10-L27) |
| **3. Where is tenant membership verified on each request?** | `backend/institution_dependencies.py` | `require_library_membership` | [L18-45](file:///d:/SDC/LibraryLLM/backend/institution_dependencies.py#L18-L45) |
| **4. Why don't global account roles grant tenant admin?** | `backend/dependencies.py` | `require_roles` | [L27-32](file:///d:/SDC/LibraryLLM/backend/dependencies.py#L27-L32) |
| **5. Can platform admins access private library data?** | `backend/platform_dependencies.py` | `require_platform_admin` | [L42-46](file:///d:/SDC/LibraryLLM/backend/platform_dependencies.py#L42-L46) |
| **6. How does immediate session revocation work?** | `backend/services/login_sessions.py` | `is_revoked`, `revoke` | [L9-35](file:///d:/SDC/LibraryLLM/backend/services/login_sessions.py#L9-L35) |
| **7. How do you prevent cross-tenant MongoDB queries?** | `backend/services/library_catalogue_repository.py` | `TenantInventory.scope` | [L41-67](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_repository.py#L41-L67) |
| **8. Where are separate FAISS indexes built per library?** | `backend/services/library_intelligence_store.py` | `directory`, `source_records` | [L46-50, L66-86](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_store.py#L46-L50#L66-L86) |
| **9. How does semantic search isolate vector candidates?** | `search/library_intelligence.py` | `TenantIntelligence.semantic` | [L87-121](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L87-L121) |
| **10. Where is RAG memory wiped before and after queries?** | `rag/services/library_asset_pipeline.py` | `clear_runtime`, `ask` | [L271-311](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L271-L311) |
| **11. How do you verify citation chunk authenticity?** | `rag/services/library_asset_pipeline.py` | `ask` (citation loop) | [L303-307](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L303-L307) |
| **12. How do you prevent path traversal in file uploads?** | `backend/services/library_asset_service.py` | `canonical_id`, `asset_directory` | [L48-67](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L48-L67) |
| **13. Where is the 64 MiB upload limit enforced?** | `backend/services/library_asset_upload_limit.py` | `LibraryAssetUploadLimit` | [L1-35](file:///d:/SDC/LibraryLLM/backend/services/library_asset_upload_limit.py) |
| **14. Where are file download security headers set?** | `backend/routes/library_assets.py` | `file` | [L66-73](file:///d:/SDC/LibraryLLM/backend/routes/library_assets.py#L66-L73) |
| **15. How do you serialize concurrent circulation changes?** | `backend/services/institution_repository.py` | `library_mutation` | [L54-86](file:///d:/SDC/LibraryLLM/backend/services/institution_repository.py#L54-L86) |
| **16. How are single-use staff invite tokens hashed?** | `backend/services/institution_service.py` | `invite_staff` | [L241-268](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L241-L268) |
| **17. How do Knowledge Tools isolate cached flashcards?** | `rag/services/library_asset_pipeline.py` | `_cache_identity` | [L312-317](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L312-L317) |
| **18. Where is the join rate limiter budget stored?** | `backend/services/institution_service.py` | `consume_join_budget` | [L130-146](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L130-L146) |

---

## 2. Detailed Navigation Cards

### CARD 1: Library Creation & Identity Assignment
- **Reviewer Question**: *Where does the code ensure a user cannot register a library under someone else's account?*
- **File**: `backend/services/institution_service.py`
- **Function**: `register_library(request, current_user)`
- **Lines**: `58–65`
- **What to show**:
  ```python
  user_id = actor_id(current_user)
  library_id = str(uuid4())
  stamp = now()
  data = request.model_dump(mode='json', exclude={'access_code'})
  row = {**data, 'library_id': library_id, 'slug': data['slug'].lower(),
         'slug_normalized': data['slug'].lower(), 'owner_user_id': user_id,
         'status': 'PROVISIONING', 'created_at': stamp, 'updated_at': stamp}
  ```
- **What to say (20–40s)**: "Notice line 59: `user_id` is extracted strictly from `actor_id(current_user)`, which decodes the verified JWT `sub` claim. In line 64, `owner_user_id` is set to that authenticated identity. Client request schemas forbid passing an owner ID, completely preventing identity spoofing during library creation."

---

### CARD 2: Access Passphrase KDF (Argon2id)
- **Reviewer Question**: *Show me the code that hashes and verifies private library access codes.*
- **File**: `backend/services/institution_security.py`
- **Functions**: `hash_code(code)`, `verify_code(encoded, code)`
- **Lines**: `10–27`
- **What to show**:
  ```python
  hasher = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)

  def hash_code(code):
      if not isinstance(code, str) or not 8 <= len(code) <= 128:
          raise ValueError('Access code must contain 8 to 128 characters.')
      return hasher.hash(code)
  ```
- **What to say (20–40s)**: "Here we configure `argon2-cffi` using the RFC 9106 Low Memory Profile. Line 15 enforces an 8 to 128 character passphrase. In `verify_code()`, lines 24–26 catch `VerificationError` and return a clean boolean without leaking cryptographic tracebacks."

---

### CARD 3: Dynamic Authorization & Resource Concealment
- **Reviewer Question**: *Where does the backend verify membership and why does it return 404 instead of 403?*
- **File**: `backend/institution_dependencies.py`
- **Functions**: `resolve_library_membership()`, `require_library_membership()`
- **Lines**: `24–45`
- **What to show**:
  ```python
  def require_library_membership(library_id, current_user, *, locked=False):
      library, membership = resolve_library_membership(library_id, current_user, locked=locked)
      if not membership:
          # Conceal the existence of protected resources from outsiders, including global admins.
          raise HTTPException(404, 'Library resource not found.')
      return library, membership
  ```
- **What to say (20–40s)**: "Notice line 42: if the user does not have an active membership in that library, we raise HTTP 404 rather than 403. This is intentional Information Concealment to prevent attackers from probing endpoints to discover whether a private library or confidential research document exists."

---

### CARD 4: Database Scoping Wrapper (`TenantInventory`)
- **Reviewer Question**: *How do you prevent a developer from writing a query that returns another library's books?*
- **File**: `backend/services/library_catalogue_repository.py`
- **Class / Method**: `TenantInventory.scope(query)`
- **Lines**: `45–50`
- **What to show**:
  ```python
  def scope(self, query=None):
      query = dict(query or {})
      if 'library_id' in query and query['library_id'] != self.library_id:
          raise ValueError('Cross-library repository predicate rejected.')
      return {**query, 'library_id': self.library_id}
  ```
- **What to say (20–40s)**: "This is our `TenantInventory` repository wrapper. On line 47, if an incoming query attempts to filter on a different `library_id`, it raises `ValueError('Cross-library repository predicate rejected.')`. Every database operation automatically injects the tenant's canonical `library_id`."

---

### CARD 5: Dedicated FAISS Vector Index Retrieval
- **Reviewer Question**: *Prove to me that vector search does not use post-filtering over a shared index.*
- **File**: `search/library_intelligence.py`
- **Method**: `TenantIntelligence.semantic()`
- **Lines**: `94–102`
- **What to show**:
  ```python
  manifest, records, index = self.cache.load(library_id, 'SEARCH_INDEX',
      status['active_generation_id'], status['manifest_checksum'])
  ...
  scores, labels = index.search(vector, min(artifacts.PARAMETERS['candidate_count'], len(records)))
  ```
- **What to say (20–40s)**: "Notice line 94: `self.cache.load()` loads the dedicated FAISS index specifically built for `library_id`. In line 101, `index.search()` queries an index whose vector count equals `len(records)` for that library. There are zero foreign vectors in the index, completely eliminating recall starvation and vector contamination."

---

### CARD 6: Ephemeral RAG Memory Swapping & Zeroing
- **Reviewer Question**: *How do you ensure chunks from one library don't linger in memory for another user's RAG query?*
- **File**: `rag/services/library_asset_pipeline.py`
- **Method**: `LibraryAssetPipeline.ask()`
- **Lines**: `281–311`
- **What to show**:
  ```python
  with self.engine.inference_lock:
      row, directory, manifest, chunks = self.prepared(library_id, asset_id, actor)
      retriever = self.engine.reranker.retriever
      self.clear_runtime()
      try:
          index = faiss.read_index(str(index_path))
          retriever.doc_index = index
          ...
          result = self.engine.ask(question=query, depth=depth, document_id=manifest['document_id'])
          ...
      finally:
          self.clear_runtime()
  ```
- **What to say (20–40s)**: "Notice lines 286 and 310: Under `inference_lock`, we execute `clear_runtime()` before inference, load the single document's FAISS index into the retriever, prompt the LLM, and in a mandatory `finally:` block execute `clear_runtime()` again. This guarantees that GPU/CPU memory is completely zeroed out after every query."

---

### CARD 7: Citation Chunk ID Authenticity Check
- **Reviewer Question**: *What prevents an adversarial prompt from returning citations from another document?*
- **File**: `rag/services/library_asset_pipeline.py`
- **Method**: `LibraryAssetPipeline.ask()` (Citation validation loop)
- **Lines**: `303–307`
- **What to show**:
  ```python
  valid_ids = {c['chunk_id'] for c in chunks}
  for source in result.get('sources', []):
      if source.get('chunk_id') not in valid_ids:
          raise HTTPException(409, 'Document source identity could not be verified.')
      source.update(library_id=library_id, asset_id=asset_id)
  ```
- **What to say (20–40s)**: "Lines 303–307 inspect every source chunk returned by the LLM. If any citation `chunk_id` is not present in `valid_ids` (the authorized manifest for that asset), the response is aborted with HTTP 409, preventing citation spoofing."

---

### CARD 8: Path Traversal Defense
- **Reviewer Question**: *Where is path traversal blocked in file storage?*
- **File**: `backend/services/library_asset_service.py`
- **Functions**: `canonical_id()`, `asset_directory()`
- **Lines**: `48–67`
- **What to show**:
  ```python
  def asset_directory(library_id, asset_id):
      root = storage_root()
      path = root / canonical_id(library_id) / canonical_id(asset_id)
      resolved = path.resolve()
      if resolved != path or root not in resolved.parents:
          raise HTTPException(404, 'Library resource not found.')
      return path
  ```
- **What to say (20–40s)**: "Line 50 enforces UUID parsing on all IDs. Line 64 calls `path.resolve()` and line 65 checks `root not in resolved.parents`. If an attacker attempts to inject relative dots or symlinks, the check fails and raises HTTP 404."
