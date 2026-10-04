# Pre-edit implementation map (2026-10-01)

Audit completed before implementation. No AGENTS.md found. This checkout has no Git metadata.

| Concern | Existing implementation | Assistant integration |
|---|---|---|
| Qwen loader | `rag.llm.LuminaRLLM.__init__`, local-only Qwen/Qwen2.5-3B-Instruct, CUDA NF4 or CPU float32 | Inject `rag.api.engine.llm`; never instantiate another model |
| Generation | `LuminaRLLM.generate`, chat template, `_prefix_function` with lm-format-enforcer | Native schema-constrained parsing, one repair, existing generation |
| Residency/concurrency | `rag.api.engine = LuminaRAG()` at import; `engine.inference_lock` | Same process and lock, one uvicorn worker |
| RAG | `/rag/ask`, `/rag/upload`, `/rag/documents`, `/rag/books`; authorization in `rag.services.book_access` | Call unchanged `rag.api.ask` with original credentials and scoped request |
| Core | `backend.main:app`, 8002 | HTTP adapters and small exact entity resolution route |
| Search | `search.api:app`, POST `/search`, 8003, authenticated | HTTP; save_history false; existing semantic algorithm |
| Recommendations | `recommendation.api:app`, GET `/recommendations`, 8004 | Preserve default formula; optional seed profile and new seed endpoint, no new model |
| Recommendation internals | `generate_semantic_candidates`, `calculate_recommendation_score`, `apply_diversity_reranking` | Reuse through existing get_recommendations; RRF for 2–4 seeds |
| Catalogue | Mongo `books`, `book_service.get_book_by_work_id`, canonical `work_id` | GET `/books/{work_id}`; exact case-insensitive title/author resolver |
| Availability | `availability_service.get_availability_context` + `with_authoritative_availability`; inventory LIB001 takes precedence | Core book response already enriched, no model-generated counts |
| Borrow/return | POST `/issues/issue`, `/issues/return/{issue_id}` | Auth forwarded only; confirmation record binds work and issue IDs |
| Reserve | POST `/reservations/` | Auth forwarded only; pending confirmation |
| Loans/history | GET `/issues/my` returns active and historical issues | Partition actual status; no arbitrary frontend user IDs |
| Fees/reservations | GET `/fines/my`, `/reservations/my` | Forward bearer auth, use existing calculations |
| Auth | `get_current_user` -> `decode_access_token` -> DB-backed `current_identity` | Same dependency; verified GENERAL_USER/LIBRARIAN/ADMIN |
| Catalogue fields | 30 live Mongo rows inspected: work_id/title/authors/subjects/description/average_rating/rating_count/reading_log_count/shelf_location/total_copies/available_copies/created_at | Filters only author/subject/availability/rating or title sorting. No invented page/year/language fields |
| Frontend | Vite 5173 proxies `/rag-api` to 8005; AIChatWidget preview, LLMPage uses RAG | No frontend edits; future `/rag-api/assistant/chat` compatibility |
| State | No assistant conversation implementation; chatbot directory empty | Bounded TTL memory, user ownership, per-conversation async serialization |

Baseline files copied and RAG hashes saved under `reports/assistant_backend_baseline` for preservation checks.
