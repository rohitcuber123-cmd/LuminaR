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
