# LuminaR RAG retrieval bottleneck audit — 2026-09-25

## Decision and scope

**C. NO REAL IMPROVEMENT — KEEP CURRENT RETRIEVER.** The frozen v8 regression reproduces its historical numbers, but its labels are keyword lists rather than judged relevant passages, and its reported “MRR” is not reciprocal rank. It cannot support Recall@k, oracle-reranker ceilings, configuration selection, or a defensible before/after improvement claim. Production RAG retrieval and answer generation were left unchanged. This is an evaluation gate, not a finding that the existing retriever is optimal.

## 1–2. Existing architecture and exact baseline

The frozen benchmark is `scratch/run_v8_step7_retrieval_regression.py` (`RETRIEVAL_QUERIES`). It contains **10 questions**: six from *Frankenstein* and four from *Dracula*. Each row supplies a selected `work_id` and separate Top-1/Top-3 keyword lists. It does **not** supply gold passages, chunk IDs, answer spans, multiple acceptable passages, or judged negatives. The index corpus has **3,959 chunks from 18 books**; only the two named books are queried. The normal reranker returns 5 final results from up to 15 dense candidates **per expanded query**, deduplicated and capped at 40 before reranking. The ten cases use two or three expansion strings apiece and admitted 17–37 distinct candidates in this run.

The v7 and v8 retrieval scripts contain **identical ten-case query/rubric data and the same keyword metric logic**; the v7 report describes the same values as a frozen v6 baseline. The archived v7 report counted 3,946 index vectors while the present corpus has 3,959, yet the proxy totals stayed unchanged. I found no comparable versioned v1–v5 retrieval corpus/label files that establish their architecture or true relevance results. An older 18-question `scratch/detailed_evaluator.py` uses question-ID-specific chapter rules, including counting an unsupported premise as a retrieval hit; those rules are not passage-level gold labels for this ten-question suite.

Active book ingestion is `rag/book_ingest.py`: 3,000-character target chunks, 400-character overlap, paragraph boundary when suitable, otherwise sentence boundary, then a raw character-offset overlap start. `rag/chunk_books.py` has an older 1,800/300 configuration but is not the producer referenced by `rag/embed.py` for the current per-book indexes. Source text normalizes line endings, horizontal whitespace and excessive blank lines. The persisted metadata includes chunk ID, work/document ID, filename, title, author, chapter and chunk ordinal; every book `page` is null and no start/end offsets are persisted. Each chunk embeds body text only. The model is `sentence-transformers/all-MiniLM-L6-v2`, 384 dimensions, L2-normalized embeddings, `IndexFlatIP` (cosine-equivalent inner product). The per-book FAISS files total 6,081,834 bytes (5.80 MiB); the global book index is 6,081,069 bytes. The reranker is `cross-encoder/ms-marco-MiniLM-L-6-v2`. The final score combines min-max-normalized cross-encoder score (0.30), evidence heuristic (0.55), and normalized FAISS score (0.15). Query handling strips whitespace, then expands book queries with the existing generic concept/term rules. The answer-generation LLM was in its existing mock mode for this retrieval-only run.

The existing script was run unchanged. Its previous JSON was copied to `reports/intent_aware_rag_v8_retrieval_regression.pre_rag_audit.json` before the script rewrote its usual output. All ten Top-1 chunk IDs and the aggregate scores matched the prior record:

| Frozen script metric | Prior | Reproduced |
|---|---:|---:|
| “MRR” proxy | 0.666 | **0.666** |
| Top-1 keyword threshold | 60% (6/10) | **60% (6/10)** |
| Top-3 combined-text keyword threshold | 70% (7/10) | **70% (7/10)** |
| Mean retrieval + rerank latency | 553.71 ms | **456.83 ms** |
| Median / p95 latency | 626.72 / 742.03 ms | **435.40 / 683.71 ms** |

The script scores Top-1 when at least half of its Top-1 keyword list appears anywhere in the first chunk. It scores Top-3 when at least half of a **different** Top-3 keyword list appears anywhere in the concatenation of the first three chunks. Its “MRR” assigns 1.0 for a Top-1 keyword pass, 0.33 for a Top-3 pass without Top-1, or 0 otherwise; it never locates the first relevant result. These are reproducible proxy scores, **not** judged Hit@k or MRR.

## 3–5. Gold-label audit and why true recall/oracle are unavailable

Every query's selected book exists in the corpus, but **0/10 have an existing gold chunk or passage label**. This provisional source review does not change the frozen labels:

| Query ID | Provisional audit class | Why a single gold chunk is not established |
|---:|---|---|
| 1 | MULTIPLE_VALID | Victor's motivation spans scientific ambition and hoped-for new life; the implementation keywords also describe the creation event. |
| 2 | BOUNDARY_AMBIGUOUS | His father's signed name appears in two overlapping neighboring chunks. |
| 3 | MULTIPLE_VALID | His refusal involves several concerns about a companion and descendants across passages. |
| 4 | BOUNDARY_AMBIGUOUS | Animation and Victor's immediate reaction cross neighboring chunks; “after” could also refer to later events. |
| 5 | GOLD_QUESTIONABLE | The requested reason for Dracula's London journey is not uniquely specified by the rubric. The passing Top-1 text instead describes Harker's journey **from** London. |
| 6 | BOUNDARY_AMBIGUOUS | The locked-exit/prison explanation appears in overlapping neighboring chunks. |
| 7 | MULTIPLE_VALID | Mina and Jonathan's relationship is expressed in several journal/letter passages. |
| 8 | MULTIPLE_VALID | The Demeter is named in several source passages. |
| 9 | MULTIPLE_VALID | Victor's regret has several causes and manifestations over the novel. |
| 10 | BOUNDARY_AMBIGUOUS | The eye-opening and subsequent bedside encounter span neighboring chunks; “first sees” has more than one plausible moment. |

Classification counts: **CLEAR_SINGLE_GOLD 0, MULTIPLE_VALID 5, BOUNDARY_AMBIGUOUS 4, GOLD_QUESTIONABLE 1**. These are audit observations, not a newly adjudicated gold set. Metrics on the genuinely single-gold subset are **undefined** because that subset has zero questions. Original-label proxy metrics are retained above. No labels were silently changed.

The rubric can mark an irrelevant first chunk correct: question 2 passes on “father” without “Alphonse”; question 5 passes on “London” and “Dracula” in a passage about Harker traveling the opposite direction; question 8 passes on “ship” without “Demeter.” Question 8 passes Top-1 but fails Top-3 (0.50 versus 0.333), which cannot happen for genuine cumulative Hit@k. Combining words from three separate passages can also pass Top-3 without any individually answer-bearing passage. Consequently true Recall@1/3/5/10/20/50, gold rank, failure-category counts A–J, and oracle Top-1/Top-3/MRR at candidate depths 5/10/20/50 are **not computable** from the existing benchmark. Computing them from the keyword rubric would mislabel them as relevance measurements.

## 6–8. Read-only error, candidate and chunk diagnostics

The frozen proxy reports four Top-1 failures (questions 1, 3, 6, 9) and three Top-3 failures (6, 8, 9); these are **proxy failures**, not adjudicated retrieval errors. `reports/rag_retrieval_diagnostic_20260925.json` captures each original-question dense Top-50, the expanded candidate IDs, all reranked candidates, scores, full text, chunk ID and source/chapter/page metadata. Selected source-phrase probes demonstrate mixed bottlenecks without treating a phrase as an exhaustive gold set:

| Source evidence probe | Original dense rank | Expanded/reranked rank | Observation |
|---|---:|---:|---|
| Victor's father's signed name, two overlapping chunks | 2 and 9 | 6 and 4 | Exact name was available early but moved down. |
| Female-creature “race of devils” concern | absent Top-50 | 5 | Expansion recovered a pertinent passage that original dense query missed. |
| Harker calls castle a prison | 29 (one overlapping copy) | 5 | Expansion/reranking raised one answer-bearing passage. |
| Demeter's name on the ship | 13 and 24 | 12 and absent | The proxy Top-1 success did not retrieve the named ship in Top-1. |
| Victor's “new species” motive | absent Top-50 | 2 | Expanded query recovered this source passage. |

These examples show that query representation/candidate recall and final ranking can each matter. They cannot establish aggregate recall or a reranker ceiling without complete accepted-passage judgments.

The active chunks have mean **2,674** characters, median **2,775**, p95 **2,984**, and range **541–2,999**. **3,626/3,959** start with a lowercase character; inspected examples begin mid-word because overlap starts at a raw character offset. **614/3,959** have chapter `Unknown`, every book page is null, and no stored character offsets permit exact source-span mapping. This makes boundary labeling and neighbor mapping harder. The inspected false positives also show topic/entity matches without the requested relation or direction.

The diagnostic contains no exact duplicate or near-duplicate pair (five-word-shingle Jaccard ≥0.8) in Top-3 or Top-10 for any of the ten questions. This narrow result does not rule out less-similar overlap or duplicates elsewhere in the corpus. The top-result near-duplicate rate under this stated threshold is **0/10 queries** at both depths. `reports/rag_retrieval_unlabeled_summary_20260925.json` contains per-query counts.

## 9–20. Controlled ablations and adoption gate

No chunking, structured-content, embedding-model, query-normalization, BM25/FTS hybrid, reranker-depth, deduplication, parent-child, or neighbor-expansion experiment was promoted to a quality comparison. Each would be selected against the defective ten-question proxy or an unreviewed new label set. The 10 questions across only two books also cannot support a meaningful development/held-out split. No training ran.

| Configuration | MRR | Top-1 | Top-3 | Recall@10/20/50 | Latency | Index size |
|---|---:|---:|---:|---|---:|---:|
| Existing frozen proxy baseline | 0.666* | 60%* | 70%* | unavailable | 456.83 ms mean | 5.80 MiB per-book FAISS total |
| Best chunking only | not run | not run | not run | unavailable | not run | not built |
| Best embedding only | not run | not run | not run | unavailable | not run | not built |
| Hybrid only | not run | not run | not run | unavailable | not run | not built |
| Reranker only | not run | not run | not run | unavailable | not run | existing only |
| Combined | not run | not run | not run | unavailable | not run | not built |

`*` Keyword proxies with the definitions above, not relevance metrics. No configuration won, so no production retrieval configuration was implemented and no final old/new regression can be claimed. Queries improved/regressed/unchanged against a new retriever are **not applicable**. The unchanged frozen benchmark remains reproducible, but a relevance-labeled benchmark is needed before experiments can identify a winner. A future label file should list accepted evidence spans for each question, allow multiple passages, flag cross-boundary answers, and be reviewed independently of candidate rankings. It should include more books and questions, with held-out validation if the sample becomes large enough.

| Requested final metric | Existing retriever | New retriever |
|---|---:|---:|
| MRR | 0.666 proxy; true MRR unavailable | not implemented |
| Top-1 / Top-3 | 60% / 70% keyword proxies; true Hit@k unavailable | not implemented |
| Recall@5 / @10 / @20 / @50 | unavailable without accepted passages | not implemented |
| Mean latency | 456.83 ms in the reproduced 10-question run | not measured |
| Per-book FAISS index size | 5.80 MiB across 18 books | unchanged |

## Files, checks and safety confirmation

Added read-only diagnostics: `scripts/audit_rag_retrieval.py`, `scripts/analyze_rag_retrieval_diagnostic.py`, and `scripts/inspect_rag_passages.py`. Added this report and two diagnostic JSON files. Backed up the prior frozen output and reran the existing script unchanged, replacing only its normal **report JSON**. No new unit tests were added because no production algorithm changed. The exact v8 regression run and both diagnostic scripts completed successfully; the candidate-capture check verified the recorded expanded pool equals the production reranker's pool for all ten questions. No script failed in the final run.

Verification: **1/1 frozen benchmark runs, 2/2 diagnostic scripts, 3/3 script syntax checks, and the diagnostic row/depth integrity check passed; 0 final failures.** No unit-test suite was rerun because no production code changed.

Remaining failure modes to evaluate after labeling: absent evidence from original dense Top-50 for some source-phrase probes, relevant material demoted by final scoring in others, ambiguous or crossing chunk boundaries, broad causal questions, and missing source offsets. The catalogue semantic HNSW, catalogue lexical sidecar, Mongo catalogue, book CRUD/search synchronization, production RAG indexes, production retrieval code and answer-generation LLM/prompt were **not changed**. No benchmark question or gold chunk ID was hardcoded into retrieval behavior or the generic diagnostic scripts.
