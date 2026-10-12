# Feature flag inventory

Configuration names/default expressions come from source AST, not .env contents. Secret defaults are redacted. No flags were added to create a parallel product. Router research flags remain frozen.

| Flag | File | Line | Default | Decision |
| --- | --- | --- | --- | --- |
| ASSISTANT_PROFILE_PATH | assistant/api.py | 108 | unset | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| ASSISTANT_PROFILE_PATH | assistant/profiling.py | 111 | unset | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| ASSISTANT_QWEN_TIMEOUT | assistant/api.py | 46 | '60' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| ASSISTANT_RAG_TIMEOUT | assistant/api.py | 81 | '120' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| ASSISTANT_ROUTER_MODE | assistant/api.py | 38 | 'existing_qwen' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| ASSISTANT_ROUTER_MODE | assistant/semantic.py | 36 | unset | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| ASSISTANT_ROUTER_V2_HARDWARE_AUDIT | assistant/api.py | 132 | unset | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| ASSISTANT_ROUTER_V2_RETRY | assistant/qwen.py | 125 | '' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| ASSISTANT_ROUTER_V2_VARIANT | assistant/qwen.py | 124 | '' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| BREVO_API_KEY | backend/services/email_service.py | 16 | REDACTED | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| BREVO_SENDER_EMAIL | backend/services/email_service.py | 17 | unset | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| BREVO_SENDER_NAME | backend/services/email_service.py | 18 | 'LuminaR' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| ISBN_LOOKUP_DB | backend/services/library_isbn_lookup.py | 8 | str(Path(__file__).resolve().parents[2] / 'datasets/ai/mappings/isbn_lookup.duckdb') | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| JWT_SECRET_KEY | backend/utils/jwt_utils.py | 13 | REDACTED | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| KNOW_MORE_CACHE_KEY_VERSION | rag/services/local_document_cache.py | 51 | REDACTED | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| KNOW_MORE_CACHE_MASTER_KEY | rag/services/local_document_cache.py | 54 | REDACTED | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| KNOW_MORE_CACHE_MAX_BUNDLE_BYTES | rag/services/local_document_cache.py | 21 | str(64 * 1024 * 1024) | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| KNOW_MORE_DEVICE_CACHE_ENABLED | rag/services/local_document_cache.py | 50 | 'false' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LEXICAL_SEARCH_ENABLED | search/api.py | 133 | 'false' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LEXICAL_SEARCH_ENABLED | search/luminar_search.py | 470 | 'false' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LEXICAL_SEARCH_ENABLED | search/ranked_pages.py | 19 | 'false' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LIBRARY_BORROW_HOLD_HOURS | backend/services/library_lending_service.py | 33 | '24' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LIBRARY_MAX_PENDING_REQUESTS | backend/services/library_lending_service.py | 34 | '5' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LOAN_MAX_RENEWALS | backend/services/loan_renewal_service.py | 18 | '1' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LOAN_RENEWAL_DAYS | backend/services/loan_renewal_service.py | 17 | str(loans.LOAN_PERIOD_DAYS) | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LOAN_RENEWAL_ENABLED | backend/services/loan_renewal_service.py | 23 | '1' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_DEBUG_PROMPT | rag/llm.py | 90 | '' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_INVITE_DAYS | backend/services/institution_service.py | 258 | '7' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_JOIN_ATTEMPTS | backend/services/institution_service.py | 134 | '5' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_JOIN_WINDOW_SECONDS | backend/services/institution_service.py | 132 | '900' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_LEXICAL_PATH | search/lexical_store.py | 44 | Path(__file__).resolve().parents[1] / 'datasets/ai/lexical/published' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_LEXICAL_SYNC_ENABLED | search/lexical_delta.py | 492 | 'false' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_LEXICAL_SYNC_ENABLED | search/luminar_search.py | 292 | 'false' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_LIBRARY_JOIN_ATTEMPTS | backend/services/institution_service.py | 135 | '200' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_MOCK_LLM | rag/llm.py | 59 | '' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_RAG_URL | backend/routes/auth.py | 28 | 'http://127.0.0.1:8005' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_SEARCH_INDEX_DIR | search/sync_queue.py | 121 | unset | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_SEARCH_MAX_CANDIDATES | search/luminar_search.py | 450 | '1000' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_SEARCH_OVERFETCH_FACTOR | search/luminar_search.py | 449 | '2' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_SESSION_DB | backend/services/login_sessions.py | 11 | str(Path(__file__).resolve().parents[2] / 'rag' / 'private_sessions.sqlite') | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| LUMINAR_TESSERACT | rag/services/private_document_ocr.py | 48 | unset | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| MONGO_DB_NAME | backend/database/mongodb.py | 11 | 'luminar_library' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| MONGO_DB_NAME | backend/scripts/migrate_5m_books.py | 16 | 'luminar_library' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| MONGO_DB_NAME | search/luminar_search.py | 48 | 'luminar_library' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| MONGO_DB_NAME | search/maintenance.py | 47 | 'luminar_library' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| MONGO_DB_NAME | search/sync_queue.py | 122 | 'luminar_library' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| MONGO_DB_NAME | search/sync_queue.py | 145 | 'luminar_library' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| MONGO_URI | backend/database/mongodb.py | 9 | REDACTED | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| MONGO_URI | backend/scripts/migrate_5m_books.py | 15 | REDACTED | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| MONGO_URI | search/luminar_search.py | 47 | REDACTED | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| MONGO_URI | search/maintenance.py | 44 | REDACTED | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| MONGO_URI | search/sync_queue.py | 144 | REDACTED | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| NOTIFICATION_DUE_CHECK_INTERVAL_MINUTES | backend/services/notification_worker.py | 25 | '60' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| NOTIFICATION_DUE_WORKER_ENABLED | backend/services/notification_worker.py | 17 | '1' | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
| TESSDATA_PREFIX | rag/services/private_document_ocr.py | 52 | unset | KEEP: code-defined configuration; existing_qwen/router/model selection unchanged; no environment secrets read into report |
