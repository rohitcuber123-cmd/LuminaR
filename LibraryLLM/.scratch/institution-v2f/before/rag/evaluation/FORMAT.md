# RAG retrieval evaluation v1

`rag_retrieval_eval_v1.json` is independent of the current FAISS ranking. Each
question has a stable ID, selected book, category, difficulty, ambiguity class,
review status, and one or more source-text evidence spans. Spans are half-open
character offsets into the processed book after `rag.book_ingest.clean_text`.
`text_excerpt` and `source_sha256` make them reviewable and reject stale labels.
`source_map_v1.json` maps existing chunk IDs to offsets; future experimental
chunkers must make their own map against the same normalized source.

An accepted passage with grade 2 directly answers the question. Grade 1 is
supporting context; it can contribute to later graded metrics but **does not**
count for primary Hit@k, MRR, or Recall@k. Multiple grade-2 spans are allowed.
The retrieved chunk receives grade 2 only when it covers at least 80% of a
grade-2 source span and at least 40 characters of it (or the entire span when
shorter). This tests source coverage, not keyword coincidence. For spans crossing
a boundary, `neighbor_allowance` records whether previous/next context could
cover the answer. `adjacent_chunk_coverage` names which previous/current/next
indexed chunks individually cover the span under the primary rule; the other
matches remain in `current_chunk_matches`. Neighbor allowances do not boost
the chunk's primary rank. A duplicate overlap chunk may count if it covers the
same span. Recall@k counts accepted grade-2 **spans**, not duplicate chunks.

All labels created by the assistant are `DRAFT`: the source and offsets are
verified, but **zero human reviewers** have independently judged completeness
or relevance. They may be used for exploratory baseline diagnostics, not final
configuration selection. A human reviewer may mark a case `REVIEWED` only after
checking the source, all reasonable answer-bearing spans, and the question's
premise. The legacy v8 keyword benchmark stays unchanged and is recorded as
`legacy_proxy_v8` in dataset provenance.

The split is deterministic by book group to prevent near-duplicate questions
from the same passage appearing in both DEV and TEST. TEST is kept untouched
for future final comparison; no ranking configuration is selected on it while
labels remain DRAFT.
