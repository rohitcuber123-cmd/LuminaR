# Assistant router archive audit

Research is frozen. No evidence was deleted, moved out of reach, resealed or reevaluated.
Normal `existing_qwen` startup uses conditional imports and pays no rejected-router model/worker cost.

## Inventory

| Category | Files | Bytes |
|---|---:|---:|
| A. Production/application source and tests | 437 | 118,314,670 |
| B. Archived experiment source / diagnostic scripts | 246 | 2,066,031 |
| C. Generated model artifacts | 77 | 459,926,234 |
| D. Generated experiment datasets | 14 | 12,270,016 |
| E. Reports/evidence | 2839 | 1,003,426,031 |

These counts cover repository application/research sources and evidence; they exclude the venv, node_modules, caches and frontend build outputs.
Category A includes application source/tests and existing RAG assets; not every file is needed by assistant routing. Category B includes archived scripts and harmless production diagnostics.
The normal assistant runtime depends on `api`, `orchestrator`, `qwen`, `state`, `schemas`, `tools`, `routing`, `kg_routing`, `contextual`, `semantic`, `profiling` and the existing Core/RAG libraries. Models under `assistant/models/router_v*`, training/evaluation packs and old reports are not opened by default initialization. RAG retains its own retrieval/reranker models and existing Qwen.

## Requested experiment scopes

| Scope | Files | Bytes |
|---|---:|---:|
| `assistant/models/router_v3` | 9 | 658,876 |
| `assistant/models/router_v4` | 13 | 91,850,217 |
| `assistant/models/router_v4_candidates` | 26 | 183,699,996 |
| `assistant/models/router_v5` | 3 | 32,589 |
| `training/assistant_router_v3` | 1 | 1,204,026 |
| `training/assistant_router_v4` | 8 | 10,709,036 |
| `evaluation/assistant_router_v5` | 5 | 356,954 |
| `assistant/router_v3` | 1 | 24,930 |
| `assistant/router_v4` | 1 | 20,311 |
| `assistant/router_v5` | 6 | 53,367 |

The V3/V4 source scope includes their `.py` module, rather than requiring a directory.
Logical quarantine is sufficient: explicit EXPERIMENTAL configuration, guarded imports and frozen evidence. No physical relocation breaks archived paths.

## Preservation

Deleted files: 0. Modified archived research evidence (excluding verified append-only live logs): 0.
Four continuing Core/Search/Recommendation/Vite services append to their old V5-named runtime logs. Exact baseline prefixes were verified against the pre-change SHA-256 and copied to `assistant_router_archive_live_log_prefixes/`. Active logs were never truncated. Fixed datasets, model artifacts, seals, experimental router sources and decision reports remain unchanged.

The archived V5 candidate seal still describes its original runtime. Authorized production changes to common executor/API files are recorded separately; no claim that the current production source matches that historical seal.

Full machine inventory: `assistant_stabilization_file_audit.json`. Baseline: `assistant_stabilization_baseline.json`.
