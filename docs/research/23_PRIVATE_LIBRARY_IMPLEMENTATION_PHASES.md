# Private-library implementation phases

**PROPOSED / FUTURE WORK — roadmap only.** No application implementation was changed. All source targets are relative to `LibraryLLM/`; symbol locations are indexed in [09](09_IMPLEMENTATION_CHEATSHEET.md) and [SOURCE_EVIDENCE_INDEX](SOURCE_EVIDENCE_INDEX.md). Dependencies are intentional: authorization and publication contracts precede private retrieval claims. Acceptance checks below are future requirements, not tests executed during this audit.

## Phase 0 — establish contracts and legacy migration boundary

**Dependencies:** none. **Complexity:** medium. **Benefit:** prevents incompatible tenant and inventory assumptions from spreading.

- Record immutable library/holding/dataset/generation identities and the public-vs-private metadata policy from [21](21_PRIVATE_LIBRARY_ARCHITECTURE.md).
- Inventory current database scope and legacy LIB001 records without assuming all historical ownership. Define orphan remediation, active-loan handling and count authority.
- Resolve current search hydration's global book counts vs library inventory counts, global full-text no-selection entitlement, and non-atomic book-index metadata publication as prerequisite correctness work.
- Decide append/merge/replace semantics, unknown-book creation, loan-safe deletion/retirement, supported formats/limits/rights, explicit route scope and publication source of truth.
- Save architecture decisions and a migration/backout plan before schema expansion.

**Targets:** backend/services/availability_service.py, issue_service.py, reservation_service.py, book_service.py; search/ranked_pages.py and luminar_search.py; rag/services/book_access.py and embed.py.

**Acceptance:** ownership/count fixtures enumerate known and ambiguous legacy cases; expected availability matches circulation; a disallowed full-text request fails before model generation; planned generation publication has one authoritative pointer. An initial private-library feature must not launch with an unscoped fallback.

## Phase 1 — library identity, membership and ownership authorization

**Dependencies:** 0. **Complexity:** medium–high. **Benefit:** real institution boundary and auditable role policy.

- Add Library and LibraryMembership collections/services with unique IDs and compound membership index.
- Seed legacy library and backfill only justified inventory/history ownership through resumable migrations.
- Implement LibraryContext using existing live JWT/current-user/revocation checks and membership status/permissions revision.
- Add owner-authorized institution registration/invitation/member management and account membership listing.
- Separate platform ADMIN from scoped OWNER/LIBRARIAN. Apply ownership checks to direct IDs and alternate admin/list/export paths.

**Targets:** backend/database/mongodb.py, backend/dependencies.py, backend/routes/auth.py and backend/routes/staff.py; backend/main.py; new scoped library/membership modules. Keep global user IDs/account signup intact.

**Acceptance:** user in A cannot read/write B despite knowing IDs or possessing global staff role; reader cannot self-promote; owner cannot transfer resources to another institution through body fields; suspended/revoked membership invalidates access; migration can resume/roll back without losing histories.

**Release gate:** no private data API is enabled before this negative authorization suite is complete.

## Phase 2 — holdings and durable circulation scope

**Dependencies:** 1. **Complexity:** high. **Benefit:** independent stock/queues and correct historical ownership.

- Formalize global public Work vs scoped Holding/private catalogue record. Add stable holding IDs, scoped source keys and dataset provenance.
- Require library+holding ownership in issue/reservation/return/renew/fine/assisted operations. Scope lease keys and reservation FIFO; preserve original scope on return.
- Remove private-scope fallback to global book stock. Derive available copies from authoritative holding/circulation policy with guarded updates.
- Make multi-step circulation operations idempotent/reconcilable; define transaction support or durable side-effect recovery.
- Scope history/activity/search/feedback/category queries and define personal global vs scoped reading-list saves.

**Targets:** backend/services/issue_service.py:49 issue_book, reservation_service.py:29 create_reservation, loan_renewal_service.py, fine_service.py, availability_service.py, activity/reading-list/book services and matching routers/models; inventory service/API/frontend contracts.

**Acceptance:** same work/ISBN in A and B has independent stock, reservation queue and return behavior; duplicate requests cannot overborrow or double-credit stock; A retirement retains active returns/history; users switching context cannot settle/access B's fines without entitlement; partial side-effect failure is detected/repaired.

**Scope control:** item-level barcode/copy tables are optional later if lending policies require them. Current count-based inventory is real; per-copy tracking should not delay the retrieval study unnecessarily.

## Phase 3 — versioned dataset preview/import and scoped durable jobs

**Dependencies:** 1 and holding identity from 2. **Complexity:** high. **Benefit:** real institution catalogue ingestion beyond matched inventory rows.

- Reuse existing CSV/XLSX validation/preview components, binding preview to uploader+library+expiry and validating ownership on confirm.
- Add immutable Dataset/version/checksum/import-mode records and durable IndexJob status/checkpoints/leases/idempotency.
- Create private records for valid unknown catalogue entries; clearly distinguish invalid/ambiguous/duplicate rows from accepted rows.
- Stage append/merge/replace changes with stable holdings and loan-safe inventory reconciliation.
- Add quotas, bounded storage/parsing, cancel/retry behavior, row error export and scoped progress APIs. Initial bounded preview can stay synchronous; indexing is asynchronous.

**Targets:** backend/services/inventory_import_service.py:510 confirm_inventory_import and parser/preview helpers, backend/routes/inventory.py; search/sync_queue.py (catalogue_mutation, MutationJournal, SyncQueue) for patterns; new datasets/jobs modules. Current inventory confirm's partial insert behavior is not a transactional replacement algorithm.

**Acceptance:** two identical uploads with one idempotency key produce one dataset/job; duplicate checksum handling is explicit; another librarian cannot confirm A's preview under B; unknown valid books are represented; crash retries do not duplicate holdings; unpublished rows are not searchable; progress counts sum to a defined denominator.

## Phase 4 — scoped index bundle and library registry

**Dependencies:** 1,3. **Complexity:** high. **Benefit:** candidate isolation and independent lifecycle.

- Refactor IndexManager inputs so catalogue reads, semantic cache, queue/journal and graph root carry authorized namespace/dataset generation.
- Add composite label mapping `(library,generation,partition,label)` to stable holding/record IDs.
- Build isolated library base/delta generations with manifests containing owner/model/hash/dimension/checksums and live coverage.
- Implement durable bundle-first, authoritative generation-pointer-last publication and recovery. Local active pointers become verified projections.
- Implement lazy registry acquire/release, per-entry load locks, pinned snapshots, byte-budgeted eviction and fail-closed unavailable states.
- Share compatible encoders/model locks; use bounded job workers and scoped writer leases/fencing. Add a small-library exact path after its threshold is measured.

**Targets:** search/index_manager.py:53 new_index, :82 Snapshot, :113 IndexManager, :293 _persist, :386 _batch_sync, :433 _full_rebuild; search/catalogue.py:49 current_books, search/sync_queue.py (catalogue_mutation), search/embedding_cache.py, search/maintenance.py; new registry/job/publication abstractions.

**Acceptance:** graphs/mappings contain only their library records; equal numeric labels in different libraries resolve correctly; pinned readers finish coherently during publication; wrong model/dimension/mapping rejects load; empty/missing/corrupt library never searches global data; restart recovers the published generation; stale writer cannot replace a newer publication; bounded memory avoids eviction of pinned readers.

**Design gate:** implement option A isolation first; registry option C adds exact small sets/lazy policy. Shared-index B remains an optional experiment with pinned-version selector validation, not a launch prerequisite.

## Phase 5 — scoped semantic search, caches and frontend library switching

**Dependencies:** 1,2,4. **Complexity:** medium–high. **Benefit:** end-to-end authorized discovery with correct physical inventory.

- Select the library registry handle before ANN; keep live authorization/generation predicates during hydration and lexical candidate merge.
- Propagate scope into ranking, paging/cache keys, histories, recommendation candidates/profiles and KG relationships.
- Add frontend membership picker, scoped deep links and route/store context. Introduce request epochs, aborts and late-response fences.
- Rehydrate library inventory counts; invalidate results on generation/permissions changes. Scope background preload and all alternate related-book/tool routes.

**Targets:** search/api.py:195 search, luminar_search.py:391 search, ranked_pages.py, lexical_store.py and optional lexical sync; recommendation/api.py/profiles and backend related/KG services; frontend/src/pages/SearchPage.tsx, lib/api.ts, lib/searchPaging.ts, account/navigation/book/recommendation components.

**Acceptance:** A-only canary never appears in B's raw candidates, reranker inputs, response, history or related-book results; same public work yields B's inventory; stale A request cannot render after switching to B; absent private index yields scoped error; exact authorized neighbors establish retrieval quality independently from leak count.

## Phase 6 — institution-scoped book/document RAG and assistant context

**Dependencies:** 1,4,5 and source entitlement policy from0. **Complexity:** high. **Benefit:** prevents private evidence and actions crossing institutions.

- Add LibraryDocument/holding rights mapping; require authorized `(library,holding,source revision,generation)` when opening full text and selecting chunks.
- Keep book/document FlatIP separate from catalogue HNSW; make source/index/metadata publication coherent and scoped.
- Enforce scope for selected and unselected QA; retain personal PDF owner/session/cache lifecycle independently.
- Bind assistant conversation, selected evidence packet, tool calls and confirmation IDs to original library and membership revision.
- On switch start/resume a separate library chat, reject old pending actions and suppress old-library sources. Add scope to internal provenance and telemetry without exposing private content in shared logs.

**Targets:** rag/api.py:191 ask, book_access.py:8 authorize_selection, book_assets.py, book_runtime.py, retriever.py, embed.py, qa.py; rag/services/private_documents.py, document_upload/private routes; assistant conversation store/tools/orchestrator and frontend LLMPage/AIChatWidget/useAssistantStore.

**Acceptance:** B prompt/reranker/chunks/citations never contain A canaries; direct A holding/document ID rejected; unselected QA cannot bypass borrowing/rights; personal PDF unavailable to another user/session; old chat stays in A and is reauthorized on resume; confirm action checks original owner/library/expiry; index replacement cannot combine old text with new mappings.

## Phase 7 — scoped events, notices and analytics

**Dependencies:** 1,2,5. **Complexity:** medium. **Benefit:** completes private operational boundaries beyond search.

- Add event ownership/related-holding checks; scope staff actions/feed/unseen receipt state to user+session+library.
- Preserve explicit platform notices as a separate authorized audience; scope due/reservation notices and delivery provenance.
- Scope dashboard aggregations and category/popularity caches; distinguish titles, copies, accounts and memberships.
- Add dataset/index health reporting. Instrument AI usage/event engagement only if needed, with defined denominators/access/retention.

**Targets:** backend events routers/service/schemas, event receipt state; notices/notifications/admin services and DueWorker; frontend StaffDashboard/event/notice stores/components and analytics APIs.

**Acceptance:** B librarian cannot edit/publish/delete A event, bind A holding or inspect A aggregates; switching replaces unseen badges; signed A receipt invalid in B; loan-derived notice preserves original ownership; dashboard totals match scoped ground-truth fixtures. Scheduled publish/expire remains separate optional work.

## Phase 8 — recovery, performance, isolation and research evidence

**Dependencies:** 3–7. **Complexity:** high, workload dependent. **Benefit:** measured reliability and defensible future paper claims.

- Create scoped reconciliation/rebuild/rollback utilities and content-safe observability.
- Exercise append/update/delete/replace/model upgrade and failure points with simultaneous queries, pinned readers, membership changes and stale writers.
- Compare isolated HNSW vs scoped FlatIP and registry policies; optionally investigate shared-selector/post-filter alternative with pinned FAISS behavior.
- Collect independent search judgments/source-span QA gold, separate development/test sets, lock versions/hardware/config/dataset hashes and run [12](12_EXPERIMENT_PLAN.md) protocols.
- Evaluate realistic 10/100/1,000/10,000-library scenarios only within hardware limits; report cold/warm latency, resident bytes, build/publication/recovery time, authorized quality and observed leak cases.

**Targets:** existing tests/semantic_* and selected-document/auth/event suites as patterns; new scoped integration/failure/workload fixtures; benchmarks/reports with reproducible manifests. Existing tests were inspected during this audit, not executed or extended.

**Acceptance:** documented attack matrix and workload results with repetitions/confidence intervals; deterministic artifact-to-run provenance; all missing/foreign mappings surfaced; finite-suite leak counts properly qualified; no current claim is upgraded solely because architecture documents exist.

## Phase 9 — controlled release and claim update

**Dependencies:** all required gates above. **Complexity:** medium. **Benefit:** reviewable operating boundaries and honest publication.

- Migrate a small representative institution set; monitor index coverage/cold loads/recovery and support scoped rollback.
- Document supported sizes/concurrency/formats/rights, actual deployment/storage topology, revocation policy and recovery operator procedure.
- Remove legacy implicit private fallback only after backfill validation. Require scoped routes from all clients/service tools.
- Update feature audit and claims ledger using implementation evidence plus actual independent experiments. Keep any unfinished event/analytics/scale variants marked future work.

**Acceptance:** authorized institution creation→upload→published search→entitled QA→circulation→events/analytics works with negative isolation and recovery evidence. Capacity claims match measured workloads. The proposed multi-tenant paper description becomes eligible only for the tested implemented scope.

## Work packages and prioritization

| Priority | Package | Relative effort | Why now | Blocking dependency |
|---|---|---|---|---|
| P0 | Current availability/entitlement/publication defects + independent gold | Medium–high | Improves the current paper and prevents extension of known gaps | None |
| P0 | Library/membership/ownership contracts | Medium–high | Everything private depends on authorization | Phase0 decisions |
| P1 | Scoped holdings/circulation + datasets/jobs | High | Gives private index authoritative input/physical semantics | Phase1 |
| P1 | Isolated registry and coherent publication | High | Central private retrieval contract | Datasets/jobs/model policy |
| P1 | Search/switching/QA/assistant source isolation | High | Completes user-visible retrieval chain | Registry+membership |
| P2 | Events/notices/analytics scope | Medium | Removes remaining operational leakage | Membership+history scope |
| P2 | Exact/HNSW threshold/cache/scaling experiments | High / hardware dependent | Optimizes using evidence rather than guessed scale | Correct end-to-end scoped path |
| P3 | Shared graph selector study, copy-level inventory, scheduled events | Variable | Optional additions; no current novelty credit | Independent justification/results |

Effort labels describe uncertainty/engineering scope, not promised calendar durations. A narrower current paper can proceed with Phase0 evaluation/correctness work while private-library phases remain future work. Avoid delaying independent relevance/QA evaluation until all institution features are built.

## Definition of done for the future claim

Identity and authorization, dataset ownership, scoped searchable records, compatible graph mappings, coherent publish/recovery, live inventory, source entitlement, scoped conversations/actions, event/analytics ownership and alternate APIs must all be demonstrated within a declared deployment/workload boundary. Quality baselines and independent labels remain necessary after engineering completion. A libraryId field, two graph files or an attractive library picker alone does not satisfy this definition.
