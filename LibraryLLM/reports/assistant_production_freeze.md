# LuminaR production assistant freeze

**PASS. Production router: `existing_qwen`. Router V1–V5 research is complete. Do not promote V2/V3/V4/V5 or automatically start V6.**

Missing ASSISTANT_ROUTER_MODE uses existing_qwen. Invalid or empty values fail safely with ValueError before assistant client/gateway/worker creation.
Legacy V2 variant/retry environment flags cannot override normal app installation. Explicit V3/V4/shadow/V5 modes remain archived,
EXPERIMENTAL / NOT PRODUCTION APPROVED. No normal frontend exposes them. See `assistant/ROUTER_FREEZE.md`.

## A–T final result

| Item | Result |
|---|---|
| A. Status | PASS for the requested stabilization gates. |
| B. Production router | existing_qwen; no newest-artifact detection. |
| C. Experiments | Frozen and retained; no research corpus run, new router, model or training. |
| D. Add before/after | Immediate write → pending canonical target → Confirm only. |
| E. Remove before/after | Immediate write → pending canonical target → Confirm only; Cancel retains item. |
| F. Pending model | Existing per-conversation state, immutable target(s), five-minute expiry, random action ID. |
| G. Authorization | Server-derived user/session owner; wrong account/session private 404, wrong conversation rejected. |
| H. Target immutability | Changed selection B cannot reinterpret stored A; unrelated new turn invalidates proposal. |
| I. HTTP | One bounded startup/lifespan client; reused; clean shutdown. |
| J. Concurrent auth | Two identities retain distinct request-local bearers and responses in transport regression. |
| K. Normal memory | Startup RSS 1857.64 MiB; CUDA allocated 2153.29, reserved 2220.00 MiB for existing RAG/Qwen. |
| L. Rejected routers loaded | NO. Fresh startup imports zero experimental router modules; zero child workers. |
| M. Live | 12/12 checks; 8/8 natural mutation prompts; zero Qwen at confirm/cancel; disposable records cleaned. |
| N. Backend | 915 passed, 10 skipped; 0 failures. |
| O. Frontend | 191 passed; all ten frontend test files. |
| P. Build/lint | Build PASS; 0 lint errors, 19 existing warnings. Existing bundle-size warning retained. |
| Q. Exact files | Existing/new paths listed below and in the file audit. |
| R. Reports | All six requested reports created; supporting live/smoke/integrity evidence retained. |
| S. Limits | Natural reference/page/previous-context routing still imperfect; generative requests are serialized and bounded. |
| T. Start commands | Below; current five services already running without duplicates. |

## Preserved strengths and known limitations

Structured actions and selected-work explicit operations bypass routing generation. Tools/API authentication and catalogue identity
remain authoritative. Circulation and reading-list mutations require explicit confirmation; Clear retains its explicit-action policy.
Existing Search, Recommendation, KG More Like This, Book RAG, private Document RAG, Admin and Notifications integration/algorithms are unchanged.

Natural reference resolution may clarify incorrectly, page references and previous-comparison follow-ups may fail, and complex language
can be slow. Qwen admission is serialized/bounded; a busy request receives the existing clear assistant-level message without internal
lock/CUDA/queue details. Explicit deterministic operations still work while the reasoning slot is held. No accepted experimental router
met the product gates; experimental precision is not production quality. No hardcoded phrases were added to conceal these limitations.

Normal memory observation after restoration: at least 4355 MiB host RAM available,
maximum 81.73% Windows commit, peak 65 pages input/sec in three brief idle samples.
Archived V5 added an approximately 857.62 MiB worker and recorded only 228 MiB host RAM available.
This is archived comparison, not a paired performance benchmark. Host commit is still high; removing rejected workers does not fix
every full-stack memory constraint. Normal RAG's own retrieval/reranker/Qwen GPU footprint is expected and was not changed.

The startup psutil swap values are separate raw observations; actual Windows commit comes from WMI. No duplicate model/service
was launched for measurements. One listener exists per service port. Models, datasets and evaluation seals were retained.

## Exact existing source/test edits

- `assistant/api.py`
- `assistant/orchestrator.py`
- `assistant/qwen.py`
- `assistant/schemas.py`
- `frontend/src/components/assistant/AssistantTurn.tsx`
- `frontend/src/lib/assistantTypes.ts`
- `frontend/tests/assistant.test.tsx`
- `tests/test_assistant_part3.py`
- `tests/test_assistant_part3_repair.py`
- `tests/test_assistant_semantic_router.py`
- `scripts/assistant_stabilization_audit.py`

## New source/test/documentation files

- `assistant/ROUTER_FREEZE.md`
- `tests/test_assistant_production_stabilization.py`
- `scripts/capture_assistant_production_memory.py`
- `scripts/check_assistant_production_live.py`
- `scripts/report_assistant_stabilization.py`
- `scripts/smoke_assistant_production.py`
- `scripts/start_assistant_production.ps1`

## Required reports

- `reports/assistant_mutation_safety.md`
- `reports/assistant_router_archive_audit.md`
- `reports/assistant_http_transport_regression.json`
- `reports/assistant_production_memory.json`
- `reports/assistant_production_freeze.md`
- `reports/assistant_stabilization_regression.json`

## Normal start commands

Services are already running. From a stopped stack, use separate terminals in `D:\SDC\LibraryLLM`:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
.venv\Scripts\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003
.venv\Scripts\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004
$env:ASSISTANT_ROUTER_MODE='existing_qwen'
.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005
```

From `D:\SDC\LibraryLLM\frontend`: `npm run dev -- --host 127.0.0.1 --port 5173`.
The local hidden RAG helper is `scripts/start_assistant_production.ps1`; it refuses duplicate listeners.
`-RestartRag` verifies the project launcher/service before replacing only that RAG process. The diagnostic helper runs from cached models
and does not change `.env` or circulation-write flags. Optional numeric profiling uses ASSISTANT_PROFILE_PATH; it stores no prompts/tokens/private records.

**STOP: production stabilization complete; router research remains frozen.**
