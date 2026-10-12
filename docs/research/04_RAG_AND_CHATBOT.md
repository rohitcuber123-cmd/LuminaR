# RAG, selected-resource grounding, and assistant audit

## Active full-text QA path

`frontend/src/pages/LLMPage.tsx:683–735 sendMessage` sends one question, depth and selected source through `lib/api.ts:784–816 askRAG` to `/rag-api/rag/ask`. It holds a conversation revision to discard late responses after a resource change. `rag/api.py:191–276 ask` validates query/depth and matching `document_id`/`work_id`, serializes inference with an `RLock`, clears transient document runtime, authorizes a selected book or session-owned PDF, refreshes changed book assets, and invokes `LuminaRAG.ask`.

Book access is substantive server logic: `rag/services/book_access.py:8 authorize_selection` calls `book_capability_service.authorize_know_more`; active issued borrowing, registered full text, and indexed capability are checked. `book_assets.py` discovers mapping and rights-qualified `.book.json` registrations, validates index/metadata/chunk identity, and restricts text paths to the processed directory. Presence in a recommendation or reading list does not confer entitlement. An unselected request returns `None` from authorization and preserves global book retrieval. Consequently the protected selected-book path does **not** prove that global `/rag/ask` applies identical borrowing rules. This is a P0 entitlement policy gap if all full text is intended to require borrowing.

```text
Selected work → active borrow/capability validation → per-book FlatIP index
Selected PDF → owner + sid + expiry validation → per-document FlatIP runtime
Question → intent analysis → retrieval/expansion → cross-encoder + evidence score
→ diverse context (24,000-character budget)
→ deterministic fast evidence gate → Qwen validation if needed
→ optional second retrieval pass on partial support
→ prompt or refusal prompt → local Qwen generation → structured sources/verdict
```

## Retrieval and reranking

`RAGRetriever.search:628–759` embeds the query, chooses uploaded-document search, per-book search, or global book search. `_search_book:766–852` loads the exact selected book's FlatIP index; missing index returns empty results instead of substituting another book. The per-book LRU holds five books. `BookRuntime.refresh` reloads modified global book assets and clears book cache under inference lock.

`RAGReranker.search:125–445` expands book questions using deterministic rules in `evidence.generate_expanded_queries`; document questions use the original query. Each retrieval query requests 15 chunks; candidate union is capped at 40 in insertion order. A duplicate chunk's matched-query list is extended, but the shown merge does not update it to the best later dense score. The same MS MARCO L6 cross-encoder scores query/passage pairs. Final score is `0.30 * minmax(crossencoder) + 0.55 * evidence + 0.15 * minmax(dense)` (`evidence.py:8–10`, reranker `413–421`). These weights are heuristics, not learned/calibrated relevance estimates.

Evidence features include actor/target/event term alignment, first-person/speaker cues, local causal windows, directionality, temporal phase, motivation/consequence cues and overlap redundancy. `evidence.calculate_evidence_score:586+` and `fast_filter.run_fast_filter:616+` are unusually detailed domain heuristics and suitable ablation subjects. They do not establish semantic entailment or universally valid causality. Minmax scaling can make a weak candidate appear relatively high when all candidates are weak.

`DEPTH_CONFIG` requests candidates/context chunks/max output tokens: concise 10/4/300, normal 15/7/320, detailed 20/10/1000, comprehensive 20/15/1500. Underlying retrieval still uses 15 per expanded query and the 40-union cap. Context selection uses diverse chunks and 24,000 characters, with special one-chunk handling for some factual cases. Record the actual prompt token length; a character cap does not guarantee tokenizer budget.

## Generation, validation and active provider

`rag/llm.py:44,150–194` loads local cached `Qwen/Qwen2.5-3B-Instruct` through Transformers. CUDA uses 4-bit NF4, double quantization, float16 compute and device_map auto; CPU uses float32. Generation is deterministic by default (`do_sample=False`); QA passes temperature 0.0. `lm-format-enforcer` constrains structured intent/evidence outputs. Qwen is both validator and generator, introducing correlated errors. No external LLM API, provider fallback chain, or commercial-provider routing is active in the traced default path. `LUMINAR_MOCK_LLM` explicitly produces a placeholder; never report mock answers as model evidence.

`qa.ask:716–839` uses FAST_ACCEPT/FAST_REJECT/NEEDS_LLM_VALIDATION. Verified author metadata and supported overview patterns may bypass model validation; partial support triggers another retrieval/validation pass. Unsupported questions still call the LLM with a narrowly scoped refusal prompt. Return verdict is not a measured correctness label. `qa.build_compact_prompt:438–482` instructs grounded interpretation, actors, negation, temporal order, and no invented source markers; `llm.SYSTEM_MESSAGE` repeats those boundaries. Malicious retrieved text remains a prompt-injection risk even with instructions.

The default API installs `DocumentLatency(mode='fast')` (`rag/api.py:70–71`, `document_latency.py:140–153`). It extracts literal intent slots for a small set of unambiguous PDF questions and uses compact document prompts for eligible normal/concise definitions/topics. Complex questions fall back to original analysis. Alternative baseline/answer_only/cache modes are experiment controls, not the default. The adapter reuses existing models and preserves context; no blanket latency benefit is established.

Structured sources include filename/page/chapter/chunk ID/work ID/title/author and ranking/evidence diagnostics (`qa.py:875–935`). Generated prose is told not to invent `[Source X]` markers. This is provenance presentation, not validated sentence-to-source citation attribution.

## Conversation and selected context

The full-text `/rag/ask` contract contains no chat transcript or conversation ID. LLMPage shows local message history, but each request is question-only; follow-up pronouns may lack previous-answer context. This differs from the contextual assistant.

`AIChatWidget` uses `useAssistantStore`, sends `/assistant/chat`, and permits up to four selected catalogue books. `install_assistant` creates a `QwenGateway`, in-memory `ConversationStore`, transport client and `AssistantOrchestrator`. The owner is `user sub:sid`; conversations expire after 1800 seconds, have a maximum of 1000, and keep compact resolved turns and canonical IDs rather than raw history. Frontend sessionStorage persists owner/selection/conversation ID, not durable server conversations. Service restart or different worker can produce an expired conversation.

AssistantTools call core/search/recommendation through authenticated HTTP and invoke the same authorized RAG callback. Selected-context `evidence_packet/metadata_packet` and constrained `respond` produce metadata comparisons and explicitly tentative interpretations; they do not retrieve all selected full books. Describe these two grounding levels precisely in a viva.

Mutations use pending action IDs and explicit confirmation; consume-before-send prevents automatic retry after an uncertain commit. Circulation writes require `ASSISTANT_MUTATING_ACTIONS_ENABLED`, default false; reading-list edits still require confirmation. The ordinary core UI can call authorized circulation APIs directly.

## Router status

`ASSISTANT_ROUTER_MODE` defaults to `existing_qwen`, confirmed by production-style launchers. V3/V4/shadow/V5 load only under explicit configuration; V2 compatibility code is not selected by the production gateway (`allow_experimental=False`). Router reports/weights/training are **EXPERIMENTAL**, not evidence the production assistant uses a newly trained router. Tests verify many routing/selection contracts; scientific accuracy and actual running mode remain separately bounded.

## Weaknesses and research requirements

P0: align unselected and selected full-text entitlement; fix or evaluate embedding truncation; independent supported/unsupported QA set; calibrate refusal/false-refusal tradeoff; source-isolation audit after concurrent switching; atomic multi-file book publication. P1: evaluate learned/ablated evidence features, candidate union ordering, token-aware chunks, claim-level source attribution and transcript-aware follow-ups. Use [12](12_EXPERIMENT_PLAN.md) for paired Qwen-only, dense RAG, cross-encoder RAG, full evidence pipeline and gates-off comparisons.

## Proposed library scope

Require `LibraryContext=L` before any catalogue/book retrieval. Authorize `holding belongs to L AND user may borrow/access L`; registry chooses only L's published resource generation. Retrieval mappings and source objects carry L. Personal PDFs retain `userId+sid+documentId` ownership; library-shared PDFs use `libraryId+documentId+ACL`. Do not silently combine those corpora. Conversations remain tied to their original library; switching opens a new one and clears pending actions/results. This is **PROPOSED**, not implemented.
