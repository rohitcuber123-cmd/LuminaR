# 09 — SECURITY CONTROLS & CODE OWNERSHIP MATRIX

## 1. Master Security Controls Matrix

The following matrix documents every security mechanism evaluated during the audit, distinguishing verified protections from absent, partial, or external mechanisms.

| Security Control | Implementation Status | Enforcement Layer | File Path | Function / Class | Verified Line Range | Architectural Limitation / Scope |
|---|---|---|---|---|---|---|
| **User Password Hashing** | **VERIFIED** | Backend Service | `backend/services/auth_service.py` | `hash_password` | [L21-34](file:///d:/SDC/LibraryLLM/backend/services/auth_service.py#L21-L34) | Uses `bcrypt` with automatic salt generation. Constrained to 72 bytes. |
| **Email Verification OTP** | **VERIFIED** | Backend Service | `backend/services/auth_service.py` | `hash_otp` | [L36-42](file:///d:/SDC/LibraryLLM/backend/services/auth_service.py#L36-L42) | 6-digit numeric OTP, stored as bcrypt hash in MongoDB, 15m expiry. |
| **JWT Token Signing** | **VERIFIED** | Auth Utility | `backend/utils/jwt_utils.py` | `create_access_token` | [L20-39](file:///d:/SDC/LibraryLLM/backend/utils/jwt_utils.py#L20-L39) | `HS256` symmetric signing. Expiry: 30m (staff) / 60m (general). |
| **Token Session Revocation** | **VERIFIED** | Auth Utility / DB | `backend/services/login_sessions.py` | `is_revoked`, `revoke` | [L22-35](file:///d:/SDC/LibraryLLM/backend/services/login_sessions.py#L22-L35) | SQLite ledger (`private_sessions.sqlite`). Checks `sid` on every decode. |
| **Auth Rate Limiting** | **VERIFIED** | API Middleware | `backend/utils/auth_rate_limit.py` | `limit_auth_attempts` | [L1-40](file:///d:/SDC/LibraryLLM/backend/utils/auth_rate_limit.py) | In-memory token bucket; resets on server restart. |
| **Private Library Code KDF** | **VERIFIED** | Backend Service | `backend/services/institution_security.py` | `hash_code`, `verify_code` | [L13-27](file:///d:/SDC/LibraryLLM/backend/services/institution_security.py#L13-L27) | **Argon2id** (RFC 9106 Low Memory Profile). Minimum 8 characters. |
| **Join Code Rate Limiter** | **VERIFIED** | Backend Service | `backend/services/institution_service.py` | `consume_join_budget` | [L130-146](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L130-L146) | 5 attempts/15m per user, 200/15m per library. Stored in `institution_attempts`. |
| **Staff Invitation Tokens** | **VERIFIED** | Backend Service | `backend/services/institution_security.py` | `invitation_token`, `token_hash`| [L29-36](file:///d:/SDC/LibraryLLM/backend/services/institution_security.py#L29-L36) | 256-bit CSPRNG token (`token_urlsafe(32)`), stored as SHA-256 hash. Single-use. |
| **Tenant Membership Guard** | **VERIFIED** | API Dependencies | `backend/institution_dependencies.py` | `require_library_membership` | [L39-44](file:///d:/SDC/LibraryLLM/backend/institution_dependencies.py#L39-L44) | Resolved dynamically from MongoDB on **every request**. Returns 404 to conceal resource. |
| **Tenant Role-Based RBAC** | **VERIFIED** | API Dependencies | `backend/institution_dependencies.py` | `require_library_role` | [L47-51](file:///d:/SDC/LibraryLLM/backend/institution_dependencies.py#L47-L51) | Enforces `ADMIN`, `LIBRARIAN`, `GENERAL_USER`. Returns 403 if insufficient. |
| **Global Role Deprecation** | **VERIFIED** | API Dependencies | `backend/dependencies.py` | `require_roles` | [L27-32](file:///d:/SDC/LibraryLLM/backend/dependencies.py#L27-L32) | Explicitly raises 403 to prevent global user roles from granting tenant authority. |
| **Platform Admin Isolation** | **VERIFIED** | API Dependencies | `backend/platform_dependencies.py` | `require_platform_admin` | [L42-46](file:///d:/SDC/LibraryLLM/backend/platform_dependencies.py#L42-L46) | Platform admins cannot read private library resources without tenant membership. |
| **Inventory Scoping Wrapper**| **VERIFIED** | DB Repository | `backend/services/library_catalogue_repository.py`| `TenantInventory.scope` | [L45-49](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_repository.py#L45-L49) | Traps cross-tenant predicates (`Cross-library repository predicate rejected`). |
| **Identity Immutability** | **VERIFIED** | DB Repository | `backend/services/library_catalogue_repository.py`| `TenantInventory.update`| [L63-66](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_repository.py#L63-L66) | Forbids altering `library_id` on existing records. |
| **Compound Unique Indexes** | **VERIFIED** | Database Schema | `backend/services/library_catalogue_repository.py`| `ensure_indexes` | [L8-39](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_repository.py#L8-L39) | Compound indexes on `(library_id, accession_number)`, `(library_id, barcode)`. |
| **Mutation Serialization Lock**| **VERIFIED** | DB Repository | `backend/services/institution_repository.py`| `library_mutation` | [L54-86](file:///d:/SDC/LibraryLLM/backend/services/institution_repository.py#L54-L86) | Cross-worker mutex via `institution_locks`. Uses `w=1, j=True` write concern. |
| **Append-Only Audit Trail** | **VERIFIED** | DB Repository | `backend/services/institution_repository.py`| `audit` | [L93-110](file:///d:/SDC/LibraryLLM/backend/services/institution_repository.py#L93-L110) | Scoped to `library_id`. Metadata whitelist prevents logging of credentials. |
| **Dedicated Vector Indexes** | **VERIFIED** | Search Service | `search/library_intelligence.py` | `TenantIntelligence.semantic`| [L94-102](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L94-L102) | Separate physical FAISS index per library. Zero cross-tenant candidate retrieval. |
| **Vector Cache Isolation** | **VERIFIED** | Search Service | `backend/services/library_intelligence_artifacts.py`| `ArtifactCache` | [L120-150](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py) | Cache keyed by `(library_id, generation_id, target)`. Max 2 resident entries. |
| **RAG Runtime Zeroing** | **VERIFIED** | AI Pipeline | `rag/services/library_asset_pipeline.py`| `clear_runtime` | [L271-280](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L271-L280) | Wipes `doc_index`, `doc_metadata`, and `doc_chunk_texts` before & after LLM query. |
| **RAG Authority Recheck** | **VERIFIED** | AI Pipeline | `rag/services/library_asset_pipeline.py`| `recheck` | [L265-269](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L265-L269) | Rechecks membership before inference and after inference before returning output. |
| **Citation ID Verification** | **VERIFIED** | AI Pipeline | `rag/services/library_asset_pipeline.py`| `ask` | [L303-307](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L303-L307) | Rejects responses citing chunk IDs outside authorized document manifest. |
| **Path Traversal Guards** | **VERIFIED** | Asset Service | `backend/services/library_asset_service.py` | `asset_directory`, `safe_child` | [L60-67](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L60-L67) | Enforces UUID format; validates `path.resolve()` remains inside storage root. |
| **Upload Size Cap** | **VERIFIED** | ASGI Middleware | `backend/services/library_asset_upload_limit.py` | `LibraryAssetUploadLimit` | [L1-35](file:///d:/SDC/LibraryLLM/backend/services/library_asset_upload_limit.py) | Rejects payloads $> 64$ MiB at the HTTP stream level. |
| **PDF Format Verification** | **VERIFIED** | Asset Service | `backend/services/library_asset_service.py` | `validate_pdf` | [L189-200](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L189-L200) | Validates `%PDF-` magic bytes, unencrypted, page count $\le 10,000$. |
| **Secure Download Headers** | **VERIFIED** | API Route | `backend/routes/library_assets.py` | `file` | [L66-73](file:///d:/SDC/LibraryLLM/backend/routes/library_assets.py#L66-L73) | Sets `Cache-Control: private, no-store`, `nosniff`, `sandbox; default-src 'none'`. |
| **HTTPS / Transport TLS** | **NOT VERIFIED** | Infrastructure | N/A | N/A | N/A | FastAPIs run locally over HTTP on ports 8002/8005. Reverse proxy TLS assumed for production. |
| **Database Encryption at Rest**| **NOT VERIFIED** | Infrastructure | MongoDB Engine | WiredTiger encryption | N/A | Application stores plain strings in MongoDB. Relies on storage/filesystem volume encryption. |
| **Spaced Repetition / SM-2** | **NOT IMPLEMENTED** | Knowledge Tools | N/A | N/A | N/A | Flashcards and quizzes are session-bound; no persistent Leitner/SM-2 spaced repetition exists. |
| **OAuth2 / SAML / SSO** | **NOT IMPLEMENTED** | Authentication | N/A | N/A | N/A | Only local email/password registration is supported. Institutional LDAP/SAML is absent. |

---

## 2. Division of Code Ownership & Dependencies

### Category A — Custom Implementations (Developed by LuminaR Engineers)
1. **Dynamic Multi-Tenant Dependency Chain**: `backend/institution_dependencies.py` (`actor_id`, `resolve_library_membership`, `require_library_role`, `require_library_staff`, `require_library_owner`).
2. **`TenantInventory` Scoping Engine**: `backend/services/library_catalogue_repository.py` (`scope`, `one`, `rows`, `count`, `insert`, `update`, `accession`).
3. **Atomic Mutual Exclusion Engine**: `backend/services/institution_repository.py:library_mutation` (cross-worker locks in `institution_locks` with durable journal write concern).
4. **Circulation & Lending State Machine**: `backend/services/library_lending_service.py` (approval, loan creation, return requests, journal reconciliation).
5. **Dedicated Vector Intelligence Pipeline**: `search/library_intelligence.py` (`TenantIntelligence`, isolated dataset extraction, FAISS build orchestration, candidate scoring, canonical MongoDB hydration).
6. **RAG Ephemeral Runtime Swapper**: `rag/services/library_asset_pipeline.py` (`clear_runtime`, `prepared`, `recheck`, citation chunk validation).
7. **Rate-Limiting Join Budget**: `backend/services/institution_service.py:consume_join_budget` (bucketed counter in MongoDB `institution_attempts`).
8. **Staff Invitation Protocol**: `backend/services/institution_service.py` (CSPRNG generation, single-use SHA256 storage, inviter authority re-check on acceptance).

### Category B — External Libraries (Standard Open-Source Packages)
1. **Password Hashing**: `bcrypt` (C-library wrapper).
2. **Institutional Passphrase KDF**: `argon2-cffi` (`PasswordHasher` with RFC 9106 Low Memory Profile).
3. **JWT Token Generation & Decoding**: `python-jose` (Cryptographic signing via `HS256`).
4. **Token Generation**: Python standard library `secrets` (`token_urlsafe(32)`).
5. **PDF Parsing & Validation**: `PyMuPDF` (`fitz.open()`).
6. **Vector Search Engine**: `faiss-cpu` (Facebook AI Similarity Search).
7. **Sentence Embeddings**: `sentence-transformers` (`all-MiniLM-L6-v2`).
8. **Reranking**: `sentence-transformers` (`CrossEncoder`).
9. **Database Driver**: `pymongo` (MongoDB Python driver).

### Category C — Pretrained Model Weights
1. **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense embeddings).
2. **Reranker Model**: `cross-encoder/ms-marco-MiniLM-L-6-v2`.
3. **Generative LLM**: `Qwen2.5-3B-Instruct` (Hosted locally; zero cloud external API calls).

### Category D — Infrastructure & Operational Dependencies
1. **MongoDB Server**: Standalone instance (`library_database`).
2. **SQLite Engines**: Embedded engine for `private_sessions.sqlite` and `registry.sqlite`.
3. **Operating System Filesystem**: Local disk partitions under `local-data/` and `rag/private_documents/`.

---

## 3. Critical Analysis: What Security Guarantees Are Code-Enforced?

| Security Guarantee | Code-Enforced by LuminaR Application? | Guaranteed by Infrastructure? |
|---|---|---|
| **Zero Cross-Tenant Data Leakage in DB** | **YES**: Enforced by `TenantInventory.scope()` and compound indexes. | No (Shared DB requires application-level scoping). |
| **Zero Cross-Tenant Vector Contamination** | **YES**: Enforced by dedicated FAISS indexes per library. | No (Vector indexes are managed directly by application). |
| **Immediate Membership Revocation** | **YES**: Enforced by dynamic MongoDB queries on every request. | No (Application-level JWT decoupling). |
| **Path Traversal Protection** | **YES**: Enforced by `canonical_id()` UUID parsing and `Path.resolve()`. | No (Filesystem allows relative paths without app checks). |
| **Transport Wire Encryption (TLS)** | **NO**: Must be provided by reverse proxy (Nginx / Caddy / Cloudflare). | **YES**: Infrastructure must provide HTTPS certificates. |
| **Data Encryption at Rest** | **NO**: Application writes plain UTF-8 text and binary FAISS files to disk. | **YES**: Must be provided by OS disk encryption (LUKS / BitLocker). |
