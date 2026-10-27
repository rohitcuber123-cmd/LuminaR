# LuminaR — Current System Definition & Technical Identity

> **Audit Report:** Part 1 Research Evidence Audit  
> **Repository:** LuminaR (`d:\SDC\LibraryLLM`)  
> **Date of Audit:** October 2026  
> **Status:** Ground-Truth Code & Runtime Verification  

---

## 1. Verified Definition of LuminaR

**LuminaR** is an **intelligent, multi-tenant digital library platform and circulation operating system** that integrates:
1. **Multi-institution tenant management** with isolated collections, approval-based circulation workflows (request $\rightarrow$ approve $\rightarrow$ receive $\rightarrow$ return), waiting queue reservations, and integer minor-unit fee ledgers.
2. **Sub-second semantic search over a 5,000,000-book catalogue** powered by a FAISS `IndexHNSWFlat` vector index (384-D, $M=32$, $efConstruction=200$, $efSearch=128$) with a Sentence-Transformers Bi-Encoder (`all-MiniLM-L6-v2`) and a 6-layer Cross-Encoder reranker (`ms-marco-MiniLM-L-6-v2`).
3. **Domain Book & Private Document RAG (Retrieval-Augmented Generation)** driven by a locally resident `Qwen/Qwen2.5-3B-Instruct` model quantized in 4-bit NF4 via `bitsandbytes`, equipped with constrained decoding (`lm-format-enforcer`) for JSON schema intent/evidence validation and strict anti-hallucination refusal guarantees.
4. **Knowledge Artifact Synthesis & Study Intelligence Tools** extracting extractive summaries, hierarchical mind maps (SVG visualization), bounded multi-type flashcards, and adaptive quizzes (MCQ, Cloze / Fill-in-the-blank with semantic vector grading, Match-the-following) directly from parsed PDF and book chunks without GPU generation bottlenecks.
5. **Multi-Factor Behavioral Recommendation Engine** synthesizing 8 distinct signals (semantic query relevance, subject alignment, author affinity, borrowing history, reservations, user ratings, catalogue popularity, real-time availability) with exponential time decay and diversity re-ranking.
6. **Multi-turn Conversational AI Assistant** operating as an orchestrator with typed tool calling into catalogue search, metadata resolution, availability checking, recommendations, user loans, reservations, and reading lists.

---

## 2. Primary Users & Actor Roles

The verified authority model operates on a four-tier hierarchical role structure:

### 2.1 Reader / Patron (`PATRON` role)
- **Identity:** Authenticated via JWT bearer token (standard expiration 60 minutes) with email verification via Brevo OTP.
- **Capabilities:**
  - Explore public libraries and join private institution libraries via access codes or email invitations.
  - Search global catalogue (5M books) and tenant-specific library inventories.
  - Submit book borrow requests and return requests to tenant librarians.
  - Place queue-ordered book reservations when inventory units are exhausted.
  - View personal active loans, borrowing history, due dates, and outstanding fee ledgers.
  - Upload session-isolated private documents (PDFs) into the RAG workspace (`/llm`).
  - Generate study artifacts (mind maps, flashcards, quizzes) and engage with grounded document QA.
  - Interact with the embedded Conversational AI Assistant (`AIChatWidget`).

### 2.2 Library Staff / Librarian (`STAFF` / `LIBRARIAN` role)
- **Identity:** Scoped strictly to a specific tenant `library_id` via `institution_memberships`.
- **Capabilities:**
  - Manage tenant inventory: add books, import CSV/XLSX catalogues (up to 2,000 rows / 5 MiB), manage copies, accession numbers, and shelf locations.
  - Review, approve, or reject circulation requests (Borrow Requests and Return Requests).
  - Confirm physical book return receipts at the library desk.
  - Reconcile overdue fees, apply manual fee adjustments, waive fines, and record physical desk payments.
  - Manage waiting reservation conversion queues.
  - Create, publish, cancel, and archive library events (`library_events`).
  - Upload and manage library digital assets (`library_assets` up to 50 MiB).
  - Inspect tenant analytics dashboards across 7-day, 30-day, 90-day, and lifetime horizons.

### 2.3 Institution Administrator (`ADMIN` role)
- **Identity:** Highest authority inside a specific tenant library.
- **Capabilities:**
  - All librarian capabilities.
  - Edit library profile (name, description, contact details).
  - Manage access control: toggle between `PUBLIC`, `INVITATION_ONLY`, and `CODE_PROTECTED`; rotate join access codes.
  - Invite staff members via email OTP, promote/demote staff roles, and revoke memberships.
  - Audit library operations ledger (`institution_audit`).

### 2.4 Platform Administrator (`PLATFORM_ADMIN` role)
- **Identity:** Global system authority authenticated via `platform_dependencies.py` and MongoDB `platform_assignments`.
- **Capabilities:**
  - Lifecycle management over tenant libraries: suspend, restore, or mark removed.
  - Platform-wide account directory inspection and account provisioning.
  - Resend activation and verification credentials.
  - Platform-wide broadcast notifications and event oversight.
  - Access to platform migration reviews and durable recovery reconciliation.

---

## 3. Library & Institution Architecture

- **Tenant Isolation:** Every library is identified by an immutable canonical `UUID` (`library_id`). All tenant database documents (`institution_library_books`, `institution_holdings`, `institution_copies`, `institution_lending_requests`, `institution_loans`, `institution_reservations`, `institution_fees`) include this `library_id` predicate.
- **Global vs. Local Linking:** A local inventory item can be linked to a global catalogue entity via `global_work_id` (OpenLibrary format e.g. `OL12345W`) or `isbn_13` / `isbn_10`, allowing tenant libraries to inherit rich global metadata while retaining local accession numbers, barcode IDs, shelf locations, and copy counts.
- **Participating Institution Types:**
  - `PUBLIC_LIBRARY`: Open catalogue discovery and self-service membership.
  - `PRIVATE_INSTITUTION`: Restricted catalogue browsing, requiring an institutional pass code or staff-issued email invitation.

---

## 4. AI & Intelligent Modules

| AI Module | Architecture & Models | Primary Files | Runtime Port | Verification Status |
|---|---|---|---|---|
| **Catalogue Semantic Search** | FAISS `IndexHNSWFlat` (384-D, Inner Product, 5M vectors) + Bi-Encoder `sentence-transformers/all-MiniLM-L6-v2` + Cross-Encoder reranker `cross-encoder/ms-marco-MiniLM-L-6-v2` | `search/luminar_search.py`, `search/index_manager.py`, `search/api.py` | `8003` | **VERIFIED IMPLEMENTED** |
| **Document & Book RAG QA** | FAISS `IndexFlatIP` (384-D) + `Qwen/Qwen2.5-3B-Instruct` in 4-bit NF4 (`bitsandbytes`) + `lm-format-enforcer` JSON schema validation | `rag/qa.py`, `rag/llm.py`, `rag/retriever.py`, `rag/reranker.py`, `rag/evidence.py` | `8005` | **VERIFIED IMPLEMENTED** |
| **Conversational AI Assistant** | Multi-step agent orchestrator with typed tool calling (`search`, `catalogue`, `availability`, `recommendation`, `loans`, `reservations`, `reading_list`, `rag`, `kg`) and conversational memory store | `assistant/orchestrator.py`, `assistant/tools.py`, `assistant/qwen.py`, `assistant/api.py` | `8005` | **VERIFIED IMPLEMENTED** |
| **Knowledge Artifact Synthesis** | Deterministic study-model builder (`document_knowledge.py`) computing concepts, extractive summaries, hierarchical mind maps, flashcards, and quizzes | `rag/services/document_knowledge.py`, `rag/services/knowledge_artifacts.py`, `rag/services/knowledge_quiz.py` | `8005` | **VERIFIED IMPLEMENTED** |
| **Semantic Cloze Grading** | Cosine similarity tolerance over MiniLM sentence embeddings for fill-in-the-blank answers | `rag/services/cloze_grading.py`, `rag/services/knowledge_cloze.py` | `8005` | **VERIFIED IMPLEMENTED** |
| **Behavioral Recommendation Engine** | 8-factor hybrid linear combination with exponential decay, implicit feedback boosts, and author/subject diversity filtering | `recommendation/recommendation_service.py`, `recommendation/api.py` | `8004` | **VERIFIED IMPLEMENTED** |
| **Bipartite Metadata Knowledge Graph** | SQLite-backed typed metadata graph connecting books via shared authors, subjects, and TF-IDF topic phrases with 2-hop explanation paths | `knowledge_graph/core.py`, `backend/routes/knowledge_graph.py` | `8002` | **VERIFIED IMPLEMENTED (Marked Experimental)** |

---

## 5. Conventional Software Modules

| Conventional Module | Implementation Details | Primary Files | Runtime Port | Verification Status |
|---|---|---|---|---|
| **Core Authentication & Sessions** | HS256 JWT (`python-jose`) + `bcrypt` password hashing + Brevo transactional email OTP + MongoDB session tracking (`sid`) | `backend/services/auth_service.py`, `backend/routes/auth.py`, `backend/utils/jwt_utils.py` | `8002` | **VERIFIED IMPLEMENTED** |
| **Tenant Membership & Access Control** | Role-based authorization (`PATRON`, `STAFF`, `ADMIN`, `PLATFORM_ADMIN`) with access-code verification and invitation tokens | `backend/services/institution_service.py`, `backend/routes/institutions.py`, `backend/institution_dependencies.py` | `8002` | **VERIFIED IMPLEMENTED** |
| **Approval-Based Lending Workflow** | Write-ahead operation journal (`institution_lending_operations`), durable locks, state machines for borrow requests and return receipts | `backend/services/library_lending_service.py`, `backend/services/library_lending_journal.py`, `backend/routes/library_lending.py` | `8002` | **VERIFIED IMPLEMENTED** |
| **Waiting Queue Reservations** | FIFO queue sequencing with automatic advancement upon copy return | `backend/services/library_reservation_service.py`, `backend/routes/library_reservations_fees.py` | `8002` | **VERIFIED IMPLEMENTED** |
| **Integer Minor-Unit Fee System** | Overdue fine calculation using configurable daily rates, grace periods, charge-stop policies, waiver records, and payment logs | `backend/services/library_fee_service.py`, `backend/routes/library_reservations_fees.py` | `8002` | **VERIFIED IMPLEMENTED** |
| **Inventory Bulk Ingestion** | CSV and XLSX parsers with column alias matching, 2,000-row limits, dry-run previews, and atomic insertion | `backend/services/library_inventory_import.py`, `backend/routes/library_inventory.py` | `8002` | **VERIFIED IMPLEMENTED** |
| **Library Events Management** | Event scheduling, draft/published/cancelled states, registration limits, and attendee tracking | `backend/services/library_event_service.py`, `backend/routes/library_events.py` | `8002` | **VERIFIED IMPLEMENTED** |
| **In-App & Scheduled Notifications** | Dual background workers (`DueWorker`, `TenantNotificationWorker`) scanning for upcoming loan due dates and overdue notices | `backend/services/notification_service.py`, `backend/services/notification_worker.py`, `backend/services/tenant_notification_worker.py` | `8002` | **VERIFIED IMPLEMENTED** |
| **Digital Asset Management** | PDF/EPUB/DOC asset uploads (up to 50 MiB) with visibility controls (`PUBLIC`, `PATRONS_ONLY`, `STAFF_ONLY`) | `backend/services/library_asset_service.py`, `backend/routes/library_assets.py` | `8002` | **VERIFIED IMPLEMENTED** |
| **Desk Analytics Dashboard** | Aggregated circulation statistics, overdue rates, popular subjects, and borrowing time distributions | `backend/services/library_analytics_service.py`, `backend/routes/library_analytics.py` | `8002` | **VERIFIED IMPLEMENTED** |

---

## 6. Runtime Microservice Architecture

The physical deployment runs across **5 decoupled network services**:

```
                    ┌──────────────────────────────────────────────┐
                    │               User Web Browser               │
                    └──────────────────────┬───────────────────────┘
                                           │ HTTP :5173
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │           Vite 6 Dev Server Proxy            │
                    │         React 19 + TypeScript + Writable     │
                    └───┬──────────────┬──────────────┬────────────┘
                        │              │              │
      /api/*            │ /search-api/*│/recommendation-api/* │ /rag-api/*
        ▼               │              │              │           ▼
┌──────────────────┐    │              │              │  ┌──────────────────┐
│ Core Library API │    ▼              │              │  │  RAG QA & AI API │
│  Port 8002       │ ┌──────────────────┐             │  │  Port 8005       │
│ backend/main.py  │ │Catalogue Search  │             │  │   rag/api.py     │
└────────┬─────────┘ │   Port 8003      │             │  └────────┬─────────┘
         │           │  search/api.py   │             │           │
         │           └────────┬─────────┘             ▼           │
         │                    │            ┌──────────────────┐   │
         │                    │            │Recommendation API│   │
         │                    │            │   Port 8004      │   │
         │                    │            │recommendation/   │   │
         │                    │            │    api.py        │   │
         │                    │            └────────┬─────────┘   │
         ▼                    ▼                     ▼             ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                           Databases & Storage Layer                       │
│                                                                           │
│ • MongoDB (localhost:27017, db: luminar_library)                          │
│   - Global: users, books (5M), issues, reservations, fines, activity      │
│   - Multi-Tenant: institution_libraries, institution_memberships,         │
│     institution_library_books, institution_loans, institution_fees, etc.  │
│ • FAISS Vector Indices:                                                   │
│   - 5M Catalogue Index: datasets/ai/faiss/hnsw/hnsw.index (IndexHNSWFlat) │
│   - Book RAG Chunks: rag/book_index/rag.index (IndexFlatIP)               │
│   - Session Private Uploads: dynamic in-memory/disk IndexFlatIP           │
│ • SQLite Databases:                                                       │
│   - HNSW Live Sync Queue: datasets/ai/faiss/hnsw/sync_queue.sqlite3       │
│   - MiniLM Embedding Cache: datasets/ai/faiss/hnsw/embedding_cache.sqlite3│
│   - Knowledge Graph: knowledge_graph/data/catalogue.sqlite                │
│   - Private Document Registry: rag/private_documents/registry.sqlite      │
│ • DuckDB Metadata:                                                        │
│   - book_metadata.duckdb, isbn_lookup.duckdb (datasets/ai/metadata)       │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Strongest Technical Differentiators

1. **Sub-second 5-Million-Scale Search with Mutable HNSW Synchronization:**
   Unlike typical academic demos that stop at a static FAISS index or a few thousand documents, LuminaR operates over **5,000,000 real book vectors**. Because raw FAISS `IndexHNSWFlat` cannot dynamically update or delete nodes, LuminaR implements an immutable base + write-ahead delta snapshot manager (`search/index_manager.py`) with SQLite queue persistence and atomic pointer swapping.
2. **Deterministic Dual-Grounded RAG with Constrained Decoding:**
   RAG in LuminaR is not an unconstrained generic chat prompt. It enforces strict context adherence:
   - Evaluates fast retrieval filters and cross-encoder scores before passing chunks to the LLM.
   - Enforces JSON Schema grammar on intent classification and hallucination validation using `lm-format-enforcer`.
   - Explicitly rejects unanswerable queries rather than fabricating details.
3. **CPU-Feasible Knowledge Artifact Pipeline (No GPU Lock Contention):**
   Generating mind maps, flashcards, concept definitions, and cloze quizzes runs entirely through a deterministic NLP knowledge extractor (`document_knowledge.py`). It avoids monopolizing the GPU inference lock, enabling concurrent readers to study while the RAG engine remains responsive.
4. **Resilient Physical-Circulation State Machine on Standalone MongoDB:**
   LuminaR builds a durable, write-ahead operation journal (`library_lending_journal.py`) with unique idempotency keys, durable write concerns (`w=1, j=True`), and explicit recovery flags (`RecoveryRequired`) to provide bank-grade consistency for physical book checkouts, returns, and overdue fees on non-transactional MongoDB instances.

---

## 8. Recommended Framing and Technical Description

### Analysis of Proposed Framings:
- *AI Library Management System:* Accurately describes the lending, circulation, inventory, and staff management layers, but understates the document intelligence and vector retrieval capabilities.
- *Intelligent Digital Library:* Captures the patron-facing catalogue, reading list, and discovery experience, but ignores multi-tenant administrative middleware.
- *Multi-Library Middleware:* Accurately characterizes the institutional routing, isolated tenant inventories, and federation layer, but misses the deep AI/RAG core.
- *RAG Knowledge Platform / Document Intelligence Platform:* Accurately captures the private PDF ingestion, mind mapping, flashcards, and Qwen QA, but ignores the library circulation engine.
- *Multi-Tenant Library Platform:* Describes the multi-institution software architecture, but ignores the generative AI and vector search stack.

### Recommended Architectural Framing:
The most technically rigorous and defensible framing of LuminaR is:

> **"A Hybrid Multi-Tenant Intelligent Library Operating System and Document Intelligence Platform"**  
> *(Combining a 5-Million-Record Vector Catalogue Search Engine, Institutional Approval-Based Circulation Middleware, and Grounded Local LLM RAG with Knowledge Artifact Synthesis)*

This composite definition accurately represents both halves of the codebase:
1. The **enterprise library infrastructure** (multi-tenant institutions, physical inventory imports, durable loan journals, queue-based reservations, and integer minor-unit fee ledgers).
2. The **advanced AI/NLP intelligence pipeline** (5M-scale HNSW vector retrieval, Cross-Encoder reranking, local 4-bit Qwen RAG with schema-constrained decoding, and deterministic study-tool generation).
