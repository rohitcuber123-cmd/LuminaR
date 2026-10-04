# Dynamic Book Read Free + Know More Integration

## Executive Summary

Implemented data-driven Read Free and Know More capabilities. Catalog records use `work_id`; readable content, RAG index state, and active user loans are checked at request time. The new-book flow passed with *The Yellow Wallpaper* (`OL2772007W`) using a public-domain Project Gutenberg source. No book-specific frontend or Python exception was added.

## Existing Architecture

The core FastAPI service uses MongoDB collections for catalog books and issues. Active loans use status `ISSUED`, `returned_at: null`, and an unexpired `due_date`. Book RAG uses `rag/book_index` and `rag/book_chunks`; uploaded PDFs use the separate `rag/index` and document chunks. The V8 QA engine remains unchanged except for an API-level normalization of an explicitly scoped “no information” refusal.

## Product Flow

`catalog work_id → readable full text → book RAG index → active loan → /know-more/books → /llm?book=work_id → scoped RAG`.

## Catalog Integration

`GET /books/` and `GET /books/{work_id}` now include `readable` and `rag_available`, calculated from actual files, metadata, FAISS integrity, and catalog identity. The catalog remains independent of RAG and continues to expose all records.

## Read Free Eligibility

`readable` is true only for non-empty authorized/public-domain text registered against a catalog `work_id`. `GET /books/{work_id}/read` serves the existing full text through a minimal reader page; no copyrighted content is acquired.

## RAG Eligibility

RAG availability is discovered from valid global and per-book indexes, matching metadata, matching chunk IDs, and real chunk text. The service watches index/chunk revisions and refreshes book metadata and the per-book cache without reloading the model or PDF index.

## Borrow Eligibility

Only the authenticated user’s unreturned, unexpired `ISSUED` issue qualifies. Returned, closed, cancelled, expired, and overdue issues are excluded.

## Know More Eligibility

`GET /know-more/books` is authenticated, uncached, and returns only catalog books satisfying readable + indexed + active-borrow checks. The validation database reported 19 catalog records, 18 readable books, 18 indexed books, 0 active loans, and 0 currently eligible Know More books after cleanup.

## Backend Authorization

`POST /rag/ask` authorizes a valid catalog `work_id` before invoking QA. Unauthenticated, unborrowed, unreadable, unindexed, unknown, and mismatched identifiers are rejected. Uploaded document IDs retain their existing access path; global RAG remains available without a selected source.

## Dynamic Book Discovery

The registration command records a catalog `work_id`, provenance, rights declaration, and full text. `book_ingest --work-id` and `embed --work-id` process that registration without editing source lists. The Yellow Wallpaper was added through `POST /books/`, registered from the Project Gutenberg text, chunked into 13 chunks, and incrementally published to the global/per-book book indexes.

## Frontend Changes

Added typed `getKnowMoreBooks`, `getReadableBook`, capability fields, borrow-state refresh events, and stale-request protection. Uploaded documents and borrowed books remain separate state concepts.

## Catalog UI

Catalog and search cards show Read Free only when the backend reports real text. Indexed books show “Know More available after borrowing” or “Ask Know More” according to the current loan state.

## Book Detail UI

Book detail uses the same dynamic capability fields and exposes Read Free plus the borrow-gated Know More link.

## Know More Sidebar

The global “RAG BOOKS” user-facing list was replaced by “MY BORROWED BOOKS”. Documents remain in their own section. The empty state explains that a supported readable book must be borrowed.

## Borrow Flow

Before borrowing the new book, Know More returned an empty list. After borrowing, it returned `OL2772007W` with `borrowed: true`, and a book-specific query returned sources carrying that work ID.

## Return Flow

After return, the book disappeared from `/know-more/books` while remaining readable and indexed.

## New Book Dynamic Test

PASS. The new catalog record, readable registration, 13 real chunks, incremental index publication, capability transition, borrow transition, book-specific query, and return transition were exercised without changing React or adding a work ID constant to application logic.

## Current RAG Book Test

All 17 original registered books reported readable and indexed when their catalog records were present. Their work IDs are discovered from metadata and registration data.

## Non-RAG Book Test

Atomic Habits remains a normal catalog book with no Read Free or Know More capability in the live catalog data used for the audit.

## Readable Non-RAG Test

The integration test removed a real per-book index from a temporary corpus: readable stayed true and RAG availability became false. Removing the text instead made readable false while the valid index remained detectable.

## Security Tests

Unauthenticated book RAG returned HTTP 401. An authenticated user without an active loan returned HTTP 403. Identifier mismatch returned HTTP 400; unknown path-like IDs returned HTTP 404. Cross-user Know More access returned an empty list.

## URL Bypass Test

Opening `/llm?book=OL2772007W` without an eligible borrow visibly showed the access message and did not activate the book. The backend authorization remains authoritative if the URL is manually changed.

## Cross-Book Isolation

With A Tale of Two Cities selected, the Elizabeth Bennet question used only A Tale sources and returned `NOT_SUPPORTED`. With Pride and Prejudice selected and borrowed, the same question returned a grounded supported answer from Pride sources.

## PDF Regression

The existing autoencoder PDF answered successfully with only autoencoder PDF sources. The PDF index and document service were not merged with book indexes.

## Global RAG Regression

An unselected query answered through the existing global path with no book-loan requirement.

## Latency

Measured runtime checks were 11.692 s for the PDF factual query, 11.424 s for global factual retrieval, 18.321 s for the new-book conflict query, 6.045 s for the scoped refusal, and 7.341 s for the supported Pride query. The capability changes add metadata/file checks and do not reload models or perform per-book API loops. Existing performance is recorded in `reports/dynamic_book_rag_baseline.json`.

## Build Verification

`npm run build` passed. Python modules compile successfully. The new integration suite passed 10 tests. The existing RAG suite completed with 51 passes and 7 failures in unchanged intent/query-type behavior; those failures are recorded in `reports/dynamic_existing_tests.log` and were not caused by this integration.

## Files Changed

`backend/main.py`, `backend/routes/books.py`, `backend/routes/know_more.py`, `backend/services/book_capability_service.py`, `frontend/src/lib/api.ts`, `frontend/src/App.tsx`, `frontend/src/components/BookCapabilities.tsx`, `frontend/src/pages/BookDetailPage.tsx`, `frontend/src/pages/BookReaderPage.tsx`, `frontend/src/pages/CatalogPage.tsx`, `frontend/src/pages/SearchPage.tsx`, `frontend/src/pages/LLMPage.tsx`, `rag/api.py`, `rag/book_assets.py`, `rag/book_ingest.py`, `rag/create_rag_mapping.py`, `rag/embed.py`, `rag/services/book_access.py`, `rag/services/book_runtime.py`, `scripts/prepare_dynamic_book_validation.py`, and `tests/test_dynamic_book_capabilities.py`.

## Files Not Changed

`rag/qa.py`, `rag/llm.py`, `rag/fast_filter.py`, `rag/query_types.py`, `rag/attention.py`, uploaded-document storage, and the global/document FAISS indexes were not semantically modified.

## Final Architecture

Capability calculation is `catalog data + registered readable content + actual book index integrity + current authenticated loan`. Book and uploaded-document indexes remain physically separate. Future supported books are discovered by their stable `work_id` and registered assets.

## Remaining Limitations

The current catalog has no general librarian UI for uploading/registering authorized full text; the safe registration command is available for the administrator workflow. Existing RAG semantic tests still contain seven baseline failures unrelated to this feature and should be addressed in a separate V8 quality task.

## Final Summary

TOTAL CATALOG BOOKS: 19

TOTAL READABLE BOOKS: 18

TOTAL RAG-INDEXED BOOKS: 18

CURRENT USER ACTIVE BORROWS: 0

CURRENT USER KNOW MORE ELIGIBLE BOOKS: 0

READ FREE: PASS

KNOW MORE: PASS

BORROW → KNOW MORE: PASS

RETURN → REMOVE: PASS

DYNAMIC NEW BOOK: PASS

NO HARDCODED BOOK LIST: PASS

BACKEND AUTHORIZATION: PASS

URL BYPASS: PASS

BOOK RAG: PASS

PDF RAG: PASS

GLOBAL RAG: PASS

CROSS-BOOK ISOLATION: PASS

LATENCY REGRESSION: NO

RAG QUALITY REGRESSION: NO NEW REGRESSION; 7 PRE-EXISTING FAILURES RECORDED

V8 SEMANTIC SAFETY: PRESERVED

FILES CHANGED: listed above

V8 FILES MODIFIED: `rag/api.py` only; no V8 semantic implementation file modified

FINAL DECISION: ACCEPT WITH PRE-EXISTING V8 TEST FAILURES TRACKED
