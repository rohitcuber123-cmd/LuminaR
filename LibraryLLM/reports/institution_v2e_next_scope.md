# Recommended next scope after Institution Part 2E

Recommendation: begin with a read-only **Institution Digital Asset + Private Document / RAG Tenancy authorization-boundary audit**, after explicit user approval. This document is a recommendation only. No implementation, migration, upload, permission grant, vector/index build or next-phase task was started.

## Remaining boundary found by source inspection

The existing private-document path is personal/session owned. `rag/services/private_documents.py` stores document ownership by account and session, checks ACTIVE state and expiry in `owned()`, and keeps its upload artifacts separate from permanent book assets. `rag/services/private_document_routes.py` exposes personal PDF upload/list/detail/delete, logout cleanup and account-scoped local-cache inspect/export/restore. `rag/api.py` checks personal document ownership for private selections and delegates permanent/global book selection to `book_access.authorize_selection`.

Those existing checks are useful personal boundaries. They do not establish library ownership, staff upload rights, patron library-document access, tenant lifecycle behavior or a canonical association between a local library book and an institution-owned file. A global work ID, existing session owner or Platform assignment must not be used to guess that authority. The current phase preserves these services and adds no document content to Staff Analytics.

## Proposed audit deliverables, before implementation

| Boundary to inspect | Required decision/evidence |
| --- | --- |
| Asset identity and ownership | Inventory personal/session uploads, permanent global book files, local-cache bundles, generated Knowledge Tool artifacts and any canonical institution references. Classify each as PERSONAL, GLOBAL, LIBRARY or unresolved; do not silently convert existing assets. |
| Library-owned PDF/document model | Propose canonical library UUID + opaque asset ID and explicit local-book association. A globally linked local book must not inherit another library's document permission. |
| Staff upload and management | Define current ADMIN/LIBRARIAN responsibilities, file/type/size limits, provenance and any ADMIN-only deletion/policy decisions. Platform authority remains independent. |
| Patron access | Specify membership, public/private visibility, library lifecycle, book association and file-download versus retrieval permissions. An outsider must not learn protected asset existence from metadata/errors. |
| Retrieval isolation | Inspect authorization before selection, file/chunk retrieval, vector candidates, reranking, citations, previews and generated answers. Scope every lookup to canonical asset ownership and permitted library UUID. |
| Assistant context | Trace explicit route/library selection into authorized document selection without changing frozen router/ranking behavior. Reject stale selections after account/library switch or revocation. |
| Caches and derived artifacts | Inspect keying and ownership for extracted text, embeddings, answers, encrypted local bundles and Knowledge Tool exports. Fresh authorization applies on cache hits and restore; stale tenant permissions cannot survive in derived output. |
| Revocation, suspension, removal and deletion | Define denial timing, data retention/recovery, purge semantics and removal of derived artifacts. Distinguish soft library lifecycle from authorized permanent document deletion. |
| Migration and ambiguity | Produce a dry-run inventory and explicit approval/mapping proposal for any historical library assets. Unattributed files remain unresolved; no first-library, legacy role or work-ID inference. |
| Audit and test matrix | Plan current ADMIN/LIBRARIAN/GENERAL_USER/Platform-only/dual-authority tests, A/B same-work isolation, download/citation leakage, revoked membership, account switch and lifecycle denial. Use disposable assets; preserve TEST and global artifacts. |

The audit should identify source files, actual storage and authorization call sites, unresolved requirements, threat cases and a concrete implementation proposal for user review. Its output should make later implementation scope reviewable before any writes or migrations.

## Deferred implementation

Library-owned document storage, tenant retrieval changes, staff uploads, patron digital access and permission migrations require a separate explicitly authorized phase. Tenant HNSW/KG, Build/Rebuild controls, analytics schedules and BI exports are outside this recommendation. Existing global catalogue, ranking, Assistant/router, HNSW/KG and personal-document behavior remain frozen during the proposed audit.

Source evidence:

- [Personal document ownership and artifacts](D:/SDC/LibraryLLM/rag/services/private_documents.py)
- [Personal document routes and cache access](D:/SDC/LibraryLLM/rag/services/private_document_routes.py)
- [RAG selection boundary](D:/SDC/LibraryLLM/rag/api.py)
- [Book access guard](D:/SDC/LibraryLLM/rag/services/book_access.py)
- [Current metric/privacy inventory](D:/SDC/LibraryLLM/reports/institution_v2e_metric_inventory.json)
- [Part 2E analytics architecture](D:/SDC/LibraryLLM/reports/institution_v2e_analytics_architecture.md)

Part 2E stops after Tenant Analytics + Reporting. Wait for explicit approval before beginning this recommended audit.
