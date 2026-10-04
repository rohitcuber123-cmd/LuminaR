# LuminaR V7R2 controlled source-referenced assisted QA

**Current gate: B. V7R2 GENERATOR SEMANTICS STILL TOO LOW QUALITY — CHANGE GENERATOR APPROACH.**

V7R0 and V7R1 remain frozen. Their saved SHA-256 values were checked after V7R2; none changed. V7R2 reused the exact same 50 TRAIN passages in the same order from `rag_domain_qa_v7r1_original_passages.json`. Source hashes, chunk IDs, source ranges, TEST exclusion, and accepted evaluation-span exclusion were verified before and after generation.

## Source presentation and grounding

The authoritative `tokens_220` passage is unchanged and remains the training positive. A separate presentation view applies Unicode NFKC to character clusters and collapses whitespace runs. Each presentation character maps to an exact authoritative source span. Mapping a presentation span back to source recovers the exact original characters, including line wraps. No fuzzy semantic matching or normalization is used to accept source evidence.

Conservative sentence segmentation, with safe clause splits only for very long sentences and merging of tiny fragments, produced **331 stable S-ID units** across 50 passages. All 50 presentation views passed deterministic round-trip checks. All 331 units passed authoritative offset and source-hash checks; there were **0 unit integrity failures** and 0 unsplit units longer than 650 presentation characters. The unit manifest records authoritative and presentation spans, absolute source offsets, exact source text, IDs, and hashes.

The V7R2 generator schema contains `question`, `answer_text`, `answer_unit_id`, `evidence_unit_ids`, `category`, `difficulty`, and `support_explanation`; it does **not** accept a generated evidence quote. Evidence may name one unit or two adjacent units. Code reconstructs exact evidence from the authoritative passage. The generator's `answer_text` must be an exact substring of the selected answer unit's presentation text and occur uniquely there. Code maps that span to the authoritative source, storing both generated and authoritative answer surfaces and offsets. Invalid, duplicate, distant, or excessive unit IDs and an answer unit outside evidence are rejected. The three-run pilot had **0 invalid unit references** and **0 evidence-source failures**.

The local cached Qwen2.5-3B-Instruct snapshot `aa8e72537993ba99e69dfaafa59ed015b17504d1` ran on CUDA in FP16 with greedy `do_sample=false`. V7R2 used 480 maximum generator tokens and 240 maximum judge tokens, slightly above V7R1's 430/210 to accommodate extra JSON unit fields. Generator and judge used the same model; judge agreement is not independent verification. The strict judge could cite only selected evidence-unit IDs. Its three UNCERTAIN outcomes were invalid judge JSON after the one allowed retry.

## Controlled comparison

All columns use the same 50 TRAIN passages. Failure reasons can overlap, and downstream checks are censored by earlier failures. A dash means the interface did not have that check. V7R0 was a misconfigured category-prompt control, not a valid semantic-quality measurement.

| Metric | V7R0 | V7R1 | V7R2 |
|---|---:|---:|---:|
| Passages | 50 | 50 | 50 |
| Raw proposals | 93 | 36 | 50 |
| Zero-candidate passages | 0 | 14 | 0 |
| Invalid JSON | 1 | 0 | 1 |
| Invalid category | 91 | 0 | 0 |
| Invalid difficulty | 1 | 0 | 0 |
| Evidence failures | 80 | 31 | 0 |
| Unit-reference failures | — | — | 0 |
| Answer presentation-match failures | — | — | 23 |
| Ambiguous answer occurrence | — | — | 3 |
| Answer completeness/type failures | 0 | 0 | 11 |
| Question/reference failures | 0 | 5 | 20 |
| Deterministic passes | 0 | 0 | 4 |
| Semantic SUPPORTED | 0 | 0 | 1 |
| Semantic UNSUPPORTED | 0 | 0 | 0 |
| Semantic UNCERTAIN | 0 | 0 | 3 |
| AUTO_CHECKED | 0 | 0 | 1 |

The source-reference interface removed the brittle generated-evidence comparison. The main remaining failures were **23/50 answers not copied exactly from their selected presentation unit**, plus question/reference and answer-type errors. The new source mapping did not cause these failures. One supported candidate, `AQA7R2-031-1`, was engineering source-audited as `PLAUSIBLE_FOR_HUMAN_REVIEW`: its authoritative S01 directly states that Bingley wanted to be alone with Jane. This is engineering inspection only, not human `REVIEWED` status. Engineering totals: plausible 1, obvious semantic error 0, ambiguous 0; observed obvious-error rate 0/1, too small to establish quality.

## Gate and verification

`AUTO_CHECKED` is **1**, below the required 20. The review packet has **0 rows and was not created**. No external human review exists. V8 finalization, V9 negative mining, and V10 Model C training were not started. TEST leakage 0; evaluation-span leakage 0; source hashes valid. The 64-file production SHA-256 snapshot has **0 changes**. The frozen V7R0/V7R1 artifacts have **0 changes**.

Focused V7/V7R1/V7R2 tests: **30 passed, 0 failed**; all new scripts compile. Added files are `rag_domain_qa_source_units_v7r2.py`, `rag_domain_qa_assisted_v7r2.py`, `audit_rag_domain_qa_source_units_v7r2.py`, `build_rag_domain_qa_assisted_v7r2.py`, `validate_rag_domain_qa_assisted_v7r2.py`, `compare_rag_domain_qa_v7_generations.py`, `audit_rag_domain_qa_assisted_v7r2.py`, `tests/test_rag_domain_qa_assisted_v7r2.py`, the V7R2 source-unit manifest and separate raw/accepted/rejected JSONL, and the V7R2 contract, generation, comparison, engineering-source-audit, and final reports. No historical artifact was overwritten.
