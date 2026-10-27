# Search Query Understanding metadata audit

Audit uses the existing luminar_library database, canonical services and local accepted artifacts. No fields or genre labels are invented. Global collection contains **5,000,000 books**.

| Capability | Global | Tenant | Classification |
|---|---|---|---|
| Title | title string | title and normalized_title | DIRECT_CANONICAL_FIELD |
| Authors | authors string | authors array | DIRECT_CANONICAL_FIELD |
| Genre / Subject | pipe-separated subjects; book_categories vocabulary | subjects array; membership-protected aggregation | DERIVABLE_FROM_EXISTING_METADATA |
| Description | description | local description or linked global description | DIRECT_CANONICAL_FIELD |
| Rating average/count | average_rating, rating_count | linked global_work_id hydration; unlinked books have no rating | GLOBAL_ONLY / DERIVABLE_FROM_EXISTING_METADATA |
| Publication year | absent in sampled imported schema | publication_year (nullable) | TENANT_ONLY; missing records excluded |
| Language | absent in sampled imported schema | language (nullable) | TENANT_ONLY |
| Online format | account's existing readable borrowed-text entitlement | authorized READY assets; MEMBERS for patrons | DERIVABLE_FROM_EXISTING_METADATA |
| Physical format | legacy global stock is not institution-authoritative | canonical holding existence | TENANT_ONLY |
| Availability | legacy counts cannot prove institution stock | Part 2B projection and READY online resources | TENANT_ONLY; global legacy stock UNRELIABLE |
| ISBN | absent in sampled imported schema | isbn_10 / isbn_13 nullable | TENANT_ONLY |
| Exact work identity | work_id | global_work_id / library_book_id | DIRECT_CANONICAL_FIELD |
| Accession/call number | unavailable | accession_number / local_call_number | TENANT_ONLY |

No normalized genre column exists. Genre / Subject search therefore matches complete canonical subject tokens and never title text. Canonical subject vocabulary examples include Fiction, History, Science fiction, Biography and Detective and mystery stories.

Global publication-year/language filters are not offered in the panel. Explicit natural-language year constraints are retained, exclude missing years, and show a metadata-unavailable notice. Global physical stock filters are not offered. Global online filtering is account-specific and cannot expose staff-only tenant assets.

KG audit: subject membership already provides sufficient deterministic category interpretation. KG is optional and is not queried or rebuilt by this phase.
