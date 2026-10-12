# LuminaR Implementation Location Cheat Sheet

Source root: `D:/SDC/LibraryLLM`. Open the file and named symbol at the recorded line. Static evidence is tied to the revision in 00; runtime deployment remains unverified.

| Reviewer asks | What to open | Lines |
|---|---|---|
| Where does semantic search enter the backend? | [search/api.py](../../LibraryLLM/search/api.py) → `search` | 195–319 |
| Where are query and book vectors encoded? | [search/index_manager.py](../../LibraryLLM/search/index_manager.py) → `IndexManager.encode` | 154–164 |
| Where is HNSW configured? | [search/index_manager.py](../../LibraryLLM/search/index_manager.py) → `new_index` | 53–57 |
| Where is ANN called and labels resolved? | [search/index_manager.py](../../LibraryLLM/search/index_manager.py) → `Snapshot.candidates` | 91–110 |
| Where is book searchable text defined? | [search/catalogue.py](../../LibraryLLM/search/catalogue.py) → `semantic_text` | 21–31 |
| Where is live Mongo candidate validation? | [search/catalogue.py](../../LibraryLLM/search/catalogue.py) → `current_books` | 49–58 |
| Where are dense candidates reranked? | [search/luminar_search.py](../../LibraryLLM/search/luminar_search.py) → `LuminaRSearchEngine.search` | 391–865 |
| Where are stable result pages built? | [search/ranked_pages.py](../../LibraryLLM/search/ranked_pages.py) → `RankedSearchPages.search` | 28–77 |
| Where are lexical candidates merged? | [search/lexical_integration.py](../../LibraryLLM/search/lexical_integration.py) → `merge_lexical_candidates` | 23–73 |
| Where is fuzzy matching? | [search/typo_assistance.py](../../LibraryLLM/search/typo_assistance.py) → `best_bounded_match` | 25–34 |
| Where are changed vectors appended/tombstoned? | [search/index_manager.py](../../LibraryLLM/search/index_manager.py) → `IndexManager._batch_sync` | 386–431 |
| Where is full catalogue rebuild? | [search/index_manager.py](../../LibraryLLM/search/index_manager.py) → `IndexManager._full_rebuild` | 433–511 |
| Where is atomic snapshot publication? | [search/index_manager.py](../../LibraryLLM/search/index_manager.py) → `IndexManager._persist` | 293–356 |
| Where are mutation intents recorded? | [search/sync_queue.py](../../LibraryLLM/search/sync_queue.py) → `catalogue_mutation` | 104–117 |
| Where is authenticated full-text QA? | [rag/api.py](../../LibraryLLM/rag/api.py) → `ask` | 191–271 |
| Where is selected-book entitlement? | [rag/services/book_access.py](../../LibraryLLM/rag/services/book_access.py) → `authorize_selection` | 8–23 |
| Where is borrowing-based Know More entitlement? | [backend/services/book_capability_service.py](../../LibraryLLM/backend/services/book_capability_service.py) → `authorize_know_more` | 101–107 |
| Where does selected-book retrieval search? | [rag/retriever.py](../../LibraryLLM/rag/retriever.py) → `RAGRetriever._search_book` | 766–1021 |
| Where is evidence reranking? | [rag/reranker.py](../../LibraryLLM/rag/reranker.py) → `RAGReranker.search` | 125–523 |
| Where are heuristic evidence features? | [rag/evidence.py](../../LibraryLLM/rag/evidence.py) → `calculate_evidence_score` | 586–1336 |
| Where is fast evidence accept/reject? | [rag/fast_filter.py](../../LibraryLLM/rag/fast_filter.py) → `run_fast_filter` | 616–685 |
| Where are context/prompt/answer produced? | [rag/qa.py](../../LibraryLLM/rag/qa.py) → `LuminaRAG.ask` | 540–1042 |
| Where is a grounded compact prompt? | [rag/qa.py](../../LibraryLLM/rag/qa.py) → `LuminaRAG.build_compact_prompt` | 438–482 |
| Where is Qwen generation? | [rag/llm.py](../../LibraryLLM/rag/llm.py) → `LuminaRLLM.generate` | 268–461 |
| Where is document latency adaptation installed? | [rag/document_latency.py](../../LibraryLLM/rag/document_latency.py) → `install_document_latency` | 140–154 |
| Where are PDFs parsed? | [rag/services/document_service.py](../../LibraryLLM/rag/services/document_service.py) → `DocumentService.extract_pdf` | 248–292 |
| Where are PDF chunks made? | [rag/services/document_service.py](../../LibraryLLM/rag/services/document_service.py) → `DocumentService.create_chunks` | 343–392 |
| Where is PDF chunk embedding? | [rag/services/document_service.py](../../LibraryLLM/rag/services/document_service.py) → `DocumentService.embed_chunks` | 443–464 |
| Where is private document ingestion? | [rag/services/private_documents.py](../../LibraryLLM/rag/services/private_documents.py) → `PrivateDocuments.ingest` | 112–139 |
| Where is session ownership verified? | [rag/services/private_documents.py](../../LibraryLLM/rag/services/private_documents.py) → `PrivateDocuments.owned` | 66–72 |
| Where are per-document vectors/index persisted? | [rag/services/private_documents.py](../../LibraryLLM/rag/services/private_documents.py) → `PrivateDocuments.publish` | 95–110 |
| Where is document deletion? | [rag/services/private_documents.py](../../LibraryLLM/rag/services/private_documents.py) → `PrivateDocuments.purge` | 211–223 |
| Where is encrypted device export? | [rag/services/local_document_cache.py](../../LibraryLLM/rag/services/local_document_cache.py) → `LocalDocumentCache.export` | 215–227 |
| Where are registered book chunks made? | [rag/book_ingest.py](../../LibraryLLM/rag/book_ingest.py) → `process_book` | 206–348 |
| Where are per-book FlatIP indexes built? | [rag/embed.py](../../LibraryLLM/rag/embed.py) → `build_book_indexes` | 252–513 |
| Where is assistant runtime/router selected? | [assistant/api.py](../../LibraryLLM/assistant/api.py) → `install_assistant` | 37–152 |
| Where is explicit mutation confirmation? | [assistant/orchestrator.py](../../LibraryLLM/assistant/orchestrator.py) → `AssistantOrchestrator.confirm` | 880–941 |
| Where is compact conversation ownership? | [assistant/state.py](../../LibraryLLM/assistant/state.py) → `ConversationStore.get` | 64–82 |
| Where is metadata selected-book evidence? | [assistant/selected_context.py](../../LibraryLLM/assistant/selected_context.py) → `evidence_packet` | 14–58 |
| Where does a recommendation profile originate? | [recommendation/recommendation_service.py](../../LibraryLLM/recommendation/recommendation_service.py) → `build_user_profile` | 340–688 |
| Where is recommendation score calculated? | [recommendation/recommendation_service.py](../../LibraryLLM/recommendation/recommendation_service.py) → `calculate_recommendation_score` | 1666–1899 |
| Where is catalogue graph similarity? | [knowledge_graph/core.py](../../LibraryLLM/knowledge_graph/core.py) → `CatalogueGraph.more_like_this` | 60–107 |
| Where is borrowing? | [backend/services/issue_service.py](../../LibraryLLM/backend/services/issue_service.py) → `issue_book` | 49–76 |
| Where is returning/fine-on-return? | [backend/services/issue_service.py](../../LibraryLLM/backend/services/issue_service.py) → `return_book` | 340–528 |
| Where is physical/default availability? | [backend/services/availability_service.py](../../LibraryLLM/backend/services/availability_service.py) → `get_availability_context` | 18–56 |
| Where are reservations made? | [backend/services/reservation_service.py](../../LibraryLLM/backend/services/reservation_service.py) → `create_reservation` | 29–102 |
| Where is pickup FIFO? | [backend/services/reservation_service.py](../../LibraryLLM/backend/services/reservation_service.py) → `mark_next_reservation_ready` | 232–283 |
| Where is loan renewal? | [backend/services/loan_renewal_service.py](../../LibraryLLM/backend/services/loan_renewal_service.py) → `renew_loan` | 83–117 |
| Where is fine formula? | [backend/services/fine_service.py](../../LibraryLLM/backend/services/fine_service.py) → `create_fine` | 26–87 |
| Where is paid status recorded? | [backend/services/fine_service.py](../../LibraryLLM/backend/services/fine_service.py) → `pay_fine` | 138–201 |
| Where is catalogue addition? | [backend/services/book_service.py](../../LibraryLLM/backend/services/book_service.py) → `create_book` | 155–238 |
| Where is library inventory addition? | [backend/services/inventory_service.py](../../LibraryLLM/backend/services/inventory_service.py) → `add_inventory` | 10–76 |
| Where is dataset preview? | [backend/services/inventory_import_service.py](../../LibraryLLM/backend/services/inventory_import_service.py) → `create_preview` | 199–503 |
| Where is inventory import confirmation? | [backend/services/inventory_import_service.py](../../LibraryLLM/backend/services/inventory_import_service.py) → `confirm_inventory_import` | 510–781 |
| Where are global summary analytics? | [backend/routes/notifications.py](../../LibraryLLM/backend/routes/notifications.py) → `summary` | 69–78 |
| Where are events published? | [backend/services/event_service.py](../../LibraryLLM/backend/services/event_service.py) → `transition` | 105–123 |
| Where is event unseen receipt state? | [backend/services/event_service.py](../../LibraryLLM/backend/services/event_service.py) → `unseen` | 180–186 |
| Where are due notifications? | [backend/services/notification_service.py](../../LibraryLLM/backend/services/notification_service.py) → `scan_due` | 157–203 |
| Where is JWT checked/current identity refreshed? | [backend/utils/jwt_utils.py](../../LibraryLLM/backend/utils/jwt_utils.py) → `decode_access_token` | 42–61 |
| Where are backend roles required? | [backend/dependencies.py](../../LibraryLLM/backend/dependencies.py) → `require_roles` | 27–44 |
| Where is password hashing? | [backend/services/auth_service.py](../../LibraryLLM/backend/services/auth_service.py) → `hash_password` | 21–33 |

## Frontend entry points

| Reviewer asks | What to open |
|---|---|
| Where is catalogue/search UI? | `frontend/src/pages/CatalogPage.tsx`, `SearchPage.tsx`; request client `frontend/src/lib/api.ts:507` |
| Where is book/document QA UI? | `frontend/src/pages/LLMPage.tsx:683`; source selection/URL revision and askRAG |
| Where is the assistant? | `frontend/src/components/AIChatWidget.tsx`; `store/useAssistantStore.ts`; `lib/assistant.ts` |
| Where is reader history? | `frontend/src/pages/ProfilePage.tsx`; `store/useLibraryStore.ts` |
| Where are actual dashboards? | `frontend/src/pages/StaffDashboard.tsx:60`; metrics at 215; library input at 366 |
| Where is dataset upload? | `frontend/src/pages/StaffForms.tsx` → `DatasetImport`; `api/core.ts:87–103` |
| Where are events? | `EventEditorPage.tsx`, `ManageEventsPage.tsx`, `EventsPage.tsx`, `EventMonitor.tsx` |
| Where are browser caches? | `frontend/src/lib/localDocumentCache.ts`, `hooks/useDeviceDocuments.ts` |
| How are API ports connected? | `frontend/vite.config.ts`; `lib/api.ts:5–8` |

## Future targets — PROPOSED

| Reviewer asks | Existing evidence / proposed location |
|---|---|
| Has private-library support started? | `inventory_service.py`, `inventory_import_service.py`, `availability_service.py:7`, `issue_service.py:195`, `search/api.py:96`, `StaffDashboard.tsx:81`. Inventory scope exists; membership/catalogue isolation does not. |
| Where is library registration/membership? | No active implementation; add core Library/Membership schemas/services/routes and LibraryContext dependency. |
| Where would library-owned book identity be added? | Extend `library_inventory` toward scoped Holdings; separate private catalogue records from shared Work metadata. See 08 and 21. |
| Where would scoped ANN go? | Extend `IndexManager` and `Snapshot` behind a LibraryIndexRegistry; scope queue/cache/current_books; see 22. |
| Where would RAG library scope go? | `rag/api.py`, `book_access.py`, `retriever.py`, `book_runtime.py`, source metadata and assistant tools/state; see 21–23. |
| Where would user switching go? | New active-library context store, App/Header/Search/Catalog/LLM/Profile/staff/events/graph/recommendation/cache changes. |

## Navigation notes

The [recursive index](SOURCE_EVIDENCE_INDEX.md) lists other symbols and file hashes. Route decorators there may need APIRouter prefixes. For complete call chains use 03–07; for claims use 17.
