# Knowledge Artifacts implementation

## Purpose

**Deterministic and embedding-assisted document knowledge artifact generation** is the architectural direction. This initial release implements the deterministic branch; it does not compute or require embeddings for artifacts. It derives key concepts, extractive summaries, definition/cloze flashcards, structured concept maps, and basic quizzes for educational and non-educational uploaded PDFs.

Knowledge Artifacts are integrated into Know More. Ask Document remains a separate existing RAG operation. No student-only data model, scheduling, or performance tracking is introduced.

All application paths below are relative to `LibraryLLM/` unless stated otherwise.

## Current architecture: runtime audit

The archive has a Git root containing the application in `LibraryLLM/`. Runtime code differs from the proposed MongoDB/HNSW upload architecture:

| Runtime step | Actual implementation |
|---|---|
| Know More | `frontend/src/pages/LLMPage.tsx`, named `LLMPage` component; `processFile`, `refreshDocuments`, `selectSource`, `sendMessage` |
| API client | `frontend/src/lib/api.ts`: `uploadRAGDocument`, `getRAGDocuments`, `askRAG`; Vite `/rag-api` proxy to port 8005 |
| Upload | `rag/services/private_document_routes.py`: `install_private_documents`, authenticated `POST /rag/upload` |
| Ownership | `backend/dependencies.py:get_current_user` verifies JWT; `PrivateDocuments.identity/owned` additionally verify owner, session ID, expiry, revocation, and ACTIVE state |
| Extraction | `rag/services/document_service.py:DocumentService.extract_pdf`, PyMuPDF page text; `clean_text` normalizes whitespace |
| Chunks | `DocumentService.create_chunks` and `chunk_text`, page-local 3,000-character chunks with 400-character overlap |
| Embeddings | `DocumentService.embed_chunks`, existing normalized 384-dimensional MiniLM vectors; the model instance comes from the existing retriever |
| Upload persistence | `rag/services/private_documents.py:PrivateDocuments`: `registry.sqlite` documents table plus `chunks.json`, `extracted.json`, `vectors.npy`, source PDF, and `runtime.faiss` under each private document directory |
| Private vector index | `PrivateDocuments.publish`, FAISS `IndexFlatIP`; this is not the catalogue HNSW index |
| Retrieval/Q&A | `rag/api.py:ask` authenticates selection, enters `PrivateDocuments.selected` under the existing inference lock, then calls `engine.ask`; existing `rag/qa.py`, retriever/reranker, and `rag/llm.py` remain unchanged |
| Library books | `rag/services/book_access.py`, `backend/services/book_capability_service.py`, and `BookRuntime` separately enforce catalogue/loan entitlement |
| Catalogue HNSW | `search/index_manager.py`: FAISS HNSW base/delta snapshots; not needed by whole-document artifact analysis |
| MongoDB | `backend/database/mongodb.py`: `luminar_library` by default, including users, books, issues, reservations, inventory, reading lists, etc.; not used to persist private uploads |
| Browser prepared-document cache | `local_document_cache.py`, `documentCacheApi.ts`, `localDocumentCache.ts`, `useDeviceDocuments.ts`, `DeviceDocuments.tsx`; opt-in encrypted prepared copies can restore under a new session document identity |

### Provenance audit

Current chunks have `document_id`, `chunk_id`, `filename`, `page`, and `text`. Pages are real one-based PDF page positions, not printed book page labels. Ownership/user/session live in the registry, not the chunk JSON. Vector association is positional, with the same chunk order as the vector array; there is no separately named embedding ID. Page ranges, chapter, section, heading, and paragraph identifiers are not extracted today.

The new provenance adapter maps an existing page to `pageStart`/`pageEnd` and returns null when absent. It passes through optional real chapter/section/heading metadata if present, without claiming it exists on current uploads. There is no destructive migration or ingestion fingerprint change. Old chunks and restored caches remain compatible.

## Existing components reused

Existing PDF extraction, text cleaning, chunk files and identifiers, JWT authentication, session revocation, ownership checks, SQLite lifecycle, FastAPI/Pydantic, React, TypeScript, and Tailwind theme tokens are reused. Existing embeddings, private FAISS indexing, catalogue HNSW, MongoDB, and encrypted device cache remain in their existing workflows. Artifact generation reads text directly, so it avoids repeat vector computation and works if `vectors.npy` is unavailable.

## Artifact generation pipeline

1. Authenticate and authorize the selected private document before reading any text or artifacts.
2. Read and validate its existing chunks; hash the complete stored source bytes.
3. Normalize the supported request: artifact type, entire-document scope, and quick/detailed summary mode.
4. Look up a compatible persisted artifact using source revision, type, scope, options, and generator version.
5. On a miss, select bounded source sentences and run pure deterministic functions.
6. Recheck session/document access inside a SQLite write transaction and persist the structured artifact.
7. Return the artifact and `cached` flag. Concurrent compatible publications converge on one stored result.

Generation is on demand, never part of upload. FastAPI runs synchronous route functions in its worker thread pool. Artifact computation does not acquire the Q&A inference lock or use the engine. Concurrent initial requests may repeat bounded analysis before converging on persistence; no distributed job scheduler is introduced.

## Key concept extraction algorithm

`knowledge_algorithms.py:concepts` extracts bounded one-to-three-word lexical phrases plus longer explicit definitional subjects. Stopwords, common verbs, excessively long phrases, and obvious repeated-character junk are rejected. Phrase frequency uses log weighting and a length preference; explicit definition subjects and trustworthy heading metadata receive bonuses. This is a frequency heuristic, not a POS tagger or semantic model.

Normalized duplicates merge. Token containment and Jaccard overlap suppress near-duplicate labels. Each concept retains up to 12 source chunk IDs and its first available location. At most 24 concepts are returned. A 30,000 ordinary candidate cap limits vocabulary growth; bounded definitional subjects remain eligible beyond that cap. Lexical output may miss specialized or multilingual terminology.

## Extractive summarization algorithm

`sentences` uses punctuation-based boundaries and rejects short, excessively long, lower-case-leading, corrupt, non-prose, or duplicate candidates. Source strings are preserved exactly, including internal extracted whitespace. It does not paraphrase or synthesize sentences.

`summary` ranks candidates using log term frequency normalized by sentence length, concept occurrences, and an early-position preference. Jaccard overlap reduces repetition. Selected sentences return in original source order, with page/chunk provenance. Quick mode returns up to 5 sentences; detailed mode up to 12. Fewer are valid for short documents.

## Definition flashcard algorithm

`definitions` recognizes sentence-initial subjects followed by `is`, `are`, `refers to`, `means`, `is defined as`, `consists of`, or `is used for`. Subject ambiguity, generic words, repeated subjects, circular answers, overly long answers, and weak predicate openings are rejected.

Cards ask what the document says about the concept. Their backs retain the complete original definition statement. This preserves relations such as “used for” instead of silently changing them into identity definitions. Up to 20 definition cards are selected.

## Cloze algorithm

`flashcards` masks a meaningful extracted concept only if it occurs once and enough source context remains. A narrow explicit construction also recognizes phrases such as “uses a fixed time quantum.” A mask is replaced with `_____`; the original matched substring becomes the answer. Restoring the answer reproduces the source sentence exactly. Conflicting normalized blank templates are discarded. Definition and cloze cards together are capped at 40.

Uniqueness is lexical/source-based, not a claim that English allows no possible synonym. The UI asks users to use the document wording. It accepts normalized case, punctuation, and whitespace when checking quiz answers.

## Mind-map algorithm

`mind_map` returns nodes and edges, never an image. Reliable optional hierarchy creates Document → Chapter → Section → Concept branches. With current upload metadata, the normal fallback is Document → Concept. There are no invented chapters or weak semantic-similarity edges.

At most 24 concepts plus bounded grouping nodes are returned (under 60 total nodes). Every edge references an existing node. No duplicate relationships or arbitrary semantic neighbors are added. The React SVG renderer uses depth columns, scroll, drag pan, zoom, reset, selectable nodes, keyboard selection, full-label titles, and source links. Existing dependencies offered no graph renderer; native SVG was sufficient for this bounded tree, so no React Flow dependency was needed.

## Quiz Formats

Quiz supports Multiple Choice (`mcq`), Fill in the Blanks (`fill_blank`), and Match the Following (`matching`). Previously, `knowledge_algorithms.quiz` prioritized existing cloze cards and filled unused capacity with true source statements. The frontend rendered only those two formats; neither requests nor cache options expressed a question-type selection. This backend architecture, rather than a frontend filter, explained predominantly fill-only quizzes. Legacy true/false records remain explicitly readable.

The existing flow remains `LLMPage` → `KnowledgeTools` → `generateArtifact` → `POST /rag/documents/{id}/artifacts/quiz` → `KnowledgeArtifacts.generate` → `knowledge_algorithms.generate` → `knowledge_quiz.generate_quiz` → the existing private SQLite artifact table → the `Quiz` component. The specialized quiz request uses the same URL and service, while other artifact requests retain their previous models and behavior.

### Multi-select behavior

Three semantic checkboxes blend with the existing paper/panel/line/brand theme. Initial requests select MCQ + Fill; matching starts off. Users can select any of the seven nonempty combinations. Zero selection disables generation and displays `Select at least one question type.` Generation disables controls to prevent duplicate requests. Reopening restores a compatible saved quiz and its selection; changing selections never displays an incompatible result. An explicit button opens older saved quizzes separately.

`QuizRequest.questionTypes` uses the typed literal values above, a nonempty list of at most three entries, and rejects unknown types. Older requests without these fields default to MCQ + Fill and 12 questions. The existing UI did not have a count selector, so it keeps 12. API callers may request strict integer `questionCount` values from 1 to 30. Scope remains the existing string `document`; no new scope convention is introduced.

### Generation algorithms

`knowledge_quiz.py` is a bounded, deterministic module. It reuses existing sentence, definition, concept, cloze, identifier and provenance helpers. Only selected generators run. Matching reserves distinct source pairs first, followed by round-robin selection of the requested types. Used facts and normalized concepts prevent cross-type repetition. When one pool is exhausted, capacity goes only to other selected types. A matching set counts as one question. Source quality and deduplication take precedence over the requested count, and the response reports `generatedCounts`, `requestedCount`, and non-disruptive `messages` for unavailable formats or reduced counts. No unselected fallback is inserted.

### MCQ distractor strategy

High-confidence, explicit definition relationships become concept-description MCQs. Four unique source concepts must share an explicit category, such as `a scheduling algorithm that...`, or a source-backed lecture-note family. Selection prefers the same section, page, then nearby sentence order. Concepts without three distinct compatible distractors are skipped. Conflicting descriptions, lexical aliases/acronyms, and highly overlapping descriptions are conservatively excluded. Parent/child concepts remain eligible independently, but contained terms never appear together as options or matching pairs. Every choice retains an `optionSources` excerpt and chunk/page provenance. Stable seeded shuffling varies the correct position; `correctAnswer` is stored independently of the options array.

Quiz version 2.1 adds `knowledge_quiz_sources.py` for line-oriented lecture notes. It reads numbered headings, colon definitions, parenthetical acronyms, and enumerated Applications lists from the existing chunks. It preserves literal source passages across wrapped lines and ignores clause subjects, repeated headers, variables, code, and generic labels. Explicit application lists establish related topic families; nearby explicit definitions/labels can share a source chunk family. Heading-to-passage questions explicitly ask which topic's section contains the passage, rather than presenting an introductory problem statement as an identity definition. Matching uses the same source-backed descriptions. This extends only quiz extraction; ingestion and the other artifact algorithms are unchanged.

### Matching-pair strategy

Matching uses the same reliable concept-description relationships, grouped by explicit category or a shared source chunk. Each set contains three or four unique pairs (within the allowed 3–5 range). Stable left/right IDs define `correctMatches`; the right column is deterministically shuffled and cannot retain its original identity ordering. Every left item preserves its own source excerpt and provenance, while the set aggregates source chunk IDs and page ranges. The frontend uses labeled dropdowns, stacks the columns on smaller screens, requires all choices before checking, and reveals correct pairs and source links with pair-level feedback. It retains existing client-side per-question checking and reset behavior; no scoring API or quiz-attempt database is added.

Fill uses the original `flashcards` cloze candidates without rewriting their questions, answers, IDs, or source excerpts. Answer checking retains the existing case/punctuation/whitespace normalization. Legacy saved true/false questions still render, but new requests never generate them.

### Cache-key changes and Quiz generator version

Quiz alone uses generator version `2.1.0` (`deterministic-v2`). All other artifacts remain on `1.0.0`. Cache compatibility includes source revision, artifact kind, scope, sorted/deduplicated `questionTypes`, `questionCount`, and version, with document and owner enforced by the existing lookup/index. Input order does not affect compatibility. MCQ-only, fill-only, mixed requests, and different counts coexist. Legacy version-1 quizzes remain readable with their old keys but cannot satisfy version-2 generation. The version change excludes saved empty 2.0 quizzes and generates a fresh result on demand. No schema migration, manual cache deletion, or MongoDB collection is needed.

### Source grounding and Qwen independence

Questions, answers, choices, and matching relations come only from the selected document's stored sentences. Exact source excerpts and real chunk/page IDs remain available after checking. The generator imports only standard-library utilities and existing deterministic artifact helpers. It never calls the assistant router/gateway, RAG inference, Qwen, or an external model. Runtime verification wraps the real model's generation method in a temporary harness outside the repository; that harness is excluded from delivered source.

`Quiz Knowledge Artifact → Qwen calls: 0`

### Limitations

This conservative English heuristic can return fewer or zero MCQs when compatible source families or sufficiently distinct descriptions are absent. Lexical ambiguity checks cannot prove that all natural-language synonyms are distinct. Matching pools depend on nearby reliable definitions. Analysis is bounded by the existing sentence/chunk limits, 160 reliable quiz facts, and 240 matching candidates; lecture extraction examines at most 1,200 chunks of 12,000 characters each. Scanned PDFs still require upstream OCR. Answers must use document wording; there is no semantic grading, new total-score rule, question-count UI, advanced inference, adaptive learning, or essay generation.

## Database/persistence design

`knowledge_artifacts.py:KnowledgeArtifacts` creates one generalized `knowledge_artifacts` table in the private-document registry database. Columns include artifact ID, document ID, owner, type, compatibility key, JSON payload, and update time. The payload contains scope, generator/version, options, structured content, aggregate source IDs, source revision, timestamps, and analysis bounds.

The unique `(document_id, owner, type, cache_key)` index supports lookups and idempotent publication. A foreign key to `documents(id)` uses `ON DELETE CASCADE`. `PrivateDocuments.db` now enables SQLite foreign keys in addition to its existing secure-delete setting. Purge/logout/expiry cleanup therefore removes artifacts with their source record. No MongoDB collection or index is introduced: keeping private derived content in MongoDB would unnecessarily split the existing session lifecycle.

Old compatible quick and detailed summaries can coexist. Regeneration prunes historical artifacts for the same type/options. There is no artifact export into the browser encrypted-document bundle; a restored document in a new session generates fresh artifacts. Reopening Know More within the same active session uses saved artifacts.

## API routes

`knowledge_routes.py:install_knowledge_artifacts` is registered alongside existing document routes in `rag/api.py`. All success responses set `Cache-Control: no-store`; application persistence is distinct from HTTP/browser caching.

| Method | Route | Result |
|---|---|---|
| GET | `/rag/documents/{document_id}/artifacts` | Compatible stored artifacts |
| POST | `/rag/documents/{document_id}/artifacts/key-concepts` | Key concepts |
| POST | `/rag/documents/{document_id}/artifacts/summary` | Extractive summary |
| POST | `/rag/documents/{document_id}/artifacts/flashcards` | Definition/cloze cards |
| POST | `/rag/documents/{document_id}/artifacts/mindmap` | Structured nodes/edges |
| POST | `/rag/documents/{document_id}/artifacts/quiz` | Source-grounded questions |
| GET | `/rag/documents/{document_id}/artifacts/{artifact_id}` | One compatible artifact |
| DELETE | `/rag/documents/{document_id}/artifacts/{artifact_id}` | Delete an owned artifact |
| GET | `/rag/documents/{document_id}/sources/{chunk_id}` | Authorized source excerpt |

POST body: `{ "scope": "document", "mode": "quick" }`; `{}` uses defaults. Mode may be `quick` or `detailed` and only affects summary compatibility. Other scopes and extra fields are rejected rather than silently fabricating structure. Unknown artifact kinds return 422. Cross-owner/session and missing documents return 404; expired sessions return 401. Missing/corrupt chunk files return 409. Sources over the analysis file bound return 413.

## Frontend components

- `LLMPage.tsx`: Ask Document / Knowledge Tools navigation for selected uploaded documents; catalogue-book Q&A is unchanged.
- `lib/knowledgeArtifacts.ts`: typed authenticated API client with safe error messages, cancellation, and session-token checks.
- `components/knowledge/KnowledgeTools.tsx`: persisted artifact loading, explicit generation, tabs, summary modes, definition/cloze filtering, flashcard flip/navigation, quiz checking, loading/errors/empty states, source excerpt panel.
- `KnowledgeMap.tsx`: SVG structured graph, pan/zoom/reset, pointer and keyboard selection.
- `SourceLink.tsx` and `styles.ts`: shared provenance and current LuminaR border/color/button styling.

State is scoped to document and auth token. Switching documents or accounts unmounts the old state and aborts requests; late replies are ignored. Derived content is not written to localStorage or IndexedDB. Layout uses wrapping controls, responsive columns, scrollable content, and an independent map viewport.

## Caching and document changes

Compatibility includes document/owner, source SHA-256, artifact type, scope, relevant options, and `generatorVersion` (`1.0.0`). The identifier is `deterministic-v1`. Source edits or a version bump make old artifacts disappear from list/get and trigger regeneration. Current upload/restore APIs do not edit existing chunks, but content hashing also handles externally replaced source files on subsequent requests. A file change during an in-flight generation is not atomically locked; the next read invalidates that result.

## Source provenance and authorization

Artifacts carry source IDs and available page/structure metadata. Source previews use a separate authenticated endpoint and confirm the chunk belongs to the authorized document. Paths never derive from arbitrary chunk IDs. A restored chunk ID may retain its original upload prefix; access is still resolved against the current document registry and chunk file, not the prefix.

Generation, list, get, delete, and previews all enforce server-side access. Publication rechecks the registry under a write transaction, preventing a concurrent logout/deletion from resurrecting derived records. Existing revocation, session expiry, sweeper retries, and private 404 behavior remain intact.

## Graceful degradation

No embeddings: lexical algorithms still operate. No structure: flat concept map and unknown location labels. Missing page metadata: null, never invented. No suitable prose: persisted empty artifact and a clear UI message. No trustworthy MCQ distractors: skip those candidates and use only other selected formats, reporting reduced coverage. Missing source files: re-upload/restore message. Invalid token or unavailable document: safe actionable error without backend stack traces.

## Performance strategy

- Maximum source JSON: 64 MiB; source preview: 12,000 characters.
- At most 1,200 evenly spaced chunks and 6,000 valid sentences; sentence quotas sample across selected chunks rather than consuming only the beginning of a long book.
- At most 12,000 characters analyzed per chunk, bounded vocabulary, 24 concepts, 5/12 summary sentences, 40 cards, fewer than 60 graph nodes, and 12 quiz questions.
- Large-document sampling is disclosed in the UI. Concepts/summary topics can be omitted by these bounds.
- No repeated embeddings, model loads, HNSW work, automatic upload generation, or large client graph payloads.
- Cache lookup still reads/hashes the bounded source file; cache compatibility favors correctness over a new ingestion-version subsystem.

## Qwen independence

**Knowledge Artifact → Qwen calls: 0**

Generation modules depend only on standard-library analysis, existing ownership/database access, FastAPI, and Pydantic. They have no generative-client, assistant, gateway, chatbot, or model-router import/call. An AST dependency allowlist test protects this boundary. The frontend artifact client addresses only the new document/artifact/source endpoints.

The existing RAG API process still constructs the existing Qwen engine at startup; this feature does not change that application boot requirement. Once registered, artifact analysis does not use the engine. Ask Document continues through the existing Qwen/RAG path. Core RAG files and Qwen configuration were byte-compared with the supplied ZIP and are unchanged.

## Tests and verification

New backend tests cover filtering, duplicate merging, exact extraction, source restoration, short-document cloze, graph integrity, quiz fallbacks, algorithm limits, legacy metadata, dependency isolation, real PDF extraction/chunking/FAISS construction with a test embedding provider, all new routes, authorization, source previews, persistent reopen, version/content/options invalidation, concurrency, document deletion, and logout during generation.

New frontend tests cover loading/generation, persisted reopen, tabs, flip/navigation/filter, source preview, SVG selection/zoom/reset, quiz checking/retry, summary options, safe HTTP errors, empty states, busy state, late responses, token changes, and rendering the real `LLMPage` with Knowledge Tools and the independent Ask Document request.

Run from `LibraryLLM/`: `python -m pytest tests/test_knowledge_quiz.py tests/test_knowledge_algorithms.py tests/test_knowledge_artifacts.py -q` for all 78 artifact/quiz checks. The 2.1 fix adds seven lecture-note format combinations, wrapped/colon/acronym extraction, code/clause rejection, parent/child preservation, helper dependency isolation, and replacement of saved empty 2.0 quizzes. Broader regression coverage previously ran `tests/test_private_document_cache.py`, `tests/test_book_access_control.py`, `tests/test_assistant_selected_context.py`, and `tests/test_document_rag_latency.py` (242 passing checks and one pre-existing frozen-manifest failure). Use a writable pytest temporary directory and bounded `OMP_NUM_THREADS`/`MKL_NUM_THREADS` in restricted Windows environments. On this Windows installation, FAISS DLL initialization during collection required disabling automatic pytest plugins and importing FAISS before PyTorch and pytest. The Quiz upgrade covers all seven format combinations, strict empty/type/count validation, category/distractor quality, shuffled answer positions, matching ID integrity, source grounding, reduced-count behavior, cross-format deduplication, cache/count/version isolation, legacy readers, ownership, and no-inference assertions.

Run from `LibraryLLM/frontend/`: `npm ci`, `npm test`, `npx tsx --tsconfig tsconfig.app.json --test tests/document-cache.test.tsx`, `npm run build`, and `npm run lint`.

Exact execution results and acceptance status are provided in the accompanying final implementation report. Initial artifact validation used an injected test engine. Subsequent local setup installed real MiniLM, CrossEncoder and Qwen weights and an isolated local MongoDB. The Quiz upgrade's verification additionally uses a real eight-page uploaded PDF, all seven request combinations, cache replays, source checks, and a temporary real-model inference counter. This verification harness is outside the repository and is not shipped as an application endpoint.

## Limitations

English-oriented lexical heuristics are intentionally conservative. Scanned/image-only PDFs need upstream OCR, which is outside this feature. PDF punctuation, hyphenation, abbreviations, headers, tables, and sentence fragments across chunk/page boundaries can reduce coverage. There is no automatic chapter detection, page-range UI, PDF highlighting/navigation, or semantic graph edges. MCQs require source-backed categories/families and distinct descriptions. Source previews expose existing text/page metadata.

Artifacts apply to private uploaded/restored documents; permanent borrowed catalogue books retain the existing Q&A UI. Artifacts expire with the source session, are not copied into encrypted device bundles, and do not persist across restore identities. The existing RAG process still requires its configured models at startup. The repository's broad Python dependency constraints also allow incompatible newer Transformers/lm-format-enforcer combinations; validation used compatible Transformers 4.57.6 and sentence-transformers 5.7.0 in an isolated environment without changing project dependency declarations.

## Future improvements

Future work includes reliable PDF structure metadata, genuine section/page scopes, OCR, confidence evaluation on broader corpora, optional reuse of existing embeddings, broader evidence-backed MCQ category recognition, and artifact bundle versioning.

Not implemented: spaced repetition/SM-2, correct/incorrect review scheduling, adaptive learning, weak-topic detection, quiz attempt/performance tracking, personalized difficulty or study plans, advanced quizzes, Qwen-enhanced cards, timelines, charts, process diagrams, collaborative decks, or analytics. Future adaptive flow may use review outcomes → scheduling, quiz attempts → weak topics, and weak topics → relevant chunks → additional grounded cards.
