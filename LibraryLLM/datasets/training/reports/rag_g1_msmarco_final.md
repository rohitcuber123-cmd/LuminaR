# G1_MS_MARCO — final controlled-pilot report

**Decision: C. MS MARCO G1 REGRESSES LUMINAR RETRIEVAL.** The primary DEV first-stage recall measures all declined. These are **experimental/descriptive** results because the LuminaR DEV labels are DRAFT. Protected TEST was **not evaluated**. Stop after G1; no other dataset or model-training phase was started.

## Scope, source, and data quality

- Model A: unchanged `sentence-transformers/all-MiniLM-L6-v2`. G1: that model trained only on bounded MS MARCO text triplets. No NQ, SQuAD, GooAQ, BEIR, LuminaR domain examples, Qwen training, or cross-encoder training.
- Source: [`sentence-transformers/msmarco-co-condenser-margin-mse-sym-mnrl-mean-v1`](https://huggingface.co/datasets/sentence-transformers/msmarco-co-condenser-margin-mse-sym-mnrl-mean-v1), configuration `triplet`, revision `84ed2d35626f617d890bd493b4d6db69a741e0e2`; schema is three strings: `query`, `positive`, `negative`. The source's `triplet` configuration supplies a mined, most-query-similar hard negative for each query–positive pair. The preferred `triplet-hard` configuration was probed first but a bounded 50k shuffled sample contained only 2,054 distinct queries and produced 1,585 train/validation query overlaps. That probe was isolated and not trained on. The `triplet` configuration yielded 50,000 unique queries.
- Hugging Face was probed and streamed automatically; no manual download or full corpus download. Cache: `datasets/training/hf_cache/`. A first local preparation attempt could not find the base tokenizer in this isolated cache; rerunning with the already-cached base model snapshot succeeded. There was no blocking network or dataset-schema issue.
- Deterministic bounded sampling: streaming shuffle seed 42, buffer 10,000; inspect until 50,000 usable rows; second seed-42 shuffle; first 45,000 TRAIN, last 5,000 generic validation. This is not a globally uniform sample of the entire source.
- Raw rows inspected: 68,822. Rejected for `positive == negative`: 18,822. Selected: 50,000. Selected exact duplicate triplets: 0; duplicate queries: 0; duplicate positives: 301; positive-equals-negative: 0; train/validation query overlap: 0. All selected fields were nonempty and within the preparation text-length bounds.
- Token lengths under the unchanged MiniLM tokenizer (min / median / p90 / p95 / p99 / max; count over 256): query `4 / 9 / 12 / 14 / 18 / 70; 0`, positive `11 / 73 / 130 / 146 / 182 / 326; 11`, negative `8 / 67 / 112 / 130 / 165 / 275; 2`. The few over-window passages are truncated by the unchanged 256-token model limit.
- TRAIN Parquet SHA-256: `7fb3fc0802a11efc3cf4b54be71509d36bbea3fc6bf3aa258c16d98ad22b6c16`; validation Parquet SHA-256: `7e34e6325b220155d970192d63d902a8a1d67770f6ef8b4efb77260f2cd7d4a3`. Full source, selection, timestamp, schema, versions, and quality data: `datasets/training/generic/msmarco_g1/manifest.json`.

## Environment and training

- Measured preflight: Python 3.11.9; PyTorch 2.11.0+cu128; Transformers 5.15.1; `datasets` 5.0.0; Sentence Transformers 5.6.0; Accelerate 1.14.0; FAISS 1.14.3. CUDA and BF16 supported on RTX 5060 Laptop GPU. Total VRAM 8,546,484,224 bytes; free before training preflight 7,385,120,768 bytes. System RAM 16,438,054,912 bytes; initially available about 3.57 GB, later about 8.2 GB. Disk free before preparation 61,876,359,168 bytes.
- Chosen loss: `MultipleNegativesRankingLoss` with `(anchor=query, positive, negative)`. The installed implementation concatenates positive and explicit negative document embeddings into the loss candidate matrix. A focused synthetic test verified the collator retained `negative_input_ids`, the trainer supplied all three feature groups, and changing the negative changed the computed loss; 1 test passed. `BatchSamplers.NO_DUPLICATES` was used. `CachedMultipleNegativesRankingLoss` was available but unnecessary because the ordinary physical batch of 16 left ample VRAM headroom.
- Seed 42; 1 epoch; learning rate `2e-5`; weight decay `0.01`; linear schedule; 0.05 warmup ratio; physical batch 16; effective contrastive batch 16; gradient accumulation 1; BF16 enabled, FP16 disabled. Each query has its explicit negative plus in-batch candidates. Gradient accumulation was **not** claimed to enlarge the in-batch negative pool. Original 384-dimensional architecture, pooling, tokenizer, and 256-token window were retained; retrieval normalization was retained.
- Smoke training: 1,024 triplets, 64 steps, finite loss 1.458337; forward/backward, save/reload, and encode passed. Peak reserved VRAM 1,203,765,248 bytes; minimum global free VRAM 6,139,412,480 bytes.
- Full training: 45,000 triplets, 2,813 steps, 364.02 seconds, final training loss 0.916193. Peak reserved VRAM 1,344,274,432 bytes; peak allocated VRAM 1,205,663,744 bytes; minimum global free VRAM/headroom 5,996,806,144 bytes; peak process RSS 2,277,363,712 bytes. Saved model reloaded and encoded successfully.
- Final G1 model: `datasets/training/models/minilm_g1_msmarco_50k_full/`; `model.safetensors` SHA-256 `18b51b15c248916dce4e99532796edbbb0de0322827ad9fe1bb1b7ec90d1ec1f`. The model, dataset hashes, configuration, duration, and resource peaks are in `datasets/training/manifests/minilm_g1_msmarco_50k_full.json`.

## Frozen-corpus indexing and DEV comparison

- Baseline A was reproduced **before** training on frozen `tokens_220`: the saved Top-50 chunk IDs matched the historical DEV result exactly for every query. Both A and G1 use original queries and dense-only, normalized 384-dimensional embeddings with per-book FAISS `IndexFlatIP`; no expansion, lexical retrieval, union, reranker, or answer LLM.
- G1 encoded the same 16,895 chunks from 18 books to shape `(16895, 384)`; L2 norms ranged from `0.9999998808` to `1.0000001192`. Isolated global `IndexFlatIP` count: 16,895; per-book indexes: 18. Global index SHA-256: `060fc0392cb471d4648d872242a0cf9aa9ef6492d450d9c235e30c91f44c50f6`. Index manifest: `datasets/training/evaluation_indexes/minilm_g1_msmarco_50k/manifest.json`.
- DEV contains 30 questions, 29 evaluable under the frozen labels. **No protected TEST evaluation** was performed.

| Metric | Baseline A | G1 | Change |
|---|---:|---:|---:|
| MRR | 0.1653 | 0.1096 | −0.0557 |
| Hit@1 | 6.90% | 3.45% | −3.45 pp |
| Hit@3 | 17.24% | 10.34% | −6.90 pp |
| Hit@5 | 24.14% | 17.24% | −6.90 pp |
| Hit@10 | 34.48% | 24.14% | −10.34 pp |
| **Hit@20** | **48.28%** | **37.93%** | **−10.35 pp** |
| **Hit@50** | **65.52%** | **51.72%** | **−13.79 pp** |
| Recall@5 | 24.14% | 17.24% | −6.90 pp |
| Recall@10 | 34.48% | 24.14% | −10.34 pp |
| **Recall@20** | **46.55%** | **37.93%** | **−8.62 pp** |
| **Recall@50** | **62.07%** | **50.00%** | **−12.07 pp** |
| **No accepted span in Top-50** | **10** | **14** | **+4** |

The first relevant rank improved on 5 queries, regressed on 13, and was unchanged on 11. Zero previously missed queries were recovered in Top-50; four previously found queries lost all accepted spans from Top-50. Those losses span four books, so the observed decline is not attributable to a single work:

| Query | Work | Question | A accepted-span rank(s) | G1 accepted-span rank(s) | Diagnostic |
|---|---|---|---|---|---|
| `v8_08` | Dracula (`OL85892W`) | What ship transported Dracula to England? | 46, outside Top-50 | both outside Top-50 | The accepted _Demeter_ passage leaves Top-50; top results discuss Dracula's other voyages/boats. |
| `v8_10` | Frankenstein (`OL45326637W`) | What happens when Victor first sees the creature? | 23, 13 | both outside Top-50 | The eye-opening/animation scene disappears; top results emphasize other monster-related scenes. |
| `alice_04` | Alice's Adventures in Wonderland (`OL38619874W`) | Who tells Alice that everyone there is mad? | 2 | outside Top-50 | The Cat's “we're all mad here” passage is displaced by other Alice dialogue. |
| `time_02` | The Time Machine (`OL27039837W`) | What is the name of the Eloi woman who befriends the Time Traveller? | 50 | outside Top-50 | The passage naming Weena drops out; top results mention the Time Traveller but not her introduction. |

The per-query JSON includes all 29 movement classifications, both models' accepted-span ranks, and the top nearby passages for every lost/recovered case. See `datasets/training/reports/rag_g1_msmarco_eval.json` and the readable passage excerpts in `datasets/training/reports/rag_g1_msmarco_eval.md`. The 13-versus-5 regression count and four lost books support a broad directional decline in this small DEV sample, not a claim of statistical generalization.

## Generic validation, artifacts, and safety

- Generic 5,000-row held-out MS MARCO sanity: pairwise query–positive versus query–negative cosine accuracy rose from **24.04% (A)** to **52.76% (G1)**; mean positive-minus-negative cosine margin rose from `−0.06259` to `+0.00425`. This confirms the trained model moved in the intended direction on the sampled generic task while LuminaR DEV retrieval regressed. It is not a full-corpus ranking evaluation and cannot override the LuminaR first-stage recall decision. Machine-readable result: `datasets/training/reports/rag_g1_msmarco_generic_validation.json`.
- New experiment scripts: `scripts/prepare_msmarco_g1.py`, `scripts/train_msmarco_biencoder_g1.py`, `scripts/build_rag_g1_index.py`, `scripts/evaluate_rag_g1.py`, `scripts/evaluate_msmarco_g1_validation.py`. Focused test: `tests/test_msmarco_g1_training.py`. New isolated artifacts: the G1 data and unused `triplet-hard` probe folders, G1 smoke/full model folders, G1 evaluation index folder, G1 manifests, and G1 reports. No prior generic-pilot artifacts or production files were overwritten.
- The before-and-after SHA-256 audit of **64** snapshotted production files found **0 changed** files. Frozen `tokens_220/chunks.parquet` and evaluation-label hashes still match `datasets/training/manifests/control_v1.json`. No changes to production model/index/retriever/reranker/LLM/catalogue/Mongo/CRUD behavior. TEST evaluated: **NO**.

**Final G1 decision: C. MS MARCO G1 REGRESSES LUMINAR RETRIEVAL.** Do not promote G1 to production or proceed to another training dataset without user review.
