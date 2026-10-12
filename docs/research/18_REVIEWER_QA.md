# Reviewer and viva questions with evidence-bound answers

Answers describe current code unless explicitly labeled PROPOSED. Numerical performance is not newly measured. Open exact source symbols using 09.

1. **What is LuminaR?** An implemented intelligent library integration: Mongo catalogue/circulation, semantic discovery, local resource QA, recommendations, contextual assistant and staff/events. It is not yet an isolated institutional catalogue platform.
2. **What is the research problem?** Evaluate whether natural-language retrieval and evidence-aware resource answers help catalogue discovery while preserving relevance, provenance and supported abstention.
3. **What is novel?** No new model or ANN algorithm is established. A rigorous domain benchmark/system comparison and evidence/maintenance tradeoffs could be the contribution (10).
4. **Where is semantic search?** `search/api.py:search` → `RankedSearchPages.search` → `LuminaRSearchEngine.search` → `Snapshot.candidates` (03,09).
5. **Why is it semantic rather than keyword-only?** Query and searchable book text use MiniLM vectors, normalized inner-product similarity provides runtime candidates, and their identities flow to final ranking.
6. **Which fields are embedded?** Title, authors, subjects, description and first_publish_date, with labels in `search/catalogue.py:semantic_text`. Later fields can truncate.
7. **Which model and dimension?** Local MiniLM-L6-v2, 384 dimensions; catalogue max_seq_length is 256 tokens. No state-of-the-art claim is justified.
8. **Why choose MiniLM?** It is the implemented compact model and existing artifacts compare alternatives. Independent current quality/cost evaluation is still needed; historical teacher proxy is not decisive human evidence.
9. **Where is HNSW implemented?** FAISS `IndexHNSWFlat` in `index_manager.new_index`; the project integrates this established library rather than implementing a new graph algorithm.
10. **What are HNSW parameters?** Runtime M32, efConstruction200, efSearch128, normalized inner-product metric. Offline builder defaults efSearch64; serving resets it.
11. **Does HNSW guarantee exact neighbors?** No. Compare against FlatIP for exact-neighbor Recall@k and measure the quality/latency tradeoff.
12. **Where do vector labels map to books?** `Snapshot.candidates` maps positional base/delta labels via work_ids/delta_ids. Overridden base/old delta labels are suppressed.
13. **Is the index a single file?** Current serving state is one global root with legacy base plus version directories/delta files/mappings/manifests and an active pointer; it is not simply one mutable file.
14. **How are additions indexed?** Catalogue mutation journal/queue triggers `_batch_sync`, real embeddings are appended to a cloned delta and a validated snapshot is published.
15. **How are updates indexed?** Searchable-text hash change appends a new vector and redirects override identity; stock-only changes do not require embeddings.
16. **How are deletions handled?** Logical tombstones and live Mongo validation prevent returned deleted identities; graph memory remains until rebuild.
17. **What if dataset/index changes during a query?** The query holds one immutable snapshot. Ranked pages detect generation changes and retry; facts rehydrate live. This is not an all-store serializable transaction.
18. **Is hybrid retrieval implemented?** Optional exact/fuzzy title/author merge exists, default flag off. A BM25+dense RRF system has not been traced.
19. **Does cross-encoder reranking already exist?** Yes, MS MARCO MiniLM L6. Evaluate it rather than describe it as an unimplemented improvement.
20. **How are scores interpreted?** ANN values are normalized cosine; cross-encoder logits and heuristic/minmax evidence scores are ranking signals, not calibrated probabilities.
21. **What is the biggest embedding limitation?** Character chunks exceed the token window; a historical truncation audit reports nearly all sampled book chunks were truncated. Test token-aware variants.
22. **How does book QA stay on the selected book?** Selected work ID is authorized and `RAGRetriever._search_book` uses that book's separate FlatIP index. Missing selected assets do not fall back to another book.
23. **Are all catalogue books full-text QA enabled?** No. Capability requires registered rights-qualified readable text, matching global/per-book indexes and usable chunks plus current borrowing entitlement.
24. **Is global QA equally restricted?** Current no-selection authorization preserves global access. If borrowing is mandatory for all full text, this path must be constrained before making that claim.
25. **Does the assistant read four selected full books?** Metadata comparisons use current selected catalogue facts. Full-text selected-book QA is a separate authorized path; do not conflate them.
26. **Is chat history passed to Qwen for book QA?** `/rag/ask` sends one question/source/depth, no transcript. The tool assistant keeps compact resolved context and IDs; LLMPage's displayed messages are not a full conversational RAG contract.
27. **Which generative model/provider is active?** Local Transformers Qwen2.5-3B-Instruct, NF4 on CUDA or float32 CPU. Mock mode is explicit. No external provider fallback is traced in default QA.
28. **Which assistant router is production-style?** `existing_qwen` default and launchers. V3/V4/V5 are opt-in experimental; reports do not make them the active production path.
29. **How is grounding checked?** Heuristic fast gate plus optional structured Qwen evidence validation, with partial-support second pass; generation receives grounded/refusal instructions. This is a testable mechanism, not a guarantee.
30. **Are sources reliable citations?** Backend emits real chunk/page/work metadata; each generated claim's entailment/coverage still requires evaluation. The model is told not to invent source markers.
31. **What happens on an unsupported premise?** Predicted NOT_SUPPORTED leads to a short evidence-limitation prompt. False refusal and unsafe answers need independent labels.
32. **Is PDF processing OCR?** No, `page.get_text('text')` extracts an existing text layer. Scanned PDFs need future OCR; ingestion is the whole preparation pipeline.
33. **Which document formats are supported by upload?** PDF only in the active route. Offline book TXT processing and inventory CSV/XLSX are different workflows.
34. **How are private documents isolated?** Registry lookup binds document ID to user, session ID, active state and expiry; queries bind one per-document index under the inference lock and clear it afterward.
35. **What happens on logout/deletion?** Revoke session first, disable/delete private artifacts, retry failed cleanup with sweeper. Permanent books and optional local encrypted copies have distinct lifecycles.
36. **Is the cache end-to-end encryption?** No. Prepared bundles are encrypted for browser storage, but server processes plaintext and holds a master-derived key. Avoid claiming server cannot access documents.
37. **How are borrowing races handled?** Process lock plus Mongo lease and guarded decrement/duplicate checks; writes across stock and issue remain separate and require failure recovery tests.
38. **How is return made idempotent?** State/due-date CAS allows one successful return transition, but later fine/activity/stock side effects can fail; completed exactly-once workflow is not proven.
39. **How is fine calculated?** UTC calendar overdue-day difference ×₹5; fine record on return. No cap/configured library policy; same-date lateness can yield zero days.
40. **Does pay actually collect money?** No. It checks ownership/unpaid state and marks PAID. No gateway or bank reconciliation was found.
41. **Do reservations have a queue?** Earliest ACTIVE reserved_at becomes READY_FOR_PICKUP after return. Queues are global by work today, not library scoped.
42. **What does dataset upload do?** CSV/XLSX ISBN matching imports physical holdings of existing catalogue works; it does not build a new institution catalogue/embedding index.
43. **Are dashboard numbers mocked?** Current admin summary uses Mongo counts/fine aggregation; some librarian figures are client-derived. Imported popularity and cached category data are not live usage metrics.
44. **Can staff publish sales/new-book events?** Yes, validated categories and publish/cancel/archive lifecycle exist. No scheduled publication or library audience targeting is verified.
45. **Are all notices emailed?** In-app notification records/polling and due worker are implemented; Brevo integration sends OTP emails. Universal event/loan email delivery is not evidenced.
46. **Is private-library support currently implemented?** Overall **EARLY IMPLEMENTATION / ARCHITECTURAL START — NOT PRODUCTION READY**. Inventory IDs, previews, issue fields and filters are real; membership and isolated catalogues/indexes/RAG remain proposed.
47. **Why does a library need its own ID?** PROPOSED immutable ownership/authorization key for holdings/datasets/history/index generations, independent of display name/location and global work identity.
48. **Why not keep all books global?** Global bibliographic works can stay shared; private institution records/holdings/access must be scoped. The current fallback/global query cannot establish independent private ownership.
49. **How would A's books be prevented from appearing in B?** PROPOSED authorized LibraryContext → B-only candidate index/lexical partition → composite mappings → Mongo query constrained to B → source/result assertion and scoped caches.
50. **Will every library need HNSW?** PROPOSED registry can use FlatIP for small libraries and HNSW for large ones; measure crossover rather than imposing graph overhead everywhere.
51. **Why separate indexes instead of global filtering?** Separate candidate spaces avoid global top-N dilution and simplify deletion/rebuild boundaries. Memory/cold-load costs require comparison; security still needs backend checks.
52. **Does FAISS support metadata filtering?** It is not a document metadata database. The installed wrapper exposes SearchParametersHNSW and inherited IDSelector; current calls pass no selector. Library→label selection, version behavior and completeness must be tested before relying on a shared graph (22).
53. **What happens with thousands of libraries?** PROPOSED bounded lazy-loading registry, exact small indexes, durable job admission, shared embedder and later workers/shards. No measured large-tenant deployment exists.
54. **Can vector IDs collide across indexes?** Local positional label 0 can appear in every graph legitimately. PROPOSED identity includes library, generation and base/delta partition plus label; book/holding IDs remain globally unique.
55. **What happens when librarian deletes/edits a book?** Today global text changes append overrides and deletion tombstones. PROPOSED scoped jobs re-embed/tombstone only that holding version and periodically compact/rebuild.
56. **How can an index rebuild be reproduced?** Freeze dataset/source checksums, ordered holding IDs, text/chunk algorithm, model/tokenizer fingerprint, dimension/metric/parameters and publication generation; rebuild from authoritative records.
57. **What if indexing fails halfway?** PROPOSED staged generation remains invisible; durable jobs retry, prior READY generation serves, validate mappings/checksums before pointer publication. Never silently switch to global retrieval.
58. **Can one user join multiple libraries?** PROPOSED global user plus multiple Membership records and one active-library preference. Private access may require invite/approval; preference does not confer permission.
59. **Where is active library stored and enforced?** PROPOSED client/session preference and explicit request L, but backend LibraryContext resolves membership for every route; frontend filtering cannot enforce isolation.
60. **Should chat follow a library switch?** PROPOSED conversation stays bound to original L; switching creates a new chat, clears pending actions/results and fences late responses by scope revision.
61. **How would RAG isolation work?** PROPOSED L-specific documents/holding index plus L+book/document checks; all source objects revalidate L. Personal PDFs remain user/session-owned.
62. **How should events/analytics be scoped?** PROPOSED immutable event/library and per-user-library seen state, leading scoped aggregation filters and explicit ADMIN platform totals; current events/summary are global.
63. **What tests prove tenant isolation?** FUTURE adversarial duplicate title/ISBN/vector collision, unauthorized L, deletion/corruption/fallback, switching/concurrency, mapping mismatch and RAG citation tests. Zero observed leakage is workload evidence, not a universal proof.
64. **What measurements exist today?** Historical teacher-proxy embedding comparisons, synthetic sync timing, truncation/latency/router/diagnostic artifacts. Their source/data/label limitations are listed in 12–13; no new measurements were made.
65. **What is paper readiness?** 47/100 rubric in 20; substantial implementation, weak independent experimental and novelty evidence. This is an audit judgment, not a statistical metric.
66. **What current paper story should be used?** Resource-specific RAG plus semantic catalogue discovery, evaluated narrowly. Institutional semantic retrieval is future work until implemented and independently evaluated.
67. **What parts are engineering versus research?** Auth/CRUD/IDs/permissions/events/circulation are engineering; retrieval quality, evidence/refusal tradeoffs, source coverage and index architecture experiments can become contributions.
68. **How can the project be reproduced?** Freeze environment/model/data/index manifests, document localhost launch topology and rebuild scripts, remove host-path assumptions, supply rights-cleared evaluation corpus and raw runs. Current lower-bound Python requirements are insufficient alone.
