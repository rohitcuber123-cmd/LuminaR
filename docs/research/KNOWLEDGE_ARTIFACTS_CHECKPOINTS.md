# Knowledge Artifacts checkpoint log

| Stage | Change | Validation / findings |
|---|---|---|
| 1 — Audit | Traced private_document_routes, PrivateDocuments, DocumentService, LLMPage, auth, cache, rag/api, search/index_manager | Private uploads use session SQLite + files and FAISS flat IP; catalogue uses MongoDB + HNSW. Page/chunk metadata exists; hierarchy does not. No AGENTS.md found. |
| 2 — Foundations | knowledge_artifacts.py; SQLite foreign keys in private_documents.py | Generalized artifact table with cascade cleanup and transactional access checks. |
| 3 — Algorithms | knowledge_algorithms.py | Standard-library extraction, ranking, definition and cloze filters; bounded output. |
| 4 — APIs | knowledge_routes.py; rag/api.py registration | Existing JWT/session authorization, source excerpts, list/get/delete/generate. |
| 5–6 — Frontend | knowledgeArtifacts.ts; KnowledgeTools.tsx; KnowledgeMap.tsx; LLMPage.tsx | Existing style tokens, source previews, flashcard interaction, SVG graph, fill-blank/true-false quiz. |
| 7 — Integration | 10 algorithm tests, 16 API/lifecycle cases, 15 frontend cases | Real PDF extraction/chunking/FAISS with an injected embedding provider, persisted reopen, all artifact routes, source checks, Know More tabs and independent Ask Document request passed. |
| 8 — Regression/build | Existing private-cache, book-access, RAG latency, frontend routing/assistant/device-cache suites | 88 backend feature/private/access tests passed; RAG latency 52 passed, 1 pre-existing frozen-manifest mismatch. Frontend build passed; new code lint clean; existing lint warnings remain. Existing frontend suites: 31 routing/read-now, 93 assistant, 11 device-cache passed. |
| 8 — Failures/fixes | Test environment and test imports | Offline npm cache lacked packages; fetched existing lockfile dependencies. Moved Python temporary files into workspace after Windows permission failures. Installed missing test dependencies in isolated venv; used Transformers 4.57.6/sentence-transformers 5.7.0 after newest Transformers broke existing lm-format-enforcer imports. Corrected a new integration test's named LLMPage import. No production model configuration changed. |
| 8 — Large sources | Sentence quotas and vocabulary cap | Improved sampling coverage across selected chunks; added explicit fixed-phrase cloze case; algorithm tests passed after changes. |
| 9 — Documentation | docs/research/KNOWLEDGE_ARTIFACTS_IMPLEMENTATION.md | Recorded exact runtime architecture, algorithms, metadata gaps, routes, lifecycle, limits, authorization, cache behavior, model independence and future work. No pre-existing docs/research directory to update. |
| 10 — Final verification | Final report and output archives | Compared eight core RAG files byte-for-byte against original ZIP; all unchanged. Forbidden generation-dependency search returned no matches in feature modules. AST dependency allowlist test passed. |

Limitations identified during implementation: no verified chapter/section extraction; no MCQ distractor taxonomy; uploaded documents expire with login session; full production startup requires local model weights and external services.

The existing hash test fails on the unmodified ZIP as well: `rag/qa.py` SHA-256 is `73461dea8e565b37851a609e7566e797046452d673f52aeb0701b5196a2129ae`, while `reports/document_rag_latency_baseline/manifest.json` expects `0e78a7c780f691b14c8e3a3337f62054e4c117f0c2df7828099d80da90a793c6`. The manifest and RAG source were not rewritten to conceal that baseline failure.
