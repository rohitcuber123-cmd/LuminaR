# Document ingestion, chunking, persistence and private QA

## Active upload workflow

`LLMPage` → `uploadRAGDocument` → POST `/rag/upload` → `install_private_documents.upload` → `PrivateDocuments.ingest` → `DocumentService.extract_pdf/create_chunks/embed_chunks` → private FlatIP publication → return source ID → selected `/rag/ask` → answer and page/chunk source objects.

The API accepts `.pdf` filenames under 256 characters, strips directory components, rejects empty bytes, bounds streamed input by `MAX_BYTES` (64 MiB default, configurable through `KNOW_MORE_CACHE_MAX_BUNDLE_BYTES`), and checks `%PDF-`. Parser failures propagate; magic/extension checks are not a full malware/content validator. It requires an authenticated user with unexpired, unrevoked `sid`. Parsing/embedding/publication run in a threadpool while holding the inference lock. This is synchronous preparation, not a durable background job.

`PrivateDocuments.begin:84–93` allocates `doc_<32-hex-UUID>`, stores an INGESTING registry row and creates a bounded directory. `ingest:112–138` writes original bytes, extracts page records, restricts pages to 1–10,000 and chunks to 1–20,000, saves extraction, embeds and publishes. Failure purges partial assets. A zero-text scanned PDF fails the usable-chunk condition.

## Extraction is not OCR

`document_service.py:248–292 extract_pdf` opens the PDF with PyMuPDF `fitz.open`, calls `page.get_text('text')`, cleans whitespace, and preserves 1-based page numbers. It extracts an existing text layer. There is no OCR engine invocation in the traced path. Ingestion is the broader sequence extraction → chunking → embedding → vector publication. LuminaR performs text extraction and ingestion; **OCR is not implemented**. DOCX and TXT web upload are rejected, even though offline book workflows ingest TXT.

## Active chunk algorithms

| Corpus/path | Algorithm | Size/overlap | Metadata | Status |
|---|---|---|---|---|
| Private PDF through `DocumentService.create_chunks` | Page-local fixed character windows after clean_text | 3000/400 characters | chunk_id, document_id, filename, page, text | Active upload |
| Registered book `rag/book_ingest.py` | Character windows with boundary/chapter handling; processed full text | 3000/400 characters | work/document ID, chapter, character offsets, chunk index, title/author | Current book_chunks builder used by embed.py |
| `rag/chunk_books.py:83–158` | Paragraph/sentence-aware character splitter | 1800/300 characters | source offsets/chapter | Older alternative writes rag/chunks; do not conflate with current book_chunks |
| `rag/ingest.py` | PDF page extraction + fixed characters | 3000/400 | page/source | Offline legacy document preparation |
| `rag/experimental_chunker.py:chunk_source` | Token-budget and source-span variants | Parameterized token limit/overlap | variant, source hash, stable span ID | EXPERIMENTAL |

PDF chunk IDs are document prefix plus sequential six-digit counter (`DocumentService.create_chunks:343–392`), so source changes/reuploads do not preserve identity. Each PDF has its own UUID and index. Overlap is within a page and does not bridge page boundaries. Chapter/page provenance aids source display, but fixed windows do not understand headings, tables, columns or semantic units. Explicit neighbor expansion was not found in the active PDF retrieval path; book heuristics may promote diverse/chapter evidence but are not a general adjacent-chunk reader.

Both `embed_chunks:443–466` and book `embed.py` encode local MiniLM text in batches of 32, normalized float32. The encoder's token limit is shorter than many 3000-character chunks. An existing book truncation artifact reports 3958 of 3959 chunks over 256 tokens; that result applies to its historical corpus, not a new measurement of every PDF. Proposed change: tokenizer-budgeted chunks with offsets and independent quality evaluation, not simply increasing a character constant.

## Persistence, isolation and deletion

`rag/private_documents/registry.sqlite` stores id/owner/sid/expires/state/cache_id/JSON metadata. Per-document files hold original PDF, extracted.json, chunks.json, vectors.npy and runtime.faiss. `publish:95–110` writes a separate `IndexFlatIP(384)` and changes state to ACTIVE after assets are built. Chunk text/vector data is not stored in MongoDB. Owner and session scope are enforced in `owned:66–72`, not inferred from frontend selection.

Before a query, `PrivateDocuments.selected:198–209` loads that document's graph/metadata/text into transient retriever state; it clears them in finally. API inference lock serializes this shared mutable state. `clear_runtime` also prevents private PDF metadata from remaining in global retrieval. This source design supports session isolation, with tests in `test_private_document_cache.py`; multiprocess/machine deployments need explicit storage/lifecycle design and concurrency tests.

`purge:211–223` marks DELETING before directory removal and registry deletion; failures leave access disabled for sweeper retry. Logout revokes first, then deletes session documents; expiry/revocation/interrupted artifacts are swept at startup and periodically. Secure physical erasure/backups/storage snapshots are **CANNOT VERIFY FROM CURRENT IMPLEMENTATION**; deletion code does not establish forensic erasure.

Regular upload hashes bytes but creates a new UUID each time; no same-content deduplication path was traced. Cache restore is idempotent within owner/session/cache ID. Permanent book assets remain a separate registry and are not removed by private session cleanup.

## Device cache

`LocalDocumentCache` uses per-owner HKDF-derived AES-GCM keys, opaque owner scope, authenticated header, format/key version, source/processing fingerprint and bounded bundle validation. Bundles contain prepared chunks, vectors and source maps, not an active catalogue membership. Browser `LocalDocumentCacheRepository` stores ciphertext in OPFS when available, otherwise IndexedDB; defaults are 10 documents/128 MiB. A restore decrypts/validates server-side, allocates a new session document, publishes the saved vectors without reparsing/re-embedding, and returns a new active ID. Master key is server-only; key custody/backups require deployment design. Code default is disabled; local nonsecret flag is enabled, actual readiness untested.

## Proposed institution documents and experiments

Personal PDF ownership should remain separate from a library's shared document ACL. Add explicit source type and optional library/holding/dataset/generation fields; authorize scope before resolving any cached artifact. A cached document from L must not restore into another library's shared index based on a client parameter. Test PDF text/no-text, malformed/oversized files, duplicate upload, expiry/logout, another user/session, cache corruption/wrong key/version, concurrent document switching, and scoped citation output. Compare 128/224/256-token variants and 0/32/64 overlap, evaluate source-span coverage, answer correctness/groundedness, prompt tokens, preparation latency/RSS, retrieval latency and refusal rates. Results: **NOT YET MEASURED for the proposed variants and institution scope**.
