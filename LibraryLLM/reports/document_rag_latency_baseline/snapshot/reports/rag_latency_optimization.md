# LuminaR RAG Latency Optimization

## Executive Summary

The exact Huckleberry Finn summary request improved from **73.19 s to 6.10 s** (91.7% faster). All requests use real local Qwen, retrieval, source attribution and scoped evidence.

## Baseline

Three unmodified HTTP requests: 80.55 s, 68.67 s, 70.35 s.
The first is the first observed request on an already-running service. Model startup is separate. Detailed original-kernel profiles are in `rag_latency_thread_sweep.json`.

## Bottleneck Analysis

| Stage | Baseline ms | Share |
|---|---:|---:|
| intent_analysis | 16913.37 | 23.13% |
| retrieval | 320.35 | 0.44% |
| fast_filter | 3.87 | 0.01% |
| validation | 10084.56 | 13.79% |
| generation | 45783.65 | 62.62% |

## Optimization Changes

- Reuse the immutable constrained-decoding tokenizer lookup; keep a fresh JSON parser per call.
- Use strict informational templates and a bounded cache containing only entity-free classifications. Arbitrary topics are not cached.
- Expand grouped K/V heads for CUDA SDPA on Windows builds without Flash Attention. Retain original SDPA for intent extraction after a measured regression.
- Use inference mode, retain deterministic decoding and KV caching.
- Fast-accept exact overview requests only with at least three substantial, uniquely identified passages from the selected book. No extra claims qualify.
- Share MiniLM with uploads and serialize GPU inference/index refresh. Upload work runs outside the event loop.
- Preserve seven evidence chunks and the original retrieval/scoring path after smaller-context experiments underperformed.

Measured ablations and rejected alternatives: `rag_attention_fixed_token_comparison.json`, `rag_latency_experiments.json`, `rag_latency_threshold_sweep.json`, `rag_latency_retrieval_sweep.json`, `rag_compute_dtype_comparison.json`, and `rag_latency_prompt_ablation.json`.

Each row below is its own measured experiment, not an additive speedup. Some experiments change answer length; the fixed-token attention comparison isolates kernel performance.

| Experiment | Before ms | After ms | Delta ms | Quality / decision |
|---|---:|---:|---:|---|
| Constrained-decoding tokenizer lookup reuse (warm summary) | 61042.7 | 38872.1 | -22170.6 | Same answer; immutable vocabulary reused, parser state remains fresh. **accepted** |
| Expanded K/V SDPA, fixed 20 generated tokens | 19938.2 | 4461.6 | -15476.6 | Fixed-token text identical. Expanded attention rejected for intent after a paraphrase regression; other uses require the final quality gate. **accepted for answer/validator only** |
| BF16 compute instead of FP16, fixed 20 tokens | 4443.9 | 3779.4 | -664.5 | Changed generated text; quality equivalence not established. **rejected** |
| CPU intra-op threads 1 | 61520.5 | 60314.1 | -1206.3 | No meaningful gain relative to run variation; default retained. **rejected** |
| CPU intra-op threads 4 | 61520.5 | 60194.7 | -1325.8 | No meaningful gain relative to run variation; default retained. **rejected** |
| Summary evidence chunks 7 to 4 | 15454.0 | 16885.2 | +1431.3 | Less context produced longer/worse answers; source breadth not qualified. **rejected** |
| Summary evidence chunks 7 to 3 | 15454.0 | 21453.7 | +5999.7 | Less context produced longer/worse answers; source breadth not qualified. **rejected** |
| Inference mode on the same summary path | 14725.5 | 11952.6 | -2772.9 | Same summary text observed; full final regressions reported separately. **accepted** |
| Compact prompt: What is the author of this book? | 2432.4 | 1696.9 | -735.4 | Input tokens 1366 to 982; output 11 to 11. Answers retained for review. **see final configuration and quality gate** |
| Compact prompt: What is this book about? | 12934.5 | 5747.8 | -7186.6 | Input tokens 5484 to 5100; output 80 to 36. Answers retained for review. **see final configuration and quality gate** |
| Compact prompt: What is the summary of this book? | 10783.0 | 6627.2 | -4155.8 | Input tokens 6098 to 5714; output 71 to 38. Answers retained for review. **see final configuration and quality gate** |
| Compact prompt: What are the major themes of this book? | 5286.9 | 5254.4 | -32.5 | Input tokens 931 to 931; output 17 to 17. Answers retained for review. **see final configuration and quality gate** |
| Compact prompt: Does this book discuss quantum computing? | 4382.1 | 4236.8 | -145.3 | Input tokens 832 to 832; output 13 to 13. Answers retained for review. **see final configuration and quality gate** |
| Compact prompt: What is an autoencoder? | 15401.7 | 7939.5 | -7462.2 | Input tokens 2271 to 1887; output 99 to 44. Answers retained for review. **see final configuration and quality gate** |

Additional scoped changes: metadata author acceptance retains real retrieval and generation; one attributed source replaces seven for that exact query. Overviews require three substantial, unique passages from the selected book. GPU serialization and shared upload embeddings are correctness/resource changes; isolated latency savings are not claimed for them.

Rejected answer-only soft repetition penalties caused longer, speculative answers (`rag_latency_prompt_ablation_rejected_answer_penalty.json`). The original soft penalty is retained; only the hard n-gram ban excludes source text so names remain copyable. Refusal generation uses one already-checked passage after validation examines the full selected evidence.

## Before vs After

| Exact summary query | Mean seconds |
|---|---:|
| Original | 73.19 |
| Final | 6.10 |

## Book Query Latency

| Question | Mean seconds | Three runs, seconds |
|---|---:|---|
| What is the author of this book? | 1.76 | 1.91, 1.69, 1.68 |
| What is this book about? | 5.76 | 5.76, 5.76, 5.76 |
| What is the summary of this book? | 6.10 | 6.05, 6.05, 6.21 |
| What are the major themes of this book? | 4.74 | 4.72, 4.68, 4.82 |
| Does this book discuss quantum computing? | 4.21 | 4.10, 4.26, 4.29 |

## PDF Query Latency

Real indexed autoencoder notes: **7.77 s** mean. Individual results and sources are in `rag_latency_pdf_final.json`.

## Intent Latency

Final measured mean: **0.05 ms** across the book/PDF benchmark.

The difficult frozen 64-case suite changed from 11011.7 to 6841.6 ms mean. No intent LLM was needed for 34.4% of that suite and 100.0% of the six normal benchmark query patterns. The generic cache does not cache retrieved evidence or answers.

## Retrieval Latency

Final measured mean: **0.10 ms** across the book/PDF benchmark.

| Candidate count | Full retrieval/rerank ms | Top-1 % | Top-3 % |
|---|---:|---:|---:|
| 3 | 154.1 | 80.0 | 80.0 |
| 5 | 206.9 | 80.0 | 80.0 |
| 8 | 285.1 | 70.0 | 80.0 |
| 10 | 366.2 | 70.0 | 80.0 |
| 15 | 499.1 | 60.0 | 70.0 |

The small frozen retrieval set improves at lower counts, but it does not establish summary breadth or causal grounding. Separate smaller-context experiments made summaries slower/worse, so the normal path keeps 15 candidates and seven diverse passages. Scoped book indexes and LRU caching were already present; no new speedup is claimed for them.

## Reranking Latency

Final measured mean: **72.28 ms** across the book/PDF benchmark.

## Fast Filter Latency

Final measured mean: **1.50 ms** across the book/PDF benchmark.

| Actor/event thresholds | False accepts | False rejects | Validator calls / 42 |
|---|---:|---:|---:|
| 1.0/0.8 | 1 | 0 | 38 |
| 0.9/0.7 | 1 | 0 | 38 |
| 0.8/0.6 | 1 | 0 | 38 |
| 0.7/0.5 | 5 | 0 | 34 |
| 0.6/0.4 | 5 | 0 | 34 |

Lower thresholds save four validator calls but introduce four additional false accepts. Rejected. Original deterministic scoring and the two-field validator schema remain unchanged.

## Validator Latency

Final measured mean: **1173.69 ms** across the book/PDF benchmark.

## Generation Latency

Final measured mean: **3613.36 ms** across the book/PDF benchmark.

## GPU Utilization

All 434 Qwen parameter tensors were verified on CUDA. Resource samples record device-wide GPU utilization/memory and per-process CPU/RSS. Samples include idle periods; Windows WDDM does not expose reliable per-process VRAM through nvidia-smi. CUPTI hardware profiling was unavailable.

| Resource during final requests | Mean | Maximum |
|---|---:|---:|
| cpu_percent | unavailable | unavailable |
| rss_mb | unavailable | unavailable |
| gpu_util_percent | unavailable | unavailable |
| gpu_memory_mb | unavailable | unavailable |

Service model/index initialization: 21198.56 ms, measured separately from requests. CPU percent uses psutil's per-process scale (100% per logical core).

## Token Throughput

Mean measured answer throughput, including prefill: **7.63 tokens/s**. Validator call rate: **50.0%**. Actual input/output counts and limits are recorded per request.

## Quality Regression

| Metric | Frozen baseline | Final |
|---|---:|---:|
| intent_canonical | 100.000 | 100.000 |
| intent_paraphrased | 72.220 | 72.222 |
| intent_adversarial | 70.000 | 70.000 |
| intent_overall | 79.690 | 79.688 |
| intent_actor | 85.940 | 85.938 |
| intent_polarity | 89.060 | 89.062 |
| adversarial_validation | 88.100 | 88.095 |
| unsupported_premise_rejection | 94.590 | 94.595 |
| e2e_valid_groundedness | 56.522 | 43.478 |
| e2e_invalid_rejection | 55.556 | 77.778 |
| retrieval_top1 | 60.000 | 60.000 |
| retrieval_top3 | 70.000 | 70.000 |
| retrieval_mrr_proxy | 0.666 | 0.666 |

Measured regression: **YES**. The expanded-attention intent variant was rejected after losing one paraphrase case. Critical `rag/fast_filter.py` and `rag/evidence.py` remain byte-for-byte unchanged.

Replay coverage: 64 intent cases, 42 validator cases, 32 end-to-end cases; all 17 FAISS index/metadata integrity checks. Runtime checks passed: True; concurrent book/PDF requests remained isolated and serialized GPU work, with maximum health-response latency 185.3 ms.

## Error Analysis

- Baseline first request was observed on an already-running service, not a process-cold launch.
- GPU hardware traces were unavailable because CUPTI initialization failed; nvidia-smi samples were used.
- Frozen groundedness scoring is a keyword/verdict heuristic, not a proof of factual accuracy.
- A broad compact-prompt variant introduced an unsupported causal motive despite passing that heuristic. It was rejected; compact instructions are restricted to the tested informational grammar.
- Frozen MRR is a top-1/top-3 proxy; actual per-rank reciprocal scores are also preserved in the sweep.
- Initial HTTP parsing, book-filter loop and merge timings were not independently instrumented; no synthetic values are assigned.

Intent failures: para_03, para_06, para_12, para_19, para_20, para_21, para_22, para_23, para_31, para_32, adv_05, adv_07, adv_08. Validator failures: 4, 8, 19, 20, 38. These metrics must be compared with the frozen baseline, not interpreted as perfect accuracy.

End-to-end selected-document source isolation: True. End-to-end cases reaching the generation cap: [].

## Final Configuration

Local Qwen2.5-3B, NF4/double quantization, FP16 compute, CUDA; deterministic single-beam generation with KV cache. MiniLM and CrossEncoder remain on CUDA. Per-book FAISS LRU size 5. Intent classification LRU bound 128; only entity-free templates are retained. Frozen actor/event thresholds remain 0.8/0.6.

Normal: 15 candidates, 7 diverse evidence chunks (1 for source-verified author metadata), 320 maximum new tokens. Compact normal answers request at most 40 words only for the strict informational grammar; other questions retain V8's original prompt. All tested summary caps (128/192/256/320) completed identically; 320 retains headroom and the ordering above concise depth. The cap itself did not improve completed-answer latency. Concise/detailed/comprehensive depth limits remain 300/1000/1500. Context budget remains 24,000 characters.

Source changes:

- `rag/api.py`
- `rag/llm.py`
- `rag/qa.py`
- `rag/reranker.py`
- `rag/retriever.py`
- `rag/services/document_service.py`
- `rag/attention.py`
- `rag/decoding.py`
- `rag/query_types.py`
- `rag/telemetry.py`
- `scripts/benchmark_rag_latency.py`
- `scripts/regression_rag_latency.py`
- `scripts/ablate_rag_prompts.py`
- `scripts/rag_evaluation_server.py`
- `scripts/monitor_rag_resources.py`
- `scripts/check_rag_index_integrity.py`
- `scripts/check_rag_runtime.py`
- `scripts/sweep_rag_fast_filter.py`
- `scripts/rag_latency_lab.py`
- `scripts/rag_inference_experiments.py`
- `scripts/report_rag_latency.py`
- `tests/test_rag_attention.py`
- `tests/test_rag_decoding.py`
- `tests/test_rag_query_types.py`

Critical frozen files: `rag/evidence.py`, `rag/fast_filter.py`. Frontend `frontend/src/pages/LLMPage.tsx` and `frontend/src/lib/api.ts` were inspected and left unchanged. The requested `src/services/api.ts` path does not exist in this project.

## Remaining Bottlenecks

Real Qwen autoregressive decoding dominates the remaining latency. Longer answers require proportionally more time at the measured throughput. Context reduction and lower token caps are not assumed to preserve completeness.

## Recommendations

Use the measured normal-depth results as the service budget. Keep the frozen quality gate for future kernel, prompt or model changes. Re-run the benchmark after hardware/runtime changes; do not trade unsupported-premise rejection for a lower latency number.

Reproduce: `.venv\Scripts\python.exe scripts\benchmark_rag_latency.py`. Quality replay uses `scripts/regression_rag_latency.py` with the temporary single-model evaluation adapter; normal operation uses `rag.api:app`.
