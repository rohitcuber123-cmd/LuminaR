# Part 2C post-implementation improvement review

These are scoped recommendations. NOW identifies safeguards already implemented in Part 2C; NEXT_PHASE/LATER are not implemented.

## Real payment integration

- TITLE: Real payment integration
- WHY IT MATTERS: Duplicate or misrouted settlement can corrupt tenant balances.
- CURRENT LIMITATION: Only manual desk records exist.
- RECOMMENDATION: Design tenant payment intents, immutable fee allocation, authenticated provider callbacks, provider event deduplication, settlement reconciliation and separate reversal entries before selecting a provider. Keep provider secrets server-side.
- PRIORITY: HIGH
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: YES

## Tenant Notifications

- TITLE: Tenant Notifications
- WHY IT MATTERS: Canonical queue members need correct-library delivery and privacy.
- CURRENT LIMITATION: Global user inbox, sender authority and source references have no canonical library scope.
- RECOMMENDATION: Make library ownership, current membership audience and source UUID explicit; add a durable tenant outbox before linking queue or fee events.
- PRIORITY: HIGH
- IMPLEMENT: NEXT_PHASE
- BREAKING CHANGE: YES
- MIGRATION REQUIRED: YES

## Email/push reservation alerts

- TITLE: Email/push reservation alerts
- WHY IT MATTERS: Members need timely action before a generated borrow hold expires.
- CURRENT LIMITATION: No Part 2C email/push or tenant delivery channel exists.
- RECOMMENDATION: After tenant notifications, add opt-in channels and delivery deduplication. Say ready for borrow approval, and name the library and hold deadline.
- PRIORITY: MEDIUM
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: YES

## Lost/damaged item charging

- TITLE: Lost/damaged item charging
- WHY IT MATTERS: Overdue and replacement responsibility have different evidence and appeals.
- CURRENT LIMITATION: Types are reserved; automatic damage/lost charge generation is absent.
- RECOMMENDATION: Add copy-specific incident evidence, reasoned staff assessment, versioned amount rules and dispute/reversal history; keep physical reconciliation separate.
- PRIORITY: HIGH
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: YES

## Copy-condition return notes

- TITLE: Copy-condition return notes
- WHY IT MATTERS: Condition evidence makes later assessments reviewable.
- CURRENT LIMITATION: Accepted condition flags exist but structured receipt notes are absent.
- RECOMMENDATION: Attach bounded observations and optional evidence references to a physical receipt; do not automatically create a financial charge.
- PRIORITY: MEDIUM
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: YES

## Member borrowing limits

- TITLE: Member borrowing limits
- WHY IT MATTERS: Institutions need consistent eligibility across direct and queue requests.
- CURRENT LIMITATION: Pending limit remains accepted installation configuration; active reservation cap is five.
- RECOMMENDATION: Version tenant active-loan and pending-request limits, and apply the same policy under the library gate at request, conversion and approval.
- PRIORITY: MEDIUM
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: YES

## Per-library loan duration

- TITLE: Per-library loan duration
- WHY IT MATTERS: Due dates should reflect institution product rules.
- CURRENT LIMITATION: Accepted Part 2B duration remains its existing configuration.
- RECOMMENDATION: Add immutable lending policy versions and issuance snapshots while preserving existing due dates.
- PRIORITY: MEDIUM
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: YES

## Per-library fine caps

- TITLE: Per-library fine caps
- WHY IT MATTERS: A deliberate cap can bound overdue liability consistently.
- CURRENT LIMITATION: Only integer safety bounds exist; no product fine cap.
- RECOMMENDATION: Add a versioned cap to the fee formula with explicit provenance; retain old snapshots and charged amounts.
- PRIORITY: MEDIUM
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: YES

## Grace periods

- TITLE: Grace periods
- WHY IT MATTERS: Small delays should follow a visible institution policy.
- CURRENT LIMITATION: Calendar-day semantics do not represent partial-day grace.
- RECOMMENDATION: Use the implemented 0–365 UTC calendar-day grace field and immutable versions; validate changes with the existing tests.
- PRIORITY: MEDIUM
- IMPLEMENT: NOW
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: NO

## Library holidays

- TITLE: Library holidays
- WHY IT MATTERS: A closed desk can make physical-receipt charging unfair.
- CURRENT LIMITATION: UTC calendar subtraction counts closed days.
- RECOMMENDATION: Add a versioned closure calendar and explicit charge-day rule; never rewrite historical fee snapshots silently.
- PRIORITY: MEDIUM
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: YES

## READY_FOR_PICKUP

- TITLE: READY_FOR_PICKUP
- WHY IT MATTERS: Approval and collection may later need separate physical stages.
- CURRENT LIMITATION: Accepted borrow approval/issue remains unchanged; pickup stage is intentionally absent.
- RECOMMENDATION: Define a separate audited allocation lifecycle, expiry and receipt before introducing pickup language or legacy pickup migration.
- PRIORITY: MEDIUM
- IMPLEMENT: LATER
- BREAKING CHANGE: YES
- MIGRATION REQUIRED: YES

## Barcode scanning

- TITLE: Barcode scanning
- WHY IT MATTERS: Desk throughput can improve without changing authority.
- CURRENT LIMITATION: Copy UUIDs exist; hardware scanning is absent.
- RECOMMENDATION: Map scanned identifiers to verified tenant copy UUIDs and reuse authorized circulation commands and idempotency.
- PRIORITY: LOW
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: YES

## QR workflows

- TITLE: QR workflows
- WHY IT MATTERS: Member/copy lookup must not turn printed codes into authority.
- CURRENT LIMITATION: No QR workflow is implemented.
- RECOMMENDATION: Use QR only for lookup or short-lived scoped action tokens; keep current account and staff checks authoritative.
- PRIORITY: LOW
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: YES

## Batch circulation

- TITLE: Batch circulation
- WHY IT MATTERS: Multiple returns should produce independent reviewable outcomes.
- CURRENT LIMITATION: Mutations are single-item operations.
- RECOMMENDATION: Use bounded batches with per-item UUID commands, receipts and failure reporting; reuse the same library gate and queue handoff.
- PRIORITY: LOW
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: NO

## Receipt printing

- TITLE: Receipt printing
- WHY IT MATTERS: Members need desk confirmation and staff need traceability.
- CURRENT LIMITATION: Internal receipt UUIDs exist; printing/PDF export is absent.
- RECOMMENDATION: Render a tenant-branded receipt from immutable ledger history with manual-record wording and original amount/paid/balance; avoid gateway claims.
- PRIORITY: LOW
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: NO

## Staff financial permission granularity

- TITLE: Staff financial permission granularity
- WHY IT MATTERS: Cash collection and financial corrections warrant distinct authority.
- CURRENT LIMITATION: Part 2C has a fixed ADMIN/LIBRARIAN matrix.
- RECOMMENDATION: Keep the implemented split now; later add explicit tenant capabilities and audited delegation instead of broadening global roles.
- PRIORITY: HIGH
- IMPLEMENT: NOW
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: NO

## Fee disputes

- TITLE: Fee disputes
- WHY IT MATTERS: Members need a review path without destroying charged history.
- CURRENT LIMITATION: No structured dispute lifecycle exists.
- RECOMMENDATION: Add own-fee dispute submission, reasoned staff resolution and separate adjustment entries; freeze settlement only by explicit policy.
- PRIORITY: MEDIUM
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: YES

## Refund/reversal

- TITLE: Refund/reversal
- WHY IT MATTERS: A correction after payment differs from a credit on unpaid balance.
- CURRENT LIMITATION: Credits cannot reduce current charges below recorded payment; provider refund flow is absent.
- RECOMMENDATION: Append separate payment reversal/refund records with actor, reason, original payment link and settlement state; never delete payment history.
- PRIORITY: HIGH
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: YES

## Branch/campus queues

- TITLE: Branch/campus queues
- WHY IT MATTERS: Location-specific stock should have predictable eligibility.
- CURRENT LIMITATION: The canonical queue scope is the institution, not a branch.
- RECOMMENDATION: Define branch holding ownership and transfer policy before adding branch queue keys; migrate without merging institution identities.
- PRIORITY: LOW
- IMPLEMENT: LATER
- BREAKING CHANGE: YES
- MIGRATION REQUIRED: YES

## Replica-set transactions

- TITLE: Replica-set transactions
- WHY IT MATTERS: Native atomic writes may reduce operator recovery complexity.
- CURRENT LIMITATION: Local Mongo is standalone; journal/gate is authoritative.
- RECOMMENDATION: After an explicit topology change, evaluate transaction-based commits while retaining idempotency, audit plans and offline reconciliation. Do not turn transactions on against the current standalone server.
- PRIORITY: MEDIUM
- IMPLEMENT: LATER
- BREAKING CHANGE: NO
- MIGRATION REQUIRED: YES
