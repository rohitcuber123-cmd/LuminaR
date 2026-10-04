# LuminaR RAG retrieval evaluation v1 — 2026-09-26

## Decision

**B. PROMISING BUT NEEDS MORE LABELING/VALIDATION.** A source-first, versioned
dataset and a reproducible overlap-aware scorer now exist. All 50 labels are
assistant-authored **DRAFTs**, with **zero independent human reviews**. The
measured retrieval numbers below are exploratory and must not be called a
validated true baseline or used to select a v9 configuration. No production
retriever change or retrieval ablation was made.

## Dataset and review gate

- Dataset: `rag/evaluation/rag_retrieval_eval_v1.json`
- Authoring seeds: `rag/evaluation/source_first_seeds_v1.json`
- Source/chunk offset map: `rag/evaluation/source_map_v1.json`
- Format and scoring policy: `rag/evaluation/FORMAT.md`
- Source-only human review packet: `reports/rag_retrieval_v1_label_review.md`
- Preserved frozen ten-case benchmark: `scratch/run_v8_step7_retrieval_regression.py`
  (`legacy_proxy_v8`); its questions and keyword scoring were not edited.

The dataset has **50 questions across 10 books**, 55 accepted source spans,
and 49 evaluable questions. One Dracula travel-motive question has a
questionable premise and no accepted span; it is excluded from metrics.
Source offsets were reconstructed for **all 18 books and 3,959 current chunks**
by rerunning the active normalizer/chunker and checking every reconstructed
chunk against current indexed metadata. Gold anchors were selected from
processed source texts without consulting Top-10 retrieval output. The
generator rejects changed source hashes and ambiguous/missing anchors. Each
span records offsets, excerpt, source hash, chapter, neighbor allowance,
grade, and current chunk matches. Relevance requires >=80% source-span
coverage and at least 40 overlapping characters (or the whole span when
shorter); duplicate overlapping chunks cannot inflate span recall. Grade 1
supporting spans do not count toward primary metrics. No grade 1 or judged
negative examples have yet been independently established.

| Distribution | Counts |
|---|---|
| Split | DEV 30 questions / 6 books; TEST 20 / 4 books |
| Difficulty | EASY 18; MEDIUM 29; HARD 3 |
| Ambiguity | CLEAR 37; MULTIPLE_VALID 6; BOUNDARY 6; QUESTIONABLE 1 |
| Category | FACTUAL_DIRECT 17; ENTITY_RELATION 9; EVENT 8; MOTIVATION 4; CAUSAL 4; LOCATION 3; QUOTE_OR_PHRASE 2; BOUNDARY_SENSITIVE 1; TEMPORAL 1; SEMANTIC_PARAPHRASE 1; MULTI_PASSAGE 0 |
| Review | DRAFT 50; REVIEWED 0 |

The distribution is still tilted toward direct facts and medium difficulty.
`MULTI_PASSAGE` needs genuine jointly required evidence, rather than relabeling
a single-passage question. Several broad legacy questions may need additional
valid spans. Human reviewers must check every premise, omitted alternatives,
grade, and boundary before these labels can become adjudicated gold. The
book-group TEST split was measured only as a descriptive current-system
baseline; it was not used to choose a configuration.

## Exploratory current-system measurement (DRAFT labels only)

The current `RAGRetriever` and `RAGReranker` ran unchanged, scoped to each
question's book. Full per-query chunk IDs, ranks, latency, label/source-map
hashes, and first-stage candidate order are in
`reports/rag_retrieval_v1_draft_baseline.json`. Its label status is
`DRAFT_ONLY_NOT_FOR_SELECTION`. The process was run with
`PYTHONHASHSEED=0`, because the unchanged query expander iterates a synonym
set when choosing terms. Two seeded runs produced identical dense, expanded,
and reranked chunk-ID sequences for all 50 queries. The final reranked pool is capped at 40, so
its displayed @50 value is the full <=40 pool, not a genuine depth-50 run.

| Stage | MRR | Hit@1 | Hit@3 | Hit@5 | Recall@5 | Recall@10 | Recall@20 | Recall@50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Original dense Top-50 | .158 | 10.2% | 14.3% | 18.4% | 18.4% | 32.7% | 43.9% | 62.9% |
| Expanded candidate admission order, cap 40 | .153 | 10.2% | 14.3% | 18.4% | 18.4% | 32.7% | 46.9% | 46.9%* |
| Current v8 expanded + reranked, cap 40 | .296 | 22.4% | 34.7% | 40.8% | 39.8% | 45.9% | 46.9% | 46.9%* |

`*` Full capped pool, at most 40 chunks. These are overlap-scored DRAFT
diagnostics, **not validated true relevance results**. The historical frozen
v8 proxies remain 0.666 pseudo-MRR, 60% Top-1 keyword, and 70% Top-3 keyword;
they are not comparable to this span-based table.

Original dense Hit@1/3/5/10/20/50 is 10.2/14.3/18.4/32.7/44.9/65.3%.
An oracle that perfectly reranked the original dense candidate prefix would
have MRR and Hit@1/3 ceilings of 18.4%, 32.7%, 44.9%, and 65.3% at candidate
depths 5, 10, 20, and 50. For the actual expanded admission pool, the
equivalent ceilings at depths 5, 10, 20, and 40 are 18.4%, 32.7%, 49.0%, and
49.0%. Those equalities follow because an oracle puts any present accepted
passage first. Expansion improves depth-20 presence slightly but the
15-per-query and 40-total admission caps lose other evidence present in the
original dense Top-50. Among 50 questions, the provisional primary outcome
classification is 15 `NO_GOLD_IN_TOP50`, 10 `CANDIDATE_POOL_LOSS`, 7
`GOLD_RANK_4_20`, 6 `RERANKER_DEMOTION`, and 1 `AMBIGUOUS_LABEL`; 11 have a
first-rank accepted passage. These mechanistic classes are sensitive to
missing alternate labels. No unsupported cause such as `QUERY_MISMATCH` or
`CHUNK_TOO_BROAD` was assigned solely from a rank.

Mean original dense search was 15.8 ms, and candidate capture plus the current
expanded/rerank path was 351.2 ms in the final evaluation run (about 367.0 ms
combined). These are local sequential timings, not a production latency SLO.

## Deferred experiments and adoption

Chunk-size/boundary changes, mid-word-overlap correction, structured embedding
text, alternative embedding models, lexical retrieval, dense+lexical RRF,
query-expansion variants, reranker candidates, ranking weights, and a combined
v9 configuration were **not run**. The dataset has no reviewed labels, and
choosing a winner from its draft scores would violate the source-review gate.
The current run only diagnoses the unchanged v8 path and shows why candidate
recall and reranking both merit study after review. There is therefore no
defensible best DEV configuration, held-out TEST comparison, before/after
quality or latency claim, or adoption candidate.

Review the source-only packet independently, add any omitted valid spans,
resolve the questionable premise, and mark labels `REVIEWED` with reviewer
identity/date in a subsequent dataset version. Once reviewed, rerun this
baseline and controlled one-variable-at-a-time ablations on DEV; use TEST
only for the final comparison.

## Files and verification

Added `scripts/build_rag_eval_source_map.py`, `scripts/build_rag_eval_v1.py`,
`scripts/evaluate_rag_retrieval_v1.py`, `scripts/render_rag_eval_review.py`,
`rag/evaluation/metrics.py`, both evaluation JSON inputs/outputs, this report,
the review packet, and two evaluation tests. `scripts/inspect_rag_passages.py`
gained a read-only `--skip-chunks` source-inspection option. Reconstructed
metadata matched all 3,959 chunks. **5 evaluation tests passed**, covering
source-span integrity, verbatim legacy questions, overlap equivalence,
grade-2-only recall, boundary threshold, MRR, and oracle aggregation. Current
retriever candidate-capture sets matched its own final candidate sets for all
50 queries. No catalogue HNSW, catalogue lexical sidecar, Mongo catalogue,
answer-generation LLM, production RAG chunker/index, or production retrieval
code changed. No benchmark-specific retrieval hardcoding was introduced.
