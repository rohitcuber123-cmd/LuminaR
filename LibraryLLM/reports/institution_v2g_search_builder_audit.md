Part 2G audit completed before tenant implementation. Global builders were inspected, never executed.

| Existing code | Classification | Decision |
|---|---|---|
| search/catalogue.py | REUSE_DIRECTLY | Deterministic semantic text and content hashes; descriptive metadata only. |
| search/index_manager.py | REUSE_WITH_TENANT_ADAPTER | Reuse checksum, durable serialization and normalized HNSW concepts; independent UUID generations and tenant-scale parameters. |
| search/embedding_cache.py | REUSE_WITH_TENANT_ADAPTER | Global cache keyed by work_id cannot be shared blindly. Tenant model/schema/text hash cache stays in tenant root. |
| search/luminar_search.py | GLOBAL_ONLY | Frozen resident model/reranker reused as injected primitives; no global ranking edits. |
| search/api.py | REUSE_WITH_TENANT_ADAPTER | Mount independent tenant routes/worker on existing resident Search process. |
| search/maintenance.py | UNSAFE_FOR_TENANT | Global paths/queues/build control cannot be invoked for library jobs. |
