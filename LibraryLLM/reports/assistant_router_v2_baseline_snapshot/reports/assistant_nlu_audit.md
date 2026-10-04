# Assistant NLU audit — before editing

The live failure originates in `fast_route` / `selected_command` only recognizing closed comparison grammars. An unseen preference follow-up reaches `QwenGateway.parse`, whose context supplies IDs but no selected titles, semantic goal or criteria state. `resolve` accepts model-mentioned entities even when they are conversational references, attempts catalogue resolution, then uses semantic Search as a title fallback. Generic “Choose the book you mean” conflates criteria and entity ambiguity.

| Path | Before: routing | Selection / previous context | Entity lookup / clarification |
| --- | --- | --- | --- |
| Compare, preference, details, availability | Closed regex grammars then Qwen; post-parser regex overrides | Fast rules see current selection/page only; Qwen sees IDs + last intent | Resolver can accept conversational pseudo-titles; generic ambiguity |
| Recommendations | Exact phrases, selected grammar, Qwen, generic recommendation override | Selected IDs win even over explicitly named seeds/ordinals | Optional resolver; context-sensitive prose uses another Qwen call |
| Search | `simple_search` regex then Qwen; concept regex can override | Previous search ID context; exact filter-refinement phrase sets | Existing Search API; title fallback may invoke it in entity paths |
| Account / reading list | Exact phrase dictionaries then Qwen | Account owner is server-derived; book context irrelevant | Existing owner-scoped APIs; reading list ordinals guarded |
| KG | Exact graph phrase set or `MORE_LIKE_THIS` action | One selected/page ID only | Typed ordinal graph intents cannot use normal reference resolver |
| Book / document RAG | Source-question regex or Qwen | Single selected/page book; page document ID | Existing authorized RAG callback; multiple books clarify |
| Mutations | Proposal phrase regex or Qwen | Canonical work lookup, owner-scoped state | Existing pending ID/expiry/confirmation; no direct mutation from parsing |
| Show more / refinement | Exact message or structured action; small phrase lists | `ResultContext` keeps rank order, seeds, filter, offsets | No title resolution; stale page/empty pool guards |
| General help | Concept regex before and after Qwen, or Qwen | Selection/page prevent conceptual override | Response generation Qwen is appropriate here |
| Explicit explain actions | Deterministic explicit action | Last comparison/recommendation snapshots | Optional response-generation call, grounded metadata |

Safe structural rules: action enums/arguments, work ID schema, canonical lookup, owner/session checks, confirmation/TTL, cardinality, pagination, metadata field validation, RRF, API result rendering. Natural-language rules to remove from the live router: `selected_command`, comparison/availability/details/recommendation grammars, manual `differnces` correction, account phrase map, proposal/source regexes, `simple_search`, concept patterns/overrides, generic recommendation overrides, graph phrase list, exact typed refinement lists and prose phrase tests. Ordinal/reference meaning will come from the single semantic decision and be bounded to authoritative supplied IDs.

The pre-edit assistant source is preserved in `assistant_semantic_router_baseline/assistant`. Frozen backend, Search, Recommendation, KG and RAG source hashes are saved alongside it for final preservation verification. No model, ranking, graph, RAG or admin implementation changes are required.
