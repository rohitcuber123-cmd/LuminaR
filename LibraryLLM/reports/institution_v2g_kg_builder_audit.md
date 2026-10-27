Part 2G audit completed before tenant implementation. Global builders were inspected, never executed.

| Existing code | Classification | Decision |
|---|---|---|
| knowledge_graph/core.py | REUSE_DIRECTLY | Canonical term and feature identity helpers, typed metadata relationships. |
| knowledge_graph/relations.py | REUSE_DIRECTLY | Author/subject relation labels; no LLM-generated edges. |
| scripts/build_catalogue_graph.py | REUSE_WITH_TENANT_ADAPTER | Pure row/path builder is deterministic but global main/default paths and 128MiB tuning are inappropriate for tenant use. |
| knowledge_graph/data/catalogue.sqlite | GLOBAL_ONLY | Frozen read-only global artifact. Never rebuild or use as a tenant-labelled graph. |
