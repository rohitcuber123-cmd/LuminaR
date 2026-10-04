# Semantic Router V2 schema audit

The public API contract and deterministic tool executors stay unchanged. A/B/C
retain the old decision dimensions for a controlled comparison; D/E replace the
internal model transport. These are candidates, not a production-readiness claim.

| Dimension | A | B/C | D/E decision |
|---|---|---|---|
| Intent | Compact code `i` | Descriptive public enum | Dynamic public enum / conditional family and action |
| Confidence | `c` | `confidence` | Removed; not an authorization or reliability score |
| Book IDs | `w` | `resolved_work_ids` | Removed; server handles bind canonical IDs |
| Reference scope | `s` | `reference_scope` | Removed when precedence leaves one permitted context |
| Book identities | Supplied context | Same supplied context | Only bounded title/author/position, without IDs |
| Position | `e` | `reference_position` | Available positions depend on cardinality and known focus |
| Goal | `g` | `goal` | FACTUAL/FIELD/PREFERENCE only for COMPARE |
| Criterion | `p` | `criterion` | Optional; only comparison preference or discovery |
| Requested fields | `k` | `comparison_fields` | Comparison/details fields; never factual output values |
| Clarification | `d` | `clarification_type` | Derived from validated missing referent/reading goal |
| Result count | `n` | `requested_result_count` | Existing executor default; removed from model |
| Filters | `f` | `filters` | Available for an existing result-list refinement only |
| Context operation | `z` | `context_operation` | CONTINUE/REFINE only when an active query exists |
| Confirmation | Already removed | Already removed | Existing UI action/pending-action executor remains authority |

Server handles: S current selection, C active previous comparison, R active
recommendations, T other active results, P page, F recent resolved references.
Only existing sources are constructed. S precedes active results, which precede
P and F. An explicit literal entity span can override context. The model sees
the permitted primary source; alternate IDs stay on the server. A single permitted
source is pre-bound rather than classified again. No model-generated IDs exist
in D/E's schema. Selection changes clear stale single-book focus.

One book permits FOCUS. A pair permits ALL/FIRST/SECOND; OTHER and FOCUS become
available only with one known focused member. Larger sets add valid ordinals
and LAST. The server maps each position into the existing contextual executor.

E's conditional JSON branches are DISCOVER, COMPARE, BOOK, ACCOUNT, CONTENT,
HELP, and CLARIFY. ACCOUNT cannot contain any book reference or criterion.
CONTENT/DOCUMENT is unavailable without document context. Reading-list CLEAR
is unavailable to the model; the explicit UI action and existing guard remain.
Available-similar discovery preserves its existing public intent and executor.

Consistency validation rejects unsupported positions, ungrounded/pronominal
entities, account/book contradictions, missing comparison mode/field, comparison
with fewer than two known books, graph with other than one seed, and irrelevant
criteria. Preference with a supplied criterion never asks for a missing criterion.
Missing preference criteria retain the known pair and ask for a reading goal.

F repeats the winning first-pass architecture with at most one focused retry,
only after schema or structural consistency failure. Valid but semantically wrong
outputs cannot be detected reliably by this validator and do not automatically
trigger another generation. No phrase dictionary or natural-language regex
classification is introduced. Fixed conceptual examples are capability-selected.

The 121 held-out messages are sealed in a separate evaluation-only file before
their first inference. They are never imported by production routing. The original
116-message corpus and all prior semantic-router evidence remain preserved.

Frozen: Search/recommendation ranking and pagination, KG, circulation, notifications,
Admin, Book/Document RAG, Know More, and the resident Qwen generation settings.


## Measured outcome and conditional comparison follow-up

E2 requires nullable criterion only for PREFERENCE and nonempty fields only for FIELD; FACTUAL carries neither. Whole-set comparison binding removes redundant position output. Its schema and enforcer contracts pass, but real accuracy is 73/116 and it makes eight non-entity title lookups in the primary corpus. E makes one. The selected flat D+retry profile reaches 76/116, held-out 68/121, and fails safety on two pseudo-title requests. No profile is promoted. The default compact baseline is restored and its original live chain passes 6/6. These failures are preserved rather than hidden behind post-evaluation phrase rules.
