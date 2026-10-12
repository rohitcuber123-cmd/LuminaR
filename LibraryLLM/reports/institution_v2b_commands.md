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
