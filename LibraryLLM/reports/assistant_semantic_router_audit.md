# LuminaR semantic router repair — PARTIAL

The architecture and required six-turn live scenario pass. Broad semantic generalization does not: 67/116 (57.8%) under strict real-Qwen fixture evaluation. This is not full acceptance. All failures and decoded decisions remain in the cases report.

## A–C. Root cause and old rules

The old closed comparison/reference grammars missed preference follow-ups. Qwen received IDs without selected titles or criteria memory. Its pseudo-entities could reach fuzzy Core title lookup and Search fallback; one generic book-choice clarification handled both unknown books and unknown preference criteria.

Removed from live routing: `selected_command`, `reference_kind`, message-based `comparison_fields`, typo replacements, comparison/details/availability/recommendation regex grammars, account phrase dictionaries, mutation/source phrase rules, `simple_search`, concept regex overrides, generic recommendation overrides, typed graph phrase list, typed continuation/refinement phrase lists, ordinal text regexes and prose-trigger phrase tests. The original versions are retained in `assistant_semantic_router_baseline/assistant`; original tests are also saved there.

Retained structural rules: explicit action enums and arguments, cardinality, canonical work IDs, literal entity gates, normalization, bare-reference rejection at the fuzzy lookup gate, owner/TTL state, pending confirmation, empty/stale result guards, pagination offsets, field validation, rank fusion and API-authoritative response rendering. Remaining token regex identifies literal work IDs; it does not classify language.

## D–F. Router, compact prompt and schema

Ordinary typed message → bounded identity context → one resident Qwen generation → strict Pydantic validation → deterministic reference binding → existing tool APIs → structured response. Explicit UI actions, confirmation/cancellation and SHOW_MORE bypass semantic generation. There is no separate model resolver/planner or invalid-output regeneration loop.

The fixed prompt with empty message/context is 3441 characters, with eight conceptual examples; none of the 116 corpus messages is copied verbatim into an example. Measured final routing inputs range 873–1098 tokens including system/chat framing, message and context. The 20-query median is 930 input and 22 output tokens. Max routing output remains 180 tokens.

`AssistantIntentDecision` extends existing public-compatible intent fields with `reference_scope`, `reference_position` (ALL/FIRST/SECOND/LAST/OTHER/FOCUS), semantic `goal`, `criterion`, `clarification_type` and `context_operation`. Existing `resolved_work_ids`, requested comparison fields, queries and validated filters remain. Compact internal keys i/c/s/e/g/p/d/w/k/q etc. expand before strict validation. Numeric ordinals remain in the executor for legacy contracts but are excluded from the current model decoder to avoid inconsistent indexing. IDs are checked against supplied canonical sources; model confidence is not factual evidence.

Generation: existing Qwen2.5-3B-Instruct 4-bit model, CUDA, do_sample=False, use_cache=True, repetition_penalty=1.0, no_repeat_ngram_size=0 for constrained JSON. Existing inference lock, one executor slot, 60-second timeout, enforcer and Pydantic limits stay. No global model/generation or RAG settings changed; no new model installed.

## E, G–H. Context and references

Context contains selected identities (work_id/title/authors), page identities/document ID, two resolved semantic turns, last intent/focus, previous comparison, previous recommendation IDs/seeds, active result type/IDs/query/filters/has_more and awaiting_criteria. At most 16 brief identities, four active identity records and 20 active IDs are supplied. No descriptions, RAG chunks, private account data, full transcript or hidden reasoning.

Precedence: exact structured action arguments → literal named books/entities → selection → active comparison/recommendations → page → recent resolved references → gated catalogue resolution → clarification. Selection overrides stale result/page scope; invented or stale subset IDs are rejected. Explicit empty result lists block stale fallback. FIRST/SECOND/LAST bind to authoritative order; OTHER requires a pair and one focused member; FOCUS requires one unambiguous referent. A reading-goal answer awaiting criteria preserves the established comparison pair. Named resolution requires EXPLICIT_BOOK plus an actual literal entity; bare conversational references cannot search titles.

Known gap: the model sometimes emits the wrong scope/position/intent despite these rules. Safe rejection does not count as successful routing. Previous-comparison-with-empty-selection, changed-selection and page-only model failures remain in the corpus.

## I–L, S. Required live scenario and clarification

Instrumented real Qwen + Mongo catalogue + normal authenticated API tools: 6/6 passed. Sports-economics IDs: `OL25644705W`, `OL20667625W`. Comparison keeps both; “which one would be better” keeps both and asks CRITERIA_AMBIGUITY with no book choices. The soccer-economics criterion keeps both and explicitly says metadata cannot establish a justified winner. Availability resolves first A, then OTHER B, then More Like This uses B. Six routing calls total, zero prose calls, zero fuzzy title or Search calls. Additional normal HTTP validation is recorded separately in `assistant_semantic_router_http.json`.

Clarifications are distinct: REFERENCE_AMBIGUITY, CRITERIA_AMBIGUITY, INSUFFICIENT_SELECTION, TITLE_AMBIGUITY. Comparison facts/ratings/subject counts/availability come from APIs. Missing content and suitability stay unknown; no winner is inferred from titles.

## M–N. Unseen language evaluation

Real resident Qwen with authoritative synthetic catalogue/API fixtures, independently established contexts and strict intent/reference/criteria/field checks. Fixtures are explicitly synthetic; live validation above uses actual Mongo/API data. Unit mocks are not counted as language accuracy. All 116 utterances made one actual intent generation; no response generation. Criterion queries must extract a nonempty criterion and avoid asking for it again.

| Category | Strict passes |
| --- | --- |
| factual_comparison | 4/12 |
| preference | 12/12 |
| preference_criterion | 5/10 |
| availability | 5/10 |
| field_comparison | 5/5 |
| subject_comparison | 3/3 |
| ordinal_details | 7/10 |
| ordinal_availability | 5/6 |
| graph | 4/8 |
| recommendation | 3/5 |
| search | 4/8 |
| account | 4/13 |
| reference_ambiguity | 5/5 |
| previous_comparison | 0/3 |
| selection_change | 1/3 |
| explicit_entity | 0/2 |
| page | 0/1 |

Fuzzy-title false positives: 0/106 non-search/non-entity cases. Unrelated Search fallback: 0/106. No invented title choices from pronouns were observed. Correct preference-without-criterion behavior is 12/12; that does not erase failures in factual versus preference classification, explicit criterion extraction, account intent selection or context scopes.

The model also classified a saved-list read query as CLEAR_READING_LIST. The final executor blocks every model-only list-wide clear and requires the existing explicit Clear UI action; a regression verifies no reading-list calls execute. The original observed case remains a failure. Borrow/return/reserve confirmation remains unchanged. Reading-list positional removal checks the latest owned IDs before writing.

## O–P. Calls and latency

20 identical benchmark requests/contexts, same existing resident model, sequential measurements; synthetic tool fixtures, not an end-to-end production-load SLA. Baseline snapshot: 24 total = 19 routing + 5 prose. Final: 20 total = 20 routing + 0 prose. One old exact fast path used zero calls; all nuanced typed requests now use one. Explicit structured controls still use zero routing calls.

Median total: 3.99s → 2.88s. Median routing generation: 3.68s → 2.86s. Median tool time: 0.28ms → 0.18ms. Model timings vary substantially; the report keeps every request/token/stage sample.

## Q–R, T. Regressions and frontend

703 backend/security/admin/notification/renewal/KG tests pass, 10 opt-in dynamic-book integration tests skipped. Assistant contracts: 409; security: 115; admin/staff: 76; notifications: 51; renewals: 40; frozen graph: 12. Search/recommendation continuation, selected context, account ownership, Know More/book access and private document RAG boundaries are covered. The skipped tests require explicitly prepared isolated Mongo/full-text/FAISS fixtures and are not represented as passes.

Frontend assistant: 85/85 passed. Production build passed. Lint exits successfully with 19 existing frontend warnings. Existing store already sends conversation_id, selected_work_ids, page_context and structured actions; its context label truthfully uses selected-book count. No frontend source change was needed for this semantic phase.

117 frozen Python sources under Core/backend, Search, Recommendation, KG and RAG match pre-edit SHA-256 hashes. `assistant/tools.py` also matches the snapshot. Ranking/RRF, graph construction, RAG, admin and notification implementations were not changed.

## U. Exact changed source/test files

- `assistant/contextual.py`
- `assistant/kg_routing.py`
- `assistant/orchestrator.py`
- `assistant/qwen.py`
- `assistant/routing.py`
- `assistant/schemas.py`
- `assistant/state.py`
- `assistant/semantic.py`
- `tests/test_assistant_backend.py`
- `tests/test_assistant_kg.py`
- `tests/test_assistant_latency.py`
- `tests/test_assistant_part3.py`
- `tests/test_assistant_part3_repair.py`
- `tests/test_assistant_selected_context.py`
- `tests/test_assistant_semantic_router.py`
- `tests/test_document_rag_latency.py`
- `scripts/evaluate_assistant_semantics.py`
- `scripts/check_assistant_semantic_http.py`

Generated artifacts: `assistant_nlu_audit.md`, this audit, cases/latency/live/HTTP/regression JSON, XML test reports and text logs, plus original source snapshots and intermediate evaluation records. The project has no Git metadata; preservation is verified by snapshots/hashes.

## V. Limitations and acceptance

PARTIAL. The required selected-book failure is repaired and measured. Broad semantic accuracy (57.8%) is insufficient for general acceptance: factual contrast can be mistaken for preference, stated criteria can be missed, account intents can be wrong, and correct contextual books can be rejected. Pydantic and scope guards prevent many unsafe fallbacks but cannot make an incorrect model classification correct. Model-reported confidence is not calibrated. Typed list-wide clearing now requires the explicit UI control. No tuning outside assistant routing, new model installation, ranking changes or new KG/RAG work was performed. Normal-service HTTP results and final service health accompany this report.


## Final HTTP and service validation

Normal `uvicorn rag.api:app` service restored on 127.0.0.1:8005. Authenticated HTTP validation: required six-turn chain 6/6; additional four-turn comparison → availability → subjects → related chain 1/4 (7/10 overall). Each typed HTTP request records one actual routing generation and no prose generation. Explicit Compare passes with zero Qwen calls. The additional chain incorrectly asks criteria for factual contrast, then loses availability and subjects follow-ups; these are failures, not successes. No borrowing, returns, reservations, notices or user messages were sent by live validation. Public catalogue reads only.

The original language corpus remains 67/116. The final list-wide-clear execution guard is covered by an additional regression and does not alter that model-classification score. 703 backend tests pass, 10 optional integration tests skipped; 85 frontend tests pass. Final frozen-source hash check finds zero changes in 117 files. Full HTTP traces and numeric timings are in `assistant_semantic_router_http.json`; service health is in `assistant_semantic_router_health.json`.
