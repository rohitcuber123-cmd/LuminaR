# LuminaR V7R1 controlled assisted-QA rerun

**Current gate: B. ASSISTED AUTHORING QUALITY STILL TOO LOW — REVISE GENERATION STRATEGY.**

V7R0 is a frozen, misconfigured control, not a semantic-quality measurement. Its prompt omitted the legal category enum. V7R1 reused the **exact same 50 TRAIN passages in the same order**, recovered from the saved V7 raw records, with verified chunk IDs, source ranges, source hashes, and no protected TEST or accepted evaluation-span overlap. The passage manifest is `datasets/training/manifests/rag_domain_qa_v7r1_original_passages.json`.

## Frozen V7 SHA-256

| Original artifact | SHA-256 |
|---|---|
| `domain_qa_assisted_v7_raw.jsonl` | `6fb14c90a1c648f1f9aad53d496413948813b50abc29b361b6955f0b3b97866f` |
| `domain_qa_assisted_v7_auto_checked.jsonl` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `domain_qa_assisted_v7_rejected.jsonl` | `0ea147a3e6e7a4f673e70041e757d61d496da71d45f535d96bedd0aeef34cd86` |
| `rag_domain_qa_assisted_v7_generation.json` | `220bcb010d19a0e3b5fc8c56453b73ae25df45d4202247af5c01c3ddf98de93a` |
| `rag_domain_qa_assisted_v7_audit.json` | `9420592ff29403c15769c5fbcdbe5c2c1d5111cbd791235e72a87695d67eee29` |
| `rag_domain_qa_assisted_v7_audit.md` | `3a14651837bc1f05639c85a0d4f3e3cddd656efec9fd91aea347575940cc034a` |

All six originals remained unchanged after V7R1.

## Contract and matcher audit

V7R1 explicitly lists all nine categories (`FACTUAL_DIRECT`, `ENTITY_RELATION`, `EVENT`, `MOTIVATION`, `CAUSAL`, `LOCATION`, `TEMPORAL`, `SEMANTIC_PARAPHRASE`, `QUOTE_OR_PHRASE`) and all three difficulties (`EASY`, `MEDIUM`, `HARD`). It requires a character-for-character contiguous evidence substring from the delimited target passage and an exact contiguous answer substring within that evidence. Context is separately delimited and cannot supply evidence. The model may return zero candidates. Invalid JSON gets one retry with the same content rules.

The original validator required exactly one occurrence of the quote and used one reason name for zero or multiple matches. Recounting all V7R0 proposals found **80 zero matches, 13 single matches, and 0 multiple matches**. Empty evidence was short-circuited by the original validator, so there was no empty-string acceptance or duplicate-occurrence bug; the error label was imprecise. V7R1 explicitly rejects empty evidence, records exact match counts and offsets for every candidate, and rejects multiple exact occurrences as ambiguous without a verified offset. NFKC/whitespace normalization is diagnostic only; accepted evidence must remain an exact authoritative substring.

The local cached Qwen2.5-3B-Instruct snapshot `aa8e72537993ba99e69dfaafa59ed015b17504d1` ran on CUDA in FP16 with greedy `do_sample=false`, 430 maximum generator tokens, and 210 maximum judge tokens. Model-index SHA-256: `bc8aaa0c87d4335177e01c765f1de0db81661c67c1a72fbfb0d521b09f5ddc56`. Generator and judge would use the same model; **no candidate reached the judge**, so there was no independent semantic verification.

## Controlled comparison

Counts of rejection reasons overlap. Downstream question and semantic checks are censored when an earlier deterministic check fails.

| Metric | V7R0 misconfigured | V7R1 fixed contract |
|---|---:|---:|
| Passages | 50 | 50 |
| Raw proposals | 93 | 36 |
| Zero-candidate passages | 0 | 14 |
| Invalid JSON | 1 | 0 |
| Invalid category | 91 | 0 |
| Invalid difficulty | 1 | 0 |
| Evidence exact failures | 80 | 31 |
| Ambiguous multiple exact occurrences | 0 | 0 |
| Answer exact failures | 45 | 12 |
| Question/reference failures | 0 | 1 |
| Deterministic passes | 0 | 0 |
| Semantic unsupported | 0 | 0 |
| Semantic uncertain | 0 | 0 |
| AUTO_CHECKED | 0 | 0 |

The category and difficulty contract worked. Evidence exact failures fell in absolute count because the model proposed fewer pairs; their proportion barely changed (80/93 vs 31/36, about 86% in both runs). Of the 31 V7R1 zero-match quotes, 19 match only after diagnostic whitespace/NFKC normalization; the other 12 do not. No normalization was used to promote a candidate. The evidence-copy strategy, especially for line-wrapped source text, remains the binding problem. This is a generation-strategy failure after the enum contract was fixed, rather than evidence matcher misclassification.

## Gate and safety

The `AUTO_CHECKED` engineering source audit had zero rows: plausible 0, obvious semantic error 0, ambiguous 0, and obvious-error rate **not applicable**. Source hashes are valid; TEST leakage 0; evaluation leakage 0. The review packet has **0 rows and was not created**. No human decisions exist, and V8, V9, and V10 were not started. The 64-file production SHA-256 snapshot has **0 changes**. The original six V7 artifacts have **0 changes**.

Focused contract/grounding tests: **16 passed, 0 failed**. All new scripts compile. The new V7R1 files are the six scripts `rag_domain_qa_assisted_v7r1.py`, `build_rag_domain_qa_assisted_v7r1.py`, `audit_rag_domain_qa_assisted_contract_v7r1.py`, `validate_rag_domain_qa_assisted_v7r1.py`, `compare_rag_domain_qa_v7_v7r1.py`, and `audit_rag_domain_qa_assisted_v7r1.py`; `tests/test_rag_domain_qa_assisted_v7r1.py`; the 50-passage manifest; separate V7R1 raw/accepted/rejected JSONL; and the V7R1 contract, generation, comparison, and audit reports. No V7R0 artifact was overwritten.
