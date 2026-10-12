# Recommended Part 2B scope — planned only

Part 2A is complete. No implementation below has begun. Current inventory snapshots are not lending availability. Inspection of actual code shows why the next migration must cover the whole lending mutation, rather than add a UI filter.

## Current dependencies

| File/flow | Actual current behavior | Required Part 2B change |
|---|---|---|
| backend/services/availability_service.py | DEFAULT_LIBRARY_ID=`LIB001`; work-ID lookup in library_inventory, then global books fallback | Require authorized library UUID/local book UUID; canonical holding/copy availability; remove cross-tenant fallback for physical lending |
| backend/services/issue_service.py | issue_book defaults LIB001; loan stores work_id/book_id/source/library_id; conditional decrement in legacy physical inventory or global books precedes issue insert | Store canonical library/book/holding IDs, optional copy ID and global reference snapshot; same-tenant conditional allocation and durable idempotent loan write |
| backend/services/issue_service.py return_book | Returns to loan inventory_source and library_id, defaults missing fields to catalogue/LIB001; increments old source, then advances a work-ID reservation queue | Persist and use original canonical source; single-return receipt/CAS; release exactly one allocated unit/copy; prevent double increment |
| backend/services/loan_renewal_service.py | Optimistic due-date CAS + renewal receipts already exist; reservations are queried by work_id across readers | Keep renewal idempotency/policy, add library+local-book predicates and same-tenant staff/borrower authorization |
| backend/services/reservation_service.py | Work-ID availability/queue and notification source references | Define a compatible transition adapter so allocation cannot release a copy into another library's legacy queue; broader reservation migration remains explicitly separately approved |
| backend/routes/issues.py | POST /issues/issue, /issues/return/{issue_id}; global-role assisted operations | Add required current library context and centralized membership/loan ownership guards |
| backend/routes/renewals.py | GET /issues/{issue_id}/renewal, POST /issues/{issue_id}/renew, assisted staff endpoint | Reauthorize loan tenant and preserve receipts; do not infer authority from JWT ADMIN |
| backend/routes/inventory.py | Legacy inventory GET is public; mutations use global staff role | Protect/retire or explicitly restrict legacy reads for migrated inventory; keep rollback adapter until cutover completes |
| frontend/src/lib/api.ts; book detail/card, My Library, staff issue screens, LoanRenewalControl | Borrow actions and availability use shared work IDs/legacy APIs | Pass explicit selected UUID context; render canonical physical availability separately from global digital capabilities |
| Assistant library operation tools | Existing availability/actions target current legacy flows | Keep existing_qwen/routing; bind authorized selected-library arguments at tool boundary only after new lending endpoints pass gates |

## Recommended architecture

Continue **aggregate holding + optional copies** initially. Actual issue/return code allocates aggregate quantities and stores no historical copy ID. Forcing every quantity into a copy record would invent borrower/copy associations and lose an honest migration path. Where genuine copy/barcode records exist, allocate a known AVAILABLE copy with conditional state transition; otherwise allocate an aggregate unit and mark that loan's allocation mode explicitly. Materialize all future individually tracked acquisitions through controlled staff workflows. Resolve `UNVERIFIED` historical barcodes before treating them as circulating copies.

Make one canonical availability service own transitions. LibraryHolding total is physical stock; circulation availability must be derived/maintained consistently with active loans, reservations and unavailable copy states under the chosen allocation mode. The Part 2A snapshot needs a reconciled cutover baseline, not continuous dual writes from two masters. Prefer replica-set transactions across holding/copy/loan/receipt when deployed. On standalone Mongo retain durable serialization and an explicit recoverable journal; never expire a lease without fencing a stale writer. Separate tenant/profile lock granularity only after membership revocation and allocation ordering remain safe.

Collections involved: institution_library_books, institution_holdings, institution_copies, institution_library_aliases, sequences, audit, current issues/borrow_locks and their new receipt/journal/index schema; reservations/fines/notifications only through deliberate compatibility boundaries. Each loan requires UUID library/book/holding references and optional copy reference, while retaining legacy IDs and source attribution for traceability. Unique idempotency keys include tenant and actor/action identity. No actor or library authority comes from request body fields.

## Recommended migration order

1. Inventory all legacy sources and active/returned issues by library_id, inventory_source and work_id. Resolve explicit aliases and quarantine unmapped/missing/ambiguous loans; inspect reservations that can affect allocation. No default LIB001 assignment for missing evidence.
2. Stop lending writes during a rehearsed cutover window, back up exact involved collections, reconcile canonical stock versus legacy current quantities and active loans. Freeze the previously independent Part 2A snapshot.
3. Add canonical loan references/receipts/indexes additively in a dry run, then explicit apply; preserve historical IDs and counts. Do not assign invented copy IDs to old aggregate loans. Resolve known copy status through actual evidence/operator verification.
4. Implement/test canonical availability + borrow conditional allocation and durable idempotent loan creation, including compensation/recovery on unknown commit outcomes. Switch one library at a time behind a rollback boundary; never decrement global books for that library's physical loan.
5. Migrate return against the original canonical source, exactly-once increment/release; adapt reservation handoff enough to prevent cross-tenant allocation, with explicit scope approval for any wider reservation behavior.
6. Bind renewal eligibility/receipts and staff operations to the canonical loan's library; preserve existing due-date/renewal policy and notification idempotency.
7. Cut frontend physical availability and borrow/return/renew actions over to new endpoints; verify multi-membership switching, stale requests and membership removal.
8. Bind Assistant tool actions to authorized selected context after direct APIs pass. Reconcile stock/loans/copies after concurrency and failure injection; disable old mutation paths for migrated libraries. A rollback must restore a consistent source snapshot, never run both availability masters.

## Required race and regression checks

Two borrowers/last aggregate unit; two requests/last copy; duplicate borrow request; issue insert failure after decrement; stale writer/recovery; double return; return concurrent with another borrow; member removal/role change during mutation; same global work in two libraries; private outsider/global ADMIN without membership; old missing tenant loan; cross-tenant reservation blocks; renewed loan returned while stale renewal retries; exactly-once activity/notification/fine side effects. Preserve existing staff/auth, 40 renewal tests, reservation/fine checks, frontend actions and Assistant selected-context behavior. Never change Qwen, embeddings, global ranking or RAG algorithms for this cutover.

Fees, full reservation tenancy, Events, Notifications, RAG assets, private semantic vectors and recommendation/search overlays require their own explicit later scope. Part 2B recommendations here do not authorize their implementation.
