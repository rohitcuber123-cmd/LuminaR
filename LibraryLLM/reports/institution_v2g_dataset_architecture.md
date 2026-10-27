# Tenant dataset generations

Canonical `institution_library_books` are the ownership source. Every source row retains `library_book_id`, `library_id`, optional `global_work_id` and ACTIVE status. Local-only, linked, Physical, Online and Both records are eligible. Holdings or public global work IDs do not define book identity. Document bytes/chunks, RAG internals and member activity are excluded.

Existing linked public work metadata can fill missing descriptive authors, subjects, description and publication year. Local title and local nonempty fields win. Deterministic NFKC/whitespace normalization, bounded metadata and sorted IDs/terms produce a schema-versioned SHA-256 fingerprint. Only these indexed fields make an artifact stale. Loan and stock changes do not trigger a metadata rebuild.

Generations have UUIDs, per-library sequence, source fingerprint, eligible/local/linked/format counts, creator/time, schema and READY/FAILED state. Snapshot files and DB records become immutable after READY. Search/KG can reuse a verified snapshot for the same source fingerprint. Limits: 50,000 records, 64 MiB encoded dataset. Empty generations remain EMPTY and never build a pretend global index.

Build authorization and snapshot publication revalidate active ADMIN membership and lifecycle under the existing canonical tenant barrier. No accepted inventory or circulation business logic was duplicated.
