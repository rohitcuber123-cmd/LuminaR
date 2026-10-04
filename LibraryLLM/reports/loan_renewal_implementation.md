# Circulation Phase 2: loan renewal and notification reconciliation

Completed 2026-10-03. PASS for this phase; the broader regression retains one permitted, pre-existing Book RAG failure. The audit and source baseline were saved before editing.

## A. Existing loan schema

Mongo issues have numeric issue_id, canonical user_id, book_id/work_id/title, issued_at, authoritative due_date, returned_at, ISSUED/RETURNED status, fine_amount and original inventory source/library_id. Borrow duration is 14 days. Return restores the same copy source and may advance the next reservation. No renewal API existed.

## B. Renewal policy

Central configuration: LOAN_RENEWAL_ENABLED=1, LOAN_RENEWAL_DAYS=14, LOAN_MAX_RENEWALS=1. Default period matches existing loans. Extension starts at current due_date. Days must be 1..365 and maximum 0..20; invalid configuration fails closed. These are technical bounds, not extra library policy. Backend eligibility requires an active own loan, valid count below maximum, non-overdue state and no conflicting reservation. UI uses backend eligibility and configured counts.

## C. Role permissions

Authenticated GENERAL_USER, LIBRARIAN and ADMIN can renew eligible own loans. Only ADMIN can assist another reader, matching existing assisted return. Routes revalidate current database identity/role; body owner/actor extras are rejected. No new Librarian cross-account permission.

## D. Renewal count/date model

Legacy missing renewal_count means zero. First renewal snapshots original_due_date. The atomic issue update saves current due_date/count, last_renewed_at, last_renewal_new_due_date and a UUID receipt with actor, old/new due, count and original time. No broad migration or historical actor backfill.

## E. Reservation rule

Another account's ACTIVE or READY_FOR_PICKUP reservation on the same work blocks renewal even with spare copies. This explicit conservative rule uses actual reservations. Own, cancelled and fulfilled reservations do not block. Structured RENEWAL_BLOCKED_BY_RESERVATION has friendly UI text.

## F. Overdue rule

V1 prohibits renewal after the actual UTC due timestamp. This is stricter than existing calendar-day fine accrual. There is no allow-overdue flag or fee reset.

## G. Fee interaction

Renewal never changes inventory, fine_amount or fine records. Return retains UTC overdue calendar days multiplied by INR 5. Return's conditional write also matches expected due_date so a concurrent renewal cannot commit a stale fee calculation; a losing return must refresh/retry.

## H. Atomicity

Mongo update_one matches issue_id, owner, active status, expected due_date and expected count (legacy missing count=0). State and receipt are saved together. Required UUID request_id plus expected_due_date protect lost responses and simultaneous requests. Receipt replay requires the same actor/original due; a different UUID with stale due cannot extend again, including when max=2. Frontend has immediate ref guard, pending disable and a retained UUID for same-version retry.

## I. Activity event

BOOK_RENEWED records canonical reader user_id, authenticated actor_user_id, issue/work/title, original occurrence time and immutable old/new due snapshots. Unique sparse event_key deduplicates retries. Existing integer activity allocation uses a process lock and bounded duplicate-ID retry. Denials create no success event.

## J. Actor/target handling and UI

Owner renewal actor=reader; assisted renewal actor=Admin, target=reader. Current-email hydration/filtering, drilldown and pagination remain. Admin Operations displays BOOK RENEWED with old/new dates and offers assisted Renew on active issue rows. Profile offers count/eligibility/Renew beside return controls and refreshes loans/activity/inbox after success.

## K. Notification reconciliation

The shared service matches only unresolved SYSTEM DUE_SOON/DUE_TODAY/OVERDUE. Renewal resolves the exact old due version; return resolves all outstanding loan reminders. Nothing is deleted. Worker catch-up handles external due changes and returned/missing sources. No manual Admin due-date API was invented.

## L. Resolved notification semantics

resolved_at/resolution_reason are separate from read_at. Resolution preserves read state, excludes stale warnings from badge/toasts, and shows subtle history after current notices. Server pagination stays bounded. Existing borrow-state events immediately refresh the inbox after return/renew; 45-second polling/focus refresh remain. Admin messages are never reconciled by loans.

## M. Worker races and indexes

Worker rechecks authoritative active status/current due before deduplicated insertion and again after insertion. If mutation wins first, postcheck resolves the late old notice; if insert wins, mutation resolves it. Thread barriers tested both orderings. Separate live worker pauses plus real Core renew/return APIs proved late inserts were created then resolved. Startup/interval sweeps recover interrupted reconciliation in indexed unresolved batches of 500.

Added notifications indexes: (source_ref.loan_id,resolved_at), (source,resolved_at,type), (user_id,resolved_at,created_at DESC,notification_id DESC). Added activity event_key unique sparse. Existing indexes stay. Explain used loan/resolved IXSCAN, examining one key/document for one result. Installed inventory: loan_renewal_indexes.json.

Actual ACTIVE to READY_FOR_PICKUP transition now emits one RESERVATION_AVAILABLE per reservation. No pickup expiry was invented. No broadcast/external delivery/WebSockets.

## N. Tests

New backend40 passed; notification/Admin48 passed (including final rerun); auth/staff76 passed; relevant broader regression385 passed,10 skipped,1 known RAG failure. Distinct backend passed549. Frontend targeted149 and routing/read-now31 passed; standard assistant81 overlaps targeted cases. Distinct frontend passed180. Build passed (main499.93 kB); lint0 errors/19 existing warnings. No new dependency. Exact counts/logs: loan_renewal_test_results.json.

## O. Live validation

Real API/worker checks covered renewal/retry/audit, read versus resolution, new-version reminders, old-version suppression, overdue return/fine, actual READY transition, and renewal/return races. Future notification generation used a scoped disposable fixture clock, not a production clock change. Browser normal login renewed Book B Oct5 to Oct19, count0/1 to1/1, disabled final button, badge4 to3, resolved history and unaffected Admin notice. Filtered Admin audit showed owner and assisted actor/target/date snapshots. Observed widths1440/1366/767/375 had no horizontal overflow. JSON and profile/Admin screenshots preserve evidence.

All disposable accounts/three works/loans/notices/events/reservations/fines were removed. Original users/circulation/inventory hashes and book count match. Final counts: users12/books5,000,000/issues38/reservations11/fines5/activity88/notifications0. Monotonic identity allocation and ordinary auth revocation metadata remain. Secondary Vite stopped; temporary tabs signed out/closed; viewport reset. Core restarted with startup/60-minute worker enabled; startup created0 in about4ms. No Qwen calls. All81 protected source hashes and KG SQLite hash/size match the baseline.

## P. Performance

Renew12.20ms, replay8.74ms. Five-sample medians: eligibility7.07ms, idempotent reconcile0.65ms, own loans22.32ms, Admin operations14.17ms. Worker final3.72ms versus prior phase7.20ms uses different fixtures, not a controlled speedup/capacity comparison. Live raced scans include deliberate synchronization. Updates use indexed loan/unresolved state; catch-up uses indexed unresolved system records. Full timings/plan: loan_renewal_performance.json.

## Q. Known limitations

Issue state/receipt is atomic; audit and notification writes are separate. UUID retry repairs side effects. Worker recovers stale notices after crashes; missing audit without client retry is not automatically rebuilt. A late insert can briefly appear before postcheck resolves it. Reservation lookup and issue CAS are not cross-collection transactional; a brand-new simultaneous reservation is not serialized. Existing borrow/return multi-document side effects and integer activity allocation are not redesigned. Assistant renewal is deferred until its pending-confirmation framework is extended. Book Detail renewal and reservation pickup expiry remain deferred. Known unrelated RAG failure is unchanged.

Exact files and start commands: [final acceptance](D:/SDC/LibraryLLM/reports/loan_renewal_final.md). Policy/security/reconciliation/performance JSON reports contain supporting detail. STOP after this phase; no subsequent feature started.
