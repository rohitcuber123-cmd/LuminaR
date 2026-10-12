# Exact PowerShell commands

Run from the existing checkout. Test fixtures use their own databases. The browser matrix
was driven through the supported computer-use viewport/UI APIs; it has no shell browser runner.

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
python -X utf8 scripts/test_frontend_workspace_regressions.py
python -X utf8 -m pytest tests/frontend_workspace -q --junitxml=reports/frontend_workspace_backend.xml
Set-Location -LiteralPath 'D:\SDC\LibraryLLM\frontend'
npm test
npx tsx --tsconfig tsconfig.app.json --test tests/search-depth.test.tsx tests/part3-contract.test.tsx tests/events.test.tsx tests/rag-answer.test.tsx
npm run build
npm run lint
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
python -X utf8 scripts/report_frontend_workspace.py
```

The isolated live fixture command used for browser testing was:

```powershell
Set-Location -LiteralPath 'D:\SDC\LibraryLLM'
python -X utf8 scripts/check_frontend_workspace_live.py --serve
```

It serves frontend 5184/core 8084 and drops its exact disposable database in finally.
In a second terminal, after the browser checks, its normal stop signal is:

```powershell
Set-Content -LiteralPath 'D:\SDC\LibraryLLM\.scratch\frontend-workspace\stop' -Value stop
```

During the final handoff the owned server processes had already stopped. Cleanup verified
their two fixture PIDs were absent and dropped only the recorded luminar_fw_live_ database.
No user service was stopped. The original development start commands remain in
LOCAL_DEVELOPMENT.md; no new deployment, cutover, router research or migration was run.
