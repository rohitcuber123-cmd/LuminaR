# Reproduce dashboard convergence verification

Run backend commands in D:\SDC\LibraryLLM with the project's virtual environment.

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/test_dashboard_convergence_regressions.py
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/dashboard_convergence -q --junitxml=reports/dashboard_convergence_authority_final.xml
```

Each Mongo fixture suite must run in its own process; do not combine suites that own different database prefixes.

From the frontend directory:

```powershell
npm test
npx tsx --tsconfig tsconfig.app.json --test tests/events.test.tsx tests/admin-notifications.test.tsx tests/loan-renewal.test.tsx tests/search-depth.test.tsx tests/part3-regression.test.tsx tests/rag-answer.test.tsx
npm run build
npm run lint
```

Dry-run account review (no inferred grants):

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/migrate_management_authority.py
```

An operator must supply an independently approved mapping before using --apply --mapping. No production apply was executed. Each row must identify an existing ready user, an explicit role, approval metadata and, for library membership, an existing active canonical library UUID. Both authorities require independent justification when one user receives both.

The live test harness is scripts/check_dashboard_convergence_live.py --serve. It owns only its generated luminar_dc_live_* database and ports 8086/5186, emits synthetic fixture credentials in .scratch only, and stops/drops its resources when its stop file appears. Never copy fixture credentials into reports. Browser proof must use the documented computer-use API.

scripts/report_dashboard_convergence.py reads the baseline, current production counts, test logs, browser records and cleanup evidence. It asserts preservation and writes only new phase reports. It cannot create authority grants.
