# V10 disabled staging integration proposal

Candidate: `search-smarteng-disabled-proof-10`. No patch in this proposal is active.
The selected design is semantic discovery plus proven native predicates, with no
learned extractor in the normal search path. Overall qualification remains PATH_C.

1. Resolve the exposed complex-query failures before staging qualification. Extend
   source ownership for explicit category/shelf operands, quote-owned normalized
   title lookup, multi-field noun phrases and supported source corrections. Keep
   descriptive subjects in semantic discovery unless the user selects a category.
   Reconcile the old category masks through source-only review; retain raw scores.
   Do not remove inconvenient historical cases or change acceptance thresholds.
2. Add a disabled server-owned adapter around `search/query_execution.py` using
   the existing provider, `catalogue.read_context`, hydration and native
   serialization. QueryIntent must not set tenant, staff, owner or membership.
   Obtain authority before facets/provider access and again before hydration and
   response. Use current backend scope masks, not query/model assertions.
3. Repair the native global negative-only format defect before binding the new
   path: load `active_borrow_ids`/`catalog_capabilities` when excluded formats are
   present, and include exclusions in constrained-provider detection. Preserve
   global ONLINE meaning as actor-readable entitlement. V10's isolated adapter
   demonstrates the repair; active `GlobalQuerySearch` remains unchanged.
4. Pass semantic topics and advisory source text to the existing embedding
   provider. Pass the proven QueryPlan to metadata filtering. Recheck canonical
   hydrated records and serialized results before returning a page. Keep totals
   explicitly limited to the ranked candidate set. Existing native bounds are
   50 global returned candidates and 1,000 structured/local candidate rows;
   neither proves whole-catalog recall. Assess sparse filter recall and offset
   behavior against a real index before choosing expansion/deep paging changes.
5. Preserve exact modes on their existing path. Distinguish title-or-author
   substring discovery from normalized title-or-identifier equality. A strict
   title-only substring or byte-exact literal remains unsupported. A title-only
   postfilter on a small page cannot establish complete matching.
6. After parser qualification, separately authorize real Mongo/JWT integration
   and live membership/revocation tests. Include patron/staff, outsider 404,
   tenant hydration, unlinked records, empty/unavailable global catalog, stale
   index generation, provider failure, pagination and result serialization.
   Linked tenant hydration still depends on global metadata availability; the
   unlinked-record fixtures do not prove full global-outage independence.
7. Keep the frontend unchanged until integration is authorized. Future patches:
   `search/interaction_api.py::ChoiceRequest.query` (150 to a reviewed unified
   500-character contract), `SuggestionRequest.q`, the search query DTOs in
   `search/api.py`, `search/library_intelligence_api.py`, and tenant discovery
   routes, plus `frontend/src/lib/searchNlu.ts`, `frontend/src/components/SearchIntelligence.tsx`, and `frontend/src/components/SearchClarification.tsx` using the existing theme and interaction contracts.
   Treat suggestions and author operands as separately bounded inputs. Update
   backend/frontend contracts together; do not silently truncate longer sources.
8. Bind choices and refinements to original and accepted source, source/IR
   digests, parser version, accepted-plan version, actor, login session, library,
   workspace, mode and expiry. Persist one-use reservation and CAS in the native
   choice/session store only after a separate authorization for real persistence
   testing. Pure previews are not durable commits. Completion and removal reuse
   V10's inherited recompilation contracts; additive filters use source appends.
9. Run a new independent evaluation only after development safety, formal
   migrations, capability consistency, scorer/mask review, structural isolation,
   source freeze and provenance gates pass. Pre-register the requested 95% typed,
   99% execution, zero critical false execution/operand loss and <=5% missed-valid
   thresholds. Include realistic short/medium queries and diverse long requests.
10. Qualify real embedding/reranking relevance with independently labeled book
    judgments, actual service/index health, full-service latency and concurrency,
    current tenant authority and durable choices. No production SLO is set by
    the offline parser timings. Keep C4 routing and activation unchanged until
    independently qualified and separately authorized.

No Mongo writes, production API/frontend edits, index rebuilds, KG rebuilds,
Qwen/RAG changes, new weights or model training are part of this proposal.
