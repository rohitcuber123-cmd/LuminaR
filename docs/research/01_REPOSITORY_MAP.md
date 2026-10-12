# Repository map and active implementation boundaries

See [00](00_PROJECT_OVERVIEW.md) for audit scope. Paths are relative to `D:/SDC`.

```text
D:/SDC/
├── .git/                              revision history
├── requirements.txt                   broad Python dependency ranges
├── IMPLEMENTATION_CODE_MAP.md          prior documentation; verify against code
├── _lumina_extract/, _updated_extract/ extracted document XML, not application
├── docs/research/                      this audit
└── LibraryLLM/
    ├── .env.example, .env.know-more.example
    ├── requirements.txt, pytest.ini
    ├── backend/
    │   ├── main.py, dependencies.py
    │   ├── database/{mongodb,app_database,metadata}.py
    │   ├── routes/                     auth, books, inventory, issues, renewals,
    │   │                               reservations, fines, activity, saved lists,
    │   │                               staff, notifications, events, KG
    │   ├── schemas/events.py
    │   ├── services/                   persistence and domain logic
    │   ├── utils/                      JWT, authentication limits, security audit
    │   └── scripts/                    migration, import, bootstrap, category/ISBN builds
    ├── frontend/
    │   ├── package.json, package-lock.json, vite.config.ts, tsconfig*.json
    │   ├── src/{App,main}.tsx
    │   ├── src/pages/                  catalogue/search/detail/reader/LLM/profile,
    │   │                               staff, events, experimental KG
    │   ├── src/components/             assistant, books, notifications, events,
    │   │                               related books, document cache, renewals
    │   ├── src/store/                  auth, reader data, assistant, event revision
    │   ├── src/lib/, src/api/core.ts   HTTP clients and browser persistence
    │   └── tests/                     TypeScript/React/Node contracts
    ├── search/
    │   ├── api.py, luminar_search.py, ranked_pages.py
    │   ├── catalogue.py, index_manager.py, embedding_cache.py, sync_queue.py
    │   ├── lexical_{store,build,delta,integration}.py, typo_assistance.py
    │   └── maintenance.py, evaluate_retrieval.py, api_benchmark.py
    ├── rag/
    │   ├── api.py, qa.py, retriever.py, reranker.py, llm.py
    │   ├── evidence.py, fast_filter.py, query_types.py, decoding.py, attention.py
    │   ├── book_assets.py, book_ingest.py, embed.py, clean_books.py
    │   ├── ingest.py, chunk_books.py   older/offline ingestion variants
    │   ├── experimental_chunker.py, evaluation/metrics.py
    │   ├── services/                  private PDF lifecycle, encrypted bundles,
    │   │                               extraction/chunking, book entitlement/reload
    │   ├── books/, processed/, book_chunks/, book_index/
    │   └── private_documents/         runtime registry/artifacts, not public catalogue
    ├── assistant/
    │   ├── api.py, orchestrator.py, schemas.py, tools.py, qwen.py
    │   ├── state.py, routing.py, semantic.py, contextual.py, selected_context.py
    │   └── router_v2*, router_v3.py, router_v4.py, router_v5/, models/
    ├── recommendation/{api,recommendation_service,ranked_pages}.py
    ├── knowledge_graph/{core,topics,relations,metrics}.py, data/
    ├── data_pipeline/
    │   ├── build_master.py and integrity/author-repair utilities
    │   └── ai/                        searchable-text/corpus/embedding builders,
    │                                   FAISS flat/HNSW builders, metadata/teacher evaluation
    ├── scripts/                       launchers, audits, benchmarks, training/evaluation
    ├── datasets/                      master/derived data, training pairs, evaluation labels,
    │                                   HNSW snapshots, SQLite/DuckDB/Parquet/NumPy assets
    ├── training/, evaluation/, benchmarks/
    ├── tests/                         Python tests including auth/events/renewals
    ├── testing/test_brevo.py           separate integration utility
    ├── reports/                       measurements, logs, and historical source copies
    └── docs/backend-review/            previous audit material
```

## How activity was determined

`backend/main.py` explicitly includes the core routers and starts the due-notification worker. `search/api.py` constructs one `LuminaRSearchEngine` and starts its sync worker. `rag/api.py` constructs `LuminaRAG`, installs the default `fast` document adapter, installs `PrivateDocuments`, and installs the assistant. `recommendation/api.py` is a separate app. `App.tsx` determines which pages are routed; the Vite proxy shows which backend each frontend prefix reaches. Import and call traces take precedence over comments such as “production IndexFlatIP baseline” in old offline HNSW builders.

Production-style launchers `scripts/start_assistant_production.ps1` and `scripts/start_events_stack.ps1` explicitly choose `ASSISTANT_ROUTER_MODE=existing_qwen`. Router v3/v4/v5 remain opt-in experimental modes. A process already running with a different launch environment cannot be inferred from these files; **CANNOT VERIFY FROM CURRENT IMPLEMENTATION** for the actual live process configuration.

## Configuration and deployment findings

* `MONGO_URI`, `MONGO_DB_NAME`, `JWT_SECRET_KEY`, Brevo variables, and optional encrypted-document variables are in examples. Examples do not cover every runtime flag.
* `LUMINAR_SEARCH_INDEX_DIR` chooses one catalogue index root. A nondefault Mongo database requires a distinct root (`search/sync_queue.py:120–124`). This is database separation groundwork, not a library registry.
* `LEXICAL_SEARCH_ENABLED=false` and `LUMINAR_LEXICAL_SYNC_ENABLED=false` are code defaults. Neither was present in the inspected safe local flag subset. Inherited process variables can override them.
* `KNOW_MORE_DEVICE_CACHE_ENABLED=false` is the example/code default; the inspected local `.env` sets this nonsecret flag to `true`. Successful service initialization and key configuration were not tested. Secret values were neither collected nor reproduced.
* `LUMINAR_MOCK_LLM` allows explicit placeholder generation; real local Qwen is the default. RAG/search require locally cached models; catalogue embedding generation has CUDA assumptions.
* No tracked Dockerfile, container composition, or CI workflow was found in the file inventory. PowerShell launchers use hard-coded `D:/SDC/LibraryLLM` paths and localhost ports. Vite proxy configuration is development infrastructure; deployed reverse proxy/TLS is not evidenced.
* Python requirements use lower bounds and do not establish an exact reproducible environment. Frontend lockfile is present. Local `faiss_cpu-1.14.3.dist-info/METADATA` reports FAISS 1.14.3; this is a host package observation, not a portable dependency lock.

## Legacy, experiments, and absence

`backend/database/app_database.py` and `backend/routes/models/user.py` create a SQLite user table but are not mounted by the current auth route; MongoDB is the active account store. `backend/database/metadata.py` supplies a hard-coded DuckDB connection, while active catalogue candidate resolution uses MongoDB `current_books`. `AdminPlaceholder.tsx` and `LibrarianPlaceholder.tsx` are unused by `App.tsx`; real dashboards use `StaffDashboard`. The `chatbot/` directory contains no active callable implementation in the inspected inventory. `.backup` pages are not imports.

Experiments include token-aware RAG variants, domain QA construction, MS MARCO/NQ/GooAQ bi-encoder training, lexical overlays, KG topic extraction, and assistant router generations. Their presence is research infrastructure; active runtime still loads the named base MiniLM and existing Qwen path. See the generated [source evidence index](SOURCE_EVIDENCE_INDEX.md) for a recursive symbol inventory, and [09](09_IMPLEMENTATION_CHEATSHEET.md) for reviewer entry points.
