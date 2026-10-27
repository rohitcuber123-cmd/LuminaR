# 10 — STRIDE THREAT MODEL & SECURITY GAP ANALYSIS

## 1. STRIDE Threat Model for Multi-Tenant LuminaR

The following threat model assesses the security architecture using the industry-standard **STRIDE** methodology (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege), specifically targeting multi-tenancy and data isolation boundaries.

| Threat Category | Specific Threat Scenario | Attack Surface | Implemented Code Protection | Code Evidence | Residual Risk Rating | Recommended Hardening |
|---|---|---|---|---|---|---|
| **Spoofing** | Attacker creates a library claiming a victim user is the owner. | `POST /libraries/register` | Derives `owner_user_id` strictly from JWT `sub`; client body cannot supply owner ID. | [institution_service.py:L59](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L59) | **LOW** | Enforce multi-factor authentication (MFA) before library provisioning. |
| **Spoofing** | Attacker brute-forces a private library access code. | `POST /libraries/{id}/join` | Rate-limited join budget (5 attempts/15m per user, 200/15m per library); Argon2id KDF. | [institution_service.py:L130-146](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L130-L146) | **LOW** | Add CAPTCHA or proof-of-work after 3 consecutive failures. |
| **Spoofing** | Stolen JWT replay after user signs out. | All endpoints | Session ID (`sid`) checked against SQLite `revoked_sessions` on every decode. | [jwt_utils.py:L54-56](file:///d:/SDC/LibraryLLM/backend/utils/jwt_utils.py#L54-L56) | **LOW** | Move session revocation ledger from SQLite to Redis cluster for horizontal scaling. |
| **Tampering** | Caller manipulates query payload to alter another library's inventory. | `/libraries/{id}/inventory/*` | `TenantInventory.scope()` rejects any mismatched `library_id`; `update()` forbids changing tenant identity. | [library_catalogue_repository.py:L47, L64](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_repository.py#L47#L64) | **LOW** | Implement MongoDB field-level encryption for sensitive institutional notes. |
| **Tampering** | Worker crashes mid-mutation, leaving inventory in inconsistent state. | Circulation & Lending | Distributed mutex via `institution_locks` with `WriteConcern(w=1, j=True)`; fail-closed design. | [institution_repository.py:L55-86](file:///d:/SDC/LibraryLLM/backend/services/institution_repository.py#L55-L86) | **MEDIUM** | Implement automated compensation transactions / saga pattern rather than requiring manual lock reconciliation. |
| **Repudiation** | Staff member waives overdue fees and denies having done so. | `POST /.../fees/{id}/waive` | Append-only audit logging in `institution_audit` with whitelisted metadata and actor ID. | [institution_repository.py:L93-110](file:///d:/SDC/LibraryLLM/backend/services/institution_repository.py#L93-L110) | **LOW** | Export audit events to an immutable WORM (Write Once Read Many) log service or syslog. |
| **Information Disclosure** | Outsider probes endpoint to see if a private library or document exists. | `/libraries/{id}/*` | Returns `404 Not Found` (instead of 403) when membership is absent, concealing existence. | [institution_dependencies.py:L41-44](file:///d:/SDC/LibraryLLM/backend/institution_dependencies.py#L41-L44) | **LOW** | Ensure response timing between existing and non-existing libraries is constant to prevent timing attacks. |
| **Information Disclosure** | Cross-tenant vector search candidate contamination. | Semantic Search | Dedicated physical FAISS index per library; candidate space $100\%$ scoped to tenant. | [search/library_intelligence.py:L94-102](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L94-L102) | **NEGLIGIBLE** | Current architecture completely prevents cross-tenant vector contamination. |
| **Information Disclosure** | RAG prompt receives chunks from another library. | RAG QA | Ephemeral runtime zeroing in `finally: clear_runtime()`; loads single authorized document. | [library_asset_pipeline.py:L281-311](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L281-L311) | **NEGLIGIBLE** | Current architecture isolates retriever memory per document. |
| **Information Disclosure** | Path traversal in file downloads. | `GET /.../assets/{id}/file` | `canonical_id()` UUID parsing, `Path.resolve()` verifying parent boundary. | [library_asset_service.py:L60-67](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L60-L67) | **LOW** | Restrict application process filesystem permissions via container sandbox. |
| **Denial of Service** | Attacker uploads huge PDF to crash OCR or exhaust disk space. | `POST /.../assets` | 64 MiB upload limit via ASGI middleware; PyMuPDF page count limit $\le 10,000$. | [library_asset_upload_limit.py](file:///d:/SDC/LibraryLLM/backend/services/library_asset_upload_limit.py) | **MEDIUM** | Implement per-library total disk quotas in addition to per-file limits. |
| **Denial of Service** | Concurrent high-DPI page rendering crashes server CPU. | `GET /.../preview/pages/{p}` | `_preview_slots = BoundedSemaphore(2)` sheds excess load with HTTP 429. | [routes/library_assets.py:L14, L100](file:///d:/SDC/LibraryLLM/backend/routes/library_assets.py#L14#L100) | **LOW** | Cache rendered PNG page images in temporary disk cache. |
| **Denial of Service** | Heavy RAG inference locks the system for other tenants. | RAG API | `engine.inference_lock` serializes GPU/CPU LLM inference across all tenants. | [library_asset_pipeline.py:L283](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L283) | **HIGH (Scalability)** | Deploy dedicated model inference replicas (e.g., vLLM / Triton) with tenant concurrency queues. |
| **Elevation of Privilege**| User redeems staff invitation issued by a former, demoted admin. | `POST /invitations/{id}/accept`| Re-verifies inviter's active `ADMIN` authority at the exact moment of redemption. | [institution_service.py:L318-323](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L318-L323) | **LOW** | Current code verified to block stale invitations. |
| **Elevation of Privilege**| Malicious admin removes library owner to seize control. | `PATCH /.../memberships/{id}` | Explicit code safeguard blocks mutating the owner's membership. | [institution_service.py:L381](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L381) | **NEGLIGIBLE** | Current code verified to enforce owner immutability. |

---

## 2. Ranked Security Gaps & Vulnerability Assessment

### Finding 1: Global LLM Inference Lock Bottleneck (Severity: HIGH)
- **Vulnerability Description**: All RAG operations across all tenants acquire `engine.inference_lock` ([library_asset_pipeline.py:L283](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L283)).
- **Impact**: While this guarantees memory safety and prevents cross-tenant vector contamination on a single GPU, it introduces an operational bottleneck: if Tenant A is generating an 800-word comprehensive summary (taking 8 seconds), Tenant B's interactive RAG queries must wait in line.
- **Remediation**: In production, decouple RAG inference from the FastAPI process. Use a pooled batch-serving framework (such as vLLM or HuggingFace TGI) supporting concurrent continuous batching with tenant request tagging.

### Finding 2: Unencrypted Storage at Rest for Artifacts & MongoDB (Severity: MEDIUM)
- **Vulnerability Description**: While credentials (passwords, codes, tokens) are cryptographically hashed using bcrypt, Argon2id, and SHA-256, the actual bibliographic records, extracted document chunks, and FAISS index files are stored in plain UTF-8 and binary formats under `local-data/`.
- **Impact**: An attacker gaining root filesystem access to the server host can inspect private institutional documents.
- **Remediation**: Configure WiredTiger native encryption-at-rest for MongoDB and place `local-data/` on an encrypted block storage volume (LUKS on Linux, BitLocker on Windows).

### Finding 3: Fail-Closed Mutex Retains Lock on Crashed Workers (Severity: MEDIUM)
- **Vulnerability Description**: In `institution_repository.py:library_mutation`, if a process terminates abruptly (SIGKILL or power loss) while holding `institution_locks`, the lock document is deliberately **never automatically expired or replaced** ([institution_repository.py:L58-60](file:///d:/SDC/LibraryLLM/backend/services/institution_repository.py#L58-L60)).
- **Impact**: This prevents data corruption, but causes all subsequent reads and mutations for that library to return HTTP 503 until an administrator manually cleans up the lock in MongoDB.
- **Remediation**: Implement a heartbeat-based lease renewal mechanism with an automatic 30-second TTL dead-man switch for benign timeout recovery, logging all auto-cleared locks to the platform console.

### Finding 4: In-Memory Authentication Rate Limiting (Severity: LOW)
- **Vulnerability Description**: The auth rate limiter (`backend/utils/auth_rate_limit.py`) stores attempt counts in a local Python dictionary in process memory.
- **Impact**: Restarting the API server or running multiple API worker processes across Uvicorn instances allows an attacker to reset or distribute brute-force attempts across workers.
- **Remediation**: Shift the rate limiting store to Redis or use MongoDB's existing `institution_attempts` pattern for the global auth endpoints.

### Finding 5: Absence of Institutional Single Sign-On (SSO / SAML / OAuth2) (Severity: INFORMATIONAL)
- **Vulnerability Description**: The system supports only local username/password account creation. Real-world university libraries require integration with institutional identity providers (SAML 2.0, Shibboleth, OAuth2/OIDC, LDAP).
- **Remediation**: Implement OIDC/SAML integration mapping university campus credentials directly to `institution_memberships`.
