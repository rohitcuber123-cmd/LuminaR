# Vector / index audit

The global catalogue HNSW and KG artifacts are frozen (196 protected entries). Book RAG validates the permanent/global index alongside per-book indexes and chunks via `rag/book_assets.py`. Personal private PDFs build their own `runtime.faiss` and install it temporarily under the resident engine lock, clearing document runtime/cache afterward.

`DocumentService.ingest_document` appends to the legacy flat document index and must not be called for tenant documents. Reuse only its accepted extraction/chunking/embedding primitives, then build an isolated per-asset FAISS artifact. Each chunk and manifest must retain library UUID, asset UUID and content revision. No library PDF enters a global HNSW, global RAG index or another asset index.
