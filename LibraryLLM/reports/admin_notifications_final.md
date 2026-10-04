# Admin operations and notifications — final result

**A. FINAL STATUS** — PASS for the requested Admin/Notifications feature; one unchanged, pre-existing BookRAG regression failure is listed separately.

**B. ORIGINAL SOURCE** — Mongo activity via activity_service.create_activity; old /activity/all and Librarian Activity table.

**C. TARGET ID** — Stored activity.user_id; API target_user_id alias; immutable canonical account ID.

**D. ACTOR ID** — Additive actor_user_id for proven new actions. Authenticated Admin actor differs from authoritative issue owner on assisted return; unknown/system actors null.

**E. EMAIL RESOLUTION** — One batched current users lookup per operation page; exact case-insensitive recipient email resolution, ambiguous/unavailable fail closed.

**F. LEGACY TARGET COUNT** — 0 missing targets; 0 current account resolution failures.

**G. LEGACY ACTOR COUNT** — 88 unknown; no historical backfill or guessing.

**H. OPERATION SCHEMA** — operation_id/type, target_user_id/current target, actor_user_id/current actor, book, occurred/due/returned timestamps, current source status, description and source_ref. admin_operation_schema.json.

**I. OPERATION API** — GET /admin/operations; /admin/users; /admin/users/{id}/activity; /admin/summary. POST /admin/operations/return/{issue_id}. ADMIN only.

**J. ADMIN UI** — Operations and Notifications tabs; email drilldown, Notify User, explicit assisted return, aggregate overview counts, sent audit; existing Staff Management/Books retained.

**K. FILTERS** — Literal current-email substring/full email, exact work ID or title substring, eight actual operation types; server side, bounded inputs.

**L. GROUPING** — Optional group by canonical target account within the current page; selected account drilldown also filters by ID.

**M. PAGINATION** — 20 rows by default/max50; nonnegative offset; newest timestamp + ID tie-breaker; no full-history React filtering.

**N. NOTIFICATION STORAGE** — Mongo notifications; canonical recipient user_id, notification UUID, type/title/message, UTC creation/read timestamps, source/ref, priority, dedupe key, canonical sender ID.

**O. NOTIFICATION INDEXES** — Six additional indexes: unique notification_id and dedupe_key; owner/creation/ID; owner/read; sender/creation; source/creation/ID. Existing _id retained.

**P. ADMIN SEND FLOW** — Notify User or Notifications composer -> selected current account(s) -> plain-text message -> ADMIN-validated persist -> stored audit -> recipient poll/toast/inbox.

**Q. MULTI-RECIPIENT** — Up to50 unique selected canonical IDs; optional emails resolve IDs; all validation before writes; UUID retry dedupe.

**R. BROADCAST** — Optional and skipped; no broadcast endpoint.

**S. CENTER UX** — Header bell, unread badge, bounded history, read/read-all, empty/retry states, close/Escape focus restoration;45-second visible polling plus focus/login/read refresh.

**T. TOAST UX** — Non-blocking,8-second dismiss/close, once per observed ID per session; consolidated arrivals; silent login backlog; closing does not delete.

**U. DUE_SOON** — Due UTC calendar date is exactly2 days after today.

**V. DUE_TODAY** — Due UTC calendar date equals today.

**W. OVERDUE** — Due UTC calendar date before today; one initial per loan/due version, returned loans excluded.

**X. DEDUPE** — TYPE:loan_id:UTC_due_timestamp under unique index/setOnInsert; Admin uses sender/request UUID/recipient. Repeat and four concurrent scans verified.

**Y. WORKER** — Core FastAPI lifespan starts a thread; startup scan then interruptible60-minute wait; configurable minimum5minutes; indexed relevant-loan cursor batch500, source recheck, shutdown stop/join.

**Z. CATCH-UP** — Only present meaningful state; no missed-state replay or overdue interval flood. Local Core restarted with worker enabled; startup created0 because current loans required no alert.

**AA. RESERVATIONS** — Optional notifications deferred; no invented pickup expiry; circulation logic preserved.

**AB. ROLE MATRIX** — All authenticated roles: own notifications. ADMIN: new operations/directory/drilldown/send/audit/assisted return. LIBRARIAN: existing circulation access plus own notifications. GENERAL_USER: existing own circulation plus own notifications.

**AC. SECURITY** — Role-claim spoofing, non-Admin send/admin reads, cross-user read404, invalid recipients/oversized payloads, inactive/deleted account checks, plain-text XSS and account-scope reset passed. Safe current-user projections; no credential/JWT output.

**AD. BACKEND TESTS** — 48 feature +76 auth +385 broader regression cases passed =509 distinct passing;1 known unchanged BookRAG failure.

**AE. FRONTEND TESTS** — 170 distinct cases passed:138 earlier targeted +1 storage-sync regression +31 routing/read-now;81 assistant cases included in targeted and rechecked by npm test, not double-counted.

**AF. LIVE VALIDATION** — Disposable Admin/Alice/Bob: actual borrow/Admin return, email change, single/multi-send, private inbox, read/read-all, refresh/relogin, all3 due types, repeat dedupe and two-tab storage-sync fix. Responsive4 sizes; long inbox clears assistant. Cleanup verified original data hashes/book count.

**AG. PERFORMANCE** — Local medians(ms): first20 operations 15.09, next 15.06, email 10.41, drilldown 18.90; inbox 8.33; unread 5.50; send 11.97; reminder batch3 loans 7.20ms; repeat0 created.

**AH. INDEX CHANGES** — Notification six indexes plus issues(status,due_date) and activity(owner/creation/ID),(work/creation),(creation/ID); no existing index dropped. Exact installed definitions in admin_notification_indexes.json.

**AI. EXACT FILES** — Complete source/test/script/report manifest below and admin_notification_integrity.json. Frontend dist rebuilt. No Git repository is present; comparison uses the saved pre-edit hashes.

**AJ. BUILD/LINT** — Production build PASS; main chunk498.91KB plus lazy Admin chunk9.11KB. Lint0 errors,19 existing warnings,0 new warnings.

**AK. PRE-EXISTING FAILURE** — test_rag_query_types.py::test_overview_rule_never_accepts_added_premises[What are the major themes of this book?]; frozen source hashes match, no RAG tuning performed.

**AL. START COMMANDS** — Exact PowerShell commands below; Core8002/Vite5173 are running. Secondary test Vite5174 stopped.

**AM. LIMITATIONS** — No broadcast, reservation alerts, renewal API, retention policy, external delivery or WebSockets. Core must run for reminders. Partial multi-recipient DB writes converge by retry, not transaction. Small-history benchmark only; legacy title match ID-list/global offset scaling deferred. Source recheck/insert has a small concurrent-return race; stored notices remain after return/date change; seen IDs retained for active session. Existing activity max+1 allocator unchanged.

## Exact application/test/script files

- backend/main.py
- backend/services/activity_service.py
- backend/services/fine_service.py
- backend/services/issue_service.py
- backend/services/reservation_service.py
- frontend/src/App.tsx
- frontend/src/main.tsx
- frontend/src/components/Header.tsx
- frontend/src/pages/Staff.css
- frontend/src/pages/StaffDashboard.tsx
- backend/routes/notifications.py
- backend/services/admin_operation_service.py
- backend/services/notification_service.py
- backend/services/notification_worker.py
- frontend/src/components/NotificationCenter.tsx
- frontend/src/components/Notifications.css
- frontend/src/lib/notifications.ts
- frontend/src/lib/sessionStorageSync.ts
- frontend/src/pages/AdminOperations.tsx
- scripts/validate_admin_notifications.py
- tests/notification_ops/test_notifications.py
- frontend/tests/admin-notifications.test.tsx
- .gitignore

## Reports and evidence

- reports/admin_notification_auth_tests.log
- reports/admin_notification_baseline.json
- reports/admin_notification_browser.json
- reports/admin_notification_build.log
- reports/admin_notification_cleanup.log
- reports/admin_notification_composer.png
- reports/admin_notification_core_stderr.log
- reports/admin_notification_core_stdout.log
- reports/admin_notification_feature_tests.log
- reports/admin_notification_frontend_feature_tests.log
- reports/admin_notification_frontend_tests.log
- reports/admin_notification_indexes.json
- reports/admin_notification_integrity.json
- reports/admin_notification_lint.log
- reports/admin_notification_live.log
- reports/admin_notification_live_toast.png
- reports/admin_notification_live_validation.json
- reports/admin_notification_mobile_inbox.png
- reports/admin_notification_mobile_toast.png
- reports/admin_notification_operations_desktop.png
- reports/admin_notification_performance.json
- reports/admin_notification_regression_tests.log
- reports/admin_notification_standard_frontend_tests.log
- reports/admin_notification_test_results.json
- reports/admin_notification_vite_secondary.log
- reports/admin_notification_vite_secondary_error.log
- reports/admin_operation_schema.json
- reports/admin_operations_audit_raw.json
- reports/admin_operations_notification_audit.md
- reports/admin_user_operations.md
- reports/notification_due_worker.json
- reports/notification_schema.json
- reports/notification_security.json
- reports/notification_system.md

## Exact start commands (separate PowerShell terminals)

```powershell
Set-Location D:\SDC\LibraryLLM
$env:NOTIFICATION_DUE_WORKER_ENABLED = '1'
$env:NOTIFICATION_DUE_CHECK_INTERVAL_MINUTES = '60'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

```powershell
Set-Location D:\SDC\LibraryLLM\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## Reproducible checks

```powershell
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe -m pytest tests/notification_ops -q
.\.venv\Scripts\python.exe -m pytest tests/staff_auth -q
```

Run those as separate processes: the legacy staff-auth tests replace database imports.

```powershell
Set-Location D:\SDC\LibraryLLM\frontend
npx tsx --tsconfig tsconfig.app.json --test tests/admin-notifications.test.tsx
npm test
npm run build
npm run lint
```

Protected assistant/Search/recommendation/KG/RAG code hashes all match the baseline; frozen v1 catalogue.sqlite SHA256 0d5c6603f8cb5cf720b46eaac5d1cf6f1ef9952b3d668a69395cf1afb57921fc matches. No graph V2 build/promotion or KG4 work.
