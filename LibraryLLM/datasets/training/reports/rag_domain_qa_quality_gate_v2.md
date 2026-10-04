# LuminaR domain QA quality gate v2 — 2026-09-27

**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**

**Decision B. GENERATOR STILL PRODUCES SEMANTIC FAILURES — REVISE AGAIN BEFORE REVIEW.** The bounded pilot produced **zero AUTO_VALIDATED candidates** from 50 new TRAIN source attempts. Human review is **NOT YET COMPLETE** and the training gate is **CLOSED**. No model C or D training, negative mining, production change, or evaluation-label edit occurred.

## 1–3. Architecture and canonical record

The previous generator selected a source sentence, asked Qwen for a question/answer, and accepted a candidate if the answer string appeared in the evidence and a few format checks passed. That let an answer-bearing entity occupy the wrong semantic role. Its ten diagnostic candidates were never REVIEWED.

The v2 path first extracts a typed proposition from exact source evidence without asking a question. Only then does it select an `asked_slot`, derive `short_answer` from that slot, and ask for a question constrained by the proposition. The validator checks the source mapping and hash; evidence offsets; proposition fields; answer/slot equality; WH type; referents; direction, cause, time, and location; duplicates and evaluation similarity; and a separate semantic judge. It records `GENERATED`, `GROUNDING_FAILED`, `SEMANTIC_FAILED`, `AUTO_CHECKED`, or `AUTO_VALIDATED`. Human `REVIEWED` remains a separate decision. The canonical record stores work/book/chapter/chunk/source identifiers, passage, proposition and evidence offsets, asked slot, question, answer, answer type, proposed and validated category, difficulty, per-check outcomes, status, and reviewer fields. Rejected attempts retain source identifiers, raw model output, stage, codes, and a short reason.

The current model extractor is still unreliable: many outputs invent a relation type or choose roles unsupported by the exact sentence. The validator blocks those outputs, but this architecture alone does not make the generator ready for human review.

## 4–14. Grounding and semantic rules

The v2 passage classifier distinguishes `GOOD_FOR_QA`, weak or ambiguous context, short/header/index/table-of-contents material, publisher/copyright or other boilerplate, malformed text, and dialogue with unclear referents. It permits named, interpretable dialogue. TEST works and DRAFT evaluation-span overlaps are excluded before classification. Across 16,895 chunks it found 12,369 heuristically eligible, 3,573 protected TEST, 69 evaluation-span overlaps, and 884 other rejected chunks; see [passage audit](rag_domain_passage_quality_v2.json). The bounded run selected from the earlier frozen passage pool; a retrospective v2 classifier check found **all 50 selected chunks `GOOD_FOR_QA`**. The selector now uses the v2 classifier for any subsequent run. `GOOD_FOR_QA` remains heuristic, not a semantic approval.

Each v2 proposition has `subject`, `predicate`, `object`, a typed `relation_type`, optional cause/effect/location/time or relation endpoints and direction, and an exact evidence quote with authoritative normalized-source offsets. The asked answer must equal the stored slot; arbitrary containment in evidence is insufficient. The proposed and validated categories remain separately visible; a relation/category mismatch is rejected rather than silently reassigned. WHO requires a person-like answer, WHERE a location, WHEN a complete temporal expression, and WHY an explicit cause/effect pair with causal language. Direction metadata rejects FROM/TO, BEFORE/AFTER, and relation endpoint reversals. Answer checks reject dangling punctuation, trailing auxiliaries, empty or vague phrases, and type-incompatible spans. Query checks reject metadata questions, answer leakage in the question, generic wording, and unresolved forms such as “the man” or “the speaker.” The conservative referent rule can also reject a valid use of “that”; improving precision is future work, not a reason to weaken this pilot gate.

`SemanticEntailmentJudge` is an explicit interface. Deterministic rule entailment is available for exact rule/template propositions in synthetic tests. The bounded pilot used the already cached Qwen2.5-3B-Instruct as an additional JSON semantic judge, never as a substitute for failed deterministic checks. Invalid judge JSON becomes `UNCERTAIN`, not `ENTAILED`. No model was downloaded. There is no general symbolic claim-reconstruction parser; role equality and ordered source spans provide a narrower check. This is a material limitation for free-form literary sentences.

## 15–16. Read-only revalidation of the previous ten

[Old-batch JSON](rag_domain_qa_old_batch_revalidation_v2.json) and [Markdown](rag_domain_qa_old_batch_revalidation_v2.md) show **0 PASS, 10 FAIL**. All ten lack a stored proposition and therefore cannot be migrated to AUTO_VALIDATED. Generic additional codes were: unresolved referent 7, answer too vague 2, truncated answer 2, wrong proposition slot 1, answer-type mismatch 1, unsupported temporal relation 1, unsupported causal relation 1, unsupported premise 1, and overly generic question 1. These counts overlap. The wrong selected-witness role, malformed “before)” time answer, unsupported WHY premise, and clipped “Thornfield will” answer are caught by generic rules and synthetic tests, not candidate-ID exceptions. This does **not** mean all ten have been fully adjudicated by a human; several fail solely because the old format lacks a proposition.

## 17–22. New bounded pilot and rejection audit

The pilot used seed 42 and **50 distinct TRAIN chunks**, balanced over all 12 TRAIN books (four or five per book). It considered 12,783 eligible chunks from the previous passage pool; 4,112 of the frozen 16,895 were outside that pool, including protected TEST and evaluation-span exclusions. The 50 selected passages all pass the stricter v2 classifier. There were 48 extracted propositions, 2 proposition rejections, 48 generated questions, 26 grounding failures, 21 semantic failures, **1 AUTO_CHECKED**, and **0 AUTO_VALIDATED**. The sole AUTO_CHECKED item remained uncertain because the semantic judge returned invalid JSON; source inspection also shows ambiguous participant roles. There are therefore zero final review candidates.

| Category requested | Attempts | AUTO_VALIDATED |
|---|---:|---:|
| FACTUAL_DIRECT | 8 | 0 |
| ENTITY_RELATION | 7 | 0 |
| EVENT | 8 | 0 |
| MOTIVATION | 6 | 0 |
| CAUSAL | 6 | 0 |
| LOCATION | 4 | 0 |
| TEMPORAL | 4 | 0 |
| SEMANTIC_PARAPHRASE | 5 | 0 |
| QUOTE_OR_PHRASE | 2 | 0 |

The generated records were labeled EASY 24, MEDIUM 12, HARD 12, but **none of those difficulty labels belongs to an accepted candidate**. Dominant rejection codes were unresolved referent 34, category/relation mismatch 22, missing/invalid proposition 20, answer-type mismatch 12, source proposition slot absent 9, question containing its answer 8, answer too vague 6, unsupported causal relation 6, relation direction 6, and answer absent from evidence 5. Counts overlap. Duplicate rejection 0, evaluation-query leakage rejection 0, and TEST leakage 0. Zero here means no flagged collision in this small attempt set; it is not a sensitivity estimate for the checkers. [Generation audit JSON](rag_domain_qa_generation_audit_v2.json), [audit Markdown](rag_domain_qa_generation_audit_v2.md), and [independent revalidation](rag_domain_qa_validation_v2.json) retain the full distributions.

The v2 review packet [Markdown](rag_domain_qa_review_v2.md) and [CSV](rag_domain_qa_review_v2.csv) were rendered with **zero rows** because no candidate passed automatic validation. They deliberately contain no retriever ranks, similarity scores, or hard-negative proposals. Human review is NOT YET COMPLETE. The v2 finalizer was implemented but **not run**; it requires a named reviewer, valid date, all source-first checklist fields, full revalidation of edits, and a fresh semantic judgment for changed QA. An evidence edit requires an explicit replacement proposition and recalculated offsets; APPROVE alone cannot bypass checks.

## 23–29. Files, tests, safety, and gate

Added `scripts/rag_domain_qa_v2.py`, `build_rag_domain_qa_candidates_v2.py`, `validate_rag_domain_qa_candidates.py`, `audit_rag_domain_qa_candidates.py`, `rag_domain_qa_v2_review.py`, `render_rag_domain_qa_review_v2.py`, `finalize_rag_domain_qa_v2.py`, and `tests/test_rag_domain_qa_validator.py`; extended the shared passage-pool function to accept a classifier. Versioned data lives only under `datasets/training/luminar/` and `datasets/training/reports/`; the v1 packet remains untouched. The focused domain suite passed **41 tests, 0 failed**, including synthetic wrong-role, direction, WH-type, causality, truncation, referent, source-integrity, leakage, review-gate, and deterministic-seed cases. All new scripts compile.

The frozen corpus/manifest/mapping/evaluation-label controls pass. The protected TRAIN/VALIDATION/TEST book split remains disjoint. The production snapshot reports **0 changes across 64 files**. No production chunks, indexes, embedding model, retriever, reranker, LLM, catalogue semantic or lexical index, Mongo catalogue, evaluation questions, accepted evaluation spans, or protected TEST works were changed. No final hard negatives were mined; model C and D were not trained. The existing pilot gate remains closed with 0 REVIEWED TRAIN, 0 REVIEWED VALIDATION, and no reviewed negatives or training Parquet.

**Next engineering step:** improve proposition extraction and relation grounding using source clauses with explicit named participants, then run another separately versioned small pilot. Do not relax source/slot checks or scale generation to hide the zero-yield result. The current v2 packet has nothing suitable to send for human approval.
