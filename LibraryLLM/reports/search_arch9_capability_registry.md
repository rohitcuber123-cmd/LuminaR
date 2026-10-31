# LuminaR Smart Search V9: Versioned Native Capability Registry

## 1. Registry Metadata
- **Version**: `V9-capability-registry-v1`
- **Status**: `AUTHORITATIVE_CONTRACT`
- **Last Updated**: `2026-10-29T14:00:00Z`
- **Purpose**: Authoritative native capability contract for LuminaR Smart Search V9, formalizing supported fields, operators, matching semantics, scope masks, and non-executable boundaries.

---

## 2. Institutional Scope Capability Masks

LuminaR partitions execution across five distinct security and inventory scopes. A query valid in an institutional scope may be non-executable in the global catalog.

| Scope Key | Workspace Type | Rating | Year | Language | Formats | Availability | Semantic | Sort |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `GLOBAL` | `GLOBAL` | ✓ | ✗ | ✗ | ONLINE | ✗ | ✓ | ✓ |
| `PUBLIC_TENANT_PATRON` | `PUBLIC_INSTITUTION` | ✓ | ✓ | ✓ | PHYSICAL, ONLINE, BOTH | ✓ | ✓ | ✓ |
| `PUBLIC_TENANT_STAFF` | `PUBLIC_INSTITUTION` | ✓ | ✓ | ✓ | PHYSICAL, ONLINE, BOTH | ✓ | ✓ | ✓ |
| `PRIVATE_TENANT_PATRON` | `PRIVATE_INSTITUTION` | ✓ | ✓ | ✓ | PHYSICAL, ONLINE, BOTH | ✓ | ✓ | ✓ |
| `PRIVATE_TENANT_STAFF` | `PRIVATE_INSTITUTION` | ✓ | ✓ | ✓ | PHYSICAL, ONLINE, BOTH | ✓ | ✓ | ✓ |

> [!NOTE]
> **Global Catalog Scope Limitation**: The `GLOBAL` scope indices online digital entries. It explicitly lacks structured publication year, language, and physical circulation availability facets. Any mandatory filter on these fields must be refused with `UNSUPPORTED` in `GLOBAL` scope.

---

## 3. Supported Native QueryPlan Field Contracts

| Field | Match Mode | Supported Operators | Negation | Boundary Enforcement |
|---|---|---|:---:|---|
| `title_text` | `APPROXIMATE_OR_TOKEN` | `contains, equals_normalized` | ✗ | Does not enforce strict title-only substring exclusion without author overlap. If exact title match is mandatory, it must be flagged. |
| `author_text` | `EXACT_OR_PREFIX` | `equals, contains` | ✓ | Explicit author values must be preserved. Cannot be dropped into generic search text when trailing clauses exist. |
| `subjects` | `CONTROLLED_VOCABULARY` | `in_taxonomy` | ✓ | Only subjects registered in the scope's taxonomy are projected to hard subjects; other topical descriptions project to semantic_text. |
| `rating` | `NUMERIC_COMPARISON` | `>=, <=, ==, between` | ✗ | Strict intervals must not invert (min <= max). Relative ratings across entities are UNSUPPORTED. |
| `year` | `NUMERIC_COMPARISON` | `>=, <=, ==, between` | ✗ | Unsupported in GLOBAL catalog; supported in institutional tenant catalogs. |
| `formats` | `ENUMERATED_SET` | `in, not_in` | ✓ | GLOBAL catalog supports only ONLINE. Excluding ONLINE in GLOBAL results in UNSUPPORTED. |
| `availability` | `BOOLEAN_OR_STATUS` | `==, !=` | ✓ | Unsupported in GLOBAL catalog. |
| `sort` | `ORDER_SPECIFICATION` | `sort_by` | ✗ | Sort specifications must not be converted into author or title tokens. |
| `semantic_text` | `NEURAL_EMBEDDING_HYBRID` | `semantic_match` | ✗ | Must not absorb failed hard constraints. Background framing discourse must be stripped where possible. |

---

## 4. Unsupported Operations and Contract Conflict Resolutions

A foundational design principle of V9 is **safety over false execution**: the parser must never drop an unsupported mandatory constraint to force execution.

### 4.1 Page Count (`pages`, `page_count`)
- **Status**: `UNSUPPORTED`
- **Backend Limitation**: LuminaR does not maintain normalized page count metadata across the catalog.
- **Contract Resolution**: Requests specifying page limits (`under 300 pages`) MUST return `UNSUPPORTED`. Incomplete expressions (`books under pages`) where operand is missing are treated as unsupported metadata requests.

### 4.2 Commercial Attributes (Price, Cost)
- **Status**: `UNSUPPORTED`
- **Backend Limitation**: LuminaR is a library circulation system, not an e-commerce platform.
- **Contract Resolution**: Requests for prices (`under $20`, `free books`) MUST return `UNSUPPORTED`.

### 4.3 Title-Only Substring Exclusion Conflict
- **Status**: `UNSUPPORTED` (Explicit Capability Boundary)
- **Conflict Analysis**: Legacy test `test_quoted_filter_words_owned_by_literal_title` expected a title-only substring filter to execute. However, the native `QueryPlan` maps titles to `title_text`, which cross-matches both title and author tokens. Strict title-only substring exclusion without author overlap cannot be guaranteed by the native backend.
- **V9 Architectural Decision**: V9 strictly refuses to advertise or execute operations the native engine cannot enforce. This case is intentionally preserved as `UNSUPPORTED`, preventing unsafe false execution.

### 4.4 Cross-Book Relative Lookups
- **Status**: `UNSUPPORTED`
- **Backend Limitation**: Single-pass query planning cannot resolve multi-hop entity references (e.g., `higher rating than Dune`).
- **Contract Resolution**: Must return `UNSUPPORTED`.

---

## 5. Clarification Contracts

When a user's intent is supported in principle but lacks mandatory information or contains unresolved disjunctions, V9 triggers targeted clarification rather than rejecting the query entirely:

1. **Missing Author (`INCOMPLETE`)**: Triggered by explicit `by:` without an author operand. Preserves topical context while requesting author specification.
2. **Unresolved Alternatives (`AMBIGUOUS`)**: Triggered by `either X or Y` across distinct entities. Requests patron choice.
3. **Ambiguous Comma Scope (`AMBIGUOUS`)**: Triggered by complex exclusion lists (e.g. `exclude Romance, Fiction`) where comma binding is grammatically ambiguous.

---

## 6. Architectural Contract Separation Summary

- **Contract A (Interpretation)**: Proposes candidate semantic units, spans, domains, and modalities without assuming capability.
- **Contract B (Validation)**: Validates candidate units against the Authoritative Capability Registry (this document), checking scope masks, operand completeness, and contradiction intervals.
- **Contract C (Planning)**: Emits native `QueryPlan` only for fully validated operations. Never downgrades an unvalidated mandatory requirement into search residue.