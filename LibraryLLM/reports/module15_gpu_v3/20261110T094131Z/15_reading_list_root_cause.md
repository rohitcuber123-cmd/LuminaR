# LuminaR Module 15 GPU V3 — Reading List Defect Root-Cause Analysis & Routing Evaluation

## 1. Historical Failure Reproduced Before Changes

In GPU V2 (preserved in `reports/module15_gpu_v2/`), the request `"Show my reading list"` routed to `USER_LOANS` instead of `USER_READING_LIST`. Replaying the 13-probe reproduction script against pre-change code on live CUDA `Qwen/Qwen2.5-3B-Instruct` (rev `aa8e72537993ba99e69dfaafa59ed015b17504d1`, 4-bit=`True`, router=`existing_qwen`) reproduced the failure deterministically in [`pre_fix_repro_trace.json`](./pre_fix_repro_trace.json):
- `"Show my reading list"` and 4 reading-list paraphrases (`"Open my saved books"`, `"Which books have I saved?"`, `"Display the books in my reading list"`, `"Show the books I want to read"`) plus `"Show my borrowing history"` and `"Show my unpaid fees"` all misrouted to `USER_LOANS`.
- `"Remove Synthetic Astronomy from my reading list"` was blocked in `CLARIFICATION` because `assistant/orchestrator.py:227` omitted `READING_LIST_PENDING` from literal-title precedence.

## 2. Exact Root Cause

1. **System Prompt Confusion (`assistant/qwen.py:256-325`)**: The `existing_qwen` compact system prompt lacked explicit non-selected (`s=account`) intent boundaries distinguishing `loans`, `reservations`, `history`, `fees`, `list`, `add_list`, `remove_list`, `clear_list`, and `unknown`. Under `Qwen2.5-3B-Instruct`, reading-list phrasing (`"reading list"`, `"saved books"`, `"books I want to read"`) defaulted to `loans` due to unanchored few-shot priors that assumed a selected book pair.
2. **Orchestrator Literal-Title Precedence Gap (`assistant/orchestrator.py:227`)**: `orchestrator.chat` checked `ENTITY | {Intent.GENERAL_LIBRARY_HELP}` instead of `ENTITY | READING_LIST_PENDING | {Intent.GENERAL_LIBRARY_HELP}`, preventing literal book titles in reading-list removal/add commands from overriding stale selection state.

## 3. Minimal Generalizable Fix

Without changing `ASSISTANT_ROUTER_MODE=existing_qwen`, schemas, or adding exact-phrase hardcoding:
- Refined `QwenGateway.parse` prompt definitions and added compact `"i"`-first examples for non-selected account queries and reading-list mutations prior to `'Examples (with a selected pair unless stated otherwise): '`, added the structural rule `'Topic search (s=none,i=search) and s=account never emit e or d.'`, and changed ambiguous wording `"list the volumes..."` to `"show the volumes..."` (`assistant/qwen.py:256-325`).
- Updated line 227 of `assistant/orchestrator.py` to include `READING_LIST_PENDING` in literal-title precedence.

## 4. Before-vs-After Reproduction Trace (13 Probes, Real CUDA)

Pre-fix (`pre_fix_repro_trace.json`) vs. Post-fix (`post_fix_repro_trace.json`) — post-fix achieved **13/13** exact matches:

| ID | User Message | Expected Intent | Pre-Fix Result | Post-Fix Result |
| :--- | :--- | :--- | :--- | :--- |
| `show_reading_list` | `Show my reading list` | `USER_READING_LIST` | `USER_LOANS` (FAIL, mut=False) | `USER_READING_LIST` (PASS, mut=False) |
| `open_saved_books` | `Open my saved books` | `USER_READING_LIST` | `USER_LOANS` (FAIL, mut=False) | `USER_READING_LIST` (PASS, mut=False) |
| `which_saved` | `Which books have I saved?` | `USER_READING_LIST` | `USER_LOANS` (FAIL, mut=False) | `USER_READING_LIST` (PASS, mut=False) |
| `display_reading_list` | `Display the books in my reading list` | `USER_READING_LIST` | `USER_LOANS` (FAIL, mut=False) | `USER_READING_LIST` (PASS, mut=False) |
| `want_to_read` | `Show the books I want to read` | `USER_READING_LIST` | `USER_LOANS` (FAIL, mut=False) | `USER_READING_LIST` (PASS, mut=False) |
| `add_to_reading_list` | `Add this book to my reading list` | `ADD_TO_READING_LIST` | `ADD_TO_READING_LIST` (PASS, mut=False) | `ADD_TO_READING_LIST` (PASS, mut=False) |
| `remove_from_reading_list` | `Remove Synthetic Astronomy from my reading list` | `REMOVE_FROM_READING_LIST` | `CLARIFICATION` (FAIL, mut=False) | `REMOVE_FROM_READING_LIST` (PASS, mut=False) |
| `show_borrowed_books` | `Show my borrowed books` | `USER_LOANS` | `USER_LOANS` (PASS, mut=False) | `USER_LOANS` (PASS, mut=False) |
| `what_on_loan` | `What books do I currently have on loan?` | `USER_LOANS` | `USER_LOANS` (PASS, mut=False) | `USER_LOANS` (PASS, mut=False) |
| `show_borrowing_history` | `Show my borrowing history` | `USER_HISTORY` | `USER_LOANS` (FAIL, mut=False) | `USER_HISTORY` (PASS, mut=False) |
| `which_must_return` | `Which books must I return?` | `USER_LOANS` | `USER_LOANS` (PASS, mut=False) | `USER_LOANS` (PASS, mut=False) |
| `show_reservations` | `Show my reservations` | `USER_RESERVATIONS` | `USER_RESERVATIONS` (PASS, mut=False) | `USER_RESERVATIONS` (PASS, mut=False) |
| `show_fees` | `Show my unpaid fees` | `USER_FEES` | `USER_LOANS` (FAIL, mut=False) | `USER_FEES` (PASS, mut=False) |

## 5. 142-Case Multi-Intent Routing Regression Matrix (Native CUDA HTTP)

Executed on `2026-11-10T12:11:43.228870+00:00` via `native_cuda_authenticated_http` (`router_mode=existing_qwen`):
- **Parsed Intent Accuracy**: **112/142 (78.87%)**
- **End-to-End Authenticated HTTP Intent Accuracy**: **115/142 (80.99%)**
- **`USER_READING_LIST` Precision / Recall**: **1.0 / 1.0 (16/16)** (parsed: **1.0 / 1.0**)
- **`USER_LOANS` Precision / Recall**: **0.9286 / 0.9286 (13/14)**
- **Reading List -> Account Tool Misroutes**: **0**
- **Unexpected State Mutations**: **0**
- **Overall Multi-Intent Gate Outcome**: **`FAIL`** (Reading List defect is fixed, while overall multi-intent accuracy `80.99%` remains below the `90%` strict bar across non-reading-list intents).

### Why Non-Reading-List HTTP Mismatches Occurred (27 of 142 cases)
1. `BOOK_DETAILS -> BOOK_CONTENT_QUESTION` (`4` cases: `RT-097`, `RT-098`, `RT-100`, `RT-102`) & `SEARCH_BOOKS` (`RT-101`): Qwen mapped metadata questions (e.g. `"Tell me about Dracula"`, `"Who wrote Frankenstein?"`) to `book_question`.
2. **Fail-closed reference guards (`CLARIFICATION`)**: When Qwen emitted conflicting `s="selected"`/`s="explicit"`/`e="FIRST"` bindings on reading-list mutations or graph/recommendation references (`RT-021`, `RT-022`, `RT-032`, `RT-034`, `RT-035`, `RT-112`, `RT-115`, `RT-118`, plus `RT-081`), `orchestrator` conservatively demanded `CLARIFICATION` without mutating database state (`mutated: false`).
3. `COMPARE_BOOKS` vs. `RECOMMEND_*` / `MORE_LIKE_THIS` overlap (`RT-111`, `RT-113`, `RT-114`, `RT-117`, `RT-126`).
4. `UNKNOWN` unsupported administrative asks (`RT-139` `"Waive all my library fines"` -> read-only `USER_FEES`; `RT-141` `"Change the library closing hours"` -> `GENERAL_LIBRARY_HELP`), neither mutating state.

### Per-Intent Metrics Table

| Intent | Parsed Support | Parsed TP | Parsed P | Parsed R | HTTP Support | HTTP TP | HTTP P | HTTP R |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `ADD_TO_READING_LIST` | 10 | 10 | 0.9091 | 1.0 | 10 | 8 | 1.0 | 0.8 |
| `BOOK_CONTENT_QUESTION` | 0 | 0 | 0.0 | None | 0 | 0 | 0.0 | None |
| `BOOK_DETAILS` | 6 | 1 | 1.0 | 0.1667 | 6 | 1 | 1.0 | 0.1667 |
| `BORROW_BOOK` | 0 | 0 | 0.0 | None | - | - | - | - |
| `CHECK_AVAILABILITY` | 8 | 7 | 0.7778 | 0.875 | 8 | 7 | 1.0 | 0.875 |
| `CLARIFICATION` | 8 | 0 | None | 0.0 | 20 | 18 | 0.5143 | 0.9 |
| `CLEAR_READING_LIST` | 4 | 3 | 1.0 | 0.75 | - | - | - | - |
| `COMPARE_BOOKS` | 6 | 6 | 0.4615 | 1.0 | 6 | 4 | 0.8 | 0.6667 |
| `DOCUMENT_QUESTION` | 4 | 3 | 0.75 | 0.75 | 4 | 3 | 1.0 | 0.75 |
| `GENERAL_LIBRARY_HELP` | 4 | 3 | 0.75 | 0.75 | 4 | 3 | 0.75 | 0.75 |
| `MORE_LIKE_THIS` | 4 | 3 | 1.0 | 0.75 | 4 | 1 | 1.0 | 0.25 |
| `RECOMMEND_BOOKS` | 2 | 0 | None | 0.0 | 2 | 2 | 1.0 | 1.0 |
| `RECOMMEND_FROM_BOOK` | 3 | 1 | 0.3333 | 0.3333 | 3 | 0 | None | 0.0 |
| `RECOMMEND_FROM_SELECTION` | 1 | 0 | None | 0.0 | 1 | 0 | None | 0.0 |
| `REMOVE_FROM_READING_LIST` | 10 | 10 | 0.8333 | 1.0 | 10 | 7 | 1.0 | 0.7 |
| `SEARCH_BOOKS` | 10 | 10 | 0.9091 | 1.0 | 10 | 10 | 0.9091 | 1.0 |
| `UNKNOWN` | 8 | 4 | 0.8 | 0.5 | - | - | - | - |
| `USER_FEES` | 8 | 8 | 0.8889 | 1.0 | 8 | 8 | 0.8889 | 1.0 |
| `USER_HISTORY` | 8 | 7 | 0.875 | 0.875 | 8 | 7 | 0.875 | 0.875 |
| `USER_LOANS` | 14 | 13 | 0.9286 | 0.9286 | 14 | 13 | 0.9286 | 0.9286 |
| `USER_READING_LIST` | 16 | 16 | 1.0 | 1.0 | 16 | 16 | 1.0 | 1.0 |
| `USER_RESERVATIONS` | 8 | 7 | 1.0 | 0.875 | 8 | 7 | 1.0 | 0.875 |

## 6. HTTP Smoke Checks, Multi-Turn Clarification, and Unavailable RAG Fail-Closed Checks

- **Live HTTP Assistant Checks (`15_assistant_http_results.json`)**: **4/4 `PASS`** (includes `missing_auth_401`, `login` `200`, `"Show my reading list"` -> `USER_READING_LIST`, `SEARCH_BOOKS`, and `REFERENCE_AMBIGUITY`).
- **Clarification Lifecycle (`15_clarification_results.json`)**: **3/4 `FAIL`** — `criteria_ambiguity_and_valid_continuation` passed Turn 1 (`COMPARE_BOOKS` + `CRITERIA_AMBIGUITY`) but failed Turn 2 (`"Best for a beginner learning Python"` bound only 1 book `OL910000001W` -> `CLARIFICATION` / `INSUFFICIENT_SELECTION`).
- **Unavailable RAG Callback (`15_unavailable_callback_results.json`)**: **2/2 `PASS`** (`DOCUMENT_QUESTION` and `BOOK_CONTENT_QUESTION` reached callback and surfaced `HTTP_503` cleanly without fabricating answers).