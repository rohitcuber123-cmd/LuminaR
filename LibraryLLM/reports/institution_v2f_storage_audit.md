# Storage audit

`rag/private_documents/registry.sqlite` is the personal registry. At baseline only this file exists under that root; no document subdirectories. Personal artifacts use guarded doc_<hex> directories and are account/session owned. Encrypted local bundles retain account scope.

`rag/documents`, `rag/extracted`, `rag/chunks`, `rag/index` are flat legacy filename-stem namespaces and cannot establish institution ownership. Global Book RAG uses `rag/processed`, `rag/book_chunks`, `rag/book_index/books` and explicit mapping metadata. Existing source filenames are never migration authority.

Part 2F adds a separate canonical library UUID / asset UUID namespace; original filename is metadata. No physical deduplication across tenants, no automatic personal transfer, no public serving of storage paths. Baseline SHA/size/mtime evidence is in institution_v2f_baseline.json.
