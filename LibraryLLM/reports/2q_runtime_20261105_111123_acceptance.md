# LuminaR Part 2Q final live runtime acceptance

**Result: PARTIAL.** The local-only borrowing proposal and cancellation worked in an existing public test fixture. The requested disposable private-library acceptance and paired validator diagnostic could not run with the available account. Three Global sequences had clear product failures or an incomplete follow-up, and one produced a justified clarification after failing to pick a single book.

1. **Service availability and startup.** Reused the already-running local stack. Core 8002 returned healthy, recommendation 8004 returned ready, RAG 8005 returned healthy with Qwen2.5-3B-Instruct on CUDA, and Vite 5173 served the frontend. MongoDB answered ping. Search 8003 served queries with its 5,000,000-vector index in STALE/degraded state. The former isolated ports 18005 and 18017 refused connections. This run started no service or model process.
2. **Live Qwen count.** The browser recorded 17 completed natural-language Assistant requests through the resident Qwen routing path, all HTTP 200. One additional natural-language POST was aborted on the browser side during a library switch, so server completion is unknown. The eighteenth completed HTTP 200 was the structured cancellation. These are request counts, since token-generation telemetry was unavailable.
3. **Local-only borrowing.** Supplemental public fixture A check. The book detail URL and catalogue record agreed on book UUID 134d5971-db66-4ad5-8558-2c9d67288a36 in library 8efa6277-40e6-48c8-943e-191170e43f5f. The record has no global work ID. “Borrow this book for me.” returned BORROW_BOOK with the same two UUIDs and no errors. The server reported enabled=false. Cancel returned “Action cancelled.” Confirmation was not submitted. The browser exposed an enabled Confirm button despite the server’s disabled flag.
4. **HTTP 409.** The old failure did not recur in the observed local-only proposal. A successful proposal for a record without a global mapping is consistent with the repaired local-ID branch. The browser does not expose internal RAG-to-Core tool calls, so there is no fresh server-side tool trace. The focused regression explicitly checks that this route skips the global resolver. The private fixture variant remains NOT_RUN.
5. **Six sequences.** All six were attempted in Global. Two passed end to end. The signed-in account exposed public isolation fixtures A/B and an unqualified private institution. Requested private A, private B, and Institution I sequence matrices remain NOT_RUN.

| Sequence | Global result |
|---|---|
| Python search → second-book physical availability | PASS. Ten results. The second result, *Python, The Complete Reference*, returned one available copy of one total. |
| Database textbooks → beginner suitability | FAIL. Recommendations were mainly Java titles. The follow-up asked for comparison criteria even though the user had specified beginner suitability. |
| Operating systems → third-book digital availability | PASS. Resolved the third result by M. Maekawa and reported that digital access could not be verified. |
| Pick a book → explicit borrowing | PARTIAL. The recommendation step returned multiple books. Asking which book to borrow was justified and produced no proposal. |
| Book-detail page → similar books | FAIL. The detail link opened OL19546426W. The initial content request returned “Know More is not available for this title.” The similar-books request asked for another comparison book. |
| First/third comparison → introductory suitability | PARTIAL. The comparison used the correct first/third pair. The follow-up asked for another book despite the established pair. |

6. **For You.** Public fixture A and B recommendation requests each returned HTTP 200 and displayed their fixture-specific rail. Private-library For You remains NOT_RUN.
7. **Availability.** Public fixture A showed one requestable physical copy. “Can I borrow this book?” returned the same count and generated no proposal. Digital availability separately returned unknown in fixture A and Global. A live authorized private PDF case remains NOT_RUN.
8. **Switching and authorization.** Global → public A → public B → Global completed. The in-flight A chat POST ended with net::ERR_ABORTED and B opened an empty chat. A B query returned B catalogue records. Live foreign-conversation replay, unauthorized asset denial and membership revocation remain NOT_RUN. The focused backend suite covers those boundaries with disposable fixtures.
9. **Browser QA.** PARTIAL. Authenticated session reuse, Global chatbot, the public fixture switching and chats, local detail navigation, stock, proposal, cancellation, and stale response handling were observed. Fresh login and private scenarios were NOT_RUN. The requested 390 px mobile override produced 487 px inner width and 469 px content width, with no horizontal overflow in the sampled view. Keyboard Tab focused “Skip to content.” The viewport override was restored. No HTTP error or warning/error console entry appeared in the captured window. The captured browser network buffer reported no truncation.
10. **Private B validator.** UNRESOLVED. The prior synthetic traces showed identical FACTUAL structured intent with actor unknown, action record, target calibration code, positive polarity, and no temporal relation or question focus. Both facts reached validation. A’s ALPHA-SEVEN returned SUPPORTED and B’s BRAVO-NINE returned NOT_SUPPORTED. Original-pair replay, code swap, label swap and all six requested negative controls remain NOT_RUN. No authorized private synthetic document scope was available to the live session, and the resident process does not expose a raw validator interface. Attribution remains unknown. The protected validator and both rejected patches retain their prior state.
11. **Exact changes.** Run-specific reports, browser/API evidence, screenshot, and test logs only. Application source delta against the accepted Q5 fingerprints is empty.
12. **Regression.** Focused backend 157 passed / 0 failed / 0 skipped. Focused frontend 31 passed / 0 failed / 0 skipped. Full suite, build and lint were last run in Q5 under the accepted source fingerprints.
13. **Preservation.** The read-only preservation comparison matched observed data, source, global and tenant index metadata, and Git HEAD. All 270 checked historical evidence files retained their entry hashes. The public fixture book had zero loans and zero lending requests before and after proposal and cancellation. The historical Q3 frontend log overwrite remains documented.
14. **Remaining limitations.** Private acceptance requires an authorized disposable private account with the A/B synthetic fixtures and Institution I scope. Private confirmation and paired diagnostics are unverified. Database recommendation relevance and conversational similar/comparison follow-ups need separate diagnosis.

```text
PART_2Q_RUNTIME_ACCEPTANCE: PARTIAL
REAL_QWEN_EXECUTED: YES (17 completed natural-language requests)
LOCAL_ONLY_BORROW_PROPOSAL: PARTIAL (public fixture passed; private fixture NOT_RUN)
UNREQUESTED_LOAN_MUTATIONS: 0
CONVERSATIONAL_SEQUENCES: 2 / 6 (Global)
LIBRARY_SWITCH: PARTIAL (public fixture workflow passed)
PRIVATE_FOR_YOU: NOT_RUN
DIGITAL_AVAILABILITY: PARTIAL
PRIVATE_B_VALIDATOR: UNRESOLVED
PROTECTED_RAG_CHANGED: NO
BROWSER_QA: PARTIAL
BACKEND_TESTS: 157 / 0 / 0
FRONTEND_TESTS: 31 / 0 / 0
PRODUCTION_AUTH_CHANGED: NO
GLOBAL_INDEX_REBUILT: NO
DEPLOYED: NO
COMMITTED: NO
```
