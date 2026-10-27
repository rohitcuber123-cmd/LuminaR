# 16 — WORKED EXAMPLE, PRODUCTION READINESS & FUTURE ROADMAP

## 1. Complete Worked Synthetic Example: Two Separate Libraries

To understand how LuminaR separates two institutional libraries in practice, we trace two synthetic institutions through registration, dataset ingestion, search, RAG, and access control:

- **Library A: Computer Science Library**
  - Identifier: `lib_cs` (`11111111-1111-4111-8111-111111111111`)
  - Owner: User 1 (`alice@cs.edu`, numeric `user_id = 1`)
  - Holdings: Books on Distributed Systems, Networks, Algorithms.
- **Library B: Medical Research Library**
  - Identifier: `lib_med` (`22222222-2222-4222-8222-222222222222`)
  - Owner: User 2 (`bob@med.edu`, numeric `user_id = 2`)
  - Holdings: Books on Anatomy, Pharmacology, Pathology.

---

### Step 1: Library Creation & Database Ingestion

Alice registers Library A:
- `POST /libraries/register` with payload:
  `{"name": "Computer Science Library", "slug": "cs-lib", "access_mode": "PRIVATE_CODE", "access_code": "SuperSecretCS2026!"}`
- BackendDerives `owner_user_id = 1` from Alice's JWT `sub`.
- Generates UUID `lib_cs`.
- Hashes access code with **Argon2id** and inserts into `institution_security`.
- Inserts Alice into `institution_memberships` with role `'ADMIN'`.

Bob registers Library B:
- `POST /libraries/register` with payload:
  `{"name": "Medical Research Library", "slug": "med-lib", "access_mode": "PUBLIC"}`
- Backend Derives `owner_user_id = 2` from Bob's JWT `sub`.
- Generates UUID `lib_med`.
- Inserts Bob into `institution_memberships` with role `'ADMIN'`.

### Step 2: Book Ingestion & Storage Partitioning

Alice uploads a catalog book in Library A:
- Book: *"Distributed Systems: Principles and Paradigms"*
- Saved in MongoDB `institution_library_books`:
  ```json
  {
    "library_book_id": "aaa11111-0000-0000-0000-000000000001",
    "library_id": "11111111-1111-4111-8111-111111111111",
    "title": "Distributed Systems: Principles and Paradigms",
    "authors": ["Andrew S. Tanenbaum", "Maarten van Steen"],
    "accession_number": "CSL-000001",
    "status": "ACTIVE"
  }
  ```

Bob uploads a book in Library B:
- Book: *"Robbins & Cotran Pathologic Basis of Disease"*
- Saved in MongoDB `institution_library_books`:
  ```json
  {
    "library_book_id": "bbb22222-0000-0000-0000-000000000002",
    "library_id": "22222222-2222-4222-8222-222222222222",
    "title": "Robbins & Cotran Pathologic Basis of Disease",
    "authors": ["Vinay Kumar", "Abul K. Abbas"],
    "accession_number": "MED-000001",
    "status": "ACTIVE"
  }
  ```

### Step 3: Intelligence Build & FAISS Index Partitioning

Alice triggers index build in Library A:
- `POST /libraries/11111111-1111-4111-8111-111111111111/intelligence/builds` (`SEARCH_INDEX`)
- Worker extracts records where `library_id == '11111111-1111-4111-8111-111111111111'` (1 book).
- Compiles MiniLM embeddings into FAISS index at:
  `local-data/library-intelligence/11111111-1111-4111-8111-111111111111/search/gen_cs/index.faiss`
- `index.ntotal = 1`.

Bob triggers index build in Library B:
- `POST /libraries/22222222-2222-4222-8222-222222222222/intelligence/builds` (`SEARCH_INDEX`)
- Worker extracts records where `library_id == '22222222-2222-4222-8222-222222222222'` (1 book).
- Compiles MiniLM embeddings into FAISS index at:
  `local-data/library-intelligence/22222222-2222-4222-8222-222222222222/search/gen_med/index.faiss`
- `index.ntotal = 1`.

### Step 4: Semantic Search Execution

Alice searches for *"consensus and replication"*:
- `GET /libraries/11111111-1111-4111-8111-111111111111/catalogue/search?search=consensus`
- System loads `gen_cs/index.faiss` (containing only Tanenbaum).
- Vector candidate retrieved: Tanenbaum ($100\%$ match).
- Hydrated from MongoDB `institution_library_books`.
- Output: Returns *"Distributed Systems: Principles and Paradigms"*.

### Step 5: Adversarial Cross-Tenant Access Attempt

Alice attempts to search or view Bob's Medical Library:
- Alice sends request:
  `GET /libraries/22222222-2222-4222-8222-222222222222/catalogue/search?search=pathology`
  Header: `Authorization: Bearer <Alice's JWT>`
- Execution in `backend/institution_dependencies.py`:
  1. `actor_id(Alice's JWT)` returns `user_id = 1`.
  2. Queries `institution_memberships` for `{'library_id': '22222222-2222-4222-8222-222222222222', 'user_id': 1, 'status': 'ACTIVE'}`.
  3. Returns `None` (Alice has no membership in Medical Library).
  4. Line 43: `raise HTTPException(404, 'Library resource not found.')`.
- **Result**: Alice receives HTTP 404. Bob's library, books, and vector indexes remain completely inaccessible.

---

## 2. Production-Readiness Checklist for Real Universities

Before deploying LuminaR across real-world university campuses and enterprise library networks, the following production checklist must be completed:

### 2.1 Infrastructure & Transport Security
- [ ] **TLS Termination**: Deploy Nginx / Caddy reverse proxy with Let's Encrypt TLS 1.3 certificates. Redirect all HTTP traffic to HTTPS.
- [ ] **WiredTiger Encryption-at-Rest**: Configure MongoDB native AES-256 encryption-at-rest with key management (KMIP or local keyfile).
- [ ] **Filesystem Volume Encryption**: Ensure host disk partitions mounting `local-data/` and `rag/` use LUKS (Linux) or BitLocker (Windows).
- [ ] **CORS Restriction**: Update `ALLOWED_ORIGINS` in `backend/main.py` and `rag/api.py` from `localhost` to verified university domain origins (e.g., `https://library.university.edu`).

### 2.2 Identity & Access Governance
- [ ] **SAML 2.0 / Shibboleth Integration**: Integrate university campus Single Sign-On (SSO) so student and faculty campus IDs automatically provision matching `institution_memberships`.
- [ ] **Distributed Session Revocation**: Migrate `revoked_sessions` from local SQLite (`private_sessions.sqlite`) to a resilient Redis cluster.
- [ ] **Distributed Rate Limiting**: Shift `consume_join_budget` and global auth rate limiters to Redis.

### 2.3 AI & Scalability Hardening
- [ ] **Decoupled Model Inference Cluster**: Shift Qwen-2.5-3B-Instruct serving from in-process FastAPI to a dedicated vLLM / Triton cluster with continuous batching and multi-GPU tensor parallelism.
- [ ] **Object Storage for Artifacts**: Migrate `local-data/` filesystem directories to S3-compatible object storage (e.g., MinIO or AWS S3), downloading FAISS indexes to local worker SSD cache on-demand.
- [ ] **Automated Dead-Man Switch for Locks**: Add an automated 30-second lease timeout on `institution_locks` so an unexpected worker SIGKILL does not require manual operator intervention.

---

## 3. Final Implementation Cheat Sheet

| Reviewer Asks | Actual Verified Implementation | Code Location | Security Guarantee | Known Architectural Limitation |
|---|---|---|---|---|
| **Multi-Tenancy Model** | Hybrid Model: Shared collections in MongoDB; separate physical FAISS indexes per library. | `institution_repository.py:collection`, `library_intelligence_store.py:directory` | High database efficiency with zero vector candidate contamination. | Shared DB requires application-level scoping. |
| **Active Context Derivation** | Canonical UUID in URL path `/libraries/{id}`; membership queried from DB on every request. | `backend/institution_dependencies.py:require_library_membership` | Immune to stale JWT token privilege leakage. | Adds 1–3 ms indexed MongoDB lookup overhead. |
| **Passphrase KDF** | Argon2id RFC 9106 Low Memory Profile; rate-limited brute force budget in MongoDB. | `institution_security.py:hash_code`, `institution_service.py:consume_join_budget` | Resistant to GPU/ASIC cracking and distributed dictionary attacks. | Memory intensive during concurrent join bursts. |
| **Database Scoping** | `TenantInventory.scope()` wrapper rejects any query predicate matching a foreign library. | `library_catalogue_repository.py:TenantInventory` | Automated programmatic barrier against cross-tenant queries. | Developers must route queries through `TenantInventory`. |
| **Semantic Search Isolation** | Dedicated physical FAISS index per library; candidate space $100\%$ scoped to tenant. | `search/library_intelligence.py:TenantIntelligence.semantic` | Complete elimination of Recall Starvation and reranker leaks. | LRU cache limited to 2 resident tenants in memory. |
| **RAG Runtime Isolation** | Ephemeral runtime swapping; memory wiped with `clear_runtime()` before and in `finally:`. | `rag/services/library_asset_pipeline.py:ask` | In-memory retriever contains zero foreign chunks; verified citations. | Global `inference_lock` serializes GPU inference across tenants. |
| **Path Traversal Defense** | Canonical UUID validation; `Path.resolve()` verifying boundary containment. | `library_asset_service.py:asset_directory`, `safe_child` | Immune to dot-dot (`..`) and symlink directory escape attacks. | Local filesystem storage requires single-node deployment. |
| **Staff Invitations** | 256-bit CSPRNG token stored as SHA-256 hash; inviter authority re-verified upon acceptance. | `institution_service.py:invite_staff`, `respond_invitation` | Stored hashes cannot leak raw tokens; former admins cannot leave backdoors. | Invitations expire after 7 days. |

---

## 4. Architectural Defense Summary for Examination

### One-Line Verified Architecture
> **User $\longrightarrow$ JWT Authentication $\longrightarrow$ Dynamic DB Membership Validation $\longrightarrow$ Tenant-Scoped API $\longrightarrow$ `TenantInventory` DB Scoping $\longrightarrow$ Dedicated Tenant Vector Index $\longrightarrow$ Ephemeral RAG Inference $\longrightarrow$ Verified Response.**

### Top 5 Strongest Architectural Contributions
1. **Dedicated Per-Library FAISS Indexes**: Solved the multi-tenant vector search dilemma by eliminating Recall Starvation and candidate cross-contamination without requiring separate vector database servers.
2. **Ephemeral RAG Memory Swapping**: Sandboxed local LLM inference under mutual exclusion with guaranteed `finally: clear_runtime()` memory scrubbing and citation chunk validation.
3. **Decoupled Identity and Dynamic Authority**: Stateless JWTs provide user identity only; tenant membership is dynamically evaluated on every request, enabling immediate permission revocation.
4. **Programmatic Scoping Repository (`TenantInventory`)**: Intercepts and rejects cross-tenant database predicates at the repository layer before queries reach MongoDB.
5. **Information Concealment by Design**: Unauthorized callers receive HTTP 404 rather than HTTP 403, preventing enumeration of private libraries and research documents.

### Top 5 Strongest Verified Security Protections
1. **Argon2id Passphrase KDF**: Memory-hard KDF with dual-scope bucketed brute-force rate-limiting (5/15m per user, 200/15m per library).
2. **CSPRNG Staff Invitation Tokens**: 256-bit entropy raw tokens returned once, stored as SHA-256 hashes, bound to verified account email, and invalidated if the inviting admin loses authority.
3. **Double Authority Recheck in RAG**: Re-evaluates membership immediately before LLM forward-pass and immediately post-generation to prevent TOCTOU race condition exploits.
4. **Path Traversal Fencing**: All path components are validated as canonical UUIDs, and all directory accesses are bounded using `Path.resolve()` boundary checks.
5. **Durable Mutual Exclusion (`library_mutation`)**: Cross-worker mutex backed by MongoDB unique indexes with journaled write concern (`j=True`), failing closed upon unexpected crashes.

### Top 5 Important Limitations to Acknowledge Openly
1. **Single-Node Global Inference Lock**: Local LLM generation serializes across all tenants under `engine.inference_lock`.
2. **Infrastructure-Dependent Encryption**: TLS transport security and storage encryption-at-rest rely on reverse proxies and host volume encryption rather than application-layer crypto.
3. **SQLite Local Revocation Ledger**: Session revocation ledger uses a local SQLite database (`private_sessions.sqlite`), requiring Redis for horizontal multi-node scaling.
4. **Absence of Institutional SSO**: Authentication supports local accounts only; lacks native SAML 2.0 / Shibboleth integration.
5. **Manual Lock Recovery on Crash**: If a worker process is terminated abruptly (SIGKILL) while holding `institution_locks`, the lock is retained to fail closed, requiring manual operator cleanup.

### Top 5 Likely Difficult Viva Questions
1. *"Why didn't you use a separate database per library?"* $\rightarrow$ Defend using resource efficiency, connection pool exhaustion, schema migration simplicity, and our programmatic `TenantInventory` scoping.
2. *"Where does vector filtering happen? Before or after retrieval?"* $\rightarrow$ Answer that neither is used; explain our dedicated per-library FAISS index architecture.
3. *"What happens if an admin revokes a student while the LLM is generating an answer?"* $\rightarrow$ Point to our post-inference `self.recheck(row, actor)` that catches the revocation and suppresses output with HTTP 404.
4. *"Can a Platform Administrator view private student loans or research documents?"* $\rightarrow$ Point to `tests/institution_v2h/test_controls.py` proving that platform admins without tenant membership receive HTTP 404.
5. *"What prevents someone from guessing another library's UUID?"* $\rightarrow$ Explain that UUIDs have 122 bits of entropy, and possession of a UUID grants zero authority without an active MongoDB membership record.

### Top 5 Recommended Future Improvements
1. **Horizontal Model Serving**: Deploy vLLM or Triton Inference Server with continuous batching and multi-tenant priority queues.
2. **S3-Compatible Object Storage**: Replace local filesystem paths with MinIO/S3 object storage for multi-node deployments.
3. **Institutional SAML 2.0 / OIDC Integration**: Connect university identity providers directly to membership provisioning.
4. **Redis-Backed Session & Rate-Limiting**: Move session revocation and rate limiting to a distributed Redis cluster.
5. **Heartbeat-Based Mutex Leases**: Upgrade `institution_locks` with automatic 30-second TTL dead-man switches for self-healing crash recovery.
