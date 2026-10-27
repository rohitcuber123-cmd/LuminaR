# V2B signal audit

Inspected actual collection counts and field names in `search_v2b_baseline.json`, the Reading List service, recommendation profile construction, and authentication/logout conventions before integrating personalization.

| Signal | Classification | V2B decision |
|---|---|---|
| Reading List global work identity | AVAILABLE_RELIABLE / GLOBAL_ONLY | Use only own saved OL work identities; rehydrate current public catalogue metadata. Ignore copied title/subject snapshots. |
| Reading List local-only book identity | TENANT_ONLY | Use only own saved local identities in the currently authorized library, rehydrated through its catalogue. |
| Global borrowing / returned issues | AVAILABLE_BUT_WEAK | Exists; not used in this batch because legacy records lack consistent tenant provenance. |
| Tenant loans / returned loans | TENANT_ONLY | Exists with library and user identities; not used in this deliberately small initial signal set. |
| Global reservations | AVAILABLE_BUT_WEAK | Exists; not used. |
| Tenant reservations | TENANT_ONLY | Exists; not used. |
| Recommendation feedback | AVAILABLE_BUT_WEAK | Exists; not reused because source/context semantics differ from Search consent. |
| Search history | DO_NOT_USE | Exists with raw queries and result IDs but lacks tenant provenance. No new permanent search history is introduced. |
| Personal book ratings | NOT_AVAILABLE | Catalogue averages exist; no verified personal-rating contract found. |
| Click/open tracking | NOT_AVAILABLE | No reliable scoped interaction contract selected. |
| RAG/chat/document/member/notification/fee/account sensitive content | DO_NOT_USE | Excluded from all profile queries. |

No existing Personalized Search preference was found. A small account-keyed browser preference defaults to OFF; turning it on authorizes only the current user's bounded Reading List derivation. Turning it off avoids profile lookup and preserves V2A ranking, NLU, session refinement, HNSW, KG, and CrossEncoder. The saved preference contains only a boolean. No permanent derived interests are stored.

Boundaries: up to 50 saved global works and 50 saved local works; at most 100 normalized subjects and 50 authors; cache 60 seconds, 256 entries maximum, keyed by account, login session, library, workspace, and profile version. A private local subject never enters a global or foreign-library cache key. A linked saved work contributes only rehydrated public global metadata, with no private ownership or source annotation.
