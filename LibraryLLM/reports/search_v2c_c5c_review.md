# V2C-C.5C — frozen parser calibration evaluation

FINAL = PASS. This means the authorized evaluation is complete and valid. It does not establish adequate parser accuracy or production/policy readiness. No tuning or policy selection occurred.

## Population and isolation

Exact C5B freeze and append-only final admission verified before inference. The five inherited core_eligible=false flags are stale intermediate metadata: frozen C5B quota code uses CORE + AI_REVIEWED + review_complete, and final admission explicitly accepts these five. No C5B artifact was edited. The first preflight stopped on that stale flag with zero parser calls; both preflight attempts are recorded.

1,024 frozen contexts: 594 eligible new independently reviewed core + 50 eligible retained reviewed parser contexts + 230 excluded native sequences + 149 excluded unreviewed derivatives + one excluded rejected core. Thirty AI_REVIEWED native records are not parser units. False execution gold is a valid negative, never missing gold.

One isolated capture made 644 parser calls, 644 outputs, no errors/retries, no model inference, no network calls, no application writes or native runs. Prediction process received only query/mode/supplied scope/workspace and frozen vocabulary/capabilities. Gold was joined after prediction capture was complete. Prediction SHA256: `0a5ebcca95b4acec9363db860cdf76b90e5c2c7b9915b4ad959090e5e65bc704`.

## Measured performance

| Population | Typed accuracy | Execution recommendation accuracy | False execution among blocked gold | Missed execution among executable gold |
|---|---:|---:|---:|---:|
| All eligible | 254/644 (39.44%) | 410/644 (63.66%) | 191/394 (48.48%) | 43/250 (17.20%) |
| New reviewed core | 204/594 (34.34%) | 360/594 (60.61%) | 191/394 (48.48%) | 43/200 (21.50%) |
| Retained reviewed originals | 50/50 (100.00%) | 50/50 (100.00%) | N/A (no applicable cases) | 0/50 (0.00%) |

Typed outputs have 390 errors; execution recommendations have 191 false positives and 43 false negatives. There were no invalid/undecidable outputs. No actual application execution occurred.

Typed recall: AMBIGUOUS: 15/98 (15.31%); INCOMPLETE: 27/99 (27.27%); UNSUPPORTED: 11/100 (11.00%); CONTRADICTORY: 64/97 (65.98%).

## Concentration and thirty-cell matrix

SAFE_UNCERTAIN_EXECUTABLE typed recall is 0/100. The current C4 policy may issue a repair notice while the parser typed decision remains EXECUTABLE; policy notice is not silently substituted for a typed gold match. Executability in this stratum is 70/100.

All five scopes and six strata are reported below. Retained50 occupy only PRIVATE_TENANT_PATRON/CLEAR_EXECUTABLE; their 100% typed accuracy raises that mixed cell. New-core counts and patterns are shown separately. All cells are small synthetic samples; no population confidence claim is warranted.

| Scope | Stratum | Eligible | New core | Patterns | Typed correct | False execution | Missed execution |
|---|---|---:|---:|---:|---:|---:|---:|
| GLOBAL | CLEAR_EXECUTABLE | 20 | 20 | 5 | 20/20 | 0 | 0 |
| GLOBAL | SAFE_UNCERTAIN_EXECUTABLE | 20 | 20 | 8 | 0/20 | 0 | 1 |
| GLOBAL | AMBIGUOUS | 18 | 18 | 12 | 0/18 | 17 | 0 |
| GLOBAL | INCOMPLETE | 20 | 20 | 12 | 4/20 | 13 | 0 |
| GLOBAL | UNSUPPORTED | 20 | 20 | 14 | 7/20 | 9 | 0 |
| GLOBAL | CONTRADICTORY | 19 | 19 | 5 | 10/19 | 9 | 0 |
| PUBLIC_TENANT_PATRON | CLEAR_EXECUTABLE | 20 | 20 | 5 | 18/20 | 0 | 2 |
| PUBLIC_TENANT_PATRON | SAFE_UNCERTAIN_EXECUTABLE | 20 | 20 | 8 | 0/20 | 0 | 6 |
| PUBLIC_TENANT_PATRON | AMBIGUOUS | 20 | 20 | 12 | 2/20 | 14 | 0 |
| PUBLIC_TENANT_PATRON | INCOMPLETE | 20 | 20 | 15 | 6/20 | 10 | 0 |
| PUBLIC_TENANT_PATRON | UNSUPPORTED | 20 | 20 | 12 | 1/20 | 12 | 0 |
| PUBLIC_TENANT_PATRON | CONTRADICTORY | 20 | 20 | 6 | 14/20 | 5 | 0 |
| PUBLIC_TENANT_STAFF | CLEAR_EXECUTABLE | 20 | 20 | 5 | 17/20 | 0 | 3 |
| PUBLIC_TENANT_STAFF | SAFE_UNCERTAIN_EXECUTABLE | 20 | 20 | 8 | 0/20 | 0 | 9 |
| PUBLIC_TENANT_STAFF | AMBIGUOUS | 20 | 20 | 12 | 5/20 | 9 | 0 |
| PUBLIC_TENANT_STAFF | INCOMPLETE | 20 | 20 | 15 | 5/20 | 10 | 0 |
| PUBLIC_TENANT_STAFF | UNSUPPORTED | 20 | 20 | 12 | 1/20 | 11 | 0 |
| PUBLIC_TENANT_STAFF | CONTRADICTORY | 20 | 20 | 6 | 14/20 | 4 | 0 |
| PRIVATE_TENANT_PATRON | CLEAR_EXECUTABLE | 70 | 20 | 5 | 66/70 | 0 | 4 |
| PRIVATE_TENANT_PATRON | SAFE_UNCERTAIN_EXECUTABLE | 20 | 20 | 8 | 0/20 | 0 | 8 |
| PRIVATE_TENANT_PATRON | AMBIGUOUS | 20 | 20 | 12 | 4/20 | 14 | 0 |
| PRIVATE_TENANT_PATRON | INCOMPLETE | 20 | 20 | 15 | 7/20 | 8 | 0 |
| PRIVATE_TENANT_PATRON | UNSUPPORTED | 20 | 20 | 12 | 1/20 | 9 | 0 |
| PRIVATE_TENANT_PATRON | CONTRADICTORY | 19 | 19 | 6 | 13/19 | 4 | 0 |
| PRIVATE_TENANT_STAFF | CLEAR_EXECUTABLE | 20 | 20 | 5 | 16/20 | 0 | 4 |
| PRIVATE_TENANT_STAFF | SAFE_UNCERTAIN_EXECUTABLE | 20 | 20 | 8 | 0/20 | 0 | 6 |
| PRIVATE_TENANT_STAFF | AMBIGUOUS | 20 | 20 | 12 | 4/20 | 12 | 0 |
| PRIVATE_TENANT_STAFF | INCOMPLETE | 19 | 19 | 14 | 5/19 | 8 | 0 |
| PRIVATE_TENANT_STAFF | UNSUPPORTED | 20 | 20 | 12 | 1/20 | 9 | 0 |
| PRIVATE_TENANT_STAFF | CONTRADICTORY | 19 | 19 | 6 | 13/19 | 4 | 0 |

Blocked-gold false execution by scope: GLOBAL: 48/77 (62.34%); PRIVATE_TENANT_PATRON: 35/79 (44.30%); PRIVATE_TENANT_STAFF: 33/78 (42.31%); PUBLIC_TENANT_PATRON: 41/80 (51.25%); PUBLIC_TENANT_STAFF: 34/80 (42.50%).

## Failure analysis

Five prominent measured categories (multi-label counts can overlap): missing required operand 496 contexts; semantic remainder mismatch 355; affected-field reporting mismatch 323; false executable classification 191; other wrong typed decision 113. Additional typed safety diagnoses include ambiguity misclassification 83/98, incomplete misclassification 72/99, unsupported misclassification 89/100, and contradiction recognition misses 33/97.

There are 635 contexts with at least one scored mismatch, 562 with applicable parser-defect dimensions, and 567 with indeterminate dimensions; those last two counts overlap. Strict semantic-remainder, intent, and affected-field granularity disagreements retain their scores but are not automatically claimed as confirmed causal parser defects. Every failure has an ID, observed/expected values, gold fingerprint, taxonomy and disposition. No confirmed evaluator/runtime/fixture defect or gold rewrite is claimed.

Safety-critical false execution is concentrated in AMBIGUOUS (66/98), INCOMPLETE (49/99), UNSUPPORTED (50/100), and CONTRADICTORY (26/97) gold. These are offline recommendations; no inventory/account/search application action was executed.

## Five revised ambiguity cases

Typed ambiguity recognition: 1/5 (20.00%). Safe non-execution: 1/5 (20.00%). Four false execution recommendations remain. Author scalar assertions are excluded as intentionally unknown; required typed/execution gold remains complete.

| Stable ID | Predicted typed decision | Execution recommendation | Native confidence signal |
|---|---|---|---:|
| C5A-1-3-11 | EXECUTABLE | True | 1.0 |
| C5A-2-3-11 | EXECUTABLE | True | 1.0 |
| C5A-3-3-11 | AMBIGUOUS | False | 0.0 |
| C5A-4-3-11 | EXECUTABLE | True | 1.0 |
| C5A-5-3-11 | EXECUTABLE | True | 1.0 |

## Confidence and limitations

The native confidence values observed were 0.0 and 1.0; they are heuristic/categorical signals, not calibrated probabilities. At native value 1.0, typed correctness is 137/398 (34.42%), with 261 typed errors and 191 false execution recommendations. No bins/cutoffs were invented, no reliability transformation fitted, and no thresholds swept.

Scope/actor accuracy is N/A because those are supplied context rather than parser-selected outputs. Live private/public API boundaries are not measured. Scalar masks exclude unresolved and scope-inapplicable fields; partially resolved lists use only their known common subset. No comparison silently treats unknown author values as absent. Detailed ambiguity-alternative span equality and new structured advisory-object accuracy are N/A because no established output-equivalence adapter exists. The retained50 advisory representation remains measured under its original contract.

Eligible contexts have 2205 excluded scalar/advisory assertions: {"INAPPLICABLE": 706, "NO_GOLD_FIELD": 594, "UNAVAILABLE_OUTPUT_ORACLE_ADAPTER": 594, "UNRESOLVED": 311}. Ten partial list/subset comparisons score only the common resolved members. All 644 typed and execution labels remain applicable. Rate denominators are explicit; zero-denominator metrics are N/A. No real-world generalization is asserted from synthetic cells of 18–20 new core cases.

## Historical separation and preservation

All 1648 protected pre-existing files match preflight hashes, including the original 1,557-file baseline and 462 production source files. C5A, C5B, original historical C5 FAIL results, sealed hashes, evaluators and native harnesses are preserved. Original50 historical parser outcomes and native 264/264, 833/833 boundaries, 59/59 suggestions, 213/213 corrections, 154 commits, supplement5/5 and security46/46 are historical evidence, not fresh C5C results. The fifty retained parser contexts were reevaluated once in C5C and are explicitly separate from their original outcomes.

Large assets retain their inherited artifact SHA256 or size/mtime verification method. No full HNSW/KG checksum or current healthy runtime claim is made. Global5,000,000 and STALE/degraded baseline_verified=False are previous observations; no endpoint or Mongo poll occurred.

## Final analysis and boundary

The measured current parser performs well on retained typed labels but has substantial new-core typed and execution-safety failures. The evidence is sufficient to plan a separately authorized policy investigation, while operand/semantic recognition gaps limit what a confidence-only policy can establish. Structured-advisory and scope/actor metrics remain explicitly unavailable; indeterminate causal dimensions require future investigation. There are no unresolved blockers to completion of this scoring phase.

Stop here. Any threshold calibration, policy alternatives, operating-point selection or parser work requires separate explicit authorization. Heldout evaluation remains separately gated. No threshold values or policy winner are recommended.

## Mandatory final QA fields

| Field | Measured value |
|---|---|
| FINAL | PASS |
| C5C_IMPLEMENTED | YES |
| C5B_FREEZE_VERIFIED | YES |
| C5B_ORIGINAL_FREEZE_PRESERVED | YES |
| C4_ACTIVE_POLICY_PRESERVED | YES |
| PRODUCTION_PARSER_CHANGED | NO |
| PRODUCTION_POLICY_CHANGED | NO |
| PARSER_CALIBRATION_EVALUATION_COMPLETE | YES |
| TOTAL_FROZEN_CONTEXTS | 1024 |
| ELIGIBLE_PARSER_CONTEXTS | 644 |
| INELIGIBLE_PARSER_CONTEXTS | 380 |
| APPLICABILITY_EXCLUSIONS | {"logical_contexts": 380, "context_reasons": {"NATIVE_SEQUENCE": 230, "REJECTED_CORE": 1, "UNREVIEWED_DERIVATIVE": 149}, "eligible_field_assertions_excluded": 2205, "field_reason_counts": {"INAPPLICABLE": 706, "NO_GOLD_FIELD": 594, "UNAVAILABLE_OUTPUT_ORACLE_ADAPTER": 594, "UNRESOLVED": 311}, "native_parser_labels_inapplicable": 230, "missing_required_eligible_decision_execution_labels": 0} |
| INDEPENDENTLY_REVIEWED_ELIGIBLE_CONTEXTS | 644 |
| NEW_CORE_EVALUATED | 594 |
| RETAINED_ORIGINAL_EVALUATED | 50 |
| DERIVATIVE_EVALUATED_SEPARATELY | 0 |
| NATIVE_CASES_EXCLUDED_FROM_CORE | 230 |
| HISTORICAL_CASES_REEVALUATED | 50 |
| TOTAL_NEW_PARSER_EVALUATIONS | 644 |
| TYPED_DECISION_ACCURACY | {"denominator": 644, "numerator": 254, "percent": 39.440993788819874, "status": "MEASURED"} |
| TYPED_DECISION_CONFUSION_MATRIX | {"AMBIGUOUS": {"AMBIGUOUS": 15, "EXECUTABLE": 66, "INCOMPLETE": 12, "UNSUPPORTED": 5}, "CONTRADICTORY": {"AMBIGUOUS": 4, "CONTRADICTORY": 64, "EXECUTABLE": 26, "INCOMPLETE": 3}, "EXECUTABLE": {"AMBIGUOUS": 11, "EXECUTABLE": 137, "INCOMPLETE": 2}, "EXECUTABLE_WITH_NOTICE": {"AMBIGUOUS": 21, "EXECUTABLE": 70, "INCOMPLETE": 9}, "INCOMPLETE": {"AMBIGUOUS": 17, "EXECUTABLE": 49, "INCOMPLETE": 27, "UNSUPPORTED": 6}, "UNSUPPORTED": {"AMBIGUOUS": 30, "EXECUTABLE": 50, "INCOMPLETE": 9, "UNSUPPORTED": 11}} |
| EXECUTION_DECISION_ACCURACY | {"denominator": 644, "numerator": 410, "percent": 63.66459627329193, "status": "MEASURED"} |
| FALSE_EXECUTION_COUNT | 191 |
| FALSE_EXECUTION_RATE | {"denominator": 394, "numerator": 191, "percent": 48.47715736040609, "status": "MEASURED"} |
| MISSED_VALID_EXECUTION_COUNT | 43 |
| MISSED_VALID_EXECUTION_RATE | {"denominator": 250, "numerator": 43, "percent": 17.2, "status": "MEASURED"} |
| AMBIGUOUS_RECOGNITION_RATE | {"denominator": 98, "numerator": 15, "percent": 15.306122448979592, "status": "MEASURED"} |
| INCOMPLETE_RECOGNITION_RATE | {"denominator": 99, "numerator": 27, "percent": 27.272727272727273, "status": "MEASURED"} |
| UNSUPPORTED_RECOGNITION_RATE | {"denominator": 100, "numerator": 11, "percent": 11.0, "status": "MEASURED"} |
| CONTRADICTION_RECOGNITION_RATE | {"denominator": 97, "numerator": 64, "percent": 65.97938144329896, "status": "MEASURED"} |
| SCOPE_ACCURACY | {"denominator": 0, "numerator": null, "percent": null, "reason": "Scope and authorization context supplied; parser emits no predicted scope.", "status": "N/A"} |
| ACTOR_ACCURACY | {"denominator": 0, "numerator": null, "percent": null, "reason": "No predicted role output or independent actor oracle for this parser.", "status": "N/A"} |
| CONFIDENCE_ANALYSIS_AVAILABLE | YES (descriptive native signals only) |
| TOTAL_CLASSIFIED_PARSER_ERRORS | 562 |
| INDETERMINATE_ERRORS | 567 |
| DUPLICATE_CANONICAL_CONTEXTS | 0 |
| CROSS_SPLIT_STRUCTURAL_OVERLAP | 0 |
| HELDOUT_HASH_UNCHANGED | YES |
| PRODUCTION_SOURCE_HASH_VERIFICATION | PASS (462 files) |
| HISTORICAL_EVIDENCE_HASH_VERIFICATION | PASS (1648 protected files, including the original 1557-file baseline) |
| C5A_MANIFEST_UNCHANGED | YES |
| C5B_MANIFEST_UNCHANGED | YES |
| C5C_EVIDENCE_FROZEN | YES |
| THRESHOLD_FITTING_PERFORMED | NO |
| POLICY_CANDIDATES_EVALUATED | 0 |
| CALIBRATION_POLICY_SELECTED | NO |
| CALIBRATION_POLICY_ACTIVATED | NO |
| HELDOUT_PARSER_EVALUATIONS | 0 |
| HELDOUT_POLICY_EVALUATIONS | 0 |
| HNSW_REBUILT | NO |
| KG_REBUILT | NO |
| MODEL_CHANGED | NO |
| NATIVE_HARNESS_RERUN | NO |
| PART_2I_STARTED | NO |
| UNIQUE_CONTEXTS_WITH_ANY_SCORED_MISMATCH | 635 |
| CLASSIFIED_PARSER_ERROR_DIMENSIONS | 1729 |
| INDETERMINATE_ERROR_DIMENSIONS | 746 |
| ERROR_COUNTS_OVERLAP | A context can contain confirmed parser and indeterminate dimensions. Do not add these context counts. |
| COHORT_METRICS | {"NEW_REVIEWED_CORE": {"abstentions": 246, "applicable_execution": 594, "applicable_typed": 594, "clarifications": 160, "confusion_matrix": {"AMBIGUOUS": {"AMBIGUOUS": 15, "EXECUTABLE": 66, "INCOMPLETE": 12, "UNSUPPORTED": 5}, "CONTRADICTORY": {"AMBIGUOUS": 4, "CONTRADICTORY": 64, "EXECUTABLE": 26, "INCOMPLETE": 3}, "EXECUTABLE": {"AMBIGUOUS": 11, "EXECUTABLE": 87, "INCOMPLETE": 2}, "EXECUTABLE_WITH_NOTICE": {"AMBIGUOUS": 21, "EXECUTABLE": 70, "INCOMPLETE": 9}, "INCOMPLETE": {"AMBIGUOUS": 17, "EXECUTABLE": 49, "INCOMPLETE": 27, "UNSUPPORTED": 6}, "UNSUPPORTED": {"AMBIGUOUS": 30, "EXECUTABLE": 50, "INCOMPLETE": 9, "UNSUPPORTED": 11}}, "correct_executable": 157, "correct_non_executable": 203, "correct_typed": 204, "eligible": 594, "evaluated": 594, "execution_accuracy": {"denominator": 594, "numerator": 360, "percent": 60.60606060606061, "status": "MEASURED"}, "false_execution_count": 191, "false_execution_rate": {"denominator": 394, "numerator": 191, "percent": 48.47715736040609, "status": "MEASURED"}, "incorrect_typed": 390, "invalid_or_undecidable": 0, "missed_execution_count": 43, "missed_execution_rate": {"denominator": 200, "numerator": 43, "percent": 21.5, "status": "MEASURED"}, "note": "False-execution denominator is applicable blocked gold; missed-execution denominator is applicable executable gold. These are recommendations, not application actions.", "per_decision": {"AMBIGUOUS": {"f1": {"denominator": 196, "numerator": 30, "percent": 15.306122448979592, "status": "MEASURED"}, "gold_count": 98, "precision": {"denominator": 98, "numerator": 15, "percent": 15.306122448979592, "status": "MEASURED"}, "predicted_count": 98, "recall": {"denominator": 98, "numerator": 15, "percent": 15.306122448979592, "status": "MEASURED"}}, "CONTRADICTORY": {"f1": {"denominator": 161, "numerator": 128, "percent": 79.5031055900621, "status": "MEASURED"}, "gold_count": 97, "precision": {"denominator": 64, "numerator": 64, "percent": 100.0, "status": "MEASURED"}, "predicted_count": 64, "recall": {"denominator": 97, "numerator": 64, "percent": 65.97938144329896, "status": "MEASURED"}}, "EXECUTABLE": {"f1": {"denominator": 448, "numerator": 174, "percent": 38.839285714285715, "status": "MEASURED"}, "gold_count": 100, "precision": {"denominator": 348, "numerator": 87, "percent": 25.0, "status": "MEASURED"}, "predicted_count": 348, "recall": {"denominator": 100, "numerator": 87, "percent": 87.0, "status": "MEASURED"}}, "EXECUTABLE_WITH_NOTICE": {"f1": {"denominator": 100, "numerator": 0, "percent": 0.0, "status": "MEASURED"}, "gold_count": 100, "precision": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}, "predicted_count": 0, "recall": {"denominator": 100, "numerator": 0, "percent": 0.0, "status": "MEASURED"}}, "INCOMPLETE": {"f1": {"denominator": 161, "numerator": 54, "percent": 33.54037267080745, "status": "MEASURED"}, "gold_count": 99, "precision": {"denominator": 62, "numerator": 27, "percent": 43.54838709677419, "status": "MEASURED"}, "predicted_count": 62, "recall": {"denominator": 99, "numerator": 27, "percent": 27.272727272727273, "status": "MEASURED"}}, "UNSUPPORTED": {"f1": {"denominator": 122, "numerator": 22, "percent": 18.0327868852459, "status": "MEASURED"}, "gold_count": 100, "precision": {"denominator": 22, "numerator": 11, "percent": 50.0, "status": "MEASURED"}, "predicted_count": 22, "recall": {"denominator": 100, "numerator": 11, "percent": 11.0, "status": "MEASURED"}}}, "strict_scored_dimension_match": {"denominator": 594, "numerator": 9, "percent": 1.5151515151515151, "status": "MEASURED"}, "typed_accuracy": {"denominator": 594, "numerator": 204, "percent": 34.343434343434346, "status": "MEASURED"}, "unsupported_decisions": 22, "unsupported_output_schema": 0, "valid_outputs": 594}, "RETAINED_REVIEWED_CORE": {"abstentions": 0, "applicable_execution": 50, "applicable_typed": 50, "clarifications": 0, "confusion_matrix": {"AMBIGUOUS": {}, "CONTRADICTORY": {}, "EXECUTABLE": {"EXECUTABLE": 50}, "EXECUTABLE_WITH_NOTICE": {}, "INCOMPLETE": {}, "UNSUPPORTED": {}}, "correct_executable": 50, "correct_non_executable": 0, "correct_typed": 50, "eligible": 50, "evaluated": 50, "execution_accuracy": {"denominator": 50, "numerator": 50, "percent": 100.0, "status": "MEASURED"}, "false_execution_count": 0, "false_execution_rate": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}, "incorrect_typed": 0, "invalid_or_undecidable": 0, "missed_execution_count": 0, "missed_execution_rate": {"denominator": 50, "numerator": 0, "percent": 0.0, "status": "MEASURED"}, "note": "False-execution denominator is applicable blocked gold; missed-execution denominator is applicable executable gold. These are recommendations, not application actions.", "per_decision": {"AMBIGUOUS": {"f1": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}, "gold_count": 0, "precision": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}, "predicted_count": 0, "recall": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}}, "CONTRADICTORY": {"f1": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}, "gold_count": 0, "precision": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}, "predicted_count": 0, "recall": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}}, "EXECUTABLE": {"f1": {"denominator": 100, "numerator": 100, "percent": 100.0, "status": "MEASURED"}, "gold_count": 50, "precision": {"denominator": 50, "numerator": 50, "percent": 100.0, "status": "MEASURED"}, "predicted_count": 50, "recall": {"denominator": 50, "numerator": 50, "percent": 100.0, "status": "MEASURED"}}, "EXECUTABLE_WITH_NOTICE": {"f1": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}, "gold_count": 0, "precision": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}, "predicted_count": 0, "recall": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}}, "INCOMPLETE": {"f1": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}, "gold_count": 0, "precision": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}, "predicted_count": 0, "recall": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}}, "UNSUPPORTED": {"f1": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}, "gold_count": 0, "precision": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}, "predicted_count": 0, "recall": {"denominator": 0, "numerator": 0, "percent": null, "status": "N/A"}}}, "strict_scored_dimension_match": {"denominator": 50, "numerator": 0, "percent": 0.0, "status": "MEASURED"}, "typed_accuracy": {"denominator": 50, "numerator": 50, "percent": 100.0, "status": "MEASURED"}, "unsupported_decisions": 0, "unsupported_output_schema": 0, "valid_outputs": 50}} |
| FIVE_REVISED_AMBIGUITY_COHORT | {"author_scalar_assertions": "Excluded for all five: intentionally unknown query operands, not missing gold.", "false_execution_count": 4, "not_tuning_targets": true, "safe_non_execution": {"denominator": 5, "numerator": 1, "percent": 20.0, "status": "MEASURED"}, "typed_recognition": {"denominator": 5, "numerator": 1, "percent": 20.0, "status": "MEASURED"}} |
| FINAL_MEANING | Evaluation complete and valid. Parser accuracy, policy readiness and production acceptance are not established by PASS. |
| UNRESOLVED_EVALUATION_BLOCKERS | [] |
| NEXT_PHASE_AUTHORIZED | NO: separate explicit authorization required for any threshold/policy investigation; heldout remains separately gated. |

## Evidence

- reports/search_v2c_c5c_preflight.json
- reports/search_v2c_c5c_eligibility.json
- reports/search_v2c_c5c_applicability_audit.json
- reports/search_v2c_c5c_parser_configuration.json
- reports/search_v2c_c5c_parser_inputs.jsonl
- reports/search_v2c_c5c_predictions.jsonl
- reports/search_v2c_c5c_prediction_complete.json
- reports/search_v2c_c5c_scoring_applicability.json
- reports/search_v2c_c5c_typed_decision_scoring.json
- reports/search_v2c_c5c_execution_decision_scoring.json
- reports/search_v2c_c5c_operand_scoring.json
- reports/search_v2c_c5c_stratified_matrix.json
- reports/search_v2c_c5c_confidence_observations.json
- reports/search_v2c_c5c_failures.jsonl
- reports/search_v2c_c5c_failure_analysis.json
- reports/search_v2c_c5c_five_case_ambiguity_diagnostic.json
- reports/search_v2c_c5c_historical_accounting.json
- reports/search_v2c_c5c_preservation.json
- reports/search_v2c_c5c_prohibited_activity_audit.json
- reports/search_v2c_c5c_final_qa.json
- reports/search_v2c_c5c_validation.json
- reports/search_v2c_c5c_freeze_manifest.json
