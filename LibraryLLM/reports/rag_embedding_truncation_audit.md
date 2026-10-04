# LuminaR RAG embedding truncation audit

Model: `sentence-transformers/all-MiniLM-L6-v2`; SentenceTransformer effective window: **256 tokens including special tokens**; embedding dimension: **384**.
Tokenizer model_max_length advertises 256; the SentenceTransformer module setting controls actual encoding.

| Statistic | Value |
|---|---:|
| Chunks | 3,959 |
| Mean / median tokens | 648.9 / 659.0 |
| p90 / p95 / p99 / max | 752 / 782 / 849 / 979 |
| At or below 256 | 1 (0.0%) |
| Truncated | 3,958 (100.0%) |
| Mean excess tokens, all / truncated only | 392.9 / 393.0 |
| Maximum excess tokens | 723 |

Of 55 accepted draft evaluation spans, 40 have at least one matching chunk whose answer evidence extends beyond the usable window; 35 have no fully visible matching chunk; 33 are entirely beyond the window in every matching chunk.

This audit reads production chunks and the DRAFT evaluation spans. It does not change production chunking, embeddings, or indexes. Span risks may change when labels are independently reviewed.
