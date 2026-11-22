# LuminaR Part 2Q — implementation and final validation

## A. Final result

PASS. Application implemented and final actual-tree validation executed. Model semantic quality is not claimed from deterministic fixtures.

## B. Executive summary

The existing chatbot now follows Global or a currently authorized canonical library. Local discovery, For You, saved references, metadata, stock, KG and selected-asset RAG use scoped adapters. No second assistant/model/runtime.

## C. Confirmed root causes

Explicit assistant transport dropped lending_context; conversations checked owner but not library; browser context persisted across library switches; global-only card selection hid local-only books. Existing tenant For You/intersection already worked and was retained.

## D. Transport fix

Explicit request serialization retains library_id and accepted lending_context/library/book/loan/reservation fields, alongside original optional fields. UI-only page_path and arbitrary properties are not sent.

## E. Effective library scope

GLOBAL or LIBRARY:canonical UUID. Request-local bearer reaches existing Core catalogue source/context validation. Current membership, private proof and role are authoritative. Revalidation after ordinary turns rejects revocation/role changes during generation; existing atomic confirmation protocols retain their original endpoint authorization.

## F. Conversation isolation

ConversationStore checks owner plus exact scope before resolving references; existing TTL, lock and bounded eviction retained. Missing scope cannot downgrade a private conversation. Confirmation may recover immutable pending scope from server state, never replacement client lending arguments.

## G. Global preservation

Global-only clients follow the original orchestrator/tool branch. Qwen, parser/router implementation and candidate algorithms are unchanged. Original global tests and actual browser global Search/recommendation/For You pass.

## H. Institution chatbot

Real Core integration tests include a PUBLIC_LIBRARY and private institution; authorized search/For You return only canonical current-library records. Staff flag derives from current server role; no client grant.

## I. Private chatbot

PRIVATE_INSTITUTION/PRIVATE_CODE admission remains existing Core authority. Cross-library, foreign owner, foreign references, forged lending context and revocation scenarios fail closed.

## J. Tenant discovery

Existing tenant Search endpoint first; operational failure falls back to existing authorized Core discovery. Authorization/validation failures do not fall back. No global replacement, new Search engine or automatic index build. Original READY/STALE/NOT_BUILT/FAILED/recovery suites retained.

## K. Select For You

Missing control was BookPersonalActions global-ID gating, not absent tenant recommendations. Actual owned local-only records now expose the existing assistant selection action in their authorized route. Personal linked saved references preserve their accepted selection behavior; Core resolves holdings before scoped output.

## L. Recommendation preservation

Up to 50 global candidates / 8s timeout feed the existing canonical tenant intersection, preserve ordering and recent local acquisitions. GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY label remains. Provider outage leaves the existing local supplement available.

## M. Local identities

Assistant work IDs are canonical library_book_id UUIDs for tenant output, with separate library/global identity metadata. Detail links use /libraries/UUID/books/UUID, including local-only and new acquisitions. Backend strings serialize safely.

## N. Availability

Book cards use current Core availability.requestable/total and shelf, never global copy counts. Follow-up ordinal tests and Chromium verify actual fixture stock.

## O. Similar books

Mapped seeds use existing global seed candidates plus tenant intersection. Local-only seeds use actual subjects via authorized tenant Search, excluding the seed. Sparse/no-subject catalogues truthfully return no similar matches; no invented score/padding.

## P. KG authority

Existing tenant graph endpoint only, current role and READY generation. Shared visible entity counts are real bounded graph metadata; every resulting book rehydrates through current Core holdings. Foreign candidates rejected; not-ready graph produces an explicit unavailable result without build/global fallback.

## Q. RAG authority

Selected library requires matching library:UUID:asset: reference before the original callback. Original asset authorization/retrieval remains authoritative. No metadata presented as document text. Protected assistant/api.py, rag/qa.py and manifests unchanged. New positive callback test is a boundary fixture, not PDF/semantic accuracy evidence.

## R. Frontend switching

Current router path drives scope even before page metadata catches up. Scope/role/token changes clear conversation, selected/recent IDs, document context and pending work. Private persisted references reset on reload. Declarative scope validation hides mismatched transcripts before effects run.

## S. Caching/concurrency

No new response cache. Existing request-local tools, scope-checked bounded server state, AbortController and monotonic revision guard prevent late response overwrite. Stored global compatibility retained; private title/reference restoration requires new authorized reads.

## T. Security tests

New scope unit/API scenarios plus 16 frontend cases; original security, tenant, source-contract mutation, Mongo fail-closed, operator, lending/reservation and RAG suites run. No original assertion edited or disabled. See security_tests JSON and raw JUnit.

## U. Backend tests

3050 passed / 0 failed / 20 skipped across 38 accepted inventory groups. New scope group includes 53 cases. Full actual-tree raw logs/JUnit retained.

## V. Frontend tests

1028 passed / 0 failed / 0 skipped; production build and lint exit0. Existing lint warnings retained, no new errors. Original 1012 cases plus 16 new scope cases.

## W. Chromium QA

PASS: 17 checks, actual password login/JWT, API/orchestrator/Core/Mongo, Global/A/B, recommendations, local-only selection, detail links, follow-up stock, foreign asset denial, revocation, mobile 390px, axe and Escape. Deterministic intent/candidate providers; native Search503 fixture exercises actual Core fallback. No real Qwen/native semantic claim.

## X. Performance

Actual bridge and Core endpoint elapsed samples in performance JSON, concurrent regression load. Membership source/context, tenant discovery and combined intersection/acquisition-supplement requests are measured. Intersection versus supplement costs and resident Qwen inference are not measured separately. Small fixture sample only; no production SLO extrapolation or model reload introduced.

Owned-fixture endpoint samples: membership_source_or_context: n=29, 11.97–35.83 ms; tenant_discovery: n=2, 64.04–125.49 ms; tenant_intersection_and_acquisition_supplement_combined: n=2, 47.10–47.68 ms.

## Y. Full regression

Zero final new failures if final QA PASS. Intermediate failures and fixes retained in regression JSON/logs. Full suite includes Search, recommendations, private data, circulation, KG, RAG, Knowledge Tools, Events,2P announcements,2P.1 custom notifications, Intelligence, Mongo and protected contracts.

## Z. Preservation

Read-only checkpoint compares global 5M count, HNSW/KG metadata, tenant generations/artifacts/jobs, membership/inventory/communications, Mongo indexes, private logical registries, protected sources and prior reports. No global scan/rebuild, live auth/telemetry change, deployment or commit. See preservation JSON for actual booleans and evidence limits.

## AA. Exact changed files

See changed_files JSON: pre-task SHA compared with current SHA for every modified existing source, plus new adapter/tests/scripts and evidence artifact hashes. Existing uncommitted2P/2P.1 work is retained. assistant/api.py is byte-identical.

Exact implementation delta against the preimplementation checkpoint (SHA256 before/after in changed_files JSON):

- [assistant/library_scope.py](D:/SDC/LibraryLLM/assistant/library_scope.py)
- [assistant/orchestrator.py](D:/SDC/LibraryLLM/assistant/orchestrator.py)
- [assistant/schemas.py](D:/SDC/LibraryLLM/assistant/schemas.py)
- [assistant/state.py](D:/SDC/LibraryLLM/assistant/state.py)
- [assistant/tools.py](D:/SDC/LibraryLLM/assistant/tools.py)
- [backend/routes/library_catalogue_experience.py](D:/SDC/LibraryLLM/backend/routes/library_catalogue_experience.py)
- [backend/services/library_catalogue_experience.py](D:/SDC/LibraryLLM/backend/services/library_catalogue_experience.py)
- [frontend/package.json](D:/SDC/LibraryLLM/frontend/package.json)
- [frontend/src/components/AIChatWidget.tsx](D:/SDC/LibraryLLM/frontend/src/components/AIChatWidget.tsx)
- [frontend/src/components/AssistantLibraryRequestButton.tsx](D:/SDC/LibraryLLM/frontend/src/components/AssistantLibraryRequestButton.tsx)
- [frontend/src/components/BookPersonalActions.tsx](D:/SDC/LibraryLLM/frontend/src/components/BookPersonalActions.tsx)
- [frontend/src/components/assistant/AssistantTurn.tsx](D:/SDC/LibraryLLM/frontend/src/components/assistant/AssistantTurn.tsx)
- [frontend/src/index.css](D:/SDC/LibraryLLM/frontend/src/index.css)
- [frontend/src/lib/assistant.ts](D:/SDC/LibraryLLM/frontend/src/lib/assistant.ts)
- [frontend/src/lib/assistantTypes.ts](D:/SDC/LibraryLLM/frontend/src/lib/assistantTypes.ts)
- [frontend/src/lib/libraryCatalogue.ts](D:/SDC/LibraryLLM/frontend/src/lib/libraryCatalogue.ts)
- [frontend/src/pages/LibraryCatalogue.tsx](D:/SDC/LibraryLLM/frontend/src/pages/LibraryCatalogue.tsx)
- [frontend/src/store/useAssistantStore.ts](D:/SDC/LibraryLLM/frontend/src/store/useAssistantStore.ts)
- [frontend/tests/assistant-library-scope.test.tsx](D:/SDC/LibraryLLM/frontend/tests/assistant-library-scope.test.tsx)
- [scripts/institution_v2q_ai_browser.py](D:/SDC/LibraryLLM/scripts/institution_v2q_ai_browser.py)
- [scripts/institution_v2q_ai_checks.py](D:/SDC/LibraryLLM/scripts/institution_v2q_ai_checks.py)
- [scripts/institution_v2q_ai_preservation.py](D:/SDC/LibraryLLM/scripts/institution_v2q_ai_preservation.py)
- [scripts/institution_v2q_ai_report.py](D:/SDC/LibraryLLM/scripts/institution_v2q_ai_report.py)
- [scripts/institution_v2q_checks.py](D:/SDC/LibraryLLM/scripts/institution_v2q_checks.py)
- [tests/institution_v2q_ai/conftest.py](D:/SDC/LibraryLLM/tests/institution_v2q_ai/conftest.py)
- [tests/institution_v2q_ai/test_integration.py](D:/SDC/LibraryLLM/tests/institution_v2q_ai/test_integration.py)
- [tests/test_assistant_library_scope.py](D:/SDC/LibraryLLM/tests/test_assistant_library_scope.py)

## AB. Limitations

No real Qwen inference or native semantic accuracy measured in the new browser fixture. KG uses existing 100-book projection; local sparse similarity may be empty. Saved-list adapter returns at most 50 current holdings. Private references reset on refresh; no new persistent chat DB. No new ranking engine/filter or public absent-seed expansion. Actual PDF model quality is outside the new boundary fixture.

## AC. Improvement review

Authority enforced in endpoints/adapters, never prompt-only. Reused existing For You and resident runtime. Fixed original transport/drop and selection gating instead of adding duplicate features. Kept source guards and original tests; scoped presentation fixes address measured browser issues.

## AD. Next scope

Stop at Part 2Q. Optional separately requested evaluation: resident Qwen intent/answer quality and native tenant Search relevance on a curated owned dataset; extend bounded KG pagination if justified. No RSVP or infrastructure activation started.

Final QA: `institution_v2q_ai_final_qa.json`. Detailed executed evidence: backend_tests, frontend_tests, security_tests, browser, performance, regression, preservation and changed_files in this report namespace.
