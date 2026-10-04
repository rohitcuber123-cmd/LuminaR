# Loan renewal audit — before edits

Existing source: backend/services/issue_service.py. issue_id is numeric/unique; user_id is canonical immutable owner; work_id/book_id identify catalogue work. issued_at, due_date and returned_at are UTC datetimes (Mongo driver reads naive UTC). status is ISSUED/RETURNED; issue includes inventory_source/catalogue or physical and library_id, title, fine_amount. No renewal fields or API exist. /issues/my and AssistantLoanTool USER_LOANS use the same active source; assistant mutating intents only BORROW_BOOK/RETURN_BOOK/RESERVE_BOOK, with explicit pending confirmation and a default-off mutation flag. Assistant renewal remains deferred.

Current policy: issue duration14days. Duplicate active borrowing of the same title is blocked; physical LIB001 inventory wins over catalogue inventory. Borrow uses per-owner/work Mongo lease and local creation lock, decrements availability; return restores the same inventory source and marks next ACTIVE reservation READY_FOR_PICKUP. Renewal must not move copies or fulfill a reservation.

Fines: return computes positive UTC calendar-day overdue duration at5currency-units/day, then create_fine persists one fine per issue. No accrued-fee reset or waiver API. Conservative V1 denies renewal after the actual due timestamp, so a renewal cannot erase accrued overdue duration. Existing fine records/fine_amount remain unchanged, including unusual manually seeded outstanding fees.

Reservations: ACTIVE/READY_FOR_PICKUP/FULFILLED/CANCELLED, canonical owner/work. Another reader ACTIVE or READY blocks renewal regardless of spare copies (explicit conservative queue policy); own reservations do not block. The ready transition is an actual successful conditional state write after copy return, so RESERVATION_AVAILABLE may be emitted from that transition, with no invented expiry.

Roles: owner self-circulation for all authenticated roles; current Admin alone has explicit assisted return. V1 adds analogous ADMIN-only assisted renewal. Librarian retains existing circulation visibility and self-renewal, without a new on-behalf permission.

Chosen V1 renewal configuration: LOAN_RENEWAL_ENABLED=1, LOAN_RENEWAL_DAYS=14 (matching the existing issue period), LOAN_MAX_RENEWALS=1. Period/max configurable centrally; overdue renewal is deliberately prohibited in V1 rather than exposing an unsafe fee-reset flag. Extension starts at current authoritative due_date. Existing renewal state defaults0; first renewal snapshots original_due_date. Required request UUID + expected_due_date protect retries and double-clicks even when configured max exceeds1.

Admin operation source is existing activity; add BOOK_RENEWED with canonical target, authenticated actor and immutable old/new due snapshots. Current email hydration/filter/pagination stay unchanged. No historical actor backfill.

Notifications: Mongo canonical user_id, unique type/loan/due-version key; worker immediate startup then60minutes, relevant ISSUED query, pre-insert source check. Current source-check/insert race will be closed by post-insert authoritative recheck plus shared reconciliation; startup sweeps unresolved system reminder batches to recover interrupted reconciliation. Resolution is separate from read; resolved system notices remain historical but excluded from unread/toast/current priority. Admin messages never reconciled by a loan mutation.

No manual Admin due-date endpoint exists; none will be added. Worker repairs externally changed due versions on its next scan. Borrow/return, inventory, fee and reservation source remain authoritative. Core Mongo is available; no multi-document transaction assumption (standalone compatible).

Baseline counts: {"users": 12, "issues": 38, "reservations": 11, "fines": 5, "activity": 88, "notifications": 0}.
Source hashes saved in loan_renewal_baseline.json before application edits.
