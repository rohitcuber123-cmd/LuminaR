# Existing document / RAG audit

Audit captured before Part 2F source changes. Ownership classification follows persisted identities, not memberships of an uploader.

| Source | Classification | Finding |
| --- | --- | --- |
| `rag/book_assets.py` | BOOK_RAG | Explicit global work mapping, processed text and validated per-book indexes. No library ownership. |
| `rag/services/private_documents.py` | PERSONAL_PRIVATE | Account + session + expiry SQLite ownership; per-document chunks, embeddings and runtime FAISS. |
| `rag/services/private_document_routes.py` | PERSONAL_PRIVATE | Authenticated personal upload/list/delete/logout/cache routes; 64 MiB PDF limit. |
| `rag/services/local_document_cache.py` | PERSONAL_PRIVATE | Authenticated encrypted device bundles bound to account and pipeline fingerprint; no library promotion. |
| `rag/services/knowledge_artifacts.py` | PERSONAL_PRIVATE | Personal owner-bound SQLite artifacts and source checks; shared study algorithms are reusable, SQL ownership is not. |
| `rag/services/document_service.py` | LEGACY_AMBIGUOUS | Flat historical filename-stem documents and append-only document FAISS. Not proof of tenant ownership. Pure parser/chunker/embed methods are reusable. |
| `rag/services/private_document_ocr.py` | LIBRARY_TENANT_CAPABLE | Accepted bounded OCR processing is ownership-neutral; caller must namespace input/output. |
| `rag/services/document_knowledge.py` | LIBRARY_TENANT_CAPABLE | Shared source-derived study model; no authority or publication by itself. |
| `rag/services/knowledge_algorithms.py` | LIBRARY_TENANT_CAPABLE | Existing study tool generators; caller supplies authorized chunks and namespace. |
| `rag/services/book_access.py` | BOOK_RAG | Permanent/global source validation; work identity cannot authorize institution PDFs. |
| `rag/api.py` | GLOBAL | Resident existing engine dispatches personal documents and authorized Book RAG. No library asset capability at baseline. |
| `assistant/schemas.py` | GLOBAL | Selected context is WorkID-based; personal PageContext.document_id separately typed. No library asset target. |
| `assistant/selected_context.py` | GLOBAL | Bounded global book metadata selection; not a document ownership or tenant retrieval guard. |

Temporary ingestion staging is TEMPORARY. Unattributed files/registrations are UNKNOWN_REVIEW_REQUIRED until explicit evidence. Neither category gains visibility or gets auto-migrated.
