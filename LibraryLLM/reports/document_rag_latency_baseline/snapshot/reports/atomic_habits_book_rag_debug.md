# Atomic Habits Book RAG Debug

## Request
The RAG pipeline failed to retrieve information for the query "What is the 1% rule and how does it compound over time?" when the book "Atomic Habits" (work_id/document_id: OL17930368W) was selected in the frontend.

## Frontend Payload
The frontend sends the following request to `/rag/ask`:
```json
{
  "query": "What is the 1% rule and how does it compound over time?",
  "depth": "normal",
  "document_id": "OL17930368W"
}
```

## Received RAG Request
The `RAGRequest` model in `api.py` receives `document_id="OL17930368W"`. For backwards compatibility, the retriever later assigns `work_id = document_id` since `work_id` is None.

## Book Identifier Verification
The request treats `OL17930368W` as a document identifier. The retriever (`rag/retriever.py`) supports both uploaded PDFs (filename stem) and Open Library `work_id` identifiers. It checks `_is_uploaded_document` and routes the search to `_search_book(work_id="OL17930368W")`.

## Book Index Verification
Verification against the global RAG metadata (`rag_metadata.json` which contains 3,946 chunks across 17 books) reveals that **0 entries** match the title "Atomic Habits" or the identifier `OL17930368W`. The book simply does not exist in the retriever's FAISS index. 

## Raw Retrieval
Because `OL17930368W.index` does not exist in the `book_index/books` directory, `_search_book()` catches a `FileNotFoundError` and returns `0` results.
- **Top Retrieval Result**: None (No chunks retrieved)
- **"1% rule" evidence retrieved**: No

## Reranking
- Number of candidates sent to CrossEncoder: 0
- CrossEncoder scores: N/A

## Fast Filter
- Candidate count entering: 0
- Candidate count leaving: 0

## Validator
- Validator called: No
- Final verdict: `NOT_SUPPORTED`

## Generation
With 0 valid context chunks provided, the Qwen language model correctly adheres to its grounded instructions, generating the fallback response: "I couldn't find enough information in this book to answer this question."

## Book-Specific vs Global Comparison
A global search (`document_id = None`) for the same query returns 10 results, but none are from Atomic Habits (since it is entirely missing from the index). Top global results were from unrelated technical documents (`Unit-1 Software Engineering`, `CN_UNIT_1_NOTES`, `AI-CSE-III-I-GRU-NOTES`).

## Root Cause
**BOOK_NOT_IN_INDEX**

## Recommended Fix
Run the ingestion/indexing script to add "Atomic Habits" (OL17930368W) to the RAG database so that its text chunks are embedded and searchable.
