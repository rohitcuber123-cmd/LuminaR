# Semantic Router V2 â€” FINAL FAIL

No production promotion. The existing compact router is restored and its original live chain passes 6/6. This phase stops at the failed adequacy gate.

A. **Outcome:** FAIL. Existing 90%, held-out 85%, critical 95%, original six-turn and safety gates failed.

B. **Baseline:** authoritative and reproduced compact result 67/116 (57.76%). All original evidence remains unchanged.

C. **Failure analysis:** exactly one category for each of 49 baseline failures. Counts: {"EXPLICIT_ENTITY_FAILURE": 2, "MISSED_CRITERION": 5, "PAGE_CONTEXT_FAILURE": 1, "UNNECESSARY_CLARIFICATION": 3, "WRONG_ACCOUNT_INTENT": 9, "WRONG_GOAL": 7, "WRONG_INTENT": 9, "WRONG_REFERENCE_POSITION": 9, "WRONG_SEARCH_EXTRACTION": 4}. Full messages, expected decisions, raw model outputs and executor results are in the failure-analysis JSON/Markdown.

D. **Compact vs descriptive:** A 67/116; B 70/116 (60.34%), a 2.59-point gain. The legacy scorer initially counted B as 73/116; three wrong-goal tables were rejected by the stronger check. A stays 67/116. Raw pre-audit evidence is preserved separately. Descriptive median 5.71s versus compact rerun 4.49s.

E. **Controlled matrix:** unchanged 116 utterances, contexts, authoritative synthetic API fixtures, Qwen checkpoint and generation settings. One resident model at a time; service restarts reload the same cached model, never a second concurrent model. A/B/C retain old dimensions; D changes the formulation to server binding and a smaller transport; E adds hierarchy; E2 is one additional conditional-field schema experiment; F is D plus at most one inconsistency retry. No held-out tuning.

| Variant | Strict | Intent | Handle | Position | Criterion | Invalid schema | Fuzzy calls | Median / p90 | Qwen/request | Input/output tokens |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 67/116 | 68.1% | 95.5% | 81.8% | 50.0% | 0 | 0 | 4.49s / 5.64s | 1.000 | 931/24.5 |
| B | 70/116 | 74.1% | 96.6% | 87.5% | 100.0% | 0 | 0 | 5.71s / 8.79s | 1.000 | 1148/31.5 |
| C | 70/116 | 76.7% | 96.6% | 87.5% | 100.0% | 0 | 0 | 5.65s / 7.84s | 1.000 | 1258/31 |
| D | 76/116 | 72.4% | 86.4% | 88.6% | 70.0% | 0 | 0 | 2.93s / 4.07s | 1.000 | 702/18 |
| E | 55/116 | 60.3% | 71.6% | 81.8% | 0.0% | 0 | 1 | 2.69s / 3.17s | 1.000 | 699/17 |
| E2 | 73/116 | 69.0% | 76.1% | 83.0% | 90.0% | 0 | 8 | 2.91s / 4.12s | 1.000 | 772/17.5 |
| F | 76/116 | 72.4% | 86.4% | 88.6% | 70.0% | 0 | 0 | 2.76s / 7.82s | 1.190 | 701/18 |

F. **Chosen architecture:** F (D plus bounded retry) was frozen before held-out inference using strict, critical, then median-latency ordering. D and F tie on strict/critical accuracy; their first raw outputs are identical. F's lower median is not evidence that retries speed generation: its p90 and retry totals are much worse. Neither is promoted; production/default remains A.

G. **Handles:** server-only S selection, C previous comparison, R recommendations, T active results, P page, F recent resolved books. Only available sources are built. Authoritative precedence pre-binds the permitted primary context; the model sees bounded title/author/position, never canonical IDs. Literal entity text must be grounded before existing catalogue resolution. That grounding alone did not prevent the two held-out pseudo-title failures.

H. **Dynamic intents:** capabilities/context only, no message-based shortlist rules. Document questions require document context; model-only list clear is excluded; known book context enables seeded/list/book operations. Explicit UI actions retain precedence and zero routing calls.

I. **Hierarchy:** E 55/116; E2 73/116. Required nullable criterion for PREFERENCE, nonempty fields for FIELD, and pre-bound whole-set comparison improved criterion extraction but did not meet broad accuracy or safety gates. The flat handle candidate was stronger overall.

J. **Retry:** only schema/structural inconsistency; maximum one extra routing call. Existing 22/116 (18.97%), hidden 22/121 (18.18%). First-pass structurally valid 94/116 and 99/121. Existing retries ended with 5/22 strict passes; hidden 0/22. F does not improve aggregate strict accuracy over D. The shorter correction prompt retains the capability shortlist, which is a limitation of this experiment.

K. **Existing:** 76/116 (65.52%), below 90% acceptance and 85% adequacy.

L. **Held-out:** 68/121 (56.20%), below 85% acceptance and 80% adequacy. The initial presence-only result was 69; semantic review rejected one criterion that omitted the soccer requirement. The original presence score and manual review remain available. The set was sealed before inference; all category minima and 20 previous-comparison paraphrases are present. No held-out utterance became a prompt example or production rule.

M. **Critical:** existing 56/88 (63.64%); held-out 44/91 (48.35%); combined 100/179 (55.87%), below 95%. Defined before results: selected/comparison/changed/page contexts, excluding literal-entity and search categories.

N. **Per-category:** intent existing 84/116 (72.41%), hidden 83/121 (68.60%). Context-handle binding 76/88 and 69/91; position 78/88 and 81/91; end-to-end resolved reference 103/116 and 96/121. Criterion meaning/coherence 7/10 and 8/14; presence-only hidden 9/14. Clarification 113/116 and 116/121. Handle and position scores are separate from overall correctness; a correct binding cannot rescue a wrong intent/goal.

| Category | Existing F | Held-out F |
|---|---:|---:|
| account | 10/13 | 14/15 |
| availability | 3/10 | 5/10 |
| explicit_entity | 0/2 | 1/5 |
| factual_comparison | 11/12 | 13/18 |
| field_comparison | 3/5 | â€” |
| graph | 2/8 | 1/5 |
| ordinal_availability | 4/6 | â€” |
| ordinal_details | 6/10 | 5/5 |
| page | 1/1 | 0/5 |
| preference | 10/12 | 5/5 |
| preference_criterion | 7/10 | 8/14 |
| previous_comparison | 1/3 | 4/16 |
| recommendation | 4/5 | 2/10 |
| reference_ambiguity | 5/5 | â€” |
| search | 5/8 | 9/10 |
| selection_change | 3/3 | 1/3 |
| subject_comparison | 1/3 | â€” |

O. **Safety:** selected primary corpus zero fuzzy-title calls and zero unrelated Search fallback. Held-out two of each, so safety FAIL. Model-only reading-list clear and confirmation bypass remain zero in contract tests; no real circulation/list mutation was executed by the live scripts.

P. **Qwen:** normally one routing call; at most two with retry. F 1.190 calls/request, hidden 1.182. Structured comparison/availability/details/account/search/recommendation/KG used zero prose calls in these evaluations. Explicit Compare was zero-Qwen in the restored HTTP smoke test. Existing lazy explanation paths are preserved.

Q. **Latency:** F median 2.76s / p90 7.82s; hidden 2.76s / p90 9.67s. Retried requests median total 7.98s existing and 10.32s hidden; median additional retry generation 6.11s and 6.38s. Input/output medians F 701/18 tokens; hidden 704/18. Historical 2.88s is separate from current A's controlled 4.49s. Timing includes ordinary hardware/warmup variability.

R. **Live:** candidate 16/24, original core 4/6, second pair 2/5. Authenticated normal HTTP, real public Mongo catalogue and existing APIs; synthetic corpus fixtures are not represented as live results.

| Live chain | Candidate result |
|---|---:|
| original_six | 4/6 |
| second_pair | 2/5 |
| previous_comparison | 2/3 |
| selection_change | 1/2 |
| page_context | 2/2 |
| account_language | 4/4 |
| search_language | 1/2 |

S. **Account live:** 4/4 loans, fees, reservations and recent borrowing-history requests; no account records, emails, identities or tokens are saved in reports.

T. **Context live:** previous comparison 2/3; selection change 1/2; page 2/2; natural search 1/2. Candidate failures remain failures. Baseline restoration separately passes 6/6 and explicit Compare zero-Qwen.

U. **Backend:** 743 passed, 10 expected opt-in dynamic-book integration skips; 449 assistant, 115 security, 76 staff/admin, 51 notifications, 52 circulation/graph. Forty new V2 contract tests cover binding, dynamic capabilities/positions, grounding, schema/enforcer compatibility, opt-in gateway and bounded retry. Mocks prove contracts, not language accuracy. Ten real full-text/isolated-Mongo integration checks were not executed.

V. **Frontend:** existing 85 assistant tests pass. No React routing, UI or selection payload changes.

W. **Build/lint:** production build passes; lint has zero errors and 19 existing warnings. Existing large-chunk build warning remains. All 117 frozen service sources and 2,536 pre-existing report files match baseline hashes.

X. **Exact source files changed/added:**

- [assistant/api.py](D:/SDC/LibraryLLM/assistant/api.py)
- [assistant/profiling.py](D:/SDC/LibraryLLM/assistant/profiling.py)
- [assistant/qwen.py](D:/SDC/LibraryLLM/assistant/qwen.py)
- [assistant/router_v2.py](D:/SDC/LibraryLLM/assistant/router_v2.py)
- [assistant/router_v2_legacy.py](D:/SDC/LibraryLLM/assistant/router_v2_legacy.py)
- [scripts/evaluate_assistant_router_v2.py](D:/SDC/LibraryLLM/scripts/evaluate_assistant_router_v2.py)
- [scripts/assistant_router_v2_corpus.py](D:/SDC/LibraryLLM/scripts/assistant_router_v2_corpus.py)
- [scripts/check_assistant_router_v2_live.py](D:/SDC/LibraryLLM/scripts/check_assistant_router_v2_live.py)
- [scripts/summarize_assistant_router_v2.py](D:/SDC/LibraryLLM/scripts/summarize_assistant_router_v2.py)
- [scripts/check_assistant_router_v2_parity.py](D:/SDC/LibraryLLM/scripts/check_assistant_router_v2_parity.py)
- [scripts/check_assistant_router_v2_restored.py](D:/SDC/LibraryLLM/scripts/check_assistant_router_v2_restored.py)
- [tests/test_assistant_router_v2.py](D:/SDC/LibraryLLM/tests/test_assistant_router_v2.py)

Generated reports include baseline/source manifests and snapshots, failure analysis, schema audit, matrix/per-variant cases, final existing/hidden cases, held-out manifest, criterion review, latency, live/restored live, regression XML/JSON, prompt-parity replay, hardware inventory/runtime and service/check logs. Recorded-output replay verifies all 812 primary candidate prompts, decoding schemas and decisions against the production gateway; this is a contract check, not an accuracy claim.

Y. **Adequacy:** FAIL. NVIDIA GeForce RTX 5060 Laptop GPU, 7.96 GiB total CUDA memory; model footprint 1.87 GiB, allocated 2.10 GiB, free at audit 4.68 GiB. Only the current generative model is cached. No install, replacement or alternate benchmark; coexistence fit for a larger router is unproven. See the separate adequacy report.

Z. **Limitations/stop:** structurally valid but semantically wrong intents/goals, criterion omissions, reference errors, unsafe literal pseudo-titles, and expensive/unhelpful retries remain. These formulations do not establish production reliability. The previous router is active; V2 stays opt-in through ASSISTANT_ROUTER_V2_VARIANT and ASSISTANT_ROUTER_V2_RETRY. Frozen Search, recommendation, KG, circulation, Admin, notifications and RAG behavior are unchanged. Search health currently reports STALE/degraded; its existing index/ranking was not rebuilt or changed. All five local services are reachable (recommendation uses its root endpoint). Stop after this V2 audit.
