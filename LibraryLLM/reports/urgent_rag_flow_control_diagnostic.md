# Urgent flow control RAG diagnostic

DOCUMENT_TEXT_EXTRACTED: YES

FLOW_CONTROL_TEXT_PRESENT: YES

MATCHING_PAGES: 1, 2, 3, 4

MATCHING_CHUNKS:
- library:e6d1e5b4-c48f-4b47-b96a-656a676fb8ae:asset:e1787913-d3f5-46c8-ac3a-af0b5dd9d9fc:generation:27dd8d41-f0be-4cbb-8579-0e23813552dc_000001
- library:e6d1e5b4-c48f-4b47-b96a-656a676fb8ae:asset:e1787913-d3f5-46c8-ac3a-af0b5dd9d9fc:generation:27dd8d41-f0be-4cbb-8579-0e23813552dc_000002
- library:e6d1e5b4-c48f-4b47-b96a-656a676fb8ae:asset:e1787913-d3f5-46c8-ac3a-af0b5dd9d9fc:generation:27dd8d41-f0be-4cbb-8579-0e23813552dc_000003
- library:e6d1e5b4-c48f-4b47-b96a-656a676fb8ae:asset:e1787913-d3f5-46c8-ac3a-af0b5dd9d9fc:generation:27dd8d41-f0be-4cbb-8579-0e23813552dc_000004

## Direct definition evidence

Page 1 contains the complete definition, wholly present in chunk `library:e6d1e5b4-c48f-4b47-b96a-656a676fb8ae:asset:e1787913-d3f5-46c8-ac3a-af0b5dd9d9fc:generation:27dd8d41-f0be-4cbb-8579-0e23813552dc_000001`:

> Flow control is a set of procedures that tells the sender how much data it can transmit before it must wait for an acknowledgment from the receiver.

It is the first paragraph after the heading and is not split across chunks. Page metadata matches source extraction; all chunks are nonempty. No extraction or chunking repair is required.

## Scoped artifact integrity

The original selected private document was `doc_dfda625ee70a4680b9460024909f4c3f` with filename `CN UNIT-2 NOTES.docx.pdf`. Its session artifact expired and was swept before offline capture. The offline audit therefore uses the already authorized member asset with the identical PDF SHA-256 `2c7843be7288b9156b2893b5bea631f9c74bbce64d60a7cfa6da3a46e22d8f4f`. The live pre-change API response is retained in `urgent_rag_backend_baseline.json`.

Library: `e6d1e5b4-c48f-4b47-b96a-656a676fb8ae`. Asset: `e1787913-d3f5-46c8-ac3a-af0b5dd9d9fc`. Active generation: `27dd8d41-f0be-4cbb-8579-0e23813552dc`.

The member source PDF checksum equals the manifest checksum. All four manifest artifact digests match. Extraction contains 29 pages, chunk metadata contains 29 chunks, vectors have shape [29, 384], and the selected runtime FAISS index contains 29 vectors of dimension 384. All chunk document/library/asset/generation identities match the selected artifact. The runtime and manifest are coherent; no stale index or document rebuild is indicated. No source PDF or index was changed by this audit.

## Search term findings

Search uses lowercase words and normalizes punctuation/whitespace for diagnosis; original extracted text is preserved.

| Term | Matching pages |
| --- | --- |
| flow control | 1, 2, 3, 4 |
| flow-control | 1, 2, 3, 4 |
| flow | 1, 2, 3, 4, 7, 11, 14 |
| receiver | 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 17, 19, 26, 27, 29 |
| sender | 1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 26, 29 |
| sliding window | 8, 9 |
| stop and wait | 1, 3, 4, 5, 8 |
| acknowledgement | 6, 8, 27 |
| acknowledgment | 1, 5, 6, 7, 10, 11, 16, 17, 19, 25, 27 |
| buffer | 1, 6, 12 |

## Pre-change retrieval and grounding

Exact query: `what is flow control`. Production normalization before repair only trims the query. Existing cached MiniLM and cross-encoder were run on CPU with `local_files_only=True`. Qwen and global catalogue indexes were never constructed by this offline audit. The reranker receives the real intent captured from the pre-change API, not an invented substitute.

The complete page 1 definition ranks 1 in semantic top 15, 1 in reranked top 15, and 1 in the final seven-chunk context. Thus semantic retrieval and context packing both preserve the relevant evidence. The existing validator evaluates the first three context chunks, including page 1, yet the real baseline result is `NOT_SUPPORTED` with answer:

> The provided passages do not establish the requested information about flow control.

Baseline sources are pages 1, 2, 3, 4, 7, 18, 6. The refusal does not make supported factual claims, so these candidate/context citations do not establish an answer.

ROOT CAUSE: The claim-oriented grounding validator falsely rejects a directly supported document definition. Retrieval does not miss the correct chunk. A document-scoped definition evidence context and the existing informational validation path are the appropriate narrow repair. A hybrid retrieval addition or global index rebuild is not justified by this reproduction.

EXTRACTION_FIX_REQUIRED: NO

RETRIEVAL_FIX_REQUIRED: NO

GROUNDING_FIX_REQUIRED: YES

Full semantic scores, reranked scores, snippets, exact final context, and validator input are recorded in `urgent_rag_retrieval_trace.json`.

## Post-change retrieval, grounding, and verification

### Implemented Fix
1. `rag/document_grounding.py`:
   - `normalize_document_query`: Lowercase, strips punctuation and collapses whitespace.
   - `document_definition_topic`: Recognizes bounded definition queries ("what is", "define", "explain"). Excludes compound, causal, conditional, and negated forms.
   - `definition_matches`: Matches explicit substantive definition sentences (`<topic> is/are/means/refers to/is defined as <definition>`) of at least 6 words.
   - `select_definition_evidence`: Filters candidates within the authorized document, prioritizing explicit definition chunks (capped at 3).
   - `definition_category`: Emits `document_definition` when definition evidence exists within the document candidates.
2. `rag/qa.py`:
   - Detects document/private/asset scopes (`is_document = bool(document_id and not valid_work_id(document_id))`).
   - Prioritizes definition evidence before building context.
   - Passes `informational_category="document_definition"` to `self.llm.validate_evidence()` when explicit definition evidence exists, routing through the existing evidence-sufficiency validation prompt rather than claim-oriented adversarial validation.
   - Keeps validation active (no FAST_ACCEPT bypass).
   - Returns empty citations `[]` for document `NOT_SUPPORTED` responses.

### Post-change Results
- Query: `what is flow control`
  - Verdict: `SUPPORTED`
  - Answer: "Flow control ensures the sender knows when to slow down its transmissions based on the receiver’s processing capacity and available buffers."
  - Citations: `[1]` (Page 1 only; extraneous pages 2, 3, 4, 7, 18, 6 eliminated)
- Query variants tested:
  - `define flow control` → `SUPPORTED`, citations `[1]`
  - `explain flow control` → `SUPPORTED`, citations `[1]`
  - `What is Flow Control?` → `SUPPORTED`, citations `[1]`
- Additional document definition test:
  - `what is sliding window` → `SUPPORTED`, citations `[9]` (Page 9 explicit definition)
- Authorization and cross-document boundary:
  - Wrong library asset access returns HTTP 404 (no leak).
  - Cross-user/session document selection fails with 404 before opening index.
- Regression suite:
  - 185 passed in pytest (`tests/test_urgent_document_rag.py`, `tests/test_document_rag_latency.py`, `tests/test_private_document_cache.py`, `tests/institution_v2f/test_asset_pipeline.py`).

