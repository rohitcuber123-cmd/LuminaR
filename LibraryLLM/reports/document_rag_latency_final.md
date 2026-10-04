# Document RAG latency finalization

Decision **A**: warm median **14.29 s**; representative RBAC median **9.32 s**, from **25.47 s**. Stretch p90 **37.32 s** remains above 18 s. Correctness preservation is relative to the frozen baseline; the existing GRU implementation answer has known quality defects.

## A. Original exact call graph

`assistant/api.py:install_assistant.chat` authenticates/current identity and validates action/context → `assistant/orchestrator.py:chat` / DOCUMENT_QUESTION tool routing → callback into `rag/api.py:ask` (RAGRequest, HTTP credentials) through threadpool → shared `engine.inference_lock` → `rag/services/book_access.py:authorize_selection` → `rag/qa.py:LuminaRAG.ask` (`profile_request`, `serialized_inference`, same RLock) → `rag/llm.py:analyze_intent` / `_analyze_intent_uncached` → `rag/reranker.py:search` / retriever MiniLM+FAISS and CrossEncoder → evidence ranking → `select_diverse_context` / `build_context` → `rag/fast_filter.py:run_fast_filter` → `rag/llm.py:validate_evidence` top-3 combined (and original partial second pass) → `build_prompt` / `build_compact_prompt` / original refusal prompt → `LuminaRLLM.generate` → deterministic deduped sources in `qa.py:ask` → unchanged assistant schemas/Pydantic/FastAPI serialization.

Semantic slots affect evidence scores and ranked context before validation/answering. Combining semantic classification with answering after retrieval is therefore invalid; no single-pass experiment was run.

## B. Semantic dependency analysis

| Field | Producer | Consumers | Required / fallback | Correctness impact |
|---|---|---|---|---|
| intent | Tier 1 grammar or Tier 2 IntentSchema | rag/evidence.py scoring; rag/reranker.py ordering; rag/fast_filter.py guards; full validator JSON | yes; original classifier | Changes relevance, selected context and support decision |
| actor | Tier 1 / Tier 2 literal slot | calculate_evidence_score actor terms and subject alignment; compute_alignment_signals actor presence; full validator JSON | nullable but material; original classifier/default None only when original schema allows | Changes actor alignment, context ranking and actor support |
| action | Tier 1 / Tier 2 literal slot | calculate_evidence_score action/event terms; compute_alignment_signals event/polarity checks; full validator JSON | nullable but material; original classifier | Changes event matching, directional/causal evidence and support |
| target | Tier 1 / Tier 2 literal slot | calculate_evidence_score combines target terms with action and object alignment; compute_alignment_signals target presence; full validator JSON | nullable but material; original classifier | Changes object/target alignment and relationship direction |
| polarity | IntentSchema positive/negative | evidence scoring, fast-filter negation/polarity and validator JSON | yes/default positive; original classifier | Can reject negated/contradicted claims |
| temporal_relation | Tier 1 grammar/Tier 2 | fast-filter temporal before/after alignment; full validator JSON | nullable hint, still material; original classifier; preserve NONE versus null | Can reject temporal conflicts |
| question_focus | Tier 1 / Tier 2 | generic-cache eligibility and complete JSON in validator prompt | no direct rank arithmetic, preserve nevertheless; original classifier | Changing focus changed validator behavior in compact experiment |
| confidence | IntentSchema constrained float [0,1] | Pydantic validates, then analyze_intent discards it | required model validation, absent in returned intent_data; retain original schema | Not a downstream ranking value; defaults alone did not prove semantic equivalence |
| tier_used | Python classifier branch | returned metadata and full JSON in evidence validator prompt | compatibility metadata; preserve legacy label | Metadata can affect the model prompt; call-count telemetry reports actual skipped calls |

## C. Fields actually consumed

Actual public/internal semantic dictionary: intent, actor, action, target, polarity, temporal_relation, question_focus, tier_used. IntentSchema additionally validates confidence then discards it. There is no object or causal_relation field to remove. Even question_focus/tier_used enter the complete validator JSON, so they cannot be treated as harmless unused fields. The JSON report records every baseline and final semantic dictionary.

## D. Deterministic fast paths

Four tightly bounded literal grammars: `Explain ACRONYM` (no expansion), `According to this PDF, what is noun phrase`, exact roles-described-in-this-document question, and `How is noun phrase implemented in ACRONYM`. Up to six literal words; original full IntentSchema validation and original returned slots/compatibility tier label. The implementation answer prompt remains original. Negation, causal/temporal clauses, multiple entities, quoted terms, ambiguous references and uncertain grammar fall through to the existing classifier. Previously accepted GRU/autoencoder definition paths remain unchanged. Global and book selections remain original.

## E. Compact schema experiment and cache

Rejected compact aliases i/a/v/o/p/t/f/c retained outside production in `document_rag_rejected_compact_candidate.py` and raw compact-trial evidence. Strict aliases mapped through the original full schema; optional null/default values were tested. Nonetheless RBAC and roles became NOT_SUPPORTED despite identical retrieved IDs; a GRU validation path also changed. The compact transport is removed from production, and installation rejects mode=compact. Original semantic cap remains 400; outputs naturally finish before it, so lowering the theoretical cap alone offers no proven speedup.

Optional metadata-only cache: SHA-256 normalized question + document_id + code/classifier hash, maximum 128 entries, TTL 120 seconds, locked copies. Default fast mode disables it. Separate indexing trial: run 1: 14.85 s / 3 calls, run 2: 6.53 s / 2 calls, run 3: 5.86 s / 2 calls. First run uses original semantic inference; later hits are explicitly excluded from the final 42-request statistics. No private document text is cached.

## F. Answer-prompt changes

Compact grounding/style instructions only for conservative definition/topic questions outside the already accepted ordinary_book_intent path, normal/concise depth. Exact context retained byte-for-byte: every passage, header and source identifier. No question or passage duplication was found. Repeated filenames are retained to keep source association clear. Targets 60–100 tokens where useful, allows shorter complete answers, retains 320-token safety budget and natural EOS. Structured citations were already constructed by the backend; no public source schema changed. Refusals, causal/negative/temporal/quoted questions, detailed depth and implementation prompts remain original.

## G. Token reductions

| Case | Baseline answer input → final | Baseline output → final |
|---|---|---|
| rbac_definition | 1712 → 1299 | 107 → 53 |
| roles | 1498 → 1085 | 183 → 26 |
| indexing | 1092 → 679 | 175 → 30 |

Prompt audit: shared system 60 tokens; RBAC question 12, evidence body 860, source headers 143, complete context 1004. Instructions/format 623 → 211 tokens. All other component counts are in the JSON. Full warm tokenization costs 3.8–5.2 ms: no static prefix cache was introduced. Existing token-enforcer/trie cache remains. Overlapping deterministic metadata work would save sub-millisecond source formatting and add complexity; no Qwen pipelining was introduced.

## H. Qwen calls

RBAC/roles/GRU implementation: 3 → 2; acronym with empty retrieval: 1 → 0. Indexing retains 3 calls, with a shorter answer. All remaining classifier/validator call paths stay as baseline. Evidence validation is unchanged across all 42 paired observations, including checked IDs, mode, result and count. Single Qwen2.5-3B NF4 CUDA, luminar_sdpa, KV cache, one inference lock; no concurrent model generation.

## I. Baseline latency

42 sequential warm requests: min 9.10, median 15.17, p90 33.76, max 50.36 s. Representative RBAC is ~25.46 s. Warm startup and excluded warmup are distinct from request time.

## J. Optimized latency

42 cache-free sequential warm requests: min 0.31, median 14.29, p90 37.32, max 45.88 s. The median meets target; the tail does not improve to the stretch target. Empty-retrieval acronym timing preserves baseline behavior and is not an answered question.

## K. 14 questions × 3 repetitions

| Case | Before median s | After min s | After median s | After p90 s | After max s | Calls before → after |
|---|---:|---:|---:|---:|---:|---|
| rbac_definition | 25.47 | 9.12 | 9.32 | 9.81 | 9.81 | 3 → 2 |
| rbac_acronym | 9.33 | 0.31 | 0.32 | 0.33 | 0.33 | 1 → 0 |
| roles | 30.26 | 5.68 | 5.71 | 5.92 | 5.92 | 3 → 2 |
| authentication | 14.41 | 15.76 | 17.22 | 17.70 | 17.70 | 3 → 3 |
| least_privilege | 15.16 | 13.89 | 15.59 | 15.94 | 15.94 | 3 → 3 |
| negative_access | 13.59 | 13.75 | 13.90 | 14.17 | 14.17 | 3 → 3 |
| auth_relationship | 15.07 | 16.21 | 16.72 | 17.87 | 17.87 | 3 → 3 |
| quoted_role | 17.26 | 17.32 | 17.73 | 17.83 | 17.83 | 3 → 3 |
| gru_definition | 10.12 | 10.00 | 10.15 | 10.18 | 10.18 | 2 → 2 |
| gru_update | 49.93 | 42.05 | 43.62 | 45.88 | 45.88 | 3 → 2 |
| gru_temporal | 33.74 | 37.10 | 37.32 | 39.59 | 39.59 | 2 → 2 |
| ambiguous | 12.63 | 13.66 | 14.71 | 15.11 | 15.11 | 3 → 3 |
| indexing | 30.81 | 13.82 | 14.40 | 15.41 | 15.41 | 3 → 3 |
| autoencoder | 10.54 | 10.83 | 11.19 | 11.25 | 11.25 | 2 → 2 |

Every run includes semantic/retrieval/validation/answer/source-construction/serialization/client/server stages, per-call input/output tokens, actual Qwen call count and latency in the JSON report. Raw trace profiles and generation observations are retained. All 42 requests returned HTTP 200 with no errors. Three uploaded PDFs cover definitions, how/why, causal, actor, negative, multiple entities, acronym, ambiguity, quoted phrase and document reference questions.

## L. Source/verdict equivalence

42/42 semantic dictionaries, complete ranked retrieval order, validator observations, fast-filter decisions/signals, verdicts and full returned source objects are identical. Candidate count/context selection/embeddings/index/chunking/reranker/evidence code and original function bodies are unchanged. No unexpected retrieval divergence remains. All 33 fallback answer strings are byte-identical.

## M. Answer quality

**method**: Manual claim review against selected existing chunks, exact fallback answer comparison, six boundary equivalence checks over all 42 pairs; keyword tests supplement rather than replace review.

**rbac_definition**: Grounded role/permission/database explanation. Preserves the essential definition and examples; no added world facts. 53 generated tokens, natural EOS.

**roles**: Lists read, readWrite, dbAdmin, userAdmin and root from the document. Removes baseline mislabeling of readOnly and unsupported role/responsibility mixing. 26 generated tokens; question asks which roles, not a full permissions tutorial.

**indexing**: Preserves creating/listing/dropping indexes and required permissions. Omits verbose examples and unrelated username discussion. 30 generated tokens including EOS, natural completion.

**all_other_cases**: All 33 fallback answers are byte-identical to baseline, including refusals, quoted readWrite, accepted GRU/autoencoder definitions, temporal and implementation answers.

**known_baseline_limitations**: GRU selected passages disagree: hidden-state formula uses (1-z) old + z candidate, while a numerical example treats z=0.9 as retaining 90% old state. The original implementation answer also mixes reset/update equations and reaches its 320-token cap. It remains byte-identical; this task does not certify it as factually correct.

**rejected_quality_candidates**: Compact semantic schema changed RBAC/roles verdicts despite identical retrieved IDs and changed a GRU validation path. Initial short definition prompts lost reset-gate/reconstruction details and were reverted. Short implementation prompts mislabeled a reset-gate formula and were reverted.

**conclusion**: No meaningful new regression in this frozen corpus. Absolute correctness of every legacy answer is not claimed.

## N. Authorization/security

All 13 read-only live probes passed: missing/invalid assistant identity 401, cross-user conversation 404, missing/traversal/absolute source 404, mismatched source IDs 400, book anonymous 401 and absent entitlement 403. Two distinct users can access the same uploaded document with source IDs restricted to that selection: existing uploads are shared/public. There is no owner-scoped cross-user upload denial to claim. One injection/source-boundary probe returned only selected-document sources and no account/book records; this supplements existing regressions and is not a proof of general injection immunity. Authorization remains before generation; no arbitrary file path is read from the selected ID.

## O. Regressions and freeze

Expanded backend 389 passed, 10 existing skips: 336 prior required/repair/independent checks plus 53 focused checks. Independent backend 16 passed; frontend 111 passed, independent frontend 5 passed, production build passed, lint exit 0 with 18 unchanged warnings. An initial broader run also passed the 14 unrelated domain contracts. New tests cover context exception/parallel isolation, original semantic fallback, rejected schema validation, 42-pair retrieval/validator/verdict/source/answer equivalence, metadata cache and real telemetry. One existing httpx deprecation remains.

1208 files frozen (including 681 previous report files). Integrity comparison finds only `rag/api.py` changed among frozen files: two top-level installation lines, all existing function/class ASTs intact. New adapter adds no model loader and leaves llm.generate/validator/reranker identity intact. Existing assistant/frontend/auth/document service/book RAG/scoring and all prior report evidence remain byte-identical.

After removing the rejected transport code, a fresh request through the shipped adapter took 8.894 s with exactly the same RBAC answer, semantic dictionary, validator observation and full sources as the final corpus. This confirmation is separate from, and does not replace, the 42-run statistics.

## P. Other operations latency sanity

One initial pass exposed cold recommendation-service caches. A warmed baseline/fast control on the same resident worker isolates environment variation from document-only code changes. No optimization of these operations was performed. Counts and status/error checks remain intact, and all 15 final warm requests are below 15 s. Single-request sanity timings are not new median estimates.

| Operation | Previous median s | Same-worker original s | Final warm s | Qwen calls |
|---|---:|---:|---:|---:|
| simple_search | 1.27 | 1.25 | 1.39 | 0 |
| complex_search | 11.50 | 12.13 | 11.92 | 1 |
| general_help | 6.76 | 7.03 | 6.63 | 1 |
| default_recommendation | 0.72 | 0.67 | 0.63 | 0 |
| single_seed | 1.30 | 1.36 | 1.36 | 0 |
| explain_recommendation | 11.85 | 12.91 | 12.13 | 1 |
| multi_seed | 2.38 | 2.36 | 2.39 | 0 |
| compare | 0.34 | 0.32 | 0.33 | 0 |
| explain_comparison | 6.87 | 6.85 | 6.73 | 1 |
| availability | 0.32 | 0.31 | 0.30 | 0 |
| fees | 0.31 | 0.31 | 0.30 | 0 |
| loans | 0.33 | 0.36 | 0.33 | 0 |
| reading_list | 0.31 | 0.33 | 0.30 | 0 |
| available_alternatives | 1.34 | 1.34 | 1.29 | 0 |
| authorized_book_rag | 7.14 | 6.55 | 6.51 | 2 |

## Q. Final decision

**A — DOCUMENT RAG <=15S TARGET ACHIEVED WITH CORRECTNESS PRESERVED**, scoped to median warm latency and no meaningful regression against the frozen behavior. Primary median PASS; stretch p90 FAIL/PARTIAL. Existing GRU answer defects are documented, not relabeled as correct. Real circulation/reading-list state stayed unchanged.

## R. Remaining bottleneck and stop

Long legacy grounded answer generation for implementation/temporal questions; 320/276 tokens take approximately 32–44 seconds. Other fallback semantic calls still cost approximately 8–12 seconds. Validator unchanged, typically 1.5–2.5 seconds.

Two sequential process lifetimes: initial baseline/compact trial worker stopped before replacement. All accepted candidate reloads preserve replacement PID 28144 and model id 1683290197904. No second simultaneous resident model.

This narrow experiment stops here. No Part 4 or new retrieval work. Owned service cleanup is recorded in `document_rag_cleanup.json`. Reproduction: run the loopback harness with the same offline environment, baseline control and benchmark --mode baseline; then fast control and benchmark --mode fast. Output phase names must be new because collectors refuse evidence overwrite. Production runs `rag.api:app` and exposes no experiment-control route.
