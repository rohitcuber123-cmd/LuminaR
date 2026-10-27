# LuminaR V2C-C.5D — semantic parser investigation and shadow remediation

FINAL: PASS. Contract audit, causal investigation, isolated shadow replay and evidence freeze are complete. No production parser was rerun or changed. This is not parser repair, deployment approval, completed calibration or policy selection.

## Exit decision

PATH C — Mixed remediation required. Separately authorize a versioned offline parser/contract remediation prototype with an explicit mandatory-requirement ledger and source-span ownership; independently review notice/field/advisory/intent contracts before any oracle change. Keep production routes/policies unchanged.

## Exact baseline and preservation

C5B admission/freeze, all31 C5C frozen payload files, captured predictions, masks, normative gold, evaluator configuration and prior preservation evidence passed SHA256 verification before analysis. C5C prediction SHA256 remains `0a5ebcca95b4acec9363db860cdf76b90e5c2c7b9915b4ad959090e5e65bc704`. All 1683 protected existing files and462 production files were preserved. Heldout bytes were hashed only; no heldout examples/predictions were decoded.

The 644 C5C parser contexts remain594 new core +50 retained reviewed originals. All new primary analysis uses these frozen predictions; no new parser/model/native evaluation occurred. All original C5A/C5B/C5C scores and dispositions remain unchanged.

## EXECUTABLE_WITH_NOTICE contract audit

This is a mixture of representation ownership ambiguity and actual missing repair behavior. The parser accepts EXECUTABLE_WITH_NOTICE as an enum but its SMART composer has no typed-notice producer. assess/execution_policy can infer notice from captured repairs/corrections/unknown_subject. The native search response instead exposes typed decisions, corrections and notices through QueryPlan.public/interpretation/interaction_for; it does not directly consume the assessment policy label.

For all100 gold notice cases, there are0 typed notices,0 downstream C4 policy notices,0 corrections/repair-provenance/unknown-subject signals,70 EXECUTABLE/AUTO_EXECUTE outcomes and30 clarification outcomes. Thus the cohort cannot be explained away by a notice merely moving downstream. Misspelled comparator/format/entity cues may be ignored, blocked, or treated as exact-star equality without repair provenance. No score correction is applied. Independent review must establish future typed/advisory ownership and native observable notice requirements before changing an evaluator contract.

Exact sources: search/query_plan.py:155; search/query_repair.py:28,48,73,126,131; search/query_numeric.py:64,110; search/query_calibration.py:16; search/query_execution.py:17,31; search/query_interaction.py:22. Full excerpts, hashes and source locations are in source_references_v2.json.

## Causal findings

All635 mismatch contexts have a causal matrix record:585 new-core and50 retained-original. Distinct counts below overlap and must not be added. They are C5D source/capture attributions, not replacements of the historical C5C classifications.

| Finding | Distinct contexts | Representative IDs | Evidence and limitation |
|---|---:|---|---|
| Quoted operand masking | 382 | C5A-1-1-03, C5A-1-1-04 | Source.remaining hides quoted content and Source.free rejects overlap; title has an ownership exception while subject/exclusion parsing does not. |
| Explicit title clears topic | 133 | C5A-1-1-02, C5A-1-1-05 | compose assigns semantic_text=None after encountering a title. |
| Other finite field-recognizer gaps | 222 | C5A-2-1-01, C5A-2-1-10 | Availability/publication/entity constructions have no corresponding captured candidate; exact responsible recognizers cited per dimension. |
| Format-only modifier scope | 141 | C5A-2-1-02, C5A-2-1-05 | Format is captured as PRESENT without separated ONLY modifier. |
| Untagged numeric fallback | 20 | C5A-1-2-01, C5A-1-2-02 | Exact-star equality replaces a misspelled comparator/range without repair provenance; can invent an extra bound. |
| Topic tokens retained despite strict mismatch | 65 | C5A-1-1-14, C5A-2-1-01 | Extra wrappers/residual requirements remain; strict disagreement alone does not prove lost semantic intent. |
| Correct typed class, affected-field contract concern | 101 | See root_cause_matrix_v2.jsonl | Family vs endpoint codes need independent specification; no equivalence adapter applied. |
| Retained author/title intent priority | 50 | v3:c3-sealed-01-00 | Composer selects FIND_AUTHOR when author is present; retained gold expects FIND_EXACT. Both hard operands can remain present. |

C5D source/capture-backed parser-defect dimensions appear in557 distinct contexts; evaluator contract concerns in151; indeterminate mismatches in213; multiple interacting causes in379. Counts overlap. The original C5C562 parser-defect-containing and567 indeterminate-containing counts remain frozen. No new normative gold concern is automatically inferred from disagreement.

## False-execution and ambiguity/incompleteness diagnostics

All191 false-execution recommendations are traced from reduced/absent requirement evidence to default EXECUTABLE and then AUTO_EXECUTE. No captured blocked parser decision was promoted by the downstream policy. Semantic typed misses are83/98 ambiguous,72/99 incomplete,89/100 unsupported and33/97 contradictory. The first observable issue is often missing candidate or mandatory unresolved-state evidence; the final validator cannot reason about requirements it never received.

The five revised author-association cases show an additional diagnostic limit: the one AMBIGUOUS output is NUMBER_WITHOUT_FIELD from publication wording, not explicit recognition of the required unresolved author relation. Four unsafe recommendations remain under every shadow candidate. The scalar author-value metric stays intentionally unresolved; required decision gold stays complete.

## Safety invariants and shadow design

Existing authority precedes native catalogue/choice access. Only executable typed kinds permit execution. Known contradictions and scope-incompatible parsed constraints block. Missing/ambiguous recognized requirements request clarification. A repair notice is compatible with legitimate execution. Owner/query/mode/version/expiry and one-use reservation remain native preconditions. These are source-grounded boundaries; a complete mandatory-requirement ledger is currently absent.

Five candidates were frozen before replay: A baseline; B recognized-candidate operand preservation; C parsed consistency/unresolved-state checks; D known output-intent/schema/capability validation; E composition. Candidate functions receive no IDs, query text, gold, expected decisions, reviewer rationale, strata, outcome scores or confidence. The runner associates IDs outside the candidate call. Candidates can only withhold a baseline recommendation and cannot authorize, issue choices, mutate plans or enter the production request path.

## Actual exploratory replay results

| Candidate | False execution / blocked gold | Missed execution / executable gold | Execution coverage | Changed recommendations | Additional missed valid executions |
|---|---:|---:|---:|---:|---:|
| A_BASELINE | 191/394 (48.48%) | 43/250 (17.20%) | 398/644 (61.80%) | 0 | 0 |
| B_CANDIDATE_OPERAND_GUARD | 183/394 (46.45%) | 43/250 (17.20%) | 390/644 (60.56%) | 8 | 0 |
| C_PARSED_CONSISTENCY_GUARD | 187/394 (47.46%) | 43/250 (17.20%) | 394/644 (61.18%) | 4 | 0 |
| D_SUPPORTED_OUTPUT_GUARD | 191/394 (48.48%) | 43/250 (17.20%) | 398/644 (61.80%) | 0 | 0 |
| E_COMPOSED_GUARD | 179/394 (45.43%) | 43/250 (17.20%) | 386/644 (59.94%) | 12 | 0 |

There were3,220 primary candidate replays on644 existing records, not3,220 parser calls. B/C/E add8/4/12 review holds, all on blocked gold in this cohort. D changes nothing because valid default output intents and omitted fields provide no semantic unsupported-operation evidence. No blocked baseline result is promoted. All five revised author cases remain unchanged. Every guard still lacks a full query-requirement completeness/authority proof on all644 records.

Additional missed CLEAR_EXECUTABLE and SAFE_UNCERTAIN_EXECUTABLE recommendations are0 for each candidate in the primary cohort; additional missed execution is0 in every scope. These observations do not establish absence of regressions elsewhere. Scope/stratum and all30 cells, exact changed IDs and reasons are retained for every candidate in shadow_replay_results.json.

False executions by scope (blocked denominators Global77, Public patron80, Public staff80, Private patron79, Private staff78):

| Candidate | Global | Public patron | Public staff | Private patron | Private staff |
|---|---:|---:|---:|---:|---:|
| A_BASELINE | 48 | 41 | 34 | 35 | 33 |
| B_CANDIDATE_OPERAND_GUARD | 46 | 39 | 34 | 33 | 31 |
| C_PARSED_CONSISTENCY_GUARD | 47 | 40 | 34 | 34 | 32 |
| D_SUPPORTED_OUTPUT_GUARD | 48 | 41 | 34 | 35 | 33 |
| E_COMPOSED_GUARD | 45 | 38 | 34 | 32 | 30 |

## Counterexample and independent-validation limits

A separately recorded post-freeze counterexample shows that C, and therefore E, uses substring containment more broadly than the production whole-word negative predicate: required author Marsh with excluded term ar is satisfiable under the source predicate, but the prototype withholds it. The frozen prototype and primary results were not edited. This is a confirmed shadow-prototype limitation and a reason not to infer deployability from apparent replay improvement.

Six pre-existing independently output-blind AI-reviewed DEVELOPMENT examples were identified and kept as one complete structural group. Their operation topology does not overlap the C5C eligible population. Frozen historical C4 predictions were replayed through the already frozen candidates: all five preserve6/6 executable recommendations; false-execution rate is N/A because there are no blocked examples. These30 supplementary replays are separate from primary denominators. No new reviewer or parser execution is claimed.

This is limited historical regression evidence, not adequate independent safety validation. Fresh structurally grouped hard negatives, safe-uncertain positives, privacy-sensitive scope cases and exact predicate-boundary adversarial examples are prerequisites for future acceptance. Primary candidates were designed after viewing C5C errors; same-corpus improvements do not establish generalization.

The supplementary metadata preparation first stopped before replay because of repeated file decoding; its corrected preparation is separately recorded. One diagnostic UTF8 read failure is also recorded. Neither event created parser calls, altered gold/predictions or erased replay attempts. Sixteen pre-freeze controlled invariant checks and one post-freeze semantic counterexample are separate from benchmark denominators.

## Confidence diagnosis

QueryPlan defaults to1.0; exact/alias/fuzzy vocabulary resolution can provide similarity values; blocked typed decisions force0.0. On this corpus the observed0.0/1.0 signal exactly duplicates binary executability. At1.0,207 executable-gold and191 blocked-gold recommendations share the same value, and typed correctness is137/398. The signal has no defensible calibrated-probability interpretation. No threshold or transformation was fitted or swept.

## Ranked remediation and next boundary

1. **Mandatory requirement ledger and semantic blocking state** — Parser semantic recognition plus fail-closed-on-known-unresolved safety boundary. 191/191 EXECUTABLE -> AUTO_EXECUTE; missing relation, incomplete, unsupported or contradiction prerequisites. Risk: Blanket uncertainty refusal would regress legitimate executable cases; ledger must distinguish required, advisory, unresolved and absent. Independent review: Required for requirement ownership and hard-negative/safe-uncertain validation. Offline test: New isolated parser fork + frozen ledger assertions; no production route.
2. **Explicit field/span ownership and candidate composition** — Parser extraction. Protected quotes hide subject/negative operands; format-only boundaries, availability phrasing and publication equality have finite grammar gaps. Risk: Do not parse inside quoted entities globally or narrow generic topical prose into hard filters. Independent review: Reviewed minimal pairs for explicit fields vs opaque literals and optional prose. Offline test: Source-span ownership, lossless candidate inventory and grouped grammar regressions.
3. **Notice, affected-field, advisory and intent contract ownership** — Output contract and evaluator alignment before score changes. Notice0/100 in both observed layers; 101 field-code and50 retained-intent concerns; 594 unavailable structured advisory oracles. Risk: An adapter could hide real missing functionality if it simply makes labels agree. Independent review: Required before any future label/oracle version; original C5C remains immutable. Offline test: Review exact observable layer ownership and deliberately inequivalent counterexamples.
4. **Bounded operator repairs with provenance and topic preservation** — Parser recognition and assembly. Title assignment clears semantic_text; exact-star fallback can replace misspelled comparator semantics without notice. Risk: Do not guess unrecoverable operands or treat every strict remainder mismatch as loss;65 contexts retain normative topic tokens. Independent review: Required operator repair and intent/topic minimal pairs. Offline test: No invented extra bounds; correct operator provenance and independent title/topic assertions.
5. **Source-grounded consistency/review guards** — Offline safety controls, not selected production policy. B/C/E hold8/4/12 false recommendations in exploratory replay; E still leaves179/394 and misses all four unsafe revised author cases. Risk: Frozen C/E substring counterexample proves possible false holds; no deployment inference from zero observed cohort regressions. Independent review: Required exact normalization/whole-word semantics and structurally separate blocked/positive validation. Offline test: Correct the prototype specification only in a future version, then freeze before fresh validation; retain current failed counterexample.
6. **Confidence representation and future calibration feasibility** — Feature/oracle design, later offline calibration. 207 valid and191 unsafe execution recommendations share native1.0; observed signal duplicates binary executability. Risk: Threshold fitting on these tied signals cannot discriminate the cases; corpus reuse risks overfitting. Independent review: Independent labels and complete grouped coverage before any new fitted model/statistic. Offline test: Collect source-backed completeness/resolution features under a separately authorized protocol.

Separately authorize a versioned offline parser/contract remediation prototype with an explicit mandatory-requirement ledger and source-span ownership; independently review notice/field/advisory/intent contracts before any oracle change. Keep production routes/policies unchanged.

Prerequisites:
- Hash-bind original C5B/C5C and the C5D candidate/counterexample evidence.
- Freeze the next prototype and future scoring contract before fresh independent labels/results.
- Obtain structurally grouped positive, safe-uncertain and hard-negative validation across all scopes; do not split near-duplicate families.
- Demonstrate preservation of literal boundaries, optional semantics, native authority and transaction invariants without live execution.
- Retain original scores and separately version every proposed oracle or implementation change.

No production policy winner is selected. No production/parser/model/UI/native changes, heldout evaluation, threshold fitting, index rebuild, Mongo mutation, new application commit or endpoint repoll occurred. Global5,000,000 and STALE/degraded baseline_verified=False remain prior observations. Stop after C5D.

## Mandatory final QA fields

| Field | Actual value |
|---|---|
| FINAL | PASS |
| C5D_IMPLEMENTED | YES |
| C5C_FREEZE_VERIFIED | YES |
| C5C_PREDICTIONS_UNCHANGED | YES |
| C4_ACTIVE_POLICY_PRESERVED | YES |
| PRODUCTION_PARSER_CHANGED | NO |
| PRODUCTION_POLICY_CHANGED | NO |
| PARSER_POLICY_CONTRACT_AUDITED | YES |
| EXECUTABLE_WITH_NOTICE_ROOT_CAUSE | {"classification": "MIXED_CONTRACT_OWNERSHIP_AND_MISSING_REPAIR_PROVENANCE", "gold_cases": 100, "typed_notice": 0, "policy_notice": 0, "auto_without_notice": 70, "clarify": 30, "historical_scores_changed": false} |
| FALSE_EXECUTION_CASES_TRACED | 191 |
| CONFIRMED_PARSER_DEFECTS | {"C5D_unique_contexts_with_source_capture_backed_dimensions": 557, "method": "Static source/control-flow plus immutable outputs, not instrumented parser reexecution.", "C5C_historical_count_unchanged": 562} |
| CONFIRMED_POLICY_ADAPTER_DEFECTS | 0 |
| EVALUATOR_CONTRACT_CONCERNS | {"issues": [{"issue": "NOTICE_OWNERSHIP_AND_REPAIR", "contexts": 100, "state": "Mixed structural ownership concern and actual missing repair signals; independent contract review required."}, {"issue": "AFFECTED_FIELD_GRANULARITY", "contexts": 101, "state": "Typed class correct; family/endpoint equality not established. No normalization applied."}, {"issue": "STRUCTURED_ADVISORY_ORACLE", "contexts": 594, "state": "C5C advisory-object metric unavailable; display strings do not constitute a typed structured oracle."}, {"issue": "AUTHOR_TITLE_INTENT_PRECEDENCE", "contexts": 50, "state": "Retained original intent gold differs from author-first composer; independent ownership review required."}], "C5D_root_matrix_contexts": 151, "counts_overlap": true} |
| INDETERMINATE_FAILURES_REMAINING | {"C5D_indeterminate_contexts": 213, "C5D_multiple_cause_contexts": 379, "C5C_historical_indeterminate_count_unchanged": 567, "counts_overlap": true} |
| OPERAND_EXTRACTION_ROOT_CAUSES | {"QUOTED_OPERAND_MASKED": 382, "FINITE_FIELD_RECOGNIZER_GAP": 222, "FORMAT_ONLY_SCOPE_GAP": 141, "UNTAGGED_NUMERIC_FALLBACK": 20} |
| AMBIGUITY_ROOT_CAUSES | 83 typed misses: unresolved relational/operator/advisory interpretations absent from modeled blocking state; numeric fallback sometimes blocks for the wrong reason. |
| INCOMPLETE_ROOT_CAUSES | 72 typed misses: narrow end-anchored/clause grammar loses missing mandatory operand evidence before executable fallback. |
| UNSUPPORTED_ROOT_CAUSES | 89 typed misses: requested unsupported requirement absent/misrepresented in finite candidate vocabulary; output-intent whitelist cannot recover it. |
| CONTRADICTION_ROOT_CAUSES | 33 typed misses: discarded prerequisite operands and missing cross-field requirement inventory prevent consistency detection. |
| CONFIDENCE_SIGNAL_SEMANTICS | Deterministic default/string-match similarity + typed-block flag. No probabilistic training, calibrated likelihood or normative confidence target. |
| SHADOW_CANDIDATES_IMPLEMENTED | 5 |
| SHADOW_CANDIDATES_EVALUATED | 5 |
| BASELINE_FALSE_EXECUTION_COUNT | 191 |
| SHADOW_FALSE_EXECUTION_COUNTS | {"A_BASELINE": {"denominator": 394, "numerator": 191, "percent": 48.47715736040609, "status": "MEASURED"}, "B_CANDIDATE_OPERAND_GUARD": {"denominator": 394, "numerator": 183, "percent": 46.44670050761421, "status": "MEASURED"}, "C_PARSED_CONSISTENCY_GUARD": {"denominator": 394, "numerator": 187, "percent": 47.46192893401015, "status": "MEASURED"}, "D_SUPPORTED_OUTPUT_GUARD": {"denominator": 394, "numerator": 191, "percent": 48.47715736040609, "status": "MEASURED"}, "E_COMPOSED_GUARD": {"denominator": 394, "numerator": 179, "percent": 45.431472081218274, "status": "MEASURED"}} |
| BASELINE_MISSED_EXECUTION_COUNT | 43 |
| SHADOW_MISSED_EXECUTION_COUNTS | {"A_BASELINE": {"denominator": 250, "numerator": 43, "percent": 17.2, "status": "MEASURED"}, "B_CANDIDATE_OPERAND_GUARD": {"denominator": 250, "numerator": 43, "percent": 17.2, "status": "MEASURED"}, "C_PARSED_CONSISTENCY_GUARD": {"denominator": 250, "numerator": 43, "percent": 17.2, "status": "MEASURED"}, "D_SUPPORTED_OUTPUT_GUARD": {"denominator": 250, "numerator": 43, "percent": 17.2, "status": "MEASURED"}, "E_COMPOSED_GUARD": {"denominator": 250, "numerator": 43, "percent": 17.2, "status": "MEASURED"}} |
| CLEAR_EXECUTABLE_REGRESSIONS | {"observed_C5C_additional_misses": {"A_BASELINE": 0, "B_CANDIDATE_OPERAND_GUARD": 0, "C_PARSED_CONSISTENCY_GUARD": 0, "D_SUPPORTED_OUTPUT_GUARD": 0, "E_COMPOSED_GUARD": 0}, "known_out_of_cohort_positive_counterexample": "C/E may falsely hold a valid whole-word-negative request; retained in prototype_counterexample_audit.json."} |
| SAFE_UNCERTAIN_EXECUTABLE_REGRESSIONS | {"A_BASELINE": 0, "B_CANDIDATE_OPERAND_GUARD": 0, "C_PARSED_CONSISTENCY_GUARD": 0, "D_SUPPORTED_OUTPUT_GUARD": 0, "E_COMPOSED_GUARD": 0} |
| SCOPE_SPECIFIC_SAFETY_REGRESSIONS | {"A_BASELINE": {"GLOBAL": 0, "PRIVATE_TENANT_PATRON": 0, "PRIVATE_TENANT_STAFF": 0, "PUBLIC_TENANT_PATRON": 0, "PUBLIC_TENANT_STAFF": 0}, "B_CANDIDATE_OPERAND_GUARD": {"GLOBAL": 0, "PRIVATE_TENANT_PATRON": 0, "PRIVATE_TENANT_STAFF": 0, "PUBLIC_TENANT_PATRON": 0, "PUBLIC_TENANT_STAFF": 0}, "C_PARSED_CONSISTENCY_GUARD": {"GLOBAL": 0, "PRIVATE_TENANT_PATRON": 0, "PRIVATE_TENANT_STAFF": 0, "PUBLIC_TENANT_PATRON": 0, "PUBLIC_TENANT_STAFF": 0}, "D_SUPPORTED_OUTPUT_GUARD": {"GLOBAL": 0, "PRIVATE_TENANT_PATRON": 0, "PRIVATE_TENANT_STAFF": 0, "PUBLIC_TENANT_PATRON": 0, "PUBLIC_TENANT_STAFF": 0}, "E_COMPOSED_GUARD": {"GLOBAL": 0, "PRIVATE_TENANT_PATRON": 0, "PRIVATE_TENANT_STAFF": 0, "PUBLIC_TENANT_PATRON": 0, "PUBLIC_TENANT_STAFF": 0}} |
| INDEPENDENT_VALIDATION_AVAILABLE | LIMITED: six pre-existing independently reviewed DEVELOPMENT positives, one structural group; no adequate independent safety/generalization validation. |
| PRODUCTION_SOURCE_HASH_VERIFICATION | PASS (462 files) |
| HISTORICAL_EVIDENCE_HASH_VERIFICATION | PASS (1683 protected pre-existing files) |
| SEALED_HELDOUT_HASH_UNCHANGED | YES |
| C5D_EVIDENCE_FROZEN | YES |
| THRESHOLD_FITTING_PERFORMED | NO |
| CALIBRATION_POLICY_SELECTED | NO |
| CALIBRATION_POLICY_ACTIVATED | NO |
| HELDOUT_EVALUATIONS | 0 |
| HNSW_REBUILT | NO |
| KG_REBUILT | NO |
| PART_2I_STARTED | NO |
| NEW_PRODUCTION_PARSER_CALLS | 0 |
| PRIMARY_SHADOW_REPLAYS | 3220 |
| HISTORICAL_DEVELOPMENT_REPLAYS | 30 |
| CONTROLLED_INVARIANT_CALLS | 16 |
| POST_FREEZE_COUNTEREXAMPLE_CALLS | 1 |
| EXIT_DECISION | PATH C — Mixed remediation required |
| PARSER_REPAIRED | NO |
| SHADOW_SAFE_TO_DEPLOY | NOT_ESTABLISHED |
| CALIBRATION_COMPLETE | NO |
| next_implementation_boundary | Separately authorize a versioned offline parser/contract remediation prototype with an explicit mandatory-requirement ledger and source-span ownership; independently review notice/field/advisory/intent contracts before any oracle change. Keep production routes/policies unchanged. |

## Exact evidence paths

- reports/search_v2c_c5d_preflight.json
- reports/search_v2c_c5d_architecture.json
- reports/search_v2c_c5d_source_references_v2.json
- reports/search_v2c_c5d_typed_decision_contract_audit.json
- reports/search_v2c_c5d_contract_review_proposals.json
- reports/search_v2c_c5d_root_cause_matrix_v2.jsonl
- reports/search_v2c_c5d_root_cause_summary.json
- reports/search_v2c_c5d_false_execution_traceability.jsonl
- reports/search_v2c_c5d_operand_extraction_diagnostics_v2.jsonl
- reports/search_v2c_c5d_semantic_remainder_diagnostics.jsonl
- reports/search_v2c_c5d_ambiguity_contradiction_diagnostics.json
- reports/search_v2c_c5d_confidence_investigation.json
- reports/search_v2c_c5d_safety_invariants.json
- reports/search_v2c_c5d_shadow_candidate_specifications.json
- reports/search_v2c_c5d_shadow_candidate_freeze.json
- reports/search_v2c_c5d_shadow_capture_binding.json
- reports/search_v2c_c5d_shadow_predictions.jsonl
- reports/search_v2c_c5d_shadow_replay_results.json
- reports/search_v2c_c5d_safety_regression_analysis.json
- reports/search_v2c_c5d_prototype_counterexample_audit.json
- reports/search_v2c_c5d_validation_population.json
- reports/search_v2c_c5d_independent_validation_limits.json
- reports/search_v2c_c5d_preservation.json
- reports/search_v2c_c5d_prohibited_activity_audit.json
- reports/search_v2c_c5d_remediation_recommendations.json
- reports/search_v2c_c5d_final_qa.json
- reports/search_v2c_c5d_validation.json
- reports/search_v2c_c5d_freeze_manifest.json
