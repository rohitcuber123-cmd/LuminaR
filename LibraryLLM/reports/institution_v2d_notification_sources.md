# Authoritative notification sources

| Committed canonical audit | Inbox type | Recipients | Destination |
|---|---|---|---|
| BORROW_REQUEST_CREATED | BORROW_REQUEST_CREATED | Exact library active staff | Staff circulation |
| BORROW_REQUEST_APPROVED | BORROW_REQUEST_APPROVED | Requesting patron | My Library |
| BORROW_REQUEST_REJECTED | BORROW_REQUEST_REJECTED | Requesting patron | My Library |
| RETURN_REQUEST_CREATED | RETURN_REQUEST_CREATED | Exact library active staff | Staff circulation, return tab |
| RETURN_CONFIRMED | RETURN_CONFIRMED | Returning patron | My Library |
| RESERVATION_CREATED | RESERVATION_CREATED | Reserving patron | Reservations |
| RESERVATION_CANCELLED | RESERVATION_CANCELLED | Reserving patron | Reservations |
| RESERVATION_EXPIRED | RESERVATION_EXPIRED | Reserving patron | Reservations |
| RESERVATION_CONVERTED_TO_BORROW_REQUEST | RESERVATION_READY | Queue-selected patron | Reservations |
| FEE_CREATED | FEE_ASSESSED | Fee owner | Fees |
| FEE_WAIVED | FEE_WAIVED | Fee owner | Fees |
| FEE_PAYMENT_RECORDED | PAYMENT_RECORDED | Fee owner | Fees |
| FEE_ADJUSTED | FEE_ADJUSTED | Fee owner | Fees |

Source UUID precedence is fee, reservation, lending request, then loan, using
canonical metadata already captured by the existing domain plan. Dedupe identity
is `LIBRARY:{library_uuid}:{immutable_audit_uuid}:{recipient_user_id}`. Reservation
readiness refers to the actual queue conversion audit, not arbitrary stock checks.
Return confirmation refers to staff's canonical physical-receipt command.

New global reminders explicitly use GLOBAL. New platform messages explicitly use
PLATFORM through the existing guarded sender. Existing unscoped ADMIN records are
safe platform/account compatibility history; unidentified SYSTEM reservation
references are marked ambiguous. No legacy work ID establishes library authority.
