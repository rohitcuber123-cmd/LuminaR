# Circulation Phase 2 — final acceptance

| Item | Result |
|---|---|
| A. Status | PASS for this phase. One permitted pre-existing broader RAG failure remains. |
| B. Loan model | Mongo issue_id/user_id/work_id, authoritative due_date, ISSUED/RETURNED, source inventory and fine_amount. |
| C. Policy | Own active loan, below max, non-overdue, no conflicting reservation. ADMIN assist follows existing assisted return permission. |
| D. Period | 14 days from current due date; LOAN_RENEWAL_DAYS. |
| E. Maximum | 1; LOAN_MAX_RENEWALS. |
| F. Overdue | Prohibited after actual UTC due timestamp. |
| G. Reservations | Another account ACTIVE/READY_FOR_PICKUP on same work blocks, including spare copies. |
| H. Fees | Preserved; existing UTC calendar overdue days x INR5 return rule. |
| I. API | GET /issues/{id}/renewal; POST /issues/{id}/renew; ADMIN POST /admin/operations/renew/{id}. Required UUID request_id + expected_due_date. |
| J. User UI | Profile Renew/count/eligibility/loading guard; refreshes due/activity/inbox. |
| K. Admin UI | Assisted Renew on active issue rows; BOOK RENEWED filter and old/new due snapshots. |
| L. Audit | BOOK_RENEWED canonical reader/authenticated actor; idempotent event_key, original time and due snapshots. |
| M. Resolution | resolved_at/reason separate from read_at; current first; resolved excluded from badge/toasts. |
| N. Return | Resolves outstanding system due reminders; worker excludes returned loans. |
| O. Renewal | Resolves old version; new due date can generate future correct reminders. |
| P. Worker | Pre/postinsert source checks + mutation reconciliation; startup/interval recovery. Both race orderings tested. |
| Q. Indexes | Three notification compound indexes + unique sparse activity event_key; one-key/document IXSCAN proof. |
| R. Backend | 549 distinct passed; 10 skipped; one permitted RAG failure. New40/notification48/auth76/broader385. |
| S. Frontend | 180 distinct passed, including10 new cases. |
| T. Live | Disposable API, real worker races and UI passed; fixtures cleaned, production hashes/counts match, protected source/KG unchanged. |
| U. Performance | Renew12.20ms; eligibility7.07ms; reconcile0.65ms; own loans22.32ms; Admin14.17ms. Small local samples. |
| V. Build/lint | Build passed; lint0 errors/19 existing warnings. Main499.93kB. |
| W. Files | 23 source/test/config files, exact list below. Generated evidence separately listed in manifest. |
| X. Start | Exact PowerShell commands below. Core8002/frontend5173 already running; reminder worker enabled. |
| Y. Existing failure | test_overview_rule_never_accepts_added_premises[What are the major themes of this book?], tests/test_rag_query_types.py. RAG unchanged. |
| Z. Limits | Cross-collection reservation check and side effects not transactional. UUID retry repairs audit; worker recovers notices. Assistant renewal/pickup expiry deferred. |

## W. Exact source/test/config files

Modified:

- [.gitignore](D:/SDC/LibraryLLM/.gitignore)
- [backend/main.py](D:/SDC/LibraryLLM/backend/main.py)
- [activity_service.py](D:/SDC/LibraryLLM/backend/services/activity_service.py)
- [admin_operation_service.py](D:/SDC/LibraryLLM/backend/services/admin_operation_service.py)
- [issue_service.py](D:/SDC/LibraryLLM/backend/services/issue_service.py)
- [notification_service.py](D:/SDC/LibraryLLM/backend/services/notification_service.py)
- [reservation_service.py](D:/SDC/LibraryLLM/backend/services/reservation_service.py)
- [NotificationCenter.tsx](D:/SDC/LibraryLLM/frontend/src/components/NotificationCenter.tsx)
- [Notifications.css](D:/SDC/LibraryLLM/frontend/src/components/Notifications.css)
- [api.ts](D:/SDC/LibraryLLM/frontend/src/lib/api.ts)
- [notifications.ts](D:/SDC/LibraryLLM/frontend/src/lib/notifications.ts)
- [AdminOperations.tsx](D:/SDC/LibraryLLM/frontend/src/pages/AdminOperations.tsx)
- [ProfilePage.tsx](D:/SDC/LibraryLLM/frontend/src/pages/ProfilePage.tsx)
- [Staff.css](D:/SDC/LibraryLLM/frontend/src/pages/Staff.css)

Added:

- [renewals.py](D:/SDC/LibraryLLM/backend/routes/renewals.py)
- [loan_notification_service.py](D:/SDC/LibraryLLM/backend/services/loan_notification_service.py)
- [loan_renewal_service.py](D:/SDC/LibraryLLM/backend/services/loan_renewal_service.py)
- [LoanRenewalControl.tsx](D:/SDC/LibraryLLM/frontend/src/components/LoanRenewalControl.tsx)
- [loanRenewal.ts](D:/SDC/LibraryLLM/frontend/src/lib/loanRenewal.ts)
- [loan-renewal.test.tsx](D:/SDC/LibraryLLM/frontend/tests/loan-renewal.test.tsx)
- [conftest.py](D:/SDC/LibraryLLM/tests/loan_renewal/conftest.py)
- [test_renewals.py](D:/SDC/LibraryLLM/tests/loan_renewal/test_renewals.py)
- [validate_loan_renewal.py](D:/SDC/LibraryLLM/scripts/validate_loan_renewal.py)

The reports, logs and screenshots are additional generated evidence. frontend/dist is generated build output. [Exact manifest](D:/SDC/LibraryLLM/reports/loan_renewal_file_manifest.json).

## X. Exact start commands

Core in one PowerShell terminal, with existing Mongo/auth configuration available:

```powershell
Set-Location D:\SDC\LibraryLLM
$env:LOAN_RENEWAL_ENABLED = '1'
$env:LOAN_RENEWAL_DAYS = '14'
$env:LOAN_MAX_RENEWALS = '1'
$env:NOTIFICATION_DUE_WORKER_ENABLED = '1'
$env:NOTIFICATION_DUE_CHECK_INTERVAL_MINUTES = '60'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
```

Frontend in a second terminal:

```powershell
Set-Location D:\SDC\LibraryLLM\frontend
$env:LUMINAR_CORE_API_TARGET = 'http://127.0.0.1:8002'
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Both services are currently running; commands are for a fresh restart, not duplicate processes on the same ports.

## Verification commands

```powershell
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe -m pytest tests/loan_renewal -q
.\.venv\Scripts\python.exe -m pytest tests/notification_ops -q
.\.venv\Scripts\python.exe -m pytest tests/staff_auth -q
.\.venv\Scripts\python.exe -m pytest tests/test_knowledge_graph.py tests/test_kg_topics.py tests/test_kg_product.py tests/test_search_depth.py tests/test_assistant_backend.py tests/test_assistant_part3.py tests/test_assistant_part3_repair.py tests/test_assistant_kg.py tests/test_private_document_cache.py tests/test_document_rag_latency.py tests/test_book_access_control.py tests/test_dynamic_book_capabilities.py tests/test_rag_query_types.py -q
Set-Location D:\SDC\LibraryLLM\frontend
npx tsx --tsconfig tsconfig.app.json --test tests/loan-renewal.test.tsx tests/admin-notifications.test.tsx tests/assistant.test.tsx tests/search-depth.test.tsx tests/kg-product.test.tsx tests/knowledge-graph.test.tsx tests/document-cache.test.tsx tests/part3-contract.test.tsx
npm test
npm run build
npm run lint
```

Full implementation A–Q, rationale and limitations: [loan_renewal_implementation.md](D:/SDC/LibraryLLM/reports/loan_renewal_implementation.md). All five requested implementation/policy/reconciliation/security/performance reports are saved. STOP after this phase.
