# LuminaR RAG token-aware chunking experiment — 2026-09-27

**RESULT LABEL: EXPLORATORY ONLY — DRAFT EVALUATION LABELS.** All 50 existing
questions and 55 accepted evidence spans remained unchanged; independent
reviewed labels: **0**. No variant was promoted to production.

## Fine-tuning decision

**B. INPUT VISIBILITY FIXED BUT DENSE RECALL STILL WEAK — SENTENCETRANSFORMER
FINE-TUNING NOW JUSTIFIED as a later controlled experiment.** The 220-token
variant makes **55/55** current DRAFT spans visible under the existing
overlap-aware policy, yet raw dense Recall@50 is only **63.3%** and 17/49
evaluable questions have no accepted passage in Top-50. Its dense-preserving
union raises full-pool Hit to 69.4%, but 15/49 still lack accepted evidence
even in that larger pool. Correcting input visibility alone therefore did not
solve first-stage recall. This is a research-priority decision, **not** a
validated model-selection or production-adoption claim: draft labels may omit
other valid passages. Fine-tuning, lexical/hybrid retrieval, and label review
remain separate next experiments. No training or external dataset download
occurred in this task.

The exploratory 220-token variant is the clearest diagnostic control: it
reaches 100% policy visibility and the highest raw dense Recall@50 (63.3%) of
the token-aware variants. The 240-token variant has better early-rank MRR
(0.250 vs 0.195) but slightly lower Recall@50 (62.2%) and one cross-boundary
span. Neither is a production winner.

## Architecture and isolated construction

The active production path is `rag/book_ingest.py`: `clean_text` normalizes
line endings/horizontal whitespace, then `chunk_text` uses a 3,000-character
target, paragraph/sentence end preference, and a raw 400-character overlap
restart. `rag/chunk_books.py` contains an older 1,800/300 path and is not the
active per-book index producer. `rag/embed.py` encodes chunk body text with
unchanged `sentence-transformers/all-MiniLM-L6-v2`, L2-normalizes 384D vectors,
and builds `IndexFlatIP` indexes. The current retriever searches a selected
book. The current reranker expands each query, admits up to 15 dense results
per expansion, deduplicates by first encounter, caps at 40, then scores with
the unchanged cross-encoder and evidence heuristic. The existing source map
was used solely to verify authoritative normalized sources and the isolated
current baseline.

All experimental outputs live under
`datasets/rag_experiments/chunking_v1/{current_baseline,tokens_180,tokens_220,tokens_240}`.
Each variant has `chunks.parquet`, `mapping.json`, `manifest.json`,
`embeddings.npy`, a global `faiss.index`, 18 book-specific `IndexFlatIP`
indexes, `visibility.json`, and `dense_evaluation.json`. The shortlisted
variants also have `candidate_pool_evaluation.json`.

The token-aware chunker uses the actual MiniLM tokenizer and reserves its two
special tokens. Targets are **180 total tokens / ~30-token overlap**, **220 /
~40**, and **240 / ~40**. It chooses paragraph boundaries first, then sentence
boundaries, then word boundaries, and rejects a truly overlong single word
rather than silently making a mid-word chunk. Sentence starts are preferred
for overlap; a word boundary is used when necessary. Each chunk records a
deterministic ID, source offsets/hash, book metadata, chapter, ordinal, token
count, variant, and exact normalized-source text. Pages remain null.

The `current_baseline` was independently reproduced in the workspace from the
active chunker and checked against all 3,959 indexed production metadata rows.
Its experimental dense metrics reproduce the prior current-index diagnostic.
A repeat 220-token build produced identical chunk Parquet, mapping, and FAISS
hashes; the build tooling refuses to stale an existing index if chunk content
changes.

## Chunk, boundary, and source audit

The installed model accepts **256 total tokens including special tokens**.
The original token audit found 3,958/3,959 current chunks over the window,
with mean 648.9 tokens; 35/55 accepted spans lacked a fully visible matching
chunk and 33/55 were entirely beyond the window in every current matching
chunk. The new visibility classifier also counts partial evidence in any
touching chunk, so its baseline `PARTIALLY_VISIBLE`/`INVISIBLE` split below
uses a broader diagnostic than that earlier matching-chunk-only audit.

| Variant | Chunks | vs current | Mean | Median | p90 | p95 | p99 | Max | >256 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current_baseline | 3,959 | 1.00× | 648.9 | 659 | 752 | 782 | 849 | 979 | 3,958 (99.9747%) |
| tokens_180 | 20,849 | 5.27× | 152.2 | 157 | 176 | 178 | 179 | 179 | 0 (0%) |
| tokens_220 | 16,895 | 4.27× | 187.4 | 194 | 216 | 218 | 219 | 219 | 0 (0%) |
| tokens_240 | 15,011 | 3.79× | 204.5 | 212 | 235 | 237 | 239 | 240 | 0 (0%) |

All four variants cover **all 18 books**, have **zero uncovered meaningful
characters**, zero invalid source offsets/text, zero empty chunks, zero
malformed-whitespace chunks, and zero invalid Unicode boundaries. The current
baseline has **2,347 real mid-word starts** under an adjacent-alphanumeric
source-offset check (not the weaker lowercase-start proxy); it has zero
mid-word ends. All three token-aware variants have **zero mid-word starts and
ends**. Their actual encoded totals remain under the model window.

## Evidence visibility

`FULLY_VISIBLE` means one chunk covers at least 80% of an accepted span and
at least 40 characters (or the whole shorter span) **inside its actual
encoder-visible window**, matching the evaluation relevance rule.
`PARTIALLY_VISIBLE` means some source evidence is visible but no single chunk
meets that rule. This is a DRAFT-label diagnostic, not adjudicated gold.

| Variant | Fully visible | Partially visible | Invisible | Fully visible % | Strict entire-span containment | Cross-boundary, no policy match |
|---|---:|---:|---:|---:|---:|---:|
| current_baseline | 20 | 7 | 28 | 36.4% | 19 | 0 |
| tokens_180 | 52 | 3 | 0 | 94.5% | 41 | 3 |
| tokens_220 | 55 | 0 | 0 | 100.0% | 49 | 0 |
| tokens_240 | 54 | 1 | 0 | 98.2% | 50 | 1 |

The three 180-token misses are `jekyll_03`, `moby_03`, and `moby_05`; the
240-token miss is `pp_05`. Each is a cross-boundary source excerpt rather than
an encoder truncation. The 180-token result is below the requested 95%
visibility target and should not be treated as a finished remediation. The
220- and 240-token variants pass that target. No evaluation span was edited.

## Original-question raw dense retrieval

All results below use the unchanged MiniLM model, book-specific experimental
`IndexFlatIP`, original question only, and no expansion, reranker, lexical
retrieval, or generation. The one questionable Dracula question is excluded;
**49 DRAFT questions** are evaluated. The full per-query files contain
first-accepted rank, candidate ID, source offsets, similarity, and Top-50.

| Variant | MRR | Hit@1 | Hit@3 | Hit@5 | Hit@10 | Hit@20 | Hit@50 | Recall@5 | Recall@10 | Recall@20 | Recall@50 | No gold Top-50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current_baseline | .158 | 10.2% | 14.3% | 18.4% | 32.7% | 44.9% | 65.3% | 18.4% | 32.7% | 43.9% | 62.9% | 17 |
| tokens_180 | .211 | 14.3% | 22.4% | 26.5% | 36.7% | 44.9% | 59.2% | 26.5% | 35.7% | 42.9% | 57.1% | 20 |
| tokens_220 | .195 | 8.2% | 22.4% | 32.7% | 42.9% | 55.1% | 65.3% | 32.7% | 42.9% | 54.1% | 63.3% | 17 |
| tokens_240 | .250 | 18.4% | 26.5% | 30.6% | 38.8% | 55.1% | 63.3% | 30.6% | 37.8% | 55.1% | 62.2% | 18 |

Relative to the isolated baseline, per-query first-accepted rank changed as
follows (IMPROVED / REGRESSED / UNCHANGED): **180: 18/19/12**;
**220: 22/14/13**; **240: 18/17/14**. Top-50 evidence was recovered/lost
for **6/9**, **7/7**, and **7/8** questions respectively. Exact per-query old
and new ranks/presence are in `reports/dense_variant_comparison.json`. These
movements alone do not establish a cause or validated quality gain.

## Candidate admission, held separate from embedding quality

After raw dense evaluation, the 220- and 240-token variants were shortlisted
for **exploratory** candidate-pool tests. `PYTHONHASHSEED=0` fixes the current
expander's synonym-set iteration. Current expansion uses the unchanged
per-expansion Top-15, first-seen deduplication, and cap 40. The three unions
preserve the promised original dense Top-30/40/50 prefix, append expansion
candidates deterministically, and cap at 50/60/80 respectively. No reranker
was used. Values below are **full-pool** availability; Hit/Recall at depths
5/10/20/40/50 are stored per pool in the JSON files.

| Variant and pool | Mean candidates | Full-pool Hit | Full-pool span Recall |
|---|---:|---:|---:|
| 220 raw dense Top-50 | 50.0 | 65.3% | 63.3% |
| 220 current expansion | 20.9 | 59.2% | 58.2% |
| 220 union 30→50 | 33.3 | 67.3% | 66.3% |
| 220 union 40→60 | 42.8 | 67.3% | 66.3% |
| 220 union 50→80 | 52.7 | 69.4% | 67.3% |
| 240 raw dense Top-50 | 50.0 | 63.3% | 62.2% |
| 240 current expansion | 21.0 | 57.1% | 57.1% |
| 240 union 30→50 | 33.1 | 63.3% | 63.3% |
| 240 union 40→60 | 42.7 | 65.3% | 65.3% |
| 240 union 50→80 | 52.4 | 67.3% | 66.3% |

The 220-token current expansion loses 6.1 percentage points of full-pool Hit
relative to its raw dense Top-50; the dense-preserving 50→80 union retains
the dense results and adds two accepted-evidence cases. Candidate-pool loss is
thus a downstream admission effect, not an embedding-model failure. These
unions were scored for availability only, not reranked or deployed.

## Latency, memory, and storage

The unchanged model was warmed before per-query timing. Book indexes were
loaded before the raw-dense timer; cold model/index startup is excluded.

| Variant | Raw dense mean / median / p95 | Chunk build | Embedding build | Index build | Global FAISS | Parquet + mapping | Total variant files |
|---|---:|---:|---:|---:|---:|---:|---:|
| current_baseline | 12.68 / 12.19 / 15.36 ms | 11.11 s | 7.74 s | 0.03 s | 5.80 MiB | 4.49 MiB | 22.44 MiB |
| tokens_180 | 12.66 / 12.47 / 15.09 ms | 33.62 s | 26.01 s | 0.10 s | 30.54 MiB | 8.04 MiB | 100.27 MiB |
| tokens_220 | 12.63 / 12.38 / 14.77 ms | 33.10 s | 25.47 s | 0.07 s | 24.75 MiB | 7.24 MiB | 82.84 MiB |
| tokens_240 | 13.01 / 12.64 / 15.58 ms | 33.41 s | 24.92 s | 0.06 s | 21.99 MiB | 6.86 MiB | 74.18 MiB |

Each variant also stores a book-index set about the size of its global index
and one float32 embedding array of similar size. Global index size scales with
chunk count and stays 384D. The maximum sampled embedding-build process RSS
across variants was about **1.65 GiB**; maximum PyTorch GPU allocated memory
was about **0.22 GiB** (device-wide usage is not implied). Raw-dense evaluation
process RSS reached about **1.47 GiB** and PyTorch GPU allocated about
**0.094 GiB**. These are local sampled peaks, not capacity forecasts.

In the final 220-token candidate run, mean original dense retrieval was
**17.23 ms**, the separate current expansion stage **37.12 ms**, and bounded
union construction **0.05 ms**; p95 values were **22.91 / 55.68 / 0.08 ms**.
For 240 tokens the corresponding means were **16.80 / 37.90 / 0.04 ms**.
The candidate run was separate from raw-dense timing and showed normal run
variation. Reranker time and total reranked latency are **not measured**, as
the optional unchanged-reranker follow-up was not run.

The optional title/chapter structured-context experiment and optional
neighbor/parent context reconstruction were also **not run**; neither is
needed to answer the visibility and raw candidate-recall question in this
task.

## Reproduce and verify (PowerShell)

```powershell
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe scripts\build_rag_chunk_variants.py --variant current_baseline
.\.venv\Scripts\python.exe scripts\build_rag_chunk_variants.py --variant tokens_180
.\.venv\Scripts\python.exe scripts\build_rag_chunk_variants.py --variant tokens_220
.\.venv\Scripts\python.exe scripts\build_rag_chunk_variants.py --variant tokens_240
@('current_baseline','tokens_180','tokens_220','tokens_240') | ForEach-Object {
    .\.venv\Scripts\python.exe scripts\audit_rag_variant_visibility.py --variant $_
}
.\.venv\Scripts\python.exe scripts\build_rag_experimental_indexes.py --all
.\.venv\Scripts\python.exe scripts\evaluate_rag_chunk_variants.py --dense-only
$env:PYTHONHASHSEED = '0'
.\.venv\Scripts\python.exe scripts\evaluate_rag_candidate_union_v2.py
.\.venv\Scripts\python.exe -m pytest tests\test_rag_experimental_chunker.py tests\test_rag_experimental_index.py -q
```

Rebuilding an existing chunk variant checks its Parquet and mapping against
the already indexed content rather than silently invalidating its FAISS
index. The model is loaded only from the local cache, without training.

## Tests and safety

Added `rag/experimental_chunker.py`, five build/audit/evaluation scripts,
`tests/test_rag_experimental_chunker.py`, and
`tests/test_rag_experimental_index.py`. **13 relevant tests passed; 0 failed**
in the final combined run. Tests cover token and source boundaries,
paragraph/sentence/word fallback, overlap, deterministic IDs, all-book source
coverage and hashes, accepted-span visibility, normalized 384D vectors,
`IndexFlatIP` type/count, book mapping, candidate-union preservation/dedupes/
caps, and the prior evaluation/truncation invariants. The experimental
candidate capture reproduced the original-question dense order saved by the
separate raw-dense run. Repeated 220-token chunk/index input hashes matched.

An SHA-256 snapshot of **64 production/evaluation files** before the index
build matched after all experiments, including production RAG chunks/indexes,
the retrieval/reranker/embedding code, the frozen v8 proxy, and evaluation
labels/source map. No production RAG chunk, index, model, retrieval config,
reranker, answer-generation LLM, catalogue HNSW, catalogue lexical sidecar,
Mongo catalogue, or book CRUD/synchronization was modified. No Natural
Questions, SQuAD, or other external training data was downloaded; MiniLM was
not fine-tuned. All new chunks, vectors, indexes, metrics, and reports remain
inside the experimental directory.
