# Know More ephemeral documents and encrypted device cache

Final status: **PARTIAL**. The feature's ownership, purge, ciphertext, restore, browser isolation and build checks pass. The broader existing Book RAG suite has one failure in `test_overview_rule_never_accepts_added_premises[What are the major themes of this book?]`. Both that test and `rag/query_types.py` match the saved baseline byte for byte. They were left unchanged as requested. Ten tests in the broader suite were skipped and are not claimed as passing.

## A. Old document lifecycle

Uploads were unauthenticated, identified from filenames, and persisted under shared `rag/documents`, `rag/extracted`, `rag/chunks` and the shared document FAISS index/metadata. The same uploaded corpus was available across accounts. Logout only removed frontend auth state. There were no Mongo uploaded-document collections in this pipeline; permanent Mongo `book_chunks` is a separate Book RAG asset.

## B. New server lifecycle

Private uploads are always authenticated and isolated under `rag/private_documents/doc_<random>/`. A SQLite registry records server-derived account, login sid, expiry and state. Lifecycle: INGESTING -> ACTIVE -> DELETING -> purged. Ingest writes a raw PDF, extraction, chunks, numeric vectors and runtime FAISS. Restore writes chunks, numeric vectors and runtime FAISS only. Active documents expire with their token; startup and a 60-second sweeper remove expired/revoked/interrupted/orphan artifacts. Cleanup failures leave data inaccessible in DELETING and retry later.

## C. Owner/session model

Existing HS256 JWT signing, live account checks and numeric sub remain. Each login now gets a random UUID sid; reader TTL remains 60 minutes, staff 30 minutes. Core and RAG share a SQLite revocation ledger (sid plus expiry only). Active authorization requires both sub and sid and an unexpired, nonrevoked session. Cross-account and same-account-other-session document lookups return identical private 404s. Missing/expired/legacy-no-sid authentication receives 401 for private documents. Legacy tokens retain account/book compatibility but must re-login for uploads. Assistant conversation ownership also includes sid.

## D. Logout purge

Frontend first settles already-started cache jobs for at most 1.5 seconds, removes temporary local records, calls authenticated RAG logout, then Core logout and clears private UI state. No export starts at logout. RAG revokes before deleting every session-owned directory and registry row and clearing document retrieval/intent caches and assistant conversations. Opted-in local cache does not alter purge behavior. Core can revoke even if the RAG worker is unavailable; the next sweep/startup completes removal. Cleanup APIs return pending status rather than reopening access. Unit tests cover file-deletion failure/retry, expiry, in-flight preparation and another session remaining active. Browser validation verified absent registry rows and directories after both A logouts.

## E. Local cache architecture

An isolated `LocalDocumentCacheRepository` owns binary ciphertext and minimal bookkeeping. OPFS stores random-named `.bin` files; IndexedDB stores opaque cache ID, owner scope, encrypted descriptor, format, size, timestamps, keep flag and OPFS pointer. When OPFS is unavailable, IndexedDB stores the ciphertext Blob itself. Atomic replacement commits a new file before replacing metadata and deleting the old file. A serialized queue and browser locks coordinate writes where supported. Authenticated server descriptor inspection supplies names only for rendering; names/hashes are not persisted in clear bookkeeping. Other accounts' records never enter the normal UI.

## F. Why OPFS/IndexedDB

They support asynchronous binary storage without string/base64 bulk payloads. OPFS is preferred for file bytes, while IndexedDB supplies structured bookkeeping and a Blob fallback. The live browser selected **OPFS**. Browser retention remains subject to quota, eviction and clearing; a persistence request is advisory. The cache is bound to the browser profile and origin, so ports 5173 and 5174 have different storage.

## G. Why cookies were rejected

Document bundles are too large and are unnecessary on every request. Cookies, localStorage and sessionStorage contain no PDFs, chunks, vectors, descriptors or cached document text. Existing auth token storage remains unchanged; it is not used for document storage. Only encrypted descriptors use bounded base64 transport, not the bulk bundle.

## H. Cache bundle contents

Exactly four ZIP_STORED entries: `manifest.json`, `chunks.json`, `embeddings.npy`, `source_map.json`. Chunks preserve IDs, text and page numbers. Vectors preserve the exact normalized float32 matrix. Source map preserves chunk-to-page references. The original PDF, redundant page extraction and serialized FAISS are omitted: the current Know More UI has no PDF viewer/download requiring them. The encrypted portable bundle is streamed to the browser and never stored as a server archive.

## I. Manifest

Version, cache ID, original PDF SHA256, pipeline fingerprint, chunker version, embedding model/dimension/dtype/normalization, chunk/page counts, source-map version, creation time, filename and per-entry SHA256 checksums. The manifest and descriptor are encrypted. Envelope metadata exposes only format/key versions, pseudonymous owner scope, cache ID, purpose and fingerprint; authenticated associated data protects this metadata.

## J. Pipeline fingerprint

SHA256 over canonical configuration plus hashes of the actual existing clean_text, chunk_text, PDF extraction, chunk creation and embedding helper source. It includes format/schema, MiniLM model, 384 dimensions, float32 normalization, 3000-character chunks/400 overlap and source map version. Changed processing or key/format versions return structured CACHE_INCOMPATIBLE (409) and require re-upload. Fingerprinting does not modify the existing algorithm.

## K. Encryption design

`cryptography` AES-256-GCM with a fresh random 12-byte nonce. The binary container is magic `LUMKMC1\0`, a bounded big-endian JSON-header length, authenticated header, nonce and ciphertext with its authentication tag. Separate purposes protect bundles and descriptors. There is no browser decryption key, plaintext device bundle or production auto-generated master key. One persistent server-only 32-byte base64 master key is configured privately in local `.env`; its value is absent from reports and frontend builds.

## L. Key derivation

HKDF-SHA256 derives 32-byte keys from that master using a versioned salt and info containing server-authenticated account ID, purpose and key version. Browser-provided user IDs are never trusted. Same account can decrypt after re-login; another account derives a different key. Replacing the master or version invalidates old copies; multi-key rotation support is a future extension.

## M. Owner scope ID

HMAC-SHA256 of a domain-separated account identifier under the master. It is a stable pseudonym within a key configuration, not a raw user ID or login sid. It permits device filtering across same-account sessions while preventing another account's server restore. It is not a substitute for authentication.

## N. Bundle integrity

AEAD authentication precedes parsing. Validated checksums protect entry consistency. Limits apply to ciphertext, decoded plaintext, central directory, exact archive entry count and per-entry/count/vector fields. Unknown, duplicate, traversal, compressed, ZIP64 and oversized archives are rejected. EOCD is checked before constructing ZipFile, and no archive extraction occurs. Malformed values, object arrays and unsafe deserializers are rejected.

## O. Restore validation

Authenticate -> bounded binary read -> derive current-account key -> validate/decrypt envelope -> check fingerprint/schema/checksums -> validate chunk IDs/text/page/count/source map -> validate NPY header/dtype/shape/length/finite normalized vectors -> create new owned session ID -> rebuild FAISS -> publish ACTIVE. `np.load(..., allow_pickle=False)` is used only after numeric header checks. Restore never calls PDF parsing, chunking or embedding inference. Repeated restore of the same cache within one session is idempotent; a fresh session receives a new document ID. No raw foreign filesystem paths are imported.

## P. FAISS reconstruction

Fresh IndexFlatIP(384), add validated float32 normalized vectors, write a server-created runtime index. No browser-supplied serialized FAISS index is read. Runtime loading reads only the already-created owned server artifact under the engine inference lock. Private retrieval is selected explicitly and cleared in finally. Global and Book RAG never receive uploaded document chunks.

## Q. Retrieval equivalence

Real MiniLM, CrossEncoder and Qwen were used on generated 2-, 40- and 200-page study PDFs. Original/restored top-k IDs match, maximum score difference is **0.0** (tolerance 1e-6), source chunk IDs/pages/text match after excluding the deliberately new document identity, verdicts are SUPPORTED and answer strings match exactly. First-question time was roughly 5.8–7.5 seconds before and after; this change saves preparation, not Qwen inference. Protected RAG prompts, retriever, reranker, evidence, chunker and Book/KG/recommendation algorithms remain unchanged.

## R. Account isolation

HTTP tests verify unauthenticated access, other-account document 404, same-account-other-session 404, other-account bundle rejection, descriptor rejection, token revocation and independent sessions. Browser A -> logout -> B hid A's copy; a controlled test page bypassed UI filtering and submitted A's ciphertext with B authentication: 400, rejected. A logged in again, saw its retained copy and restored a distinct ACTIVE document.

## S. Browser threat model

Ciphertext at rest protects copied storage against disclosure of plaintext without server-account authorization and master key. It does not protect an authenticated account from same-origin XSS, malicious extensions, profile/OS compromise or stolen valid credentials. React renders descriptor names as text. The cache ID/scope/size/timestamps are visible bookkeeping. Browser caches cannot be remotely wiped after server purge; removal is a device-local user action. Filesystem deletion is logical removal, not a promise of physical secure erasure/backups being overwritten.

## T. Cache sizes

| Fixture | Pages/chunks | PDF bytes | Encrypted bytes |
|---|---:|---:|---:|
| Small | 2/2 | 2,903 | 9,023 |
| Medium | 40/40 | 49,418 | 148,770 |
| Large | 200/200 | 246,222 | 737,937 |

Vectors/text can make the prepared bundle larger than a compressed PDF. Limits: 64 MiB encrypted request/bundle, 128 MiB decoded plain ceiling, 20,000 chunks, 10,000 pages. Actual uncompressed archive must also fit the encrypted limit. Device profile: 10 copies/128 MiB; quota check before writing. Full cache rejects with manual removal guidance. No silent LRU pruning or deletion of a selected copy. Timestamps support future policy; no automatic retention TTL is imposed on opted-in device copies.

## U. Full processing versus restore timings

| Fixture | Full upload ms | Export ms | Restore ms | Preparation saved | FAISS restore ms | Parse/chunk/embed original -> restore |
|---|---:|---:|---:|---:|---:|---|
| Small | 120.96 | 50.63 | 30.02 | 75.18% | 1.24 | 1/1/1 -> 0/0/0 |
| Medium | 170.99 | 35.39 | 30.49 | 82.17% | 0.46 | 1/1/1 -> 0/0/0 |
| Large | 649.30 | 38.25 | 30.25 | 95.34% | 0.92 | 1/1/1 -> 0/0/0 |

Warm resident models, local HTTP/TestClient paths, generated access-control documents; these are measured examples, not broad hardware/corpus guarantees. Local browser smoke copy: 3,554 bytes, OPFS read 5.3 ms and write 18.7 ms. Browser write was measured by rewriting the same encrypted copy through the real repository. Export runs asynchronously after upload; first question is usable before export finishes.

## V. Tests

| Check | Result | Evidence |
|---|---|---|
| Private docs + latency + book access + assistant + KG contract suite | 376 passed, 10 skipped | know_more_cache_backend_tests.log |
| Final private-doc security/metrics suite after final edits | 50 passed | know_more_cache_backend_final_tests.log |
| Auth/staff suite | 76 passed | know_more_cache_auth_tests.log |
| Additional Book RAG/KG suite | 124 passed, 1 pre-existing failure | know_more_cache_book_kg_tests.log |
| Cache/assistant/KG/Part 3 frontend combined | 117 passed | know_more_cache_frontend_tests.log |
| Final cache/assistant/graph/Part 3 rerun after UI edits | 102 passed (KG product's 15 tests were in prior run) | know_more_cache_frontend_final_tests.log |
| Standard frontend commands | 31 routing/Read Now + 81 assistant passed | know_more_cache_standard_frontend.log |
| Production build | PASS | know_more_cache_build.log |
| Lint | exit 0, 19 existing warnings | know_more_cache_lint.log |

Counts overlap and should not be added. New tests cover corrupt archive/AEAD/manifest/vectors, owner+session access, safe restoration, identical retrieval, in-flight logout, failure cleanup, expiry, source isolation, device backend fallback, quotas, account switching and UI. Existing semantic hashes remain protected; only transport/session-boundary expectations were adapted. No accepted Book RAG behavior was modified to silence its unrelated failing expectation. Safe aggregate counters record exports/restores/failures by code/incompatibilities/uploads/size and total preparation/export/restore time without text/filenames. Development logs contain opaque identities, pseudonyms, versions, sizes, durations and cleanup reasons. Sweeper failures are logged without sensitive payloads and retried next interval.

## W. Live validation

UI on isolated origin `127.0.0.1:5174`, disposable verified Mongo accounts 17 and 18. A opted in, uploaded, observed ACTIVE + cached, asked a question; its cache survived token expiry/service interruption. A's fresh-session restore ID differed from upload ID. Explicit A logout removed all active files/registry. B saw zero cache entries; controlled foreign-ciphertext restore was rejected. B logout -> A login -> restore received another new ID; question/source matched; final logout removed all active files/registry again. Device test copy and both accounts were removed afterward; temporary credentials file was deleted.

The tiny one-page UI fixture produced the same existing UNSUPPORTED answer before and after restore (source p.1). It is an honest UI lifecycle smoke test, not evidence of answer quality. Three richer real-model benchmark fixtures independently produced equivalent SUPPORTED answers. Screenshot: `know_more_browser_restored.png`. Detailed browser evidence: `know_more_browser_validation.json` and `know_more_cache_security.json`.

## X. Known limitations

One unchanged Book RAG test fails; ten skipped tests remain unverified. Existing lint warnings remain. Cache support requires IndexedDB and a usable browser quota; fallback was unit tested, OPFS was live tested. Cache export/restore is bounded but buffered in memory. Single RAG worker is required because current engine retriever/lock are process-local; shared session ledger assumes services share the same host/path. Revocation denies access immediately when reachable; offline deletion completes on worker restart/sweep. Legacy ownerless server files remain inaccessible and must be cleaned by an operator under the existing retention policy; they are never silently migrated/exported. No original-PDF viewing/downloading is available after restore. Master-key loss/rotation or pipeline change requires re-upload. Current metadata counters are process-local. Browser device caches are neither synchronized between origins/devices nor remotely removable. The benchmark corpus is synthetic and warm-model timings exclude cold startup. The restarted search service reports its existing STALE index condition; no index rebuild or recommendation/KG change was made. Core and RAG health are healthy, with private_document_cache_enabled=true.

## Files changed

- Auth: backend/services/login_sessions.py (new), backend/utils/jwt_utils.py, backend/routes/auth.py.
- Private document/cache: rag/services/local_document_cache.py, rag/services/private_documents.py, rag/services/private_document_routes.py (new); rag/api.py; assistant/api.py (conversation sid only).
- Frontend: src/lib/localDocumentCache.ts, src/lib/documentCacheApi.ts, src/hooks/useDeviceDocuments.ts, src/components/DeviceDocuments.tsx (new); src/pages/LLMPage.tsx, src/store/useAuthStore.ts, src/components/Header.tsx, src/App.tsx; package.json/package-lock.json (fake-indexeddb).
- Tests/tooling: tests/test_private_document_cache.py (new), tests/staff_auth/test_auth.py, tests/test_document_rag_latency.py, tests/test_assistant_backend.py; frontend/tests/document-cache.test.tsx and cache-storage-inspector.html (new); scripts/benchmark_private_document_cache.py (new).
- Config: .env.know-more.example (new), .gitignore; private local .env (persistent secret plus enabled flag, never published).
- Reports: this report, secure_cache_audit.md, cache_security/performance/equivalence/preexisting_failure/browser_validation JSON, browser screenshot and test/build/lint logs prefixed know_more_.

The repository has no Git metadata, so this is an explicit implementation file inventory rather than a git diff.

## Exact startup commands

Local `.env` now has `KNOW_MORE_DEVICE_CACHE_ENABLED=true` with a configured persistent server-only key. The example defaults false. User checkbox always initializes false. Run each blocking server in its own PowerShell terminal from D:\SDC\LibraryLLM; Mongo and configured model/data assets must be available. Do not start duplicate workers on occupied ports.

```powershell
Set-Location 'D:\SDC\LibraryLLM'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --workers 1
```

```powershell
Set-Location 'D:\SDC\LibraryLLM'
.\.venv\Scripts\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003 --workers 1
```

```powershell
Set-Location 'D:\SDC\LibraryLLM'
.\.venv\Scripts\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004 --workers 1
```

```powershell
Set-Location 'D:\SDC\LibraryLLM'
.\.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1
```

```powershell
Set-Location 'D:\SDC\LibraryLLM\frontend'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Core/RAG/search/recommendation/main frontend were restarted after validation, using one worker and existing real models. The isolated test frontend at 5174 is stopped after validation. No KG or recommendation algorithm work follows this task.

## Acceptance checklist

Items 1–29 and 31: PASS in the scoped automated/live checks described above. Item 30 (all existing tests pass): PARTIAL because of the verified pre-existing Book RAG failure and ten skips. Therefore the overall outcome is PARTIAL, not a claim of a clean full regression run.
