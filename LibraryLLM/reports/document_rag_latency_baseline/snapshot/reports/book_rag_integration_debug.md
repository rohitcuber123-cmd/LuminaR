# Book RAG Integration Debug — Global Failure

> [!CAUTION]
> **ROOT CAUSE: `INDEX_DATASET_MISMATCH`** — The frontend shows modern bestsellers from the catalog DB. The RAG index contains only classic public-domain literature. These are two completely different datasets with **zero overlap**. Every book-specific query will fail.

## Request

Every Library Book selected in the "Know More" sidebar produces:
> "I couldn't find enough information in this book to answer this question."

Tested with: Atomic Habits, The 48 Laws of Power, It Ends With Us, Rich Dad Poor Dad, and others.

## Frontend Payload

When `selectedDocumentId = "OL17930368W"` (Atomic Habits) and the user asks "What is this book about?":

```json
{
  "query": "What is this book about?",
  "depth": "normal",
  "document_id": "OL17930368W"
}
```

The frontend correctly sends `document_id`. The `work_id` field is not sent separately — the backend handles aliasing.

## Received RAG Request

In `api.py`, the `RAGRequest` model receives:
- `document_id = "OL17930368W"`
- `work_id = None`
- `query = "What is this book about?"`

The engine is called with `engine.ask(question=query, depth=depth, document_id="OL17930368W", work_id=None)`.

## Retriever Routing

In `retriever.py`, the `search()` method processes the request:

1. `_is_uploaded_document("OL17930368W")` → **False** (not in the set of uploaded PDF document IDs)
2. Backwards compatibility: `work_id = document_id = "OL17930368W"`
3. Since `work_id` is truthy → `_search_book(work_id="OL17930368W")` is called
4. `_load_book_index("OL17930368W")` tries to open `book_index/books/OL17930368W.index`
5. **`FileNotFoundError`** — file does not exist
6. Returns **0 results**

> [!IMPORTANT]
> The routing logic itself is **correct**. It correctly identifies this as a book (not an uploaded PDF) and correctly routes to book-specific search. The problem is that the target book simply doesn't exist in the index.

## Book Index Verification

| Property | Value |
|---|---|
| Global FAISS index | `rag/book_index/rag.index` |
| Global metadata | `rag/book_index/rag_metadata.json` |
| Vectors | 3,946 |
| Dimension | 384 |
| Metadata entries | 3,946 |
| Per-book indexes | 17 (in `book_index/books/`) |
| Metadata ID field | Both `work_id` and `document_id` contain the same Open Library work ID |

### Books Actually in the RAG Index

| work_id | Title | Author |
|---|---|---|
| OL15933082W | The Strange Case of Dr. Jekyll and Mr. Hyde | Robert Louis Stevenson |
| OL17494673W | The Adventures of Sherlock Holmes | Arthur Conan Doyle |
| OL27039837W | The Time Machine | H. G. Wells |
| OL27471326W | Moby-Dick | Herman Melville |
| OL28944494W | The Adventures of Tom Sawyer | Mark Twain |
| OL33027136W | The War of the Worlds | H. G. Wells |
| OL33723557W | The Importance of Being Earnest | Oscar Wilde |
| OL35758281W | Adventures of Huckleberry Finn | Mark Twain |
| OL36979234W | Jane Eyre | Charlotte Bronte |
| OL38619874W | Alice's Adventures in Wonderland | Lewis Carroll |
| OL41470186W | Great Expectations | Charles Dickens |
| OL42479046W | The Metamorphosis | Franz Kafka |
| OL43032614W | A Tale of Two Cities | Charles Dickens |
| OL44512357W | The Picture of Dorian Gray | Oscar Wilde |
| OL45326637W | Frankenstein | Mary Shelley |
| OL66524W | Pride and Prejudice | Jane Austen |
| OL85892W | Dracula | Bram Stoker |

### Books Shown in Frontend Sidebar

| Title | Author | In RAG Index? |
|---|---|---|
| Atomic Habits | James Clear | ❌ |
| The 48 Laws of Power | Robert Greene | ❌ |
| It Ends With Us | Colleen Hoover | ❌ |
| Rich Dad, Poor Dad | Robert T. Kiyosaki | ❌ |
| The Subtle Art of Not Giving a F... | Mark Manson | ❌ |
| Control Your Mind and Master Y... | Eric Robertson | ❌ |
| Um casamento arranjado | Zana Kheiron | ❌ |

**Overlap: 0 out of 7 frontend books exist in the RAG index.**

## Book-Specific vs Global Comparison

| Test | document_id | Index Searched | Results | Notes |
|---|---|---|---|---|
| Global | null | Global book + uploaded doc | 10 | Returns classic lit + uploaded PDFs |
| Atomic Habits | OL17930368W | Per-book (attempted) | 0 | `FileNotFoundError` — index missing |
| Any frontend book | any catalog work_id | Per-book (attempted) | 0 | Same failure for every frontend book |

## Root Cause

**`INDEX_DATASET_MISMATCH`**

The RAG book index was built from **public-domain classic literature** (likely Project Gutenberg texts). The frontend "Library Books" sidebar fetches **modern bestsellers** from the backend catalog database (MongoDB, via `getPopularBooks()` API). These are two completely separate, non-overlapping datasets.

The retriever, the routing logic, the reranker, the Fast Filter, the validator, and V8 are all functioning correctly. The failure occurs because the requested book literally does not exist in any index.

## Recommended Fix

> [!IMPORTANT]
> Three options, in order of implementation simplicity:

**Option A (Frontend-side, easiest):** Change the "Library Books" sidebar to only show books that are actually in the RAG index. Create a new `/rag/books` endpoint that returns the 17 indexed work_ids/titles, and use that list instead of `getPopularBooks()`.

**Option B (Backend-side, most complete):** Ingest the catalog bestsellers into the RAG book index. This requires obtaining their full text, which may not be freely available for copyrighted modern books.

**Option C (Hybrid):** Show both sections — "RAG-Indexed Books" (the 17 classics, available for Q&A) and "Catalog Books" (the bestsellers, visually marked as not yet available for Q&A).

## V8 Modification Status

**V8 was NOT modified.** No changes were made to:
- V8 intent logic
- Fast Filter thresholds
- Validator schema
- Qwen generation settings
- Retrieval ranking
- Any source code files
