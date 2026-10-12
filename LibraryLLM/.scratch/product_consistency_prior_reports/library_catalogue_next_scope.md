# Recommended next phase: Events + Notifications Tenancy V1

This is a recommendation only. No next-phase code, migrations, workers or UI have been implemented.

## Repository evidence

`backend/routes/events.py` exposes account-global `/events` and PlatformRoleAssignment-guarded `/platform/events`. `backend/services/event_service.py` uses a global events collection, global related_work_ids and a seen receipt indexed by user_id. `backend/routes/notifications.py` exposes account inbox operations and platform administration. `backend/services/notification_service.py` stores user_id, source/source_ref and global dedupe keys; platform recipients use the installation account directory. Current header Events and bell remain global. These are the next visible major global dependencies inside a selected-library experience.

## Exact proposed scope

1. Explicit GLOBAL or LIBRARY scope for events/notices. A library event belongs to one immutable library ID; staff commands require fresh active ADMIN/LIBRARIAN membership according to an explicit operation policy. Platform operations continue to govern only global announcements, with no tenant mutation grant.
2. Scoped patron Events pages and scoped unseen/seen receipts. Library A publication cannot change B's seen cursor, count, related books or content. Validate related library_book_id through canonical metadata; local-only books need no global work ID. Global platform notices remain separately labelled.
3. Account inbox authorization plus library context on every library notice. Match recipient identity and eligible active membership; revocation/private membership must stop unauthorized content disclosure. Scope dedupe keys/read-all operations so A cannot resolve B's messages. Preserve existing global notices and independent platform flows.
4. Durable idempotent outbox/worker delivery for accepted canonical loan/request/reservation/fee milestones, integrated through the accepted command journals/commit protocol. Do not add a second lending writer or send external email/SMS by default. Replay, cancellation/expiry, retry, dedupe, crash recovery and revoked-member delivery need explicit tests.
5. Migration report classifies legacy records as evidenced GLOBAL, evidenced LIBRARY, or unresolved. Do not guess a library from legacy User.role, author identity or the first membership. Stage ambiguous records for operator review.
6. Header/nav and workspace pages bind to current library, discard late prior-library responses, and keep platform-global functions separate. Bound feeds/count queries; preserve the existing visual system and 0/1/multi-library account behavior.

## Acceptance before approval

Disposable A/B with the same account, private-library outsider, revoked member, staff-only account and platform-only account must prove scope isolation. Test global+library inbox coexistence, read-all/seen-cursor isolation, local-only related books, approved staff policy, idempotent outbox replay and no duplicate/missing delivery after crashes. Re-run frozen Institution 1/2A/2B/2C, workspace, authority, catalogue, Events, Notifications, Search/KG/Recommendation/RAG and build/lint checks. Capture baseline and migration/ambiguity reports first. No tenant HNSW/KG, analytics, digital tenancy or private vector routing belongs in that proposed phase.

Implementation waits for the user's explicit approval of this next scope.
