# V2C-C.2 development review

PARTIAL. Calibration is not authorized. Bounded deterministic hardening and the complete V2 development evaluation are implemented; mandatory gates remain authoritative.

V2 has 7211 unique contexts,82 original/query families grouped into30 conservative structural components,2000 paraphrase and1000 noisy cases. All seven duplicates removed; exposed legacy holdout removed. Zero cross-split family/topology overlap. Conservative sanitation moved all legacy heldout parser material into development/calibration before evaluation. Fifty newly authored cases form the final unseen holdout; the independent reviewer flagged all100 new sealed calibration/holdout labels as ambiguous. They remain UNREVIEWED, not ready for final acceptance.

Executed 6529 parser cases and352 real Mongo/API native cases, with no silently dropped development rows. Native ownership/state oracles pass, but233 raw HTTP statuses disagree with historical author expectations. Four legacy delta plans mismatch nonempty authored fields. Synthetic-prior rating changes are explicitly listed, including intentional rating updates; they are not all classified as corruption. These are not exact lifecycle passes or hidden gold corrections.

Final disjoint backend population: 2086 passed,3 failed. Three of136 original legacy gold plans expect an additional broader text exclusion. Their original labels and failing raw assertions remain unchanged. All1000 legacy seeded variant checks pass; no subset totals are added twice. Tenant129, catalogue88, retrieval23, inventory95, C1 matrix20 and B1 lifecycle18 pass; frontend Search34 pass.

Focused Chromium: PASS; live Search restarted from current parser source. Global/public/private authorized checks, outsider concealment, scoped suggestions, clarification, chip removal, original-wording correction and accepted-session preservation are recorded separately.

Parser n1000 p50/p95/p99: 5.076/13.949/17.672 ms. Identical rotating workload; no speedup claim across different runs.

Original C/C.1 structured reports,raw corpus,original metrics and540-row seed source remain byte preserved. Recommendation/MLT/Inventory and model/index sources unchanged. The normal authentication revocation SQLite journal changed during logout tests; this runtime store is disclosed, not claimed byte preserved. Production HNSW/KG are not rebuilt; tiny isolated test fixtures are separate.

Safety metrics (original labels; full raw denominators):
- EXACT_PLAN_MATCH: 2090/6529 (32.0110%)
- DECISION_ACCURACY: 4892/6529 (74.9272%)
- HARD_CONSTRAINT_PRECISION: 3555/4296 (82.7514%)
- HARD_CONSTRAINT_RECALL: 3555/6580 (54.0274%)
- COMPARATOR_ACCURACY: 628/912 (68.8596%)
- SUBJECT_EXACTNESS: 4952/6529 (75.8462%)
- NEGATIVE_CONSTRAINT_ACCURACY: 5954/6529 (91.1931%)
- SEMANTIC_REMAINDER_EXACT_MATCH: 3252/6529 (49.8085%)
- SEMANTIC_REMAINDER_TOKEN_F1: 3807.903946053941/6529 (58.3229%)
- PROTECTED_ENTITY_PRESERVATION: 1404/1440 (97.5000%)
- UNSAFE_AUTO_PARSE_RATE: 268/1912 (14.0167%)
- FALSE_HARD_FILTER_RATE: 455/6529 (6.9689%)
- FALSE_CLARIFICATION_RATE: 594/4617 (12.8655%)
- CROSS_SCOPE_VOCABULARY_LEAKAGE_RATE: 0/6529 (0.0000%)
- AMBIGUITY_RECALL: 291/449 (64.8107%)
- CONTRADICTION_RECALL: 267/585 (45.6410%)
- INCOMPLETE_RECALL: 362/554 (65.3430%)
- UNSUPPORTED_HONESTY: 285/324 (87.9630%)
- ALL_CASE_UNSAFE_AUTO_PARSE_RATE: 268/6529 (4.1048%)
- SUPPORTED_CONTRADICTION_RECALL: 267/583 (45.7976%)

No calibration, heldout evaluation,LLM second opinion or Part2I occurred. No parser tuning followed the final development evaluation. See final_qa JSON and exact case lists for the stop conditions.