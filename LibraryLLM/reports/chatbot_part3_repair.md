# LuminaR Part 3 repair and latency completion

Project: `D:\SDC\LibraryLLM`. October 2, 2026, Asia/Calcutta.

## A. Final acceptance

**Functional acceptance: PASS. Performance: PARTIAL.** All confirmed Part 3 defects are repaired in the existing frontend overlay. The build, required regressions and independent contracts pass. Fifteen benchmark operations meet the 15-second target in every measured run; Document RAG remains above it with its original evidence checks intact. No Part 4 work was started.

The failed audit was reproduced and saved before repair: five TypeScript errors, 265 passing backend tests with 10 skips, 108 passing frontend tests, 13 failing independent backend probes and three failing independent frontend probes. The correctness gate passed before latency changes: 298 backend/contract checks plus 10 skips, 111 frontend tests, five independent frontend probes, and production build. The final expanded backend suite passes 336 checks plus 10 skips.

## B. Build and lint

`npm run build`: PASS, TypeScript and Vite production output. `npm run lint`: exit 0, 18 existing warnings; both introduced assistant unused-variable warnings are removed. No new product-assistant warnings remain; the byte-unchanged independent frontend test still has an unused import warning. See `part3_repair_final_build.log` and `part3_repair_final_lint.log`.

## C. Each original defect and repair

| Original defect | Repair and evidence |
|---|---|
| Five TypeScript failures | Shared typed SendOptions; valid action unions; removed unused explanation declarations and double casts. Production build passes. |
| Why recommendations sent RECOMMEND | It sends EXPLAIN_RECOMMENDATION, the conversation ID and empty current selection. Original seed IDs and recommendation mode stay on the server. |
| Explain comparison did nothing | Typed EXPLAIN_COMPARISON traverses ComparisonView, AssistantTurn, widget, store and API. Original comparison IDs and requested fields survive tray changes. |
| Show More sent intents as actions / lost query | Dedicated SHOW_MORE literal, strict intent rejection, server-owned ResultContext, query/filter/mode/seed preservation, monotonic offset and delivered-ID exclusion. Historical buttons are disabled. |
| Available alternatives/default has_more false | Alternatives retain the full bounded pool; default recommendations fetch offset + page size + 1. No ranking/scoring formula changed. |
| Recommendation continuation unavailable | Same cached seed rankings and RRF fusion, up to 50 candidates per seed / 200 merged; default depth expands through the existing API up to 50. Fresh metadata and availability on every page. |
| Available-only follow-up became a new search | Conservative refinement clones the original context/query and rehydrates facts. Same author uses a known single author or asks for clarification; different author preserves original seed authors. |
| Concept guard overrode PDF/account requests | Explicit actions, current source context, account phrases and clear book questions take precedence. Genuine concepts bypass extraction; background catalogue results do not add a model pass. |
| Explanations left old confirmations live | Pending state, issue binding and deadline are cleared centrally before every ordinary early-return path, including both explanations and continuation. Replay is rejected. |
| Reading-list availability stale | Owned stored canonical IDs are rehydrated through Core; persisted copy counts are not used as current facts. |
| Reading-list items not referenceable/selectable | Ordered owned IDs become active recent results; shared BookSelectButton feeds the existing global tray. An explicit empty active set blocks older comparison, client and background-page references, while fresh explicit selection still works. Explanations restore their displayed result IDs after a pending proposal. First-two and individual ordinals work in fixtures. |
| Ordinal removal used selection / failed | Ordinals resolve against the last owned list order, with current server-side membership and canonical catalogue validation before owned deletion. |
| Unavailable cards omitted Reserve | Fresh unavailable cards offer both Reserve and Available Alternatives. A Reserve card creates an owner-scoped disabled proposal, never a direct reservation. |
| Due-first returned source order | Active loans sort by parseable actual due date, with unknown dates last and stable ties; deterministic earliest title/date message. Empty/unparseable cases are explicit. |
| Additional live stale Reserve intent | Closed card proposal wording binds BORROW/RESERVE/RETURN intent before model extraction; catalogue checks, ownership, disabled flag and confirmation remain unchanged. |
| Additional ordinal comparison prose | Exact first-two/three/four comparison wording uses verified comparison cards without automatic synthesis. The populated-list fixture asserts zero response generations; the real overlay repeat confirms the structured result. |

## D. Backend regressions

Required six-suite command: **265 passed, 10 skipped** (`part3_repair_final_backend_required.log`). Expanded command with 55 new repair checks and 16 independent contracts: **336 passed, 10 skipped** (`part3_repair_final_backend_all.log`). The one warning is FastAPI/Starlette's httpx deprecation, present before repair. No model was loaded by these tests. Enabled mutation tests use isolated fake tools/collections only. The ten existing skips require the opt-in live-write flag LUMINAR_RUN_BOOK_INTEGRATION=1, which was not enabled.

## E. Frontend regressions

`npm test`: **111 passed**, comprising 31 routing/read-now tests and 80 assistant tests. New HTTP assertions exercise typed explanation payloads, cleared/changed tray, SHOW_MORE query/offset/no tray, historical continuation disabling, reading-list selection and empty-reference reset. Existing axe checks pass. The real overlay was also checked in all four requested viewport sizes; see `part3_repair_browser_checks.json` and screenshots.

## F. Independent contracts and test consistency

Backend: **16 passed**. Frontend: **5 passed**, with `frontend/tests/part3-contract.test.tsx` byte-identical to baseline.

Exactly one independent backend assertion changed: the failed audit accepted `action=SEARCH_BOOKS`, while this request explicitly forbids using an intent as an action and requires dedicated SHOW_MORE. It now accepts SHOW_MORE and rejects SEARCH_BOOKS, RECOMMEND_FROM_BOOK and RECOMMEND_BOOKS. The original test was reconstructed exactly and its SHA-256 verified against the pre-repair manifest at `part3_repair_baseline/source/reports/part3_contract_test.py`. Every other independent assertion is unchanged.

Existing backend tests had three contract-required expectation updates: the initial recommendation count increases 5→6 / 10→11 for one-candidate lookahead; simple search extraction count decreases 1→0; clear general-help extraction decreases 1→0 while the response remains exactly one call. Verified results and no-extra-prose assertions remain, with stronger canonical result/query and intent checks. Originals remain in the source baseline. No original failure reports or logs were overwritten.

## G–H. Qwen calls and final warm latency

Three real sequential warm requests per operation, no concurrent model workers, mock LLM disabled. Model startup and preliminary warmup requests are excluded. Before means the repaired functional baseline, not the earlier failed Part 3 audit. Timings are actual HTTP wall times. Tool ms excludes nested RAG model generation; early explanations use measured Core metadata wall. Complete inclusive stages and tensor-observed token counts are in `chatbot_part3_latency_final.json` and the raw JSONL profiles. Overlapping stage timers must not be added together.

| Operation | Before median s | Min s | Median s | Max s | Calls before → after | Tool ms | Model ms | ≤15s median |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Simple Search | 20.80 | 1.21 | 1.27 | 1.34 | 1 → 0 | 954 | 0 | PASS |
| Complex Search | 18.02 | 10.97 | 11.50 | 13.49 | 1 → 1 | 917 | 10325 | PASS |
| General Help | 24.36 | 5.92 | 6.76 | 7.34 | 2 → 1 | 0 | 6473 | PASS |
| Explain Recommendation | 8.29 | 10.95 | 11.85 | 13.26 | 1 → 1 | 135 | 11417 | PASS |
| Explain Comparison | 11.71 | 6.14 | 6.87 | 7.28 | 1 → 1 | 51 | 6495 | PASS |
| Book RAG | 6.45 | 6.16 | 7.14 | 7.34 | 2 → 2 | 418 | 6159 | PASS |
| Document RAG | 26.11 | 24.60 | 25.24 | 28.16 | 3 → 3 | 63 | 24901 | OVER |
| Default Recommendation | 0.73 | 0.72 | 0.72 | 0.73 | 0 → 0 | 432 | 0 | PASS |
| Single Recommendation | 1.51 | 1.27 | 1.30 | 1.50 | 0 → 0 | 1009 | 0 | PASS |
| Multi Recommendation | 2.51 | 2.31 | 2.38 | 2.59 | 0 → 0 | 2091 | 0 | PASS |
| Compare | 0.36 | 0.32 | 0.34 | 0.37 | 0 → 0 | 48 | 0 | PASS |
| Availability | 0.33 | 0.31 | 0.32 | 0.34 | 0 → 0 | 26 | 0 | PASS |
| Fees | 0.30 | 0.30 | 0.31 | 0.32 | 0 → 0 | 12 | 0 | PASS |
| Loans | 0.35 | 0.33 | 0.33 | 0.35 | 0 → 0 | 36 | 0 | PASS |
| Reading List | 0.31 | 0.31 | 0.31 | 0.38 | 0 → 0 | 12 | 0 | PASS |
| Available Alternatives | 1.31 | 1.30 | 1.34 | 1.56 | 0 → 0 | 1043 | 0 | PASS |

The prompt-only intermediate trial is retained at `part3_repair_latency_trial1_raw.json`: shortening input alone left complex extraction around 21.6 seconds. Compact internal intent keys/codes then reduced the measured output, while mapping into the full unchanged strict Pydantic contract. HTTP request/response keys did not change. Optional fields/defaults remain Python-owned. Intent generation cap is 180 tokens, response cap 160, with the existing repair/clarification fallback for invalid output.

The stronger recommendation-explanation grounding instructions did not improve every timing: its median rose from 8.29s to 11.85s. Its one-call contract and all three sub-15-second observations still hold. No timing regression is hidden.

## I. Operations at or below 15 seconds

Simple Search, Complex Search, General Help, Explain Recommendation, Explain Comparison, Book RAG, Default Recommendation, Single Recommendation, Multi Recommendation, Compare, Availability, Fees, Loans, Reading List, Available Alternatives. Simple Search also meets the 5-second target. Fast structured operations remain below 5 seconds in all three runs; their observed times are shown above without artificial delay.

## J–K. Remaining Document RAG blocker and correctness

Document RAG's three calls are internal semantic classification, evidence validation and grounded generation. It already skips assistant extraction and response generation. Source context establishes the route, but does not establish the semantic actor/action/polarity used by retrieval or validate evidence support. Deleting either required stage would change the accepted RAG behavior. Its semantic input is already small; its complete grounded answer is concise. Lowering the output cap cannot accelerate calls that already finish below that cap, and forced truncation can lose qualifications or stop the answer mid-sentence.

No RAG prompt, semantic classifier, retrieval, embedding, index, chunks, reranker, accepted evidence logic, source authorization or answer generation code was changed. This is the correctness-preserving stop required by Phase 39. The observed fastest Document RAG request is 24.60s; this is an empirical lower bound for these runs, not a universal hardware limit. Exact model calls follow; the small residual is retrieval, authorization and serialization, with full stage timers in the JSON.

| RAG | Run | Call purpose | Input tokens | Output tokens | Generation s |
| --- | --- | --- | --- | --- | --- |
| Book RAG | 1 | Evidence validation | 2070 | 19 | 3.069 |
| Book RAG | 1 | Grounded answer | 4528 | 14 | 3.090 |
| Book RAG | 2 | Evidence validation | 2070 | 19 | 2.711 |
| Book RAG | 2 | Grounded answer | 4528 | 14 | 2.775 |
| Book RAG | 3 | Evidence validation | 2070 | 19 | 3.061 |
| Book RAG | 3 | Grounded answer | 4528 | 14 | 3.377 |
| Document RAG | 1 | Semantic intent classification | 443 | 63 | 12.156 |
| Document RAG | 1 | Evidence validation | 676 | 12 | 1.671 |
| Document RAG | 1 | Grounded answer | 1712 | 107 | 13.922 |
| Document RAG | 2 | Semantic intent classification | 443 | 63 | 10.474 |
| Document RAG | 2 | Evidence validation | 676 | 12 | 1.418 |
| Document RAG | 2 | Grounded answer | 1712 | 107 | 12.335 |
| Document RAG | 3 | Semantic intent classification | 443 | 63 | 11.357 |
| Document RAG | 3 | Evidence validation | 676 | 12 | 1.502 |
| Document RAG | 3 | Grounded answer | 1712 | 107 | 12.041 |

All six measured book/document answers retain SUPPORTED verdicts and seven returned source citations. Book sources are isolated to the authorized selected canonical work, and document sources remain within the chosen existing PDF. The sampled book answer identifies Victor Frankenstein; the PDF answer explains RBAC using its retrieved role examples. Unauthorized book requests are denied before generation.

## L. Security and preservation

Real mutations stayed disabled for every worker. Issues, reservations and reading-list collection digests match before/after baseline, intermediate trial and final validation. No real reading-list writes occurred. Authentication, active-loan entitlement, reservation FIFO, fees/history ownership, conversation TTL/ownership and confirmation execution logic were retained. Live anonymous and malformed-token requests return 401; another user's conversation returns privacy-preserving 404 with zero model calls; unauthorized selected book returns HTTP_403; unknown catalogue IDs fail safely. Enabled confirmation, replay, expiry, pending invalidation and list writes run only against disposable fixtures.

The 185-file pre-repair source manifest and 215 existing report hashes are at `part3_repair_baseline/manifest.json`. `part3_repair_integrity.json` confirms only the documented independent-test exception among existing reports. Protected RAG and recommendation hashes / AST checks pass in the existing backend suite. All prior Part 1/2/2.5/failed-Part-3 report evidence remains unchanged. Numeric profiles retain no credentials, raw private prompts or account rows.

## M. Files changed

Existing source/test files:

- `assistant/orchestrator.py`
- `assistant/qwen.py`
- `assistant/routing.py`
- `assistant/schemas.py`
- `assistant/state.py`
- `frontend/src/components/AIChatWidget.tsx`
- `frontend/src/components/assistant/AssistantTurn.tsx`
- `frontend/src/lib/assistantTypes.ts`
- `frontend/src/store/useAssistantStore.ts`
- `frontend/tests/assistant.test.tsx`
- `tests/test_assistant_backend.py`
- `tests/test_assistant_latency.py`

Independent-test exception: `reports/part3_contract_test.py`. New code/evidence helpers: `tests/test_assistant_part3_repair.py`, `scripts/part3_repair_services.ps1`, `scripts/test_assistant_part3_repair_live.py`, `scripts/report_assistant_part3_repair.py`, the baseline, logs, profiles, browser screenshots and these two requested final reports. Built frontend output is regenerated. No dependencies were installed or changed.

## N. Real-service results

All 48 measured requests succeeded with no assistant errors. Each benchmark category has three observations. Additional live checks:

| Live check | Result |
| --- | --- |
| continuation_setup | PASS |
| continuation | PASS |
| available_only_refinement | PASS |
| recommendation_continuation_setup | PASS |
| recommendation_continuation | PASS |
| concept_after_search | PASS |
| pdf_after_search | PASS |
| fees_after_search | PASS |
| due_first | PASS |
| unauthenticated | PASS |
| invalid_token | PASS |
| unknown_book | PASS |
| cross_user_conversation | PASS |
| reserve_disabled | PASS |
| confirm_disabled | PASS |
| pending_before_explanation | PASS |
| explanation_invalidates_pending | PASS |
| old_confirmation_replay | PASS |
| unauthorized_book_rag | PASS |

The repaired baseline and first intermediate trial correctly returned 404 for cross-user conversations; their harness predicate incorrectly expected 403 and was corrected to the existing privacy contract. This is a harness failure, not a source-authorization defect. The first trial also found the real stale Reserve-intent defect, repaired and revalidated subsequently. Browser review of the second trial found a comparison inference that treated unlisted topics as absent. Both explanation prompts now explicitly distinguish unknown coverage from negative facts, require tentative interpretations, and treat metadata as data. The model still repeated an unsupported absence claim with missing descriptions, so the final comparison path deterministically returns verified authors/shared subject values plus an explicit unknown-content statement for that case. It retains the optional one-generation contract but does not expose the unsupported prose. An adversarial fake-output test and a real browser repeat verify this safeguard. Both intermediate raw datasets and the quality-trial numeric profiles remain available. Existing live reading-list data is empty, so populated-list comparison/removal/freshness scenarios use isolated fixtures; no real list content was created for testing.

Runtime: NVIDIA GeForce RTX 5060 Laptop GPU, luminar_sdpa, 2.11.0+cu128, 5.15.1, CUDA 12.8; cached Qwen2.5-3B-Instruct NF4 with KV cache and the shared inference lock. One worker/model existed at a time. Six controlled worker replacements (seven sequential workers) were needed to load successive code versions; each predecessor was stopped before replacement, and benchmark phases reused their one resident worker. The sparse-metadata and reference-handling browser observations preceding the final ordinal fix are preserved as reference_trial and ordinal_trial profiles. Plain first-two/three/four comparisons now stay structured rather than adding automatic prose; interpretation remains available via Explain comparison. Startup timing is excluded. No downloads, model replacement, retraining, torch.compile or new inference framework.

## O. Exact start commands

From `D:\SDC\LibraryLLM` in PowerShell, with ports free:

```powershell
$env:PYTHONUTF8='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:ASSISTANT_ENABLED='true'
$env:ASSISTANT_MUTATING_ACTIONS_ENABLED='false'
$env:LUMINAR_MOCK_LLM='0'
$env:LUMINAR_DEBUG_PROMPT='0'
.\scripts\part3_repair_services.ps1 -Phase local
```

That starts exactly one worker each for `backend.main:app` (8002), `search.api:app` (8003), `recommendation.api:app` (8004), and `rag.api:app` (8005), using `.venv\Scripts\python.exe -m uvicorn MODULE --host 127.0.0.1 --port PORT --workers 1`, and refuses occupied ports. In a frontend terminal:

```powershell
Set-Location D:\SDC\LibraryLLM\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`, sign in through the existing login and use the existing LuminaR overlay. Local-phase logs do not overwrite benchmark/audit evidence.

Review cleanup is complete: all owned backend/Vite processes stopped, the five review ports are free, temporary local session files are removed, the browser was signed out, its temporary tab closed and viewport override reset. See `part3_repair_cleanup.json`.

## P. Known limitations

- Document RAG remains above 15 seconds for the measured question; all original grounding stages are preserved. No claim of an all-operation latency pass.
- Bounded continuation: at most 50 search/default candidates, and up to 200 fused candidates for four recommendation seeds. No promise of results beyond the actual API pool. State remains owner-scoped, in-memory, TTL-bounded and lost on worker restart.
- Complex/ambiguous phrasing, short acronyms, unsupported filters and multi-operation requests fall back to Qwen/clarification. A failed compact output may still use the original repair attempt; the measured complex searches each use one call.
- Same-author refinement only uses one verified shared author or an existing author filter; ambiguity asks for clarification. Availability changes between pages are freshly applied and may reduce a page's length.
- The existing live reader's list is empty. Populated-list operations and enabled mutation execution were exercised only with isolated fixtures.
- Ten pre-existing live-write integration skips and 18 existing lint warnings remain, including an unused import in the unchanged independent frontend test; they were not concealed or converted to passes. The production build passes.
- For comparisons with missing descriptions, one optional model generation is still measured, but the displayed explanation uses verified authors/shared recorded subjects and explicitly unknown detailed coverage.
