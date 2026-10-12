# Recommended Part 2C: tenant reservations and fees

Repository evidence supports Reservations + Fees as the next phase. backend/services/reservation_service.py creates global work_id reservations using global availability with no tenant ID. backend/services/fine_service.py deduplicates on integer issue_id and charges overdue_days × FINE_PER_DAY (currently5), with no tenant policy or library_id. backend/routes/fines.py exposes legacy account/global staff views. New Part2B UUID loans and separate requested/received timestamps now provide a canonical source, but the old schemas cannot safely charge these loans or allocate tenant queues.

## Proposed authorized scope for the next phase

1. Introduce tenant UUID reservation and charge records bound to canonical library_book_id and loan_id; current membership/staff admission and private list isolation.
2. Define queue order, eligibility, cancellation and expiry. Convert a reservation into exactly one BORROW request hold under the existing gate/journal; approval still means physical issue. Do not make reservation and borrow request own the same unit.
3. Version a fee policy and choose charge-stop rules for first return request, rejected/re-requested returns, verified physical hand-in and staff delay. Preserve existing borrowed/due/requested/received times and immutable policy provenance.
4. Make charges, adjustment, waiver and payment-record state changes idempotent and audited. Design real payment processing separately before integrating a provider. No speculative financial transactions.
5. Migrate only proven library/loan associations; retain unknown/global legacy records in legacy history. Provide read-only planning, per-library cutover, reconciliation and explicit stopped-writer recovery.
6. Extend My Library and tenant staff dashboards with scoped queues/charges. Add assistant adapters only after direct API validation, with immutable IDs and confirmation.
7. Test two libraries sharing a global work, last-unit queue conversion, reservation/renewal/return races, rejected return fee behavior, membership removal, staff authority loss and unknown acknowledgement across charge transitions.

## Boundaries and dependencies

Part2B source of availability remains authoritative. Existing proven same-tenant reservations can block renewal; reservations with unknown scope cannot. Fees remain on the accepted legacy formula until an approved tenant fee implementation exists. Part2B does not automatically create legacy fines for new canonical loans. Physical return still releases stock independently of charge policy.

Notifications may receive narrow deduplicated decision intents after the existing architecture is inspected. Full Events, Notifications or analytics tenancy, READY_FOR_PICKUP, kiosk/hardware scanning, global search availability filters, recommendation overlays and RAG/vector tenancy remain separate future work. Replica-set transactions are an operational option to benchmark, not a prerequisite silently introduced in Part2C. User approval is required before beginning the next phase.
