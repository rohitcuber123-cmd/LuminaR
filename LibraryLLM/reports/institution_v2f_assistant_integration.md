# Part 2F Assistant and Knowledge Tools integration

This report describes the implemented source boundary. It does not replace the live browser, security, regression or preservation evidence produced for Part 2F. No password, token, private document text or user prompt is recorded here.

## Explicit library document interaction

Library document Q&A is available on the canonical Staff Digital Assets and Patron Resources detail routes. The frontend constructs a `LibraryAssetTarget` containing the route's canonical `libraryId` and `assetId`; `askAsset()` sends it to `POST /libraries/{library_id}/assets/{asset_id}/rag` in the existing RAG service. The screen states that the question uses only the selected document. It accepts the existing concise, normal, detailed and comprehensive answer depths and renders the existing `RAGAnswer` component with returned source filename/page citations.

`rag/api.py` installs `LibraryAssetPipeline` with the resident `engine`. The adapter reuses the accepted `DocumentService` PDF extraction, chunk creation and embedding methods, bounded private-document OCR, the resident retrieval/reranking engine and `engine.ask()`. It creates no second Qwen model, library LLM, new router or catalogue intelligence index.

## Authorization before private reads and generation

`LibraryAssetPipeline.prepared()` calls `library_asset_service.authorize_asset(..., ready=True)` before reading the artifact directory, manifest or chunks. The repository obtains a fresh account, ACTIVE library and exact ACTIVE LibraryMembership through the existing institution guards. ADMIN/LIBRARIAN can use STAFF_ONLY and MEMBERS assets; GENERAL_USER can use only READY MEMBERS assets. PlatformRoleAssignment and historical User.role confer no asset permission. Deleting/deleted assets are concealed and non-READY documents cannot generate answers.

The adapter verifies library UUID, asset UUID, active generation UUID, source checksum, document identity, chunk count and each chunk's tenant/source identity. It checks the artifact checksums before installing the document index. These checks precede retrieval; the code does not retrieve a shared private corpus and filter the answer afterward.

Inside the existing inference lock, `ask()` clears the previous document runtime and latency cache, loads exactly the authorized asset's FAISS index and chunks, and passes its namespaced document identity to `engine.ask()`. It rechecks current authorization immediately before generation and again before returning output. A generation switch produces a conflict instead of serving an answer labelled as current. Returned citations must identify chunks from the selected asset and receive explicit library/asset identity. A `finally` block clears the private runtime and latency cache on success or failure.

Changing MEMBERS to STAFF_ONLY, revoking membership, disabling an account, suspending/removing the library or beginning deletion therefore affects the next protected question and prevents a newly completed answer from being returned after a failing final authorization check. A previously delivered or downloaded document cannot be recalled from a user's device; this is a server access boundary.

## Global Assistant and Select for AI

The accepted global Assistant request and page-context schemas remain `selected_work_ids`, global work IDs and personal/session document IDs. The global Assistant does not enumerate LibraryMemberships to search their documents. Existing `/rag/ask` dispatch still authorizes permanent Book RAG selections through `book_access.authorize_selection` and personal selections through `private_documents.owned()`/`selected()`. A library asset UUID is not registered as a personal session document or global work, so placing it in those older fields does not grant library access.

Typed LIBRARY_ASSET entries were **not** added to the global Select for AI collection. Phase 20 explicitly permits this when adding such targets would require changing the frozen router/schema. The implemented, reviewable alternative is the explicit asset detail Q&A and Knowledge Tools path. Existing globally linked book selection behaviour remains available; selecting that global book does not select or authorize a linked private library PDF. Future typed asset selection needs a separately scoped schema/router review and fresh execution-time authorization.

## Shared Knowledge Tools

The existing `KnowledgeTools` component accepts an optional typed library target. Its API adapter changes only the source URL for that target; personal document URLs remain unchanged. Supported tools are the existing key concepts, extractive summary, flashcards, mind map, quiz and cloze grading. The library adapter reuses `document_knowledge`, `knowledge_algorithms`, `knowledge_quiz`, evidence/relations, `knowledge_cloze`, `cloze_grading` and the existing encoder. It adds no separate model or alternative learning algorithm.

The server exposes scoped artifact list/generate/read/delete, chunk source and cloze-grade routes. Every operation prepares or rechecks the current asset. Generating or reading a permitted study artifact is available to eligible readers; deleting a shared generated artifact additionally requires current library staff authority. Source previews search only the authorized asset's validated chunks. Artifact identities include the owning library, asset, active generation, source checksum/chunk revision, tool parameters and generator/knowledge versions. Artifact files and document-knowledge model caches live inside that asset generation's `knowledge` directory. Equal file checksums across libraries do not share cache paths or cache identities.

The frontend keys the asset workspace and Knowledge Tools session by current account token, library and document. It aborts pending requests and discards previous display state on context switches. File and Q&A adapters also reject a response after token change and verify canonical response identity. Knowledge Tools clears displayed private artifacts/source previews when the next request returns an authorization denial. File reads use the Core's authorized endpoint rather than an exposed storage path.

## Source evidence and limits

| Boundary | Implemented source |
| --- | --- |
| Existing engine installation | `rag/api.py` |
| Scoped document AI routes | `rag/services/library_asset_routes.py` |
| Retrieval isolation, final recheck and cache identity | `rag/services/library_asset_pipeline.py` |
| Fresh membership, visibility and lifecycle checks | `backend/services/library_asset_service.py` |
| Canonical frontend request target | `frontend/src/lib/libraryAssets.ts` |
| Asset page, Q&A, file reader and book resource entry | `frontend/src/pages/LibraryAssets.tsx` |
| Reused Knowledge Tools interface and adapter | `frontend/src/components/knowledge/KnowledgeTools.tsx`, `frontend/src/lib/knowledgeArtifacts.ts` |
| Frozen global context contract | `frontend/src/lib/assistantTypes.ts`, `frontend/src/lib/assistant.ts`, `frontend/src/store/useAssistantStore.ts` |
| Existing Book/personal RAG boundary | `rag/services/book_access.py`, `rag/services/private_documents.py` |

The implementation is per asset. It does not add cross-document tenant semantic search, automatic library discovery for global Assistant, public document publishing or personal-to-library sharing. Browser and automated execution results are reported separately; this source report makes no independent PASS claim.
