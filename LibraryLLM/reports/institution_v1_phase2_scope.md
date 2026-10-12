# Institution V1 tenant inventory and Part 2 recommendation

No Part 2 source or domain-record writes were made. Classification below distinguishes the current repository from its intended scope.

| Resource | Current source / collection | Current scope | Intended scope / required change |
|---|---|---|---|
| Accounts / passwords / verified emails / login sessions | users, email_verifications; identity_service, auth_service, login_sessions | GLOBAL identity; USER_SCOPED sessions | Keep global account IDs; separate library memberships |
| Library profiles / access security / memberships / invites / audit | institution_*; institution_service, institution_dependencies | LIBRARY_SCOPED; membership is LIBRARY_AND_USER_SCOPED | Implemented in Part 1 |
| Catalogue works, authors, subjects, descriptions | books; book_service; data_pipeline | GLOBAL | Keep canonical work_id and bibliographic metadata global |
| Dense vectors / FAISS HNSW / lexical store / embedding cache | search; data_pipeline/ai/faiss; catalogue indexes | GLOBAL | Keep one catalogue/vector corpus; add holdings filters only after overlay |
| Knowledge graph | knowledge_graph; backend/routes/knowledge_graph.py | GLOBAL bibliographic graph | Keep graph global; local holdings/permissions overlay if needed |
| Physical holdings and copies | library_inventory; inventory_service, inventory_import_service | Legacy library string + work_id; no canonical membership authorization | LIBRARY_SCOPED UUID holdings/copy inventory; resolve aliases before migration |
| Availability | availability_service; book_service; catalogue copy fields | Legacy LIB001 fallback + global books counts | LIBRARY_SCOPED holding/copy state; never infer tenant stock from global work counts |
| Loans / returns / renewals | issues; issue_service, loan_renewal_service; routes/issues, renewals | USER_SCOPED history; physical issues sometimes carry legacy library_id, catalogue fallback does not | LIBRARY_AND_USER_SCOPED; explicit UUID on every issue path, renewal and return authorization |
| Reservations / ready queue / expiry | reservations; reservation_service; routes/reservations | USER_SCOPED records + GLOBAL work queue | LIBRARY_AND_USER_SCOPED; queue uniqueness/order keyed library + work |
| Fees | fines; fine_service; routes/fines | USER_SCOPED with installation-wide staff views | LIBRARY_AND_USER_SCOPED; derive UUID from authoritative issue, tenant billing policy |
| Reading/borrowing history / activity | activity; activity_service; issue/reservation event writers | USER_SCOPED + legacy GLOBAL staff listing | Library source actions LIBRARY_AND_USER_SCOPED; personal aggregate remains across libraries |
| Reading lists | reading_list; reading_list_service | USER_SCOPED, unique user_id + work_id | Can remain personal/global-work list; local availability resolves selected library later |
| Search history / recommendation feedback | search_history_service; recommendation_feedbacks | USER_SCOPED | Can remain personal; optional library context stored with explicit purpose |
| Events / event receipts | events, event_user_state; event_service; routes/events | GLOBAL events, USER_SCOPED receipts; global staff roles | LIBRARY_SCOPED events + LIBRARY_AND_USER_SCOPED receipts; internal visibility uses tenant guard |
| Notifications / sent directory / due reminders | notifications; notification_service, notification_worker, loan_notification_service | USER_SCOPED delivery with GLOBAL admin audience | Library notifications LIBRARY_AND_USER_SCOPED, separate platform notices; source records supply UUID |
| Admin Operations / analytics | activity; admin_operation_service; routes/notifications admin endpoints | GLOBAL installation directory, summary and hydration | LIBRARY_SCOPED dashboards; library + user queries; explicitly separate platform operations |
| Catalogue ingestion / inventory uploads | book_service, inventory_import_service, data_pipeline | GLOBAL catalogue writes / legacy string inventory previews | Global ingestion requires separate platform authority; inventory uploads LIBRARY_SCOPED |
| Datasets | datasets files; search metadata/vector assets; rag source assets | GLOBAL machine/deployment assets | Keep public catalogue global; institution uploads LIBRARY_SCOPED with resource UUID and storage prefix |
| Search filters | search/api.py, luminar_search; availability decoration | GLOBAL retrieval with legacy availability decoration | Global retrieval retained; tenant-owned availability filter based on UUID holdings |
| Recommendation | recommendation_service, recommendation/api.py | GLOBAL works + USER_SCOPED behavior + legacy stock | Retain ranking; tenant availability overlay only when explicitly requested |
| Assistant tools and pending actions | assistant/tools.py, state.py, orchestrator | Global user identity and legacy circulation bindings | Bind library UUID in immutable action target, revalidate membership at confirmation/execution |
| Book RAG / reader authorization | book_capability_service, book_runtime, routes/books, rag/services/book_runtime | Global work assets; existing active-loan authorization | Preserve existing loan authorization; tenant-private assets require library guard + explicit work/asset scope |
| Private Document RAG / OCR / local cache | rag/services/private_documents.py, private_document_routes, private_document_ocr, local_document_cache | USER_SCOPED login-session documents and cached artifacts | Remain personal; introduce separate library-owned document mode later, never relabel all private uploads as institution data |
| Know More / Knowledge Tools | routes/know_more.py; rag/services/knowledge_* | Global borrowed work + USER_SCOPED/session private artifacts | Revalidate source access including tenant when library-owned sources exist; preserve current deterministic algorithms |
| Audit | institution_audit; legacy activity and security audit | LIBRARY_SCOPED new events; global/personal old events | Keep new immutable audit; integrate display only when tenant query discipline is ready |
| Background jobs | notification_worker, reservation expiry, event/analytics work | Installation/global scans | Explicit library UUID from source/job payload; no mutable global active library |

## Holding architecture comparison

| Option | Strength | Limitation for this repository |
|---|---|---|
| A: LibraryHolding(library_id, work_id, total_copies, available_copies) | Closest to existing aggregate inventory and atomic quantity updates; cheap stock queries | Cannot identify a physical item, barcode, lost copy or copy-level loan |
| B: LibraryCopy(copy_id, library_id, work_id, barcode, status) | Correct physical circulation identity and per-copy audit | Count queries and migration complexity; existing inventory lacks historical copy identifiers |
| C: Both | Holding provides aggregate/shelf/call-number/local-tag/acquisition overlay; copy provides accountable physical identity | Requires one authoritative write path and reconciliation of derived counters |

Recommendation: C. First migrate the current aggregate `library_inventory` into canonical holdings because circulation already depends on quantity decrements; add copy identity in that phase only for items with known barcodes. Generate clearly marked synthetic migration IDs for anonymous physical quantities if copy allocation is required, without pretending they are historical barcodes. Keep availability counters derived/reconciled from authoritative copy/reservation state as copy tracking is introduced. Digital/public catalogue access remains a separate permission model. Do not copy title/author/vector corpora per library.

## Dependency-aware Part 2 order

1. **Canonical alias mapping and holdings.** Explicitly map `LIB001` and every observed legacy inventory string to UUIDs; never assume a string belongs to the newly registered library. Add unique UUID + work_id holdings keys, library-copy/barcode uniqueness, typed library-required repository methods, and reversible dry-run migration. Reconcile global book copy fields before removing their availability fallback.
2. **Availability + atomic circulation together.** Replace default-library fallbacks in availability/issue services and borrower-facing book decoration. Require the requested UUID, current membership, holding/copy ownership, and capacity update in the same operation. Migrate issue rows, returns, renewals, borrow gates and copy identities; preserve history and audit. Test parallel borrowing and cross-library return/renewal IDOR.
3. **Reservations with circulation handoff.** Migrate library + work queues, ready-for-pickup transitions, cancellation, expiry and available-count interactions. Backfill from authoritative issue/inventory alias evidence or quarantine ambiguous rows. Test same work in two libraries, queue fairness, cancellation and expiry jobs.
4. **Fees.** Backfill UUID through the linked issue, isolate staff billing queries, local policy and fine payment updates. Preserve user-owned aggregate views across libraries. Test outsiders, dual-library borrowers, amounts and historical joins.
5. **Private assets and RAG access.** Introduce explicit library resource/asset ownership, storage/download query scope and cache keys; combine membership with source permissions. Test read, download, graph and Knowledge Tools artifacts and expiry after membership loss. Keep personal session documents and global public catalogue assets distinct.
6. **Events, notifications, admin analytics and background jobs.** Supply UUIDs in every producer, job, receipt and audience selector. Events/notifications are not changed by Part 1; make their follow-on migration an explicit approved phase.
7. **Assistant and recommendation/search overlays.** Bind selected tenant to confirmed actions and scoped availability. Preserve existing_qwen, frozen routing, retrieval and ranking; no model training is required by tenancy.

## Endpoint/frontend/test map

| Area | Affected API / frontend | Migration and security tests |
|---|---|---|
| Holdings | /inventory, inventory import/preview; StaffDashboard Inventory/Dataset import | alias map, UUID indexes, missing tenant fails closed, concurrent quantities, cross-library CRUD |
| Availability / loans | /books decoration, /issues, /renewals; BookDetailPage, ProfilePage, LoanRenewalControl, My Library | schema backfill, copy allocation, concurrent borrow/return/renew, memberships at execution |
| Reservations | /reservations and pickup queue; ProfilePage / StaffDashboard | per-library ordering, wrong-tenant IDs, expiry and next-ready transition |
| Fees | /fines; ProfilePage, StaffDashboard Fines | issue-derived tenant, local billing query, historical preservation |
| Assets / RAG | /books/{work}/read, /rag and Know More/knowledge artifacts; LLMPage/BookReaderPage | explicit library asset ownership, download IDOR, session cache keys, revoked membership |
| Events / notifications | /events, /staff/events, /notifications, /admin/*; event pages and AdminOperations | internal visibility, tenant receipt and audience, source-based job UUIDs |
| Assistant | assistant/actions and confirmation; AssistantTurn/AIChatWidget | immutable UUID binding, stale membership and switched context before confirm |

Future repository methods should require an explicit tenant parameter rather than accepting a default library. Jobs must carry UUIDs as data; a frontend switcher cannot scope a scheduled job. No query helper should infer authorization from a slug or caller-provided role.
