# Claims ledger: allowed wording and evidence burden

Scope: static source audit at revision/date in 00. “Verified” establishes a code mechanism. It is not a benchmark, availability promise or deployment certification. **NOT YET MEASURED** applies to new independent result claims. Never copy future wording into an implemented-contributions paragraph.

## Verified implementation claims

| ID | Safe claim | Evidence | Boundary |
|---|---|---|---|
| V01 | LuminaR integrates four FastAPI services with a React client | backend/main.py; search/api.py; recommendation/api.py; rag/api.py; vite.config.ts | Local topology; deployed reliability unverified |
| V02 | Catalogue queries use normalized local MiniLM embeddings in 384 dimensions | luminar_search.py:55,136–142,423; index_manager.py:encode | Input can truncate at 256 tokens |
| V03 | FAISS HNSW retrieves catalogue candidates and maps positional labels to work IDs | index_manager.py:new_index/Snapshot.candidates | Existing algorithm; approximate neighbors |
| V04 | Search reranks candidates with an MS MARCO MiniLM cross-encoder | luminar_search.py:536–570 | Does not prove better human relevance |
| V05 | Optional title/author lexical/fuzzy candidates can merge into dense ranking | lexical_integration.py; lexical_store.py | Flags default false; no BM25/RRF default |
| V06 | Catalogue indexing uses versioned base/delta snapshots and logical tombstones | index_manager.py:_batch_sync/_persist/_full_rebuild | Eventual Mongo/FAISS consistency |
| V07 | Active metadata is resolved/revalidated in Mongo | catalogue.py:current_books; ranked_pages.py | No library ownership filter in current books lookup |
| V08 | Selected book QA uses a separate book FlatIP index and active-borrow/capability authorization | book_access.py; book_capability_service.py; retriever._search_book | Unselected global QA is a separate policy gap |
| V09 | Personal PDFs are owned by account/session and use per-document FlatIP | private_documents.py:owned/publish/selected | Session isolation code; no proof for all deployment/failure scenarios |
| V10 | PDF ingestion extracts existing text with PyMuPDF | document_service.py:extract_pdf | No OCR; active upload PDF only |
| V11 | QA combines dense/cross-encoder/evidence scoring and predicted support checks | reranker.py; evidence.py; qa.py:ask | Heuristic and model predictions, not guaranteed truth |
| V12 | Default local generation uses Qwen2.5-3B-Instruct | llm.py:44,150–194; api.py | Explicit mock override exists; live process not inspected |
| V13 | Sources return backend-generated chunk/page/work provenance | qa.py:875–935 | No validated claim-level citations |
| V14 | Default assistant is existing_qwen with structured tools and owner/session compact state | assistant/api.py; state.py; launchers | Experimental routers are opt-in; process-local memory |
| V15 | Confirmed circulation assistant writes are additionally feature-gated | orchestrator.py:confirm | Default circulation mutations disabled |
| V16 | Mongo stores count-based holdings/loans/reservations/fines | inventory/issue/reservation/fine services | Multi-write failure windows; default library borrow |
| V17 | Fine settlement state can be marked paid | fine_service.py:pay_fine | No financial transaction processor |
| V18 | CSV/XLSX inventory import matches known works and consolidates copies | inventory_import_service.py | Does not ingest unknown private catalogue into semantic index |
| V19 | Events provide validated draft/publish/cancel/archive lifecycle and unseen receipts | event_service.py; events schema/routes | Global audience; no scheduled publication |
| V20 | Admin metrics derive Mongo counts and unpaid-fine aggregation | routes/notifications.py:summary | Global totals; some librarian counts derived in browser |
| V21 | There is early library_id inventory/issue/search/UI groundwork | inventory_service; availability_service; issue_service; StaffDashboard; search API | EARLY IMPLEMENTATION, not catalogue/tenant isolation |
| V22 | Optional prepared-PDF bundles are encrypted and owner/version validated | local_document_cache.py and frontend repository | Standard crypto; server holds key and processes plaintext |
| V23 | Recommendation scoring uses heuristic weighted semantic/behavior/feedback signals | recommendation_service.py | Not trained collaborative filtering |
| V24 | Related books use metadata relationship similarity | knowledge_graph/core.py | Not a general symbolic knowledge reasoner |

## Historical artifacts, not new results

| ID | Permitted artifact statement | Required qualifier |
|---|---|---|
| A01 | An HNSW manifest records 5M vectors and runtime versioned mappings | Manifest only; baseline_verified=false; binary/live DB not revalidated |
| A02 | Embedding benchmark JSON records MiniLM/BGE proxy metrics | 30 teacher-relative queries/candidate corpus; producing script provenance incomplete |
| A03 | Document latency report records median improvement with worse p90 | Historical workload/relative behavior, not independent correctness or current SLA |
| A04 | Truncation audit reports 3958 of 3959 book chunks beyond 256 tokens | Historical sampled asset generation; no new corpus-wide measurement |
| A05 | Sync benchmark records temporary 500-record performance | Synthetic scale, not 5M rebuild estimate |
| A06 | Router V5 sealed manifest includes 168 cases and author-bias disclosure | Experimental, same coding agent authored manual contracts/eval; default remains Qwen |

## Claims requiring experiments

| ID | Claim candidate | Evidence needed |
|---|---|---|
| E01 | Semantic retrieval improves conceptual catalogue relevance | E1 independent labels and paired group metrics |
| E02 | HNSW is more efficient than exact search at acceptable recall | E2 identical corpus/vector/hardware Pareto curves |
| E03 | Evidence scoring reduces unsupported generation | E3 full pipeline vs controlled variants and independent atomic-claim judgments |
| E04 | Token-aware chunks improve QA | E4 source-span retrieval and paired quality/cost |
| E05 | Resource binding remains correct under concurrent switching | E6/E7 direct access + source assertions + failure tests |
| E06 | Recommendations improve useful discovery | E12 temporal holdout/independent users or judgments |
| E07 | Base/delta maintains reliable fresh catalogues | E10 fault/churn/rebuild study and visibility latency |
| E08 | Device cache saves preparation time | Controlled current upload vs restore, same document/device/server |
| E09 | Assistant router variant improves independent reference resolution | E11 held-out data + current mode disclosure |

All above independent production claims: **NOT YET MEASURED** in this audit.

## Future/proposed claims

“The architecture is being extended toward institution-scoped catalogues.” “We propose a LibraryContext and registry for scoped index selection.” “Future work will evaluate independently owned catalogue datasets, retrieval isolation, and multi-library index tradeoffs.” See 21–23. Dynamic isolated uploads, scoped RAG, library membership, zero leakage and thousand-library performance are unimplemented targets.

## Claims that must not be made

Do not state the current system is a production multi-tenant/private-library platform, creates isolated indexes for newly registered institutions, proves zero cross-library leakage, supports OCR/DOCX web ingestion, indexes full text for every catalogue book, uses HNSW for all QA, trains a novel MiniLM/HNSW method in the default runtime, uses current experimental router results in production, supplies human relevance gold, eliminates hallucinations, achieves claimed speedups without controls, performs financial payments, provides ACID Mongo–FAISS publication, or supports arbitrary many concurrent users.

Before submission each headline claim must have a row linking frozen source, independent dataset, run manifest/raw outputs, metric definition, CI and exact permissible wording. A README/report assertion alone is not sufficient.
