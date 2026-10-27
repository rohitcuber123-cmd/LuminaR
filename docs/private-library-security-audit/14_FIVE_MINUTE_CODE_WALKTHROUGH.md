# 14 — FIVE-MINUTE LIVE CODE DEMONSTRATION SCRIPT

This document provides a timed, rehearsed 5-minute code demonstration script for your examination committee or viva reviewers. It proves the complete lifecycle of multi-library security and data isolation across 7 primary files.

---

## Demonstration Timeline Overview

```
 [0:00 - 0:45] File 1: backend/institution_dependencies.py (Dynamic Per-Request Authorization & 404 Concealment)
 [0:45 - 1:30] File 2: backend/services/institution_service.py (Identity Derivation & Argon2id Passphrase KDF)
 [1:30 - 2:15] File 3: backend/services/library_catalogue_repository.py (TenantInventory Query Scoping & Compound Indexes)
 [2:15 - 3:00] File 4: search/library_intelligence.py (Dedicated Per-Library FAISS Index Search)
 [3:00 - 3:45] File 5: rag/services/library_asset_pipeline.py (Ephemeral RAG Runtime Zeroing & Citation Validation)
 [3:45 - 4:15] File 6: backend/services/library_asset_service.py (Path Traversal Defense & File Sandbox)
 [4:15 - 5:00] File 7: tests/institution_v2f/test_assets.py (Automated Proof: Cross-Tenant Access Denied)
```

---

## Detailed Step-by-Step Script

### [MINUTE 0:00 – 0:45] STEP 1: Dynamic Per-Request Authorization
- **Action**: Open [backend/institution_dependencies.py](file:///d:/SDC/LibraryLLM/backend/institution_dependencies.py#L18-L45) in VS Code / Antigravity IDE. Highlight lines 18–45.
- **Spoken Script**:
  > "Distinguished reviewers, let's begin with how LuminaR handles tenant authorization.
  > Notice lines 18 to 45 in `backend/institution_dependencies.py`.
  > We deliberately decouple user identity from tenant permissions. Our JWTs do NOT embed static library permissions because tokens cannot be revoked immediately when a user is suspended.
  > Instead, on line 24, on every single incoming API request, `resolve_library_membership()` queries MongoDB collection `institution_memberships` in real time.
  > Look at line 42: if the user does not have an active membership in that library, we raise `HTTPException(404, 'Library resource not found.')`.
  > We return 404 rather than 403 to implement Information Concealment—preventing outsiders from discovering whether a private library or confidential research document exists."

---

### [MINUTE 0:45 – 1:30] STEP 2: Identity Derivation & Passphrase Security
- **Action**: Open [backend/services/institution_service.py](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L58-L86). Highlight lines 58–66 and 130–146.
- **Spoken Script**:
  > "Next, let's look at how libraries are created in `backend/services/institution_service.py`.
  > On line 59, `user_id = actor_id(current_user)` extracts the canonical numeric user ID directly from the validated JWT `sub` claim. The request model forbids client-supplied owner IDs, preventing any attacker from creating a library under a victim's name.
  > On line 65, the library is inserted with `status: 'PROVISIONING'`, making it completely undiscoverable until credentials and sequence counters are committed under a distributed lock.
  > For private libraries, the access passphrase is encrypted using Argon2id with RFC 9106 Low Memory Profile.
  > To prevent brute force, look at line 130: `consume_join_budget()` caps a user at 5 attempts per 15 minutes, and the library globally at 200 attempts per 15 minutes."

---

### [MINUTE 1:30 – 2:15] STEP 3: Database Scoping Wrapper (`TenantInventory`)
- **Action**: Open [backend/services/library_catalogue_repository.py](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_repository.py#L41-L67). Highlight lines 41–67.
- **Spoken Script**:
  > "Now, how do we guarantee that one library's catalog queries never return another library's books?
  > Rather than relying on raw MongoDB queries, all inventory reads and writes run through our custom `TenantInventory` class.
  > Look at line 45: `self.scope(query)` injects `library_id` into every query. On line 47, if an incoming query predicate attempts to query a different library, it throws `ValueError('Cross-library repository predicate rejected.')`.
  > On line 64, `update()` raises an error if any update attempts to modify the `library_id` field.
  > Furthermore, lines 10 to 22 show our compound unique indexes: uniqueness for ISBNs and accession numbers is enforced per `(library_id, field)`, so two institutions can upload identical books without collision."

---

### [MINUTE 2:15 – 3:00] STEP 4: Dedicated Semantic Search Indexes
- **Action**: Open [search/library_intelligence.py](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L87-L121). Highlight lines 94–107.
- **Spoken Script**:
  > "Here is our most important AI security contribution: Semantic Search Isolation.
  > Naive RAG and search systems use a single global vector index with post-filtering, which causes Recall Starvation and leaks foreign text into rerankers.
  > LuminaR builds dedicated separate FAISS indexes per library. Look at line 94: `self.cache.load()` loads the index belonging exclusively to that `library_id`.
  > On line 101, `index.search()` queries an index where 100% of the candidate vectors belong to that library.
  > On line 104, our CrossEncoder reranker scores only candidates from this library.
  > Finally, lines 112 to 114 hydrate the results against MongoDB, verifying that the books are still `ACTIVE` in that library."

---

### [MINUTE 3:00 – 3:45] STEP 5: Ephemeral RAG Runtime Swapping & Memory Zeroing
- **Action**: Open [rag/services/library_asset_pipeline.py](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L281-L311). Highlight lines 281–311.
- **Spoken Script**:
  > "For document question-answering, we use our local Qwen-2.5 LLM. How do we ensure document chunks don't linger in memory?
  > Look at `LibraryAssetPipeline.ask()` on lines 281 to 311.
  > On line 283, we acquire `engine.inference_lock`. On line 286, we call `self.clear_runtime()`, zeroing out all in-memory retriever vectors.
  > We read the single authorized document's `runtime.faiss`, inject its chunks into the retriever, re-verify user authority, and prompt Qwen.
  > Look at lines 303 to 307: we inspect every citation returned by the model to verify its `chunk_id` exists in the authorized document manifest.
  > And most importantly, on line 310, in a mandatory `finally:` block, we call `self.clear_runtime()` again to wipe GPU and CPU retriever memory completely clean."

---

### [MINUTE 3:45 – 4:15] STEP 6: Path Traversal & Filesystem Sandbox
- **Action**: Open [backend/services/library_asset_service.py](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L48-L67). Highlight lines 48–67.
- **Spoken Script**:
  > "On the storage layer, digital PDFs and DOCX files are protected against Path Traversal.
  > On line 50, `canonical_id()` validates that all path components parse as canonical UUIDs.
  > On lines 64 to 66 in `asset_directory()`, `path.resolve()` resolves all symlinks, and we assert that the storage root directory remains an ancestor of the resolved path.
  > Uploaded files are capped at 64 MiB by an ASGI middleware, checked for PDF magic bytes, and page counts are capped at 10,000 pages to defeat decompression bombs.
  > When files are served, we attach `Content-Security-Policy: sandbox; default-src 'none'` and `Cache-Control: private, no-store`."

---

### [MINUTE 4:15 – 5:00] STEP 7: Automated Integration Test Verification
- **Action**: Open [tests/institution_v2f/test_assets.py](file:///d:/SDC/LibraryLLM/tests/institution_v2f/test_assets.py#L145-L155). Highlight lines 145–155.
- **Spoken Script**:
  > "To conclude, everything I have shown is verified by automated integration tests.
  > Here in `tests/institution_v2f/test_assets.py`, line 146 defines `test_cross_tenant_asset_uuid_denied`.
  > Library B uploads an asset. A user in Library A attempts to download it using Library B's asset UUID. The test asserts that the response is strictly HTTP 404.
  > In `test_intelligence.py`, we test that building a search index in Library A includes zero books from Library B.
  > In summary, LuminaR enforces multi-tenancy at the network layer, authentication layer, database layer, filesystem layer, and AI vector layer.
  > Thank you. I am ready for your questions."
