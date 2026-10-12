# Metrics, baselines and measurement boundaries

## Retrieval metrics

For returned ranking R and relevant gold set G (grade>0), `Precision@k=|R[:k]∩G|/k`; report short lists and use the fixed k denominator for comparability. `Recall@k=|R[:k]∩G|/|G|`; when gold is pooled/incomplete label it **pooled recall**, not exhaustive catalogue recall. `HitRate@k=1` if any relevant result appears, otherwise 0. `MRR@k=1/rank(first relevant)` if rank≤k else 0. `DCG@k=Σ(2^grade_i−1)/log2(i+1)`; `nDCG@k=DCG/ideal DCG`. Define handling of no-relevant queries separately; report abstention/false positive results, not arbitrary perfect nDCG.

ANN fidelity is a different measure: `ANNRecall@k=|HNSW_k(q)∩ExactDense_k(q)|/k` on identical vectors/corpus. High ANN recall does not prove a good embedding space. RAG source-span recall counts distinct accepted gold spans covered by retrieved chunks; repeated overlapping chunks must not inflate it. `rag/evaluation/metrics.py:overlaps/evaluate_query` uses ≥80% span coverage and ≥min(40,span length) overlapping characters; freeze this definition and report sensitivity.

Latency: mean, median/p50, p95, optional p99, standard deviation, failure/timeout fraction. Query embedding, graph search, Mongo hydration, cross-encoder, evidence/validation, generation and network/client time are distinct. Throughput is successful requests/time at stated concurrency; do not infer it by inverse single-query mean under serialized generation. Build time, insertion/update/deletion publication time, time-to-searchable, cold load, RSS, peak rebuild RSS and disk bytes quantify maintenance cost.

## RAG and isolation metrics

Correctness, groundedness, relevance, completeness and source consistency use blinded 0–2 rubric in 12. Add unsupported-claim fraction, false-refusal rate over answerable questions, unsafe-answer rate over unanswerable questions, citation entailment/coverage, and token counts. A `SUPPORTED` backend verdict is a prediction, not a gold label.

Future `CrossLibraryLeakageRate = wrong-or-unauthorized-library returned resources / all returned resources`. Zero denominator must be reported as no results, not proof of isolation. Track violating queries/total queries and incorrect source objects independently; answer-level scope compliance requires all supporting sources belong to allowed context. A generated fact may come from model memory, so source-only inspection cannot prove all answer content is isolated. Record IDs/library/generation through the whole trace and human-check answers against authorized passages.

## Baselines and ablations

| Baseline | Present or proposed | Fair control |
|---|---|---|
| Exact title/author | Existing structured lexical functions | Same current catalogue and IDs |
| Optional bounded fuzzy lexical | Implemented, default integration off | Freeze typo thresholds and sidecar generation |
| Mongo regex/text | Regex used in some lookup/event/admin paths; generic catalogue text-search baseline requires implementation/index | Do not call regex BM25 or assume a Mongo text index exists |
| BM25 | PROPOSED catalogue baseline | Same text fields, tokenize once, tune dev only |
| Exact dense FlatIP | Existing builder/FAISS tools; experimental baseline | Identical vectors, normalization and subset as HNSW |
| Dense HNSW without reranker | Existing stage can be isolated in harness | Same ANN candidate depth |
| Dense HNSW + CrossEncoder | Active catalogue path | Measure reranker recall ceiling and cost |
| Lexical merge + dense + reranker | Implemented optional path | Keep graph/model and identical judge pool |
| BM25+dense RRF+rerank | PROPOSED extension | Fusion tuning on dev, report retrieval and cost separately |
| Qwen alone | Local generator exists; experiment harness | Same prompt style/output budget, no supplied evidence |
| Dense top1/topk RAG | Harness variant | Same resource/source corpus and decoding |
| CrossEncoder RAG | Existing scorer isolated | Same candidate union |
| Evidence composite and gates | Active | Remove each feature/gate independently; supported vs unsupported strata |
| Existing_qwen vs router_v3/v4/v5 | Default vs EXPERIMENTAL | Same independent contract set, tool state and temperature |
| Popularity / dense-only recommendations | Harness baselines | Temporal users/items split; no future interaction leakage |
| Shared postfilter / per-library / hybrid | FUTURE | Exact authorized per-library nearest neighbors, same total N and tenant selectivity |

Recommended ablations: dense off, ANN→exact, lexical off, rerank off, expansion off, evidence weights/features off, fast gate off, model validation off, context overlap off, metadata fields removed, different k/token budgets/model snapshots, and future library partitions. Do not change all factors at once and attribute improvement to one. New metrics for these controls are **NOT YET MEASURED**.

## Historical numeric examples with limited scope

The recorded embedding-model JSON gives MiniLM MRR 0.95 and nDCG@10 ≈0.8553 for its 30 teacher-relative queries; these are **proxy historical results**, not paper headline quality. Document latency JSON records median 15174.27 ms baseline and 14286.35 ms optimized, while p90 rises from 33762.58 to 37318.60 ms; it therefore does not establish across-the-board faster tails. Synthetic sync benchmark's 500-record timings cannot be scaled linearly into 5M performance. Prefer a newly frozen independent benchmark before using any values in an IEEE results section.
