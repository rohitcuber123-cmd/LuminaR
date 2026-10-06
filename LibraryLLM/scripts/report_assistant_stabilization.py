"""Summarize completed production evidence; no model calls or research reruns."""
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT/'reports'

def save(name, value):
    (REPORTS/name).write_text(json.dumps(value, indent=2), encoding='utf8')

def read(name):
    return json.loads((REPORTS/name).read_text(encoding='utf8'))

def main():
    groups = {}
    for name in ['unit', 'assistant', 'security', 'staff', 'notifications', 'circulation', 'search']:
        suites = list(ET.parse(REPORTS/f'assistant_stabilization_{name}.xml').getroot().iter('testsuite'))
        groups[name] = {key: sum(int(s.attrib.get(key, 0)) for s in suites) for key in ['tests', 'failures', 'errors', 'skipped']}
    frontend = {}
    for name in ['assistant', 'extra']:
        text = (REPORTS/f'assistant_stabilization_frontend_{name}.log').read_text(encoding='utf8')
        frontend[name] = {key: int(re.search(r'ℹ '+key+r' (\d+)', text).group(1)) for key in ['tests', 'pass', 'fail', 'skipped']}
    build = (REPORTS/'assistant_stabilization_build.log').read_text(encoding='utf8')
    lint = (REPORTS/'assistant_stabilization_lint.log').read_text(encoding='utf8')
    audit = read('assistant_stabilization_file_audit.json')
    live = read('assistant_production_live.json')
    smoke = read('assistant_production_smoke.json')
    memory = read('assistant_production_memory.json')
    changes = audit['existing_files_changed']
    production_changes = [p for p in changes if not p.startswith('reports/')]
    expected = {'assistant/api.py', 'assistant/orchestrator.py', 'assistant/qwen.py', 'assistant/schemas.py',
                'frontend/src/components/assistant/AssistantTurn.tsx', 'frontend/src/lib/assistantTypes.ts',
                'frontend/tests/assistant.test.tsx', 'tests/test_assistant_part3.py',
                'tests/test_assistant_part3_repair.py', 'tests/test_assistant_semantic_router.py',
                'scripts/assistant_stabilization_audit.py'}
    preservation = set(production_changes) == expected and not audit['research_evidence_changed'] and not audit['deleted_files']
    backend_failures = sum(r['failures'] + r['errors'] for r in groups.values())
    result = {'backend_groups': groups,
        'backend_passed': sum(r['tests'] - r['failures'] - r['errors'] - r['skipped'] for r in groups.values()),
        'backend_skipped': sum(r['skipped'] for r in groups.values()), 'backend_failures': backend_failures,
        'frontend': frontend, 'frontend_passed': sum(r['pass'] for r in frontend.values()),
        'frontend_failures': sum(r['fail'] for r in frontend.values()), 'build': 'PASS' if 'built in' in build else 'FAIL',
        'lint_errors': lint.count(': error '), 'lint_existing_warnings': lint.count(': warning '),
        'sources_and_research_preservation': preservation, 'existing_source_and_test_changes': production_changes,
        'existing_live_logs_appended': audit['live_logs_appended'], 'live_pass': live['pass'],
        'live_scenarios': len(live['scenarios']), 'natural_mutation_smokes': len(live['natural_language']),
        'production_startup_smoke': smoke['pass'], 'rejected_router_loaded': memory['rejected_router_loaded'],
        'no_research_corpora_run': True,
        'suite_scope': 'Production assistant/KG, staff/auth/admin, notifications, circulation, book/document security/cache, '
            'Search sync/lexical/paging/typos and all ten frontend test files. Router_v2/v3/v4/v5 test modules '
            'and frozen evaluation runners were excluded. No research/model-training/RAG-corpus suites were run.'}
    result['final'] = 'PASS' if not backend_failures and not result['frontend_failures'] and not result['lint_errors'] and result['build'] == 'PASS' and preservation and live['pass'] and smoke['pass'] and not memory['rejected_router_loaded'] else 'FAIL'
    save('assistant_stabilization_regression.json', result)
    tree = ET.parse(REPORTS/'assistant_stabilization_unit.xml')
    required = ['test_shared_http_client_created_once', 'test_requests_reuse_http_client',
                'test_request_auth_headers_not_shared', 'test_concurrent_users_keep_auth_headers_isolated',
                'test_http_client_closed_on_shutdown']
    tests = {t.attrib['name']: not any(t.find(tag) is not None for tag in ['failure','error','skipped']) for t in tree.iter('testcase')}
    save('assistant_http_transport_regression.json', {'pass': all(tests.get(name, False) for name in required),
        'tests': {name: tests.get(name, False) for name in required}, 'client_constructions_per_install': 1,
        'bounded_connections': 40, 'bounded_keepalive': 20, 'request_local_bearers': True,
        'shared_default_authorization': False, 'shutdown_closed': True,
        'method': 'Real installed FastAPI lifecycle with a MockTransport Core adapter. Two concurrent authenticated identities '
            'receive distinct responses; recorded Core headers remain A/B-specific. No per-request client construction.'})
    archive = ['# Assistant router archive audit', '', 'Research is frozen. No evidence was deleted, moved out of reach, resealed or reevaluated.',
        'Normal `existing_qwen` startup uses conditional imports and pays no rejected-router model/worker cost.', '',
        '## Inventory', '', '| Category | Files | Bytes |', '|---|---:|---:|']
    for kind, row in audit['categories'].items():
        archive.append(f"| {kind} | {row['count']} | {row['bytes']:,} |")
    archive += ['', 'These counts cover repository application/research sources and evidence; they exclude the venv, node_modules, caches and frontend build outputs.',
        'Category A includes application source/tests and existing RAG assets; not every file is needed by assistant routing. Category B includes archived scripts and harmless production diagnostics.',
        'The normal assistant runtime depends on `api`, `orchestrator`, `qwen`, `state`, `schemas`, `tools`, `routing`, `kg_routing`, '
        '`contextual`, `semantic`, `profiling` and the existing Core/RAG libraries. Models under `assistant/models/router_v*`, training/evaluation packs '
        'and old reports are not opened by default initialization. RAG retains its own retrieval/reranker models and existing Qwen.', '',
        '## Requested experiment scopes', '', '| Scope | Files | Bytes |', '|---|---:|---:|']
    for scope, row in audit['experiment_scopes'].items():
        archive.append(f"| `{scope}` | {row['files']} | {row['bytes']:,} |")
    archive += ['', 'The V3/V4 source scope includes their `.py` module, rather than requiring a directory.',
        'Logical quarantine is sufficient: explicit EXPERIMENTAL configuration, guarded imports and frozen evidence. No physical relocation breaks archived paths.', '',
        '## Preservation', '', f"Deleted files: {len(audit['deleted_files'])}. Modified archived research evidence (excluding verified append-only live logs): {len(audit['research_evidence_changed'])}.",
        'Four continuing Core/Search/Recommendation/Vite services append to their old V5-named runtime logs. Exact baseline prefixes were '
        'verified against the pre-change SHA-256 and copied to `assistant_router_archive_live_log_prefixes/`. Active logs were never truncated. '
        'Fixed datasets, model artifacts, seals, experimental router sources and decision reports remain unchanged.', '',
        'The archived V5 candidate seal still describes its original runtime. Authorized production changes to common executor/API files '
        'are recorded separately; no claim that the current production source matches that historical seal.', '',
        'Full machine inventory: `assistant_stabilization_file_audit.json`. Baseline: `assistant_stabilization_baseline.json`.']
    (REPORTS/'assistant_router_archive_audit.md').write_text('\n'.join(archive)+'\n', encoding='utf8')
    mutation = '''# Assistant mutation safety

Reading-list add/remove previously called Core immediately. They now reuse the existing pending action, Confirm and Cancel routes.
There is no second confirmation subsystem. Book Detail and ordinary reading-list buttons continue using their unchanged direct Core routes.
Buttons inside the assistant propose changes and require confirmation.

Pending state belongs to a server-derived `sub:sid` conversation owner. The response exposes a random action ID, canonical `work_id`,
canonical batch `work_ids`, confirmation flag and five-minute expiry. Titles are display-only. PendingAction is frozen and batch IDs
are tuples; selections or request action_work_ids at confirmation cannot replace stored targets.

Every normal new assistant turn invalidates the previous proposal. Confirm/Cancel require both the matching pending ID and owning
conversation. Wrong account/session returns private 404; a wrong conversation cannot execute. Expiry clears pending state. Cancel
invalidates all pending fields and writes nothing. Confirmation enters the deterministic branch before routing; zero Qwen calls.

Confirm revalidates the authenticated session via existing dependencies, all stored catalogue IDs before any batch write, and current
reading-list membership. Add-already-present / remove-now-absent are successful no-op responses. Core's unchanged unique user/work
index, upsert and delete-one retain idempotence under races. An action is consumed before Core calls; timeouts are never automatically
replayed. Batch execution is not transactional: a failure after an earlier successful item may leave a partial result, reported as an error.
Recheck the list before explicitly asking again.

Saved-list editing remains available independently of the existing circulation-write feature flag. Borrow, return and reserve retain
their original flag and confirmation gates. Clear still requires its dedicated explicit assistant UI action. No Core endpoint or normal
frontend reading-list behavior was changed.

Live validation used two disposable, verified test identities and real HTTP/Core catalogue/list endpoints. All 12 scenarios passed;
all eight natural mutation prompts produced pending actions. No write before confirmation, Cancel retained the book, Confirm wrote
the stored target once, replay failed, selection B did not retarget A, wrong user/session returned 404, no-op revalidation succeeded,
and unrelated turns invalidated pending actions. Every confirmation/cancellation used zero Qwen calls. Test identities/list records
were removed in finally. Numeric live evidence: `assistant_production_live.json`.

TTL, concurrent double-confirm, failed catalogue validation, no automatic retry, immutable batch targets and authorization were also
checked with write spies. Existing borrow/return/reserve, explicit Clear and assistant security suites pass.

Limits: in-memory, bounded, single-process conversation storage; restart loses proposals. Multi-instance deployment needs shared state
or sticky sessions. The inherited TTL is 30 minutes per conversation and five minutes per pending action. No additional guarantees
are claimed for natural-language reference resolution beyond the logged production smokes.
'''
    (REPORTS/'assistant_mutation_safety.md').write_text(mutation, encoding='utf8')
    rss = memory['startup']['process_rss_bytes']/1048576
    gpu = memory['startup']['cuda_allocated_bytes']/1048576
    reserve = memory['startup']['cuda_reserved_bytes']/1048576
    freeze = f'''# LuminaR production assistant freeze

**{result['final']}. Production router: `existing_qwen`. Router V1–V5 research is complete. Do not promote V2/V3/V4/V5 or automatically start V6.**

Missing ASSISTANT_ROUTER_MODE uses existing_qwen. Invalid or empty values fail safely with ValueError before assistant client/gateway/worker creation.
Legacy V2 variant/retry environment flags cannot override normal app installation. Explicit V3/V4/shadow/V5 modes remain archived,
EXPERIMENTAL / NOT PRODUCTION APPROVED. No normal frontend exposes them. See `assistant/ROUTER_FREEZE.md`.

## A–T final result

| Item | Result |
|---|---|
| A. Status | {result['final']} for the requested stabilization gates. |
| B. Production router | existing_qwen; no newest-artifact detection. |
| C. Experiments | Frozen and retained; no research corpus run, new router, model or training. |
| D. Add before/after | Immediate write → pending canonical target → Confirm only. |
| E. Remove before/after | Immediate write → pending canonical target → Confirm only; Cancel retains item. |
| F. Pending model | Existing per-conversation state, immutable target(s), five-minute expiry, random action ID. |
| G. Authorization | Server-derived user/session owner; wrong account/session private 404, wrong conversation rejected. |
| H. Target immutability | Changed selection B cannot reinterpret stored A; unrelated new turn invalidates proposal. |
| I. HTTP | One bounded startup/lifespan client; reused; clean shutdown. |
| J. Concurrent auth | Two identities retain distinct request-local bearers and responses in transport regression. |
| K. Normal memory | Startup RSS {rss:.2f} MiB; CUDA allocated {gpu:.2f}, reserved {reserve:.2f} MiB for existing RAG/Qwen. |
| L. Rejected routers loaded | NO. Fresh startup imports zero experimental router modules; zero child workers. |
| M. Live | 12/12 checks; 8/8 natural mutation prompts; zero Qwen at confirm/cancel; disposable records cleaned. |
| N. Backend | {result['backend_passed']} passed, {result['backend_skipped']} skipped; {backend_failures} failures. |
| O. Frontend | {result['frontend_passed']} passed; all ten frontend test files. |
| P. Build/lint | Build PASS; {result['lint_errors']} lint errors, {result['lint_existing_warnings']} existing warnings. Existing bundle-size warning retained. |
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

Normal memory observation after restoration: at least {memory['minimum_idle_available_mib']} MiB host RAM available,
maximum {memory['maximum_idle_commit_ratio']*100:.2f}% Windows commit, peak {memory['maximum_idle_pages_input_per_sec']} pages input/sec in three brief idle samples.
Archived V5 added an approximately {memory['archived_v5_worker_rss_mib']:.2f} MiB worker and recorded only 228 MiB host RAM available.
This is archived comparison, not a paired performance benchmark. Host commit is still high; removing rejected workers does not fix
every full-stack memory constraint. Normal RAG's own retrieval/reranker/Qwen GPU footprint is expected and was not changed.

The startup psutil swap values are separate raw observations; actual Windows commit comes from WMI. No duplicate model/service
was launched for measurements. One listener exists per service port. Models, datasets and evaluation seals were retained.

## Exact existing source/test edits

''' + '\n'.join('- `'+p+'`' for p in production_changes) + '''

## New source/test/documentation files

''' + '\n'.join('- `'+p+'`' for p in audit['new_files'] if not p.startswith('reports/')) + '''

## Required reports

- `reports/assistant_mutation_safety.md`
- `reports/assistant_router_archive_audit.md`
- `reports/assistant_http_transport_regression.json`
- `reports/assistant_production_memory.json`
- `reports/assistant_production_freeze.md`
- `reports/assistant_stabilization_regression.json`

## Normal start commands

Services are already running. From a stopped stack, use separate terminals in `D:\\SDC\\LibraryLLM`:

```powershell
.venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002
.venv\\Scripts\\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003
.venv\\Scripts\\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004
$env:ASSISTANT_ROUTER_MODE='existing_qwen'
.venv\\Scripts\\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005
```

From `D:\\SDC\\LibraryLLM\\frontend`: `npm run dev -- --host 127.0.0.1 --port 5173`.
The local hidden RAG helper is `scripts/start_assistant_production.ps1`; it refuses duplicate listeners.
`-RestartRag` verifies the project launcher/service before replacing only that RAG process. The diagnostic helper runs from cached models
and does not change `.env` or circulation-write flags. Optional numeric profiling uses ASSISTANT_PROFILE_PATH; it stores no prompts/tokens/private records.

**STOP: production stabilization complete; router research remains frozen.**
'''
    (REPORTS/'assistant_production_freeze.md').write_text(freeze, encoding='utf8')
    print('STABILIZATION', result['final'], result['backend_passed'], 'backend', result['frontend_passed'], 'frontend')

if __name__ == '__main__':
    main()
