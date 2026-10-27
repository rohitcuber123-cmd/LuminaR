# Search NLU review and remaining limits

Implemented the reviewer-visible canonical Fiction interpretation, four modes, strict ratings/year/format/availability filters, controlled typos, query chips and normal filters. Global, TEST and private tenant HTTP paths were exercised. All tested results satisfy their explicit canonical predicates. KG and Qwen are not required.

Global publication year/language/ISBN are absent in sampled imported metadata, so their controls are not offered globally. Natural-language global year requests show an unsupported-metadata notice and no fabricated dates. Tenant publication year works on actual optional canonical fields; missing values are excluded. Rating count is preserved, with no new confidence threshold or ranking weighting.

The global facet vocabulary is bounded at 4,096 canonical categories, tenant vocabulary at 2,048. Structured candidates are bounded at 1,000, global ranked pages at 50. Sorts cover this candidate universe, not every matching book across 5M. Unindexed broad structured searches may hit the safe 6-second timeout. Future work could build authorized metadata indexes/materialized facet memberships and richer exact ISBN sidecars after review; none were built here.

The parser deliberately recognizes common constrained phrases rather than arbitrary grammar. Ambiguous terms stay semantic with suggestions. Global Online means this account's existing readable entitlement, not all books in the world with an electronic edition. Global physical availability requires selecting a library.

Browser review is incomplete because the saved origin permission blocks the local app. Six viewport checks, visual contrast and real keyboard behavior must be verified after permission is enabled. Backend and JSDOM evidence cannot substitute for Chromium acceptance. Overall review is pending, not a full acceptance PASS. Part 2I has not started.
