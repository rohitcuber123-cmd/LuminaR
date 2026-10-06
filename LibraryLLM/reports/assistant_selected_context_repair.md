# Assistant selected-context repair: PASS

Production remains `existing_qwen`; Router V1-V5 research stays frozen. No new model, classifier, retry generation, Search ranking, recommendation algorithm, KG or RAG changes.

## Root cause and repair

The visible tray already sent the correct IDs. The semantic contract did not consistently treat the current selection as explicit context, and general help had no authoritative selected-metadata binding before clarification. The repair supplies selected count/status and ordered catalogue titles to the existing router, preserves literal-title precedence, and binds current canonical IDs before conversational answering. Requested positions are validated; free-form explanations receive the entire selected set, so cross-ordinal questions retain both records. Structured tools retain their own positional targets.

Typed messages snapshot the visible tray. New chat intentionally clears conversation/history while preserving selection. Six frontend tests verify payload, count, removal, replacement, Clear and New chat; no frontend production change was necessary.

Metadata is limited to four records: title 200 characters, authors four by 80 (or string 320), subjects eight by 80 (or string 640), description 1200. Qwen chooses one to three verified observations with an enum-constrained answer plan; application rendering supplies canonical titles and source-derived facts. This prevents invented descriptions or publication claims. Answers remain verified observations; missing cause/reputation/publication evidence cannot support an invented claim. Source-gap notes are available in the answer plan. No full catalogue/private data or automatic RAG chunks are supplied. Prompt-only free prose failed source grounding during development and was replaced before acceptance.

## Live results

Actual pair: `OL17930368W` (Atomic Habits) and `OL37490159W` (Atomic Habits, I Will Teach You To Be Rich, Mindset, The One Thing 4 Books Collection Set). The collection is one catalogue record and has no description. The original question now mentions both titles and their recorded shared words/authorship. There is no missing-book clarification, fuzzy title resolution or unrelated Search.

Seven original paraphrases pass; the main-difference request uses verified metadata contrasts while objective rating comparison remains structured. First/second relationship reasoning, source-limited inspiration, single-book reputation, three and four selections also pass. A same-conversation chain replaces the pair, removes one and clears selection while deliberately supplying stale page/recent IDs; current selection wins. Invalid third position clarifies. Explicit Frankenstein overrides selection through normal catalogue title ambiguity (several real works); the user must choose the intended edition/work.

Higher rating uses authoritative comparison, second availability uses Core, ordinal details use catalogue, recommendations use both seeds, related alternatives use KG, and borrow/reading-list actions retain pending confirmation. Account requests remain account; unseeded topics remain Search. A real chapter request uses Book RAG and is denied for the disposable reader without an active borrow; no metadata answer bypasses that boundary.

## Performance and generation counts

Each selected answer plan uses one generation. Typed free-form fallback uses the existing router plus that plan: two total. Typed structured operations use one routing generation. Explicit UI comparison/availability use zero. Removing the routing pass would require a broader change and cannot safely identify account, Search, mutations or content questions from selection alone.

| Check | Total ms | Qwen | Fuzzy | Search |
|---|---:|---:|---:|---:|
| reported | 12291 | 2 | 0 | 0 |
| rating | 4718 | 1 | 0 | 0 |
| availability | 3969 | 1 | 0 | 0 |
| search | 6187 | 1 | 0 | 1 |
| loans | 3271 | 1 | 0 | 0 |
| ui_compare | 48 | 0 | 0 | 0 |
| ui_availability | 33 | 0 | 0 | 0 |

Fallback median: 10833 ms on the current local GPU. These are observed serial development timings, not a benchmark or latency guarantee. Numeric/categorical profiles contain counts, route and timings; no raw user question, email or metadata is recorded in profiling.

## Validation and preservation

Backend: 1045 passed, 10 existing optional security/integration skips, zero failures/errors, including 54 new repair tests. Frontend: 246 passed (six new payload tests). Build passes; lint has zero errors and 19 existing warnings. Existing bundle-size warning remains.

Initial concurrent frontend testing exhausted memory and MongoDB stopped. The user restored MongoDB; final frontend tests ran serially and all database-dependent groups passed after recovery. On resumption, missing normal services were restored and the disposable access token refreshed. Intermediate failures are retained in development logs; final XML and live evidence determine acceptance.

Hash audit: 870 baseline files, exactly six existing files changed. All Events reports/source, Search, Recommendations, KG, RAG and Router V1-V5 research/models remain unchanged. Runtime has no experimental router imports or child worker processes. Disposable account and temporary frontend are cleaned up; normal local stack remains running.

## Exact files changed or added

- `assistant/orchestrator.py`
- `assistant/qwen.py`
- `assistant/schemas.py`
- `assistant/semantic.py`
- `assistant/tools.py`
- `frontend/tests/assistant.test.tsx`
- `assistant/selected_context.py`
- `scripts/check_selected_context_live.py`
- `scripts/finalize_selected_context_repair.py`
- `scripts/start_selected_context_repair.ps1`
- `scripts/test_selected_context_regressions.py`
- `tests/test_assistant_selected_context_repair.py`

## Evidence and limits

- `assistant_selected_context_live.json`: raw public-book live answers, canonical IDs, profiles and acceptance.
- `assistant_selected_context_regression.json`: tests, preservation, exact files, performance and cleanup.
- `assistant_selected_context_ui.png` / `assistant_selected_context_ui.json`: real frontend pair/tray/answer and New chat/removal proof.
- XML/logs under `assistant_selected_context_*`: suite results and development diagnostics.

Answers are bounded catalogue observations, not unrestricted literary analysis. The collection lacks a description. Publication influence/reputation cannot be established from absent metadata. Explicit-title ambiguity still needs user choice. True Book RAG requires its existing borrow authorization. Two total generations remain for typed fallback. No Router V6 was started. Repair work stops here.
