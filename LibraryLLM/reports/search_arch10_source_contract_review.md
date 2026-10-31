# V10 source-only contract review

Review: `V10_SOURCE_ONLY_CONTRACT_REVIEW_V1`. Separate agent source review; development contract evidence only.

## Historical assertions

### TITLE_ONLY_SUBSTRING_QUOTED_WORDS

Original: `scratch/search_architecture_v9/test_roles_edits.py::test_quoted_filter_words_owned_by_literal_title`.

Decision: **MIGRATION_JUSTIFIED_FOR_STRICT_TITLE_ONLY_REQUEST**.

The sentence explicitly assigns containment to title. Native title_text accepts author-only matches, violating that ownership. Quotation opacity expectation remains valid and must be preserved.

Required equivalent coverage:

- UNSUPPORTED and nonexecutable for strict title-only containment.
- No formats or availability may be invented from the quoted text.
- An author-only matching record must not be returned as satisfying title-only containment.
- A separately explicit title-or-author approximate/general query remains executable and projects the quoted string without format/availability filters.
- Normalized equality via exact_text is tested separately under its title-or-identifier semantics.

### MISSING_PAGES_UNSUPPORTED_DOMAIN

Original: `scratch/search_arch9_regression/test_search_v2c_c4_reviewed_legacy.py::test_curated_candidate_plan[gold-088]`.

Decision: **MIGRATION_JUSTIFIED_IF_CAPABILITY_PRIORITY_POLICY_IS_ADOPTED**.

Page-count filtering is absent from native QueryPlan and matches, regardless of whether an operand is supplied. UNSUPPORTED is a truthful capability-first response and avoids implying that choosing a number will make the operation executable. However native source does not logically force UNSUPPORTED precedence over INCOMPLETE; this is an explicit typed decision policy migration, not a discovered native behavior. Retaining INCOMPLETE while recording unsupported capability would also be execution-safe.

Required equivalent coverage:

- UNSUPPORTED and nonexecutable for missing mandatory page-count requirement.
- IR retains page_count ownership, operator and missing operand state.
- Supplying a numeric page count remains UNSUPPORTED and cannot create a rating/year/text filter.
- Contrast missing supported rating or author operands: INCOMPLETE with targeted clarification.
- Preserve every remaining gold-088 expected field assertion unchanged.

## Native capability findings

- **title_general_relevance**: Semantic provider relevance or normalized substring across title OR joined author text; lexical store may propose fuzzy correction. General title discovery must remain usable.
- **title_normalized_equality**: NFKC casefold, punctuation to spaces, whitespace normalization; equal to title OR any accepted identifier. Not case/punctuation exact and not strict title-only if operand coincides with identifier. Literal quoted content must not create independent filters.
- **title_only_substring**: title_text author fallback violates strict title-only ownership. Postfilter of bounded candidates cannot claim complete recall or catalog pagination.
- **author**: Joined authors are searched by normalized substring, not prefix/equality. exclude_terms is broader searchable-text word exclusion and cannot substitute for negative author ownership.
- **rating**: Missing, nonfinite and uncounted zero rating fail a positive required bound. Institutional hydration obtains ratings from linked global metadata, so unlinked institution-owned books have no rating; they remain discoverable absent a rating constraint.
- **year**: Institutional publication_year survives hydration and native matches enforces bounds; fallback first_publish_date accepted only if four digit year or ISO date. GLOBAL facet capability explicitly false. Missing positive bound data fails match. Malformed hydrated year types can throw rather than prove safe enforcement.
- **language**: Canonical row field survives hydration; missing does not match a nonempty requested language. GLOBAL capability false.
- **format**: ONLINE and PHYSICAL require booleans exactly True; BOTH requires both. Institutional online is authorized READY library asset (MEMBERS visibility for patrons); physical means holding exists. ONLY must project opposite-format exclusion because exclusive_formats alone is not checked in matches. Unknown negative booleans fail open in pure matches, so canonical derivation is required.
- **global_online**: Current active borrow AND readable catalog capability; not catalog-wide ebook existence. Canonical has_physical always False. Negative-only ONLINE has a native execution defect: entitlement set construction and constrained boolean omit excluded_formats, so cannot authorize as natively enforced without isolated repair.
- **availability**: REQUESTABLE needs CIRCULATING and requestable_count>0; AVAILABLE_NOW also accepts online. physical_available_only forbids online-only fallback. No native negated availability field exists.
- **sort**: NEWEST sorts publication_year only, no first_publish_date fallback. Missing fields use zero/empty defaults. Ordering is over bounded candidate set, not complete catalog. GLOBAL NEWEST useful ordering not established by year capability and needs truthful limitation.
- **subject**: Every included subject required; exclusions are set intersection. Interpret only explicitly structured subject/category references through authorized taxonomy. Ordinary topical words must remain semantic.
- **text_exclusion**: Searches title, authors, subjects and description together with normalized word boundaries. Not equivalent to author-only or title-only negation.
- **page_count_price_publisher_edition**: No enforceable native QueryPlan/matches field or predicate. Commercial price comparisons unsupported. Free-to-borrow access preference must not automatically become price comparison.
- **semantic_retrieval**: Global engine.search(query=semantic_text, library_id=None); institutional service.encoder and scoped index, 384 finite vector, with lexical fallback if index unavailable. Semantic relevance cannot be established by source audit. Advisory ranking only by preserved query/ranking_query where native reranker supports it.

## Limits and integration blockers

- Independent means a separate source-only reviewer turn/agent with no V10 candidate/prediction or fresh/heldout population access; it is not an external human approval or full independent acceptance.
- No native modules were imported; only source text/AST and historical normative assertions were inspected. No live DB, JWT, provider, model, index or persistence operations occurred.
- No replacement tests were executed by this reviewer; this artifact specifies their required semantics for implementation and verification.
- Source establishes enforcement code paths, not current service health, populated field quality, relevance, commercial suitability or complete corpus recall.
- Native read_context can enter library_mutation/access_locked canonical maintenance. Treat live use as potentially mutating; this review does not authorize invoking it.
- Global structured raw limit 1000, final candidate bound 50; tenant raw bound 1000 and semantic/reranking bounds truncate before final pagination. Filtering before page slicing protects returned items but does not prove exhaustive counts, full recall or complete catalog sort.
- Post-hydration global acceptance occurs before capability enrichment. canonical recomputes online afterwards but no general mandatory-predicate recheck follows final serialization; adapter tests must inspect final rows.
- Native tenant hydration accepts scoped input rows but does not independently reject a foreign row passed by a compromised fixture. Scope is established by usable aggregate/read_context and must be checked end to end.
- No catalog-wide strict title-only match is qualified. A small postfiltered page is insufficient to claim complete exact/title-only capability.

The JSON companion records exact reviewed file SHA-256 hashes and symbol/line references. No historical source or assertion was changed. A migration may only replace execution of the two identified assertions with the equivalent coverage above while preserving their originals and provenance.
