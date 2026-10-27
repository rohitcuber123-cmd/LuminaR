V2C-C remains PARTIAL. Calibration remains blocked.

C3 implemented bounded source-evidenced numeric, range, format/subject collision, entity, negation and boundary repairs. Original reports, raw gold and assertions are byte-preserved. No parser change followed final development scoring.

Complete development population: 6529 parser + 352 native. Native raw/canonical status agreement: 99/332 29.8193% / 352/352 100.0000%. State/privacy: 352/352 100.0000% / 352/352 100.0000%.

Raw legacy136: 131/136; reviewed136: 134/136; raw seeded1000: 1000/1000. The three independently reviewed overrides do not silently repair two newly exposed raw natural-negation disagreements. Nine raw regression assertions retain broader text-exclusion expectations; these are reported as failures, not green regressions.

| QA field | Observed |
|---|---|
| FINAL | PARTIAL |
| V2C_C3_IMPLEMENTED | YES |
| CALIBRATION_AUTHORIZED | NO |
| CALIBRATION_RUN | NO |
| HELDOUT_RUN | NO |
| LLM_STARTED | NO |
| SEALED_LABEL_CASES | 100 |
| SEALED_LABELS_CONFIRMED | 0 |
| SEALED_LABELS_REVISED | 100 |
| SEALED_QUERIES_REPLACED | 0 |
| SEALED_CASES_REMOVED | 0 |
| SEALED_CASES_RECLASSIFIED_AMBIGUOUS | 0 |
| SEALED_AI_REVIEWED | 100 |
| SEALED_HUMAN_REVIEWED | 0 |
| NATIVE_HISTORICAL_STATUS_DISAGREEMENTS | 233 |
| NATIVE_V2_STATUS_DISAGREEMENTS | 0 |
| NATIVE_STATE_ORACLE_FAILURES | 0 |
| NATIVE_PRIVACY_ORACLE_FAILURES | 0 |
| RAW_LEGACY_GOLD | 131/136 |
| REVIEWED_V2_LEGACY_GOLD | 134/136 |
| RAW_LEGACY_SEEDED_1000 | 1000/1000 |
| LEGACY_GOLD_CASES_CLASSIFIED_PARSER_DEFECT | 0 |
| LEGACY_GOLD_CASES_CLASSIFIED_GOLD_DEFECT | 3 |
| LEGACY_GOLD_CASES_EQUIVALENT | 0 |
| DELTA_PLAN_CASES_AUDITED | 4 |
| DEVELOPMENT_PARSER_CASES | 6529 |
| DEVELOPMENT_NATIVE_CASES | 352 |
| EXACT_PLAN_MATCH | 2540/6529 38.9034% |
| DECISION_ACCURACY | 5493/6529 84.1323% |
| HARD_CONSTRAINT_PRECISION | 4946/5224 94.6784% |
| HARD_CONSTRAINT_RECALL | 4946/6533 75.7079% |
| COMPARATOR_ACCURACY | 911/911 100.0000% |
| SUBJECT_EXACTNESS | 5265/6529 80.6402% |
| NEGATIVE_CONSTRAINT_ACCURACY | 6346/6529 97.1971% |
| SEMANTIC_REMAINDER_EXACT | 3879/6529 59.4119% |
| SEMANTIC_REMAINDER_TOKEN_F1 | 4570.738739038747/6529 70.0067% |
| AMBIGUITY_RECALL | 263/450 58.4444% |
| CONTRADICTION_RECALL | 557/585 95.2137% |
| SUPPORTED_CONTRADICTION_RECALL | 557/583 95.5403% |
| INCOMPLETE_RECALL | 390/554 70.3971% |
| UNSUPPORTED_HONESTY | 293/324 90.4321% |
| PROTECTED_ENTITY_PRESERVATION | 1428/1440 99.1667% |
| FALSE_HARD_FILTER_RATE | 194/6529 2.9714% |
| BLOCKED_CASE_UNSAFE_AUTO_PARSE | 54/1913 2.8228% |
| ALL_CASE_UNSAFE_AUTO_PARSE | 54/6529 0.8271% |
| FALSE_CLARIFICATION_RATE | 297/4616 6.4341% |
| CROSS_SCOPE_VOCABULARY_LEAKAGE | 0/6529 0.0000% |
| SECURITY_FAMILY_UNSAFE_AUTO_PARSE | 0/328 0.0000% |
| SESSION_CORRUPTION_RATE | 0/352 0.0000% |
| PRIVATE_DATA_LEAKS | 0 |
| V2A_REGRESSION | FAIL |
| V2B_REGRESSION | PASS |
| V2C_A_REGRESSION | FAIL |
| V2C_A1_REGRESSION | PASS |
| V2C_B_REGRESSION | FAIL |
| V2C_B1_REGRESSION | PASS |
| V2C_C1_REGRESSION | PASS |
| RECOMMENDATION_REGRESSION | PASS |
| MORE_LIKE_THIS_REGRESSION | PASS |
| STAFF_INVENTORY_REGRESSION | PASS |
| FOCUSED_BROWSER | PASS |
| PARSER_P50_P95_P99 | 1.129/14.863/17.160 ms (n=1000) |
| GLOBAL_BOOK_COUNT | 5000000 |
| GLOBAL_SEARCH_HEALTH | STALE / degraded; baseline_verified=False |
| GLOBAL_HNSW_REBUILT | NO |
| GLOBAL_KG_REBUILT | NO |
| TENANT_HNSW_KG_REBUILT | NO |
| EMBEDDING_MODEL_CHANGED | NO |
| CROSSENCODER_CHANGED | NO |
| QWEN_CHANGED | NO |
| RECOMMENDATION_CHANGED | NO |
| MORE_LIKE_THIS_CHANGED | NO |
| STAFF_INVENTORY_CHANGED | NO |
| PART_2I_STARTED | NO |
| metric_view | Independent reviewed development field overrides + proven positive BOTH equivalence; raw and normalized-original metrics separately preserved |
| calibration_evaluations | 0 |
| heldout_evaluations | 0 |
| frozen_sources_unchanged | True |
| final_parser_changes_after_evaluation | 0 |
| completed_at | 2026-10-16T19:08:32.503041+00:00 |

Mandatory violations:
- FALSE_HARD_FILTER_RATE: {'numerator': 194, 'denominator': 6529, 'percent': 2.971358554143054} (required <=1)
- SUPPORTED_CONTRADICTION_RECALL: {'numerator': 557, 'denominator': 583, 'percent': 95.54030874785592} (required ==100)

Metrics describe this development population, not real-world accuracy. Sealed labels:100 independently AI revised,0 human reviewed; all sealed parser evaluation counts remain0. Development review is partial field review: uncertain projections remain unresolved and original values retained.

Backend 2181/2190; frontend34/34; focused Chromium16/16. No production HNSW/KG rebuild or model/source change outside the bounded Search parser. Global5,000,000; health remains truthfully STALE/degraded, baseline unverified. Large indexes verified by prior-preservation size/mtime where full checksums unavailable; no fresh full checksum claimed.
