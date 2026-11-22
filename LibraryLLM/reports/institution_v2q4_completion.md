# LuminaR Part 2Q.4 completion

**A. Final result**

PARTIAL. Narrow reliability and information-intent repairs verified; remaining limits below.

**B. Checkpoint**

3124/0/20 backend;1030/0/0 frontend. Existing dirty work retained; checkpoint and before snapshots recorded.

**C. Recommendation503 cause**

Confirmed source defect: canonical read_context called the unlocked membership guard before its30-second library_mutation wait. A competing ordinary read holds the same gate, so require_readable immediately returned503. Reproduced with a real disposable Mongo lock and actual endpoint. Historical A/B responses lack bodies: cannot attribute every historical503 solely to this cause. Reload502 was separately ECONNREFUSED.

**D. Exact recommendation repair**

For canonical reads, acquire the existing bounded durable authority gate before checking membership. Perform the original guard before canonical maintenance, then repeat original access_locked and final guard. Legacy reads retain original guards. No lock takeover, timeout increase, ranking, candidate mapping, eligibility or recovery-policy change.

**E. Concurrency/retry**

Short lock wait succeeds; revocation during wait404;8 overlapping A/B requests all succeed with own books. Old parallel-client scenario now succeeds too. Existing frontend idempotent-read retry budget retained; controlled browser503 exhausted3 attempts, then one explicit manual retry recovered. No Qwen retry added.

**F. Tenant ownership**

Canonical intersection and recent-local supplementation unchanged. Browser B84/84local book links; stale A HTTP200 canceled on switch. No foreign Global filler.

**G. Informational borrowing cause**

Qwen BORROW_BOOK/RESERVE_BOOK classification could reach propose without a separate user-request modality check.

**H. Borrowing repair**

Narrow interrogative/negative borrowing boundary converts model action labels to physical availability while preserving canonical reference resolution. Eligibility/loan-period questions conservatively clarify rather than invent policy. Explicit requests/actions and confirmation path remain. Digital questions still use Q3 authoritative digital lookup.

**I. Circulation authority**

Actual authority, roles, restrictions and confirmation code unchanged. Owned fixture has0loans and0lending_requests after live checks. No confirmation clicked.

**J. Digital preservation**

All existing digital tests included; real A/B authorized PDF and Global/I UNKNOWN correct. Browser B PDF question after borrowing remains authorized with canonical local link and no physical badge.

**K. PrivateB RAG**

Actual A and B intents have actorunknown/actionrecord/targetcalibration code. Authorized extraction/retrieval/selection preserve each synthetic fact. A supports; B validator returns NOT_SUPPORTED. No source-supported unprotected adapter defect established. Remains unresolved; no tuning loop or source patch.

**L. Protected source**

rag/llm.py and rag/qa.py hashes unchanged; both rejected validator candidates remain unapplied. Frozen guards/manifests untouched.

**M. Security**

Live security cases and complete security/tenant/native/protected suites retained. Revocation while lock waits rechecks authority and denies404; browser revoked A and foreign B resources concealed.

**N. Real Qwen**

16 authorized chat workflows plus2 authorized private RAG workflows;3 additional browser workflows.5 initial fixture authorization denials retained. Browser explicit follow-up partial; PrivateB abstains. Controlled parser fixtures, deterministic API contention and browser transport injection are separate evidence.

**O. Browser**

Global/A/B ForYou, controlled failure/manual recovery, A->B cancellation, local detail, information question, explicit request, digital question, revoked/foreign denials recorded. Exact mobile viewport unavailable;487px observed. Native Tab reaches Skip control. Explicit follow-up clarified instead of proposing; browser remains partial.

**P. Backend**

{'passed': 3133, 'failed': 0, 'skipped': 20} across38groups.9new tests; no newly introduced automated failures. Initial obsolete test failure retained; both original paths and unchanged-data snapshots now require successful responses.

**Q. Frontend**

{'passed': 1031, 'failed': 0, 'skipped': 0};1new recovery test. Preliminary failed runs retained; final run passes.

**R. Build/lint**

Both exit0;16warnings, same16baseline.

**S. Preservation**

Live/global/index/source comparison result: PASS. Overall evidence preservation PARTIAL: accidental Q3runner invocation overwrote Q3frontend.log; original bytes unavailable. Historical JSON counts and original hash manifest retained; damage explicitly recorded. No production auth/telemetry, existing index rebuild, deployment, commit or rollback. Only owned lab removed.

**T. Exact files**

changed_files.json lists7source/test files with before/after hashes. Patch SHA256 53f37371ff601e016c19c499a9cab553ef8d393ab54b10025858234df740b7f8. Supporting files enumerated in artifact_manifest.json.

**U. Remaining product defects**

PrivateB false negative; explicit borrowing conversational reference clarification; policy eligibility remains conservative unknown. No claim every historical503was explained or every possible borrowing wording classified.

**V. Research limits**

Synthetic task-owned data, controlled Global candidates; no5M relevance benchmark, independent reviewer labels or new subjective evaluation. No new validator prompt experiment.

**W. Next scope**

Separately diagnose explicit local-record follow-up resolution and actual validator entity/evidence interaction under protected approval policy. Stop at Part2Q.4; noPart2R begun.

Final QA: institution_v2q4_qa.json. Errors, initial failures and limited coverage remain in raw evidence.
