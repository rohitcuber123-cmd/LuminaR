# Part 2F authorized activity identity hydration

The canonical audit architecture stores immutable `actor_user_id`, `target_user_id`, event code, library UUID, reference metadata and timestamp. It has no historical actor-email snapshot. Invitation events already contain the safe `target_email_normalized` snapshot. This addendum does not update or backfill any historical event.

**Displayed email is current account identity; canonical actor ID remains the historical authority.** Current identity is explicitly marked `CURRENT_ACCOUNT`. When a current target account cannot be resolved and its existing safe event email snapshot is available, the member decoration is marked `EVENT_SNAPSHOT`; its tooltip identifies the event-time meaning. No historical actor email is invented.

The two existing endpoints retain their authority:

- `GET /libraries/{libraryId}/staff/activity`: exact active ADMIN or LIBRARIAN membership.
- `GET /libraries/{libraryId}/audit`: exact active ADMIN membership.

After authorization, rows are fetched with the exact canonical `library_id` and existing server-side pagination (maximum 100 events). The presentation helper rejects mixed-library rows and oversized batches, collects at most 200 unique actor/target numeric IDs, and performs one bounded users query with a projection containing only `user_id`, `name` and `email`. Repeated identities are resolved once per page. Empty ID sets require no users query. Account security/authentication fields are never returned in the identity decoration. Existing canonical audit fields remain present.

The response adds `actor` and `member` objects separately. It does not provide browser account lookup calls. Authorization is checked again after hydration before returning rows, preventing an in-flight membership revocation from returning private identity data. GENERAL_USER, Platform-only authority, legacy ADMIN without membership and cross-library staff do not receive these rows or emails. Historical actors may no longer have current membership: this does not erase an already-authorized library event or its canonical referent.

Resolvable accounts show email as the primary text. Disabled accounts still resolve their existing safe identity. If email is absent, an available name is used. Deleted/missing actors fall back to `Account #<canonical ID>`; this is deliberately restricted to unresolved identity. A null canonical actor shows `System`; member absence shows a dash. IDs for resolved accounts remain tooltip metadata rather than normal primary text.

Isolated tests verify actor/member distinction, current email changes, disabled/deleted accounts, existing member snapshots, immutable event documents, exact-library denial, role-only denial, in-flight revocation and one identity query for fifty rows with repeated users. The real TEST browser verifies the Owner/Admin and Patron emails against canonical account lookup, without hardcoded rendering identities.

Future review only: add actor/member email-at-event-time snapshots for new events if an approved audit-retention policy requires them. No persistence redesign or historical backfill is part of this addendum.
