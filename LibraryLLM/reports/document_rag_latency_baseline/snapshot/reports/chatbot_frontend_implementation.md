# LuminaR chatbot Part 2 — frontend integration

The existing LuminaR AI overlay now calls the real assistant endpoint. Part 1 remains authoritative: no assistant, recommendation, Core, RAG or model source changed. Production mutations remain disabled by default.

## Architecture and scope (A–F)

The frontend is React 19 with React Router 7, Vite 8, Tailwind 4 and Zustand 5. AIChatWidget was a timed mock mounted in DashboardLayout; the /llm route had a separate existing RAG workspace. The shared API request function in src/lib/api.ts already reads luminar_token, adds bearer authentication, sanitizes failures, and dispatches luminar-session-expired on 401. The existing Vite /rag-api proxy targets 8005. Existing frontend tests use node:test.

The implementation extends this architecture. The same widget now appears in the existing dashboard layout and the /llm layout, allowing the selected source in that workspace to accompany assistant questions. The accepted workspace's own RAG behavior is preserved. Sending a question through the assistant makes one /assistant/chat call; it does not also call /rag/ask.

New components: BookSelectButton, SelectedBooksTray (exported from AIChatWidget), AssistantTurn, ComparisonView, AvailabilityBadge. Reused: BookCover for generated covers when the backend has no cover field; existing catalogue/search/ForYou/detail card layouts; existing book-details route; Toast for the fifth-selection notice; theme colors, fonts and header placement; shared API client and authentication.

Files changed or added:

- frontend/src/components/AIChatWidget.tsx — real overlay, typed turns, quick actions, tray, loading and confirmation dispatch.
- frontend/src/components/assistant/AssistantTurn.tsx — structured results, comparison, availability, clarification, account, RAG, errors and pending cards.
- frontend/src/components/BookSelectButton.tsx — shared canonical selection control.
- frontend/src/store/useAssistantStore.ts — global selection, conversation, history and request state.
- frontend/src/lib/assistantTypes.ts — backend-aligned contracts, including intent/action/mode enums.
- frontend/src/lib/assistant.ts — typed client, bounded IDs, safe page context and display helpers.
- frontend/src/lib/api.ts — exports the existing request wrapper; introduces ApiError carrying status for conversation-expiry handling. Existing authentication and error sanitization remain in that wrapper.
- frontend/src/hooks/useAssistantPageContext.ts — route-scoped context publication/cleanup.
- frontend/src/pages/CatalogPage.tsx, SearchPage.tsx, BookDetailPage.tsx — selection controls and structured page context.
- frontend/src/components/ForYou.tsx — selection control in existing recommendation cards; existing feed behavior remains unchanged.
- frontend/src/pages/LLMPage.tsx — publishes selected document/book context only.
- frontend/src/App.tsx — widget in /llm and account ownership reset.
- frontend/src/index.css — native drawer, compact controls, mobile layout and focus styles.
- frontend/tests/assistant.test.tsx — node:test component/contract tests.
- frontend/package.json, package-lock.json — test commands and development-only tsx, jsdom, Testing Library, user-event and axe-core. No new production state library.
- scripts/assistant_frontend_services.py — optional local review harness; uses existing eligible reader authentication and removes its temporary session bootstrap on exit. --reuse does not start or stop operator services.
- reports/assistant_frontend_backend_baseline.json — pre-edit SHA-256 snapshot proving backend source preservation.
- this report and verification evidence/logs/screenshots.

## Selection and recommendation UX (G–K)

Zustand tracks at most four selected books, identified exclusively by work_id. Metadata is limited to title/authors for display. Selection is shared by cards and the overlay and survives client route navigation. Re-selecting an existing ID does not duplicate it. The fifth attempt is rejected with the requested message: “You can select up to 4 books. Remove one first.” Controls expose pressed state, an icon and a visible Selected label.

The tray appears above the composer, with bounded scrolling chips, per-book removal and Clear. One selection exposes Recommend Similar. Two to four expose Compare with AI and Recommend From These. Zero selections retains Recommend in quick actions. Clearing selection does not delete chat history.

All recommendation buttons send “Recommend” and the selected_work_ids snapshot to /rag-api/assistant/chat. All natural-language submissions also send current selection. Backend recommendation_mode supplies the heading. Personalized zero-result responses show the legitimate empty state and no fallback titles. One/multi/explicit-book modes are rendered independently from generated prose. React does no ranking, fusion, title resolution or service routing.

A result-card Recommend Similar uses that card's canonical ID for that request only. It does not overwrite the user's existing tray. Book-scoped availability and proposed mutation actions follow the same explicit ID strategy. VIEW_BOOK uses /book/:workId. SELECT_BOOK/UNSELECT_BOOK update the shared store; COMPARE adds the book and requires at least two selections. Action controls derive from response.actions; secondary actions use a compact disclosure menu.

## Structured responses (L–O)

Book cards show only provided authors/subjects/rating/copies/shelf/description. The actual Part 1 Book schema has no cover, rating_count, page/year/language/difficulty fields; the UI does not manufacture them. BookCover is an existing visual placeholder. Null availability is Unknown, false is Unavailable, and true can show an actual copy count. Explicit response.availability takes priority over book copy metadata, including null values.

Comparison discovers non-null keys in comparison.books dynamically. Desktop uses a semantic table; mobile uses stacked metadata cards. Missing requested fields appear as Not recorded. Subjects and descriptions have expansion controls, and long titles/values wrap within the drawer. No fixed Pages/Year/Language/Difficulty columns exist.

Clarification presents the supplied reason and actual canonical choices. Clicking a choice retries the original user task with that one selected_work_id and the same conversation_id. This is an explicit user choice, never an automatic first-option pick; the persistent tray is left intact.

Account results render the actual issues/reservations/fines envelopes, count/total_unpaid and supplied record fields. No account data is extracted from prose, saved in selection, added to URLs or persisted to sessionStorage. user_id and _id are omitted from displayed account records. RAG renders response.rag answer/verdict/sources as text, with source disclosures and no HTML execution or duplicate RAG fetch. Sources display actual filename/title/page/chapter where present.

## Conversation and page context (P–Q)

Returned conversation_id is reused for every later turn. New chat clears local conversation/history/recency and disables old confirmations. Recent structured book IDs preserve current result ordering, deduplicate, and are bounded to 20. They supplement the authoritative server conversation state; the UI has no ordinal parser.

Book detail/reader URLs supply a safe work_id. Catalogue/search pages publish at most four visible result IDs as work_ids. /llm publishes the currently selected uploaded document_id or eligible book work_id. Context is tied to pathname plus query, sanitized to accepted fields, and cleared when the publishing route changes. No page_type, raw page data or user_id is sent.

Unknown/expired server conversations (HTTP 404) clear the local ID/recency, announce expiry, and let the reader resend without auto-replaying a mutation. Session storage retains only owner, minimal selected books and conversation ID. Message history remains in memory across drawer closes and client route changes. Reload retains selection/conversation ID but drops private history and pending cards. An account change or logout aborts waiting and clears selection, conversation, account/RAG turns and pending cards; late responses from an old session are discarded.

## Confirmations and latency (R–T)

A pending card shows the exact backend action/book, expiry and enabled state. Confirm/Cancel send the same conversation_id with the matching pending_action_id and structured CONFIRM_ACTION/CANCEL_ACTION. Cancel goes to the backend. The assistant never performs direct Core borrow/reserve/return mutations. Old cards become inactive after any subsequent turn, and expired cards disable controls. Default-disabled cards explain the flag; confirming a disabled action cleanly displays MUTATIONS_DISABLED without bypassing it. Successful explicitly enabled confirmations refresh existing library state via the shared event; no production flag is enabled here.

Submitting immediately adds the user's message, keeps history scrollable and shows “Working on that…”. After 15 seconds it explains local model latency. There is no fake token streaming, percentage or invented service progress. One in-flight request is enforced in the store as well as disabled send/quick-action buttons. The submitted selection/page/recent context is a snapshot; changing selection later cannot alter it. The reader may close the overlay or browse while waiting; this keeps the request alive so the eventual response is available on reopening. Routine drawer closure does not claim native generation was stopped.

HTTP failures and successful responses with errors[] both render safely. Nonfatal explanation errors retain book/comparison/account results. React escapes all response text. The response wrapper records frontend elapsed milliseconds as a non-sensitive DOM attribute for review evidence.

## Accessibility and responsive layout (U–V)

The launcher has an accessible label, the overlay is a labelled modeless dialog, and opening focuses the composer. Escape closes it and focus returns to the launcher; no incorrect modal focus trap blocks catalogue selection. The history uses a live log, loading a status region, and HTTP errors an alert. Selection controls are native keyboard buttons with aria-pressed, visible text/icons and focus outlines. Remove controls name their books. The table uses caption/column/row headers. Enter submits, Shift+Enter inserts a newline, and composition events are respected. Input is bounded to 4000 characters.

The drawer preserves the paper/panel palette, rust accent, Oswald/Inter typography, floating placement and brand header. Height is bounded by the viewport. Mobile uses a nearly full-height panel with independent history scrolling and a fixed composer/tray. Four chips remain bounded. Reduced-motion settings disable drawer animation. Semantic axe checks are included; jsdom cannot validate real color contrast or all assistive-technology behavior, so those checks are supplemented by browser layout/keyboard review.

## Verification (W–AB)

Frontend validation: npm test passed 87 tests (31 existing tests plus 56 assistant component/contract/accessibility tests), with zero failures/skips. All 44 requested named test cases are present. npm run build passed. npm run lint succeeded with 18 warnings in existing components/pages and no warnings in the new assistant modules. Two axe semantic audits passed with zero violations; color contrast is excluded because jsdom has no real layout. Logs: assistant_frontend_tests.log, assistant_frontend_component_tests.log, assistant_frontend_build.log, assistant_frontend_lint.log. No backend regression suite is rerun merely to repeat Part 1: a full source-hash comparison covers all 89 Python source files under assistant/, rag/, recommendation/ and backend/, with zero changed files (assistant_frontend_backend_preservation.json). Part 1's 68 focused / 154 combined / 10 skipped validation remains the backend baseline.

### Real browser/service review (Z–AA)

All 12 requested manual scenarios were exercised through the actual overlay and existing services on 8002–8005. Existing operator services were reused; no second Qwen process was started. /health confirmed Qwen2.5-3B-Instruct on cuda:0, with the existing MiniLM/FAISS/CrossEncoder stack. The temporary local review identity used the normal bearer mechanism; the session was signed out and its bootstrap/harness removed afterward. Operator backend services and the frontend preview remain available.

| Scenario | Observed result | Frontend elapsed |
|---|---|---:|
| AI search | 10 real catalogue cards; two selectable | 51.52 s |
| Compare two | Dynamic fields and missing page_count notice | 41.60 s |
| Recommend From These | MULTI_SELECTED_BOOKS; 10 results; both seeds excluded | 62.52 s |
| Clear + Recommend | PERSONALIZED_EXISTING_FORMULA; this existing account returned 10 results | 26.43 s |
| One selected + Recommend Similar | SINGLE_SELECTED_BOOK; 10 results | 37.37 s |
| Explicit Dracula recommendation | Ambiguous bare title produced six choices; title plus author produced EXPLICIT_BOOK_SEED and one real result | 20.52 s clarification; 45.07 s explicit recommendation |
| Clarification choice | Retried original task with chosen canonical ID; returned 10 results | 37.43 s |
| Science-fiction search + second follow-up | Returned work_id exactly matched the second prior card | 50.97 s search; 20.83 s availability |
| Typed recommendation with two selected | MULTI_SELECTED_BOOKS; 10 results | 46.16 s |
| Fees | Actual own-account summary and fee records rendered | 18.25 s |
| Reservation / disabled Confirm / Cancel | Bound pending card, MUTATIONS_DISABLED, then server cancellation; no Core mutation | 33.57 s / 0.50 s / 0.58 s |
| Uploaded document | DOCUMENT_QUESTION; actual NOT_SUPPORTED verdict and seven references from selected PDF | 49.95 s |
| General help, fresh conversation | GENERAL_LIBRARY_HELP; actual explanatory text | 23.61 s |
| Current book page | CHECK_AVAILABILITY resolved the page's canonical work_id | 16.24 s |

Measured request range for the principal model-backed flows: about 18–63 seconds. The UI continued to scroll and accept selection/closure throughout. Response timing, intent and mode are captured from structured response-derived DOM attributes in assistant_frontend_live_evidence.json; no tokens or private account records are included there. The raw turn summaries retain exploratory routing outcomes rather than treating them as frontend fixes.

Browser review also verified native Enter selection on a detail card, canonical selection reflected in the tray, four selected chips, fifth-selection rejection, route navigation retaining assistant history, and logout clearing the private session. Desktop 1440×900, laptop 1366×768, tablet 768×1024 and mobile 375×812 were checked. Mobile panel clientWidth/scrollWidth both measured 341px, tablet both 438px: no drawer horizontal overflow. Browser console returned zero warnings/errors, including no React key/control/nesting warnings or fetch loops. Screenshots: assistant_frontend_screenshots/comparison-desktop.jpg, comparison-laptop.jpg, comparison-tablet.jpg and mobile-four-selected.jpg. The temporary viewport override was reset after review.

### Known limitations (AB)

- Backend natural-language interpretation is context sensitive. Two general-style questions within a prior search conversation were classified as SEARCH_BOOKS. Starting a fresh conversation yielded GENERAL_LIBRARY_HELP for the same Gothic-fiction concept. This is recorded in the evidence; no model prompts or orchestrator rules were altered for frontend convenience.
- The selected-document example returned the accepted RAG service's NOT_SUPPORTED verdict. The UI faithfully displays that result and its seven actual sources; this frontend task does not establish answer coverage for every document/question.
- Generated explanatory prose can disagree with verified metadata. Cards, comparisons, modes, actions and account results use structured fields; they never parse operational facts from that prose.
- The catalogue uses zero ratings for unrated books. Assistant cards follow existing detail/search conventions and show only positive finite ratings; comparison can still display the literal supplied metadata.
- Model latency remains material, and the 8005 service must remain one worker. There is no token streaming, native generation cancellation or extra model process in this change.
- In-memory conversation expiry/restarts are handled without automatic replay. Reload keeps minimal selection/conversation ID but intentionally loses private message history and pending cards.
- Semantic axe checks exclude color contrast and do not replace a full screen-reader/device certification. Physical phone keyboard behavior was not tested; responsive browser viewport behavior was checked.
- Enabled production mutations were not exercised. Disabled confirmation and server cancellation were tested, and frontend mutation contracts have component coverage. No production mutation flag was enabled.
- Existing ForYou feed fallback behavior remains its original feature. Assistant personalized recommendations have their own honest empty state and no fallback catalogue calls.
- The existing development proxy is reused. A production deployment must retain equivalent /rag-api routing, as with the existing RAG frontend.

## Exact commands (AC–AD)

Frontend:

```powershell
Set-Location 'D:\SDC\LibraryLLM\frontend'
npm run dev -- --host 127.0.0.1
```

Frontend validation:

```powershell
Set-Location 'D:\SDC\LibraryLLM\frontend'
npm test
npm run test:assistant
npm run build
npm run lint
```

Use one terminal per backend service; if already running, reuse it. Keep existing Mongo and environment configuration.

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

Do not add --reload or a second 8005 worker/process for real-Qwen review.

## Reviewer demo (AE)

1. Sign in with an existing reader, open LuminaR AI and search for artificial intelligence books.
2. Select two actual cards. Compare with AI; inspect structured fields and missing metadata notice.
3. Recommend From These; inspect heading and non-seed book cards.
4. Remove one selection, then Recommend Similar. Clear the tray, then Recommend.
5. Send a follow-up about the second result; inspect actual availability.
6. Ask about fines or loans; inspect structured own-account data.
7. Select one book and request a reservation. Confirm under the default-disabled setting, then Cancel the still-pending proposal if present.
8. On Know More, select an existing uploaded document, open the overlay and ask a document question. Inspect RAG source information.
9. Navigate to a book detail page and ask “Is this available?”; context accompanies the turn.
10. Close/reopen the overlay, test keyboard selection and review mobile comparison/tray layout.

Stop after Part 2 review; no Part 3, scoring changes, model tuning or production mutation enablement is included.