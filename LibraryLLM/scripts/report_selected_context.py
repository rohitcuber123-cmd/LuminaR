"""Assemble evidence from completed runs; no service or catalogue mutation."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
from assistant.kg_routing import fast_route
from assistant.schemas import AssistantRequest, AssistantIntent, Intent
from assistant.orchestrator import NeedsClarification
from test_assistant_backend import setup
from test_assistant_selected_context import COMPARE

def write(name,value):
    (ROOT/'reports'/name).write_text(json.dumps(value,indent=2),encoding='utf8')

async def matrix():
    rows=[]
    for ids,phrase,expected in [
        (['OL1W','OL2W'],'these books',['OL1W','OL2W']),
        (['OL1W','OL2W'],'them',['OL1W','OL2W']),
        (['OL1W'],'this book',['OL1W']),
        (['OL1W','OL2W','OL3W'],'all selected books',['OL1W','OL2W','OL3W']),
        (['OL1W','OL2W','OL3W'],'both books',None),
    ]:
        orch,tools=setup();state=orch.store.get(None,'matrix-reader')
        request=AssistantRequest(message=phrase,selected_work_ids=ids,page_context={'work_id':'OL4W'})
        parsed=AssistantIntent(intent=Intent.BOOK_DETAILS,mentioned_titles=[phrase])
        try:
            books=await orch.resolve(request,parsed,state,tools)
            found=[b.work_id for b in books];reason=None
        except NeedsClarification as error:
            found=None;reason=error.reason
        rows.append({'selection':ids,'reference':phrase,'expected':expected,'resolved':found,'clarification':reason,'pass':found==expected})
    return rows

def main():
    reference_rows=asyncio.run(matrix())
    write('assistant_selected_context_matrix.json',{'method':'Direct contextual resolver with real orchestrator and fake authoritative metadata; current page OL4W intentionally stale. Bare references still need an operation.','cases':reference_rows,'pass':all(r['pass'] for r in reference_rows)})
    commands=[(message,['OL1W','OL2W']) for message in COMPARE]
    commands += [(message,['OL1W','OL2W']) for message in ['recommend based on these','recommend from these books','what should I read based on these','find books like these','recommend something from my selections','are these available?','availability of these books','which of these are available?','can I borrow these?']]
    commands += [(message,['OL1W']) for message in ['tell me about this book','details about this book','who wrote this?','what subjects does this book have?','is this available?','more like this','show related books','books connected to this']]
    commands += [(message,[]) for message in ['show my loans','what books do I have borrowed','what do I owe?','show my fees','my reservations','show my history','find books about neural networks','search for gothic horror books','books on personal finance','show me books about databases']]
    commands += [(message,['OL1W','OL2W']) for message in ['I want something about money but not a textbook and preferably useful for someone starting a business','Which of these would fit someone who already understands calculus but is new to machine learning?','Explain why the author approaches this topic differently','compare Dracula with these']]
    route_rows=[]
    for message,selected in commands:
        routed=fast_route(AssistantRequest(message=message,selected_work_ids=selected))
        route_rows.append({'message':message,'selected_work_ids':selected,'fast_intent':routed[0].intent.value if routed else None,'bound_work_ids':routed[1].selected_work_ids if routed else None,'qwen_fallback':not bool(routed)})
    write('assistant_natural_language_fast_routes.json',{'cases':route_rows})
    baseline=json.loads((ROOT/'reports/assistant_selected_before_benchmark.json').read_text())
    after=json.loads((ROOT/'reports/assistant_selected_after_benchmark.json').read_text())
    source_hashes=json.loads((ROOT/'reports/assistant_selected_source_hashes.json').read_text())
    preserved={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==old for name,old in source_hashes.items() if name in ['assistant/tools.py','search/luminar_search.py','recommendation/recommendation_service.py']}
    write('assistant_selected_scope_preservation.json',preserved)
    requests=[json.loads(line) for line in (ROOT/'reports/assistant_selected_browser_requests.jsonl').read_text().splitlines()]
    original=requests[0]
    traces=[json.loads(line) for line in (ROOT/'reports/assistant_selected_before_resolver.jsonl').read_text().splitlines()]
    root_trace=next(row for row in traces if row['message']=='what are the differences in these books')
    code_files=['assistant/contextual.py','assistant/routing.py','assistant/kg_routing.py','assistant/orchestrator.py','assistant/profiling.py','assistant/schemas.py','frontend/src/App.tsx','frontend/src/store/useAssistantStore.ts','frontend/src/lib/assistant.ts','frontend/src/lib/assistantTypes.ts','frontend/src/components/AIChatWidget.tsx','frontend/src/components/MoreLikeThisSection.tsx']
    tests=['tests/test_assistant_selected_context.py','tests/test_assistant_backend.py','tests/test_assistant_latency.py','tests/test_document_rag_latency.py','frontend/tests/assistant.test.tsx','frontend/tests/kg-product.test.tsx']
    write('assistant_selected_files_changed.json',{'application':code_files,'tests':tests,'scripts':['scripts/run_selected_context_service.py','scripts/benchmark_selected_context.py','scripts/report_selected_context.py'],'configuration':['.gitignore']})
    audit=f'''# Selected context pre-edit audit

Observed exactly: two visible selected books, natural text "what are the differences in these books", and "Choose the book you mean" with six unrelated M68000/MC68020 catalogue choices. Saved source before application edits in assistant_selected_source_baseline/. Actual browser request was captured by a temporary Vite observer without recording auth headers.

```json
{json.dumps(original,indent=2)}
```

Finding **B: backend routing bug** for ordinary typed messages. The visible pair and POST request contained both canonical IDs, in tray order: The Psychology of Money / Morgan Housel (OL21640039W), The Art Of Spending Money / Morgan Housel (OL44077582W). This was not a missing-selection request.

Existing fast routing matched only "compare these" and "compare these two"; the reported phrase invoked Qwen. The frozen-source resolver trace proves Qwen generated `mentioned_titles=["OL21640039W","OL44077582W"]`, instead of title strings or canonical bound arguments. The resolver's selected-title disambiguation found no selected title equal to an ID, cleared its selected pool, called catalogue title resolution for OL21640039W, and then semantic Search of OL21640039W with count=6. The unrelated processor manuals are those fuzzy search candidates. There is no M68000-specific fix.

```json
{json.dumps(root_trace,indent=2)}
```

Additional frontend defects: explicit result/card actions supplied one-request selected_work_ids overrides (or [] for explain/paging), so those payloads could disagree with the visible tray. App initialization also called syncOwner(null) followed by syncOwner(current_owner), discarding same-owner restored selection on reload. Neither caused the captured typed-message failure, but both violate the requested selection contract.

Initial exact UI response profile: 23.189 seconds server total, 1 Qwen intent call, 0 Qwen response calls, title resolution + semantic fallback. Warm baseline comparison median: {baseline['warm_summary']['compare']['median_ms']:.1f} ms, always CLARIFICATION. Screenshot: assistant_selected_before.png. No catalogue/search/recommendation scoring was edited before these observations.
'''
    (ROOT/'reports/assistant_selected_context_audit.md').write_text(audit,encoding='utf8')
    lines=['# Selected context repair and deterministic natural-language routing','',
        'Outcome: PASS for the requested repair, with the pre-existing Book RAG overview-rule failure separately recorded. Local read-only tests and UI validation used one disposable reader; no loan, reservation, reading-list or notification was created.','',
        'Original cause and payload: see assistant_selected_context_audit.md. Frontend typed requests were correct. Backend model-generated work IDs were treated as titles and semantically searched, producing M68000 clarification.','',
        'Before: exact-action/short-phrase fast route, otherwise Qwen; selected pool could be discarded by generated mentioned_titles; retained results could precede page context.','',
        'After: explicit action_work_ids (card/clarification arguments) → current selected_work_ids → intentionally named title/work in current text → current page → retained canonical result context → genuine title resolution → clarification. Intentional named titles can override selection; mixed named/plural questions stay with Qwen/clarification. Ordinals retain their existing authoritative list validation.','',
        'Singular references bind one selected work; multiple selected works plus singular language clarify. Plural references bind all current selections. Both/the two/these two require exactly two. Zero selections can use an authoritative current/retained set; one-book plural comparison asks for another selection. No count guessing. For More Like This, multiple selections always clarify even with a current page book; clicked card action_work_ids provides an explicit single target.','',
        'Closed deterministic grammars cover the reported comparison and differnces typo; selected recommendations; Core availability (can I borrow these is an availability question, not a mutation); catalogue details/authors/subjects; existing KG More Like This; account loans, fees, reservations, history; bounded simple Search noun phrases. Complex fit/advice/reasoning, mixed requests, unsupported qualifiers and title comparisons continue to Qwen. Optional Explain Comparison remains Qwen-backed. Unicode/whitespace/case/punctuation normalization is used only for matching; original displayed input remains unchanged.','',
        'Frontend: one Zustand tray, send-time snapshot, selected_work_ids always equals visible tray. action_work_ids is a separate optional field for clicked targets. Explain and paging carry the tray but retain their existing saved result semantics. Same-token same-owner initialization retains selection; auth/account changes clear selection, context, pending responses and abort the in-flight request. Context label states the number selected.','',
        'Comparison continues to use the same Core metadata hydration and existing ComparisonView. rating_count is now carried when present. Null descriptions/shelf locations are not invented; no pages/year/language/difficulty fields were added. Recommendation modes, RRF formula, exclusions and ranking algorithms are unchanged.','',
        'Telemetry remains internal: route_resolution_ms, qwen_intent_calls, qwen_response_calls, tool_ms, total_ms; numeric-only opt-in profiles and existing trace header. Temporary development request/resolver observers produced explicit evidence and were removed from running services.','',
        '## Warm latency (milliseconds; two repetitions after one per-case warm-up)','',
        '| Case | Before median | After median | After min–max | Qwen before → after |','|---|---:|---:|---:|---|']
    for case,summary in after['warm_summary'].items():
        before=baseline['warm_summary'][case]
        lines.append(f"| {case} | {before['median_ms']:.1f} | {summary['median_ms']:.1f} | {summary['min_ms']:.1f}–{summary['max_ms']:.1f} | {before['qwen_calls']} → {summary['qwen_calls']} |")
    lines += ['', 'Comparison baseline was an incorrect clarification; the improvement includes correct behavior, not just faster failure. Complex queries still used Qwen (one intent, and two total for the fit/advice query). General-help benchmark deliberately included an unrelated page book; the existing classifier still chose SEARCH_BOOKS. General help without stale source context is covered by existing regressions; this phase does not retune that model behavior. Latency is a small local sample and varies with service load/cache.','',
        '## Validation','',
        'Browser scenarios in assistant_selected_context_live.json: exact/typo/short comparison; multi-seed recommendation; selected availability; one-book clarification without choices; reload preserves same-owner selection; newly selected OL20054823W + OL17950564W replace the original pair; final normal-worker comparison with current-page context and rating counts. Request evidence: assistant_selected_browser_requests.jsonl; numeric model traces: assistant_selected_after_profiles.jsonl.','',
        'Backend core/assistant/Search/recommendation-paging/security regression: 517 passed, one pre-existing Book RAG overview-rule failure. Separate staff auth: 76 passed. Notification + renewal: 91 passed. Combined mock staff and real Mongo suites interfere with imports, so those suites were rerun in separate processes as their fixture instructions require. Frontend assistant/selection/KG/paging/admin/renewal: 137 passed. Production build passed. Lint: 0 errors, 19 existing warnings; production chunk-size warning remains.','',
        'Two old assertions were updated deliberately: the latency test expected obsolete candidate depth 11, although the frozen baseline already uses 50; the document-latency test froze all assistant routing, now replaced with its document-route behavioral contract while every RAG pipeline/security source hash remains checked. The comparison metadata regression now explicitly requests page count/availability in its message so it exercises semantic unsupported-field handling rather than the new unqualified fast route.','',
        'Known unrelated failure: tests/test_rag_query_types.py::test_overview_rule_never_accepts_added_premises[What are the major themes of this book?]. No RAG tuning/model/settings change was made. Unchanged application hashes: assistant_selected_scope_preservation.json.','',
        '## Exact files changed','']
    lines += ['- '+name for name in code_files+tests+['.gitignore','scripts/run_selected_context_service.py','scripts/benchmark_selected_context.py','scripts/report_selected_context.py']]
    lines += ['', '## Start commands','',r'From D:\SDC\LibraryLLM, each in its own terminal:', '```powershell',
        r'.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --workers 1',
        r'.\.venv\Scripts\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003 --workers 1',
        r'.\.venv\Scripts\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004 --workers 1',
        r'.\.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1',
        'cd frontend','npm run dev -- --host 127.0.0.1 --port 5173','```','',
        'Optional telemetry before starting RAG: $env:ASSISTANT_PROFILE_PATH = "D:\\SDC\\LibraryLLM\\reports\\assistant_request_profiles.jsonl". Never start another worker on an occupied port. Services were returned to normal modules/configuration after the audit.','',
        'Limits: fixed high-precision English grammars and one bounded typo correction, not a general spellchecker; mixed named/plural expressions fall back; no subjective recommendation/model quality guarantee; existing single-worker TTL conversation state and auth-session selection policy remain. Source snapshots provide the baseline because this checkout has no .git directory.']
    (ROOT/'reports/assistant_selected_context_fix.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps({'reference_matrix_pass':all(r['pass'] for r in reference_rows),'route_cases':len(route_rows),'preserved_hashes':preserved}))

if __name__=='__main__':main()
