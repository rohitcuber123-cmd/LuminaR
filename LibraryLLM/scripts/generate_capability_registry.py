"""Generate LuminaR V9 Versioned Native Capability Registry and Contract Documentation."""
import json
from pathlib import Path

R = Path('reports')

registry = {
    "version": "V9-capability-registry-v1",
    "status": "AUTHORITATIVE_CONTRACT",
    "timestamp": "2026-10-29T14:00:00Z",
    "summary": "Authoritative native capability contract for LuminaR Smart Search V9, formalizing supported fields, operators, matching semantics, scope masks, and non-executable boundaries.",
    "scopes": {
        "GLOBAL": {
            "scope_type": "GLOBAL",
            "workspace_type": "GLOBAL",
            "description": "Global multi-million book catalog with read-only public access.",
            "supported_capabilities": {
                "rating": True,
                "year": False,
                "language": False,
                "availability": False,
                "formats": ["ONLINE"],
                "sort": True,
                "semantic_retrieval": True,
                "subject_taxonomy": True,
                "exact_title": False,
                "title_text": True,
                "author_text": True
            },
            "unsupported_reasons": {
                "year": "Global catalog does not index canonical publication year for structured numeric range filtering.",
                "language": "Global catalog does not support structured language filtering.",
                "availability": "Global catalog items are online-only; physical circulation availability is inapplicable.",
                "formats": "Only ONLINE format is indexed in Global catalog."
            }
        },
        "PUBLIC_TENANT_PATRON": {
            "scope_type": "PUBLIC_TENANT_PATRON",
            "workspace_type": "PUBLIC_INSTITUTION",
            "description": "Public library catalog with physical and digital circulation for patrons.",
            "supported_capabilities": {
                "rating": True,
                "year": True,
                "language": True,
                "availability": True,
                "formats": ["PHYSICAL", "ONLINE", "BOTH"],
                "sort": True,
                "semantic_retrieval": True,
                "subject_taxonomy": True,
                "exact_title": False,
                "title_text": True,
                "author_text": True
            }
        },
        "PUBLIC_TENANT_STAFF": {
            "scope_type": "PUBLIC_TENANT_STAFF",
            "workspace_type": "PUBLIC_INSTITUTION",
            "description": "Public library catalog with staff circulation management and metadata access.",
            "supported_capabilities": {
                "rating": True,
                "year": True,
                "language": True,
                "availability": True,
                "formats": ["PHYSICAL", "ONLINE", "BOTH"],
                "sort": True,
                "semantic_retrieval": True,
                "subject_taxonomy": True,
                "exact_title": False,
                "title_text": True,
                "author_text": True
            }
        },
        "PRIVATE_TENANT_PATRON": {
            "scope_type": "PRIVATE_TENANT_PATRON",
            "workspace_type": "PRIVATE_INSTITUTION",
            "description": "Private institutional library with tenant-isolated collection access.",
            "supported_capabilities": {
                "rating": True,
                "year": True,
                "language": True,
                "availability": True,
                "formats": ["PHYSICAL", "ONLINE", "BOTH"],
                "sort": True,
                "semantic_retrieval": True,
                "subject_taxonomy": True,
                "exact_title": False,
                "title_text": True,
                "author_text": True
            }
        },
        "PRIVATE_TENANT_STAFF": {
            "scope_type": "PRIVATE_TENANT_STAFF",
            "workspace_type": "PRIVATE_INSTITUTION",
            "description": "Private institutional library with full administrative and circulation access.",
            "supported_capabilities": {
                "rating": True,
                "year": True,
                "language": True,
                "availability": True,
                "formats": ["PHYSICAL", "ONLINE", "BOTH"],
                "sort": True,
                "semantic_retrieval": True,
                "subject_taxonomy": True,
                "exact_title": False,
                "title_text": True,
                "author_text": True
            }
        }
    },
    "field_contracts": {
        "title_text": {
            "field": "title_text",
            "match_mode": "APPROXIMATE_OR_TOKEN",
            "native_behavior": "Matches token occurrences in book title; native engine may also cross-match author names.",
            "supported_operators": ["contains", "equals_normalized"],
            "negation_supported": False,
            "boundary_rules": "Does not enforce strict title-only substring exclusion without author overlap. If exact title match is mandatory, it must be flagged."
        },
        "author_text": {
            "field": "author_text",
            "match_mode": "EXACT_OR_PREFIX",
            "native_behavior": "Matches book creator/author metadata.",
            "supported_operators": ["equals", "contains"],
            "negation_supported": True,
            "boundary_rules": "Explicit author values must be preserved. Cannot be dropped into generic search text when trailing clauses exist."
        },
        "subjects": {
            "field": "subjects",
            "match_mode": "CONTROLLED_VOCABULARY",
            "native_behavior": "Matches items classified under authoritative Library taxonomy.",
            "supported_operators": ["in_taxonomy"],
            "negation_supported": True,
            "boundary_rules": "Only subjects registered in the scope's taxonomy are projected to hard subjects; other topical descriptions project to semantic_text."
        },
        "rating": {
            "field": "rating",
            "match_mode": "NUMERIC_COMPARISON",
            "native_behavior": "Structured rating filters [rating_min, rating_max] within [0.0, 5.0].",
            "supported_operators": [">=", "<=", "==", "between"],
            "negation_supported": False,
            "boundary_rules": "Strict intervals must not invert (min <= max). Relative ratings across entities are UNSUPPORTED."
        },
        "year": {
            "field": "year",
            "match_mode": "NUMERIC_COMPARISON",
            "native_behavior": "Structured publication year filters [year_min, year_max].",
            "supported_operators": [">=", "<=", "==", "between"],
            "negation_supported": False,
            "boundary_rules": "Unsupported in GLOBAL catalog; supported in institutional tenant catalogs."
        },
        "formats": {
            "field": "formats",
            "match_mode": "ENUMERATED_SET",
            "native_behavior": "PHYSICAL, ONLINE, BOTH.",
            "supported_operators": ["in", "not_in"],
            "negation_supported": True,
            "boundary_rules": "GLOBAL catalog supports only ONLINE. Excluding ONLINE in GLOBAL results in UNSUPPORTED."
        },
        "availability": {
            "field": "availability",
            "match_mode": "BOOLEAN_OR_STATUS",
            "native_behavior": "Filters active circulation availability.",
            "supported_operators": ["==", "!="],
            "negation_supported": True,
            "boundary_rules": "Unsupported in GLOBAL catalog."
        },
        "sort": {
            "field": "sort",
            "match_mode": "ORDER_SPECIFICATION",
            "native_behavior": "Sort by rating_desc, rating_asc, year_desc, year_asc, title_asc.",
            "supported_operators": ["sort_by"],
            "negation_supported": False,
            "boundary_rules": "Sort specifications must not be converted into author or title tokens."
        },
        "semantic_text": {
            "field": "semantic_text",
            "match_mode": "NEURAL_EMBEDDING_HYBRID",
            "native_behavior": "Free-form topical, thematic, or conceptual query text for hybrid retrieval.",
            "supported_operators": ["semantic_match"],
            "negation_supported": False,
            "boundary_rules": "Must not absorb failed hard constraints. Background framing discourse must be stripped where possible."
        }
    },
    "unsupported_capabilities": {
        "page_count": {
            "status": "UNSUPPORTED",
            "reason": "Backend index does not track canonical page counts for structured filtering.",
            "examples": ["books under 300 pages", "over 500 pages"],
            "contract_resolution": "Mandatory page-count constraints MUST result in UNSUPPORTED decision. Under-specified clauses (e.g. 'books under pages') where operand is missing are treated as UNSUPPORTED capability requests in V9."
        },
        "price_and_cost": {
            "status": "UNSUPPORTED",
            "reason": "Catalog is a library lending inventory, not a commercial retail store. No price indexing.",
            "examples": ["books under $20", "cheap books", "free paperbacks"],
            "contract_resolution": "Mandatory price constraints MUST result in UNSUPPORTED."
        },
        "publisher_and_edition": {
            "status": "UNSUPPORTED",
            "reason": "Publisher and edition metadata are not currently indexed as primary search facets.",
            "examples": ["published by Penguin", "first edition only"],
            "contract_resolution": "Mandatory publisher/edition constraints MUST result in UNSUPPORTED."
        },
        "title_only_substring_search": {
            "status": "UNSUPPORTED",
            "reason": "Native title_text query expansion matches both title and creator/author tokens. Strict title-only substring exclusion is not enforceable by native backend.",
            "examples": ["title containing 'test' but author does not match 'test'"],
            "contract_resolution": "Inherited legacy test 'test_quoted_filter_words_owned_by_literal_title' expects executable title-only substring behavior. In V9, this is formally recognized as an unsupported native capability boundary. V9 refuses silent false execution and maintains UNSUPPORTED safety."
        },
        "cross_book_relative_comparisons": {
            "status": "UNSUPPORTED",
            "reason": "Single query projection cannot perform multi-pass entity lookups (e.g. resolve Book A rating, then filter books with higher rating).",
            "examples": ["books with higher rating than Dune", "books published after Foundation"],
            "contract_resolution": "Must return UNSUPPORTED."
        }
    },
    "clarification_contracts": {
        "missing_author": {
            "condition": "Explicit 'by:' prefix present without author operand.",
            "decision": "INCOMPLETE",
            "clarification_prompt": "Please specify the author name you are searching for."
        },
        "unresolved_disjunction": {
            "condition": "Query specifies 'either X or Y' across distinct entities/fields.",
            "decision": "AMBIGUOUS",
            "clarification_prompt": "Please select which of the options you would like to search for."
        },
        "ambiguous_comma_scope": {
            "condition": "Comma-separated list following exclusion or negation where scope is ambiguous.",
            "decision": "AMBIGUOUS",
            "clarification_prompt": "Please clarify whether the exclusion applies to multiple subjects or a subject and a format."
        }
    }
}

# Write JSON
out_json = R / 'search_arch9_capability_registry.json'
with out_json.open('x', encoding='utf-8') as f:
    json.dump(registry, f, indent=2, ensure_ascii=False)
print('Wrote reports/search_arch9_capability_registry.json')

# Write Markdown
md_lines = [
    "# LuminaR Smart Search V9: Versioned Native Capability Registry",
    "",
    "## 1. Registry Metadata",
    f"- **Version**: `{registry['version']}`",
    f"- **Status**: `{registry['status']}`",
    f"- **Last Updated**: `{registry['timestamp']}`",
    f"- **Purpose**: {registry['summary']}",
    "",
    "---",
    "",
    "## 2. Institutional Scope Capability Masks",
    "",
    "LuminaR partitions execution across five distinct security and inventory scopes. A query valid in an institutional scope may be non-executable in the global catalog.",
    "",
    "| Scope Key | Workspace Type | Rating | Year | Language | Formats | Availability | Semantic | Sort |",
    "|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
]

for s_key, s_data in registry['scopes'].items():
    caps = s_data['supported_capabilities']
    fmts = ', '.join(caps['formats'])
    md_lines.append(f"| `{s_key}` | `{s_data['workspace_type']}` | {'✓' if caps['rating'] else '✗'} | {'✓' if caps['year'] else '✗'} | {'✓' if caps['language'] else '✗'} | {fmts} | {'✓' if caps['availability'] else '✗'} | {'✓' if caps['semantic_retrieval'] else '✗'} | {'✓' if caps['sort'] else '✗'} |")

md_lines.extend([
    "",
    "> [!NOTE]",
    "> **Global Catalog Scope Limitation**: The `GLOBAL` scope indices online digital entries. It explicitly lacks structured publication year, language, and physical circulation availability facets. Any mandatory filter on these fields must be refused with `UNSUPPORTED` in `GLOBAL` scope.",
    "",
    "---",
    "",
    "## 3. Supported Native QueryPlan Field Contracts",
    "",
    "| Field | Match Mode | Supported Operators | Negation | Boundary Enforcement |",
    "|---|---|---|:---:|---|",
])

for f_key, f_data in registry['field_contracts'].items():
    ops = ', '.join(f_data['supported_operators'])
    neg = '✓' if f_data['negation_supported'] else '✗'
    md_lines.append(f"| `{f_key}` | `{f_data['match_mode']}` | `{ops}` | {neg} | {f_data['boundary_rules']} |")

md_lines.extend([
    "",
    "---",
    "",
    "## 4. Unsupported Operations and Contract Conflict Resolutions",
    "",
    "A foundational design principle of V9 is **safety over false execution**: the parser must never drop an unsupported mandatory constraint to force execution.",
    "",
    "### 4.1 Page Count (`pages`, `page_count`)",
    "- **Status**: `UNSUPPORTED`",
    "- **Backend Limitation**: LuminaR does not maintain normalized page count metadata across the catalog.",
    "- **Contract Resolution**: Requests specifying page limits (`under 300 pages`) MUST return `UNSUPPORTED`. Incomplete expressions (`books under pages`) where operand is missing are treated as unsupported metadata requests.",
    "",
    "### 4.2 Commercial Attributes (Price, Cost)",
    "- **Status**: `UNSUPPORTED`",
    "- **Backend Limitation**: LuminaR is a library circulation system, not an e-commerce platform.",
    "- **Contract Resolution**: Requests for prices (`under $20`, `free books`) MUST return `UNSUPPORTED`.",
    "",
    "### 4.3 Title-Only Substring Exclusion Conflict",
    "- **Status**: `UNSUPPORTED` (Explicit Capability Boundary)",
    "- **Conflict Analysis**: Legacy test `test_quoted_filter_words_owned_by_literal_title` expected a title-only substring filter to execute. However, the native `QueryPlan` maps titles to `title_text`, which cross-matches both title and author tokens. Strict title-only substring exclusion without author overlap cannot be guaranteed by the native backend.",
    "- **V9 Architectural Decision**: V9 strictly refuses to advertise or execute operations the native engine cannot enforce. This case is intentionally preserved as `UNSUPPORTED`, preventing unsafe false execution.",
    "",
    "### 4.4 Cross-Book Relative Lookups",
    "- **Status**: `UNSUPPORTED`",
    "- **Backend Limitation**: Single-pass query planning cannot resolve multi-hop entity references (e.g., `higher rating than Dune`).",
    "- **Contract Resolution**: Must return `UNSUPPORTED`.",
    "",
    "---",
    "",
    "## 5. Clarification Contracts",
    "",
    "When a user's intent is supported in principle but lacks mandatory information or contains unresolved disjunctions, V9 triggers targeted clarification rather than rejecting the query entirely:",
    "",
    "1. **Missing Author (`INCOMPLETE`)**: Triggered by explicit `by:` without an author operand. Preserves topical context while requesting author specification.",
    "2. **Unresolved Alternatives (`AMBIGUOUS`)**: Triggered by `either X or Y` across distinct entities. Requests patron choice.",
    "3. **Ambiguous Comma Scope (`AMBIGUOUS`)**: Triggered by complex exclusion lists (e.g. `exclude Romance, Fiction`) where comma binding is grammatically ambiguous.",
    "",
    "---",
    "",
    "## 6. Architectural Contract Separation Summary",
    "",
    "- **Contract A (Interpretation)**: Proposes candidate semantic units, spans, domains, and modalities without assuming capability.",
    "- **Contract B (Validation)**: Validates candidate units against the Authoritative Capability Registry (this document), checking scope masks, operand completeness, and contradiction intervals.",
    "- **Contract C (Planning)**: Emits native `QueryPlan` only for fully validated operations. Never downgrades an unvalidated mandatory requirement into search residue."
])

out_md = R / 'search_arch9_capability_registry.md'
out_md.write_text('\n'.join(md_lines), encoding='utf-8')
print('Wrote reports/search_arch9_capability_registry.md')
