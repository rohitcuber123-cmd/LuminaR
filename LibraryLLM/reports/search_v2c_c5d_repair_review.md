# C5D targeted parser repair — disabled candidate v2

FINAL: PASS for completed, auditable development repair/regression assessment. The candidate remains disabled and is not certified production-safe or authorized for rollout. One known unsafe recommendation remains.

## Implementation and isolation

The candidate lives under scratch/search_v2c_c5d_repair_v2/candidate_search. Production search/, active C4 policy, native authorization, frontend, databases and indexes were not modified. Seven pure parser modules were copied into a separate namespace; only explicit candidate evaluators/tests can import it. The earlier frozen C5D investigation is preserved under its original names.

Confirmed repairs: explicit field owners can consume quoted category/negative operands while keeping literal interiors opaque; title extraction preserves separate topical text; format-only/borrow-now/publication equality grammar is recognized; bounded unique grammar/scoped canonical repairs retain source provenance; mandatory relationships, missing values and unowned mandatory clauses are inventoried; deterministic guards distinguish existing executable, notice, clarification, unsupported and contradiction outcomes. Cross-field exclusions use production normalization and whole-word boundaries, preserving the earlier Marsh/ar counterexample.

Actual semantic-change files are query_constraints.py, query_numeric.py, query_repair.py, semantic_safety.py and the candidate version identity in query_plan.py. query_confidence.py, query_session.py and query_calibration.py keep inherited logic in the disabled namespace. changed_files.json and candidate_changes.patch provide parents, hashes and reasons.

## Parser/policy and scoring contracts

The established enum already permits EXECUTABLE_WITH_NOTICE, and unchanged C4 assessment maps repair provenance to EXECUTE_WITH_NOTICE. The candidate adds a source-backed producer for bounded grammar/scoped canonical repairs. It does not relabel every EXECUTABLE output or change the C4 policy. Native rendering/choice issuance for these new repair types remains an integration-validation prerequisite.

The exact frozen C5C scorer is reused with output namespace redirection only. Normative labels, BOTH normalization, per-field masks and inapplicable/unknown/false distinctions are unchanged. Structured advisory-object accuracy and scope/actor prediction accuracy stay N/A. Strict intent/field-code representation concerns are not normalized away.

## Frozen measurements

| Version | Typed accuracy | Execution recommendation accuracy | False execution / blocked | Missed execution / executable |
|---|---:|---:|---:|---:|
| C5C_BASELINE | 254/644 (39.44%) | 410/644 (63.66%) | 191/394 (48.48%) | 43/250 (17.20%) |
| REPAIR_V1 | 466/644 (72.36%) | 525/644 (81.52%) | 99/394 (25.13%) | 20/250 (8.00%) |
| REPAIR_V2 | 598/644 (92.86%) | 643/644 (99.84%) | 1/394 (0.25%) | 0/250 (0.00%) |

The final new-core results are548/594 typed correct (92.26%) and593/594 execution recommendations correct (99.83%). Retained originals stay50/50 on both metrics. False executions resolve190 previous failures with no newly introduced false executions; all43 previous missed valid executions resolve with no new missed executions.

V1 was frozen and measured once, then preserved after it introduced28 new false executions and15 newly missed queries. All43 introduced regressions have individual investigations and safe V2 outcomes. V2 was separately frozen and measured once. These are iterative development measurements on an exposed corpus, not independent validation. No candidate was silently edited or rerun after its measurement.

Primary parser-context calls are644 per version (1,288 total), plus six structurally grouped development contexts per version (12 additional). There were zero capture runtime errors/retries. Candidate unit-test parser invocations are not conflated with these denominators.

## Thirty scope/decision cells

| Scope | Stratum | Eligible | Baseline typed | V2 typed | Baseline false → V2 | Baseline missed → V2 |
|---|---|---:|---:|---:|---:|---:|
| GLOBAL | CLEAR_EXECUTABLE | 20 | 20/20 | 20/20 | 0 → 0 | 0 → 0 |
| GLOBAL | SAFE_UNCERTAIN_EXECUTABLE | 20 | 0/20 | 13/20 | 0 → 0 | 1 → 0 |
| GLOBAL | AMBIGUOUS | 18 | 0/18 | 16/18 | 17 → 1 | 0 → 0 |
| GLOBAL | INCOMPLETE | 20 | 4/20 | 19/20 | 13 → 0 | 0 → 0 |
| GLOBAL | UNSUPPORTED | 20 | 7/20 | 20/20 | 9 → 0 | 0 → 0 |
| GLOBAL | CONTRADICTORY | 19 | 10/19 | 19/19 | 9 → 0 | 0 → 0 |
| PUBLIC_TENANT_PATRON | CLEAR_EXECUTABLE | 20 | 18/20 | 20/20 | 0 → 0 | 2 → 0 |
| PUBLIC_TENANT_PATRON | SAFE_UNCERTAIN_EXECUTABLE | 20 | 0/20 | 13/20 | 0 → 0 | 6 → 0 |
| PUBLIC_TENANT_PATRON | AMBIGUOUS | 20 | 2/20 | 19/20 | 14 → 0 | 0 → 0 |
| PUBLIC_TENANT_PATRON | INCOMPLETE | 20 | 6/20 | 19/20 | 10 → 0 | 0 → 0 |
| PUBLIC_TENANT_PATRON | UNSUPPORTED | 20 | 1/20 | 20/20 | 12 → 0 | 0 → 0 |
| PUBLIC_TENANT_PATRON | CONTRADICTORY | 20 | 14/20 | 20/20 | 5 → 0 | 0 → 0 |
| PUBLIC_TENANT_STAFF | CLEAR_EXECUTABLE | 20 | 17/20 | 20/20 | 0 → 0 | 3 → 0 |
| PUBLIC_TENANT_STAFF | SAFE_UNCERTAIN_EXECUTABLE | 20 | 0/20 | 13/20 | 0 → 0 | 9 → 0 |
| PUBLIC_TENANT_STAFF | AMBIGUOUS | 20 | 5/20 | 19/20 | 9 → 0 | 0 → 0 |
| PUBLIC_TENANT_STAFF | INCOMPLETE | 20 | 5/20 | 19/20 | 10 → 0 | 0 → 0 |
| PUBLIC_TENANT_STAFF | UNSUPPORTED | 20 | 1/20 | 20/20 | 11 → 0 | 0 → 0 |
| PUBLIC_TENANT_STAFF | CONTRADICTORY | 20 | 14/20 | 20/20 | 4 → 0 | 0 → 0 |
| PRIVATE_TENANT_PATRON | CLEAR_EXECUTABLE | 70 | 66/70 | 70/70 | 0 → 0 | 4 → 0 |
| PRIVATE_TENANT_PATRON | SAFE_UNCERTAIN_EXECUTABLE | 20 | 0/20 | 13/20 | 0 → 0 | 8 → 0 |
| PRIVATE_TENANT_PATRON | AMBIGUOUS | 20 | 4/20 | 19/20 | 14 → 0 | 0 → 0 |
| PRIVATE_TENANT_PATRON | INCOMPLETE | 20 | 7/20 | 19/20 | 8 → 0 | 0 → 0 |
| PRIVATE_TENANT_PATRON | UNSUPPORTED | 20 | 1/20 | 20/20 | 9 → 0 | 0 → 0 |
| PRIVATE_TENANT_PATRON | CONTRADICTORY | 19 | 13/19 | 19/19 | 4 → 0 | 0 → 0 |
| PRIVATE_TENANT_STAFF | CLEAR_EXECUTABLE | 20 | 16/20 | 20/20 | 0 → 0 | 4 → 0 |
| PRIVATE_TENANT_STAFF | SAFE_UNCERTAIN_EXECUTABLE | 20 | 0/20 | 13/20 | 0 → 0 | 6 → 0 |
| PRIVATE_TENANT_STAFF | AMBIGUOUS | 20 | 4/20 | 19/20 | 12 → 0 | 0 → 0 |
| PRIVATE_TENANT_STAFF | INCOMPLETE | 19 | 5/19 | 18/19 | 8 → 0 | 0 → 0 |
| PRIVATE_TENANT_STAFF | UNSUPPORTED | 20 | 1/20 | 20/20 | 9 → 0 | 0 → 0 |
| PRIVATE_TENANT_STAFF | CONTRADICTORY | 19 | 13/19 | 19/19 | 4 → 0 | 0 → 0 |

Every cell has zero new false-execution and missed-execution regressions. The private patron clear cell contains50 retained cases in addition to20 new core; they remain explicitly separate in machine-readable cohort results.

## Recognition and semantic/operand findings

| Gold class | Baseline recall | V2 recall |
|---|---:|---:|
| AMBIGUOUS | 15/98 (15.31%) | 92/98 (93.88%) |
| INCOMPLETE | 27/99 (27.27%) | 94/99 (94.95%) |
| UNSUPPORTED | 11/100 (11.00%) | 100/100 (100.00%) |
| CONTRADICTORY | 64/97 (65.98%) | 97/97 (100.00%) |
| EXECUTABLE_WITH_NOTICE | 0/100 (0.00%) | 65/100 (65.00%) |

All150 clear-executable contexts receive the correct typed decision, including100 new core. All100 safe-uncertain cases remain executable;65/100 receive the required typed notice. All five revised author-association cases now receive AMBIGUOUS/false.

| Applicable operand/semantic metric | Baseline | V2 |
|---|---:|---:|
| subjects | 263/614 (42.83%) | 612/614 (99.67%) |
| exclude_subjects | 512/613 (83.52%) | 607/613 (99.02%) |
| exclude_terms | 533/629 (84.74%) | 557/629 (88.55%) |
| author_text | 592/604 (98.01%) | 597/604 (98.84%) |
| title_text | 604/609 (99.18%) | 609/609 (100.00%) |
| formats | 622/632 (98.42%) | 632/632 (100.00%) |
| exclusive_formats | 488/634 (76.97%) | 629/634 (99.21%) |
| availability | 389/523 (74.38%) | 523/523 (100.00%) |
| year_min | 430/515 (83.50%) | 511/515 (99.22%) |
| year_max | 430/515 (83.50%) | 511/515 (99.22%) |
| semantic_text | 289/644 (44.88%) | 338/644 (52.48%) |
| protected_entities | 550/589 (93.38%) | 566/589 (96.10%) |

Do not equate near-perfect execution classification with complete semantic correctness:504 contexts still have at least one strict scored-dimension mismatch. Semantic remainder exactness is338/644; affected-field granularity, residual words, exclusions and the unchanged retained intent-priority contract remain material limitations. No blanket semantic-equivalence adapter was introduced.

## Regression, independent validation and native boundaries

Final V2 passes1,380 assertions:1,342 existing namespace-adapted parser/numeric/C4 reviewed legacy assertions plus38 targeted requirement/semantic cases. The original assertions and gold are unchanged; only parser namespace and repository-root resolution were adapted. One native-transformer-dependent test was excluded from the pure suite because it imports application/session/database code. Initial development failures and all regression-run logs/XML are retained.

Six pre-existing independently reviewed DEVELOPMENT positives occupy one complete structural group disjoint in operation topology from C5C. Candidate outputs were captured without gold, then scored separately. Results are in independent_validation_limits.json. These six positives cannot validate blocked safety or generalization. No fresh independent-labeling claim is made.

Public/private and patron/staff capability contexts are evaluated across all30 cells. Active native authority/owner/workspace/expiry/commit code is byte-preserved, and capability/EXACT/predicate/source-span tests pass. No native API, inventory action, suggestion issuance or transaction was executed. Candidate end-to-end native rendering/workflows and privacy acceptance remain unverified and must precede activation.

## Remaining blockers and next boundary

One unsafe recommendation remains: C5A-1-3-12. Its note leaves ONLINE access mandatory versus advisory unresolved, but the uncertainty inventory lacks format/access ownership and marks the format resolved. The baseline also executed this case; it is not a new regression. The frozen V2 candidate is retained unchanged rather than silently tuning another reported result.

Other remaining typed errors:35 missing typed notices, five ambiguous cases called incomplete, and five incomplete cases called unsupported. The latter ten remain safely non-executable. Remaining notice grammar and structured/advisory/field-code ownership require further focused work and validation. Confidence remains the inherited heuristic; no probability claim or threshold was added.

A disabled candidate and transparent evidence are ready for separately authorized final regression/validation planning, with these blockers carried forward. No production acceptance, deployment, policy selection/activation, heldout evaluation or C5E execution is authorized or performed.

## Preservation and exact evidence

All 1790 protected entries pass, including462 production source files and every prior C5A/B/C/D freeze. C5B labels and C5C predictions retain their original SHA256. No endpoint repoll, Qwen call, Mongo mutation, HNSW/KG rebuild or unrelated UI/backend change occurred. Global5,000,000 and STALE/degraded baseline_verified=False remain recorded prior observations.

| QA field | Actual |
|---|---|
| FINAL | PASS |
| meaning | Completed auditable disabled development repair and regression assessment; not production safety or rollout approval. |
| FINAL_CANDIDATE | C5D-disabled-repair-v2 |
| CANDIDATE_ACTIVATED | NO |
| PRODUCTION_PARSER_CHANGED | NO |
| ACTIVE_C4_POLICY_CHANGED | NO |
| C5A_C5B_C5C_PRIOR_C5D_PRESERVED | YES |
| C5C_SCORER_AND_GOLD_CHANGED | NO |
| SAME_CORPUS_USED_IN_DEVELOPMENT | YES |
| TOTAL_FROZEN_CONTEXTS | 1024 |
| ELIGIBLE_CONTEXTS | 644 |
| NEW_CORE_EVALUATED | 594 |
| RETAINED_EVALUATED | 50 |
| EXCLUDED_CONTEXTS | 380 |
| PRIMARY_CANDIDATE_EVALUATIONS | {"v1": 644, "v2": 644, "total": 1288} |
| SUPPLEMENTARY_DEVELOPMENT_EVALUATIONS | {"v1": 6, "v2": 6, "total": 12} |
| CANDIDATE_RUNTIME_ERRORS | 0 |
| CANDIDATE_CAPTURE_RETRIES | 0 |
| PRODUCTION_PARSER_EVALUATIONS | 0 |
| BASELINE_TYPED_ACCURACY | {"denominator": 644, "numerator": 254, "percent": 39.440993788819874, "status": "MEASURED"} |
| CANDIDATE_TYPED_ACCURACY | {"denominator": 644, "numerator": 598, "percent": 92.85714285714286, "status": "MEASURED"} |
| BASELINE_EXECUTION_ACCURACY | {"denominator": 644, "numerator": 410, "percent": 63.66459627329193, "status": "MEASURED"} |
| CANDIDATE_EXECUTION_ACCURACY | {"denominator": 644, "numerator": 643, "percent": 99.84472049689441, "status": "MEASURED"} |
| BASELINE_FALSE_EXECUTION | {"denominator": 394, "numerator": 191, "percent": 48.47715736040609, "status": "MEASURED"} |
| CANDIDATE_FALSE_EXECUTION | {"denominator": 394, "numerator": 1, "percent": 0.25380710659898476, "status": "MEASURED"} |
| BASELINE_MISSED_EXECUTION | {"denominator": 250, "numerator": 43, "percent": 17.2, "status": "MEASURED"} |
| CANDIDATE_MISSED_EXECUTION | {"denominator": 250, "numerator": 0, "percent": 0.0, "status": "MEASURED"} |
| FINAL_NEW_FALSE_EXECUTION_REGRESSIONS | 0 |
| FINAL_NEW_MISSED_EXECUTION_REGRESSIONS | 0 |
| V1_NEW_FALSE_EXECUTION_REGRESSIONS_RETAINED | 28 |
| V1_NEW_MISSED_EXECUTION_REGRESSIONS_RETAINED | 15 |
| NEW_CORE_TYPED_ACCURACY | {"denominator": 594, "numerator": 548, "percent": 92.25589225589225, "status": "MEASURED"} |
| NEW_CORE_EXECUTION_ACCURACY | {"denominator": 594, "numerator": 593, "percent": 99.83164983164983, "status": "MEASURED"} |
| RECOGNITION | {"AMBIGUOUS": {"denominator": 98, "numerator": 92, "percent": 93.87755102040816, "status": "MEASURED"}, "INCOMPLETE": {"denominator": 99, "numerator": 94, "percent": 94.94949494949495, "status": "MEASURED"}, "UNSUPPORTED": {"denominator": 100, "numerator": 100, "percent": 100.0, "status": "MEASURED"}, "CONTRADICTORY": {"denominator": 97, "numerator": 97, "percent": 100.0, "status": "MEASURED"}, "EXECUTABLE_WITH_NOTICE": {"denominator": 100, "numerator": 65, "percent": 65.0, "status": "MEASURED"}} |
| CLEAR_EXECUTABLE_TYPED_ACCURACY | {"denominator": 150, "numerator": 150, "percent": 100.0, "status": "MEASURED"} |
| SAFE_UNCERTAIN_EXECUTABLE_EXECUTION | {"numerator": 100, "denominator": 100, "percent": 100.0, "status": "MEASURED"} |
| FIVE_REVISED_AMBIGUITY_RECOGNITION | {"numerator": 5, "denominator": 5, "percent": 100.0, "status": "MEASURED"} |
| REGRESSION_ASSERTIONS_PASSED | 1380 |
| REGRESSION_ASSERTIONS_FAILED_FINAL | 0 |
| SCOPE_ACTOR_PREDICTION_ACCURACY | N/A: supplied context; native authorization stays external and unchanged. |
| NATIVE_HARNESS_RERUN | NO |
| PRIVATE_PUBLIC_ISOLATION | Active boundaries preserved by hashes; candidate scoped offline cases assessed. End-to-end candidate native validation not performed. |
| STRUCTURED_ADVISORY_ACCURACY | N/A under unchanged C5C oracle. |
| THIRTY_CELL_REPORT | reports\search_v2c_c5d_repair_thirty_cell_comparison.json |
| REMAINING_FALSE_EXECUTION_IDS | ["C5A-1-3-12"] |
| REMAINING_TYPED_ERRORS | 46 |
| REMAINING_STRICT_DIMENSION_MISMATCH_CONTEXTS | 504 |
| INDEPENDENT_VALIDATION | Limited six historical reviewed positives, one complete structural group; no generalization/safety acceptance. |
| PRODUCTION_SOURCE_HASH_VERIFICATION | PASS (462 files) |
| PROTECTED_EVIDENCE_HASH_VERIFICATION | PASS (1790 protected entries) |
| SEALED_HELDOUT_HASH_UNCHANGED | YES |
| THRESHOLD_FITTING_PERFORMED | NO |
| POLICY_SELECTED | NO |
| POLICY_ACTIVATED | NO |
| HELDOUT_EVALUATIONS | 0 |
| HNSW_REBUILDS | 0 |
| KG_REBUILDS | 0 |
| MONGO_MUTATIONS | 0 |
| QWEN_INFERENCES | 0 |
| C5E_STARTED | NO |
| NEXT_PHASE_READINESS | DISABLED_DEVELOPMENT_CANDIDATE_AVAILABLE_WITH_BLOCKERS |

Evidence:
- reports/search_v2c_c5d_repair_changed_files.json
- reports/search_v2c_c5d_repair_candidate_changes.patch
- reports/search_v2c_c5d_repair_baseline_candidate_comparison.json
- reports/search_v2c_c5d_repair_thirty_cell_comparison.json
- reports/search_v2c_c5d_repair_decision_transitions.jsonl
- reports/search_v2c_c5d_repair_introduced_regression_investigation.jsonl
- reports/search_v2c_c5d_repair_safety_regressions.json
- reports/search_v2c_c5d_repair_regression_accounting.json
- reports/search_v2c_c5d_repair_independent_validation_limits.json
- reports/search_v2c_c5d_repair_remaining_blockers.json
- reports/search_v2c_c5d_repair_preservation.json
- reports/search_v2c_c5d_repair_next_phase_readiness.json
- reports/search_v2c_c5d_repair_final_qa.json
- reports/search_v2c_c5d_repair_freeze_manifest.json
- reports/search_v2c_c5d_repair_v2_candidate_freeze.json
- reports/search_v2c_c5d_repair_v2_predictions.jsonl
- reports/search_v2c_c5d_repair_v2_failures.jsonl
- reports/search_v2c_c5d_repair_v2_operand_scoring.json
