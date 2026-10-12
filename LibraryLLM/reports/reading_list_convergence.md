# Reading List convergence

Reading List, header bookmark and Saved navigation are one personal concept: reading_list_service, reading_list collection and useLibraryStore. Global-linked local books save the actual OL work ID; existing unique user_id/work_id keys deduplicate the representations. Frontend adopts the acknowledged server target_key before success.

Local-only support uses local:<library UUID>:<book UUID> in the same service/key field. UUIDs normalize. Add requires active GENERAL_USER membership, readable library and an ACTIVE scoped book; no grant/migration. GET rechecks each library, batch hydrates active local records and masks revoked/withdrawn cached metadata. Owners may remove unavailable entries; other users cannot delete them. There is no parallel local saved collection/store.

ReadingListPage uses shared BookCard, canonical local deep links and safe remove controls. Saved entries gain no physical Request action outside canonical owned library cards/detail. Explicit patron_library return metadata preserves library logo/profile/Saved navigation; / and /catalog reset global. Return metadata grants no authority.

Saved responses and success/failure toasts are scoped to the initiating session. Tests cover linked dedup, local saving, revocation masking, staff rejection, ownership, failed saves and session races. Assistant summaries disclose local AI limits; clear/remove uses owner-bound target keys.
