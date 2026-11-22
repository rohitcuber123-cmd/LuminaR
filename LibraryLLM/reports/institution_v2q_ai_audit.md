# Part2Q library-aware AI — initial runtime audit

This request replaces the earlier Event RSVP scope. The RSVP audit is retained separately as prior evidence; no Event implementation was applied. This is an incomplete audit, not implementation acceptance.

## Executed baseline

The completed2Q baseline has2997 backend passed,0 failed,20 skipped and1012 frontend passed,0 failed,0 skipped. Build/lint exit0. See institution_v2q_ai_checkpoint.json for execution evidence and application-source equality against the pre-edit checkpoint. No application source has changed.

## Traced assistant path

frontend/src/store/useAssistantStore.ts send builds AssistantRequest using route-derived productLibraryId, session-bound memberships and GENERAL_USER membership for optional lending_context. frontend/src/lib/assistant.ts assistantChat reconstructs an explicit request body and does not copy lending_context. This drops even the existing institution circulation context. This is one confirmed defect, not proof of all observed recommendation failures.

Browser chat goes to /rag-api/assistant/chat, proxied to the existing RAG process. rag/api.py installs assistant.api.install_assistant. assistant/api.py constructs one resident QwenGateway using engine.llm and engine.inference_lock, one HTTP client and AssistantOrchestrator(ConversationStore()). /assistant/chat authenticates with existing get_current_user/security and passes owner sub:sid to orchestrator.chat. No model replacement or new inference process is needed.

assistant/state.py ConversationStore.get checks owner and TTL but has no library scope; frontend saved session key luminar_assistant_session binds owner email and conversation ID, not library. setPageContext updates page metadata without resetting conversation/results. setDocumentContext does reset when its library asset document ID changes. Thus ordinary library switching does not establish a conversation authority boundary.

assistant/tools.py ServiceTransport attaches the request-local bearer to existing Core/Search/Recommendation service URLs. Catalogue/search/recommendation adapters need a validated effective scope before any global tools can be reused for tenant discovery. Existing library_* methods support circulation but are not a general scoped discovery boundary. assistant/orchestrator.py branches on lending_context for circulation/account methods; ordinary discovery is not made tenant-aware by that field. Merely adding the missing frontend field would not solve tenant discovery or history isolation.

assistant/api.py rag_callback already recognizes library:<UUID>:asset:<UUID> and invokes app.state.library_assets.ask with the authenticated user. This route must retain its existing document authorization; rag/qa.py must remain untouched. Cross-context document references still need to be checked against effective assistant scope before tool invocation.

## Existing tenant recommendation path — preserve it

frontend/src/components/ForYou.tsx already has a HomeCatalogueContext branch. It calls libraryRecommendationPage from frontend/src/lib/libraryCatalogue.ts. That helper obtains global recommendations (bounded50,8-second timeout), submits their work IDs to POST /libraries/{UUID}/catalogue/recommendations, verifies the returned library source and rejects foreign result rows. Backend owner backend/services/library_catalogue_experience.py recommendations intersects candidate work IDs with usable current-library records, retains incoming candidate order and fills recent canonical local acquisitions. Ranking label GLOBAL_INTERSECTION_AND_LOCAL_DISCOVERY. This must not be replaced with tenant HNSW recommendations.

LibraryCatalogue.tsx already supports member view=for-you; staff views do not take that branch. ForYou already supports local-home recommendations. The broad claim that private recommendations are wholly absent is therefore not supported by source. Remaining investigation: exact observed page/control, home context provider, book-card Select-for-assistant visibility and behavior for local-only IDs, role-specific routes, small/empty collections and fresh acquisitions.

The existing loadCatalogue books path uses tenant Search/discovery with local fallback for authorized requests. It can separately use globalPage when source catalogue_source is GLOBAL_FALLBACK. This accepted browsing fallback must not silently become tenant assistant results. A scoped assistant must return an accurate empty local result rather than relabel global books as holdings. Source and ownership checks must occur server-side as well as in frontend normalization.

## Required next implementation work

Finish the capability inventory by tracing all adapters in assistant/tools.py, current intent dispatch/continuation/explanation/KG paths, card actions and caches. Add canonical validated effective scope at the existing assistant API/tool boundary, enforce current membership each turn, namespace conversations by owner and effective scope, clear stale frontend conversation/results on context transitions and reject foreign result/book/document references. Preserve global request/response behavior, production existing_qwen routing, global recommendation ranking and private RAG implementation.

For tenant book IDs, use existing canonical local identities and actual holdings; local-only acquisitions cannot be discarded merely because they lack a global work ID. Do not encode local availability from global Book fields. Reuse existing tenant Search/HNSW/local fallback and recommendation intersection services. Enforce final ownership for every discovery/metadata/similarity/availability/KG result. Do not add a second assistant or selector.

No application changes or new-feature tests have been applied yet. All30 conversational scenarios, disposable A/B/global fixtures, actual Chromium flows, performance observations and final regressions remain required. The current baseline is not evidence of new AI integration. No protected manifest, Qwen/RAG implementation, infrastructure security, telemetry, index artifacts, deployment or commit was changed.
