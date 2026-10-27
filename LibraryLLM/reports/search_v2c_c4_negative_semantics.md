# C4 independently reviewed negative semantics

Frozen AI authorship SHA256: `8edfa36dbc8fd883a059f9a053a104f4eb6d74782c75b1a17e7201b3596a6c8f`. AI_REVIEWED=68; HUMAN_REVIEWED=0. Original labels, predictions, source and failure reports were not visible to the semantic reviewer.

Canonical subjects and text exclusions are different candidate predicates. Do not automatically emit both. Canonical negative requests preserve incidental words in title, author and description. Explicit not-about content negation uses text only. Not-only does not prohibit a category; non-fiction is lexical text unless the current scope provides its canonical category. Chip removal and canonical exclusion choices retain this distinction.

All nine historical broader-exclusion assertions remain raw evidence. Seven legacy rows have versioned field overrides: the original three reviewed defects, two independently reviewed natural-negation disagreements, and two explicit C4 free-prefix title policy changes.

| Review | Decision / strict negatives | Reason |
|---|---|---|
| natural-01 | EXECUTABLE; categories=['Romance']; text=[] | The bare category phrase explicitly excludes the scoped canonical subject Romance. It supplies a category predicate only, not a second literal-text ban. |
| natural-02 | EXECUTABLE; categories=['Romance']; text=[] | The bare category phrase explicitly excludes the scoped canonical subject Romance. It supplies a category predicate only, not a second literal-text ban. |
| natural-03 | EXECUTABLE; categories=['Romance']; text=[] | The bare category phrase explicitly excludes the scoped canonical subject Romance. It supplies a category predicate only, not a second literal-text ban. |
| natural-04 | EXECUTABLE; categories=['Romance']; text=[] | The bare category phrase explicitly excludes the scoped canonical subject Romance. It supplies a category predicate only, not a second literal-text ban. |
| natural-05 | EXECUTABLE; categories=['Romance']; text=[] | The bare category phrase explicitly excludes the scoped canonical subject Romance. It supplies a category predicate only, not a second literal-text ban. |
| natural-06 | EXECUTABLE; categories=[]; text=['romance'] | Not about romance negates content/topic, not just a catalog category. Under the supplied text-negative contract this is represented by the romance literal text negative across the specified searchable fields. A canonical Romance exclusion is not separately inferred. |
| natural-07 | UNRESOLVED; categories=[]; text=[] | Not only romance requests nonexclusivity or broader variety. It does not prohibit Romance and does not justify requiring Romance for every result. The supplied contract does not specify a deterministic diversity/ranking plan or whether to execute a soft preference versus ask for clarification, so no decision or executable gold is forced. |
| natural-08 | EXECUTABLE; categories=[]; text=[] | Non-fiction is a complete lexical category phrase. The review scope supplies no Nonfiction canonical subject, so this review preserves it as a soft category/topic request and does not manufacture a canonical Fiction exclusion or a literal fiction-word ban. |
| natural-09 | EXECUTABLE; categories=['JavaScript']; text=[] | The bare category phrase explicitly excludes the scoped canonical subject JavaScript. It supplies a category predicate only, not a second literal-text ban. The positive Java independently names a scoped canonical subject. |
| natural-10 | EXECUTABLE; categories=['Deep learning']; text=[] | The bare category phrase explicitly excludes the scoped canonical subject Deep learning. It supplies a category predicate only, not a second literal-text ban. AI is not a supplied canonical category; it remains the soft positive topic. |

Partial intent and soft-carrier projections are disclosed in the frozen authored records. No parser probability or LLM second opinion is implemented.
