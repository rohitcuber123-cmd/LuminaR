# Institution Part 2F completion

**FINAL: PASS.** Library Digital Assets + Private Document / RAG Tenancy is complete.

| Field | Result |
| --- | --- |
| A. FINAL | PASS — Institution Part 2F complete; stopped before tenant catalogue intelligence. |
| B. EXISTING DOCUMENT / RAG AUDIT | Personal/session registry, permanent Book RAG, flat historical indexes, OCR, Knowledge Tools and AI context audited before product changes. |
| C. CONTENT CLASSIFICATION | GLOBAL, PERSONAL_PRIVATE, BOOK_RAG, reusable LIBRARY_TENANT_CAPABLE, LEGACY_AMBIGUOUS, TEMPORARY and UNKNOWN_REVIEW_REQUIRED; no inferred ownership. |
| D. DIGITAL-ASSET MODEL | Immutable asset UUID + canonical library UUID, uploader, PDF metadata/checksum/storage key, visibility, book link, explicit statuses and tombstone fields. |
| E. AUTHORIZATION | Fresh active verified account + ACTIVE exact LibraryMembership + ACTIVE library. ADMIN/LIBRARIAN manage; GENERAL_USER reads permitted READY assets. Platform role supplies no tenant authority. |
| F. VISIBILITY | STAFF_ONLY and MEMBERS; list/detail/file/RAG/cache/source/tool paths freshly enforce current visibility. |
| G. STORAGE | local-data/library-assets/<library UUID>/<asset UUID>/source.pdf; fenced generation UUID artifacts; original filename is metadata. |
| H. PATH / FILE SAFETY | 64 MiB PDF limit, bounded multipart spooling, PDF signature and native parser validation, empty/corrupt/encrypted/unsupported rejection, canonical containment and symlink/junction guards. |
| I. PROCESSING | UPLOADING → PROCESSING → READY or FAILED; durable Mongo jobs, heartbeat and fenced publication. UTF-8 derived JSON is capped at 64 MiB and manifests at 1 MiB; ARTIFACT_LIMIT preserves the source and prevents READY. |
| J. OCR / EXTRACTION REUSE | Accepted DocumentService extraction/chunk/embedding primitives and private_document_ocr PyMuPDF/Tesseract pipeline reused; no replacement OCR or model. |
| K. CHUNK IDENTITY | Every chunk and manifest retain library UUID, asset UUID, generation UUID, chunk ID, page and source offsets. |
| L. VECTOR / RAG ISOLATION | Per-asset FAISS, source/checksum manifests and engine inference lock. Fresh authorization before private reads and before returning answers; runtime/cache cleared after use. |
| M. BOOK ↔ ASSET LINKING | Same-library ACTIVE book association works for global-linked and local-only records. Cross-library linking rejected; global work reference never globalizes the PDF. |
| N. PERSONAL SEPARATION | Personal upload remains account/session owned; actual UI upload/list separation and cleanup verified, original personal logical corpus unchanged. |
| O. STAFF DIGITAL ASSETS UI | Canonical /staff/libraries/:libraryId/assets[/assetId], upload/search/filter/list/detail/edit/book link/visibility/retry/delete. |
| P. PATRON RESOURCE UI | Canonical /libraries/:libraryId/resources[/assetId], authorized metadata/PDF/explicit document Ask/Knowledge Tools. |
| Q. BOOK DETAIL | Library-owned detail shows only permitted linked resources; explicit global Book Detail has none. |
| R. ASSISTANT | Explicit per-asset document Q&A reuses resident production engine/Qwen. Global Assistant never automatically searches library assets; floating global launcher suppressed only in dedicated document workspace. |
| S. SELECT FOR AI | Global work selection unchanged. Typed LIBRARY_ASSET selection deferred under Phase 20 allowance; explicit source-scoped document Q&A is functional. |
| T. KNOWLEDGE TOOLS | One shared frontend renderer and existing DKM/summary/concepts/flashcards/mindmap/quiz/cloze algorithms, with library/asset/version/options cache identity and fresh guards. |
| U. FILE ACCESS | Authorized streaming FileResponse and Range 206, private no-store/nosniff; PDF reader sandbox, each new download reauthorizes. |
| V. DELETION | DELETING immediately denies access; derived index retired, source retained in tombstoned retired directory, metadata/audit retained, final DELETED. |
| W. REVOCATION | Same logged-in browser next file and RAG requests denied after membership removal; frontend clears denied answers/readers/tool artifacts. |
| X. LIFECYCLE | Disposable SUSPENDED/REMOVED access denial and both restore paths validated with exact retained asset/source data; TEST lifecycle unchanged. |
| Y. AUDIT | All eight required event types observed live with actor/library/asset/time and bounded metadata; metadata edit also audited. |
| Z. FAILURE / RETRY | Same immutable asset reprocessed from FAILED to READY. Fault tests cover persistence, OCR, chunking, embeddings, acknowledgement loss, lease expiry and incomplete deletion. |
| AA. RECONCILIATION | Dry-run detects orphan/missing source and RAG artifacts, checksum/provenance/job anomalies. Explicit known empty failed QA generation retired safely; final scan has no findings. |
| AB. MIGRATION | Historical dry-run inventory and explicit evidence/mapping validation only; no apply/sharing/personal transfer or ownership guessing. |
| AC. MULTI-LIBRARY | Same QA account A GENERAL_USER, B ADMIN, C LIBRARIAN uses only the selected library assets; identical PDF asset IDs and sources remain separate. |
| AD. CACHE ISOLATION | Library + asset + generation + checksum + chunk revision + tool/version/options; same-content A/B cache hits retain different artifact identities. |
| AE. SECURITY | 148 new backend tests and 21 live boundary checks pass; no tenant authorization bypass found in independent review. |
| AF. PERFORMANCE | Local list max 37.78 ms, metadata 32.96 ms, file Range startup 21.19 ms. Small native PDF upload-to-READY 1.20–2.27 s; existing Q&A 16.88–24.20 s. No throughput/load guarantee. |
| AG. RESPONSIVE | 48 document page/dialog checks +96 accepted product checks, all six specified viewports, no page overflow or inaccessible action overlap. |
| AH. ACCESSIBILITY | 144 axe audits without violations; 870 rendered contrast measurements; native dialog focus trap/Escape/restore and >=44px controls. |
| AI. LIVE BROWSER | All A–J document scenarios, 32 product walkthrough steps, Staff/Home/Events/Notifications/Analytics/Platform checks, zero page errors. |
| AJ. BACKEND TESTS | 1928 unique PASS; 10 existing security skips; 21 regression groups; 132 asset tests +16 activity/identity tests. |
| AK. FRONTEND TESTS | 775 PASS, including 37 asset tests +14 activity tests; shared existing tools and affected workspace suites retained. |
| AL. REGRESSION | V1,2A,2B,2C,2D,2E, workspace/Platform/catalogue, Search/Recommendation/KG, Book/personal RAG, OCR/Knowledge Tools/Assistant production pass. Router research excluded. |
| AM. BUILD / LINT | Build PASS; lint 0 errors /14 pre-existing warnings, including final scoped CSS repairs. |
| AN. TEST PRESERVATION | 150 ACTIVE local books and 150 holdings intact; original non-asset records exact hashes unchanged. Two READY QA documents retained, one MEMBERS and one STAFF_ONLY. 1 separately inventoried concurrent Owner upload preserved; 3 current TEST assets in total. |
| AO. GLOBAL CATALOGUE | Estimated 5,000,000 preserved; no full 5M-row digest claim. |
| AP. HNSW / KG | 196 protected artifact size/mtime records unchanged; 155 frozen source hashes unchanged. rag/api.py differs only by two adapter-install lines; no tenant HNSW/KG built. |
| AQ. EXACT FILES CHANGED | See institution_v2f_files_changed.json: exact post-baseline SHA differences, plus the separately listed baseline operator authored before capture. |
| AR. REPORTS | All 29 requested reports exist, including four activity addendum reports; supporting routes, responsive, cleanup, preservation, JUnit and screenshots retained. |
| AS. KNOWN LIMITATIONS | PDF-only; local filesystem and bounded single-worker queue; no malware scanner/quota/S3/hard-purge. Already delivered bytes cannot be recalled. Historical migration applies no transfers; global asset selection remains deferred. Unknown Mongo commit outcomes fail closed for operator reconciliation. |
| AT. IMPROVEMENT REVIEW | All 20 requested future topics reviewed and deferred; none implemented automatically. |
| AU. RECOMMENDED NEXT PHASE | Tenant Catalogue Intelligence Infrastructure: versioned per-library generation/job/artifact validation and atomic publish, followed by explicit scoped Search/KG routing. Recommendation only; wait for approval. |
| BM. OPERATIONAL ACTIVITY CSS ROOT CAUSE | ui-table had no cell styling: browser-default geometry concatenated raw event/account/reference text. Accessible reference text also needed a containing block inside the scroll region. |
| BN. OPERATIONAL ACTIVITY TABLE REPAIR | Shared StaffUI Table/Pager, padded fixed-layout columns, sentence-case event labels and bounded UUID presentation with complete accessible value. |
| BO. AUDIT TABLE CONVERGENCE | Same shared Staff table variant and Pager; administrative meaning and ADMIN-only authorization preserved. |
| BP. ACTOR IDENTITY HYDRATION | Current canonical account email displayed as primary identity; actor_user_id retained unchanged. No hardcoded identities. |
| BQ. MEMBER IDENTITY HYDRATION | Separate member decoration from target_user_id; correct live TEST Patron email verified independently from Actor. |
| BR. HISTORICAL IDENTITY FALLBACK | System for null actor; existing safe target-email snapshot where applicable; otherwise available name or Account #canonical ID. Missing/deleted accounts do not erase history. |
| BS. IDENTITY LOOKUP PERFORMANCE | One projected bounded users query per nonempty page, at most 200 unique IDs for100 events. A50-row repeated-ID fixture confirms one lookup; no N+1. |
| BT. ACTIVITY / AUDIT RESPONSIVE RESULT | Both pages pass all six specified sizes:12 browser/axe/keyboard/contrast checks, contained scrolling,44px pagination targets and no document overflow. |

## Retained TEST resources

- `TEST_members`: asset `b0095984-ad97-49a2-96ad-d0fc7be6d1d0`, visibility `MEMBERS`, linked book `3deb40a3-a3de-407d-973c-a9c6aae919b2`.
- `TEST_staff`: asset `f2598ccf-3845-4bc9-9cd5-3aa28517cb13`, visibility `STAFF_ONLY`, linked book `a8a04662-23be-45ea-bb20-0f0b86bcfa12`.

## Activity addendum QA summary

| Check | Result |
| --- | --- |
| OPERATIONAL_ACTIVITY_COLUMNS_SEPARATED | YES |
| OPERATIONAL_ACTIVITY_SHARED_TABLE_STYLE | YES |
| AUDIT_SHARED_TABLE_STYLE | YES |
| ACTOR_EMAIL_DISPLAYED | YES |
| MEMBER_EMAIL_DISPLAYED | YES |
| RAW_USER_NUMBER_PRIMARY_DISPLAY_REMAINS | NO |
| RAW_ACCOUNT_NUMBER_PRIMARY_DISPLAY_REMAINS | NO |
| CANONICAL_USER_ID_PRESERVED_IN_AUDIT | YES |
| IDENTITY_LOOKUP_BATCHED | YES |
| IDENTITY_N_PLUS_ONE | NO |
| UNRESOLVED_HISTORICAL_ACTOR_SAFE | YES |
| LONG_REFERENCE_LAYOUT_PASS | YES |
| ACTIVITY_MOBILE_LAYOUT_PASS | YES |
| AUDIT_MOBILE_LAYOUT_PASS | YES |

Raw numbered primary identities are removed for resolvable accounts; Account #id remains the intentional historical fallback only when identity is unavailable. Displayed email is current account identity; canonical actor ID remains the historical authority.

One concurrent upload by the existing TEST Owner was observed during final validation and preserved separately. Its content was not inspected or included in reports. See institution_v2f_concurrent_user_activity.json for bounded identity/provenance metadata.

Six disposable QA libraries are soft-removed; eight ordinary QA accounts disabled; both temporary Platform grants revoked. The final local QA Platform account remains ordinary and unprivileged under the self-disable guard. Human Owner/Patron roles were preserved. Services remain running.

## Reports

- [institution_v2f_baseline.json](D:/SDC/LibraryLLM/reports/institution_v2f_baseline.json)
- [institution_v2f_document_rag_audit.md](D:/SDC/LibraryLLM/reports/institution_v2f_document_rag_audit.md)
- [institution_v2f_storage_audit.md](D:/SDC/LibraryLLM/reports/institution_v2f_storage_audit.md)
- [institution_v2f_vector_index_audit.md](D:/SDC/LibraryLLM/reports/institution_v2f_vector_index_audit.md)
- [institution_v2f_ai_context_audit.md](D:/SDC/LibraryLLM/reports/institution_v2f_ai_context_audit.md)
- [institution_v2f_asset_architecture.md](D:/SDC/LibraryLLM/reports/institution_v2f_asset_architecture.md)
- [institution_v2f_authorization.json](D:/SDC/LibraryLLM/reports/institution_v2f_authorization.json)
- [institution_v2f_storage_isolation.json](D:/SDC/LibraryLLM/reports/institution_v2f_storage_isolation.json)
- [institution_v2f_processing.json](D:/SDC/LibraryLLM/reports/institution_v2f_processing.json)
- [institution_v2f_rag_isolation.json](D:/SDC/LibraryLLM/reports/institution_v2f_rag_isolation.json)
- [institution_v2f_book_linking.json](D:/SDC/LibraryLLM/reports/institution_v2f_book_linking.json)
- [institution_v2f_personal_document_separation.md](D:/SDC/LibraryLLM/reports/institution_v2f_personal_document_separation.md)
- [institution_v2f_assistant_integration.md](D:/SDC/LibraryLLM/reports/institution_v2f_assistant_integration.md)
- [institution_v2f_deletion_recovery.json](D:/SDC/LibraryLLM/reports/institution_v2f_deletion_recovery.json)
- [institution_v2f_reconciliation.json](D:/SDC/LibraryLLM/reports/institution_v2f_reconciliation.json)
- [institution_v2f_migration.json](D:/SDC/LibraryLLM/reports/institution_v2f_migration.json)
- [institution_v2f_frontend.json](D:/SDC/LibraryLLM/reports/institution_v2f_frontend.json)
- [institution_v2f_browser.json](D:/SDC/LibraryLLM/reports/institution_v2f_browser.json)
- [institution_v2f_accessibility.json](D:/SDC/LibraryLLM/reports/institution_v2f_accessibility.json)
- [institution_v2f_performance.json](D:/SDC/LibraryLLM/reports/institution_v2f_performance.json)
- [institution_v2f_security.json](D:/SDC/LibraryLLM/reports/institution_v2f_security.json)
- [institution_v2f_regression.json](D:/SDC/LibraryLLM/reports/institution_v2f_regression.json)
- [institution_v2f_preservation.json](D:/SDC/LibraryLLM/reports/institution_v2f_preservation.json)
- [institution_v2f_improvement_review.md](D:/SDC/LibraryLLM/reports/institution_v2f_improvement_review.md)
- [institution_v2f_next_scope.md](D:/SDC/LibraryLLM/reports/institution_v2f_next_scope.md)
- [institution_v2f_activity_ui_audit.md](D:/SDC/LibraryLLM/reports/institution_v2f_activity_ui_audit.md)
- [institution_v2f_activity_identity_hydration.md](D:/SDC/LibraryLLM/reports/institution_v2f_activity_identity_hydration.md)
- [institution_v2f_activity_table_validation.json](D:/SDC/LibraryLLM/reports/institution_v2f_activity_table_validation.json)
- [institution_v2f_audit_identity_validation.json](D:/SDC/LibraryLLM/reports/institution_v2f_audit_identity_validation.json)
- [institution_v2f_files_changed.json](D:/SDC/LibraryLLM/reports/institution_v2f_files_changed.json)
- [institution_v2f_responsive.json](D:/SDC/LibraryLLM/reports/institution_v2f_responsive.json)
- [institution_v2f_routes.json](D:/SDC/LibraryLLM/reports/institution_v2f_routes.json)
- [institution_v2f_qa_cleanup.json](D:/SDC/LibraryLLM/reports/institution_v2f_qa_cleanup.json)

STOPPED after Part 2F. No Events/Notifications/Analytics domain expansion, tenant catalogue index/KG, Build/Rebuild controls, digital sharing or next phase was started.

## Part 2F.1 closure

The counts and acceptance evidence above describe the accepted Part 2F baseline. The subsequent critical closure is complete: [institution_v2f1_critical_completion.md](D:/SDC/LibraryLLM/reports/institution_v2f1_critical_completion.md). All additional gates 186–230 pass; current regression totals are 1,944 unique backend tests and 805 frontend tests. This includes canonical Staff Catalog, the three-way Physical/Online/Both workflow, original-colour cover restoration, card controls, native document reading/Q&A and preservation. Part 2G has not started.
