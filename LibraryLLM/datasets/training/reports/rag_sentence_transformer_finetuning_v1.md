# LuminaR controlled bi-encoder pilot — 2026-09-27

**EXPERIMENTAL ONLY — DRAFT EVALUATION LABELS. No production deployment.**

## Decision

Stop at pilot. The unchanged MiniLM baseline (A) was reproduced exactly. A bounded generic NQ+SQuAD pilot (B) trained and evaluated on DEV, but its raw dense Hit@50 and span Recall@50 each fell by one of 29 evaluable DEV questions. Its dense-preserving union reached the same DEV full-pool scores as A. No source-grounded, answer-verified LuminaR domain QA set or safe hard-negative set exists yet, so the required pilot gate for C, D, and scaled training is not met. The 20-passage domain-generation probe yielded zero formatted, answer-verified pairs and included ambiguous/unsupported questions. **No model should be promoted.**

## Controls and environment

- Python environment: torch 2.11.0+cu128; transformers 5.15.1; datasets 5.0.0; sentence-transformers 5.6.0; accelerate 1.14.0.
- Hardware: 16,438,054,912 bytes RAM; NVIDIA GeForce RTX 5060 Laptop GPU, 8,546,484,224 bytes VRAM. BF16 support was probed and is available.
- Initial D: free: 64,016,429,056 bytes. Initial training workspace: 607,180 bytes; HF cache and training-model folder were empty. External dataset cache was explicitly directed to `datasets/training/hf_cache`. After the probe, that cache used about 1.10 GB, including FLAN-T5-Base for the failed domain QA probe. The trained B pilot model uses 91,601,584 bytes.
- Frozen control: 16,895 chunks, 18 source books, `tokens_220`, 384-dimensional normalized vectors, `faiss.IndexFlatIP`. `chunks.parquet` SHA-256 `c41cd28eb870ab318c67ffbb7071748a95c5f76ce5af84ea2d898636ae8bc57f`; `mapping.json` `3775242485e1bf852b015adfc6ad55b5a7fa058c3a743ffc1c3d574d6d8d940d`; `manifest.json` `edec2e8b24f16a3dec22a222e625619bd12bfac1e697858f02d66611437b55d7`; source map `96d5ed1627b82f8450d00fd514ec57656870e04c06364b2c92344d30b46fbc4b`; DRAFT labels `fed44ff900e1a141afb129706106ee625c9b27e033ec5ccb4776ab341a1c9143`. All 18 per-book source hashes are saved in `../manifests/control_v1.json`. All manifest checks passed. The chunks were not rebuilt.
- Baseline A rerun: full 49-evaluable-question MRR 0.19505, Hit@1 8.16%, @3 22.45%, @5 32.65%, @10 42.86%, @20 55.10%, @50 65.31%; span Recall@20 54.08%, @50 63.27%; 17/49 no accepted span in Top50. Every Top50 chunk ID, in order, matched the previous saved run. This reproduction includes TEST only as the already-established control; model B was evaluated on DEV only.
- Production safety: the 64-file production hash snapshot in the previous chunking report still matches byte-for-byte. No production model setting, active chunks, active RAG/FAISS index, catalogue book, evaluation question, accepted span, or TEST book was changed. The original `tokens_220/dense_evaluation.json` was regenerated for baseline reproduction; its metrics/rankings remained identical.

## Data preparation and leakage

| Source | Inspected | Accepted pilot pairs | Saved artifact | Quality checks |
|---|---:|---:|---|---|
| Natural Questions train, streaming | 6,056 | 2,000 | `../processed/nq_pairs_v1.parquet` | 4,056 rejected by answer/context/window converter; none duplicate/exact eval query |
| SQuAD train, bounded cached load | 1,000 | 1,000 | `../processed/squad_pairs_v1.parquet` | all 1,000 passed annotation/span converter |

Both converters retained the annotated answer, used bounded passages of 15–220 model tokens, checked token counts, and saved source IDs, answer text, source metadata, and provenance. SQuAD rows were chosen by seed 42 from train; NQ used the first 2,000 accepted streaming rows, with an inspection cap of 15,000. Training can resume from local Parquet without re-streaming. The deterministic 100-row sample from each source is in `rag_generic_training_data_review.json`; automated checks across all 3,000 found no empty/duplicate pairs, missing answer, residual HTML markup, invalid token counts, or query string with ≥0.85 similarity to a DRAFT evaluation question. A human semantic review of all 200 sampled pairs remains outstanding; automated answer containment alone is not proof of full QA quality. Spot inspection found some noisy NQ infobox-style passages.

NQ source is [Google Research Natural Questions](https://huggingface.co/datasets/google-research-datasets/natural_questions); Google's [NQ data documentation](https://github.com/google-research-datasets/natural-questions/blob/master/nq_open/README.md) states CC BY-SA 3.0 for the data. [SQuAD's dataset card](https://huggingface.co/datasets/rajpurkar/squad) states CC BY-SA 4.0. The FLAN-T5-Base probe model is [Apache-2.0](https://huggingface.co/google/flan-t5-base); its generated text was not admitted as training data. These are provenance records, not a conclusion about downstream redistribution rights for book text.

Protected TEST work IDs, derived from the frozen evaluation file: `OL15933082W`, `OL27471326W`, `OL42479046W`, `OL44512357W`. The domain split plan has 12 train books and two validation books (`OL17494673W`, `OL2772007W`), with no TEST overlap. Of 16,895 frozen chunks, 3,573 TEST chunks and 69 chunks overlapping DRAFT accepted spans were excluded; 12,196 TRAIN and 1,057 VALIDATION chunks remain eligible source material. Their source hashes match the control manifest. A 12-word-shingle check found no overlap between the 3,000 generic positive passages and TEST-book chunks. Reports: `rag_training_decontamination_v1.json` and `rag_generic_test_leakage_v1.json`. No domain training examples or negatives were admitted. Therefore domain query/paraphrase decontamination and negative false-positive review remain unproven, and the domain gate is closed.

## Pilot B and retrieval comparison

B started from the exact locally cached `sentence-transformers/all-MiniLM-L6-v2`, kept max sequence length 256 and 384 dimensions, and used `SentenceTransformerTrainer` with `MultipleNegativesRankingLoss(query, positive)`. The loss received **no explicit hard-negative column**, appropriate only for generic B; this does not satisfy the domain C/D loss requirement. Seed 42, BF16, batch 8, no gradient accumulation, 60 steps, AdamW, learning rate 2e-5, linear scheduler, six warmup steps, weight decay 0.01, no-duplicate batching. Two checkpoints were saved. Training took 8.28 seconds; loss 0.03477; peak torch GPU allocation 553,420,288 bytes. Save/reload succeeded with finite, normalized 384D output. The full hyperparameter manifest is `../manifests/minilm_generic_pilot_v1.json`.

An isolated B index embedded all 16,895 unchanged chunks in 25.50 seconds. It contains 18 book-scoped `IndexFlatIP` indexes and one global index, all normalized, under `../evaluation_indexes/minilm_generic_pilot_v1`. Peak build process RSS was 1,628,794,880 bytes; peak torch GPU allocation 222,790,144 bytes. No production index was replaced.

| Raw dense DEV (29 evaluable DRAFT questions) | A unchanged | B generic pilot |
|---|---:|---:|
| MRR | 0.1653 | 0.1777 |
| Hit@1 | 6.90% | 10.34% |
| Hit@3 | 17.24% | 17.24% |
| Hit@5 | 24.14% | 24.14% |
| Hit@10 | 34.48% | 34.48% |
| Hit@20 | 48.28% | 48.28% |
| Hit@50 | **65.52%** | **62.07%** |
| Span Recall@20 | 46.55% | 46.55% |
| Span Recall@50 | **62.07%** | **58.62%** |

Across DEV: seven first accepted ranks improved, seven regressed, 15 were unchanged; zero queries were recovered into Top50, and one was lost. Per-query ranks and candidates are in `minilm_generic_pilot_dev_v1.json` and the isolated index's `dense_dev_evaluation.json`. B query encoding mean 13.05 ms, FAISS mean 0.15 ms, total mean 13.20 ms (30 DEV queries, including first-use effects). The unchanged reranker was not tested, because raw dense gain was not established. The B model was **not** evaluated on protected TEST; no TEST result is claimed.

The dense-preserving union retained B's exact Top50 in order and added expansion candidates up to 80. On DEV, B full-pool hit rose from 62.07% to 72.41% and span recall from 58.62% to 68.97%. Baseline A union on the same DEV subset also reached 72.41% hit and 68.97% recall. B provides no observed union gain. Details: `minilm_generic_pilot_union_dev_v1.json`.

## Pilot gate and next action

The 20-passage FLAN-T5-Base probe sampled eligible non-TEST, non-evaluation-overlap chunks. It produced question-only outputs rather than the required question-plus-evidence format: 0/20 parsed answers and 0/20 answer-visible verified pairs. Examples included “What is the title of the passage?” and “What is the relationship between De Bourgh and De Bourgh?”, which do not establish useful source-grounded retrieval labels. The probe is saved in `domain_qa_generation_probe_v1.json` and was **not** used for training.

Pilot acceptance: NQ streaming, SQuAD preparation, local Parquet, TEST exclusion, corpus integrity, generic model training, checkpoint reload, 384D normalized IndexFlatIP, and DEV evaluation passed. LuminaR domain QA generation/verification, domain query decontamination, safe hard-negative mining, and proof that explicit negatives reach the loss did **not** pass. Thus C and D pilots, all scaled B/C/D runs, TEST model comparison, and production deployment were not performed. This is a **data-quality gate**, not a GPU or disk failure. The next step is to create a small, human-reviewed source-grounded LuminaR QA set from eligible TRAIN books, validate its category mix and answers, then mine and independently reject false negatives before any domain pilot. Revisit scaled training only after all pilot gates pass. Independent review of DRAFT evaluation labels is also needed before model selection.

## Verification and artifacts

- `pytest` focused RAG suite: 14 passed, 0 failed.
- Control SHA-256 checks and exact baseline rank reproduction passed.
- Generic TEST 12-word-shingle leakage check passed; domain train/validation/TEST work IDs and source hashes are disjoint.
- Production snapshot: 64/64 files unchanged.
- New code: `scripts/prepare_rag_finetuning_data.py`, `scripts/audit_rag_generic_pairs.py`, `scripts/audit_rag_domain_pool.py`, `scripts/audit_rag_training_leakage.py`, `scripts/train_rag_biencoder_pilot.py`, `scripts/evaluate_rag_finetuning_pilot.py`, `scripts/evaluate_rag_pilot_union.py`, `scripts/probe_rag_domain_qa.py`, and `tests/test_rag_finetuning_prep.py`. `scripts/evaluate_rag_chunk_variants.py` gained optional isolated-index/output arguments without changing its default behavior. The workspace `../README.md` documents the gate. No failure was hidden or scored as a successful domain result.
