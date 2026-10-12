# LuminaR: evidence-based project overview

Audit date: 6 October 2026 (Asia/Calcutta). Source revision: `c220bc5f53d25d0f7a6bca03b9d7c68400c3a5ce`. Repository root: `D:/SDC`; application root: `D:/SDC/LibraryLLM`. All source locations below are repository-relative. Line numbers describe this revision and may change.

## Scope and evidence standard

This is a static source and artifact audit. Application modules, configuration defaults, startup scripts, frontend calls, tests, and selected experimental artifacts were inspected. Services were not started, databases were not modified, large indexes were not rebuilt, and tests were not executed for this audit. **VERIFIED IMPLEMENTED** means an executable source path was traced, not a certification of deployed reliability. A checked-in measurement is historical evidence with its stated scope, not a new measurement or proof of current production performance. Unmeasured conclusions are labeled **NOT YET MEASURED**. Credentials are excluded.

The meaningful implementation is in `LibraryLLM/`. `reports/**/source`, `reports/**/snapshot`, baseline copies, `.backup` frontend files, extracted Word XML, caches, virtual environments, and vendor code are not the active application merely because they contain similar names. No application code was changed by this audit.

## What LuminaR actually is

LuminaR is a local intelligent library platform integrating a MongoDB catalogue and circulation service, dense catalogue retrieval, behavior-based recommendations, full-text book QA, private session-owned PDF QA, a contextual tool-using assistant, catalogue relationship discovery, and staff operations/events. React communicates through four Vite proxy prefixes with four FastAPI applications. The services share identity and MongoDB logic, while retrieval assets use FAISS and local files/SQLite.

The central research candidate is an evaluated retrieval and grounding system: natural-language catalogue retrieval followed by resource-specific QA, with conventional library operations providing entitlement and useful interaction context. Embeddings, HNSW, RAG, React, and MongoDB are established techniques; their presence alone is insufficient novelty.

## Verified architecture

| Service | Entry point | Frontend proxy / default target | Responsibility |
|---|---|---|---|
| Core | `LibraryLLM/backend/main.py` | `/api` → 8002 | Authentication, books, copies, loans, reservations, fines, renewals, saved lists, staff, events, notifications, related books |
| Search | `LibraryLLM/search/api.py` | `/search-api` → 8003 | MiniLM query encoding, global FAISS HNSW base/delta snapshots, optional lexical merge, cross-encoder reranking, 50-result paging, search history |
| Recommendation | `LibraryLLM/recommendation/api.py` | `/recommendation-api` → 8004 | Search/loan/reservation/feedback profiles and heuristic recommendation ranking |
| RAG and assistant | `LibraryLLM/rag/api.py` | `/rag-api` → 8005 | Flat-index book/PDF retrieval, evidence checks, local Qwen generation, private PDF lifecycle, `/assistant/chat` |
| Browser | `LibraryLLM/frontend/src/App.tsx` | Vite 5173 | React routes, Zustand stores, staff and reader interfaces |

Evidence: `frontend/vite.config.ts`; `backend/main.py:10–144`; `search/api.py:59–73`; `rag/api.py:69–83,292–293`; `assistant/tools.py:23–52`.

## Important distinctions

* Catalogue semantic search is real: query and catalogue text use compatible normalized 384-dimensional MiniLM vectors, and FAISS HNSW matches supply candidates to the runtime ranker (`search/luminar_search.py:423–570`).
* Catalogue ANN is HNSW; active book/PDF QA uses FAISS `IndexFlatIP`, including separate book and private-document indexes (`rag/embed.py:build_book_indexes`; `rag/services/private_documents.py:95–110`). Do not describe all RAG retrieval as HNSW.
* Selected books in the assistant can provide metadata comparison/interpretation; full-text Know More requires registered indexed content and an active borrowing entitlement (`assistant/selected_context.py`; `backend/services/book_capability_service.py:92–112`).
* PDF processing is text extraction and ingestion. It does not perform OCR. The active upload accepts PDF only (`private_document_routes.py:41–54`; `document_service.py:248–292`).
* Fine payment is a persisted status transition; no payment gateway was found (`fine_service.py:138–180`).

## Private libraries: present versus future

**EARLY IMPLEMENTATION / ARCHITECTURAL START — NOT PRODUCTION READY.** There are real `library_id` inventory records, upload previews, issue history fields, an editable staff inventory ID, and optional inventory filtering in global search. There is no traced Library entity, user membership, institution-owned catalogue import, authorized active-library context, per-library catalogue HNSW registry, or institution-scoped RAG.

`books` remain global; the borrow endpoint accepts only `work_id` and defaults to `LIB001`; reservations are keyed by global work; events and summary analytics are global. Supplying a `library_id` to inventory/search does not prove membership or ownership. The proposed institution architecture is documented in [21](21_PRIVATE_LIBRARY_ARCHITECTURE.md), [22](22_PRIVATE_LIBRARY_HNSW_PLAN.md), and [23](23_PRIVATE_LIBRARY_IMPLEMENTATION_PHASES.md).

## Research position

The best current story is **Intelligent Digital Library with Resource-Specific RAG**, anchored in measured catalogue retrieval and evidence-aware QA. A narrower semantic-search paper is possible if retrieval evaluation is strongest. A multi-library paper remains future work.

Paper readiness: **47/100**, a transparent editorial score rather than a metric. Implementation breadth is substantial; independent labels, current reproducible baseline comparisons, grounding evaluation, consistency guarantees, and a defensible novelty argument remain submission blockers. See [20](20_FINAL_RESEARCH_ASSESSMENT.md).

## Reading order

Start with [feature matrix](02_FEATURE_AUDIT.md), [implementation cheat sheet](09_IMPLEMENTATION_CHEATSHEET.md), [experiments](12_EXPERIMENT_PLAN.md), [claims ledger](17_CLAIMS_LEDGER.md), and [assessment](20_FINAL_RESEARCH_ASSESSMENT.md). Technical walkthroughs are in 03–08. Paper components are in 10–18. Private-library plans are 21–23.
