# LuminaR — Code Location & Implementation Cheatsheet

> **Audit Report:** Part 1 Research Evidence Audit  
> **Repository:** LuminaR (`d:\SDC\LibraryLLM`)  
> **Purpose:** Viva / Technical Review Reference Guide. Contains exact verified relative paths, function names, line numbers, HTTP routes, database models, and frontend components.

---

## 1. Multi-Library Federation & Identity

### 1.1 Library Selection & Switching
- **Frontend Component:** `frontend/src/components/LibrarySwitcher.tsx` (Lines 1–45)
  - Selects active tenant library; updates `useInstitutionStore` and redirects router context to `/libraries/:libraryId`.
- **Frontend Discovery Page:** `frontend/src/pages/Institutions.tsx` (`ExploreLibrariesPage`, Lines 45–180)
- **Backend API Endpoints:**
  - `GET /libraries`: `backend/routes/institutions.py` (Line 23, `discovery()`)
  - `GET /me/libraries`: `backend/routes/institutions.py` (Line 29, `mine()`)
  - `POST /libraries/{library_id}/join`: `backend/routes/institutions.py` (Line 50, `join()`)
- **Backend Service:** `backend/services/institution_service.py` (Lines 120–185, `discover()`, `my_libraries()`, `join_library()`)
- **Database Model:** MongoDB `institution_memberships` (fields: `membership_id`, `library_id`, `user_id`, `role`, `status`)

### 1.2 Unique Library IDs
- **Schema & Type Definition:** `backend/schemas/institutions.py` (Lines 15–35, `UUID` field types)
- **Validation Route:** `backend/routes/institutions.py` (Lines 18–118; path parameters typed as `library_id: UUID`)
- **Tenant Scope Enforcement:** `backend/services/institution_repository.py` (Line 43, `TenantInventory.__init__` validating `UUID(str(library_id))`)
- **Frontend State:** `frontend/src/store/useInstitutionStore.ts` (Lines 20–60, storing active `libraryId: string`)

---

## 2. Inventory & Dataset Ingestion

### 2.1 Dataset Upload & Spreadsheet Parsing
- **Frontend Interface:** `frontend/src/pages/LibraryInventory.tsx` (`ImportModal`, Lines 250–380)
- **Backend API Endpoints:**
  - `POST /libraries/{library_id}/inventory/imports/preview`: `backend/routes/library_inventory.py` (Line 61, `preview()`)
  - `POST /libraries/{library_id}/inventory/imports/{import_id}/apply`: `backend/routes/library_inventory.py` (Line 73, `apply()`)
  - `GET /libraries/{library_id}/inventory/imports/{import_id}`: `backend/routes/library_inventory.py` (Line 78, `status()`)
- **Backend Service Logic:** `backend/services/library_inventory_import.py`:
  - File parser & alias mapper: `parse_file(filename, content)` (Lines 41–94; max 5 MiB, 2,000 rows, 40 aliases)
  - Row validator: `validated_row(raw)` (Lines 96–120)
  - Dry-run preview builder: `preview(library_id, filename, content, actor)` (Lines 122–170)
  - Batch commit: `apply(library_id, import_id, request, actor)` (Lines 172–230)
- **Database Model:** MongoDB `institution_inventory_imports`, `institution_inventory_previews` (TTL index on `expires_at`)

### 2.2 Book & Holding Import
- **Backend Service:** `backend/services/library_catalogue_service.py`:
  - Record builder: `prepare_book()` (Lines 80–125)
  - Locked insertion: `insert_locked()` (Lines 140–185)
  - Copy accession: `add_copy_locked()` (Lines 190–235)
- **Database Model:** MongoDB `institution_library_books` (fields: `library_book_id`, `library_id`, `accession_number`, `global_work_id`, `isbn_13`, `status`), `institution_holdings`, `institution_copies`

---

## 3. 5M Semantic Search & HNSW Indexing

### 3.1 Semantic Search Execution
- **Frontend Search Page:** `frontend/src/pages/SearchPage.tsx` (Lines 1–136) & `frontend/src/components/CatalogueSurface.tsx` (Lines 1–120)
- **Backend API Route:** `POST /search`: `search/api.py` (Lines 196–275, `search()`)
- **Backend Engine Pipeline:** `search/luminar_search.py` (`LuminaRSearchEngine.search()`, Lines 391–700):
  - Stage 1: Query Embedding (Lines 418–440)
  - Stage 2: HNSW Candidate Retrieval (Lines 442–480)
  - Stage 3: Cross-Encoder Reranking (Lines 500–565)
  - Stage 4: Author Intent & Lexical Fusion (Lines 566–573)
  - Stage 5: Metadata Lookup via DuckDB/MongoDB (Lines 585–597)
  - Stage 6: Authoritative Inventory Resolution (Lines 599–615)
- **Pagination & Caching:** `search/ranked_pages.py` (`RankedSearchPages.page()`, Lines 45–95)

### 3.2 Query Embeddings
- **Model Loader:** `search/luminar_search.py` (Lines 136–143, `SentenceTransformer("all-MiniLM-L6-v2", device=self.device)`)
- **Vector Normalization:** `search/luminar_search.py` (Lines 437–439, `faiss.normalize_L2(query_vector)`)
- **Embedding Cache:** `search/embedding_cache.py` (`EmbeddingCache.get()` / `set()`, Lines 45–95; SQLite3 database)

### 3.3 HNSW Vector Index
- **Index Constructor:** `search/index_manager.py` (Lines 53–58, `new_index()` creating `faiss.IndexHNSWFlat(384, 32, faiss.METRIC_INNER_PRODUCT)`)
- **Index Parameters:** $M=32$, $efConstruction=200$, $efSearch=128$ (Lines 55–56, `index.hnsw.efConstruction = 200`, `index.hnsw.efSearch = 128`)
- **Persistent Index Path:** `datasets/ai/faiss/hnsw/hnsw.index` (Size: 9.04 GB; 5,000,000 vectors)
- **Write-Ahead Sync Queue:** `search/sync_queue.py` (`SyncQueue`, Lines 40–120; `sync_queue.sqlite3`)

### 3.4 Vector-to-Metadata Mapping
- **NumPy Array Mapping:** `datasets/ai/faiss/hnsw/index_work_ids.npy` (Size: 67.8 MB; maps FAISS ordinal ID to OpenLibrary `work_id`)
- **Snapshot Resolver:** `search/index_manager.py` (`Snapshot.candidates()`, Lines 91–115)
- **Bulk Metadata DB:** `datasets/ai/metadata/book_metadata.duckdb` & MongoDB `books` collection

---

## 4. RAG QA & Qwen2.5-3B LLM

### 4.1 RAG Orchestrator & Pipeline
- **Frontend QA Interface:** `frontend/src/pages/LLMPage.tsx` (Lines 1–550) & `frontend/src/components/rag/RAGAnswer.tsx` (Lines 1–95)
- **Backend API Route:** `POST /rag/ask`: `rag/api.py` (Lines 194–277, `ask()`)
- **RAG QA Core Engine:** `rag/qa.py` (`LuminaRAG.ask()`, Lines 540–720):
  - Unified depth configuration: `DEPTH_CONFIG` (Lines 36–62; concise, normal, detailed, comprehensive)
  - Diverse context selection: `select_diverse_context()` (Lines 141–195)
  - Prompt construction: `build_prompt()` (Lines 268–325)
  - Evidence validation & refusal check: Lines 650–690
- **Retriever & Reranker:**
  - Dense Retriever: `rag/retriever.py` (`RAGRetriever`, Lines 45–140; FAISS `IndexFlatIP`)
  - Cross-Encoder: `rag/reranker.py` (`RAGReranker`, Lines 35–110; `ms-marco-MiniLM-L-6-v2`)
  - Evidence & Concept Scorer: `rag/evidence.py` (Lines 8–35; weights: CrossEncoder 0.30, Evidence 0.55, FAISS 0.15)

### 4.2 Local Qwen LLM Integration
- **Model Loader:** `rag/llm.py` (`LuminaRLLM.__init__()`, Lines 101–210):
  - Model Name: `Qwen/Qwen2.5-3B-Instruct` (Line 44)
  - 4-bit Quantization: Lines 174–185 (`BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16)`)
  - HuggingFace Model Call: Line 181 (`AutoModelForCausalLM.from_pretrained(MODEL_NAME, quantization_config=bnb_config, device_map="auto")`)
- **Constrained Decoding & JSON Enforcement:**
  - Pydantic Schema: `rag/llm.py` (`IntentSchema`, `ValidatorSchema`, Lines 26–39)
  - Token Enforcer Integration: `rag/llm.py` (Lines 20–25, `JsonSchemaParser`, `build_transformers_prefix_allowed_tokens_fn`)
- **Assistant Generation Gateway:** `assistant/qwen.py` (`QwenGateway.generate()`, Lines 45–130)

---

## 5. Document Ingestion & Knowledge Artifacts

### 5.1 Document Parsing & OCR
- **Frontend Uploader:** `frontend/src/pages/LLMPage.tsx` (`handleFile()`, Lines 120–180)
- **Backend API Route:** `POST /rag/upload`: `rag/services/private_document_routes.py` (Lines 61–95, `upload()`)
- **PyMuPDF Native Text Parser:** `rag/services/document_service.py` (`extract_pdf()`, Lines 248–293 using `fitz.open()`)
- **Local OCR Fallback:** `rag/services/private_document_ocr.py` (`read_page()`, Lines 60–120 using Tesseract CLI / PyMuPDF)
- **Session Document Isolation:** `rag/services/private_documents.py` (`PrivateDocuments.ingest()`, Lines 105–170; isolated FAISS index per document)

### 5.2 Text Chunking
- **Document Chunking Logic:** `rag/services/document_service.py` (`chunk_text()`, Lines 85–124; `CHUNK_SIZE=3000`, `CHUNK_OVERLAP=400`)
- **Domain Book Chunker:** `rag/chunk_books.py` (`chunk_file()`, Lines 45–95)

### 5.3 Knowledge Artifact Synthesis (Mind Maps, Flashcards, Summaries, Key Concepts)
- **Frontend Study Interface:** `frontend/src/components/knowledge/KnowledgeTools.tsx` (Lines 1–162)
- **Backend API Route:** `POST /rag/documents/{id}/artifacts/{kind}`: `rag/services/knowledge_routes.py` (Lines 53–57, `generate()`)
- **Knowledge Artifact Service:** `rag/services/knowledge_artifacts.py` (`KnowledgeArtifacts.generate()`, Lines 105–165)
- **Study Model Engine:** `rag/services/document_knowledge.py` (`build()`, Lines 380–480):
  - Key concepts & definitions extraction: Lines 400–435
  - Extractive summary sentence ranking: Lines 440–470
  - Mind map hierarchical tree synthesis: `rag/services/knowledge_artifacts.py` (Lines 185–225)
  - SVG Layout Engine: `frontend/src/components/knowledge/mapLayout.ts` & `KnowledgeMap.tsx`

### 5.4 Quiz Engine (MCQ, Cloze / Fill-in-Blank, Matching)
- **Frontend Quiz Runner:** `frontend/src/components/knowledge/Quiz.tsx` (Lines 1–150)
- **Backend API Endpoints:**
  - `POST /rag/documents/{id}/artifacts/quiz`: `rag/services/knowledge_routes.py` (Line 45, `generate_quiz()`)
  - `POST /rag/documents/{id}/artifacts/{aid}/cloze/{iid}/grade`: `rag/services/knowledge_routes.py` (Line 49, `grade_cloze()`)
- **Quiz Generator:** `rag/services/knowledge_quiz.py` (`build_quiz()`, Lines 45–140)
- **Format Generators:**
  - Multiple Choice (MCQ): `rag/services/knowledge_mcq.py` (`build_mcq()`, Lines 25–95)
  - Cloze (Fill-in-the-blank): `rag/services/knowledge_cloze.py` (`build_cloze()`, Lines 30–80)
  - Match-the-following: `rag/services/knowledge_match.py` (`build_matching()`, Lines 25–90)
- **Semantic Cloze Grading Engine:** `rag/services/cloze_grading.py` (`grade_cloze()`, Lines 40–115; exact match + MiniLM vector similarity $\ge 0.82$)

---

## 6. Recommendations & Knowledge Graph

### 6.1 Multi-Factor Recommendation Engine
- **Frontend Recommendations Display:** `frontend/src/components/ForYou.tsx` (Lines 1–120) & `frontend/src/pages/Home.tsx`
- **Backend API Endpoints:**
  - `GET /recommendations`: `recommendation/api.py` (Line 192, `recommendations()`)
  - `POST /recommendations/from-book`: `recommendation/api.py` (Line 225, `recommendations_from_book()`)
  - `POST /feedback`: `recommendation/api.py` (Line 244, `submit_feedback()`)
- **Hybrid Scoring Implementation:** `recommendation/recommendation_service.py`:
  - Weights Configuration: Lines 33–40 (Semantic 0.40, Subject 0.15, Author 0.10, Borrowing 0.15, Reservation 0.10, Rating 0.05, Popularity 0.03, Availability 0.02)
  - User profile builder with exponential decay: `build_user_profile()` (Lines 110–190; `DECAY_RATE=0.15`)
  - Diversity re-ranking: Lines 380–430 (`MAX_BOOKS_PER_AUTHOR=2`, `SUBJECT_SIMILARITY_THRESHOLD=0.80`)
- **Database Model:** MongoDB `recommendation_feedbacks`, `issues`, `reservations`, `books`

### 6.2 Bipartite Metadata Knowledge Graph
- **Frontend Graph Explorer:** `frontend/src/pages/KnowledgeGraphPage.tsx` (Lines 1–180) & `frontend/src/components/BookConnectionGraph.tsx`
- **Backend API Endpoints:**
  - `POST /experimental/kg/more-like-this`: `backend/routes/knowledge_graph.py` (Line 77, `more_like_this()`)
  - `GET /kg/books/{work_id}/more-like-this`: `backend/routes/knowledge_graph.py` (Line 80, `product_more_like_this()`)
- **Graph Traversal Core:** `knowledge_graph/core.py` (`CatalogueGraph.more_like_this()`, Lines 60–115):
  - Shared feature scoring query: Lines 70–73 (`SELECT e.book_id, SUM(f.weight*f.weight) / SQRT(...) AS score`)
  - 2-hop reason path extraction: Lines 84–105 (`reasons.append({'nodes': [work_id, feature_id, book_id], ...})`)
- **Graph Database File:** SQLite `knowledge_graph/data/catalogue.sqlite`

---

## 7. Institutional Circulation, Waiting Queues & Fines

### 7.1 Borrowing Workflow
- **Frontend Action Button:** `frontend/src/components/CatalogueBookActions.tsx` (Lines 40–95) & `frontend/src/pages/LibraryCirculation.tsx`
- **Backend API Endpoints:**
  - `POST /libraries/{library_id}/lending/borrow-requests`: `backend/routes/library_lending.py` (Line 51, `borrow()`)
  - `POST /libraries/{library_id}/staff/lending/borrow-requests/{request_id}/{action}`: `backend/routes/library_lending.py` (Line 87, `review_borrow()`)
- **Backend Service State Machine:** `backend/services/library_lending_service.py` (`borrow()`, Lines 95–160; `review_borrow()`, Lines 165–230)
- **Durable Write-Ahead Journal:** `backend/services/library_lending_journal.py` (`durable()`, `ensure_indexes()`, Lines 18–45)
- **Database Collections:** MongoDB `institution_lending_requests`, `institution_loans`, `institution_lending_operations`

### 7.2 Return Workflow
- **Frontend Loan Actions:** `frontend/src/components/BorrowedBookActions.tsx` & `frontend/src/pages/LibraryCirculation.tsx`
- **Backend API Endpoints:**
  - `POST /libraries/{library_id}/loans/{loan_id}/return-request`: `backend/routes/library_lending.py` (Line 92, `return_request()`)
  - `POST /libraries/{library_id}/staff/lending/return-requests/{request_id}/{action}`: `backend/routes/library_lending.py` (Line 97, `review_return()`)
  - `POST /libraries/{library_id}/staff/loans/{loan_id}/receive`: `backend/routes/library_lending.py` (Line 127, `assisted_receive()`)
- **Backend Service Logic:** `backend/services/library_lending_service.py` (`return_request()`, Lines 240–280; `review_return()`, Lines 285–340)

### 7.3 Reservation Queuing
- **Frontend Reservation Control:** `frontend/src/pages/LibraryReservationsFees.tsx` (Lines 1–180) & `LibraryCirculation.tsx`
- **Backend API Endpoints:**
  - `POST /libraries/{library_id}/reservations`: `backend/routes/library_reservations_fees.py` (Line 26, `reserve()`)
  - `GET /libraries/{library_id}/inventory/{library_book_id}/reservation-status`: `backend/routes/library_reservations_fees.py` (Line 31, `book_state()`)
  - `POST /libraries/{library_id}/reservations/{reservation_id}/cancel`: `backend/routes/library_reservations_fees.py` (Line 55, `cancel()`)
- **Backend Service Logic:** `backend/services/library_reservation_service.py` (`create()`, Lines 45–95; `advance_locked()`, Lines 100–145)
- **Database Collection:** MongoDB `institution_reservations` (indexes on `library_id`, `library_book_id`, `queue_sequence`)

### 7.4 Fine Calculation & Ledgers
- **Frontend Fees Desk:** `frontend/src/pages/LibraryReservationsFees.tsx` (`fees` tab, Lines 190–320)
- **Backend API Endpoints:**
  - `GET /libraries/{library_id}/me/fees`: `backend/routes/library_reservations_fees.py` (Line 71, `mine_fees()`)
  - `GET /libraries/{library_id}/staff/fees`: `backend/routes/library_reservations_fees.py` (Line 81, `staff_fees()`)
  - `POST /libraries/{library_id}/staff/fees/{fee_id}/waive`: `backend/routes/library_reservations_fees.py` (Line 93, `waive()`)
  - `POST /libraries/{library_id}/staff/fees/{fee_id}/adjust`: `backend/routes/library_reservations_fees.py` (Line 98, `adjust()`)
  - `POST /libraries/{library_id}/staff/fees/{fee_id}/payments`: `backend/routes/library_reservations_fees.py` (Line 103, `payment()`)
  - `GET /libraries/{library_id}/settings/fee-policy`: `backend/routes/library_reservations_fees.py` (Line 113, `policy()`)
- **Backend Service Logic:** `backend/services/library_fee_service.py`:
  - Daily fine calculation: `calculation(loan, stop)` (Lines 28–47; integer minor units)
  - Automatic return trigger: `fee_effects()` (Lines 49–75)
  - Ledger mutations: `mutate()` (Lines 95–160)
- **Database Collections:** MongoDB `institution_fee_policies`, `institution_fees`, `institution_payments`

---

## 8. Authentication & Authorization

### 8.1 Authentication & Sessions
- **Frontend Pages:** `frontend/src/pages/LoginPage.tsx`, `SignUpPage.tsx`, `VerifyOTPPage.tsx`, `StaffLoginPage.tsx`
- **Backend API Endpoints:**
  - `POST /auth/register`: `backend/routes/auth.py` (Line 77, `register()`)
  - `POST /auth/login`: `backend/routes/auth.py` (Lines 105–140, `login()`)
  - `POST /auth/verify-otp`: `backend/routes/auth.py` (Lines 145–170)
  - `POST /auth/logout`: `backend/routes/auth.py` (Lines 22–37, `logout()`)
- **JWT Encoding / Decoding:** `backend/utils/jwt_utils.py` (`create_access_token()`, `decode_access_token()`; HS256 algorithm)
- **Password Hashing:** `backend/services/auth_service.py` (`hash_password()`, `verify_password()` using `bcrypt`)
- **Transactional Email Service:** `backend/services/email_service.py` (Brevo API transactional template delivery)
- **Database Collections:** MongoDB `users`, `email_verifications`, `login_sessions`

### 8.2 Authorization & Access Control
- **Core User Dependency:** `backend/dependencies.py` (`get_current_user`, Lines 15–45)
- **Institution Security Dependencies:** `backend/institution_dependencies.py`:
  - `require_library_membership()` (Lines 25–55)
  - `require_library_staff()` (Lines 60–90)
  - `actor_id()` (Line 15)
- **Platform Administrator Dependency:** `backend/platform_dependencies.py` (`require_platform_admin()`, Lines 30–65)
- **Frontend Route Protections:**
  - `frontend/src/components/ProtectedRoute.tsx` (Lines 1–35; checks JWT validity)
  - `frontend/src/components/WorkspaceRoute.tsx` (Lines 1–95; checks tenant membership & staff role)
  - `frontend/src/components/ManagementRoutes.tsx` (`PlatformRoute`, Lines 1–45)
