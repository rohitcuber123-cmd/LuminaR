# LuminaR chatbot backend — Part 1

Implemented 2026-10-01 in `D:\SDC\LibraryLLM`. Backend only; frontend is unchanged.

## Discovered architecture

| Process | Entry point | Routes used |
|---|---|---|
| Core, 8002 | `backend.main:app` | `/books/{work_id}`, `/issues/my`, `/issues/issue`, `/issues/return/{issue_id}`, `/reservations/my`, `/reservations/`, `/fines/my` |
| Search, 8003 | `search.api:app` | POST `/search` |
| Recommendations, 8004 | `recommendation.api:app` | GET `/recommendations`, new POST `/recommendations/from-book` |
| Existing RAG/Qwen, 8005 | `rag.api:app` | Existing `/rag/ask`, `/rag/upload`, `/rag/documents`, `/rag/books`; new POST `/assistant/chat` |
| Frontend, 5173 | React/Vite | Existing `/rag-api` proxy can reach `/rag-api/assistant/chat` in Part 2 |
| Catalogue | MongoDB `books`, inventory, issues, reservations, fines | Authoritative metadata, canonical `work_id` |

The initial audit is recorded in `reports/assistant_backend_implementation_map.md`. Roles are `GENERAL_USER`, `LIBRARIAN`, and `ADMIN`. `get_current_user` decodes the existing bearer JWT and refreshes identity/eligibility from MongoDB through `current_identity`. The current AIChatWidget is a frontend preview and has no assistant endpoint contract to preserve.

Thirty live Mongo catalogue rows were inspected without changes. Present fields include title, authors, subjects, description, average_rating, rating_count, reading_log_count, shelf_location, total_copies, available_copies, created_at, book_id, and work_id. Page counts, publication years, and languages are absent from this schema. Search has additional indexed metadata, but assistant factual values are rehydrated from Core/Mongo, not taken from model text or stale search metadata.

## Qwen reuse and loading

Exact loader: `rag/llm.py`, `LuminaRLLM.__init__`. Model: `Qwen/Qwen2.5-3B-Instruct`. `AutoTokenizer.from_pretrained` and `AutoModelForCausalLM.from_pretrained` already use `local_files_only=True`. CUDA uses the existing NF4 4-bit configuration; CPU uses the existing float32 path.

`rag.api` creates `engine = LuminaRAG()` once at import; `LuminaRAG.__init__` creates its resident `self.llm` once. The added registration injects this exact `engine.llm` and `engine.inference_lock` into `QwenGateway`. Assistant modules never instantiate LuminaRLLM/LuminaRAG or call a model loader. No new model, external provider, inference process, download, training, chunking or index change was introduced.

Run **one worker**, without `--reload`. Multiple independent Python workers each initialize the existing model loader. The assistant does not solve the pre-existing multiprocess model residency problem.

Intent extraction reuses the existing `_prefix_function` and `generate`. The installed lm-format-enforcer cannot combine a string pattern and length bounds. `AssistantDecodingSchema` removes only that combination in the decoder schema, while full Pydantic validation still enforces both. Validation failure permits exactly one repair; a second invalid JSON result becomes CLARIFICATION. Confidence is advisory, never authorization. For a concrete entity intent, the authoritative resolver checks ambiguity even if Qwen marks clarification_needed; a unique selected/ordinal target can proceed to a read or proposal. Explicit natural-language ordinal tokens also have a literal guard when Qwen omits that field. Ambiguity and entity checks remain server enforced.

Stage two sends verified service results to the same Qwen for explanations. Structured facts are always service derived. Availability messages, fee/account summaries, pending confirmation wording, empty-result messages, and notices for missing comparison fields are rendered from verified fields so generated prose cannot override those operational facts. Other comparison and recommendation explanations remain generated text and subjective inferences are identified in the prompt. Literal availability questions override stale comparison intent from earlier turns; mixed factual/subjective comparisons retain the extracted comparison intent.

## Assistant endpoint and schemas

`POST http://127.0.0.1:8005/assistant/chat`, authenticated with the existing bearer token. Disabled assistant flag returns HTTP 503. Invalid request structure returns 422; unauthenticated requests are rejected by the existing dependency. Normal tool/LLM failures return the stable response with an `errors` list.

Request (`assistant/schemas.py`, `AssistantRequest`):

```json
{
  "message": "Compare these two",
  "conversation_id": null,
  "selected_work_ids": ["OL1W", "OL2W"],
  "recent_work_ids": [],
  "page_context": {"work_id": null, "work_ids": [], "document_id": null},
  "pending_action_id": null,
  "action": null
}
```

Messages are limited to 4,000 characters; selection to four books; recent context to twenty. `page_context` intentionally has a bounded typed contract. Top-level/page-context unknown fields, including `user_id`, are rejected. IDs permit existing safe catalogue identifier syntax, and their actual existence is independently checked through Core. An unknown syntactically valid ID returns a structured Core error; path-shaped IDs fail validation.

`AssistantIntent`: intent, confidence, query, mentioned_titles, mentioned_authors, resolved_work_ids, requested_result_count (1–20), filters, comparison_fields, ordinal_references, reference, requires_confirmation, clarification_needed, unsupported_filters. Supported filters are `available_only`, `author`, `subject`, `exclude_seed_authors`, and `sort_preference` (relevance/title/rating). Unsupported constraints return clarification; beginner-friendly search wording stays in the existing semantic query. Neither missing difficulty/page/year values nor fake filters are synthesized.

Intent enum:

`SEARCH_BOOKS`, `RECOMMEND_BOOKS`, `RECOMMEND_FROM_BOOK`, `RECOMMEND_FROM_SELECTION`, `COMPARE_BOOKS`, `CHECK_AVAILABILITY`, `BOOK_DETAILS`, `BORROW_BOOK`, `RETURN_BOOK`, `RESERVE_BOOK`, `USER_LOANS`, `USER_RESERVATIONS`, `USER_HISTORY`, `USER_FEES`, `GENERAL_LIBRARY_HELP`, `BOOK_CONTENT_QUESTION`, `DOCUMENT_QUESTION`, `CLARIFICATION`, `UNKNOWN`.

Action enum:

`VIEW_BOOK`, `SELECT_BOOK`, `UNSELECT_BOOK`, `COMPARE`, `RECOMMEND_SIMILAR`, `RECOMMEND_FROM_SELECTION`, `CHECK_AVAILABILITY`, `BORROW`, `RESERVE`, `RETURN`, `CONFIRM_ACTION`, `CANCEL_ACTION`.

Response (`AssistantResponse`):

```json
{
  "conversation_id": "server-issued-id",
  "intent": "COMPARE_BOOKS",
  "message": "Explanation from verified metadata",
  "books": [],
  "comparison": null,
  "recommendation_mode": null,
  "seed_work_ids": [],
  "availability": [],
  "actions": [],
  "clarification": null,
  "pending_action": null,
  "account": null,
  "rag": null,
  "errors": []
}
```

Books expose canonical work_id, title, authors, subjects, description, average_rating, shelf_location and optional copy counts. Availability includes work_id, nullable available, nullable available_copies and nullable total_copies. Comparison contains authoritative books, requested_fields, and missing_fields. Clarification contains a reason and structured book choices with SELECT_BOOK actions. Account/RAG results remain structured so the UI need not parse prose.

## Adapters and orchestration

`assistant/tools.py` implements AssistantSearchTool, AssistantRecommendationTool, AssistantCatalogueTool, AssistantAvailabilityTool, AssistantLoanTool, AssistantReservationTool, AssistantFeeTool, and AssistantRAGTool around the existing APIs. Service URLs can be configured through `ASSISTANT_CORE_URL`, `ASSISTANT_SEARCH_URL`, and `ASSISTANT_RECOMMENDATION_URL`; defaults match the verified Vite configuration. HTTP requests forward the original bearer token; no prompt/body user identity is sent.

Exact entity lookup is the new authenticated Core POST `/assistant/catalogue/resolve`. It escapes title/author regex input, returns up to six actual matches, and calls `with_authoritative_availability`. Resolution uses selection, literal IDs, title/author matches, prior result/compared/recommended IDs, page context, then clarification. Ordinals are 1-based in the active selected/recent list. Titles/authors can resolve against known recent books first; otherwise exact catalogue lookup precedes search. Fuzzy search suggestions require a choice unless an exact title/author match is unique. Unknown Qwen-generated IDs are never accepted merely because the model output includes them. Singular “this” with multiple books asks for a choice. All proposed seeds and referenced books are revalidated through Core.

Search calls the existing POST `/search` with `save_history=false`; Qwen supplies only query/filter interpretation. Candidate IDs are rehydrated from Core, deduplicated, filtered against actual fields, and truncated to the requested count. Filtering examines up to fifty search candidates, so a sparse filter can yield fewer than TopN.

Comparison accepts 2–4 verified books. Actual metadata and availability are returned verbatim through typed models; fields absent from the catalogue appear in missing_fields. Qwen can infer subjective suitability from verified descriptions/subjects but cannot populate missing structured values.

Core `get_book_by_work_id` already calls authoritative availability. `LIB001` physical inventory takes precedence over the catalogue fallback, exactly as existing issue/reservation logic does. No assistant copy-count calculation or reservation eligibility algorithm was added. Reservation queue information is not invented; no extra public per-book queue capability was introduced.

## Recommendations

| Context | recommendation_mode | Call |
|---|---|---|
| No selection and no explicit reference | PERSONALIZED_EXISTING_FORMULA | Existing GET `/recommendations` with the same requested TopN when unfiltered |
| One selected book | SINGLE_SELECTED_BOOK | Existing scoring pipeline, seeded from that work_id |
| 2–4 selected books | MULTI_SELECTED_BOOKS | One seeded call per selected book, then rank fusion |
| Explicit title/ID or conversational reference, no selection | EXPLICIT_BOOK_SEED | Resolve book, then seeded call |

Selection overrides model-extracted titles/ordinals for recommendation seed routing: all selected books are seeds. Plain “Recommend”, “recommend me something”, “What should I read?” and similar generic requests always follow the zero/one/many selection rule after Qwen extraction; they do not require preferences first.

The existing service had no seed or multi-seed endpoint. `get_recommendations` now has an optional `seed_work_id`. The seed branch replaces preference queries/subject/author counters with the verified seed and neutralizes historical preference counters; active account exclusions are retained. The existing generate_semantic_candidates, calculate_recommendation_score, scoring weights, feedback formula, and apply_diversity_reranking are reused. Without a seed, the existing default profile, formula and diversity behavior are preserved.

For multiple seeds, each receives a call to POST `/recommendations/from-book`. Equal-weight reciprocal rank fusion sums `1 / (60 + rank)` per unique work_id, with work_id ascending as the deterministic tie breaker. Raw scores are not compared between seeds. All seed IDs are removed and candidates deduplicated before final filtering/truncation. Availability/author/subject filters use current Core metadata after fusion. Candidate coverage is bounded to fifty per seed.

Assistant requests opt into `strict_service_errors` on the default recommendation route; seed requests always use it. This propagates search dependency outages as a structured service error instead of silently treating failures as an empty recommendation list. Other existing callers retain the prior default failure behavior. This changes error reporting, not recommendation scoring. Assistant-mode recommender logs omit query contents.

## Accounts and confirmation

Loans use `/issues/my` and filter status ISSUED; due dates remain in those actual issue records. History returns the existing full issue history, including active/returned records. Reservations and fees use `/reservations/my` and `/fines/my`, including the Core-calculated total_unpaid. Staff requests also use the authenticated user's own account; the assistant has no “all users” route.

An initial borrow/reserve/return request can only produce a `PendingAction`: random action_id, type, verified work_id, requires_confirmation=true, expiry and enabled flag. Return proposals first locate exactly one active loan in the current user's records and bind its issue_id server side. The Qwen requires_confirmation field is advisory; the backend always enforces confirmation.

Execute only by sending **both** `action: "CONFIRM_ACTION"` and the matching `pending_action_id` with the same conversation/user. Prose such as “yes” cannot execute a mutation. CANCEL_ACTION clears the proposal. Pending actions expire after five minutes; unrelated ordinary turns invalidate earlier proposals. A per-conversation async lock serializes confirmations. An enabled action is consumed before the mutation request; duplicate confirmation and timeout retries cannot re-execute it automatically. Core still checks borrowing/reservation/return business rules at execution.

`ASSISTANT_MUTATING_ACTIONS_ENABLED=false` by default. Read-only operations and proposals work regardless; confirming a disabled action returns MUTATIONS_DISABLED without touching Core. `ASSISTANT_ENABLED=true` by default. `.env.assistant.example` documents all flags; copy desired values into the existing environment or set them in PowerShell.

## State, failures and logs

ConversationStore holds at most 1,000 user-owned conversations, expires idle entries after thirty minutes, evicts the oldest idle entry at capacity, and stores no raw chat transcript, auth token, fee record or account record. Fields: conversation_id, owner, recent_result_work_ids, selected_work_ids snapshot, last_search_work_ids, last_recommendation_work_ids, last_comparison_work_ids, last_referenced_work_ids, last_intent and expiring pending action/return issue binding. Restarting the single process clears state; unknown/expired/cross-user IDs return 404.

Independent metadata/seed calls run concurrently. HTTP timeout is forty seconds, connect timeout three seconds. Qwen defaults to sixty seconds per generation; RAG defaults to 120 seconds. Qwen uses a bounded worker slot and the existing inference lock. Timeout does not cancel a running native GPU generation: it retains the slot until completion, rejects concurrent assistant generation safely, and avoids an unbounded queue. No mutation runs in that worker.

Logs record conversation ID, extracted intent/confidence/reference, selection count, referenced IDs, result count, services invoked, tool/Qwen stage latency and parse failures. Tokens, passwords, raw messages and private account records are not logged. Existing RAG diagnostics are preserved. HTTP 5xx internal detail is suppressed. Successful structured results remain available if explanation generation fails.

## RAG preservation

Assistant book/document questions call the **unchanged** existing `rag.api.ask` with RAGRequest and the original credentials. BookRuntime refresh, authorize_selection, active-loan eligibility, source isolation, depth and evidence validation remain in the original route. Uploaded document scope comes from typed page_context.document_id; missing/ambiguous source context asks for clarification. RAG answers/verdict/source data are preserved in response.rag and are not rewritten in stage two.

Baseline hash/AST checks verify original RAG handlers and request models unchanged. `rag/llm.py`, `rag/qa.py`, `rag/retriever.py`, `rag/reranker.py`, and `rag/services/document_service.py` match their pre-edit SHA-256 hashes. Only registration was appended to `rag/api.py`. G1/G2/G3, R0 variants, retrieval/chunking, indexes, source-first evaluation and accepted RAG integration were not edited or tuned.

## Files changed

New: `assistant/__init__.py`, `assistant/schemas.py`, `assistant/state.py`, `assistant/qwen.py`, `assistant/tools.py`, `assistant/orchestrator.py`, `assistant/api.py`, `backend/routes/assistant_catalogue.py`, `tests/test_assistant_backend.py`, `.env.assistant.example`, `scripts/smoke_assistant_backend.py`, `scripts/diagnose_assistant_qwen.py`, this report and the pre-edit implementation map.

Existing files edited: `backend/main.py` (register entity resolver), `rag/api.py` (register shared-Qwen assistant), `recommendation/api.py` (seed route and opt-in dependency failure reporting), `recommendation/recommendation_service.py` (optional seed profile and dependency failure reporting). No frontend file changes.

Evidence: `reports/assistant_backend_baseline/*`, assistant unit/regression JUnit XML, live smoke JSON, smoke service logs and decoder diagnostic log. The checkout has no Git metadata, so local baseline/hash/AST evidence is used instead of Git diff.

## Validation

Focused suite: **68 passed**. Combined assistant/access-control/dynamic-book/staff-auth regression suite: **154 passed, 10 skipped**, with no failures. The ten skips are pre-existing opt-in integration cases in the dynamic-book suite. The installed Starlette test client emits one httpx deprecation warning. `compileall` also succeeded for the added/edited backend modules. JUnit evidence is in `reports/assistant_backend_tests.xml` and `reports/assistant_backend_regressions.xml`.

Tests cover every requested Part 1 test category, plus compatible constrained decoding, selected-seed overrides, author/title/page references, literal ID spoofing, owned/expired/replayed/cancelled confirmations, concurrent confirmations, mutation timeout consumption, catalogue identity mismatch, dependency error propagation, exact-query escaping, TTL/ownership, endpoint auth/flags, default recommender preservation, original RAG hashes and routing.

Live validation: **11 verified cases passed**, using the real cached Qwen and existing Mongo/Core/Search/Recommendation services. Search returned ten actual catalogue books; comparison returned two; availability resolved the second reference; zero selection invoked the existing default formula (validly empty for the smoke account); one and two selected seeds each returned ten non-seed recommendations. Fees/general help routed correctly. A server conversation follow-up resolved the second prior result, a reservation request produced a pending action for that same canonical ID, and explicit confirmation with the default flag returned MUTATIONS_DISABLED. No library/user mutation occurred.

Evidence is `reports/assistant_backend_live_smoke.json`. This combines the full read-only run with targeted reservation/disabled-confirmation and saved-conversation reruns after fixing Qwen's omitted ordinal and stale comparison intent. The raw full-run and targeted-rerun JSON files are retained separately, as are earlier decoder/confidence/reference diagnostics; the combined result does not claim the earlier raw run had no failures. Each validation process loaded Qwen exactly once, with real CUDA generation; no two Qwen test processes ran concurrently. Smoke processes were stopped after validation. Observed main-case request latency was approximately 15–57 seconds on the laptop; no RAG generation settings were tuned.

Commands:

```powershell
Set-Location 'D:\SDC\LibraryLLM'
.\.venv\Scripts\python.exe -m pytest tests\test_assistant_backend.py -q --junitxml=reports\assistant_backend_tests.xml
.\.venv\Scripts\python.exe -m pytest tests\test_assistant_backend.py tests\test_book_access_control.py tests\test_dynamic_book_capabilities.py tests\staff_auth\test_auth.py -q --junitxml=reports\assistant_backend_regressions.xml
.\.venv\Scripts\python.exe scripts\smoke_assistant_backend.py
```

The live script starts/stops its owned service processes, uses an existing eligible identity, performs read-only/proposal/disabled-confirmation calls, and never writes loans/reservations/users. Ports 8002–8005 must be free before running it. It forces offline cached models and confirms one Qwen load in the 8005 process.

## Exact backend run commands

Run each command in a separate PowerShell terminal, from the project root. The existing MongoDB/config and local cached models are prerequisites.

```powershell
Set-Location 'D:\SDC\LibraryLLM'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --workers 1
```

```powershell
Set-Location 'D:\SDC\LibraryLLM'
.\.venv\Scripts\python.exe -m uvicorn search.api:app --host 127.0.0.1 --port 8003 --workers 1
```

```powershell
Set-Location 'D:\SDC\LibraryLLM'
.\.venv\Scripts\python.exe -m uvicorn recommendation.api:app --host 127.0.0.1 --port 8004 --workers 1
```

```powershell
Set-Location 'D:\SDC\LibraryLLM'
$env:ASSISTANT_ENABLED = 'true'
$env:ASSISTANT_MUTATING_ACTIONS_ENABLED = 'false'
$env:LUMINAR_MOCK_LLM = '0'
.\.venv\Scripts\python.exe -m uvicorn rag.api:app --host 127.0.0.1 --port 8005 --workers 1
```

## Example PowerShell requests

Use a valid token from the existing login flow. Replace sample IDs with catalogue work_ids. Do not provide user_id.

```powershell
$token = Read-Host 'Existing LuminaR access token'
$headers = @{ Authorization = "Bearer $token" }
$uri = 'http://127.0.0.1:8005/assistant/chat'

$body = @{ message = 'Find books about neural networks'; selected_work_ids = @() } | ConvertTo-Json -Depth 6
$search = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body

# The same request selects the existing personalized recommendation formula.
$body = @{ message = 'Recommend'; selected_work_ids = @() } | ConvertTo-Json -Depth 6
Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body

# One selected ID seeds similarity; two to four use every selected ID.
$ids = @($search.books | Select-Object -First 2 -ExpandProperty work_id)
$body = @{ message = 'Recommend'; selected_work_ids = $ids } | ConvertTo-Json -Depth 6
Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body

$body = @{ message = 'Compare these two'; selected_work_ids = $ids } | ConvertTo-Json -Depth 6
$comparison = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body
$body = @{ message = 'Is the second one available?'; conversation_id = $comparison.conversation_id } | ConvertTo-Json -Depth 6
Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body

$body = @{ message = 'Do I have fines?' } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body

$body = @{ message = 'Reserve this book'; selected_work_ids = @($ids[0]) } | ConvertTo-Json -Depth 6
$proposal = Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body
$body = @{ message = 'Confirm'; conversation_id = $proposal.conversation_id; action = 'CONFIRM_ACTION'; pending_action_id = $proposal.pending_action.action_id } | ConvertTo-Json -Depth 6
Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body
# Default configuration returns MUTATIONS_DISABLED. Enabling actions is an operator decision.

$body = @{ message = 'What does the PDF say about indexing?'; page_context = @{ document_id = 'your-existing-upload-id' } } | ConvertTo-Json -Depth 6
Invoke-RestMethod -Method Post -Uri $uri -Headers $headers -ContentType 'application/json' -Body $body
```

## Known limitations

- This initial conversation/pending store is in memory and requires a single worker; deploy a shared store before horizontal scaling.
- Native generation can finish after an HTTP/Qwen timeout; its slot/lock remain held until completion. Timeout after a Core mutation leaves outcome uncertain; check your account before requesting a new action.
- Qwen is small and generative; arbitrary phrasing can require clarification. Confidence is advisory; deterministic entity/confirmation checks establish authority. Subjective recommendation/comparison prose should not be consumed as structured data.
- Existing default recommendations can validly be empty for users without recommendation history; the assistant does not invent a cold-start formula.
- Missing page/year/language/difficulty fields prevent factual filters/comparisons using those values. A metadata migration would be a separate task.
- Filters operate on bounded candidate pools and may return fewer than requested results. Fuzzy title matches never silently select a different book.
- RAG still requires existing source IDs and book entitlement; the assistant does not grant access or select an uploaded PDF without source context.
- Qwen response latency on this laptop is material; this task did not change or tune accepted RAG/model generation behavior.
- Frontend wiring/UI work remains Part 2. Mutations remain disabled by default.
