# Institution Part 2B completion

Validated on 9 October 2026 (Asia/Calcutta). Stop after Part2B; no Part2C or production cutover performed.

| Item | Topic | Result |
|---|---|---|
| A | FINAL PASS | PASS for the implemented Part2B scope. Production cutover is explicit and has not been applied. |
| B | OLD CIRCULATION | Legacy user issue immediately created an ISSUED record and changed stock; user return closed it immediately. |
| C | NEW ARCHITECTURE | Canonical tenant request → held unit → staff issue; return request → physical staff receipt. |
| D | BORROW REQUEST | UUID unified request model, BORROW type, PENDING/review/terminal states and current tenant admission. |
| E | BORROW HOLD | One aggregate unit or genuine HELD_FOR_REQUEST copy; no active loan or due date. |
| F | REQUESTABLE AVAILABILITY | Derived from tenant totals minus holds, active loans and unavailable units; no global authority. |
| G | BORROW FLOW | Request Book, review in My Library, cancellation permitted while pending. |
| H | APPROVAL | Current OWNER/ADMIN/LIBRARIAN approves physical handover; same hold becomes one ACTIVE loan, due now+14 days. |
| I | REJECT/CANCEL/EXPIRE | Terminal request releases once; default24h bounded server expiry, processed in50-row batches. |
| J | LOAN MODEL | UUID library/book/holding/copy/borrower/reviewer/request and operation provenance; stable accession snapshot. |
| K | RETURN MODEL | RETURN request binds an ACTIVE UUID loan; loan holds pending return pointer. |
| L | RETURN FLOW | Request Return leaves ACTIVE loan/current visibility/responsibility/stock unchanged. |
| M | CONFIRM RECEIVED | Authorized staff verifies physical receipt, records returned_at/reviewer, completes request and releases once. |
| N | RETURN REJECTION | ACTIVE loan preserved; original request time retained; borrower may request again. |
| O | RENEWAL | Owning member, expected due date and existing policy; pending return blocks; only proven same-tenant reservations influence. |
| P | SHELF/LOCATION | Prominent add/edit fields and safe journaled staff shelf control; member/queue show current shelf. |
| Q | STOCK MANAGEMENT | Visible default1 initial stock; canonical totals/status/unavailable editor; allocation and known-copy floor; no editable derived availability. |
| R | CIRCULATION STATUS | CIRCULATING, REFERENCE_ONLY, TEMPORARILY_UNAVAILABLE, WITHDRAWN; only circulating books requestable. |
| S | STAFF DASHBOARD | Borrow/return queues, badges, bounded paging/filtering, borrower essentials, availability and physical confirmation dialogs. |
| T | MY LIBRARY | Separate requests/current/history; pending returns remain current and disable return/renew controls; library changes clear stale state. |
| U | IDEMPOTENCY | Tenant+actor+UUID key and command fingerprint; stored receipt;409 on conflicting reuse. |
| V | JOURNAL | Durable PREPARED plan with absolute tenant effects and audit intents; verified COMMITTED receipt. |
| W | UNKNOWN RECOVERY | 503 retained gate; stopped-writer plan replay and reconciliation before reopening; no TTL takeover. |
| X | SECURITY | Current account/membership/role; tenant IDOR and global ADMIN bypass denied; own request/loan scope and private inventory enforced. |
| Y | LEGACY MIGRATION | Read-only default; explicit verified alias, physical issue mapping and preserved dates; old records retained. |
| Z | CUTOVER | Per-library LEGACY/PREPARING/CANONICAL/RECOVERY_REQUIRED; empty consistent online activation or offline proven migration. |
| AA | ROLLBACK | Durable rollback only before requests/loans/post-cutover operations; repeat receipt stable; migrated active loan prevents rollback. |
| AB | ASSISTANT | Explicit immutable library/book/loan request actions with mandatory confirmation; existing router/models/context repair preserved. |
| AC | LIVE VALIDATION | All real HTTP/Mongo/Vite A–M scenarios pass; browser owner/member workflows and six viewport sizes pass; fixture cleaned. |
| AD | RACES | 20 users/5 units, two users/last unit, approve/reject/cancel/expiry and double staff receipt races; return/renew serialization; failure replay verified. |
| AE | PERFORMANCE | Nine operations measured with actual local small-fixture samples; raw, median and p90 in performance.json. No production-scale claim. |
| AF | BACKEND | 57 Part2B +56 V1 +95 Part2A passed; ten frozen groups1300 passed/10 existing skipped. |
| AG | FRONTEND | 253 full-chain +156 extended =409 passed executions;23 lending tests included. |
| AH | REGRESSION | Auth, staff, legacy circulation/renewal/reservations/fines/activity, events, notifications, search/recommendations/KG, Book/private RAG/Knowledge Tools and assistant pass; research router benchmarks not run. |
| AI | BUILD/LINT | Build passes; lint0 errors and19 existing warnings; existing Vite chunk-size warning retained. |
| AJ | FILES | 29 modified existing +22 added source files; exact paths and SHA256 in manifest.json, compared with786 baseline files. |
| AK | COLLECTIONS/INDEXES | institution_lending_requests, institution_loans, institution_lending_operations, institution_lending_config; shared holdings/copies/audit/locks. Exact unique/partial/query indexes in operation_journal.json. |
| AL | SCRIPTS | migrate_lending_v2b.py and reconcile_lending_v2b.py use lending_v2b_operations.py; read-only default, explicit offline apply. |
| AM | REPORTS | All21 required baseline/workflow/category/live/performance/regression/review/Part2C reports created; additional manifest, preservation, journal, browser, JUnit, logs, screenshots and commands. |
| AN | LIMITS | Standalone serialized gates; occasional busy-read503 requires refresh; lazy expiry/no scheduled sweeping; small-fixture timing; no power-loss test; incomplete legacy tenant evidence needs operator review. New canonical fees/reservation fulfillment and external notification delivery are deferred. Existing assistant mutation flag retained. |
| AO | REVIEW | 20 required topics assessed with Why/Current limitation/Recommendation/Priority/Implement/Breaking/Migration in improvement_review.md. |
| AP | READY_FOR_PICKUP | Defer pending evidence for a separate approved collection stage. Approval currently means physical issue. |
| AQ | BARCODE/QR | Genuine copy identity fits tenant barcode lookup, then matching request and confirmation. Hardware and QR authority infrastructure deferred. |
| AR | NEXT PHASE | Repository evidence supports tenant Reservations+Fees; legacy work queues and issue_id fines cannot safely consume new UUID loans. |
| AS | PART2C SCOPE | Canonical queues/one-hold conversion, versioned fee/timestamp policy, idempotent charge/adjustment records, proven migration and scoped UX/security tests; approval required. |
| AT | DEFERRED | Full reservations/fees/events/notifications/analytics tenancy, pickup/kiosk/hardware, RAG/vector tenancy, global availability filters and recommendation overlays. |
| AU | COMMANDS | Exact executed test/build/live/report commands and explicit parameterized offline migration/recovery/rollback commands are below. |

```powershell
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe -m pytest tests/institution_v2b -q --junitxml=reports/institution_v2b_backend.xml
.\.venv\Scripts\python.exe -m pytest tests/institution_v1 -q --junitxml=reports/institution_v2b_v1.xml
.\.venv\Scripts\python.exe -m pytest tests/institution_v2a -q --junitxml=reports/institution_v2b_v2a.xml
.\.venv\Scripts\python.exe scripts/test_institution_v2b_regressions.py
.\.venv\Scripts\python.exe scripts/check_institution_v2b_live.py
Set-Location D:\SDC\LibraryLLM\frontend
npm test
npx tsx --tsconfig tsconfig.app.json --test tests/admin-notifications.test.tsx tests/document-cache.test.tsx tests/events.test.tsx tests/knowledge-graph.test.tsx tests/kg-product.test.tsx tests/mind-map.test.tsx tests/loan-renewal.test.tsx tests/part3-contract.test.tsx tests/search-depth.test.tsx tests/rag-answer.test.tsx
npm run build
npm run lint
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe scripts/report_institution_v2b.py
```

Use a verified existing UUID and its explicit legacy alias; placeholders below must be replaced. Planning/reconciliation is read-only by default. Stop all API and worker writers before any apply; retain that downtime until reconciliation succeeds.

```powershell
$libraryUuid = '<verified-library-uuid>'
$legacyLibraryAlias = '<verified-Part2A-legacy-alias>'
.\.venv\Scripts\python.exe scripts/migrate_lending_v2b.py --library-id $libraryUuid --legacy-library-id $legacyLibraryAlias
# Explicit offline apply after reviewing the plan:
$cutoverKey = [guid]::NewGuid().ToString()
.\.venv\Scripts\python.exe scripts/migrate_lending_v2b.py --library-id $libraryUuid --legacy-library-id $legacyLibraryAlias --apply --writers-stopped --idempotency-key $cutoverKey
.\.venv\Scripts\python.exe scripts/reconcile_lending_v2b.py --library-id $libraryUuid
# Recovery review, then explicit application while writers remain stopped:
.\.venv\Scripts\python.exe scripts/reconcile_lending_v2b.py --library-id $libraryUuid --action recover
.\.venv\Scripts\python.exe scripts/reconcile_lending_v2b.py --library-id $libraryUuid --action recover --apply --writers-stopped
# Rollback eligibility review; apply only if reported safe:
.\.venv\Scripts\python.exe scripts/reconcile_lending_v2b.py --library-id $libraryUuid --action rollback
.\.venv\Scripts\python.exe scripts/reconcile_lending_v2b.py --library-id $libraryUuid --action rollback --apply --writers-stopped
```

Normal development services: `.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000` and frontend `npm run dev`. Keep the project's existing database/environment configuration. Opening a library does not activate canonical lending; ADMIN uses the reviewed Enable Approval Circulation action only when snapshot consistency and absence of mapped active legacy loans are proven. Assistant mutations retain the existing configured feature flag. No production migration command was run in this task.
