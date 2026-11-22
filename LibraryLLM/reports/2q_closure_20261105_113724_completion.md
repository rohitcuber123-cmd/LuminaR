# LuminaR Part 2Q focused defect closure

| Item | Finding |
|---|---|
| A. Result | PARTIAL. Source and controlled regressions cover the five observed failures. The frontend repair was verified on the running stack. The patched Assistant source still needs resident-model verification. |
| B. Checkpoint | Accepted Q5 baseline of 3,137 backend passes, 20 skips, and 1,031 frontend passes. Prior runtime acceptance supplied the original reproductions and request context. |
| C. Confirmation root cause | The lending boundary sets proposal enabled from ASSISTANT_MUTATING_ACTIONS_ENABLED. It returns structured Confirm and Cancel actions even when the flag is false, and the backend independently rechecks it at execution. The frontend kept the field, displayed the disabled explanation, and omitted it from the Confirm button and send guard. |
| D. Confirmation repair | Confirm now requires an enabled, active, unexpired proposal. The store rejects confirmation without a matching latest action ID, enabled flag, valid deadline, and compatible tenant scope. Cancel remains usable on an active disabled proposal. The existing server gate remains authoritative. A controlled enabled proposal reached the API and its simulated denial was rendered. |
| E. Database root cause | The original request yielded the personalized recommendation response, mainly Java titles. That route consumes seeds and filters and never passes the topic query to Search. With “Find database textbooks,” resident Qwen returned SEARCH_BOOKS with database titles, including *A First Course in Database Systems* and *Database concepts*. This supports a routing explanation for the observed case. The original raw Qwen routing JSON and exact internal Search payload are unavailable. |
| F. Database repair | Explicit topic-and-book recommendation wording now sends the stated query to the existing scoped Search path. Equivalent adapter tests assert query propagation for database textbooks, DBMS, relational databases, SQL, networks, Java, OS and ML. Generic, seeded and count-only recommendations keep their route. An explicit suitability criterion survives a comparison decision that omitted it. No claim is made about the entire ranking pipeline or other query formulations. Direct unauthenticated Search probes returned 401. |
| G. Singular root cause | The original request produced the normal recommendation page. Nothing enforced a single result or established a single focus when the intent carried the default count. |
| H. Pick-one repair | Recognized singular wording selects one eligible candidate from the existing ordered pool. The response names the pick and retains its verified ID as the conversational focus. Empty results stay empty and a pick creates no mutation proposal. Controlled tests verify rank, empty candidates, borrowing follow-up and an actual Core fixture's local-only cold start and cross-library denial. |
| I. Similarity root cause | The prior run opened OL19546426W and the content path returned a capability limitation. The next similar-books response was a comparison clarification. The old compare-to-discovery correction only covered explicit selected-book scope. A verified page book therefore did not protect the single-seed request from misrouting. |
| J. Similarity repair | An explicit similar-books request with one current page book and no conflicting selection uses the existing seeded recommender. Canonical catalogue resolution and tenant ownership checks still run. The regression first executes a content-capability limitation, then supplies the wrong comparison decision for the similarity turn. |
| K. Comparison follow-up | The previous pair was stored, but positional binding could narrow the next comparison to one ID. Explicit “those two” suitability wording reuses the immediately preceding verified pair when the current selection does not conflict. First/third and second/fourth regressions replay a singleton model decision. The answer explains when catalogue metadata cannot establish suitability. |
| L. Library context and safety | Scoped catalogue and conversation validation remain in place. Fixture checks cover tenant ownership, cold start, a local-only selection and cross-library denial. The full suite covers revocation, recommendations, reservation/lending authority, digital access, RAG boundaries, and stale frontend responses. |
| M. Real Qwen | Two completed fresh natural-language requests against the existing resident backend. A public local-only borrowing proposal and a Global Search wording control both completed. One structured cancellation also completed. The resident process has reload disabled and still has the previous backend code loaded. Live verification of the four patched Assistant behaviors is NOT_RUN. |
| N. Browser | The previous public fixture again returned an active disabled proposal. With updated frontend source, Confirm was disabled and Cancel enabled. The cancel turn returned “Action cancelled.” Confirmation was not clicked. Private end-to-end checks are BLOCKED because the session lacks qualified disposable private fixtures. Private B protected validation remains outside this closure. |
| O. Backend | 3,151 passed / 0 failed / 20 skipped. All 38 groups completed across two runs. The first run stopped after 17 completed groups. The remaining 21 ran under fresh isolation with the same test inventory and guard settings. |
| P. Frontend | 1,032 passed / 0 failed / 0 skipped. |
| Q. Build and lint | Production build and lint passed. Lint reported 16 existing warnings. |
| R. Preservation | Observed data and index metadata, protected RAG hashes, Git HEAD, and 270 historical evidence files match. The public fixture book had zero requests and zero loans before the run and after cancellation. |
| S. Exact files | assistant/orchestrator.py, frontend/src/components/assistant/AssistantTurn.tsx, frontend/src/store/useAssistantStore.ts, frontend/tests/assistant.test.tsx, tests/test_assistant_backend.py, and tests/institution_v2q_ai/test_integration.py. Run-specific evidence is adjacent. |
| T. Remaining limitations | Fresh resident-model QA for the new backend behavior, the qualified private matrix, and broader Search quality beyond the bounded wording control remain unverified. Single-book choices retain the recommender's existing eligibility and ranking, and do not certify reading level. |
| U. Next engineering step | At the next authorized backend reload, replay the four natural-language closure cases with the same resident model and capture structured route, candidate IDs and comparison pair. Add a separately measured Search investigation only if the correct Search path itself returns irrelevant books. |

The first focused backend run found one count-only recommendation regression. The final Assistant group reran the existing test with the repaired guard. No assertions were suppressed. The browser and API evidence separates the frontend change from the old resident backend.

The resumed run removed its own fallback database and session directory. The interrupted run did not produce a cleanup record, and its isolated scratch directory remains. The pre-existing Q3 evidence overwrite remains recorded in the earlier checkpoint.

## Final QA

```json
{
  "RUNTIME_DEFECT_CLOSURE": "PARTIAL",
  "CONFIRM_BUTTON_AUTHORITY": "PASS",
  "UNREQUESTED_LOAN_MUTATIONS": 0,
  "DATABASE_QUERY_RELEVANCE": "PARTIAL",
  "SINGULAR_BOOK_SELECTION": "PARTIAL",
  "CURRENT_BOOK_SIMILARITY": "PARTIAL",
  "COMPARISON_PAIR_FOLLOW_UP": "PARTIAL",
  "LIBRARY_SCOPE": "PASS",
  "PRIVATE_E2E": "BLOCKED",
  "REAL_QWEN": "2 requests completed on resident pre-patch backend. Public proposal and Global Search control.",
  "BROWSER_QA": "PARTIAL",
  "BACKEND": {
    "passed": 3151,
    "failed": 0,
    "skipped": 20
  },
  "FRONTEND": {
    "passed": 1032,
    "failed": 0,
    "skipped": 0
  },
  "BUILD": "PASS",
  "LINT": "PASS",
  "NEW_REGRESSIONS": 0,
  "PROTECTED_RAG_CHANGED": "NO",
  "GLOBAL_HNSW_REBUILT": "NO",
  "GLOBAL_KG_REBUILT": "NO",
  "PRODUCTION_AUTH_CHANGED": "NO",
  "PRODUCTION_TELEMETRY_ENABLED": "NO",
  "DEPLOYED": "NO",
  "COMMITTED": "NO"
}
```
