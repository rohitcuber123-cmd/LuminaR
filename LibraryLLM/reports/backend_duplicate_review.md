# Backend duplicate review

| Overlap | Classification | Reason / writer boundary |
| --- | --- | --- |
| Global /books / tenant catalogue | GLOBAL_ONLY / TENANT_CANONICAL | Metadata vs actual holdings; linked metadata batch hydration; platform metadata never stock authority |
| Legacy availability / tenant holdings | READ_ONLY_COMPATIBILITY / TENANT_CANONICAL | LIB001 legacy semantic availability retained in batches; tenant counts canonical |
| Saved / bookmark / Reading List | PERSONAL_SHARED | One owner-bound service with namespaced local targets and linked dedup |
| Legacy issues/reservations/fees / tenant operations | READ_ONLY_COMPATIBILITY / TENANT_CANONICAL | Old reads retained; old physical mutations 410; Part 2B/C writers only |
| Global/local recommendation hydration | GLOBAL_ONLY / TENANT_CANONICAL | Unchanged global ranking + actual ownership intersection; no filler |
| Global/local Search | GLOBAL_ONLY / TENANT_CANONICAL | Distinct semantic and lexical engines; shared display contract |
| KG/RAG/reader from linked local works | GLOBAL_ONLY / PERSONAL_SHARED | Existing global assets/entitlement; physical loans do not grant digital access |
| Personal legacy / tenant activity | READ_ONLY_COMPATIBILITY / TENANT_CANONICAL | Different labelled histories; no compatibility writer |
| Platform / library management | GLOBAL_ONLY / TENANT_CANONICAL | PlatformRoleAssignment vs LibraryMembership; no automatic internal-library access |


All 190 HTTP declarations and 192 Python modules have source/dependency/call inventories. No route was removed simply because nouns overlap. There is no new physical writer, grant or production migration.

Performance changes: legacy availability is one bounded-batch query instead of per-card lookup; local linked metadata/assets are batch hydrated; local saved entries group by verified library then batch read active records. Filtered count is bounded to 1 second and pagination probes limit+1. Detail remains one-work lookup. Existing unfiltered numeric response contracts are preserved.

Frozen authority/security tests verify retired writers and non-authoritative legacy User.role. New target tests use disposable databases; production TEST is preserved.
