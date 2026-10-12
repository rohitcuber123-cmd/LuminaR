# Library circulation and catalogue operations

## Catalogue and inventory

`CatalogPage/BookDetailPage` call `/books/` and `/books/{work_id}` through `frontend/src/lib/api.ts`; routes delegate to `book_service`. Browse is Mongo paging ordered by numeric `book_id`. Popular books rank imported reading-log/rating fields; new arrivals rank `created_at`, which can reflect import time rather than a physical arrival. Categories are cached in `book_categories`, not recomputed for each query. Staff book forms call protected create/update/delete routes; creates build a global work record, updates retain immutable work_id, and deletion refuses active issues or physical inventory.

Books and inventory are count-based, not Boolean availability. `books` contain `total_copies/available_copies`; `library_inventory` additionally keys `library_id/work_id` and has ISBN/shelf/source. `availability_service.get_availability_context:18–56` prefers matching physical inventory and otherwise uses catalogue counts, default `LIB001`. The fallback is valid for the current mixed global system but must be prohibited in future private holdings flows: lack of a holding must not confer borrowability from a global record.

## Borrow sequence

`BookDetailPage`/borrow controls → `issueBook` → POST `/issues/issue` → `issues.issue` → `issue_service.issue_book(user_id,work_id)` → get book/default-library availability → reserve/duplicate checks → guarded stock decrement → insert issue → reservation fulfillment/activity → response → browser `BORROW_STATE_CHANGED` refresh.

`issue_book:49–76` uses a process lock plus a five-minute Mongo lease keyed `user_id:work_id` to serialize duplicate issue creation across workers. `_issue_book:89–251` verifies global book presence, stock >0, pickup reservations and no existing ISSUED loan. Due date is UTC now plus 14 days. Physical inventory or global book stock is decremented only with `available_copies >0`. Record fields include numeric issue/user/book IDs, work/title snapshot, `inventory_source`, library_id, issued/due/returned timestamps, status and fine_amount.

The HTTP IssueRequest contains only `work_id` (`routes/issues.py:27–29`); user library selection is not propagated. Borrow lease/duplicate/reservation keys are global by work. Decrement and issue insertion are separate writes. If insertion fails after decrement, code inspected does not provide a multi-collection rollback transaction. Guarded decrement prevents negative stock from that operation, but is not complete atomic circulation.

## Return sequence

`BorrowedBookActions/ProfilePage` → `returnBook` → POST `/issues/return/{issue_id}` → `return_book:340–505` → verify issue ownership/status → calculate calendar overdue days → CAS update requiring ISSUED and same due_date → create fine/activity → restore original stock source → mark earliest reservation READY_FOR_PICKUP → notify → response/refetch.

CAS prevents two concurrent return updates from both succeeding, including conflict with changed due date. Side effects after it are not one transaction; failure can leave a RETURNED record with stock/fine/notification work unfinished. Persist an idempotent workflow/outbox or use supported Mongo transactions for future strengthening. Do not claim exactly-once completed circulation from CAS alone.

## Reservations

Detail page → POST `/reservations/` → `create_reservation:29–102` checks book, default-library availability, rejects available books, checks ACTIVE duplicate, stores user/book/work/title/timestamp/status. Cancellation verifies ownership and ACTIVE/READY_FOR_PICKUP, atomically sets CANCELLED. `mark_next_reservation_ready:232–279` chooses earliest reserved_at ACTIVE record and CAS transitions it to pickup, emits notice/activity. Borrow can mark the user's ready reservation FULFILLED. A queue exists; no timed pickup-expiry or library-specific queue was traced. Duplicate-check/insert races and same-work multi-library queues require tests and unique active keys.

## Fines and renewals

Return computes `overdue_days = now.date() - due_date.date()` only when late; amount is days × 5. `fine_service.FINE_PER_DAY=5` repeats the rate. Both are hard-coded; no maximum or configurable per-library fee policy exists. A late return within the same UTC calendar date yields zero calendar days, unlike elapsed 24-hour or per-started-day billing. Fine is persisted on return; `/fines/my` sums UNPAID records, not continuously accruing projected overdue debt.

`pay_fine:138–180` verifies owner and unpaid status and marks PAID/paid_at. It does not validate money received or integrate a gateway. Safe description: **fine settlement status management**. Actual financial payment is **IMPLEMENTED BUT INCOMPLETE**.

`loan_renewal_service.policy/renew_loan` supports enabled flag, configurable extension days (default 14) and maximum renewals (default one), rejects overdue/returned/maxed/reservation-blocked loans, uses expected_due_date and request_id for optimistic/idempotent behavior, records renewal details and reconciles reminders. Reader and assisted admin routes are separate. No independently configured library policy exists.

## History and saved lists

`ProfilePage` pulls `/issues/my`, `/reservations/my`, `/fines/my`, `/activity/my`, and search history. Issue history includes returns via status; reservations include cancellation/fulfillment; fines include settlement. `useLibraryStore` fetches issues/reservations/reading-list with session/request guards. It is not an institution membership store. `reading_list_service` has a unique `(user_id,work_id)` index and denormalized title/author/copy fields; metadata can be stale until reconciled. User-specific queries and record detail authorization are present, while staff all-record views are global.

## Research and future isolation

Circulation CRUD, queues, fees and renewal are engineering functionality. Their research value is supporting entitlement-aware book QA and meaningful recommendation signals. User benefit, reduced handling time and recommendation improvement require experiments.

For private libraries add immutable library_id/holding_id to loans, reservations, fines, renewal/activity/outbox records. Bind every mutation to authorized L and holding, remove global availability fallback, partition leases/queues and analytics, and retain original library context in historical records after switching. Bibliographic work IDs remain globally shareable while holding IDs distinguish copies owned by different institutions. Optional physical Copy records can follow later; current total/available counts already support a practical first version.
