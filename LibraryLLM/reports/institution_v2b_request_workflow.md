# Request workflows

| Trigger | Request state | Physical allocation | Loan |
|---|---|---|---|
| Member Request Book | BORROW PENDING | One unit held; copy HELD_FOR_REQUEST when verified | None; due date absent |
| Staff Approve & Issue | APPROVED, reviewer recorded | Same held unit converts; copy BORROWED | ACTIVE; borrowed/due dates start now |
| Staff reject / owner cancel / bounded expiry | REJECTED / CANCELLED / EXPIRED | Released once | None |
| Borrower becomes ineligible before approval | CANCELLED with reason | Released once | None |
| Book becomes non-circulating before approval | REJECTED with reason | Released once | None |
| Member Request Return | RETURN PENDING | Loan keeps its unit; copy BORROWED | Still ACTIVE and in Current Loans |
| Staff reject return | REJECTED | Unchanged | ACTIVE; re-request allowed |
| Staff Confirm Received | COMPLETED, reviewer recorded | Released once; copy AVAILABLE | RETURNED and in History |

Staff authority must be current in the same library. User actions cannot set reviewer, borrower or final physical status. Return confirmation is allowed for a historical loan even if its borrower lost membership. Request timestamps and received timestamps are distinct; the original return_requested_at survives rejection/re-request.

Renewal uses current policy, owning member, UUID loan, expected due date and idempotency key. Pending physical return blocks it. Reservation influence requires proven same-library UUID or an explicit alias; unknown/global reservations have no tenant authority.

All mutations are serialized and journaled. Repeated command keys return stored results; terminal-state commands with new keys cannot create a second allocation/release. Unknown commit returns503 and requires stopped-writer recovery. A normal busy gate uses Retry-After; UI Refresh/retry is safe with the original key. Browser testing observed a concurrent config read503 that recovered via Refresh.
