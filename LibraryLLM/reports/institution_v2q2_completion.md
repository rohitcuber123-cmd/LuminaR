# LuminaR Part 2Q.2

## A. FINAL PASS / PARTIAL / FAIL

PARTIAL. The protected candidate remains unapproved and fails the expanded safety review. Software regression results and remaining model limitations are reported separately.

## B. CURRENT BASELINE

Initial backend: 3097/0/20; frontend: 1028/0/0. Final backend: 3102 / 0 / 20; frontend: 1028 / 0 / 0. Existing dirty work and Git HEAD are preserved. The final run freezes 554 baseline source files plus the two new test/fixture files.

## C. PROTECTED VALIDATOR REVIEW

Verified patch SHA-256: 53a4bbd40eb950622b28a7e5b2b2c0daf9390d1f9dc5d16c5de3ed5031a31c92. The existing Qwen judge exposes supported/confidence only. It receives the question, structured intent and up to three passage texts; authorization is enforced outside the model. Entity, field, negation and conflict matching remain semantic. The informational prompt and qa.py are unchanged. See institution_v2q2_validator_review.md for exact source context and contract impact.

## D. PRIVATE B ROOT CAUSE

Fresh equivalent synthetic PDFs reproduced A answers in 3/3 runs and B answers in 0/3. The B fact survives extraction, chunking, real MiniLM/FAISS retrieval, reranking, context selection and validator input. The original validator returns NOT_SUPPORTED; refusal and source removal follow that decision. The judge exposes no internal explanation. Selected synthetic passages, verdict details, answers, sources and timings are retained in private_B_analysis.json and private_stages.jsonl.

## E. CANDIDATE BEFORE/AFTER RESULTS

The isolated candidate answers A and B in 3/3 runs each using the same resident engine and prepared assets. Each variant retains 6/6 outsider denials. The separate validator matrix covers 25 categories plus four bounded repeats: 58 runs, 56 genuine Qwen calls and two empty-evidence refusals before inference. Original verdicts match 22/29 strict expectations; candidate verdicts match 13/29. The direct matrix generates no final answers; synthetic PDF answers are recorded separately. No failed run was discarded.

## F. SECURITY NEGATIVE TESTS

The original accepts 7/25 strict-negative cases; the candidate accepts 16/25. Clear new candidate failures include wrong entity, wrong field and absent value. False-premise and injection controls also fail; conflicts and injection expose original weaknesses. Yes/no and contradiction oracles can differ from a corrective-answer policy, which is documented. Entity/field failures do not depend on that ambiguity. Raw provenance challenges are separate from access control: all 20 authenticated security checks pass, denied calls produce no private answer, and outsider/revoked browser resource access is denied. Exact per-case evidence is in validator_matrix.json/.md.

## G. PATCH APPROVAL STATUS

NOT APPROVED and NOT APPLIED. Do not apply this candidate based on positive coverage alone. The exact historical diff is retained in institution_v2q2_protected_validator_proposal.patch together with adverse review evidence. Its CRLF check fails against the LF source; a separately hashed LF review copy passes check-only application. Both results are retained in patch_checks.json. Neither artifact is applied. Any source and contract revision requires separate exact approval. Original manifests, frozen tests and protected qa.py/llm.py remain intact; no arbitrary-version exception was added.

## H. CONVERSATIONAL REFERENCES

Only QwenGateway._reference_examples changed. Nonexistent second/third positions now demonstrate clarification, and a single current book has a canonical-ID availability example. For three or more books, example serialization exactly matches the previous revision. No parsed decision override, scope rewrite, schema, lock or resolver change occurred. The final 36 genuine Qwen questions cover Global, A, B and I: all 20 identity assertions match, all four ambiguous that-one requests clarify, and no foreign book IDs return. Eight additional single-page cases pass. Broader semantic coverage remains partial.

## I. BOOK AVAILABILITY

All eight second-item/selected-book availability cases and four single-page stock cases resolve correctly. The final B browser answer confirms two available copies out of two. Its digital-copy follow-up incorrectly repeats physical stock counts despite a visible online resource. This remains an unresolved semantic defect; stock counts are not evidence of digital availability. Four broader API digital-copy cases clarify.

## J. PRIVATE FOR YOU

All ten ownership cases pass across A, B, single-book, five-book, empty, cold-start and unmapped/nonmatching Global-candidate fixtures. GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY is unchanged; fresh local-only acquisitions remain eligible. Scoped results belong to the selected library, and the empty library returns no tenant recommendations. A/B browser rails retain local metadata; all 84 observed B book links belong to B. Relevance remains unreviewed. The controlled Global provider supplies IDs without complete recommendation metadata, producing Unknown Title cards; this is a diagnostic fixture limitation.

## K. BROWSER QA

PARTIAL. One owned IAB session remained available without tab loss. Previous port 18017 was offline after intentional fixture cleanup; the cause of earlier tab disappearance is not proven. This run covers login/logout/relogin, Global For You, A/B For You, book navigation, genuine Global/A/B Qwen cases, private-resource and revocation denial, no-match search, library switching and keyboard Skip-link focus. A successful held A response is canceled on B navigation, with an exact request-ID match and no A conversation content. This is controlled transport timing, not proof of overlapping Qwen generation. A requested 390px viewport produced browser-imposed 487px inner/469px client width; page scroll width was 469px, so exact 390px coverage remains unverified. Missing diagnostic facets 404, temporary library-update 503 and a reload-overlap 502 are retained. Console warnings/errors: zero. See browser_qa.json for exact coverage.

## L. HUMAN RELEVANCE REVIEW STATUS

All 50 original and 20 prior private ranking rows are preserved exactly. The readable 70-row worksheet includes query, library, rank, title, author, metadata, constraints, scale 0/1/2/3/UNKNOWN, and blank reviewer/rationale fields. Human judgments: zero. No relevance labels or Precision@K, MRR or nDCG were fabricated.

## M. LIVE METADATA DRIFT

The historical audit increment of five, membership increment of one and security digest change remain unattributed. The audit sequence is three failed private joins, an access-code change and a successful private join; membership joined_at matches the final event. Counts remain 1935/130/49 during this phase. Current fixture IDs do not appear in those live collections, and prior Part 2Q.1 reports do not reference that scope. Initiator/approval evidence is unavailable. No personal identities were exported, and no live data was rolled back or overwritten.

## N. QWEN PERFORMANCE

Original/candidate validator pairs use the same resident Qwen with identical schema, evidence and authored intent, alternating order and bounded repeats. The latency export retains model loads, exposed input/generated tokens, retrieval/evidence/validation/generation/tool timings and total request time. Sequential A/B cache warming limits causal latency conclusions; direct encode counts exclude chat framing. No first-token/prefill measurements were invented. Precision, provider, inference lock and token caps are unchanged. Only one Qwen model process ran at a time; later serial reloads verified unprotected prompt revisions after candidate comparison finished.

## O. BACKEND REGRESSION

Final accepted product inventory: 38 groups, 3102 passed / 0 failed / 20 skipped, with source unchanged throughout. Coverage includes Assistant, RAG/private authorization, conversation isolation, Search, recommendations, KG, tenant authority, availability, Events, announcements, notifications, Staff, frozen guards, Mongo configuration, operator access and native protocols. The preliminary run is retained but excluded from final closure because source changed during it. Focused 21/0/0 and affected Assistant 439/0/0 repeats are separate, without double counting or suppression.

## P. FRONTEND REGRESSION

Executed npm test: 1028 / 0 / 0. Frontend application source is unchanged. Counts come from current execution logs.

## Q. BUILD / LINT

Production build and lint exit zero. Initial lint had 18 warnings, including two from disposable Vite configuration. Final lint after cleanup is separately recorded and compared with the previous 16-warning baseline. No lint exclusions or warning suppression were added.

## R. GLOBAL PRESERVATION

Current-phase preservation: PASS. Source, global catalogue/HNSW/KG, ranking, recommendations, model configuration, tenant artifacts/holdings, private/personal data, authority/protocols, announcements/notifications and .env checks are recorded. Large artifacts use size/mtime checks. Historical drift remains a separate qualification. Only three explicit initial Search builds ran for newly created fixtures; no existing tenant/global rebuild, auth cutover, telemetry activation, deployment or commit occurred. Owned DB/assets/sessions/temp frontend are removed and regular local RAG is restored.

## S. EXACT SOURCE CHANGES

Application: assistant/qwen.py only, one method. Added tests/institution_v2q_ai/test_v2q2_reference_examples.py and fixtures/v2q1d_three_book_examples.json, covering five new cases. All other Qwen executable AST is unchanged. The complete source/test/script/report inventory and hashes are in institution_v2q2_changed_files.json. Unprotected diff SHA-256: 4eb7f07a774e7e15e7ddda627322a38272b0ab9cde12ae991b28d9507157a6bd. Protected proposal SHA-256: 53a4bbd40eb950622b28a7e5b2b2c0daf9390d1f9dc5d16c5de3ed5031a31c92; unapplied.

## T. REMAINING BLOCKERS

The candidate fails grounding safety review and actual Private B abstention remains unresolved. Some original judge adversarial cases also fail. Digital-copy phrasing and Global related-book discovery remain incomplete. Diagnostic provider/facets and viewport limitations prevent full production browser claims. Independent human judgments and historical metadata ownership evidence remain unavailable. Green software tests do not establish general model accuracy.

## U. NEXT RECOMMENDED ACTION

Reject application of the current protected candidate. Review a more precise grounding revision against the full negative matrix before requesting exact source/guard approval. Obtain independent relevance labels and complete remaining production-equivalent browser checks in a separately authorized follow-up. Stop after Part 2Q.2; Part 2R has not started.

## FINAL QA

PART_2Q2_RESULT: PARTIAL

PRIVATE_B_VALIDATOR: CANDIDATE_ONLY

PROTECTED_PATCH_APPROVED: NO

PROTECTED_SOURCE_CHANGED_WITHOUT_APPROVAL: NO

FALSE_PREMISE_REJECTION: PARTIAL

FOREIGN_DOCUMENT_DENIAL: PASS

MULTI_TURN_CONTEXT: PARTIAL

LIBRARY_SWITCH_ISOLATION: PASS

PRIVATE_FOR_YOU: PARTIAL

REAL_BROWSER_QA: PARTIAL

HUMAN_RELEVANCE: UNAVAILABLE

LIVE_METADATA_DRIFT: UNATTRIBUTED

BACKEND_TESTS: 3102 / 0 / 20

FRONTEND_TESTS: 1028 / 0 / 0

NEW_REGRESSIONS: 0

GLOBAL_HNSW_REBUILT: NO

GLOBAL_KG_REBUILT: NO

PRODUCTION_AUTH_CHANGED: NO

PRODUCTION_TELEMETRY_ENABLED: NO

DEPLOYED: NO

COMMITTED: NO
