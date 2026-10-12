"""Evidence-based pre-implementation document ownership inventory; no migration."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / 'reports'

SOURCES = [
    ('rag/book_assets.py', 'BOOK_RAG', 'Explicit global work mapping, processed text and validated per-book indexes. No library ownership.'),
    ('rag/services/private_documents.py', 'PERSONAL_PRIVATE', 'Account + session + expiry SQLite ownership; per-document chunks, embeddings and runtime FAISS.'),
    ('rag/services/private_document_routes.py', 'PERSONAL_PRIVATE', 'Authenticated personal upload/list/delete/logout/cache routes; 64 MiB PDF limit.'),
    ('rag/services/local_document_cache.py', 'PERSONAL_PRIVATE', 'Authenticated encrypted device bundles bound to account and pipeline fingerprint; no library promotion.'),
    ('rag/services/knowledge_artifacts.py', 'PERSONAL_PRIVATE', 'Personal owner-bound SQLite artifacts and source checks; shared study algorithms are reusable, SQL ownership is not.'),
    ('rag/services/document_service.py', 'LEGACY_AMBIGUOUS', 'Flat historical filename-stem documents and append-only document FAISS. Not proof of tenant ownership. Pure parser/chunker/embed methods are reusable.'),
    ('rag/services/private_document_ocr.py', 'LIBRARY_TENANT_CAPABLE', 'Accepted bounded OCR processing is ownership-neutral; caller must namespace input/output.'),
    ('rag/services/document_knowledge.py', 'LIBRARY_TENANT_CAPABLE', 'Shared source-derived study model; no authority or publication by itself.'),
    ('rag/services/knowledge_algorithms.py', 'LIBRARY_TENANT_CAPABLE', 'Existing study tool generators; caller supplies authorized chunks and namespace.'),
    ('rag/services/book_access.py', 'BOOK_RAG', 'Permanent/global source validation; work identity cannot authorize institution PDFs.'),
    ('rag/api.py', 'GLOBAL', 'Resident existing engine dispatches personal documents and authorized Book RAG. No library asset capability at baseline.'),
    ('assistant/schemas.py', 'GLOBAL', 'Selected context is WorkID-based; personal PageContext.document_id separately typed. No library asset target.'),
    ('assistant/selected_context.py', 'GLOBAL', 'Bounded global book metadata selection; not a document ownership or tenant retrieval guard.'),
]


def main():
    table = ['| Source | Classification | Finding |', '| --- | --- | --- |']
    for source, classification, finding in SOURCES:
        assert (ROOT / source).exists()
        table.append(f'| `{source}` | {classification} | {finding} |')
    common = '\n'.join(table)
    (REPORTS / 'institution_v2f_document_rag_audit.md').write_text('# Existing document / RAG audit\n\nAudit captured before Part 2F source changes. Ownership classification follows persisted identities, not memberships of an uploader.\n\n' + common + '\n\nTemporary ingestion staging is TEMPORARY. Unattributed files/registrations are UNKNOWN_REVIEW_REQUIRED until explicit evidence. Neither category gains visibility or gets auto-migrated.\n', encoding='utf8')
    (REPORTS / 'institution_v2f_storage_audit.md').write_text('# Storage audit\n\n`rag/private_documents/registry.sqlite` is the personal registry. At baseline only this file exists under that root; no document subdirectories. Personal artifacts use guarded doc_<hex> directories and are account/session owned. Encrypted local bundles retain account scope.\n\n`rag/documents`, `rag/extracted`, `rag/chunks`, `rag/index` are flat legacy filename-stem namespaces and cannot establish institution ownership. Global Book RAG uses `rag/processed`, `rag/book_chunks`, `rag/book_index/books` and explicit mapping metadata. Existing source filenames are never migration authority.\n\nPart 2F adds a separate canonical library UUID / asset UUID namespace; original filename is metadata. No physical deduplication across tenants, no automatic personal transfer, no public serving of storage paths. Baseline SHA/size/mtime evidence is in institution_v2f_baseline.json.\n', encoding='utf8')
    (REPORTS / 'institution_v2f_vector_index_audit.md').write_text('# Vector / index audit\n\nThe global catalogue HNSW and KG artifacts are frozen (196 protected entries). Book RAG validates the permanent/global index alongside per-book indexes and chunks via `rag/book_assets.py`. Personal private PDFs build their own `runtime.faiss` and install it temporarily under the resident engine lock, clearing document runtime/cache afterward.\n\n`DocumentService.ingest_document` appends to the legacy flat document index and must not be called for tenant documents. Reuse only its accepted extraction/chunking/embedding primitives, then build an isolated per-asset FAISS artifact. Each chunk and manifest must retain library UUID, asset UUID and content revision. No library PDF enters a global HNSW, global RAG index or another asset index.\n', encoding='utf8')
    (REPORTS / 'institution_v2f_ai_context_audit.md').write_text('# AI context audit\n\nThe production Assistant selected context resolves global WorkID metadata; personal PDF selection uses session-owned document IDs. Its string syntax admits opaque IDs, but a library asset UUID or filename does not authorize a global book record and cannot acquire tenant authority through selected_work_ids. The schema has no typed library asset target or library ownership field.\n\nReuse existing resident Qwen and document retrieval via an explicit library asset page/API. Global Assistant does not enumerate libraries or search assets. Authorization must precede file/chunk/index/cache access and be rechecked before returning generated output. Dedicated source context retains canonical library/asset identity.\n\nTyped library assets in the global Select for AI list are deferred under the request\'s Phase 20 allowance because its current router/schema supports global book selections and personal session document IDs. Explicit per-asset document Q&A and shared Knowledge Tools provide the permitted library document interaction without changing the frozen router.\n', encoding='utf8')
    print(json.dumps({'classified_source_types': len(SOURCES), 'reports': 4, 'historical_ownership_inferred': False}))


if __name__ == '__main__':
    main()
