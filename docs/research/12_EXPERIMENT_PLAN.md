# Reproducible experimental plan

No experiments were executed for this audit. New result cells are **NOT YET MEASURED**. Existing artifacts and their limited scope are inventoried below. Separate ANN fidelity from human relevance and retrieval quality from generated-answer quality.

## Dataset and controls

Proposed catalogue evaluation: start with 200–400 independently authored queries, stratified equally across exact title, exact author, subject, synonyms, beginner requests, conceptual, descriptive and ambiguous/no-match cases. These counts are a plan, not an existing benchmark. Sample common/rare titles, short/long metadata, popular/long-tail works, typo variants and contradictory metadata. Hold out a frozen test portion before tuning. Pool top-50 from exact/lexical/BM25/exact-dense/HNSW/hybrid systems, deduplicate and blind the system provenance. Two domain-competent judges assign 0 irrelevant / 1 useful / 2 highly relevant; adjudicate disagreements and report agreement. Preserve IDs and source revisions. Do not mark a fixed percentage relevant per query.

Proposed QA: 150–300 questions over rights-cleared books and PDF text, with gold answer elements, accepted character/page spans, supported/unsupported/partial labels and adversarial wrong-resource questions. Include facts, summaries, causal/temporal relations, negation, actor confusion, false premises, tables and no-text scans. Gold passages should not be selected from the tested ranker's output alone. Keep evaluation sources and prompt templates outside training; audit dataset/source overlap and generator contamination.

Freeze git revision, package lock/freeze, model snapshots, data/model/index checksums, M/ef settings, chunk variant, thread/device configuration, cache flags and random seeds. Record CPU/GPU/RAM/disk/OS, batch/concurrency/warmups, localhost/client placement and background load. Public paper data excludes personal queries/borrow identities and private PDFs unless consented and licensed.

## Experiments

| ID | Question and comparison | Protocol / outputs | Current feasibility |
|---|---|---|---|
| E1 | Keyword/lexical vs semantic vs optional hybrid | Same frozen catalogue, query groups and judges; exact title/author, bounded lexical/fuzzy, BM25 (new baseline), exact MiniLM, HNSW, rerank, lexical merge; nDCG@10, MRR@10, P/R/Hit@5/@10, counts/failures | Dense/rerank and optional lexical code available; new independent labels/BM25 needed |
| E2 | HNSW efficiency and fidelity | Same vectors with FlatIP; N=1K/10K/100K/1M/5M only when resources allow; M=16/32/48, efConstruction=100/200, efSearch=32/64/128/256; exact-neighbor Recall@k, warm/cold p50/p95, RSS/disk/build | Helpers exist; large current index must be cloned/read-only, no submission numbers inferred from manifest |
| E3 | RAG vs Qwen alone | Same questions/model/decoding/output budget; no-context Qwen, dense top1/topk, cross-encoder, full evidence pipeline; randomize answer order, blind judges | Active QA tools exist; global/selected permission policy first |
| E4 | Chunk size/overlap | Separate immutable variants 128/224/256 total tokens with 0/32/64 overlap and current characters baseline; freeze source bytes/offsets; measure coverage, source-span Recall, QA quality, preparation/query cost | Experimental chunker and tests exist; default is character based |
| E5 | Retrieval/context depth | k=1/3/5/10/20 controlling candidate pool/output budget; report retrieved tokens, prompt tokens, answer correctness/latency | QA depth config is not a pure k ablation: candidates/output budgets also change; explicit experiment adapter required |
| E6 | Selected-book grounding | Known A/B books with contradictory shared characters/facts; query A about B, direct forged work ID, no selection, expired/returned borrow, source switching during request; verify sources and entitlement | Access tests exist; must include unselected route gap |
| E7 | Private document QA/lifecycle | Text PDFs, no-text scans, long/tables/layout, malformed/size limits; two users and sessions, expiry/logout/delete, concurrent switches; source ID/page accuracy, QA, upload/restore latency | Private service and cache fixtures exist |
| E8 FUTURE | Cross-library isolation | A/B catalogues with exact duplicate titles/ISBNs and highly similar vectors, forged L, deleted L, missing/corrupt index/fallback, all API/source/cache paths; result/source/event/analytics violations | Requires 21–23 implementation first |
| E9 FUTURE | Index architecture/scale | Separate, shared postfilter, selector-enabled shared where supported, registry hybrid; tenants=10/100/1000/10000, control total N and skew; authorized exact per-library reference | Requires scope pipeline; no current result |
| E10 | Synchronization under churn/failure | Adds/updates/deletes/replace, worker crash between writes/publication, corruption, model change; freshness, stale exposure, successful recovery, writer contention | Existing SyncQueue/IndexManager test harness reusable; use temporary DB/index |
| E11 | Assistant reference/routing quality | Freeze independent intents/selection/page/document cases; existing_qwen vs experimental routers; entity/reference errors, safe clarify, action errors, p50/p95 and calls | Experimental reports exist; keep same-agent authored limitation visible |
| E12 | Recommendation/graph usefulness | Popularity, semantic-only, current heuristic, KG; temporal user holdout, cold start/long-tail, diversity/coverage and blind explanation checks | Current services exist; ethically usable interaction labels still needed |

## Latency and statistical procedure

Measure client wall time and server stages separately. Include cold model/index load and warm query timings; report cache hits separately. Proposed warm protocol: fixed 10 warmups, at least 100 queries across each condition, 5 repeated runs, controlled concurrency 1/5/20, and randomized condition order. These are planned parameters, not actual runs. Use `perf_counter`, synchronize CUDA around GPU stages, record FAISS/OpenMP threads, peak RSS/GPU allocated/reserved, disk/index bytes and transient rebuild memory. Include failed/timeout requests; do not report only successes.

For relevance/QA compare paired per-query outcomes and bootstrap confidence intervals (e.g. 10,000 resamples with fixed seed), plus effect size. Pre-register primary outcome nDCG@10 and groundedness/correctness rubric; correct multiple comparisons when testing many variants. Do not infer statistical significance from a small mean difference. Report query-group means and confidence intervals alongside overall values.

## RAG annotation rubric

Score correctness, grounding, relevance, completeness, source consistency 0–2 each: 0 wrong/unsupported; 1 mixed/partial; 2 correct and adequately supported. Record unsupported atomic claim count and denominator, answerable refusal (false refusal), unanswerable answered (unsafe answer), and legitimate abstention. Generated citations/source list must match actual evidence; an answer can be fluent and incorrect. Human judges remain blinded; a separate model judge can assist but is not sole truth, especially when Qwen is validator/generator.

## Existing evidence that can be reused cautiously

| Artifact | What it supports | What it does not support |
|---|---|---|
| `benchmarks/embedding_model_comparison/benchmark_results.json`, query CSV/report | Recorded 30-query MiniLM/BGE measurements on a candidate-derived corpus | Independent human gold or current full 5M system advantage; exact producing script not confidently matched in source inventory |
| `datasets/ai/evaluation/labeled_evaluation_dataset.json` + `create_relevance_labels.py` | Teacher-relative proxy judgments | All labels genuinely relevant, unbiased cross-model comparison |
| `reports/semantic_sync_benchmark.json` | 500-record synthetic temporary corpus timing; some real Mongo lookup observations | Five-million rebuild throughput or production SLA |
| `datasets/ai/faiss/hnsw/hnsw_metadata.json` + active manifest | Persisted count/config/build-time record | Binary integrity, live counts, exact-neighbor recall/quality |
| `reports/rag_embedding_truncation_audit.json` | Historical 3959-chunk length diagnostic | New chunk variant superiority or every uploaded PDF |
| `reports/document_rag_latency_final.json` + raw runs | Historical baseline vs fast adapter latency/relative behavior study | Independent domain QA correctness or current private-session workload performance |
| `reports/rag_retrieval_unlabeled_summary_20260925.json` | 10-query diversity/diagnostics explicitly without gold | Retrieval accuracy |
| `reports/search_depth_*results.json` | Paging/ranking observations | Independent search-quality improvement |
| Router sealed manifest/results | Contract evaluation with explicit same-author bias | Default production learned routing, external blinded benchmark |
| Existing XML/log test results | Historical contract outcomes for their versions | This audit ran tests or every current suite passes |

## Execution order

First freeze and validate sources/contracts, then label retrieval/QA pools, run E1/E2/E3 with baseline decoding, then E4/E5 and evidence/gate ablations, then E6/E7/E10 safety/consistency and E11/E12 secondary studies. E8/E9 begin after scoped implementation. Export raw per-query records, scripts, manifests, failure logs and aggregate tables; fill [16](16_TABLE_TEMPLATES.md) only from those outputs.
