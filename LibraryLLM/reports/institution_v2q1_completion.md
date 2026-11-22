# LuminaR Part 2Q.1 — observed results

## A. Final result

PARTIAL. Real services were exercised and real functional failures were observed; the requested comprehensive quality and security evaluation remains incomplete.

## B. Executive summary

Thirty evaluated public RAG requests executed the resident Qwen, MiniLM and FAISS across three separately recorded runs. Signed-in browser probes exercised Global and authorized public tenant contexts. One scoped hydration concurrency defect was repaired, tested on identical controlled Core data, and revalidated live after the user restarted services. Grounding and reference failures remain.

## C. Current baseline

The Part 2Q source freeze matched at the Part 2Q.1 checkpoint. Historical Part 2Q tests were 3050/0/20 backend and 1028/0/0 frontend; they are not substituted for current results.

## D. Qwen configuration

Qwen/Qwen2.5-3B-Instruct, resident service reports cuda:0. Source uses local-only loading, 4-bit NF4 and double quantization on CUDA; model configuration in local cache has 32768 maximum positions. Cached revision is recorded in baseline; active loaded revision was not independently proven. Generation is deterministic; temperature/top-p arguments are unused with sampling disabled.

## E. MiniLM and FAISS

The RAG retriever uses all-MiniLM-L6-v2 and real FAISS; RAG health reports 3959 vectors. The separate Global Search health reports 5000000 active vectors, STALE and baseline_verified false. Source specifies 384 dimensions, HNSW efSearch 128 and rerank depth 50. No Global HNSW execution trace was captured.

## F. Evaluation dataset

A reproducible inventory of 160 unjudged queries exists; it does not imply 160 executions. Initial exploratory probes preceded that inventory. The new 21-query public RAG sample was declared before execution, and remains separate from the earlier four- and five-query runs. This is not a comprehensive held-out assistant evaluation.

## G. Relevance judgments

All labels are provisional or unjudged; no independent human review and no exhaustive Global relevance set. Precision, recall, MRR and nDCG are not validly estimated from this sample.

## H. Global Search quality

Selected Global assistant queries returned apparently topical results, with provisional author matching for Bram Stoker. A history-free, non-personalized direct Global Search query returned ten machine-learning titles from 50 ranked candidates. Three duplicate UI requests took 1569.508–1626.913 ms. No independent relevance judgments or native Global execution trace were obtained.

## I. Tenant Search quality

Direct TEST Search succeeded with TENANT_SEMANTIC, READY and LIBRARY_LOCAL/CANONICAL: 20 results in 854.362 ms, all independently matched canonical holdings. After the user restart, the previously failing networking requests returned HTTP 200, no assistant errors and ten results in both TEST and public isolation A. Five resumed result sets contained 50/50 active books in their selected library; 49/50 had holdings. The CN recommendation had no holdings and displayed Availability unknown. Relevance remains provisional.

## J. Private-library Search

Not measured with a disposable private library in this run. Previous Part 2Q deterministic evidence remains historical.

## K. Global versus tenant

Direct Search and resumed assistant discovery succeeded in both public tenant scopes. Global and tenant corpora, queries and judgments differ; no comparable relevance benchmark or private-library quality percentage is claimed.

## L. Intent interpretation

Beginner Python query requested a reference clarification; exact tenant workbook title was routed to a document-access prompt. Database recommendation was routed to personalized recommendations. Parsed model decisions were not exposed, so exact attribution remains open.

## M. Live Qwen responses

Thirty public RAG cases have raw responses and model/retrieval profiles: initial n=4, extended n=5 and restarted n=21. All 21 restarted cases recorded two or three model calls and positive FAISS stage timing. Natural-language browser assistant requests ran against resident services, but their upstream parsed model fields/calls were not independently traced. Structured actions are explicitly marked as using no Qwen.

## N. Follow-ups

The Global ordinal failure was observed twice before restart. The resumed public isolation A conversation reproduced it: after ten Search results, Is the second one available? returned That position is not in the current book list. The follow-up carried all ten recent IDs and matched the previous response conversation ID. A pure-function diagnostic binds SECOND correctly for RECENT_RESULTS/NONE, while empty SELECTED_BOOKS/CURRENT_PAGE_BOOK scopes reproduce the error. The actual parsed scope remains unknown, so no scope fallback or authorization rule was changed.

## O. Select For You

The public TEST Recommend action returned HTTP 200, no errors and ten scoped books after restart. The earlier isolation-library 503 is preserved as historical live evidence. Private Select For You and independently judged small-library recommendation quality remain incomplete.

## P. Similar books

One live local-only workbook seed, independently confirmed to have no global work ID, returned ten scoped recommendations with the seed excluded. Computing, business-network and mathematics topics were mixed. This validates the local-only path, not similarity precision or ranking quality; no independent relevance labels are available.

## Q. Local-only and acquisitions

The completed regression covers local-only paths and the new concurrency repair on disposable data. Live RECOMMEND_SIMILAR also succeeded for the public TEST workbook with global_work_id null. No global mapping was invented and no acquisitions or catalogue mutations were performed.

## R. Availability

The resumed AVAILABLE_NOW action returned ten books with positive available-copy counts; all ten had canonical holdings. It is a collection-level discovery action, not a selected-book availability question. The local workbook detail displayed one total and one requestable copy. Independent quantity reconciliation was not completed, and ordinal availability still failed. The CN recommendation correctly displayed unknown availability when no holdings existed.

## S. Grounding and hallucinations

All 30 public RAG outputs remain provisional. RAG001 and resumed RAG013 produced abstaining answers with SUPPORTED verdicts. RAG027 returned Page 15 with SUPPORTED although every returned source page and all four matched public chunk page values were null; this is an unsupported pagination claim in the source audit. RAG019 may conflate first-journey events with epilogue speculation and needs independent adjudication. No hallucination-rate or citation-accuracy percentage is inferred.

## T. Knowledge Graph

Live KG relevance was not evaluated. TEST metadata reports a READY published target. Existing protocol and security test groups are included in regression evidence; no graph was built.

## U. Private RAG authorization

No live private-document retrieval, revocation or foreign-asset matrix was completed. Public RAG030 abstained on a request for another member’s private documents, but this unauthenticated public-corpus probe is not a private asset authorization test. Existing regression groups retain bounded security evidence; no private document content was exported.

## V. Performance and resources

Separate public RAG timing runs: initial n=4 median 20.827s, extended n=5 range 15.837–20.860s, restarted n=21 median 17.338s and range 11.861–24.003s. Restarted FAISS stages ranged 0.42–36.67 ms. Do not pool runs or infer a production p95/SLO. Resumed assistant networking took 5.377s in isolation A and 11.883s in TEST; structured actions took 10.087–13.366s. Early structured probes overlapped public RAG work. The 50-candidate controlled Core fixture took 3442.71 ms without Qwen. Post-probe resource snapshot: 2416.5 MiB RAM available of 15676.6 MiB; GPU CSV (name,total MiB,used MiB,utilization percent): NVIDIA GeForce RTX 5060 Laptop GPU, 8151, 4083, 0. This is not a peak or per-request measurement.

## W. Identified defects

The tenant 503 was reproduced on controlled canonical Core reads and no longer occurred in the resumed public probes. Remaining observed defects include ordinal binding in Global and isolation A, topical recommendation mismatch, verdict/abstention mismatch and unsupported pagination. Exact parsed decisions remain unavailable; no speculative change to model scope semantics or protected RAG was made.

## X. Controlled fixes

Serialized per-request scoped book hydration, retaining each Core authorization check, input order and the existing overall timeout. Controlled evidence confirms avoidance of self-contention on canonical-library locks and absence of later sibling requests after failure. The user restarted the services; the agent did not restart, deploy or change the model. Subsequent real scoped requests succeeded. Independent clients can still contend and must continue to fail closed.

## Y. Before/after

Same disposable canonical library, same 12 book IDs and unchanged collection hashes: original parallel hydration returned 503; serialized hydration returned 200, ten scoped books and twelve successful Core reads. The prior error and successful request are not comparable success-latency measurements. After the user restart, the same networking input that previously returned 503 succeeded in both existing public libraries, and structured TEST recommendations also succeeded. The final preservation check confirms unchanged tenant data. This supports the narrow repair; it does not establish generalized model or relevance improvement.

## Z. Security negatives

Live tenant switches cleared selected-book and transcript state before new scoped requests. Fifty resumed returned book instances matched active records in their selected public library; there were zero observed cross-tenant book instances in those results. Public instruction probes RAG028/029 abstained and RAG030 returned no private content. These bounded cases do not establish private-library or foreign-asset security generally; deterministic authorization/mutation suites supply separate evidence.

## AA. Browser QA

PARTIAL. The real signed-in browser exercised earlier Global/public tenant flows plus six resumed cases. Recommendations, available-only discovery, local-only similarity and networking succeeded; ordinal context failed. Full mobile, private asset, revocation and tenant security matrices remain incomplete. Sanitized browser observations are retained without credentials or account identifiers.

## AB. Backend regression

Current application tree: 3053 passed / 0 failed / 20 skipped across 38 completed groups. The interrupted earlier attempt and its launch errors remain preserved. No additional application source changed during resumed evaluation, so the executed closure run still covers the current source tree.

## AC. Frontend regression

Current run: 1028 passed / 0 failed / 0 skipped. See frontend log for all raw results.

## AD. Build and lint

Production build: PASS; lint: PASS, 16 warnings, prior-warning multiset match=True. Raw output, including the build chunk-size warning, is retained.

## AE. Preservation

Final resumed preservation comparison: PASS. All 553 frozen source files match except the intended scoped adapter change, and all 594 prior reports match. Tenant records, private logical state, Mongo indexes, communications, global/tenant artifacts and HEAD match the saved checkpoint. Large global artifact checks use size/mtime, as recorded in preservation limits. No rebuild, auth/telemetry activation, commit or deployment was performed.

## AF. Changed files

One scoped assistant adapter was changed, one integration test was added, and task-scoped evaluation scripts and reports were created. Exact file hashes and source-freeze comparison are in changed_files JSON. Existing uncommitted application work is preserved.

## AG. Limitations

Thirty public RAG queries are not representative Global/tenant assistant quality coverage. The 160-row query inventory remains unjudged and mostly unexecuted. Global native HNSW execution, live private-library quality, independent relevance judgments and the complete browser/security matrix remain unverified. Raw response metadata cannot establish factual accuracy. Two structured browser timestamps were not retained across navigation; their elapsed times were captured before navigation. Three timing runs must not be pooled. Services were initially unavailable, then the user restarted them and signed in; the old checkpoint/report is preserved separately.

## AH. Acceptance

PARTIAL. Complete backend/frontend checks, build, lint and preservation pass, and the narrow tenant repair has both controlled and live support. Observed grounding/reference failures, unjudged relevance and incomplete private-library coverage prevent overall PASS.

## AI. Next scope

Continue Part 2Q.1 only: inspect actual parsed reference decisions using authorized non-production diagnostics; complete independent relevance and live private-library/asset evaluation; propose a separately reviewed protected-RAG repair for observed grounding defects. Do not alter the protected implementation or weaken scope binding automatically. See institution_v2q1_grounding_followup_proposal.md; it applies no source changes.
