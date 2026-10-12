# LuminaR Institutions Part 2C — completion

## A. FINAL PASS

Part 2C implementation, direct API and browser validation, migrations/recovery tooling and all 18 requested reports are complete. Production migration/cutover was not applied. Backend Part 2C: 59 passed; accepted V1/V2A/V2B: 56/95/57 passed. Frozen product suites: 1,300 passed, 10 existing skips. Frontend full chain: 270 passed; extended product UI: 156 passed. Build passes; lint has zero errors and 19 existing warnings. Both owned live fixture databases were removed and owned services stopped. Stop after Part 2C.

Preservation inspection found production institution_libraries changed from zero to one: the V1 library TEST was registered at 2026-10-08 21:16:39 UTC, after the baseline. Its registration source is not inferred; it was preserved. Catalogue, legacy inventory/issues/reservations/fines and canonical inventory/lending counts remain equal to baseline; every production Part 2C collection remains empty. See preservation.json for this explicitly recorded difference.

## B. OLD RESERVATION ARCHITECTURE

Global work_id + user queue and legacy stock/pickup assumptions in reservation_service.py; no canonical institution/local-book scope. Retained only as legacy history/explicit legacy mode.

## C. NEW TENANT RESERVATION ARCHITECTURE

Explicit library UUID/local book UUID queue; current member eligibility; shared durable gate and Part 2B journal. Optional global work links remain metadata. Local-only books work normally.

## D. RESERVATION MODEL

reservation_id, library_id, library_book_id, user_id, queue_sequence, requested_at, expires_at, lending_request_id, loan_id and lifecycle timestamps/provenance. States WAITING, CONVERTED, FULFILLED, CANCELLED, EXPIRED. Eligibility/conversion occurs inside one journal plan instead of persistent intermediate holds.

## E. QUEUE ORDERING

FIFO by persistent per-book monotonic sequence. Counter and reservation write share the gate/journal; never count+1. Unique library/book/sequence index. History gaps remain and timestamps are display metadata.

## F. RESERVATION ELIGIBILITY

Active verified account, ACTIVE membership, active/circulating local book/holding, unavailable stock or an existing strict FIFO head blocking immediate requests, no duplicate same-book active loan/pending request/reservation, maximum five WAITING+CONVERTED per member/library. Invalid accounts/members cancel before conversion; a temporary pending-request limit blocks the head without reordering.

## G. QUEUE → BORROW REQUEST CONVERSION

Deterministic UUID5 borrow request linked to one reservation; PENDING borrow owns exactly one aggregate allocation or verified HELD_FOR_REQUEST copy. Staff approval continues unchanged; one reservation cannot create two requests.

## H. STOCK FAIRNESS

Queue processing projects physical release, stock increase, copy restoration or request terminal effects under the same durable library gate. Queue gets the first opportunity before direct requestability. WAITING changes no physical stock arithmetic; only generated Part 2B requests hold units.

## I. CANCELLATION / EXPIRY

Members cancel own WAITING rows. After conversion they cancel the borrow request. Approval → FULFILLED; request rejection/cancel → CANCELLED; hold timeout → EXPIRED. No reinsertion. WAITING has no default timeout; an explicit expires_at is lazily enforced.

## J. RENEWAL INTERACTION

Another eligible WAITING borrower on the same library/local book blocks accepted renewal. Other-library queues do not. Legacy renewal checks remain only before Part 2C authority.

## K. OLD FEE ARCHITECTURE

Global integer issue_id and installation FINE_PER_DAY=5 with INR text; no canonical library/loan UUID or policy snapshot. Original legacy records are retained.

## L. NEW FEE ARCHITECTURE

Canonical loan/library UUID charge, immutable versioned policy at issuance, final physical-return calculation and append-only financial ledger. Final return and queue handoff share one operation; unpaid amounts never block return.

## M. FEE MODEL

fee_id/library_id/loan_id/library_book_id/user_id, type/status/currency, immutable original amount, current/paid/balance minor units, policy ID/snapshot, calculation, source event and timestamps. Only OVERDUE is created; other fee types and CANCELLED enum are future foundations, not implemented workflows.

## N. FEE POLICY VERSIONING

Initial INR 500 minor units/day, zero grace, physical receipt, UTC calendar day. Tenant ADMIN/OWNER creates a new immutable complete version. Loans snapshot at issuance; pre-cutover loans snapshot at activation; renewal keeps provenance. Existing fees and rates remain unchanged after later versions.

## O. RETURN-TIMESTAMP POLICY

Default PHYSICAL_RECEIPT; optional FIRST_VALID_RETURN_REQUEST uses only the request ultimately confirmed by staff. Original first-request metadata, completed request time and physical receipt are retained separately. Rejected/fake requests never stop accrual. See return_fee_semantics.md.

## P. OVERDUE CALCULATION

max(0, UTC stop date − UTC due date − grace days) × integer daily rate. Preserve the actual legacy calendar rule; crossing midnight can charge before a full 24 hours elapses. Active amounts are ESTIMATED/nonpayable. Zero charge creates no fee.

## Q. ADJUSTMENT / WAIVER

ADMIN/OWNER only; reason required. Append CHARGE/CREDIT or WAIVER; original amount/calculation remain immutable. Waiver zeroes remaining unpaid balance and retains prior payments. Credits cannot reduce current charge below already paid money.

## R. PAYMENT-RECORD FOUNDATION

LIBRARIAN/ADMIN/OWNER may record CASH/EXTERNAL/OTHER desk payments with UUID receipt, reference/note, actor, time and idempotency key. Supports partial/full payment, rejects overpayment, marks MANUAL_RECORD_ONLY. No provider processing or real money attempt occurred.

## S. USER RESERVATION UX

Inventory Join Waitlist confirmation, own Position N of M, own cancellation, converted request link and My Library reservation history. Library switches clear dialog/data and late old responses are discarded.

## T. STAFF RESERVATION UX

Circulation Reservations with default WAITING view, status/title/accession filters, member identity, queue position, date, availability and converted status; pagination. No arbitrary reordering.

## U. USER FEE UX

My Library fees scoped to active institution, separate estimated amounts, original/current/paid/balance, date/policy breakdown and immutable detail history. Payment is handled at the library; no online checkout.

## V. STAFF FEE UX

Tenant fees with status/type/date/name/email/book/accession/fee/loan filtering, paginated results, immutable details, desk payment modal, admin adjustment/waiver reason and policy version form. Librarian controls reflect limited financial authority.

## W. TENANT AUTHORIZATION

Current verified account + ACTIVE membership after the shared gate; role comes from tenant membership. Own-member views prevent IDOR. Cross-library UUIDs, private outsiders and unaffiliated global ADMIN are denied. Strict request schemas reject caller library/user/policy/paid-amount spoofing. Removed/demoted staff and disabled stale accounts cannot record payment.

## X. IDEMPOTENCY

Persistent library/actor/key receipt and payload fingerprint. Same request returns identical result; changed payload/type returns 409. Stable generated fee/request/import UUIDs and unique indexes prevent duplicate charge/hold/ledger entries. See idempotency.json.

## Y. OPERATION RECOVERY

Standalone Mongo w=1,j=True durable PREPARED plan; absolute effect replay. Uncertain acknowledgment reports 503 RECOVERY_REQUIRED and retains the gate. Offline recover requires all writers stopped and a proven cutover/gate, then reconciles all Part 2B/2C invariants before clearing it. Eight injected partial return plans replay to one fee and one next hold.

## Z. LEGACY RESERVATION MIGRATION

Dry run first; verified tenant alias + unique local work mapping + reliable borrower/date. Sort reserved_at then old ID; retain canonical counter history. Ambiguous/no-tenant, pickup allocation, duplicates and active loan/hold conflicts quarantine. Legacy records are never modified.

## AA. LEGACY FEE MIGRATION

Verified alias + unique migrated issue→loan + borrower proof. Missing library_id in real legacy fines can be proven by globally unique migrated issue identity. Preserve original Decimal-safe INR amount and paid history; ambiguous/duplicate charges quarantine. Deterministic IDs and receipt retries make apply repeatable.

## AB. CUTOVER / ROLLBACK

Per-library institution_v2c_config tracks reservation_mode/fee_mode/state. Mapped history must migrate and reconcile before admin activation; legacy mutations then cannot compete. Explicit offline rollback permitted only before canonical queue/fee/new-loan usage. After usage, recover forward. No production cutover was performed.

## AC. RECONCILIATION

Read-only circulation arithmetic, local identity, active pair/sequence/counter, all conversion/terminal links, issuance policy/fee snapshot/currency, loan borrower/book, immutable ledger/status/overpayment and proven legacy charge mappings. Corruption tests demonstrate detection without writes. Both API and browser fixture libraries passed inspection before deletion.

## AD. ASSISTANT ADAPTERS

Direct APIs first. Explicit reserve/cancel adapters carry immutable library/book/reservation UUIDs and key, five-minute TTL, existing write flag and confirmation. Reads own scoped fees/reservations; only explicit LEGACY mode retains legacy envelope. No financial staff tool. existing_qwen/selected context/retrieval unchanged.

## AE. LIVE VALIDATION

All A–K scenarios passed through real HTTP/JWT disposable accounts and two libraries. Synthetic overdue/request dates are labeled. Browser verified 15 member/admin interactions including confirmed waitlist join/cancel, library switching, versioning, manual payment/adjustment/waiver history. Queue and fee geometry checked at 1440, 1366, 1024, 767 (768 target Windows rounding), 390 and 360 CSS widths; no horizontal overflow. Owned fixtures/services cleaned, production mutations zero.

## AF. RACE TESTS

Concurrent sequence/duplicate requests; direct borrow versus returned queue unit; cancel versus stock/conversion; membership removal versus conversion; renewal versus reserve; return versus generation; two fee generators; payment retry versus waiver/adjustment; adjustment versus waiver. Shared tenant gate produces coherent results. Fault tests cover eight partial journal cutpoints.

## AG. PERFORMANCE

Actual local Windows/standalone Mongo disposable-fixture timings; nearest-rank p90. New fee creation is measured together with physical receipt/stock release; queue conversion with stock increase. Pure fee calculation is separate. Idempotent generation timings reconcile an existing fee. No capacity/production-scale claim.

| Operation | n | Median ms | p90 ms |
|---|---:|---:|---:|
| reservation_create | 32 | 68.513 | 89.425 |
| queue_read | 21 | 95.463 | 117.921 |
| return_confirmation_combined | 19 | 65.862 | 75.336 |
| reservation_cancel | 13 | 62.656 | 74.015 |
| staff_fee_list | 17 | 55.353 | 72.974 |
| fee_waive | 7 | 62.497 | 71.434 |
| payment_record | 8 | 64.835 | 94.413 |
| queue_conversion_with_stock_increase | 12 | 86.153 | 105.483 |
| fee_calculation_pure | 12 | 0.027 | 0.033 |
| fee_creation_with_physical_return | 12 | 64.643 | 74.366 |
| fee_generation_idempotent | 12 | 50.374 | 52.302 |
| own_fee_list | 12 | 46.521 | 54.343 |
| staff_reservation_list | 12 | 242.165 | 272.039 |

## AH. BACKEND TESTS

Part 2C 59 passed with real standalone Mongo and isolated databases. Includes privacy, money/policy spoofing, membership/authority freshness, migrations, copies, ledger concurrency, assistant scope and corruption/recovery. Deprecation warning is existing.

## AI. FRONTEND TESTS

Full configured chain 270 passed (including 17 new reservation/fee tests). Extended notifications/events/renewal/staff/search/document/KG/mind-map/RAG UI 156 passed. Library switching and stale response cancellation, role visibility, exact decimal conversion and stable payment keys are covered.

## AJ. REGRESSION

V1 56, V2A 95, V2B 57 passed. Ten frozen product groups execute 1,310 tests: 1,300 pass and 10 existing security skips. Auth, inventory, borrowing/returns/renewal, legacy reservations/fines/activity, Events/Notifications, Search/Recommendation/KG, Book/Document RAG/Know More/Knowledge Tools, production assistant/selected context and UI exercised. Old Events test constants only are time-aligned. Router V1–V5 research excluded.

## AK. BUILD / LINT

TypeScript/Vite build passes. Lint zero errors, 19 existing warnings at unchanged source locations. Existing Vite large-chunk warning retained.

## AL. EXACT FILES CHANGED / ADDED

Relative to the captured pre-Part-2C baseline: 15 existing integration files changed and 24 new source/test/script files added. Existing accepted dirty workspace files outside this list are preserved. SHA256 evidence in manifest.json and preservation.json.

Changed:

- [assistant/orchestrator.py](D:/SDC/LibraryLLM/assistant/orchestrator.py)
- [assistant/schemas.py](D:/SDC/LibraryLLM/assistant/schemas.py)
- [assistant/tools.py](D:/SDC/LibraryLLM/assistant/tools.py)
- [backend/main.py](D:/SDC/LibraryLLM/backend/main.py)
- [backend/services/fine_service.py](D:/SDC/LibraryLLM/backend/services/fine_service.py)
- [backend/services/library_lending_journal.py](D:/SDC/LibraryLLM/backend/services/library_lending_journal.py)
- [backend/services/library_lending_service.py](D:/SDC/LibraryLLM/backend/services/library_lending_service.py)
- [backend/services/reservation_service.py](D:/SDC/LibraryLLM/backend/services/reservation_service.py)
- [frontend/package.json](D:/SDC/LibraryLLM/frontend/package.json)
- [frontend/src/App.tsx](D:/SDC/LibraryLLM/frontend/src/App.tsx)
- [frontend/src/components/LibrarySwitcher.tsx](D:/SDC/LibraryLLM/frontend/src/components/LibrarySwitcher.tsx)
- [frontend/src/components/assistant/AssistantTurn.tsx](D:/SDC/LibraryLLM/frontend/src/components/assistant/AssistantTurn.tsx)
- [frontend/src/lib/assistantTypes.ts](D:/SDC/LibraryLLM/frontend/src/lib/assistantTypes.ts)
- [frontend/src/pages/LibraryCirculation.tsx](D:/SDC/LibraryLLM/frontend/src/pages/LibraryCirculation.tsx)
- [frontend/src/pages/LibraryInventory.tsx](D:/SDC/LibraryLLM/frontend/src/pages/LibraryInventory.tsx)

Added:

- [assistant/reservation_boundary.py](D:/SDC/LibraryLLM/assistant/reservation_boundary.py)
- [backend/routes/library_reservations_fees.py](D:/SDC/LibraryLLM/backend/routes/library_reservations_fees.py)
- [backend/schemas/library_reservations_fees.py](D:/SDC/LibraryLLM/backend/schemas/library_reservations_fees.py)
- [backend/services/library_reservation_service.py](D:/SDC/LibraryLLM/backend/services/library_reservation_service.py)
- [backend/services/library_fee_service.py](D:/SDC/LibraryLLM/backend/services/library_fee_service.py)
- [backend/services/library_v2c_plan.py](D:/SDC/LibraryLLM/backend/services/library_v2c_plan.py)
- [backend/services/library_v2c_legacy.py](D:/SDC/LibraryLLM/backend/services/library_v2c_legacy.py)
- [backend/services/library_v2c_integrity.py](D:/SDC/LibraryLLM/backend/services/library_v2c_integrity.py)
- [frontend/src/lib/libraryReservationsFees.ts](D:/SDC/LibraryLLM/frontend/src/lib/libraryReservationsFees.ts)
- [frontend/src/pages/LibraryReservationsFees.tsx](D:/SDC/LibraryLLM/frontend/src/pages/LibraryReservationsFees.tsx)
- [frontend/tests/institution-reservations-fees.test.tsx](D:/SDC/LibraryLLM/frontend/tests/institution-reservations-fees.test.tsx)
- [tests/institution_v2c/conftest.py](D:/SDC/LibraryLLM/tests/institution_v2c/conftest.py)
- [tests/institution_v2c/test_reservations_fees.py](D:/SDC/LibraryLLM/tests/institution_v2c/test_reservations_fees.py)
- [tests/institution_v2c/test_migration_edges.py](D:/SDC/LibraryLLM/tests/institution_v2c/test_migration_edges.py)
- [tests/institution_v2c/test_concurrency_edges.py](D:/SDC/LibraryLLM/tests/institution_v2c/test_concurrency_edges.py)
- [tests/institution_v2c/test_assistant_boundary.py](D:/SDC/LibraryLLM/tests/institution_v2c/test_assistant_boundary.py)
- [scripts/institution_v2c_migration.py](D:/SDC/LibraryLLM/scripts/institution_v2c_migration.py)
- [scripts/institution_v2c_operations.py](D:/SDC/LibraryLLM/scripts/institution_v2c_operations.py)
- [scripts/migrate_reservations_v2c.py](D:/SDC/LibraryLLM/scripts/migrate_reservations_v2c.py)
- [scripts/migrate_fees_v2c.py](D:/SDC/LibraryLLM/scripts/migrate_fees_v2c.py)
- [scripts/reconcile_institution_v2c.py](D:/SDC/LibraryLLM/scripts/reconcile_institution_v2c.py)
- [scripts/check_institution_v2c_live.py](D:/SDC/LibraryLLM/scripts/check_institution_v2c_live.py)
- [scripts/test_institution_v2c_regressions.py](D:/SDC/LibraryLLM/scripts/test_institution_v2c_regressions.py)
- [scripts/report_institution_v2c.py](D:/SDC/LibraryLLM/scripts/report_institution_v2c.py)

## AM. COLLECTIONS / INDEXES

Six new institution-prefixed collections: reservations (unique reservation UUID; unique library/book/sequence; FIFO lookup; partial WAITING library/book/user uniqueness; library/user/status), reservation_counters (unique library/book), fees (unique fee UUID; unique library/loan/type; tenant status/date and user/status), fee_ledger (unique entry UUID; library/fee/date), fee_policies (unique policy UUID; unique library/version; tenant/user/status generic lookup), v2c_config (unique library UUID). Accepted Part 2B journal uniqueness, loans/requests/copies/holdings, persistent locks and audits are reused.

## AN. MIGRATION / RECOVERY SCRIPTS

migrate_reservations_v2c.py, migrate_fees_v2c.py, reconcile_institution_v2c.py; shared institution_v2c_migration.py and institution_v2c_operations.py. Also check_institution_v2c_live.py, test_institution_v2c_regressions.py and report_institution_v2c.py for reproducible verification. Defaults are read-only for migration/recovery/rollback.

## AO. REPORTS CREATED

All 18 requested artifacts:

- [reports/institution_v2c_baseline.json](D:/SDC/LibraryLLM/reports/institution_v2c_baseline.json)
- [reports/institution_v2c_architecture.md](D:/SDC/LibraryLLM/reports/institution_v2c_architecture.md)
- [reports/institution_v2c_reservations.json](D:/SDC/LibraryLLM/reports/institution_v2c_reservations.json)
- [reports/institution_v2c_queue_conversion.json](D:/SDC/LibraryLLM/reports/institution_v2c_queue_conversion.json)
- [reports/institution_v2c_fee_policy.md](D:/SDC/LibraryLLM/reports/institution_v2c_fee_policy.md)
- [reports/institution_v2c_fees.json](D:/SDC/LibraryLLM/reports/institution_v2c_fees.json)
- [reports/institution_v2c_return_fee_semantics.md](D:/SDC/LibraryLLM/reports/institution_v2c_return_fee_semantics.md)
- [reports/institution_v2c_payments.json](D:/SDC/LibraryLLM/reports/institution_v2c_payments.json)
- [reports/institution_v2c_idempotency.json](D:/SDC/LibraryLLM/reports/institution_v2c_idempotency.json)
- [reports/institution_v2c_migration.json](D:/SDC/LibraryLLM/reports/institution_v2c_migration.json)
- [reports/institution_v2c_reconciliation.json](D:/SDC/LibraryLLM/reports/institution_v2c_reconciliation.json)
- [reports/institution_v2c_security.json](D:/SDC/LibraryLLM/reports/institution_v2c_security.json)
- [reports/institution_v2c_assistant.json](D:/SDC/LibraryLLM/reports/institution_v2c_assistant.json)
- [reports/institution_v2c_performance.json](D:/SDC/LibraryLLM/reports/institution_v2c_performance.json)
- [reports/institution_v2c_live.json](D:/SDC/LibraryLLM/reports/institution_v2c_live.json)
- [reports/institution_v2c_regression.json](D:/SDC/LibraryLLM/reports/institution_v2c_regression.json)
- [reports/institution_v2c_improvement_review.md](D:/SDC/LibraryLLM/reports/institution_v2c_improvement_review.md)
- [reports/institution_v2c_next_scope.md](D:/SDC/LibraryLLM/reports/institution_v2c_next_scope.md)

Additional verification/manifest/preservation/completion/commands, browser live/geometry/reconciliation/cleanup, isolated API cleanup, screenshots, JUnit and command logs accompany them.

## AP. KNOWN LIMITATIONS

INR only; UTC calendar days (not institution-local/holiday calendar); no fine product cap; fixed five-active reservation policy; installation-level accepted pending/loan rules; no automatic WAITING expiry/periodic tenant worker. General lazy queue maintenance visits at most 50 waiting book identities per request; specific-book access and stock/return events still process that book. Large queue/library capacity was not benchmarked. Standalone journal recovery needs an operator to stop writers. Ambiguous legacy/pickup rows require physical/operator review. No production migration or provider payment was performed. Existing test skips/lint/bundle warnings are recorded.

## AQ. IMPROVEMENT REVIEW

improvement_review.md covers all 20 required topics with title, why, limitation, recommendation, priority, timing, breaking-change and migration fields. It identifies implemented grace/financial authority and defers subsequent work.

## AR. REAL PAYMENT RECOMMENDATION

Design tenant payment intents, authenticated/deduplicated callbacks, immutable settlement allocation and provider reconciliation/reversal boundaries before provider selection. Current desk receipts remain manual records. No provider integration is included.

## AS. LOST / DAMAGED WORKFLOW RECOMMENDATION

Add copy-specific receipt/incident evidence, versioned assessment rules, reasoned staff authorization, disputes and separate charge/reversal history in a future approved phase. Condition flags alone must not automatically charge members.

## AT. NOTIFICATION RECOMMENDATION

Build canonical tenant audience/source ownership and a durable outbox before delivery channels. Alerts should name library/local book and generated borrow-request deadline; pickup wording is deferred.

## AU. NEXT PHASE RECOMMENDATION

Events + Notifications tenancy, based on actual global-role event routes, global event/seen IDs, user-only notification queries and legacy issue/work reminders. Detailed source evidence is in next_scope.md. No next-phase implementation was started.

## AV. DEFERRED ITEMS

Real payment/refund providers, Events/Notifications/analytics tenancy, lost/damage charging, pickup workflow, barcode/QR hardware, digital asset/private semantic tenancy, Search availability filters and Recommendation overlays. Stop after Part 2C and wait for explicit approval.

## AW. EXACT RUN / MIGRATION COMMANDS

All commands below are run from `D:\SDC\LibraryLLM` in PowerShell. MongoDB must already be running. The test/live tools use their own named disposable databases; they do not migrate production.

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
.venv\Scripts\python.exe -m pytest tests/institution_v2c -q --junitxml=reports/institution_v2c_backend.xml
.venv\Scripts\python.exe -m pytest tests/institution_v1 -q --junitxml=reports/institution_v2c_v1.xml
.venv\Scripts\python.exe -m pytest tests/institution_v2a -q --junitxml=reports/institution_v2c_v2a.xml
.venv\Scripts\python.exe -m pytest tests/institution_v2b -q --junitxml=reports/institution_v2c_v2b.xml
.venv\Scripts\python.exe scripts/test_institution_v2c_regressions.py
.venv\Scripts\python.exe scripts/check_institution_v2c_live.py
Push-Location -LiteralPath frontend
npm.cmd test
npx.cmd tsx --tsconfig tsconfig.app.json --test tests/admin-notifications.test.tsx tests/events.test.tsx tests/loan-renewal.test.tsx tests/part3-contract.test.tsx tests/search-depth.test.tsx tests/document-cache.test.tsx tests/knowledge-graph.test.tsx tests/kg-product.test.tsx tests/mind-map.test.tsx tests/rag-answer.test.tsx
npm.cmd run build
npm.cmd run lint
Pop-Location
.venv\Scripts\python.exe scripts/report_institution_v2c.py
```

To run the app against your configured local database, use the existing backend/frontend setup. Reuse running services when available. These are foreground development commands for separate terminals; the Core port matches the existing Vite proxy default. No production cutover is implied:

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM\frontend'
npm.cmd run dev -- --host 127.0.0.1 --port 5182
```

Migration examples are templates, not commands executed against production. Replace the angle-bracket values with a proven library UUID and its verified legacy alias; explicitly configure the intended database. Stop every API and worker writer before `--apply`. Retain the same UUID key for retries. Inspect quarantine and reconciliation before tenant ADMIN/OWNER activation at POST `/libraries/{library_id}/staff/reservations-fees/activate` with `{ "idempotency_key": "<UUID>" }`.

```powershell
$env:MONGO_DB_NAME = '<intended-database>'
.venv\Scripts\python.exe scripts/migrate_reservations_v2c.py --library-id '<library-UUID>' --legacy-library-id '<verified-legacy-alias>'
.venv\Scripts\python.exe scripts/migrate_fees_v2c.py --library-id '<library-UUID>' --legacy-library-id '<verified-legacy-alias>'
.venv\Scripts\python.exe scripts/reconcile_institution_v2c.py --library-id '<library-UUID>'
.venv\Scripts\python.exe scripts/migrate_reservations_v2c.py --library-id '<library-UUID>' --legacy-library-id '<verified-legacy-alias>' --apply --writers-stopped --idempotency-key '<stable-UUID>'
.venv\Scripts\python.exe scripts/migrate_fees_v2c.py --library-id '<library-UUID>' --legacy-library-id '<verified-legacy-alias>' --apply --writers-stopped --idempotency-key '<different-stable-UUID>'
.venv\Scripts\python.exe scripts/reconcile_institution_v2c.py --library-id '<library-UUID>' --operation recover
.venv\Scripts\python.exe scripts/reconcile_institution_v2c.py --library-id '<library-UUID>' --operation recover --apply --writers-stopped
.venv\Scripts\python.exe scripts/reconcile_institution_v2c.py --library-id '<library-UUID>' --operation rollback
.venv\Scripts\python.exe scripts/reconcile_institution_v2c.py --library-id '<library-UUID>' --operation rollback --apply --writers-stopped
```

Recovery apply requires a retained matching library gate and proven Part 2B cutover. Rollback apply is deliberately denied after queue, fee or new-loan use. Do not delete gates manually. No real gateway, Events/Notifications cutover or subsequent phase command is included.
