# Private-library architecture — proposed design

## Status and evidence boundary

**PROPOSED / FUTURE WORK — EARLY IMPLEMENTATION, NOT YET PRODUCTION READY.** The active application has physical `library_inventory` and issue `library_id` fields, selected inventory import, and a library value in parts of the UI. It does not establish institution membership, private catalogue ownership, or independently selected retrieval indexes. Personal PDF owner/session isolation is a separate, implemented boundary. None of the schemas or APIs below were implemented by this audit.

Evidence: `LibraryLLM/backend/services/inventory_import_service.py:510 confirm_inventory_import`, `backend/services/issue_service.py:49 issue_book`, `search/api.py:195 search`, `search/index_manager.py:113 IndexManager`, `rag/services/private_documents.py:23 PrivateDocuments`. See [current schema](08_DATABASE_ARCHITECTURE.md), [search](03_SEMANTIC_SEARCH.md), [RAG](04_RAG_AND_CHATBOT.md), and [exact symbol index](SOURCE_EVIDENCE_INDEX.md). Source paths below are relative to `LibraryLLM/` unless prefixed explicitly.

## 1. Design invariants

1. A library is a persistent institution with a server-assigned immutable ID; its display name and slug can change.
2. An account is global. Membership, role and active status are scoped to a library. A saved active-library preference never grants permission.
3. Every private catalogue record, holding, dataset, job, graph namespace and full-text source has an authoritative library owner. Client-supplied scope is checked against that owner.
4. Authorization happens before candidate retrieval. Returned candidates, hydrated books, RAG chunks and sources are checked again against the authorized scope.
5. Unavailable, corrupt, missing or unauthorized private indexes never fall back to the global catalogue or another library.
6. Index labels are local to a partition and generation. Public API book/holding identities remain stable through rebuilds.
7. Publication exposes a coherent dataset/index generation. A failed replacement leaves the preceding published generation usable, with failure reported to the librarian.
8. A conversation, pending action and result cache remember their originating library. Library switching creates a new context and rejects late responses from the old context.
9. Public discovery, platform administration and cross-library search are explicit policies/endpoints, not implicit exceptions to private scope.

These are required engineering contracts. Their mere implementation is not an algorithmic novelty claim.

## 2. IDs, ownership and relationships

Keep backend `library_id` spelling for compatibility; frontend `libraryId` can be translated at the API boundary. Use a server-generated UUID or a similarly immutable opaque identifier. IDs are not secrets or authorization tokens. Existing `LIB001` can map to a seeded legacy institution during migration; do not silently reinterpret all historical records as belonging to a newly created institution.

```text
User ──< LibraryMembership >── Library
Library ──< CatalogueDataset ──< DatasetRow / ImportFailure
Library ──< LibraryHolding >── BibliographicWork
Library ──< PrivateCatalogueRecord (optional work reference)
Library ──< IndexGeneration / IndexJob
LibraryHolding ──< Issue / Reservation / Fine / ScopedActivity
Library ──< Event / LibraryDocument / ScopedConversation
```

Separate bibliographic identity from physical ownership. A public Open Library work can be shared by many libraries; each holding has independent copies and shelf details. A private description or unknown work belongs to a scoped catalogue record, rather than overwriting the global public work. Same title or ISBN in different libraries is valid. ISBN identifies an edition imperfectly and is not a globally unique physical-holding key. Existing inventory already partially expresses this separation; search hydration currently sometimes substitutes global book copy counts, so inventory authority must be resolved before extending it.

### Proposed record shapes

| Entity | Minimum proposed fields | Ownership/index contract |
|---|---|---|
| Library | library_id, name, slug, status, creator_id, created_at, policy_version, visibility_policy, published_catalogue_generation | Unique immutable ID; lifecycle ACTIVE/SUSPENDED/DELETING/DELETED; creator does not replace membership authorization |
| LibraryMembership | user_id, library_id, role, status, invited_by, accepted_at, permissions_version | Unique user+library; roles OWNER/LIBRARIAN/READER; server validates administrative transitions |
| CatalogueDataset | dataset_id, library_id, version, uploader_id, source_filename, checksum, byte_count, import_mode, schema_version, uploaded_at, status, valid_count, rejected_count, book_count, indexed_count, job_id, published_generation | Unique library+version; checksum used with idempotency/import mode, not as universal semantic identity |
| LibraryHolding | holding_id, library_id, work_id or private_record_id, edition/ISBN, total_copies, available_copies, shelf_location, status, dataset_id/version, semantic_hash, index_status | Stable globally unique holding ID; unique scoped source key; nonnegative counts and guarded updates |
| PrivateCatalogueRecord | record_id, library_id, title, authors, subjects, description, publication/edition data, source/provenance, content_hash, active | Unknown work can be indexed without fabricating an Open Library work ID |
| LibraryDocument | document_id, library_id, holding_id, owner_type, source_path/object_key, rights/access policy, revision, chunking/model versions, index generation, state | Catalogue metadata upload is not a right to ingest its full text; selected full-text source is separately authorized |
| IndexGeneration | library_id, generation_id, dataset_id/version, model ID/fingerprint, dimension, metric, normalization/text versions, partition type, counts/checksums, durable bundle locator, state, created_at | Immutable manifest; publication uses one authoritative generation pointer |
| IndexJob | job_id, library_id, dataset_id/version, requested_by, type, status, stage, processed/total, retry_count, lease_owner/expiry/fencing_token, error_code, idempotency_key | Durable scoped execution; safe structured errors and resumable checkpoints |
| ScopedConversation | conversation_id, user_id, library_id, membership/permissions revision, selected holding/document IDs, created_at, state version | Reject actions and sources from other libraries; personal PDFs remain separately owner-authorized |

Issues, reservations, fines, activity, searches and recommendation feedback store immutable `library_id`, holding identity and relevant generation/policy version. A loan's ownership must survive a library switch or holding retirement. Reading lists need an explicit product decision: global bibliographic saves can remain personal, while a library-specific save must carry its holding and scope. Do not infer current access from saved metadata.

### Mongo indexes and migration

Create unique `(user_id, library_id)` membership, `(library_id, dataset_version)` datasets, scoped holding source-key indexes, `(library_id, status, timestamp)` circulation/event indexes, scoped idempotency keys and job lease lookup indexes. Unique ISBN across all holdings is inappropriate. Enforce ownership of redundant IDs on write, even when database references lack foreign-key enforcement.

Migration order: inventory the observed legacy data; seed a legacy library; bind justified records to it; resolve orphan/ambiguous histories; introduce nullable fields with dual-read compatibility restricted to the legacy namespace; backfill; validate counts/ownership; require scope for new writes; finally remove global fallback. Keep migrations resumable with an audit log. Historical loans without provable ownership need explicit remediation, not a guessed library. Numeric public IDs can remain globally allocated; existing `book_service` max+1 allocation should be replaced by an atomic counter before concurrent dataset ingestion.

## 3. Authorization and request context

Extend the existing JWT identity and revocation checks rather than embedding permanent memberships in the JWT. A `LibraryContext` dependency resolves the requested library, current account, live membership status, allowed operation and permissions revision. It attaches a validated context to each request and rejects inconsistent holding/dataset/event/conversation owners. It does not trust a browser store, query parameter, JWT role alone, or guessed library ID.

| Operation | Reader member | Librarian member | Owner member | Platform admin |
|---|---|---|---|---|
| Private catalogue/search/authorized QA | Yes, subject to source entitlement | Yes | Yes | Only explicit audited support capability |
| Borrow/reserve/own histories | Own actions within policy | Own or explicitly assisted policy | Same | Explicit support policy |
| Dataset upload/index job control | No | Yes | Yes | Explicit support policy |
| Books/inventory/event administration | No | Own library | Own library | Explicit support policy |
| Invite/remove librarian or change institution policy | No | Restricted invitation policy | Yes | Explicit platform operation |
| Read library analytics | No by default | Scoped aggregates | Scoped aggregates | Explicit aggregate/report capability |

Current global ADMIN/LIBRARIAN roles do not prove institutional ownership. Keep platform and library roles distinct; do not give a librarian access to every library. Revocation must invalidate selection, jobs/actions where required, and cached results; defining an acceptable short permissions-cache TTL needs an explicit policy. Uniform unauthorized/not-found responses should avoid revealing resource existence. Anonymous/public catalogue browsing can be separately enabled by a library's policy with an explicit public scope; private content remains unavailable.

## 4. API scope design

Recommend explicit library IDs in route paths for reviewability and stable links. An account preference can supply the UI default but cannot change an existing resource's owner. The alternative implicit active-library header/context is convenient but creates ambiguous deep links, stale requests and service-to-service propagation. If a header is used, the backend still validates it and binds resource IDs.

The current Vite `/api` prefix is stripped before core FastAPI. Proposed public URLs below would therefore mount `/libraries/...` in the core app. Search and RAG remain separate services behind `/search-api` and `/rag-api`; propagate the validated scope and user identity, then verify membership in each service or through a trusted internal authorization boundary. Do not accept an arbitrary client header as proof of internal authorization.

| Proposed public endpoint | Purpose / required scope | Current integration location |
|---|---|---|
| POST /api/libraries | Register institution and initial owner, subject to platform policy | backend/main.py + new libraries service/router |
| GET /api/libraries/mine | Authorized memberships and capabilities | Existing auth identity dependencies |
| GET/PATCH /api/libraries/{L} | Details / owner-authorized policy changes | New scoped library service |
| POST /api/libraries/{L}/members/invitations | Authorized scoped invitation; acceptance verified | auth/staff setup can supply reusable account mechanics |
| POST /api/libraries/{L}/datasets/preview | Bounded validated CSV/XLSX preview with uploader ownership | inventory_import_service preview machinery |
| POST /api/libraries/{L}/datasets | Confirm immutable version and enqueue ingestion; return job ID | Existing confirm is inventory-only, must not be mislabeled catalogue indexing |
| GET /api/libraries/{L}/datasets/{D}/jobs/{J} | Stage/counts/failure/retry state | New durable jobs/status service |
| POST /api/libraries/{L}/datasets/{D}/publish-or-retry | Authorized state transition, idempotency and expected version | New job/publication service; exact publish UX depends on policy |
| POST /search-api/libraries/{L}/search | Authorized scoped catalogue generation, filters/paging | search/api.py; registry replaces one engine selection |
| GET/PATCH /api/libraries/{L}/holdings/{H} | Scoped metadata/inventory CRUD | books/inventory/availability services |
| POST /api/libraries/{L}/issues, reservations, renewals | Server binds holding and library; scoped queues/stock | issue_service, reservation_service, renewal_service |
| POST /rag-api/libraries/{L}/ask | Scoped conversation/source entitlement and retrieval | rag/api.py, book_access.py, book_assets.py, retriever.py |
| POST /rag-api/libraries/{L}/assistant/chat-or-confirm | Conversation-bound tool scope and confirmed mutations | assistant tools/client/orchestrator |
| GET/POST /api/libraries/{L}/events | Member feed or scoped staff administration | events routers/service and receipt state |
| GET /api/libraries/{L}/analytics | Scoped role and aggregation predicate | notifications summary/admin services |
| GET /recommendation-api/libraries/{L}/recommendations | Scoped profile, candidate, availability and graph | recommendation/api.py + related-book service |

Review *all* lookup, list, export, summary, search history, related-book, capability/know-more, read-now, fine settlement, notices, receipts, sync status and repair endpoints. Checking the principal search endpoint alone leaves alternate data paths open. Existing personal PDF upload/cache routes can remain owner/session scoped; attaching a personal document to a library chat requires an explicit source policy and does not convert it into a library-owned file.

## 5. Dataset lifecycle and visibility

The current CSV/XLSX import resolves ISBN against existing metadata and inserts matched physical inventory. It does not create unknown catalogue works, embed uploaded rows or create a private index. Extend it as a separate versioned catalogue pipeline, preserving useful preview validation.

```text
UPLOADED → VALIDATING → IMPORTING → EMBEDDING → INDEXING
         → validation failure         → failure/retry
INDEXING → VERIFIED → READY/PUBLISHED
any unfinished state → FAILED or CANCELLED with scoped checkpoints
```

1. Authorize uploader membership and quotas; store bounded file with sanitized display filename and opaque storage key, checksum and idempotency token.
2. Parse supported formats; validate title/identifier/list types/copy counts and row lengths; reject formulas/unsafe archive expansion where relevant; retain row numbers and reason codes.
3. Resolve public work/edition matches. Unknown books become private catalogue records, not discarded rows or invented public IDs. Preview duplicates/ambiguities and obtain import mode (`append`, `merge`, `replace`) explicitly.
4. Stage dataset records and reconcile stable holdings. Replacement must not reset available copies while loans remain active; preserve loan/return history and retired holdings.
5. Generate normalized semantic text and hashes with a named text-rule version; embed compatible model batches; checkpoint counts and content hashes.
6. Build the library's index generation and complete mapping, validate counts/checksums/scope/model, then persist the immutable bundle durably.
7. Publish a single authoritative catalogue-generation record binding the dataset, allowed records and index manifest. Queries require that exact generation; local disk pointers are projections, not independent authorities.
8. Retain the preceding generation for rollback/readers; clean expired versions only after no active jobs/readers require them and retention policy permits it.

Mongo and files cannot be committed together atomically. A durable blob-first, authoritative Mongo-pointer-last protocol is a proposed solution: failed prepublication files are unreferenced garbage; a pointer never references an unverified nondurable bundle. Where Mongo transactions are available, stage metadata/outbox and change the publication record in a transaction. Otherwise explicitly adopt and test durable journaling/reconciliation similar to the existing semantic mutation journal. Do not claim two independent pointers are atomic. Queries validate generation compatibility, and unavailable bundles fail closed while recovery restores the referenced version.

Use `PENDING/INDEXED/FAILED/STALE` record indexing states tied to model/generation/hash. Physical `ntotal` includes tombstones; compare expected live searchable records to live mapping/hash coverage, not just raw vector count. A recovery utility should reconcile DB, jobs, manifests and live mapping, retry scoped failures and rebuild deterministically. Progress exposes processed/total and stages; an accurate ETA is optional and must account for batching/queueing. Content/error details visible only to authorized librarians.

## 6. Retrieval and RAG scope

Recommend a registry selecting separate library partitions with FlatIP for small collections and HNSW for larger ones. The threshold is **TO BE MEASURED**, not an asserted universal size. Share model resources, not private graph namespaces. [22](22_PRIVATE_LIBRARY_HNSW_PLAN.md) specifies current base/delta behavior, alternatives, identifiers and recovery.

Catalogue candidates map to scoped holding/private-record IDs, hydrate only authorized published records and use that library's inventory counts. Optional lexical SQLite candidates, reranker inputs, ranked cache, recommendations and KG neighbors must all honor the same library/generation. A global public metadata cache may serve public work fields, but must never replace private description/stock/rights fields or cause a fallback private query.

The current book QA path uses per-book/global **FlatIP**, not catalogue HNSW. Future library QA binds `(library_id, holding_id, source_revision, index_generation)` before loading a book/document index. Select only authorized library corpus/source IDs; hydrate and cite only chunks with matching owner and generation. Metadata retrieval is not full-text authorization. Borrow-based read-now policy remains separate from staff rights and source licensing. Unselected library QA must also enforce source entitlement; current global no-selection QA is a gap if all full text requires borrowing.

Personal PDFs retain owner+sid authorization, including encrypted cache restore and expiry. Library-shared PDFs require LibraryDocument ownership/membership and independent lifecycle. Do not reuse a personal document's session expiry as institutional retention, or a global work ID alone as private full-text identity. Model output, source citations and assistant tool results must include scope for internal validation; visible technical metadata should be limited to useful source provenance.

## 7. Frontend selection and conversations

Add an account library picker showing authorized memberships, capability-specific navigation and a scoped URL. Registration/join/invitation, dataset preview/progress/error/retry, library holdings and owner membership management are new pages. Existing SearchPage, book detail/capability/read-now, LLMPage, AIChatWidget, recommendations/related books, StaffDashboard, circulation/reservations/fines/history/reading list, events/notices and analytics need scoped requests and rendering.

On switch: increment context epoch; abort outstanding requests; ignore late old-epoch responses; clear pending actions and selection; scope URL paging and result caches; reload permissions/inventory/feed/unseen counts. Cache keys include user, library, permissions revision, dataset/index/model generation and query/filter/depth/source selection. A library name in the header alone does not make the underlying data scoped.

Keep an existing conversation bound to its original library. Switching starts or opens that library's conversation; show the original context when viewing an older chat, and reauthorize on resume. Do not concatenate previous-library evidence into a new-library prompt. Confirmation IDs include conversation/library/owner/expiry and are checked against current membership. Existing frontend owner/session fences and selected-resource revision checks are useful precedents, but the current process-local conversation store has no institutional scope.

## 8. Events, notifications and analytics

Add library ownership to events and validate related holdings against it. Scoped staff can create/edit/publish/cancel/archive/delete drafts only within their library; published global platform notices use an explicit separate audience. Bind unseen state and signed receipt to user+session+library, and reset/reload badge state on switch. Library membership changes control delivery/access. Current date-based views do not constitute scheduled publication.

Analytics start with an authorized library predicate on holdings, issues, reservation queues, fines, members, searches, events and jobs. Preserve immutable ownership in histories so aggregation remains valid after retirement. Distinguish titles with stock from total copies and users from memberships. Platform totals require a separate explicit role/report. Aggregate AI usage/event engagement would be new instrumentation; it is not currently demonstrated. Protect query/content telemetry, report denominators/time windows, and suppress or restrict small sensitive cohorts as policy requires.

## 9. Workload and experiments

10 libraries can still exceed memory if each has millions of vectors; 10,000 libraries can be manageable if tiny and mostly cold. Evaluate active working set, total vectors, concurrent queries/imports, library skew and storage limits, not library count alone. One 384-dimensional float32 vector uses 1,536 bytes before graph/mapping/metadata overhead. Shared GPU/model loading, lazy graph acquisition, byte-budgeted eviction, quotas and durable jobs are necessary planning tools, not a proven 10,000-library capacity claim.

Run controlled 10/100/1,000/10,000-library scenarios only within actual available hardware. Include uniform/skewed collections, cold-load bursts, small/large datasets, concurrent uploads/searches, exact authorized neighbor ground truth, model upgrades, membership revocation, duplicates, corrupt mappings and process restarts. Measure authorized recall/nDCG, zero observed unauthorized candidates/outputs/sources, p50/p95/p99 including cold load, jobs/sec, publication delay, resident/disk bytes, fairness and recovery time. A zero leak count in a suite is bounded evidence, not a proof for all inputs. Protocols: [12](12_EXPERIMENT_PLAN.md), [13](13_METRICS_AND_BASELINES.md), [22](22_PRIVATE_LIBRARY_HNSW_PLAN.md).

## 10. Explicit answers to the 31 requested questions

1. **Cleanest libraryId introduction?** Add a first-class Library + Membership and validated LibraryContext. Keep current snake_case naming and seed/backfill a justified legacy scope; do not add an unchecked filter alone.
2. **Which entities change?** Holdings/inventory, private book records, datasets/previews/jobs/manifests, issues/locks/reservations/fines/activity, search/profile/feedback, category/graph caches, events/receipts/notices and conversation/source mappings; global users/public works remain shared. Full field/index matrix is above and in [08](08_DATABASE_ARCHITECTURE.md).
3. **Which APIs need scope?** Catalogue/search, holdings/import/CRUD, capabilities/full text/QA/assistant tools, recommendations/KG, circulation and histories, events/notices/analytics and index administration. Personal account and owned-PDF endpoints retain their own explicit boundary.
4. **Which frontend pages?** Search/book/read-now/LLM/assistant/recommendations; reader circulation/history/saves; staff datasets/inventory/books/events/analytics; account memberships/library picker. Scope deep links and requests, not just navigation labels.
5. **Which admin routes need ownership?** Every dataset/holding/book/inventory/event/member/policy/job/repair/export/analytics and assisted circulation route. Global staff authentication currently lacks this institution ownership proof.
6. **Can current HNSW support multiple indexes?** FAISS can create independent graphs, and IndexManager accepts a root/collection. Current singleton selection, global query hydration, queues and corpus builder must be refactored; merely instantiating multiple managers over the same global books does not isolate them.
7. **Is the HNSW object global/singleton?** One module-level engine in search/api.py owns one IndexManager per process; snapshots contain base and delta graphs. This is not a cluster-wide singleton or institution registry.
8. **Is persistence one file?** No. Legacy base assets coexist with versioned delta/mapping/override/manifests and an active pointer. A future library uses its own immutable bundle/root; see [22](22_PRIVATE_LIBRARY_HNSW_PLAN.md).
9. **How are vector IDs generated?** FAISS implicit zero-based row labels; base mapping array and delta list translate them. Appending uses the partition's current length; no universal vector-ID counter.
10. **Will labels collide across libraries?** The same integer label can validly occur in every graph. A collision becomes harmful when mappings omit library/generation/partition or the wrong graph is acquired.
11. **Independent numeric sequences?** Each graph already has independent positional labels. No database counter is needed for implicit add; stable external IDs need a separate supported mapping strategy. Do not assume bare IndexHNSWFlat supports arbitrary add_with_ids.
12. **Composite mapping?** Yes, stronger than `(libraryId, vectorId)`: `(library_id, generation_id, partition, vector_label) → holding/record ID + hash/model/dataset`. Base/delta and rebuilds can reuse labels.
13. **Globally unique book IDs?** Preserve globally stable public work and holding/private-record identifiers; one bibliographic work can have multiple library holdings. Do not expose FAISS labels as book IDs.
14. **One index per library practical?** Potentially with lazy loading, byte budgets and exact indexes for small sets. Expected scale is CANNOT VERIFY FROM CURRENT IMPLEMENTATION; benchmark real distribution before choosing thresholds or capacity promises.
15. **Shared global leakage?** Current unscoped global retrieval can mix libraries. Strict backend validation can prevent unauthorized output, but post-filtering may destroy recall and does not give isolated graph namespaces. Logs, caches, reranker and sources need the same controls.
16. **True metadata filtering?** Current caller uses plain `.search` and no metadata predicate. Modern FAISS offers HNSW search parameters with an ID selector; this is label-level selection, not automatic Mongo/library filtering, and version/mode behavior must be checked. Separate partitions are the recommended first design; nuanced evidence is in [22](22_PRIVATE_LIBRARY_HNSW_PLAN.md).
17. **Deletion?** Immediately deactivate scoped source/holding access, append a tombstone/override, then rebuild that library to compact graph nodes. Preserve active loans/history; library deletion disables access/jobs before retention-aware cleanup.
18. **Rebuild?** Acquire scoped writer lease, stream one library's authoritative published/staged records, construct immutable compatible mappings/graph, validate and publish atomically through the generation record, retaining rollback.
19. **Dataset replacement?** Explicit replace mode, immutable dataset version/checksum and staged diff; preserve stable holding IDs/loan counts, remove omitted searchable rows only on verified publication, and retain prior generation.
20. **Embedding model change?** Record model/fingerprint/dimension/text/chunk versions; rebuild compatible catalogue and affected QA indexes into new generations. Query with matching model; do not mix, pad or compare incompatible vectors.
21. **Build failure recovery?** Durable scoped job checkpoints/idempotency/retries, lease fencing, validated immutable bundles and DB-pointer reconciliation. Serve preceding generation; no partially published private namespace.
22. **Synchronous or background?** Bounded preview can be synchronous; parsing/import/embedding/index publication should be durable background jobs. Existing semantic sync worker supplies patterns, not a completed multi-library queue.
23. **Librarian progress?** Authorized job-status API with stages, processed/total, rejected/indexed counts, retryable error codes and generation; polling or scoped server events. Never fabricate a percentage without a known denominator.
24. **Visible when?** When records, rights, mapping, model and durable index validate and the authoritative generation is published. Earlier rows remain staging; an existing catalogue continues serving its previous generation.
25. **Switching caches?** Partition by owner/library/permissions/dataset/index/model and request inputs, abort requests, reject old epochs and clear pending selection. Never reuse old-library ranked IDs or citations under a new heading.
26. **Switching history?** Chat histories stay in separate library contexts, with explicit old-context labels and reauthorization. No cross-library evidence carryover by default.
27. **Existing chat tied to original?** Yes, immutable library identity; a new library starts/resumes another conversation. Confirmation and selected resources remain bound to the original context.
28. **Events scoped how?** library_id ownership, member feed and scoped staff CRUD; related holdings and user/session/library receipts checked. Platform notices use an explicit separate scope.
29. **Analytics scoped how?** Authorized library predicate on all facts and memberships, including immutable historical provenance. Platform totals separate; no reader-driven arbitrary library summary.
30. **Which isolation tests?** Two libraries with overlapping names/ISBNs and unique canaries; exercise every positive/negative API, raw candidates/mapping/reranker/prompt/sources, alternate tools/caches/history, revocation/switch races, failed/corrupt publication and restart. Exact scoped baseline measures recall separately from leakage; finite tests give bounded evidence.
31. **Research vs engineering?** IDs/memberships/ACLs/CRUD are necessary engineering. Empirical scoped ANN architecture tradeoffs, quality-preserving incremental recovery, and measured resource-bound QA grounding/abstention can support research if compared fairly with baselines and independent gold. Planned functionality earns no current experimental credit.

## Paper wording

Current safe wording: “The architecture is being extended toward institution-scoped catalogues in which participating libraries maintain independent datasets and retrieval indexes.” A completed multi-tenant intelligent-library claim requires the authorized upload→publish→query→QA chain, scoped events/analytics, recovery and independent isolation/quality/scalability experiments. The [claims ledger](17_CLAIMS_LEDGER.md) separates these future claims from verified mechanisms.
