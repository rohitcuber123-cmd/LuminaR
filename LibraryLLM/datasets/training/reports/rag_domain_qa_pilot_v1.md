# LuminaR domain QA pilot preparation — 2026-09-27

**RESULT LABEL: EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS**

**FINAL DECISION: D. DOMAIN DATA QUALITY GATE NOT MET — DO NOT TRAIN.**

The frozen 220-token corpus and protected book split remain intact. A locally cached Qwen2.5-3B-Instruct model was tested after FLAN-T5-Base failed, but its questions still failed source-first semantic review. The first bounded Qwen attempt produced 32 mechanically valid candidates from 79 attempts, reused 11 source chunks, and had unsupported premises/category errors. A stricter attempt prevented source reuse and produced 10 mechanically valid candidates from 20 attempts; assistant source inspection found none ready to mark REVIEWED as-is. Mechanical answer containment did not prove the question was answerable. Generation stopped rather than expanding weak data to the requested quota.

## 1–10. Passage and QA audit

The frozen `tokens_220` corpus has 16,895 chunks. The passage filter and source verification classified them as follows:

| Classification | Chunks |
|---|---:|
| Protected TEST | 3,573 |
| Evaluation-span overlap | 69 |
| GOOD_FOR_QA heuristic | 12,783 |
| WEAK_CONTEXT | 152 |
| BOILERPLATE | 88 |
| TOO_AMBIGUOUS | 225 |
| TOO_SHORT | 3 |
| MALFORMED | 1 |
| DIALOGUE_FRAGMENT_WITHOUT_CONTEXT | 1 |
| HEADER_ONLY | 0 |

The `GOOD_FOR_QA` label means a passage survived coarse filtering, **not** that it yields a valid QA pair. There are 11,748 such TRAIN chunks and 1,035 VALIDATION chunks. The classifier checks source-hash/text/offset integrity, length, OCR damage, boilerplate, sentence structure, and named detail. [Passage-quality report](rag_domain_passage_quality_v1.json) records counts and book distribution.

The first Qwen attempt generated 79 raw outputs and admitted 32 only to an AUTO_VALIDATED diagnostic file; it was stopped after a source spot check found duplicate source use (11 repeated chunks), unsupported question premises, and misclassified question types. Those files were retained as rejected probes under `domain_qa_attempts_rejected_probe_v1.jsonl` and `domain_qa_candidates_rejected_probe_v1.jsonl`.

The refined attempt required a specific source sentence with a named detail, withheld book title from generation, supplied evidence verbatim from the source, limited category shape, and prevented chunk reuse. It generated 20 raw attempts and 10 AUTO_VALIDATED diagnostic candidates before stopping. Automatic rejection reasons were category/question mismatch 6, unresolved pronoun 2, answer absent from evidence 2, and bad question length/format 1 (an attempt can have multiple reasons). The 10 candidates have no repeated source chunk. [Generation audit](rag_domain_qa_generation_v1.json) includes all counts and assistant spot findings.

The 10 diagnostic candidates span FACTUAL_DIRECT 2 and one each of ENTITY_RELATION, EVENT, MOTIVATION, CAUSAL, LOCATION, TEMPORAL, SEMANTIC_PARAPHRASE, and QUOTE_OR_PHRASE. All ten self-declared EASY; these labels are **not reviewed**. Concrete failures include `DQ00004` asking who the magistrate selected and answering “Daniel Nugent,” although the passage names him as the selected witness's brother-in-law; `DQ00007` giving “before)” as a temporal answer; and `DQ00008` asking why someone came while the evidence never states the purpose. The remaining candidates need rejection or edits for vague referents, incomplete answers, weak retrieval value, or unsupported premises. No candidate is counted as human-approved.

The source-first [QA review packet](rag_domain_qa_review_v1.md) shows every diagnostic candidate, positive passage, evidence quote, answer, category, difficulty, source offsets, and warnings, without retriever ranks. Its [CSV decision sheet](../luminar/domain_qa_review_v1.csv) supports APPROVE, REJECT, and EDIT plus a named reviewer and ten YES checklist fields. `finalize_rag_domain_qa.py` rechecks source hashes, offsets, evaluation-query similarity, evidence, and edits before assigning REVIEWED. The current sheet is blank: **0 approved, 0 rejected, 0 edited, 10 unreviewed; 0 REVIEWED TRAIN and 0 REVIEWED VALIDATION.** The packet is diagnostic and should not be bulk-approved.

## 11–22. Split, negatives, and decontamination

TRAIN contains 12 books: `OL27039837W`, `OL28944494W`, `OL33027136W`, `OL33723557W`, `OL35758281W`, `OL36979234W`, `OL38619874W`, `OL41470186W`, `OL43032614W`, `OL45326637W`, `OL66524W`, `OL85892W`. VALIDATION contains `OL17494673W` and `OL2772007W`. Protected TEST, derived again from the evaluation JSON, contains `OL15933082W`, `OL27471326W`, `OL42479046W`, `OL44512357W`. The sets are disjoint. All QA prompts and candidates used TRAIN chunks only; source files, normalized hashes, source offsets, and frozen chunk text were checked. The 69 chunks overlapping any accepted DRAFT evaluation span were excluded from generation. Candidate queries are screened against exact and near-duplicate evaluation questions. No TEST passage entered prompts, positives, negatives, or validation examples.

Hard-negative mining was **not run**: it correctly refused to proceed without reviewed QA. Therefore negative candidates mined, VALID_NEGATIVE, FALSE_NEGATIVE, UNCERTAIN, and negatives per query are all **zero/not applicable**. The review-only miner is implemented to search baseline same-book Top20 and reject positive/evidence overlap, near-source chunks, answer-text containment, ineligible chunks, and non-TRAIN books. Proposed negatives would then need a separate [negative review packet script](../../../scripts/render_rag_negative_review.py) and VALID/FALSE_NEGATIVE/UNCERTAIN CSV decisions; only VALID with reviewer and checklist could enter a gated training Parquet. This safety logic has a focused test. No negative review packet or training Parquet was fabricated.

Domain decontamination removed protected TEST books and evaluation-span-overlap chunks before generation, checked source hash/offsets, screened generated queries against evaluation questions, and checked the book split again at the pilot gate. The [pilot gate](rag_domain_pilot_gate_v1.json) passes frozen corpus, unchanged production snapshot, and TEST exclusion. It fails the required ≥200 REVIEWED TRAIN QA, ≥40 REVIEWED VALIDATION QA, reviewed valid negatives for each query, negative safety review, and gated training file. The strict source controls and Qwen attempt/rejection logs are preserved for audit.

## 23–31. Training and retrieval status

SentenceTransformers 5.6.0 `MultipleNegativesRankingLoss` accepts `query`, `positive`, and an explicit `hard_negative` as separate embedding inputs; the installed implementation concatenates all document columns into the candidate matrix. A synthetic unit test verifies that the collator retains the negative column and adding it changes the contrastive loss. This is **proof of supported plumbing, not a C training run**. No domain loss, checkpoint, hyperparameters, duration, RAM/VRAM peak, model C, C DEV score, per-query C analysis, or C candidate union exists. Model D is outside this task and was not run.

For comparison only, unchanged A on DEV's 29 evaluable DRAFT questions remains MRR 0.1653; Hit@1 6.90%, @3 17.24%, @5 24.14%, @10 34.48%, @20 48.28%, @50 65.52%; span Recall@10 34.48%, @20 46.55%, @50 62.07%; no accepted span in Top50 for 10/29. Generic pilot B previously reached Hit@50 62.07% and Recall@50 58.62%; it did not justify scaling. C has no results and must not be compared as if trained.

## 32–36. Files, checks, safety, decision

Added isolated domain-preparation and review scripts under `scripts/`: `rag_domain_common.py`, `audit_rag_domain_passages.py`, `probe_qwen_domain_qa.py`, `build_rag_domain_qa_candidates.py`, `render_rag_domain_qa_review.py`, `finalize_rag_domain_qa.py`, `summarize_rag_domain_qa_candidates.py`, `mine_rag_domain_hard_negatives.py`, `render_rag_negative_review.py`, `finalize_rag_hard_negatives.py`, and `check_rag_domain_pilot_gate.py`; plus focused tests under `tests/`. Artifacts live only under `datasets/training/`. No production RAG chunks/indexes/retriever/model/reranker, catalogue search, Mongo, lexical sidecar, evaluation labels, or generic training pairs were changed. The earlier 64-file production hash snapshot remains unchanged and frozen control hashes match.

The focused domain tests passed, including exact evidence/offset validation, disjoint TEST split, negative rejection, and proof an explicit negative reaches the loss. Running the miner and gate checker with zero reviewed examples produced their expected closed-gate results. No scaled B, C, D, LLM fine-tuning, reranker fine-tuning, or TEST model evaluation was attempted.

**Next:** obtain a genuinely source-reviewed set of specific, answerable literary QA with 200 REVIEWED TRAIN and at least 40 separate REVIEWED VALIDATION examples. Rework generation or author questions directly from source; the current diagnostic candidates should be edited or rejected, not bulk-approved. Only then mine and review hard negatives, create the gated Parquet, and run a short C pilot on DEV. Do not proceed to D automatically.
