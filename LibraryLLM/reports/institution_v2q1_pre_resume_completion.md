# LuminaR Part 2Q.1 — observed results

## A. Final result

PARTIAL. Real services were exercised and real functional failures were observed; the requested comprehensive quality and security evaluation remains incomplete. 

## B. Executive summary

Four public RAG requests executed real Qwen, MiniLM and FAISS. Actual signed-in browser probes exercised Global and authorized public tenant contexts. One narrow tenant-read concurrency fix was implemented and validated on controlled Core fixtures. A separate five-query public RAG run also completed; all nine raw responses are retained. Direct Global and public TEST Search probes subsequently succeeded.

## C. Current baseline

The Part 2Q source freeze matched at the Part 2Q.1 checkpoint. Historical Part 2Q tests were 3050/0/20 backend and 1028/0/0 frontend; they are not substituted for current results. 

## D. Qwen configuration

Qwen/Qwen2.5-3B-Instruct, resident service reports cuda:0. Source uses local-only loading, 4-bit NF4 and double quantization on CUDA; model configuration in local cache has 32768 maximum positions. Cached revision is recorded in baseline; active loaded revision was not independently proven. Generation is deterministic; temperature/top-p arguments are unused with sampling disabled. 

## E. MiniLM and FAISS

The RAG retriever uses all-MiniLM-L6-v2 and real FAISS; RAG health reports 3959 vectors. The separate Global Search health reports 5000000 active vectors, STALE and baseline_verified false. Source specifies 384 dimensions, HNSW efSearch 128 and rerank depth 50. No Global HNSW execution trace was captured. 

## F. Evaluation dataset

A reproducible inventory of 160 queries exists, covering the requested broad categories. It was built after exploratory probes and is not held out; only recorded live probes were executed. 

## G. Relevance judgments

All labels are provisional or unjudged; no independent human review and no exhaustive Global relevance set. Precision, recall, MRR and nDCG are not validly estimated from this sample. 

## H. Global Search quality

One operating-systems query returned ten titles appearing topically related; one author query returned ten records whose displayed author matched Bram Stoker. These are provisional observations, not validated retrieval metrics. Native Global FAISS use was not traced. The history-free, non-personalized direct Global Search query returned ten machine-learning titles from 50 ranked candidates. Three duplicate UI requests took 1569.508–1626.913 ms. No independent relevance judgments or native Global execution trace were obtained.

## I. Tenant Search quality

Correction to the earlier assistant observation: direct TEST Search succeeded with TENANT_SEMANTIC, READY, LIBRARY_LOCAL/CANONICAL. Twenty results took 854.362 ms; all 20 IDs independently matched active canonical holdings. The broad networking query mixed technical and social/business topics, so relevance remains unjudged. This does not prove the assistant 503 is resolved live.

## J. Private-library Search

Not measured with a disposable private library in this run. Previous Part 2Q deterministic evidence remains historical. 

## K. Global versus tenant

Direct Search succeeded in both scopes, but queries and corpora differ, so these are not comparable retrieval-quality measurements.

## L. Intent interpretation

Beginner Python query requested a reference clarification; exact tenant workbook title was routed to a document-access prompt. Database recommendation was routed to personalized recommendations. Parsed model decisions were not exposed, so exact attribution remains open. 

## M. Live Qwen responses

The separate extended run completed five public RAG questions in 20.860, 15.837, 16.905, 17.361 and 19.226 seconds. Keep this overlapping-resource run separate from the initial four-query timing summary.

## N. Follow-ups

In two fresh Global conversations, “Is the second one available?” after ten search results returned an out-of-range clarification. The browser sent the conversation ID and ten recent IDs. After switching to TEST, an equivalent follow-up returned clarification and no books; this is one isolation observation, not a complete audit. 

## O. Select For You

The TEST library page displayed tenant recommendations and canonical links. An isolation-library assistant quick-action recommendation returned HTTP 503. Live private/small-library recommendation quality remains unmeasured. 

## P. Similar books

Not measured with sufficient evidence. No claim of recommendation similarity quality is made. 

## Q. Local-only and acquisitions

Task-owned Part 2Q.1 scope tests and the full backend inventory cover local-only paths deterministically. The same-fixture concurrency comparison uses 12 local books. Live quality for these cases remains incomplete. 

## R. Availability

The Global result cards displayed copy counts, but independent holdings verification was not performed. The requested Global follow-up failed to bind the second result. Tenant availability was not measured in the 503 cases. 

## S. Grounding and hallucinations

Four public RAG probes: the unrelated machine-learning question abstained but returned SUPPORTED; the smartphone question abstained with NOT_SUPPORTED. Two book questions returned answers and sources, without independent citation verification. This is not a hallucination-rate estimate. The extended run answered two book questions and abstained on smartphones, dinosaurs and publication page count. Answers and verdicts require independent review; no accuracy percentage is inferred.

## T. Knowledge Graph

Live KG relevance was not evaluated. TEST metadata reports a READY published target. Existing protocol and security test groups are included in regression evidence; no graph was built. 

## U. Private RAG authorization

No new live private-document retrieval or foreign-asset trial was completed. Existing regression groups and historical Part 2Q isolated tests provide limited boundary evidence; no new private content was exported. 

## V. Performance and resources

Public RAG endpoint samples (n=4) have median 20.827s and range 17.739–30.911s. Each used two or three model calls. A separate 50-candidate controlled Core fixture completed in 3442.71 ms; no Qwen was used. Stage-level embedding and FAISS times are in performance JSON. p95 and production SLOs are not inferred. A shared GPU/system snapshot is in resource_sample JSON. Direct Search timings and qualifications are recorded in global_search_probe.json and tenant_search_probe.json. The tenant ownership sample is 20/20, not a general isolation guarantee.

## W. Identified defects

Global ordinal follow-up failed twice despite ten recent IDs being sent. Scoped topic and structured recommendation calls returned 503 across two libraries. A canonical-library controlled fixture reproduced the 503 with concurrent book reads. A topical recommendation returned ten results with no literal “database” in title/subjects. Public RAG returned SUPPORTED alongside an abstaining answer. Exact parsed model fields and the live 503 upstream status remain unobserved. 

## X. Controlled fixes

Serialized book hydration within each scoped assistant request, retaining per-book Core authorization and the overall timeout. This avoids self-contention on canonical-library locks and prevents a set of sibling lookups from continuing after the first failed lookup. The existing running service retains previously loaded code; no restart or deployment was performed. Other simultaneous clients can still contend and fail closed. 

## Y. Before/after

A single disposable canonical library, same 12 book IDs and matching book, holdings and copy collection hashes, same structured action and deterministic fixture providers: prior parallel hydration returned HTTP 503 in 280.70 ms with concurrent Core 503s; serialized hydration returned HTTP 200 and ten tenant-owned books in 5747.05 ms, with all twelve Core reads successful. A failing request and a successful request are not comparable success-latency measurements. See same_fixture_final.log and the comparison JSON. This is controlled Core evidence, not a live Qwen or production before/after measurement. The recommendation query omission and reference-scope issues remain unresolved. 

## Z. Security negatives

One actual Global-to-TEST switch cleared the old transcript and returned no book for an ordinal follow-up. This is not sufficient to establish tenant ownership or zero leakage generally. Isolated scope and prior accepted security tests supply additional bounded evidence. 

## AA. Browser QA

PARTIAL. Real signed-in in-app browser exercised Global and public TEST/isolation-library flows, and failures were observed. It did not cover the full requested mobile, private asset, revocation or tenant matrix in this phase. 

## AB. Backend regression

Current run: 3053 passed / 0 failed / 20 skipped; complete=True, 38 groups. The earlier postfix attempt was interrupted and contains process-launch errors; its raw results are preserved. The closure run is the current full-suite result.

## AC. Frontend regression

Current run: 1028 passed / 0 failed / 0 skipped. See frontend log for all raw results. 

## AD. Build and lint

Production build: PASS; lint: PASS, 16 warnings, prior-warning multiset match=True. Raw output, including the build chunk-size warning, is retained. 

## AE. Preservation

Post-observation comparison: PASS. See preservation JSON for each check and any concurrent-state drift. No action intentionally rebuilt an index, activated auth/telemetry, committed or deployed. 

## AF. Changed files

One scoped assistant adapter was changed, one integration test was added, and task-scoped evaluation scripts and reports were created. Exact file hashes and source-freeze comparison are in changed_files JSON. Existing uncommitted application work is preserved. 

## AG. Limitations

Direct tenant semantic Search and canonical ownership were observed for one public library. Global native execution, private-library live quality and comprehensive relevance evaluation remain unverified. Nine evaluated public RAG queries do not meet the requested 30–60 live-Qwen sample; the 160-query inventory does not imply 160 executions. Core, Search, RAG and frontend were unreachable at the recorded resume checkpoint; no services were restarted.

## AH. Acceptance

PARTIAL. Actual model and RAG retrieval ran, but quality defects remain and multiple required metrics and scenarios are not measured. No PASS is asserted from fixture tests. 

## AI. Next scope

Continue Part 2Q.1 only: inspect sanitized upstream errors and parsed reference decisions without changing security; reproduce on controlled disposable data; validate any narrow repair before and after; complete remaining real-model, tenant and security measurements. 
