# Selected context repair and deterministic natural-language routing

Outcome: PASS for the requested repair, with the pre-existing Book RAG overview-rule failure separately recorded. Local read-only tests and UI validation used one disposable reader; no loan, reservation, reading-list or notification was created.

Original cause and payload: see assistant_selected_context_audit.md. Frontend typed requests were correct. Backend model-generated work IDs were treated as titles and semantically searched, producing M68000 clarification.

Before: exact-action/short-phrase fast route, otherwise Qwen; selected pool could be discarded by generated mentioned_titles; retained results could precede page context.

After: explicit action_work_ids (card/clarification arguments) → current selected_work_ids → intentionally named title/work in current text → current page → retained canonical result context → genuine title resolution → clarification. Intentional named titles can override selection; mixed named/plural questions stay with Qwen/clarification. Ordinals retain their existing authoritative list validation.

Singular references bind one selected work; multiple selected works plus singular language clarify. Plural references bind all current selections. Both/the two/these two require exactly two. Zero selections can use an authoritative current/retained set; one-book plural comparison asks for another selection. No count guessing. For More Like This, multiple selections always clarify even with a current page book; clicked card action_work_ids provides an explicit single target.

Closed deterministic grammars cover the reported comparison and differnces typo; selected recommendations; Core availability (can I borrow these is an availability question, not a mutation); catalogue details/authors/subjects; existing KG More Like This; account loans, fees, reservations, history; bounded simple Search noun phrases. Complex fit/advice/reasoning, mixed requests, unsupported qualifiers and title comparisons continue to Qwen. Optional Explain Comparison remains Qwen-backed. Unicode/whitespace/case/punctuation normalization is used only for matching; original displayed input remains unchanged.

Frontend: one Zustand tray, send-time snapshot, selected_work_ids always equals visible tray. action_work_ids is a separate optional field for clicked targets. Explain and paging carry the tray but retain their existing saved result semantics. Same-token same-owner initialization retains selection; auth/account changes clear selection, context, pending responses and abort the in-flight request. Context label states the number selected.

Comparison continues to use the same Core metadata hydration and existing ComparisonView. rating_count is now carried when present. Null descriptions/shelf locations are not invented; no pages/year/language/difficulty fields were added. Recommendation modes, RRF formula, exclusions and ranking algorithms are unchanged.

Telemetry remains internal: route_resolution_ms, qwen_intent_calls, qwen_response_calls, tool_ms, total_ms; numeric-only opt-in profiles and existing trace header. Temporary development request/resolver observers produced explicit evidence and were removed from running services.

## Warm latency (milliseconds; two repetitions after one per-case warm-up)

| Case | Before median | After median | After min–max | Qwen before → after |
|---|---:|---:|---:|---|
| compare | 11882.6 | 358.0 | 332.8–383.3 | [1, 1] → [0, 0] |
| compare_typo | 12389.9 | 367.4 | 359.5–375.3 | [1, 1] → [0, 0] |
| compare_short | 365.2 | 396.1 | 378.8–413.3 | [0, 0] → [0, 0] |
| availability | 4517.1 | 421.3 | 397.3–445.2 | [1, 1] → [0, 0] |
| recommend | 17638.4 | 2070.6 | 2047.6–2093.5 | [2, 2] → [0, 0] |
| fees | 317.5 | 321.4 | 312.1–330.7 | [0, 0] → [0, 0] |
| loans | 329.1 | 342.3 | 336.6–348.0 | [0, 0] → [0, 0] |
| reservations | 3337.8 | 316.2 | 310.4–322.0 | [1, 1] → [0, 0] |
| more_like_this | 1770.4 | 1614.9 | 1561.3–1668.5 | [0, 0] → [0, 0] |
| simple_search | 1125.7 | 1201.6 | 1122.1–1281.1 | [0, 0] → [0, 0] |
| complex_search | 6859.7 | 6509.8 | 6451.6–6568.0 | [1, 1] → [1, 1] |
| general_help | 3875.2 | 3674.0 | 3422.4–3925.6 | [1, 1] → [1, 1] |
| ambiguous | 48599.5 | 48078.9 | 46117.6–50040.2 | [2, 2] → [2, 2] |

Comparison baseline was an incorrect clarification; the improvement includes correct behavior, not just faster failure. Complex queries still used Qwen (one intent, and two total for the fit/advice query). General-help benchmark deliberately included an unrelated page book; the existing classifier still chose SEARCH_BOOKS. General help without stale source context is covered by existing regressions; this phase does not retune that model behavior. Latency is a small local sample and varies with service load/cache.

## Validation

Browser scenarios in assistant_selected_context_live.json: exact/typo/short comparison; multi-seed recommendation; selected availability; one-book clarification without choices; reload preserves same-owner selection; newly selected OL20054823W + OL17950564W replace the original pair; final normal-worker comparison with current-page context and rating counts. Request evidence: assistant_selected_browser_requests.jsonl; numeric model traces: assistant_selected_after_profiles.jsonl.

Backend core/assistant/Search/recommendation-paging/security regression: 517 passed, one pre-existing Book RAG overview-rule failure. Separate staff auth: 76 passed. Notification + renewal: 91 passed. Combined mock staff and real Mongo suites interfere with imports, so those suites were rerun in separate processes as their fixture instructions require. Frontend assistant/selection/KG/paging/admin/renewal: 137 passed. Production build passed. Lint: 0 errors, 19 existing warnings; production chunk-size warning remains.

Two old assertions were updated deliberately: the latency test expected obsolete candidate depth 11, although the frozen baseline already uses 50; the document-latency test froze all assistant routing, now replaced with its document-route behavioral contract while every RAG pipeline/security source hash remains checked. The comparison metadata regression now explicitly requests page count/availability in its message so it exercises semantic unsupported-field handling rather than the new unqualified fast route.

Known unrelated failure: tests/test_rag_query_types.py::test_overview_rule_never_accepts_added_premises[What are the major themes of this book?]. No RAG tuning/model/settings change was made. Unchanged application hashes: assistant_selected_scope_preservation.json.

## Exact files changed

- assistant/contextual.py
- assistant/routing.py
- assistant/kg_routing.py
- assistant/orchestrator.py
- assistant/profiling.py
- assistant/schemas.py
- frontend/src/App.tsx
- frontend/src/store/useAssistantStore.ts
- frontend/src/lib/assistant.ts
- frontend/src/lib/assistantTypes.ts
- frontend/src/components/AIChatWidget.tsx
- frontend/src/components/MoreLikeThisSection.tsx
- tests/test_assistant_selected_context.py
- tests/test_assistant_backend.py
- tests/test_assistant_latency.py
- tests/test_document_rag_latency.py
- frontend/tests/assistant.test.tsx
- frontend/tests/kg-product.test.tsx
- .gitignore
- scripts/run_selected_context_service.py
- scripts/benchmark_selected_context.py
- scripts/report_selected_context.py

## Start commands

From D:\SDC\LibraryLLM, each in its own terminal:
```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --workers 1
.\.venv\Scripts\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003 --workers 1
.\.venv\Scripts\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004 --workers 1
.\.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Optional telemetry before starting RAG: $env:ASSISTANT_PROFILE_PATH = "D:\SDC\LibraryLLM\reports\assistant_request_profiles.jsonl". Never start another worker on an occupied port. Services were returned to normal modules/configuration after the audit.

Limits: fixed high-precision English grammars and one bounded typo correction, not a general spellchecker; mixed named/plural expressions fall back; no subjective recommendation/model quality guarantee; existing single-worker TTL conversation state and auth-session selection policy remain. Source snapshots provide the baseline because this checkout has no .git directory.
