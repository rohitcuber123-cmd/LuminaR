# LuminaR SentenceTransformer fine-tuning preflight — 2026-09-27

## Decision

**C. TRAINING NOT JUSTIFIED DUE TO INPUT/TRUNCATION ISSUE.** The actual
`all-MiniLM-L6-v2` SentenceTransformer accepts **256 tokens including special
tokens**, while **3,958/3,959 (99.9747%)** indexed RAG chunks exceed that
limit. Mean chunk length is 648.9 tokens, or about 393 excess tokens per
chunk. Of 55 accepted but still DRAFT evaluation evidence spans, **35** have
no fully visible matching indexed chunk and **33** are entirely beyond the
model's usable window in every matching chunk. A direct check of the installed
model's tokenization confirmed a representative 570-token chunk is encoded as
256 tokens, exposing only the beginning of its text.

Fine-tuning this same architecture against the unchanged long-chunk index
cannot teach it to retrieve evidence it never receives. The input/index
relationship should be corrected in an **isolated experimental variant** and
measured before external dataset preparation or training. Production chunking,
RAG indexes, and models remain unchanged. This is a preflight finding, not a
claim that fine-tuning can never help after the input problem is addressed.

**IMPORTANT RESULT LABEL: EXPERIMENTAL ONLY — NOT FOR MODEL SELECTION.** All
current evaluation labels are DRAFT; independent reviewed labels: **0**.

## Environment and model

| Item | Verified value |
|---|---|
| Project Python packages | torch 2.11.0+cu128; transformers 5.15.1; datasets 5.0.0; sentence-transformers 5.6.0; accelerate 1.14.0 |
| CPU / RAM | AMD Ryzen 7 260, 16 logical processors; 15.31 GiB physical RAM |
| GPU / VRAM | NVIDIA GeForce RTX 5060 Laptop GPU; 8,151 MiB VRAM |
| D: free before data acquisition | 59.89 GiB |
| Base model | `sentence-transformers/all-MiniLM-L6-v2`, loaded locally |
| Effective maximum input | 256 tokens including `[CLS]` and `[SEP]` |
| Embedding dimension | 384, normalized in current production indexing |
| Base parameter tensor size | 22,713,216 parameters; 90,852,864 bytes (86.64 MiB) of parameter tensors |
| Current per-book FAISS indexes | 18 `IndexFlatIP` files, 6,081,834 bytes (5.80 MiB) total |

All required packages were already installed. No packages were upgraded. No
Natural Questions, SQuAD, HotpotQA, or other external dataset was downloaded
or streamed. The explicit `datasets/training/hf_cache` exists but has no
downloaded data. NQ mode is therefore **not used** (neither streaming nor full
download); NQ rows inspected/accepted: **0/0**. SQuAD rows inspected/accepted:
**0/0**. There are no transformed generic or LuminaR training pairs, mined
hard negatives, training checkpoints, or new FAISS indexes. Directory-only
workspace preparation used negligible disk space.

## Complete current-chunk token audit

`scripts/audit_rag_embedding_lengths.py` loaded the installed local
SentenceTransformer and used its actual tokenizer with no truncation to count
all 3,959 indexed chunk texts. It then applied the model's body-token budget
to the tokenizer's offset mapping, reserving special tokens, to locate the
visible character prefix. The script writes the exact per-span risk evidence
to `reports/rag_embedding_truncation_audit.json` and the human-readable result
to `reports/rag_embedding_truncation_audit.md`.

| Metric | Result |
|---|---:|
| Mean / median tokens | 648.9 / 659 |
| p90 / p95 / p99 / maximum | 752 / 782 / 849 / 979 |
| Chunks within 256 tokens | 1 (0.0253%) |
| Chunks truncated | 3,958 (99.9747%) |
| Mean truncated tokens, all chunks | 392.9 |
| Mean truncated tokens, truncated chunks only | 393.0 |
| Maximum truncated tokens | 723 |
| Accepted DRAFT spans, any matched chunk loses evidence | 40 / 55 |
| Accepted DRAFT spans, no fully visible matching chunk | 35 / 55 |
| Accepted DRAFT spans, entirely beyond window in all matches | 33 / 55 |

These span-risk counts reflect the present DRAFT labels and their current
source-span/chunk mapping. Independent review may add or adjust spans, but it
cannot make the measured 99.97% chunk truncation disappear. The audit does not
assume characters are tokens. A test compares its computed visible prefix
with actual `tokenizer(..., truncation=True, max_length=256)` on a current
indexed chunk.

## Existing retrieval baseline and candidate-pool control

Variant **A** is the unchanged base model and current indexes. Existing
fixed-seed source-span diagnostics on 49 evaluable **DRAFT** questions report
raw dense MRR **0.158**, Hit@1/3/5 **10.2/14.3/18.4%**, and
Recall@10/20/50 **32.7/43.9/62.9%**. These are diagnostic values only; they
are not independently reviewed true relevance scores. Current reranked metrics
are available in `reports/rag_retrieval_v1_draft_baseline.json` but are not the
primary bi-encoder measure. Original dense mean latency was **15.8 ms** in
that run; this task did not benchmark model variants.

`scripts/analyze_rag_candidate_union.py` reuses captured current-model
candidates without re-embedding or reranking. It preserves original dense
Top-50, appends expansion candidates in their captured admission order,
deduplicates, and caps the experimental union at 80. With identical embeddings
and draft labels:

| Candidate pool | Mean size | Full-pool Hit | Full-pool span Recall |
|---|---:|---:|---:|
| Original dense Top-50 | 50.0 | 65.3% | 62.9% |
| Current expanded admission pool | 20.0 | 49.0% | 46.9% |
| Dense-preserving union, cap 80 | 51.8 | 69.4% | 67.0% |

Expansion recovers accepted evidence for two questions missed by original
dense Top-50, but current admission loses evidence present in other original
Top-50 results. The union is a **candidate-availability oracle**, not a
latency-tested or reranked production proposal. Its details are in
`reports/rag_candidate_union_draft_diagnostic.json`. Candidate-admission loss
must not be attributed to the embedding model.

## Training, data, and evaluation status

| Requested item | Status after preflight |
|---|---|
| Variant B, generic NQ + SQuAD | Not prepared or trained |
| Variant C, LuminaR domain only | Not prepared or trained |
| Variant D, generic then domain | Not prepared or trained |
| Domain examples/books/categories/positives/negatives | 0 / 0 / none / 0 / 0 |
| Domain training/validation book split | Not assigned; no examples generated |
| Protected TEST books | `OL15933082W`, `OL44512357W`, `OL27471326W`, `OL42479046W`; no training data was created from any book |
| Decontamination | 0 before, 0 removed, 0 after; no training file exists to scan |
| Training-data quality sample | Not applicable; no NQ/SQuAD/domain examples or negatives exist |
| NQ/SQuAD passage construction and loss choice | Deferred until the input/index gate is resolved |
| Training duration, checkpoints, peak training RAM/VRAM | Not applicable; training did not start |
| New model sizes and isolated evaluation indexes | Not applicable; no model was trained or index built |
| B/C/D dense metrics, reranker compatibility, latency, before/after | Unavailable; no trained variants |

The existing 50 evaluation questions were not used for training. The four
book-group TEST works above are explicitly protected for any later domain
pipeline. No draft labels were used to choose a model. The current 50-question
set also has zero reviewed labels, so even a pilot comparison would remain
`DRAFT_ONLY_NOT_FOR_SELECTION`.

## Next gate and commands

Before a fine-tuning pilot, build a separate sentence/paragraph-aware RAG
passage index whose evidence-bearing text fits the 256-token window, keep the
same source provenance, and measure source-span coverage and raw dense
retrieval. Do not replace the production index in that experiment. Independently
review the evaluation labels; then create book-separated training and
validation data, reject TEST-book examples and evaluation-question/accepted-span
leakage, and only then prepare a small NQ-streaming/SQuAD/domain pilot with
explicit cache and versioned model outputs. No production winner can be chosen
from DRAFT-only measurements.

```powershell
Set-Location D:\SDC\LibraryLLM
.\.venv\Scripts\python.exe scripts\audit_rag_embedding_lengths.py
.\.venv\Scripts\python.exe scripts\analyze_rag_candidate_union.py
.\.venv\Scripts\python.exe -m pytest tests\test_rag_embedding_truncation_audit.py -q
```

`datasets/training/README.md` documents the reserved isolated workspace and
gate. Download/prep-only, train-only, and evaluate-model-only commands are not
provided because their scripts and data were deliberately not created after
the decisive preflight result.

## Files and non-regression verification

Added `scripts/audit_rag_embedding_lengths.py`,
`scripts/analyze_rag_candidate_union.py`,
`tests/test_rag_embedding_truncation_audit.py`, this report, both audit
reports, the union diagnostic, and `datasets/training/README.md` plus its six
empty subdirectories. **7 relevant tests passed, 0 failed** (audit and
existing source-span evaluation tests). Two current-model chunks were checked
against actual SentenceTransformer truncation, and the audit's visible prefix
was independently checked with the tokenizer's true truncation output.

No catalogue HNSW or embeddings, catalogue lexical sidecar, Mongo catalogue,
book CRUD synchronization, production RAG chunks/indexes/model/retriever,
cross-encoder reranker, answer-generation LLM, or frozen v8 proxy benchmark
was modified. No external training or model download occurred, and no TEST
data entered training. The remaining limitation is structural: until evidence
is visible to the encoder in an isolated short-passage retrieval variant,
bi-encoder fine-tuning cannot be fairly evaluated against the current
long-chunk index.
