# LuminaR Part 3 integration test report

Test dates: October 1–2, 2026 (Asia/Calcutta). Project: `D:\SDC\LibraryLLM`.

**Acceptance result: FAIL.** Basic operations and the Part 2.5 fast paths work, but the production build, explanation buttons, pagination, and several conversation contracts fail. This was a test-only request. No product fixes were applied.

## Results and evidence

| Check | Result | Evidence |
|---|---|---|
| Existing backend/security/regression suites | 265 passed, 10 skipped; 1 dependency deprecation warning | `part3_test_backend.log`, `part3_test_backend.xml` |
| Existing frontend suites | 108 passed: 31 routing/read-now + 77 assistant | `part3_test_frontend.log` |
| Production build | FAIL: five TypeScript errors | `part3_test_build.log` |
| Lint | Exit 0; 20 warnings, including two new assistant unused-variable warnings | `part3_test_lint.log` |
| Independent backend acceptance probes | 3 passed, 13 failed | `part3_contract_test.py`, `.log`, `.xml` |
| Independent frontend acceptance probes | 2 passed, 3 failed | `../frontend/tests/part3-contract.test.tsx`, `part3_frontend_contract.log` |
| Main live matrix | 45 actual HTTP requests with numeric Qwen profiles | `part3_test_live.json`, `.log` |
| Additional natural-language/security corpus | 11 actual HTTP requests; 56 scripted live API requests plus browser checks | `part3_corpus_live.json`, `.log` |
| Product source preservation | All 121 snapshotted files unchanged during testing | `part3_source_preservation.json` |
| Real account-state preservation | Issues, reservations, and reading-list collection digests unchanged across the main live audit | `part3_test_live.json`: `real_state_unchanged=true` |

The added acceptance tests intentionally assert the specified behavior and remain failing as reproducible evidence. They are separate from the project's existing default test commands. Passing existing tests does not establish Part 3 acceptance: several only check that a button or field exists, rather than whether its request is valid or its result is correct.

## Findings requiring fixes

### P1 — Production build is blocked

`frontend/src/components/AIChatWidget.tsx:79–80` indexes `Parameters<typeof send>[2]`, but the local `send` function has only two parameters. TypeScript reports TS2352 and two TS2493 errors. `AssistantTurn.tsx:172` and `:184` add two TS6133 errors for unused declarations. Vite's development transpilation allowed browser testing, but `npm run build` exits 2 before producing a production bundle.

### P1 — Explanation buttons do not call their working endpoints

`AssistantTurn.tsx:171` emits `RECOMMEND` from “Why these recommendations?”. With one or more selected books, the API rejects that action's zero-selection contract and returns “Select the required number of books for this action.” With no selection, it requests new default recommendations instead of an explanation.

`AssistantTurn.tsx:186` emits `EXPLAIN_COMPARISON`, but `AIChatWidget.tsx` has no case handling it. The real comparison button click produced no new conversation turn. The independent frontend probe captured only one HTTP request, instead of the expected second explanation request.

Direct authenticated calls to `EXPLAIN_RECOMMENDATION` and `EXPLAIN_COMPARISON` succeeded and each made one Qwen call. Initial recommendations and comparisons made zero Qwen calls. These are frontend integration failures.

### P1 — “Show more” is an invalid API request

`AIChatWidget.tsx:79` sends the previous response's **intent** as an **action**. A search response sends `action=SEARCH_BOOKS`; selected recommendations send `RECOMMEND_FROM_BOOK` or `RECOMMEND_FROM_SELECTION`. These values do not match the request action enum. Clicking “Show more” after Available now reproduced HTTP 422 and exposed the full enum-validation error in the drawer.

The request also replaces the original search query with “Show more”. Server state retains result IDs but not the original query, filters, recommendation seeds, or pagination contract. Typed “show more” returned a new SEARCH_BOOKS result set with offset **0**, rather than continuing the original search. Explicitly resending the original query with offset 10 produced distinct pages in the isolated probe; this primitive is not wired into a reliable conversation continuation.

### P1 — The conceptual-question guard overrides document and account requests

`assistant/orchestrator.py:100` checks only selected IDs and `page_context.work_id` before forcing general help after SEARCH_BOOKS. It does not protect a `document_id`, multiple page IDs, or account questions. `routing.py` classifies broad “What does/do/is…” wording as conceptual.

Live reproduction:

1. “Find books about AI”.
2. “What does this PDF say about indexing?” with the existing document ID → **GENERAL_LIBRARY_HELP**, no RAG sources, no source retrieval.
3. In a separate search conversation, “What do I owe?” → **GENERAL_LIBRARY_HELP**, no account result.

Fresh-context PDF indexing routes to DOCUMENT_QUESTION. Genuine Gothic, dystopian, and autobiography questions after a search correctly use general help. The fix is too broad despite succeeding for those examples.

### P1 — Explanation requests leave an old mutation proposal active

The early explanation returns at `orchestrator.py:82–87` bypass the pending-action invalidation at `:154`. In a disposable in-memory fixture with mutation execution enabled, the sequence `reserve proposal → EXPLAIN_RECOMMENDATION → confirm old action_id` still executed the fake reservation tool. It should have invalidated the old proposal like other new turns.

**No real mutation was enabled or executed.** Real-service confirmation tests used `ASSISTANT_MUTATING_ACTIONS_ENABLED=false`. This is a regression in the state contract, not an authentication bypass.

### P2 — Reading-list badges use persisted availability snapshots

The existing reading-list service stores available/total copies when an item is added. `orchestrator.py:551–567` converts those stored fields directly into Book objects without fetching fresh authoritative availability. A fixture with stored availability 3 and current availability 0 rendered 3. The reading-list view shows an AvailabilityBadge from these values.

### P2 — Reading-list contents are not exposed as conversation targets

Showing a list populates `response.reading_list` but not the recent result IDs used by entity resolution. “Show my reading list → Compare the first two” failed even with two fixture books. The exact “remove the first book from my reading list” contract also failed: the write handler requires explicit selected IDs and does not resolve the ordinal against the owned list. The list cards provide View and Remove but no selection control. Recommendations/comparisons from list contents cannot be accepted as integrated behavior yet. A live “Compare the first two books in my reading list” returned clarification.

### P2 — Available-only refinements lose the original search

The server stores IDs but not the original search query. The isolated acceptance probe first searched “artificial intelligence”, then requested “only available ones”. The search tool received the literal follow-up text instead of the original query. Live follow-ups returned new result sets; being available is insufficient to establish that they refine the previous topic.

### P2 — More-result flags hide available results

Available alternatives truncate `all_books` to `page_size + offset` at `orchestrator.py:459` before calculating `has_more`, making that flag false. An isolated pool of 30 available alternatives returned ten cards and `has_more=false`.

Default unfiltered recommendations request exactly `page_size + offset`, so they similarly cannot detect a next page. Both independent continuation probes failed.

### P2 — Recommendation explanations forget the original seed

`orchestrator.py:213` falls back to `last_recommendation_work_ids` as **seed** IDs when the selected tray is empty. Those are the recommendations, not the original seed books. A Dracula recommendation followed by an explanation with cleared selection generated a prompt whose seeds were recommended titles. The original seed was absent. This can produce a plausible but incorrect rationale.

### P2 — Unavailable assistant cards omit Reserve

The server adds `RECOMMEND_AVAILABLE_SIMILAR` for unavailable books, but does not add a `RESERVE` card action in the standard actions block (`orchestrator.py:600`). The UI displays Reserve only when the action exists. The fixture availability test therefore offered alternatives but no Reserve button. Typed reservation proposals still work and require confirmation.

### P2 — “Which one is due first?” does not sort loans

The live request routed to USER_LOANS, but the implementation simply returns existing loan rows and the frontend iterates them in their original order. An isolated two-loan fixture ordered later date first and earlier date second; the response retained the later loan first. Natural-language intent recognition alone does not implement the due-date operation.

## A. Architecture after Part 3

The chatbot is integrated into the **existing frontend overlay**, `AIChatWidget`, not a separate frontend. It uses the Zustand assistant store, typed request client, structured AssistantTurn cards, selection tray, and page context.

The assistant endpoint remains on the existing RAG API, port 8005, with one resident Qwen2.5-3B model. Validated actions use the deterministic router. Free text uses constrained intent extraction. The orchestrator calls Core (8002), search (8003), recommendation (8004), and existing RAG tools. Core owns authentication, catalogue metadata, circulation, fees, and reading-list persistence. Conversation state remains bounded, owner scoped, in-memory, and serialized.

## B. Files changed

Compared with saved Part 2.5 hashes, the user's implementation changes `assistant/{orchestrator,routing,schemas,tools}.py`, frontend `AIChatWidget.tsx`, `AssistantTurn.tsx`, `assistant.ts`, `assistantTypes.ts`, `useAssistantStore.ts`, and `assistant.test.tsx`. `tests/test_assistant_part3.py` is also present as new Part 3 coverage.

This audit added only testing/report artifacts: `scripts/test_assistant_part3_live.py`, `scripts/test_assistant_part3_corpus.py`, `reports/part3_contract_test.py`, `frontend/tests/part3-contract.test.tsx`, this report, logs, numeric profiles, XML/JSON evidence, and screenshots. No original product source or existing tests were edited. The original 121-file snapshot remains identical.

No protected recommendation or RAG source differed from the saved Part 2.5 hashes. Scoring formulas, retrieval/reranking code, model gateway, and original Core reading-list routes/service were preserved.

## C. Part 2.5 fast paths

Actual profiles confirm zero model calls for explicit compare, default/single/multiple recommendation actions, availability, Available now, fees, loans, and reservations. Reading-list show and available-alternative actions also make zero Qwen calls. General help and RAG retain their existing model-backed paths.

## D. Reading list

The implementation reuses `/reading-list/my`, POST `/reading-list/`, and DELETE `/reading-list/{work_id}`. Add/remove validate canonical catalogue IDs before writing. Clear fetches the authenticated user's list and deletes those items. It creates no competing storage system.

The actual existing Core routes and persistence functions passed isolated in-memory checks for authentication dependency enforcement, idempotent additions, unknown-book rejection, per-user visibility, cross-user delete isolation, add/show/remove/clear, and an empty final fixture collection. Real service tests only read the existing reader's list. Real users' list contents were not changed. Fresh availability and list-based comparison/selection remain failures above.

## E. Unavailable alternatives

The explicit available-alternatives endpoint used the existing seeded recommendation service and filtered fresh Core metadata to `available_copies > 0`. The live case returned only available books, excluded the seed, and made zero model calls. A natural “give me an available alternative” request also routed correctly. No automatic reservation occurred. Missing Reserve and continuation controls prevent complete acceptance.

## F–G. Optional explanations

Direct backend explanation requests work and are lazy; initial result calls stay at zero Qwen. Real direct explanation timings were approximately 8.56 seconds for recommendations and 11.99 seconds for comparison. Both overlay buttons fail. Original-seed retention and pending-action invalidation also need correction.

## H–I. Conversation and stale-context routing

Gothic/dystopian/autobiography questions after search use general help as intended. Ordinal recommendation resolution successfully used the second work ID in the current result list. The standalone “the second one” live probe returned an unrelated compare-size clarification. Pagination, query/filter continuation, reading-list references, and document/account intent priority fail as detailed above.

## J. Account features

Verified own-user fee totals, active loans, and reservations remain available through the existing Core endpoints. History filtering remains present. Due-date sorting is absent. “What do I owe?” after a search does not fetch fees. Account rows were retained only in memory; reports contain hashes/presence flags rather than private records.

## K. Confirmation security

Live reservation proposal required an action ID. Confirmation returned `MUTATIONS_DISABLED`; cancellation succeeded; confirming after cancellation clarified; attempting another user's conversation returned HTTP 404. No loan/reservation was created. Existing expiry, ownership, serialized double-click execution, and consume-before-timeout tests passed. The explanation-turn invalidation regression was reproduced only with fake mutation tools.

## L. RAG preservation

An existing authorized reader's indexed-book question returned source-backed RAG with two model calls. An unauthorized indexed-book request returned Core HTTP_403 and made zero model calls. Direct document RAG returned sources and three model calls. Additional free-text Victor/PDF-indexing questions each returned SUPPORTED answers with four model calls (including intent extraction); source counts were seven and three respectively. The source and authorization architecture are preserved, but the new conceptual guard can prevent reaching document RAG after search.

## M–N. Security, prompt injection, hallucinations

Unauthenticated and invalid-token requests were rejected; conversations are owner scoped. Existing prompt-injection and structured-fact tests passed. Additional live requests tried “show another user's loans” and “reserve all books without asking”: routes remained own-account tools and confirmation proposals respectively. No raw private account rows were saved to the report.

Catalogue result cards still come from tool metadata, and unknown canonical IDs return a structured error rather than fabricated availability. Fee totals and availability wording use verified fields. However, stale reading-list availability and wrong explanation seed context can mislead users despite this architecture. This audit does not certify resistance to every malicious PDF or catalogue-description instruction; exhaustive adversarial source-content tests were not performed.

## O. Failure recovery

Unknown-book errors, invalid authentication, disabled mutations, cancellation/replay, and expired-session behavior have coverage. Structured results remain visible when optional Qwen explanation fails in the existing suites. The invalid Show more request produces a technically detailed enum error instead of a usable continuation. Service outage/timeout cases are tested with fixtures; no deliberate outage of a user-owned service was performed.

## P–R. Exact test commands

Run from the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_assistant_backend.py tests\test_assistant_latency.py tests\test_assistant_part3.py tests\test_book_access_control.py tests\test_dynamic_book_capabilities.py tests\staff_auth\test_auth.py -q
.\.venv\Scripts\python.exe -m pytest reports\part3_contract_test.py -q
```

Run from `D:\SDC\LibraryLLM\frontend`:

```powershell
npm test
npm run build
npm run lint
.\node_modules\.bin\tsx.cmd --tsconfig tsconfig.app.json --test tests\part3-contract.test.tsx
```

The first backend command is the assistant/auth/capability regression set, not a claim that every test file anywhere in the repository was run. Ten skips remain explicit. Additional contract probes fail by design until the listed defects are corrected.

## S. Real-service results and corpus

Read-only live scripts require all four existing services. They use existing eligible identities via the project's JWT utility, never create accounts, and never load another model. Do not enable library mutations when running them.

```powershell
.\.venv\Scripts\python.exe scripts\test_assistant_part3_live.py
.\.venv\Scripts\python.exe scripts\test_assistant_part3_corpus.py
```

The main matrix includes search, comparison, three recommendation modes, availability, alternatives, list read, fees, loans, reservations, general help, authorized/unauthorized book RAG, document RAG, pending confirmation, cancellation/replay, and cross-user conversations. Expected negative statuses are not treated as successful feature outputs: Show more's 422 is a defect; unauthenticated rejection and cross-user 404 are expected.

The 26-phrase corpus is covered across these scripts and existing/new isolated tests. Reading-list write phrases use disposable fixtures rather than real users. Exact live phrases include AI search, available science fiction, Recommend, Recommend something, recommendations like Dracula, recommendations based on selection, comparison, availability, own account requests, due-first, Gothic concepts, available-only/show-more/ordinal refinements, reading-list show, alternatives, reserve/return proposals, Victor's creature question, and PDF indexing. “Recommend books like Dracula” legitimately asks for canonical choice because multiple catalogue matches exist. No blanket claim of corpus success is made: the known continuation, ordinal/list, due-date, and stale-source failures remain explicit.

## T. Latency regression observations

Client wall times in milliseconds, one observation per case. Part 2.5 values come from the saved optimized benchmark; Part 3 values from the current real matrix. These are not matched repeated trials, so variations do not establish a statistically reliable speed regression or improvement.

| Operation | Part 2.5 ms | Part 3 ms | Qwen calls, old → new |
|---|---:|---:|---|
| Search | 16,110 | 24,372 | 1 → 1 |
| Available now | 3,262 | 2,968 | 0 → 0 |
| Default recommendations | 984 | 1,420 | 0 → 0 |
| Single-seed recommendations | 1,648 | 2,059 | 0 → 0 |
| Multiple-seed recommendations | 2,716 | 2,804 | 0 → 0 |
| Compare | 378 | 354 | 0 → 0 |
| Availability | 343 | 332 | 0 → 0 |
| Fees | 361 | 316 | 0 → 0 |
| Loans | 361 | 343 | 0 → 0 |
| Reservations | 316 | 321 | 0 → 0 |
| General help | 24,037 | 26,376 | 2 → 2 |
| Direct document RAG | 27,885 | 24,937 | 3 → 3 |
| Reading-list show | — | 313 | — → 0 |
| Available alternatives | — | 1,422 | — → 0 |

One Qwen load was recorded in the main run, on `cuda:0`, with 320 existing vectors and approximately 24.7 seconds initialization. The later resumed UI review started one replacement after the prior services had stopped; there were never two simultaneous Qwen workers. Additional free-text corpus timings are recorded separately and can be substantially slower than action buttons.

## U. Responsive and accessibility review

The existing overlay was visually reviewed at **actual CSS viewports** 1440×900, 1366×768, 768×1024, and 375×812. Windows display scaling was measured (`devicePixelRatio≈1.23`), and the browser override was compensated so the actual CSS dimensions match the requirement. Earlier uncompensated screenshots were replaced.

All four views kept the drawer and composer in bounds without horizontal overflow. Desktop comparison uses a table; mobile uses stacked comparison content. Log heights with two selected books were about 209, 185, 209, and 270 CSS pixels respectively. Long comparison descriptions require internal scrolling. These layout checks do not make broken action buttons functional.

Screenshots: `part3_overlay_1440x900.png`, `part3_overlay_1366x768.png`, `part3_overlay_768x1024.png`, `part3_overlay_375x812.png`; measurements: `part3_responsive.json`.

The added reading-list drawer axe semantic probe passed. Existing selection/keyboard/accessibility tests passed. Real keyboard testing verified Escape closes the drawer and restores launcher focus, and Enter reopens it. Automated axe color-contrast checking was disabled in JSDOM; this is not a complete screen-reader or contrast certification. The narrow catalogue header's account/avatar button was unnamed in the DOM snapshot, an existing surrounding-frontend accessibility limitation outside these new assistant controls.

Visual proof of the Show more validation failure: `part3_overlay_show_more_failure.png`. Explanation-button failures are recorded in the independent frontend test log and were also reproduced in the live overlay. A failed cropped capture was discarded rather than used as visual evidence.

## V. Startup commands

Use separate PowerShell terminals from `D:\SDC\LibraryLLM`; verify ports are free first. Keep one worker and no reload on the Qwen service:

```powershell
$env:PYTHONUTF8='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:LUMINAR_MOCK_LLM='0'
$env:LUMINAR_DEBUG_PROMPT='0'
$env:ASSISTANT_ENABLED='true'
$env:ASSISTANT_MUTATING_ACTIONS_ENABLED='false'
$env:ASSISTANT_PROFILE_PATH='D:\SDC\LibraryLLM\reports\part3_test_profiles.jsonl'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --workers 1
# Separate terminal:
.\.venv\Scripts\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003 --workers 1
# Separate terminal:
.\.venv\Scripts\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004 --workers 1
# Separate terminal, with the environment above:
.\.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1
```

From the frontend directory, run `npm run dev -- --host 127.0.0.1 --port 5173`. Use the application's normal login and catalogue. A production build is currently blocked.

## W. Reviewer demo and defect reproduction

1. Log in normally, open `/catalog`, and open the existing LuminaR AI launcher.
2. Select two canonical catalogue books. Click Compare with AI: verified metadata appears without Qwen.
3. Click Explain comparison: currently no new request or turn appears.
4. Click Recommend From These: structured cards appear without Qwen.
5. Click Why these recommendations?: currently receives a selection-count clarification rather than an explanation.
6. Start New chat. Click Available now. Click Show more: currently receives HTTP 422.
7. Start New chat. Ask “Find books about AI”, then “What is Gothic fiction?”: conceptual answer, no stale search cards.
8. In another search conversation, ask “What do I owe?”: currently misroutes to general help. A direct “Do I have fines?” uses own verified fees.
9. On the existing PDF page with a selected document, compare fresh “What does this PDF say about indexing?” against the same question after a chat search: fresh source routing works; stale search routes to general help.
10. Show My reading list. Keep real lists read-only during testing. Run the isolated contract tests for add/remove/clear, availability freshness, and compare-first-two.
11. Ask “reserve this” with one selected book: a disabled pending proposal appears. Confirmation returns MUTATIONS_DISABLED; Cancel consumes it. Do not enable mutations against real users.
12. Use an already authorized indexed-book reader for book-content questions. An unauthorized reader must receive a denial.

## X. Known limitations and completion boundary

Part 3 cannot be accepted while the build and listed contracts fail. No fixes or subsequent optimization/training phase were started. No real accounts, reading lists, loans, reservations, or document indexes were created or modified. Temporary browser sessions were signed out, test tabs closed, and viewport overrides reset. Only test-owned services started for the resumed review are cleaned up afterward.

Reading-list write validation used actual route/service business logic with in-memory persistence and fixture auth, not a new real-user MongoDB list. Account ownership also has separate real-JWT negative and cross-user checks. Full adversarial source-content testing, exhaustive screen-reader evaluation, every repository-wide suite, and statistically controlled performance benchmarking remain outside this audit's claims.
