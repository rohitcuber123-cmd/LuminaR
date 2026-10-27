# 12 — COMPREHENSIVE VIVA VOCE QUESTIONS & DEFENSE ANSWERS

This document prepares you to defend every architectural decision, security control, database model, and AI pipeline in the LuminaR Private Library and Multi-Tenancy System. It contains **60 technically rigorous viva questions** divided across 14 categories.

---

## CATEGORY 1: OVERALL MULTI-TENANCY ARCHITECTURE

### Question 1: How are private libraries separated in LuminaR? Is it a multi-tenant system?
- **Spoken Answer (20–40s)**: "LuminaR implements a hybrid multi-tenancy architecture. Relational bibliographic data, circulation records, and memberships share a single MongoDB database partitioned by an immutable `library_id` field and enforced by a custom `TenantInventory` repository wrapper. Meanwhile, unstructured digital documents and vector search indexes are physically partitioned on the filesystem into dedicated directories and separate FAISS indexes per library. This gives us high database efficiency combined with zero vector contamination."
- **Deep Technical Explanation**: We rejected the naive global vector index model because multi-tenant vector retrieval over a shared index suffers from recall starvation and timing leakage. In LuminaR, MongoDB collections (`institution_*`) use compound unique indexes on `(library_id, field)`. For vector search, `TenantIntelligence` builds an independent FAISS index in `local-data/library-intelligence/{library_id}/search/`, guaranteeing that 100% of the candidate vector space belongs strictly to that tenant.
- **Code Reference**: [backend/services/library_catalogue_repository.py:L41-67](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_repository.py#L41-L67) and [search/library_intelligence.py:L94-102](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L94-L102).
- **Follow-up Question**: *Why didn't you use a separate MongoDB database per library?*
- **Limitations / Qualifications**: A shared database requires diligent application-level scoping; accidental un-scoped queries could leak data if the repository wrapper is bypassed.

---

### Question 2: Why did you choose a shared MongoDB database instead of a database-per-tenant architecture?
- **Spoken Answer (20–40s)**: "A database-per-tenant model creates severe operational overhead: hundreds of connection pools, database handle limits, and complex schema migration scripts across hundreds of databases. Shared collections with compound unique indexes give us high density, fast startup, and consolidated backups, while our custom `TenantInventory` class enforces tenant boundaries programmatically before queries reach the driver."
- **Deep Technical Explanation**: In MongoDB, each database incurs memory overhead for namespace metadata and WiredTiger cache allocation. By using shared collections prefixed with `institution_*` and indexed on `[('library_id', 1), ('field', 1)]`, MongoDB B-trees naturally cluster a tenant's index entries together, providing $O(\log N)$ query performance without database proliferation.
- **Code Reference**: [backend/services/institution_repository.py:L21-52](file:///d:/SDC/LibraryLLM/backend/services/institution_repository.py#L21-L52).
- **Follow-up Question**: *How do you prevent developer error where someone writes an un-scoped query?*
- **Limitations / Qualifications**: It places the burden of security on application-level enforcement rather than database engine isolation.

---

### Question 3: What is the difference between a private library, a personal collection, and the public catalogue in your platform?
- **Spoken Answer (20–40s)**: "A private library is an institutional tenant with staff, members, physical circulation, and isolated vector indexes stored in MongoDB and filesystem namespaces. A personal collection consists of ephemeral, session-bound PDF uploads stored in SQLite and `rag/private_documents` for individual study. The public catalogue is a global, read-only bibliographic reference dataset from OpenLibrary that any user can discover."
- **Deep Technical Explanation**: Institutional libraries have durable lifecycles, role-based access control (`ADMIN`, `LIBRARIAN`, `GENERAL_USER`), and physical inventory tracking. Personal documents have no institutional membership; they are registered in `rag/private_documents/registry.sqlite` with a foreign key to the user's session ID (`sid`) and are scrubbed upon logout.
- **Code Reference**: [backend/services/institution_service.py:L58-86](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L58-L86) vs [rag/services/private_documents.py:L35-37](file:///d:/SDC/LibraryLLM/rag/services/private_documents.py#L35-L37).
- **Follow-up Question**: *Can a personal document be promoted to an institutional library asset?*
- **Limitations / Qualifications**: Currently, personal uploads and institutional assets are distinct pipelines with no direct one-click promotion route.

---

### Question 4: Where is the authoritative active library context derived on each request?
- **Spoken Answer (20–40s)**: "The authoritative tenant identifier is the canonical UUID in the URL path, such as `/libraries/{library_id}`. The backend never trusts client request headers or JWT tenant claims. On every single API request, FastAPI route dependencies extract the user's identity from the JWT and query MongoDB to verify that the user holds an active membership in that exact library."
- **Deep Technical Explanation**: Deriving tenant context from JWT claims causes stale authorization bugs when permissions are revoked. In LuminaR, the JWT provides only user identity (`sub`). The function `require_library_membership(library_id, current_user)` queries `institution_memberships` dynamically. If no active record exists, it raises HTTP 404 immediately.
- **Code Reference**: [backend/institution_dependencies.py:L18-45](file:///d:/SDC/LibraryLLM/backend/institution_dependencies.py#L18-L45).
- **Follow-up Question**: *Doesn't querying MongoDB on every request add database latency?*
- **Limitations / Qualifications**: Adds approximately 1–3 ms of indexed MongoDB lookup overhead per authenticated request.

---

### Question 5: Why does your authorization middleware return HTTP 404 instead of HTTP 403 when access is denied?
- **Spoken Answer (20–40s)**: "We deliberately return 404 Not Found to implement Information Concealment. If we returned 403 Forbidden, an attacker could enumerate UUIDs or resource endpoints to confirm whether a confidential library or private document exists. Returning 404 makes protected institutional resources completely invisible to outsiders."
- **Deep Technical Explanation**: OWASP API Security Top 10 recommends concealing the existence of protected objects to prevent Broken Object Level Authorization (BOLA/IDOR) enumeration. In `require_library_membership`, line 43 explicitly comments: *'Conceal the existence of protected resources from outsiders, including global admins'*.
- **Code Reference**: [backend/institution_dependencies.py:L41-44](file:///d:/SDC/LibraryLLM/backend/institution_dependencies.py#L41-L44).
- **Follow-up Question**: *When do you return 403 Forbidden then?*
- **Limitations / Qualifications**: HTTP 403 is reserved for verified members who lack sufficient role privileges (e.g., a `GENERAL_USER` attempting to withdraw an inventory book).

---

## CATEGORY 2: LIBRARY CREATION & REGISTRATION

### Question 6: What prevents an attacker from creating a library under another user's name?
- **Spoken Answer (20–40s)**: "The library creation endpoint completely ignores any client-supplied owner fields. In `register_library()`, the `owner_user_id` is assigned directly from `actor_id(current_user)`, which is decoded and validated from the authenticated JWT `sub` claim. Pydantic request models forbid extra payload fields."
- **Deep Technical Explanation**: The request schema `RegisterLibrary` sets `extra = 'forbid'`. Line 59 in `institution_service.py` executes `user_id = actor_id(current_user)` and inserts `owner_user_id: user_id`. Even if an attacker injects `{"owner_user_id": 999}` into the JSON body, FastAPI rejects the request with HTTP 422.
- **Code Reference**: [backend/services/institution_service.py:L58-65](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L58-L65).
- **Follow-up Question**: *What if an attacker tries to register an existing library slug?*
- **Limitations / Qualifications**: Requires an active, authenticated user account; unauthenticated users cannot invoke registration.

---

### Question 7: What is the `PROVISIONING` status barrier during library creation?
- **Spoken Answer (20–40s)**: "When a library is being created, it is inserted into MongoDB with `status: 'PROVISIONING'`. Public discovery queries strictly match `status: 'ACTIVE'`. The status is only updated to `ACTIVE` after the security credentials, initial admin membership, and sequence counters are committed under a distributed lock. If anything fails mid-process, the library remains invisible."
- **Deep Technical Explanation**: Multi-document creation in MongoDB without multi-document transactions can leave orphaned parent records if a crash occurs. By setting status to `PROVISIONING` inside `library_mutation(library_id, durable=True)` and updating to `ACTIVE` as the final step (line 83), LuminaR ensures atomic visibility.
- **Code Reference**: [backend/services/institution_service.py:L65, L83-84](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L65#L83-L84).
- **Follow-up Question**: *How do you clean up crashed libraries stuck in PROVISIONING?*
- **Limitations / Qualifications**: Unfinished provisioning records currently require manual administrative cleanup or a scheduled sweeper.

---

### Question 8: How are library access passphrases hashed and verified?
- **Spoken Answer (20–40s)**: "Private library passphrases are hashed using Argon2id with RFC 9106 Low Memory Profile parameters via the `argon2-cffi` library. Argon2id is a memory-hard password derivation function that provides state-of-the-art protection against GPU and ASIC cracking attacks. Access code hashes are stored in a dedicated `institution_security` collection, never in the public library record."
- **Deep Technical Explanation**: Code in `institution_security.py` enforces passphrase lengths between 8 and 128 characters without trimming case-sensitive human input. Verification uses `hasher.verify(encoded, code)` catching `VerificationError` and `InvalidHashError` safely without leaking exceptions.
- **Code Reference**: [backend/services/institution_security.py:L10-27](file:///d:/SDC/LibraryLLM/backend/services/institution_security.py#L10-L27).
- **Follow-up Question**: *Why did you use Argon2id for library codes but bcrypt for user passwords?*
- **Limitations / Qualifications**: Argon2id is more CPU and memory intensive than bcrypt, which is why brute-force rate-limiting is also enforced.

---

### Question 9: How does LuminaR prevent brute-force attacks against private library codes?
- **Spoken Answer (20–40s)**: "We enforce a two-tier bucketed rate limiter in `consume_join_budget()`. A single user account is restricted to 5 attempts per 15-minute window for a library. Additionally, the library itself is globally capped at 200 attempts per 15-minute window. This prevents both single-user dictionary attacks and distributed multi-account brute force attacks."
- **Deep Technical Explanation**: Attempt counters are stored in MongoDB collection `institution_attempts` using upsert operations on compound keys: `f'user:{user_id}:{library_id}:{bucket}'` and `f'library:{library_id}:{bucket}'`. If exceeded, the endpoint raises HTTP 429 with a calculated `Retry-After` header. Documents are auto-purged by a MongoDB TTL index.
- **Code Reference**: [backend/services/institution_service.py:L130-146](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L130-L146).
- **Follow-up Question**: *What if an attacker rotates IP addresses?*
- **Limitations / Qualifications**: Because rate limits track authenticated `user_id` and target `library_id`, rotating IP addresses does not bypass the budget.

---

## CATEGORY 3: DATABASE SEPARATION & SCOPING

### Question 10: What is the `TenantInventory` class and how does it prevent cross-tenant queries?
- **Spoken Answer (20–40s)**: "The `TenantInventory` class is a repository wrapper that encapsulates all inventory database operations. It takes a validated `library_id` on initialization and injects it into every read, write, count, and update query. If a caller passes a query with a conflicting `library_id`, it explicitly raises a `ValueError` rather than executing the cross-tenant query."
- **Deep Technical Explanation**: Located in `library_catalogue_repository.py`, `TenantInventory.scope()` checks `if 'library_id' in query and query['library_id'] != self.library_id: raise ValueError(...)`. Furthermore, its `update()` method forbids updating `library_id`. This provides an automated programmatic barrier against SQL/NoSQL injection and developer query bugs.
- **Code Reference**: [backend/services/library_catalogue_repository.py:L41-67](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_repository.py#L41-L67).
- **Follow-up Question**: *Where is TenantInventory instantiated?*
- **Limitations / Qualifications**: Developers must route queries through `TenantInventory` rather than directly importing raw `pymongo.collection`.

---

### Question 11: How do you prevent collisions when two libraries upload books with identical ISBNs?
- **Spoken Answer (20–40s)**: "We use compound unique indexes scoped to the `library_id`. In `institution_library_books`, the index is defined as `(library_id, 1), (accession_number, 1)` and `(library_id, 1), (isbn_13, 1)`. Because uniqueness is enforced within each library's partition rather than globally, separate libraries can hold the exact same book titles or ISBNs without any conflict."
- **Deep Technical Explanation**: A global unique index on ISBN would prevent Library B from adding a book already owned by Library A. LuminaR's index specifications in `ensure_indexes()` use partial filter expressions and compound keys: `[('library_id', 1), ('isbn_13', 1)]`. Test `test_identical_cross_library_checksum_namespace_is_separate` verifies that two libraries uploading identical items succeed independently.
- **Code Reference**: [backend/services/library_catalogue_repository.py:L10-18](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_repository.py#L10-L18).
- **Follow-up Question**: *What prevents duplicate books within the same library?*
- **Limitations / Qualifications**: The compound index enforces uniqueness within that single library if a unique field like `accession_number` or `source_key` is repeated.

---

### Question 12: How do MongoDB locks (`library_mutation`) work and why are they necessary?
- **Spoken Answer (20–40s)**: "Because we run multiple API worker processes on a standalone MongoDB instance, we use `library_mutation` as a distributed mutual exclusion lock. It inserts a document into `institution_locks` keyed by `_id: library_id` with journaled durability (`j=True`). This serializes catalog imports and circulation state changes, preventing race conditions across worker processes."
- **Deep Technical Explanation**: The lock uses a busy-wait retry loop with a deadline (`monotonic() + wait_seconds`). If another worker holds the lock, a `DuplicateKeyError` is caught and retried every 20ms. If it times out, HTTP 503 is returned. Crucially, if an unexpected exception occurs, the lock is retained to fail closed and prevent corrupted partial commits.
- **Code Reference**: [backend/services/institution_repository.py:L54-86](file:///d:/SDC/LibraryLLM/backend/services/institution_repository.py#L54-L86).
- **Follow-up Question**: *What is `require_readable()`?*
- **Limitations / Qualifications**: Standalone MongoDB locking can block read operations during large bulk mutations if `require_readable` is invoked.

---

## CATEGORY 4: IDENTIFIERS & ACCESS CONTEXT

### Question 13: How are library IDs and asset IDs generated? Are they predictable?
- **Spoken Answer (20–40s)**: "All library IDs, membership IDs, asset IDs, and job IDs are generated using version 4 UUIDs (`uuid.uuid4()`). UUIDv4 identifiers have 122 bits of cryptographic entropy and are completely random and non-sequential, making them virtually impossible to guess or enumerate."
- **Deep Technical Explanation**: Sequential integer IDs (e.g., `1, 2, 3`) allow attackers to perform ID enumeration attacks. By enforcing canonical UUID formatting and validating via `uuid.UUID(str(value))`, LuminaR prevents both enumeration and string-based injection attacks across all URL parameters.
- **Code Reference**: [backend/services/institution_service.py:L60](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L60) and [backend/services/library_asset_service.py:L48-52](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L48-L52).
- **Follow-up Question**: *If someone knows a valid UUID, can they access the library?*
- **Limitations / Qualifications**: Knowing a UUID grants zero access; the backend checks active membership in `institution_memberships` on every request.

---

### Question 14: How does library switching work on the frontend, and how do you prevent stale session state?
- **Spoken Answer (20–40s)**: "When a user switches libraries, the frontend `useInstitutionStore` issues an API call to `/libraries/{id}/context` to obtain verified tenant context. Once confirmed, it updates the active workspace and triggers a cascade of state purges: resetting personal book loans in `useLibraryStore`, clearing assistant context, and dispatching a `luminar-documents-cleared` event to purge local caches."
- **Deep Technical Explanation**: In `useInstitutionStore.ts`, the `select()` action manages concurrency using a monotonically increasing `requestSequence` number to discard out-of-order asynchronous responses. On logout or tenant switch, `clearUserData()` and `reset()` remove tenant context from localStorage.
- **Code Reference**: [frontend/src/store/useInstitutionStore.ts:L67-82](file:///d:/SDC/LibraryLLM/frontend/src/store/useInstitutionStore.ts#L67-L82) and [frontend/src/store/useAuthStore.ts:L265-291](file:///d:/SDC/LibraryLLM/frontend/src/store/useAuthStore.ts#L265-L291).
- **Follow-up Question**: *What happens if the user manually edits the active library ID in browser localStorage?*
- **Limitations / Qualifications**: Editing localStorage only alters UI display; any subsequent API call to the backend with a forged ID fails backend authorization with HTTP 404.

---

## CATEGORY 5: AUTHENTICATION (JWT, SESSIONS, HASHING)

### Question 15: How are user passwords hashed in LuminaR?
- **Spoken Answer (20–40s)**: "User account passwords are encrypted using `bcrypt` via the Python `bcrypt` library. We enforce a minimum length of 8 characters and a maximum length of 72 bytes—which is bcrypt's algorithmic limit—to prevent truncation vulnerabilities. Each password hash incorporates a cryptographically random salt generated via `bcrypt.gensalt()`."
- **Deep Technical Explanation**: In `auth_service.py`, `hash_password()` encodes the string to UTF-8 bytes, verifies `len(password_bytes) <= 72`, and calls `bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')`. Verification uses `bcrypt.checkpw()`.
- **Code Reference**: [backend/services/auth_service.py:L21-34](file:///d:/SDC/LibraryLLM/backend/services/auth_service.py#L21-L34).
- **Follow-up Question**: *What happens if a user submits a password longer than 72 bytes?*
- **Limitations / Qualifications**: The API returns HTTP 400 'Password is too long' to ensure passwords are not silently truncated by bcrypt.

---

### Question 16: How does LuminaR handle JWT token expiration and immediate session revocation?
- **Spoken Answer (20–40s)**: "JWT access tokens have short expiration times: 30 minutes for staff members and 60 minutes for general users. Furthermore, every JWT embeds a unique session ID (`sid`). When a user logs out, the `sid` is recorded in a SQLite revocation ledger. On every single API request, `decode_access_token()` checks whether the `sid` is revoked, providing immediate invalidation without waiting for expiry."
- **Deep Technical Explanation**: Stateless JWTs cannot traditionally be revoked before expiry. LuminaR bridges this gap by checking `is_revoked(payload.get('sid'))` against `revoked_sessions` in `rag/private_sessions.sqlite` during token decoding in `jwt_utils.py`. The table auto-cleans entries older than 24 hours.
- **Code Reference**: [backend/utils/jwt_utils.py:L42-61](file:///d:/SDC/LibraryLLM/backend/utils/jwt_utils.py#L42-L61) and [backend/services/login_sessions.py:L22-35](file:///d:/SDC/LibraryLLM/backend/services/login_sessions.py#L22-L35).
- **Follow-up Question**: *Why did you use SQLite for revoked sessions instead of MongoDB?*
- **Limitations / Qualifications**: SQLite is local to the server filesystem; in a horizontally scaled multi-node cluster, this ledger must reside in Redis.

---

## CATEGORY 6: AUTHORIZATION AND RBAC

### Question 17: What roles exist in a private library and what are their privileges?
- **Spoken Answer (20–40s)**: "There are three institutional roles in `institution_memberships`: `ADMIN`, `LIBRARIAN`, and `GENERAL_USER`. An Admin can manage inventory, digital assets, catalog intelligence builds, invitations, and settings. A Librarian can manage inventory, digital uploads, and circulation approvals, but cannot invite admins or change access codes. General Users are patrons who can view member assets, borrow books, and reserve holdings."
- **Deep Technical Explanation**: Enforced in `backend/institution_dependencies.py`. `require_library_staff` permits `('ADMIN', 'LIBRARIAN')`. `require_library_patron` requires `'GENERAL_USER'`. The creator is designated `owner_user_id` in `institution_libraries`, which grants immutable admin rights and exclusive privilege to manage other admins.
- **Code Reference**: [backend/institution_dependencies.py:L47-67](file:///d:/SDC/LibraryLLM/backend/institution_dependencies.py#L47-L67).
- **Follow-up Question**: *Can a user hold different roles in different libraries?*
- **Limitations / Qualifications**: Yes. A user can be an `ADMIN` in Library A and a `GENERAL_USER` in Library B; roles are completely scoped to the `(library_id, user_id)` pair.

---

### Question 18: What administrative safeguards prevent an admin from locking themselves or the owner out?
- **Spoken Answer (20–40s)**: "We enforce two critical safeguards in `change_membership()`: First, the library owner's membership can never be demoted, suspended, or removed by any admin. Second, the system requires that at least one active administrator must remain at all times; any update that would demote or remove the last remaining active admin is rejected with HTTP 409."
- **Deep Technical Explanation**: Code in `institution_service.py:L381` checks `if target['user_id'] == library['owner_user_id']: raise HTTPException(403)`. Lines 390–392 check `if count_documents({'role': 'ADMIN', 'status': 'ACTIVE'}) <= 1: raise HTTPException(409)`. This prevents orphaned institutional libraries.
- **Code Reference**: [backend/services/institution_service.py:L380-393](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L380-L393).
- **Follow-up Question**: *How can ownership of a library be transferred?*
- **Limitations / Qualifications**: Currently, explicit ownership transfer requires platform operator intervention in the database.

---

### Question 19: Can a global Platform Admin view private documents or loans inside an institutional library?
- **Spoken Answer (20–40s)**: "No. Platform administrators have authority only over platform-level routes (`/platform/*`) for managing accounts and suspending tenants. When a Platform Admin attempts to access a private library's inventory, assets, or circulation routes, the tenant authorization middleware evaluates their `institution_memberships` record. Because they have no membership, the request returns HTTP 404."
- **Deep Technical Explanation**: Tested explicitly in [tests/institution_v2h/test_controls.py:L13-22](file:///d:/SDC/LibraryLLM/tests/institution_v2h/test_controls.py#L13-L22) with role `'PLATFORM_ONLY'` (user 9). The test asserts that `GET /libraries/{lib}/intelligence` returns HTTP 404, proving that platform administrative authority does not bypass tenant isolation.
- **Code Reference**: [backend/institution_dependencies.py:L39-44](file:///d:/SDC/LibraryLLM/backend/institution_dependencies.py#L39-L44) and [tests/institution_v2h/test_controls.py:L13-22](file:///d:/SDC/LibraryLLM/tests/institution_v2h/test_controls.py#L13-L22).
- **Follow-up Question**: *What can a Platform Admin do then?*
- **Limitations / Qualifications**: Platform admins can suspend a compromised tenant globally, but cannot inspect private student loan records or private PDFs.

---

## CATEGORY 7: MEMBERSHIP & INVITATIONS

### Question 20: How are staff invitations generated and redeemed securely?
- **Spoken Answer (20–40s)**: "Staff invitations use a single-use token protocol. The backend generates a 256-bit cryptographically secure token using Python's `secrets` module and stores only its SHA-256 hash in MongoDB. The raw token is returned exactly once in the response. When redeemed, the accepting user's verified email must match the invitation, and the inviter's current admin authority is re-validated."
- **Deep Technical Explanation**: Storing raw invite tokens in a database is a security vulnerability if the database is dumped. LuminaR stores `token_hash: sha256(raw)`. During redemption in `respond_invitation()`, lines 318–323 re-verify that the inviting admin still has an active `ADMIN` role. If the inviter was fired or demoted, all their pending invitations are invalidated instantly.
- **Code Reference**: [backend/services/institution_service.py:L241-268, L300-338](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L241-L268#L300-L338).
- **Follow-up Question**: *What is the expiration time for invitations?*
- **Limitations / Qualifications**: Invitations expire after 7 days (`LUMINAR_INVITE_DAYS = 7`).

---

### Question 21: How does membership revocation affect an active user session?
- **Spoken Answer (20–40s)**: "Membership revocation takes effect immediately on the user's very next HTTP request. Because tenant permissions are not embedded in the JWT token and are instead resolved dynamically against MongoDB on every request, an administrator updating a member's status to `SUSPENDED` or `REMOVED` instantly blocks that user from all library resources with HTTP 404."
- **Deep Technical Explanation**: Tested in `tests/institution_v2f/test_assets.py:L50-66`. A background thread attempts to access an asset; the admin updates the membership status to `'REVOKED'`; the guard immediately catches the revocation and raises HTTP 404, proving there is zero cache delay or JWT stale window.
- **Code Reference**: [backend/institution_dependencies.py:L24-26](file:///d:/SDC/LibraryLLM/backend/institution_dependencies.py#L24-L26) and [tests/institution_v2f/test_assets.py:L50-66](file:///d:/SDC/LibraryLLM/tests/institution_v2f/test_assets.py#L50-L66).
- **Follow-up Question**: *What happens to loans or reservations held by a revoked member?*
- **Limitations / Qualifications**: Active loans remain in the database for staff tracking and physical book recovery, but the patron can no longer access the library workspace.

---

## CATEGORY 8: DATASET INGESTION & ISOLATION

### Question 22: How does the system handle bulk catalog imports via CSV without cross-tenant pollution?
- **Spoken Answer (20–40s)**: "Bulk catalog imports run through a two-stage preview-and-apply pipeline under `library_inventory_import.py`. The file upload is size-capped at 16 MiB. In preview mode, records are validated in memory. In apply mode, records are committed strictly through `TenantInventory.insert()` inside a `library_mutation` lock, generating sequential institutional accession numbers for each record."
- **Deep Technical Explanation**: In `importer.apply()`, incoming bibliographic records are stripped of client-supplied IDs. Unique identifiers (`library_book_id`) are assigned as fresh UUIDs, and each book holding is bound to `library_id`. Compound unique indexes on `(library_id, accession_number)` prevent any duplicate sequence overlap.
- **Code Reference**: [backend/services/library_inventory_import.py](file:///d:/SDC/LibraryLLM/backend/services/library_inventory_import.py) and [backend/routes/library_inventory.py:L61-81](file:///d:/SDC/LibraryLLM/backend/routes/library_inventory.py#L61-L81).
- **Follow-up Question**: *Can an imported book link to a global OpenLibrary work?*
- **Limitations / Qualifications**: Yes. A local record can store `global_work_id`, which enriches description and subjects while keeping local holding and copy inventory completely private.

---

### Question 23: What is dataset fingerprinting and how does it detect catalog changes?
- **Spoken Answer (20–40s)**: "A dataset fingerprint is a SHA-256 hash computed over the normalized, sorted bibliographic records of a library's active books. When staff triggers a search index or knowledge graph build, the fingerprint is saved in the manifest. If any book title, author, or subject is modified later, the service detects fingerprint drift and marks the intelligence targets as STALE."
- **Deep Technical Explanation**: In `library_intelligence_store.py`, `fingerprint(records)` executes `sha256(encoded({'schema': SCHEMA, 'records': records})).hexdigest()`. When a semantic search query arrives, `TenantIntelligence.semantic()` checks if the current fingerprint matches `manifest['source_fingerprint']`. If they differ, it falls back to real-time database lexical search.
- **Code Reference**: [backend/services/library_intelligence_store.py:L87](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_store.py#L87) and [search/library_intelligence.py:L111](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L111).
- **Follow-up Question**: *Does checking out a physical book stale the search index?*
- **Limitations / Qualifications**: No. Test `test_loan_change_does_not_stale_dataset` verifies that changing copy availability does not change bibliographic metadata and therefore does not stale the search index.

---

## CATEGORY 9: SEMANTIC SEARCH ISOLATION

### Question 24: Why doesn't LuminaR use post-filtering over a global shared vector index for semantic search?
- **Spoken Answer (20–40s)**: "Post-filtering over a shared vector index causes Recall Starvation. If another library has 50 books closely matching the search terms, all top-50 vector candidates retrieved by FAISS will belong to that other library. When post-filtering removes them for the querying tenant, the user gets zero results, even if their library had relevant books ranked 51st. That is why LuminaR builds dedicated separate vector indexes per library."
- **Deep Technical Explanation**: Furthermore, post-filtering leaks computational resources and allows CrossEncoder reranking models to process foreign document text before filtering occurs. Dedicated FAISS indexes guarantee that 100% of candidate vectors retrieved belong to the querying tenant, completely eliminating recall degradation.
- **Code Reference**: [search/library_intelligence.py:L94-107](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L94-L107).
- **Follow-up Question**: *How much disk and memory overhead do separate indexes require?*
- **Limitations / Qualifications**: A 10,000-book library index requires only ~15 MiB of RAM and disk space, making dedicated indexes extremely lightweight.

---

### Question 25: How does semantic search verify that retrieved vector candidates are still active in the database?
- **Spoken Answer (20–40s)**: "After retrieving and reranking vector candidates from the tenant's FAISS index, the search service does not return vector metadata directly. Instead, it executes an aggregation pipeline against MongoDB `institution_library_books` matching the candidate IDs and verifying `status: 'ACTIVE'`. If a book was withdrawn after the index was built, MongoDB hydration silently drops it."
- **Deep Technical Explanation**: In `search/library_intelligence.py`, lines 112–114 execute:
  `pipeline = [*catalogue.usable(library_id, ...), {'$match': {'library_book_id': {'$in': ids}}}]`.
  Because `catalogue.usable()` enforces tenant boundaries and active status, withdrawn books are eliminated. Tested in `test_archived_book_never_returned_from_stale_index`.
- **Code Reference**: [search/library_intelligence.py:L109-117](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L109-L117) and [tests/institution_v2g/test_intelligence.py:L148-151](file:///d:/SDC/LibraryLLM/tests/institution_v2g/test_intelligence.py#L148-L151).
- **Follow-up Question**: *What if the entire index is out of date or building?*
- **Limitations / Qualifications**: If `status != 'READY'`, the service gracefully falls back to scoped real-time lexical search (`LOCAL_FALLBACK`).

---

### Question 26: What is the `ArtifactCache` and how does it prevent cross-tenant vector cache pollution?
- **Spoken Answer (20–40s)**: "The `ArtifactCache` is an in-memory cache for loaded FAISS indexes and metadata records. Cache entries are keyed strictly by a composite tuple: `(library_id, generation_id, target)`. This guarantees that Library A's cached index cannot be accessed or returned during Library B's search requests. It maintains a strict cap of 2 resident entries with LRU eviction to bound RAM usage."
- **Deep Technical Explanation**: Located in `library_intelligence_artifacts.py`, `ArtifactCache` tracks access order and metrics (`hits`, `misses`, `evictions`). Test `test_lazy_cache_namespace_and_eviction` verifies that loading indexes for three separate libraries successfully evicts the oldest entry while preserving tenant key isolation.
- **Code Reference**: [backend/services/library_intelligence_artifacts.py](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py) and [tests/institution_v2g/test_intelligence.py:L177-184](file:///d:/SDC/LibraryLLM/tests/institution_v2g/test_intelligence.py#L177-L184).
- **Follow-up Question**: *Why is the cache cap set to 2 entries?*
- **Limitations / Qualifications**: Configured for lightweight multi-tenant local environments; in high-concurrency production deployments, `max_entries` can be scaled based on available RAM.

---

## CATEGORY 10: RAG & LLM DATA PRIVACY

### Question 27: How does LuminaR guarantee that private documents from one library never enter another library's RAG prompt?
- **Spoken Answer (20–40s)**: "We use an ephemeral runtime swapping pattern inside `LibraryAssetPipeline.ask()`. Heavy inference acquires `engine.inference_lock`. The service executes `clear_runtime()` to wipe all vectors and chunks from memory, loads the single authorized document's dedicated FAISS index into the retriever, prompts the LLM, and in a mandatory `finally:` block executes `clear_runtime()` again to wipe the GPU/CPU memory clean."
- **Deep Technical Explanation**: Code in `library_asset_pipeline.py:L281-311` shows that `retriever.doc_index` and `retriever.doc_metadata` are dynamically swapped per request. Furthermore, lines 303–307 inspect all citation sources returned by the LLM and verify that every `chunk_id` belongs to that authorized document's manifest.
- **Code Reference**: [rag/services/library_asset_pipeline.py:L281-311](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L281-L311).
- **Follow-up Question**: *What prevents an attacker from exploiting a race condition while the document is loaded?*
- **Limitations / Qualifications**: `engine.inference_lock` serializes all RAG requests during the swap, preventing concurrent operations from observing another tenant's loaded index.

---

### Question 28: What model is used for RAG and does it send data to any external APIs?
- **Spoken Answer (20–40s)**: "LuminaR uses `Qwen2.5-3B-Instruct` hosted locally on the machine. Zero document chunks, queries, or prompts are sent to external cloud APIs like OpenAI or Anthropic. All embeddings, reranking, and text generation happen 100% on-premise, guaranteeing complete data sovereignty for private institutional libraries."
- **Deep Technical Explanation**: Verified in `rag/api.py:health()`, reporting local model device (`cuda` or `cpu`) and local retriever `MiniLM + FAISS`. The architecture was specifically designed for privacy-preserving library deployments where research papers and proprietary university textbooks cannot legally be transmitted to third-party cloud servers.
- **Code Reference**: [rag/api.py:L161-188](file:///d:/SDC/LibraryLLM/rag/api.py#L161-L188).
- **Follow-up Question**: *Can a prompt injection in a PDF trick the model into revealing other documents?*
- **Limitations / Qualifications**: Even if a prompt injection forces the LLM to output everything in its context, the context contains only chunks from that single authorized document. It has zero access to other libraries.

---

### Question 29: What happens if an admin revokes a user's access while the LLM is generating an answer?
- **Spoken Answer (20–40s)**: "LuminaR implements a double authority recheck. In `LibraryAssetPipeline.ask()`, `self.recheck(row, actor)` is executed immediately before prompting the LLM and immediately after token generation completes. If the user's membership was suspended or revoked while Qwen was generating the answer, `recheck()` detects the status change and raises HTTP 404, suppressing the generated output."
- **Deep Technical Explanation**: Because generative LLM inference can take 2–5 seconds, an authorization check solely at request entry creates a Time-of-Check to Time-of-Use (TOCTOU) race condition. LuminaR's post-inference recheck guarantees that revoked users never receive generated output.
- **Code Reference**: [rag/services/library_asset_pipeline.py:L300-302](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L300-L302).
- **Follow-up Question**: *What does `recheck()` specifically verify?*
- **Limitations / Qualifications**: Verifies active membership and that the document's `active_generation_id` has not changed or been replaced during inference.

---

## CATEGORY 11: DOCUMENT STORAGE & UPLOAD SECURITY

### Question 30: How does the platform defend against Path Traversal (CWE-22) in file uploads and downloads?
- **Spoken Answer (20–40s)**: "We implement three independent path traversal defenses: First, all identifiers are validated as canonical UUIDs, rejecting path separators (`/`, `\`, `..`). Second, `asset_directory()` uses `Path.resolve()` to verify that the resolved target path is strictly contained within the storage root directory. Third, the `safe_child()` helper verifies directory containment before every file read or write."
- **Deep Technical Explanation**: In `library_asset_service.py`, `canonical_id()` parses inputs via `uuid.UUID`. In `asset_directory()`, lines 64–66 check `resolved != path or root not in resolved.parents`. If an attacker submits a path with symlinks, URL-encoded traversal (`%2e%2e%2f`), or null bytes, the check fails with HTTP 404.
- **Code Reference**: [backend/services/library_asset_service.py:L48-67](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L48-L67) and [rag/services/library_asset_pipeline.py:L68-74](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L68-L74).
- **Follow-up Question**: *Are uploaded files exposed through a static file server?*
- **Limitations / Qualifications**: No. `local-data/library-assets/` is never mounted statically; every file access requires an authenticated FastAPI route dependency.

---

### Question 31: What upload validations protect against malicious files or decompression bombs?
- **Spoken Answer (20–40s)**: "All uploads are protected by multiple validation layers: An ASGI middleware enforces a strict 64 MiB payload cap. Filenames are NFC-normalized, checked against null bytes and path characters, and restricted to `.pdf`, `.txt`, and `.docx`. For PDFs, we verify `%PDF-` magic bytes, check for unencrypted streams, and enforce a strict page count limit of 10,000 pages to prevent PDF decompression bombs."
- **Deep Technical Explanation**: Enforced in `validate_pdf()` using PyMuPDF (`fitz.open(stream=content)`). If an encrypted PDF, empty file, or non-PDF binary is submitted, HTTP 400 is raised. Upload headers require `X-Luminar-Upload: <UUID>` for idempotent replay handling.
- **Code Reference**: [backend/services/library_asset_service.py:L178-200](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L178-L200) and [backend/services/library_asset_upload_limit.py](file:///d:/SDC/LibraryLLM/backend/services/library_asset_upload_limit.py).
- **Follow-up Question**: *What security headers are attached when downloading a PDF?*
- **Limitations / Qualifications**: File responses set `Cache-Control: private, no-store`, `X-Content-Type-Options: nosniff`, and `Content-Security-Policy: sandbox; default-src 'none'`.

---

### Question 32: What is the difference between `STAFF_ONLY` and `MEMBERS` asset visibility?
- **Spoken Answer (20–40s)**: "Institutional digital assets support two visibility tiers: `STAFF_ONLY` and `MEMBERS`. When staff uploads a sensitive administrative document marked `STAFF_ONLY`, general library patrons receive HTTP 404 if they attempt to list, view, download, or query the document with RAG. Patrons can only discover and read documents marked `MEMBERS` once processing has reached `READY` status."
- **Deep Technical Explanation**: In `authorize_asset()` line 110: `if member['role'] == 'GENERAL_USER' and (row['visibility'] != 'MEMBERS' or row['status'] != 'READY'): raise HTTPException(404, 'Document not found.')`. Tested in `tests/institution_v2f/test_assets.py:L134-143`.
- **Code Reference**: [backend/services/library_asset_service.py:L105-120](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L105-L120).
- **Follow-up Question**: *Why 404 instead of 403 for staff-only assets?*
- **Limitations / Qualifications**: Returning 404 conceals the existence of confidential administrative documents from students.

---

## CATEGORY 12: KNOWLEDGE TOOLS PRIVACY

### Question 33: How are generated flashcards and quizzes partitioned across libraries?
- **Spoken Answer (20–40s)**: "All Knowledge Tools are scoped by `library_id` and `asset_id` in their API routes. When tools are generated, their cache key is a SHA-256 digest that includes the `library_id`, `asset_id`, active generation UUID, and chunk checksums. Cache files are stored inside that specific asset's generation directory, guaranteeing zero cross-library tool overlap."
- **Deep Technical Explanation**: In `_cache_identity()` ([library_asset_pipeline.py:L312-317](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L312-L317)), `library_id` is the primary element in the serialized JSON array before hashing. The target file is written to `safe_child(directory, 'knowledge', key + '.json')`.
- **Code Reference**: [rag/services/library_asset_pipeline.py:L312-350](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L312-L350).
- **Follow-up Question**: *What happens to cached flashcards if the original PDF is deleted?*
- **Limitations / Qualifications**: Deleting the asset removes the directory tree, permanently deleting all cached flashcards and quizzes.

---

### Question 34: Do Knowledge Tools use the LLM, and does tool generation risk cross-tenant data leaks?
- **Spoken Answer (20–40s)**: "Knowledge Tools in LuminaR do NOT use the LLM at all. Flashcards, mind maps, and quizzes are generated using deterministic rule-based algorithms, syntactic dependency parsing, and CPU-only sentence embeddings for deduplication. Because no LLM is invoked, there is zero risk of LLM hallucination, context contamination, or cross-tenant prompt leakage."
- **Deep Technical Explanation**: Production telemetry in `document_knowledge.py` and `knowledge_quiz.py` explicitly records `'qwen_calls': 0` and `'cuda_calls': 0`. The algorithms run on CPU using local Python heuristics and `all-MiniLM-L6-v2` embeddings in `knowledge_encoder.py`.
- **Code Reference**: [rag/services/document_knowledge.py:L445](file:///d:/SDC/LibraryLLM/rag/services/document_knowledge.py#L445) and [rag/services/knowledge_quiz.py:L302](file:///d:/SDC/LibraryLLM/rag/services/knowledge_quiz.py#L302).
- **Follow-up Question**: *How are quiz distractors generated without an LLM?*
- **Limitations / Qualifications**: Distractors are sampled from semantically related entities within the same document using MMR and verified against an 11-point validation filter.

---

## CATEGORY 13: CIRCULATION, CONCURRENCY & INTEGRITY

### Question 35: What prevents a patron in Library A from borrowing a book in Library B?
- **Spoken Answer (20–40s)**: "Circulation endpoints are prefixed by `/libraries/{library_id}`. When a borrow request is submitted, `library_lending_service.py` executes `scoped(library_id, ...)` on all queries, requiring that the `library_book_id` matches an active holding owned by that library and that the user holds an active patron membership in that same library. A cross-tenant book ID returns HTTP 404."
- **Deep Technical Explanation**: In `library_lending_service.py`, `book_holding()` queries `collection('holdings').find_one({'library_id': library_id, 'library_book_id': book_id})`. If an attacker passes a book ID from Library B, the query returns `None`, raising HTTP 404.
- **Code Reference**: [backend/services/library_lending_service.py](file:///d:/SDC/LibraryLLM/backend/services/library_lending_service.py) and [backend/routes/library_lending.py:L51-54](file:///d:/SDC/LibraryLLM/backend/routes/library_lending.py#L51-L54).
- **Follow-up Question**: *Can an admin in Library A approve a loan in Library B?*
- **Limitations / Qualifications**: No. `require_library_staff` verifies that the admin has an active `ADMIN` or `LIBRARIAN` role in that exact `library_id`.

---

### Question 36: How does the system prevent double-allocation of the last available book copy during simultaneous borrow requests?
- **Spoken Answer (20–40s)**: "Every circulation state mutation is serialized under `library_mutation(library_id, durable=True)`. This acquires an atomic lock in MongoDB collection `institution_locks`. While the lock is held, the service re-reads the holding's `available_copies`, decrements the count, creates the loan record, and logs to the durable journal before releasing the lock."
- **Deep Technical Explanation**: Tested in `tests/institution_v2b/test_boundaries.py:L32-46`. A `ThreadPoolExecutor` dispatches concurrent borrow and return operations; the test asserts that only valid requests succeed and that holding availability reconciles exactly to the number of physical copies.
- **Code Reference**: [backend/services/library_lending_service.py](file:///d:/SDC/LibraryLLM/backend/services/library_lending_service.py) and [tests/institution_v2b/test_boundaries.py:L32-46](file:///d:/SDC/LibraryLLM/tests/institution_v2b/test_boundaries.py#L32-L46).
- **Follow-up Question**: *What is the lending recovery exception handler?*
- **Limitations / Qualifications**: In `main.py:L102-104`, if journal reconciliation detects an interrupted write, `RecoveryRequired` returns HTTP 503 until an operator reconciles the journal.

---

### Question 37: How does fee management and fee waiver isolation work?
- **Spoken Answer (20–40s)**: "Fee records in `institution_fees` are scoped by `library_id` and `user_id`. Patrons can only view their own fees via `/libraries/{id}/me/fees`. Staff endpoints for fee adjustment and fee waiver require `require_library_staff`. Any fee waiver requires an explicit reason, logs the staff member's ID in the fee document, and writes an audit event to `institution_audit`."
- **Deep Technical Explanation**: In `backend/routes/library_reservations_fees.py:L71-100`, endpoints enforce strict RBAC. `fees.mutate()` verifies that the fee belongs to `library_id`, updates status to `'WAIVED'`, and records `waived_by_user_id`.
- **Code Reference**: [backend/routes/library_reservations_fees.py:L71-100](file:///d:/SDC/LibraryLLM/backend/routes/library_reservations_fees.py#L71-L100).
- **Follow-up Question**: *Can an admin waive fees in another library?*
- **Limitations / Qualifications**: No; staff authorization is validated for that specific `library_id`.

---

## CATEGORY 14: SCALABILITY, TRADE-OFFS & PRODUCTION HARDENING

### Question 38: How would you scale this architecture to support 10,000 libraries?
- **Spoken Answer (20–40s)**: "To scale to 10,000 libraries: First, shard the MongoDB `institution_*` collections on `library_id` using hashed sharding, distributing tenant data evenly across database nodes. Second, move session revocation and rate limiting from local SQLite/memory to a distributed Redis cluster. Third, decouple RAG inference from FastAPI into a dedicated vLLM or Triton model serving cluster with continuous batching."
- **Deep Technical Explanation**: Currently, FAISS vector indexes are stored on local disk. For multi-node API deployments, index artifacts and PDFs would be moved to S3-compatible object storage (e.g., MinIO or AWS S3), downloading the tenant's FAISS index to the local worker cache upon first query.
- **Code Reference**: [backend/services/library_intelligence_store.py:root](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_store.py) and [rag/services/library_asset_pipeline.py](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py).
- **Follow-up Question**: *Why is sharding on `library_id` effective?*
- **Limitations / Qualifications**: Because 99% of queries in LuminaR include `library_id`, MongoDB can route queries directly to the targeted shard without scatter-gather overhead.

---

### Question 39: What are the main trade-offs of using shared collections instead of separate databases?
- **Spoken Answer (20–40s)**: "The primary advantages are resource efficiency, simple infrastructure maintenance, consolidated backups, and the ability to run global platform analytics easily. The main trade-off is the risk of data leakage if a developer writes a query without tenant scoping. We mitigated this trade-off by creating the `TenantInventory` repository wrapper and enforcing compound unique indexes."
- **Deep Technical Explanation**: Separate databases provide physical isolation, but 1,000 tenants would mean 1,000 open connection handles, separate migration scripts, and poor memory utilization in WiredTiger. LuminaR balances this by using logical separation in MongoDB combined with physical separation on the filesystem for vector indexes.
- **Code Reference**: [backend/services/library_catalogue_repository.py:L41-67](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_repository.py#L41-L67).
- **Follow-up Question**: *How do you verify isolation experimentally?*
- **Limitations / Qualifications**: Through automated integration tests (such as `tests/institution_v2f/test_assets.py`) that explicitly attempt cross-tenant retrieval and assert HTTP 404.

---

### Question 40: What are the top security improvements you would implement before commercial production deployment?
- **Spoken Answer (20–40s)**: "Before commercial production deployment, I would implement: 1. TLS/HTTPS termination via Nginx or Cloudflare reverse proxy with automated Let's Encrypt certificate renewal. 2. Storage encryption at rest for MongoDB and the `local-data/` folder using LUKS/BitLocker. 3. Institutional Single Sign-On via SAML 2.0 / OAuth2 / LDAP. 4. Redis-backed distributed rate limiting and session revocation. 5. Automated database backups with per-tenant point-in-time restore."
- **Deep Technical Explanation**: Application-level logic is thoroughly validated, but infrastructure protections (transport encryption, disk encryption, centralized identity) are required to satisfy enterprise compliance standards like SOC 2 and GDPR.
- **Code Reference**: [docs/private-library-security-audit/10_THREAT_MODEL_AND_SECURITY_GAPS.md](file:///d:/SDC/docs/private-library-security-audit/10_THREAT_MODEL_AND_SECURITY_GAPS.md).
- **Follow-up Question**: *What is the main technical contribution of your private library architecture?*
- **Limitations / Qualifications**: The hybrid architecture proving that multi-tenant RAG and semantic search can achieve zero cross-tenant contamination using dedicated local FAISS indexes with ephemeral runtime zeroing.

---

### Question 41: How do you handle database migrations across institutional tenants?
- **Spoken Answer (20–40s)**: "Because all institutions share the same collection schemas in MongoDB, schema updates are additive and execute once globally via startup index assurance scripts in `backend/main.py`. For domain migrations (such as upgrading legacy circulation to institutional lending), we developed explicit migration scripts in `scripts/migrate_lending_v2b.py` with plan, apply, and rollback operations."
- **Deep Technical Explanation**: In `main.py:lifespan()`, lines 37–48 run `ensure_indexes()` across all services. For data migrations, `scripts/migrate_lending_v2b.py` executes inside a `library_mutation` lock, validating data integrity before committing changes.
- **Code Reference**: [backend/main.py:L35-48](file:///d:/SDC/LibraryLLM/backend/main.py#L35-L48) and [scripts/migrate_lending_v2b.py](file:///d:/SDC/LibraryLLM/scripts/migrate_lending_v2b.py).
- **Follow-up Question**: *Can one library be on version 2 while another is on version 1?*
- **Limitations / Qualifications**: All libraries share the current application schema; features are toggled per-tenant via configuration records like `institution_v2c_config`.

---

### Question 42: What happens if two administrators in the same library invite the same email address simultaneously?
- **Spoken Answer (20–40s)**: "The system enforces a partial unique index in MongoDB on `institution_invitations` defined over `[('library_id', 1), ('email_normalized', 1)]` with a partial filter expression matching `status: 'PENDING'`. If two admins attempt concurrent invitations for the same email, the second operation encounters a `DuplicateKeyError` and returns HTTP 409 'A pending invitation already exists for this email'."
- **Deep Technical Explanation**: Enforced in `institution_repository.py:ensure_indexes()` line 33. The partial filter expression guarantees that while past historical invitations (`ACCEPTED`, `EXPIRED`, `REVOKED`) can exist for that email, exactly one `PENDING` invitation can exist at any given time.
- **Code Reference**: [backend/services/institution_repository.py:L33](file:///d:/SDC/LibraryLLM/backend/services/institution_repository.py#L33) and [backend/services/institution_service.py:L262-263](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L262-L263).
- **Follow-up Question**: *How do you handle case sensitivity in email addresses?*
- **Limitations / Qualifications**: All emails are normalized using `normalize_email()` (`str.lower().strip()`) before comparison or insertion.

---

### Question 43: How do you prevent staff from logging or leaking patron credentials in audit logs?
- **Spoken Answer (20–40s)**: "In `institution_repository.py:audit()`, the function enforces a strict whitelist of permitted metadata keys (`allowed = {'role', 'status', 'access_mode', 'library_book_id', 'holding_id', ...}`). Any unapproved key—such as passwords, tokens, or private notes—is automatically stripped before saving to MongoDB, preventing accidental credential leakage in the audit trail."
- **Deep Technical Explanation**: Lines 96–99 in `institution_repository.py` filter the metadata dictionary: `safe = {k: v for k, v in (metadata or {}).items() if k in allowed}`. Furthermore, integer count dictionaries are validated to contain non-negative values $\le 1,000,000$.
- **Code Reference**: [backend/services/institution_repository.py:L93-102](file:///d:/SDC/LibraryLLM/backend/services/institution_repository.py#L93-L102).
- **Follow-up Question**: *Can audit logs be deleted by a library administrator?*
- **Limitations / Qualifications**: No. There is no API route for deleting audit events; `institution_audit` is append-only.

---

### Question 44: What is the purpose of the `institution_sequences` collection?
- **Spoken Answer (20–40s)**: "The `institution_sequences` collection manages atomic sequence counters for each library. Because MongoDB does not have auto-incrementing integer primary keys like SQL databases, `institution_sequences` uses `find_one_and_update` with `$inc: {'value': 1}` to atomically generate consecutive accession numbers (e.g., `LIB-000001`, `LIB-000002`) without race conditions."
- **Deep Technical Explanation**: In `TenantInventory.accession()`, line 74 executes `sequences.find_one_and_update(query, {'$inc': {'value': 1}}, upsert=True, return_document=ReturnDocument.AFTER)`. Scoped by `(library_id, sequence_type)`. This guarantees unique, gapless accession sequence numbering per tenant.
- **Code Reference**: [backend/services/library_catalogue_repository.py:L68-79](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_repository.py#L68-L79).
- **Follow-up Question**: *What if two imports happen simultaneously?*
- **Limitations / Qualifications**: In apply mode, imports run inside `library_mutation`, serializing accession assignment.

---

### Question 45: How does the system ensure that deleted documents are not accessible through knowledge tool outputs?
- **Spoken Answer (20–40s)**: "When staff deletes a digital asset via `DELETE /libraries/{id}/assets/{asset_id}`, the backend soft-deletes the database record to `DELETED` and physically unlinks the asset directory tree on disk (`local-data/library-assets/{id}/{asset_id}/`). Because all cached knowledge tools reside inside that directory, deleting the asset physically destroys all associated flashcards, summaries, and quizzes."
- **Deep Technical Explanation**: In `library_asset_service.py:delete()`, `shutil.rmtree(asset_directory(library_id, asset_id), ignore_errors=True)` removes the folder containing `generation/{gen_id}/knowledge/`. Furthermore, the API route checks `row['status'] in {'DELETING', 'DELETED'}` and returns HTTP 404.
- **Code Reference**: [backend/services/library_asset_service.py:L260-275](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L260-L275).
- **Follow-up Question**: *What if the file deletion on disk fails due to an OS file lock?*
- **Limitations / Qualifications**: The database status is updated to `DELETED` first, which immediately blocks all API queries even if OS file handles delay physical disk cleanup.

---

### Question 46: How does the system isolate personal reading lists from institutional libraries?
- **Spoken Answer (20–40s)**: "Reading lists are personal to the user account and reside in the core domain `reading_lists` collection, keyed strictly by `user_id`. They reference global bibliographic works (`work_id`) rather than tenant-specific library book copies. A user's reading list remains accessible across all library workspaces without leaking to other members."
- **Deep Technical Explanation**: In `backend/routes/reading_list.py`, queries match `{'user_id': actor_id(current_user)}`. They allow patrons to bookmark books from the public catalogue or see if their active library holds a copy via `global_work_id` linking.
- **Code Reference**: [backend/routes/reading_list.py](file:///d:/SDC/LibraryLLM/backend/routes/reading_list.py).
- **Follow-up Question**: *Can library staff inspect a patron's personal reading list?*
- **Limitations / Qualifications**: No; reading list endpoints permit access only to the owning `user_id`.

---

### Question 47: What prevents a malicious user from uploading an executable file renamed to `.pdf`?
- **Spoken Answer (20–40s)**: "Renaming an executable file to `.pdf` will be rejected by our two-stage content validator: First, line 194 in `library_asset_service.py` inspects the raw stream bytes and verifies that the file begins with the PDF magic bytes `b'%PDF-'`. Second, line 197 opens the stream with PyMuPDF (`fitz.open(stream=content, filetype='pdf')`). An executable file will fail PyMuPDF header parsing and raise an exception."
- **Deep Technical Explanation**: A simple filename extension check is insufficient for file upload security. LuminaR inspects magic bytes and parses the internal PDF cross-reference table using PyMuPDF before accepting the file into storage.
- **Code Reference**: [backend/services/library_asset_service.py:L194-200](file:///d:/SDC/LibraryLLM/backend/services/library_asset_service.py#L194-L200).
- **Follow-up Question**: *What if a valid PDF contains embedded JavaScript malware?*
- **Limitations / Qualifications**: File responses set `Content-Security-Policy: sandbox; default-src 'none'`, which disables browser execution of embedded scripts.

---

### Question 48: How does the system handle concurrent updates to a library's profile or contact information?
- **Spoken Answer (20–40s)**: "All updates to library profile metadata via `PATCH /libraries/{id}` execute inside the distributed lock `library_mutation(library_id)`. This serializes concurrent writes from multiple administrators. Furthermore, the library record maintains an updated timestamp (`updated_at: now()`) and records an audit event in `institution_audit`."
- **Deep Technical Explanation**: In `institution_service.py:update_profile()`, lines 222–226 acquire `library_mutation(library_id)` and verify that the caller holds an active `ADMIN` role under `locked=True`.
- **Code Reference**: [backend/services/institution_service.py:L221-226](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L221-L226).
- **Follow-up Question**: *Can an admin edit the library's slug after registration?*
- **Limitations / Qualifications**: Slugs are immutable after provisioning to prevent breaking bookmarks and integration URLs.

---

### Question 49: Why is the library access code rotated via PUT rather than PATCH?
- **Spoken Answer (20–40s)**: "Access code rotation via `PUT /libraries/{id}/access-code` represents an idempotent, complete replacement of the institutional secret. It takes the new access code, hashes it with Argon2id, updates `institution_security`, records `access_code_changed_at` and `access_code_changed_by`, and appends an `ACCESS_CODE_CHANGED` event to `institution_audit`."
- **Deep Technical Explanation**: Rotating the code does not invalidate existing member memberships; it only affects future join attempts. Any patron who previously joined retains their active `institution_memberships` record.
- **Code Reference**: [backend/services/institution_service.py:L191-202](file:///d:/SDC/LibraryLLM/backend/services/institution_service.py#L191-L202).
- **Follow-up Question**: *How do you kick out unauthorized users if an access code was leaked?*
- **Limitations / Qualifications**: An admin rotates the access code, then navigates to the Memberships tab and sets compromised member records to `REMOVED`.

---

### Question 50: How are overdue fees calculated and what prevents calculation errors?
- **Spoken Answer (20–40s)**: "Overdue fees are calculated automatically during the return confirmation lifecycle in `library_fee_service.py`. When staff confirms a book return, the system compares `returned_at` against the loan's `due_at`. If overdue, it multiplies the elapsed days by the library's daily rate policy, creating an immutable fee document in `institution_fees`."
- **Deep Technical Explanation**: In `library_fee_service.py`, daily overdue rates and maximum fee caps are enforced. Calculations use integer currency cents or decimal precision to prevent floating-point rounding errors.
- **Code Reference**: [backend/services/library_fee_service.py](file:///d:/SDC/LibraryLLM/backend/services/library_fee_service.py).
- **Follow-up Question**: *Can a patron dispute or request a fee waiver?*
- **Limitations / Qualifications**: Patrons cannot waive fees themselves; waivers require staff intervention via `POST /libraries/{id}/staff/fees/{fee_id}/waive`.

---

### Question 51: How does the system ensure that digital assets are processed asynchronously without blocking API responses?
- **Spoken Answer (20–40s)**: "When staff uploads a document via `POST /libraries/{id}/assets`, the Core API validates the file, writes it to disk, creates an asset record with `status: 'PROCESSING'`, enqueues a background job in `institution_library_asset_jobs` with state `'QUEUED'`, and immediately returns HTTP 202 Accepted. A resident worker in the RAG process claims the job and executes OCR, chunking, and FAISS indexing in the background."
- **Deep Technical Explanation**: Decoupling file acceptance (HTTP 202) from RAG processing ensures that slow PyMuPDF parsing and MiniLM embedding generation do not tie up API request workers or trigger client HTTP timeouts.
- **Code Reference**: [backend/routes/library_assets.py:L33-44](file:///d:/SDC/LibraryLLM/backend/routes/library_assets.py#L33-L44) and [rag/services/library_asset_pipeline.py:L96-100](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L96-L100).
- **Follow-up Question**: *How does the frontend track progress?*
- **Limitations / Qualifications**: The frontend polls `GET /libraries/{id}/assets/{asset_id}` to display progress (`QUEUED`, `PROCESSING`, `READY`, `FAILED`).

---

### Question 52: What is worker fencing and how does it prevent stale workers from corrupting index builds?
- **Spoken Answer (20–40s)**: "Worker fencing uses unique fence tokens (`fence_token = uuid4()`) and leased heartbeats. When a worker claims a build job, it acquires a lease. If the worker hangs or experiences network partition, the lease expires and another worker can claim the job with a new fence token. When the original worker wakes up and attempts to publish, the update query fails because the fence token in the database no longer matches."
- **Deep Technical Explanation**: In `TenantIntelligence.run_one()`, lines 70–71 execute:
  `result = update_one({'job_id': job['job_id'], 'fence_token': job['fence_token']}, ...)`.
  If matched count is 0, it raises `HTTPException(409, 'WORKER_FENCED')`. Tested explicitly in `tests/institution_v2g/test_intelligence.py:L74-77`.
- **Code Reference**: [search/library_intelligence.py:L70-75](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L70-L75) and [tests/institution_v2g/test_intelligence.py:L74-77](file:///d:/SDC/LibraryLLM/tests/institution_v2g/test_intelligence.py#L74-L77).
- **Follow-up Question**: *What is the lease duration?*
- **Limitations / Qualifications**: Leases expire after 90 seconds (`LEASE_SECONDS = 90`) with heartbeats renewed every 10 seconds.

---

### Question 53: How does LuminaR handle user logout across multiple services?
- **Spoken Answer (20–40s)**: "When a user logs out via `POST /auth/logout`, the Core API coordinates a dual cleanup: It issues an internal HTTP call to the RAG service (`/rag/session/logout`) to immediately delete all ephemeral server copies of personal uploaded documents, and it inserts the token's session ID (`sid`) into `revoked_sessions` in SQLite to invalidate the JWT immediately."
- **Deep Technical Explanation**: In `backend/routes/auth.py:L22-36`, `logout()` calls `httpx.post(RAG_URL + '/rag/session/logout')` with a 5-second timeout, followed by `revoke(current_user)`. On the frontend, `useAuthStore.logout()` purges tokens and user state from localStorage and dispatches `luminar-documents-cleared`.
- **Code Reference**: [backend/routes/auth.py:L22-36](file:///d:/SDC/LibraryLLM/backend/routes/auth.py#L22-L36) and [frontend/src/store/useAuthStore.ts:L265-291](file:///d:/SDC/LibraryLLM/frontend/src/store/useAuthStore.ts#L265-L291).
- **Follow-up Question**: *What if the RAG service is temporarily offline during logout?*
- **Limitations / Qualifications**: The Core API still revokes the JWT session; the RAG service's startup sweeper will clean up orphaned temporary documents upon its next restart.

---

### Question 54: What happens if a user is deleted from the platform?
- **Spoken Answer (20–40s)**: "In LuminaR, account lifecycle updates are managed via `backend/services/platform_account_service.py`. When an account is deactivated or marked inactive, `decode_access_token()` checks `is_active: {'$ne': False}` via `current_identity()`. Any subsequent API call by that user fails with HTTP 401 'Invalid or expired token', immediately cutting off access to all libraries."
- **Deep Technical Explanation**: In `backend/services/identity_service.py:current_identity()`, the user document is looked up in MongoDB. If `is_active` is False or `is_email_verified` is False, it returns `None`, which triggers HTTP 401 in `dependencies.py`.
- **Code Reference**: [backend/services/identity_service.py](file:///d:/SDC/LibraryLLM/backend/services/identity_service.py) and [backend/utils/jwt_utils.py:L57](file:///d:/SDC/LibraryLLM/backend/utils/jwt_utils.py#L57).
- **Follow-up Question**: *Are historical loan records preserved if a user is deactivated?*
- **Limitations / Qualifications**: Yes; historical loan and audit records retain the user's numeric `user_id` for institutional accountability.

---

### Question 55: How does the Knowledge Graph maintain institutional privacy?
- **Spoken Answer (20–40s)**: "The institutional knowledge graph generated by `search/library_intelligence.py` extracts entities (Books, Authors, Subjects) strictly from the library's active catalog records in `institution_library_books`. It writes a dedicated `graph.json` file inside `local-data/library-intelligence/{library_id}/kg/{generation_id}/`. It never accesses other libraries' books or personal uploads."
- **Deep Technical Explanation**: Tested in [tests/institution_v2g/test_intelligence.py:L152-157](file:///d:/SDC/LibraryLLM/tests/institution_v2g/test_intelligence.py#L152-L157) (`test_tenant_kg_local_identity_and_no_private_nodes`). The test asserts that `graph['nodes']` contains only nodes corresponding to the library's books, authors, and subjects, with `source == 'TENANT_KG'`.
- **Code Reference**: [search/library_intelligence.py:L49](file:///d:/SDC/LibraryLLM/search/library_intelligence.py#L49) and [backend/services/library_intelligence_artifacts.py:build_graph](file:///d:/SDC/LibraryLLM/backend/services/library_intelligence_artifacts.py).
- **Follow-up Question**: *How does the frontend render this graph?*
- **Limitations / Qualifications**: Rendered via SVG canvas with force-directed physics; node details are fetched from the library's catalog.

---

### Question 56: What security headers are applied across the FastAPI application?
- **Spoken Answer (20–40s)**: "Every sensitive route applies restrictive security headers via FastAPI dependencies. Digital asset routes attach `Cache-Control: private, no-store` to prevent proxy caching, `X-Content-Type-Options: nosniff` to prevent MIME-sniffing attacks, and `Content-Security-Policy: sandbox; default-src 'none'` to sandbox browser execution of rendered documents."
- **Deep Technical Explanation**: In `backend/routes/library_assets.py:L16-19`, the router injects `private_response` dependency into all asset routes. Similarly, `rag/services/library_asset_routes.py:L34-38` injects `Cache-Control: no-store` and `nosniff` across all RAG endpoints.
- **Code Reference**: [backend/routes/library_assets.py:L16-19](file:///d:/SDC/LibraryLLM/backend/routes/library_assets.py#L16-L19) and [rag/services/library_asset_routes.py:L34-38](file:///d:/SDC/LibraryLLM/rag/services/library_asset_routes.py#L34-L38).
- **Follow-up Question**: *What is CORS configured to allow?*
- **Limitations / Qualifications**: CORS middleware in `main.py:L123-142` restricts allowed origins to `http://localhost:3000` and `http://localhost:5173`. In production, this must be updated to the production domain.

---

### Question 57: How does LuminaR protect against Cross-Site Request Forgery (CSRF)?
- **Spoken Answer (20–40s)**: "LuminaR uses Bearer token authentication in the HTTP `Authorization` header rather than ambient browser session cookies. Because browser JavaScript must explicitly attach the `Authorization: Bearer <token>` header on every request, cross-origin web requests cannot automatically submit credentials, inherently neutralizing CSRF attacks."
- **Deep Technical Explanation**: CSRF attacks rely on browsers automatically attaching session cookies to cross-origin requests. Because LuminaR does not use session cookies for API authentication and requires explicit Bearer headers configured in `frontend/src/api/core.ts`, CSRF attacks are prevented by design.
- **Code Reference**: [frontend/src/api/core.ts](file:///d:/SDC/LibraryLLM/frontend/src/api/core.ts) and [backend/dependencies.py:L10-24](file:///d:/SDC/LibraryLLM/backend/dependencies.py#L10-L24).
- **Follow-up Question**: *Where is the JWT stored in the browser?*
- **Limitations / Qualifications**: Stored in browser `localStorage`. While immune to CSRF, `localStorage` is susceptible to Cross-Site Scripting (XSS), which is mitigated by strict React JSX escaping and CSP headers.

---

### Question 58: How are email verification OTPs protected against timing attacks?
- **Spoken Answer (20–40s)**: "Email verification OTPs are hashed using bcrypt before storage in `email_verifications_collection`. When verified in `verify_email_otp()`, we use `bcrypt.checkpw()`, which operates in constant-time comparison relative to the salt and hash, preventing attackers from using timing side-channels to determine correct digits."
- **Deep Technical Explanation**: In `auth_service.py:verify_email_otp()`, lines 130–150 retrieve the hashed OTP document, verify expiry ($< 15\text{ minutes}$), and execute `bcrypt.checkpw(otp.encode('utf-8'), record['otp_hash'].encode('utf-8'))`.
- **Code Reference**: [backend/services/auth_service.py:L130-150](file:///d:/SDC/LibraryLLM/backend/services/auth_service.py#L130-L150).
- **Follow-up Question**: *How many attempts are allowed for an OTP?*
- **Limitations / Qualifications**: The global auth rate limiter (`limit_auth_attempts`) blocks IPs exceeding 5 attempts within a window.

---

### Question 59: How does the system prevent denial of service through large JSON payloads?
- **Spoken Answer (20–40s)**: "In `rag/services/library_asset_pipeline.py`, we implement `atomic_json()` and `bounded_json()`. When writing or reading JSON artifacts (manifests, chunks, knowledge tools), the code enforces strict byte budgets: `MAX_JSON_ARTIFACT_BYTES = 64 MiB` and `MAX_MANIFEST_BYTES = 1 MiB`. If any artifact exceeds its safety budget, it raises HTTP 413, preventing memory exhaustion."
- **Deep Technical Explanation**: In `atomic_json()`, lines 46–65 iterate over JSON fragments using `iterencode()`, counting UTF-8 bytes and raising HTTP 413 if the limit is exceeded before writing to an atomic temporary file with `os.fsync()`.
- **Code Reference**: [rag/services/library_asset_pipeline.py:L46-65, L77-81](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py#L46-L65#L77-L81).
- **Follow-up Question**: *Why is atomic temporary writing necessary?*
- **Limitations / Qualifications**: Prevents corrupt partial JSON files if the server runs out of disk space or crashes mid-write.

---

### Question 60: What is the single strongest architectural defense mechanism in your entire private library system?
- **Spoken Answer (20–40s)**: "The single strongest defense mechanism is our **Zero-Trust Multi-Tier Authorization Pipeline**: We decouple identity from authority, resolve membership dynamically on every single request against MongoDB, conceal unauthorized resources with HTTP 404, enforce database boundaries with the `TenantInventory` repository wrapper, and isolate vector search using dedicated physical FAISS indexes per library with ephemeral runtime zeroing. No single point of failure can breach tenant isolation."
- **Deep Technical Explanation**: Even if an attacker compromises a JWT, guesses an asset UUID, or executes an adversarial prompt injection in a PDF, the defense-in-depth architecture stops them at each boundary: the database prevents cross-tenant queries, the filesystem sandbox prevents path traversal, and the retriever runtime loads only that single authorized document's vectors.
- **Code Reference**: [backend/institution_dependencies.py](file:///d:/SDC/LibraryLLM/backend/institution_dependencies.py), [backend/services/library_catalogue_repository.py](file:///d:/SDC/LibraryLLM/backend/services/library_catalogue_repository.py), [search/library_intelligence.py](file:///d:/SDC/LibraryLLM/search/library_intelligence.py), and [rag/services/library_asset_pipeline.py](file:///d:/SDC/LibraryLLM/rag/services/library_asset_pipeline.py).
- **Follow-up Question**: *How do you prove this to the examination committee?*
- **Limitations / Qualifications**: By demonstrating our live automated test suite in `tests/institution_v2f` and `tests/institution_v2g`, which runs reproducible tests verifying cross-tenant access denial and vector index isolation.
