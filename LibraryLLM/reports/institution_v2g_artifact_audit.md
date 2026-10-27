Part 2G audit completed before tenant implementation. Global builders were inspected, never executed.

| Existing code | Classification | Decision |
|---|---|---|
| search/index_manager.py | REUSE_WITH_TENANT_ADAPTER | Private generations, fsync, checksum validation and atomic pointer principles. |
| backend/services/library_asset_service.py | REUSE_WITH_TENANT_ADAPTER | Canonical UUID path containment and symlink rejection; asset corpus remains distinct. |
| rag/services/library_asset_pipeline.py | GLOBAL_ONLY | Document chunks/runtime FAISS are not catalogue sources. |
| backend/services/institution_repository.py | REUSE_DIRECTLY | Canonical tenant barrier and durable mutation context. |
