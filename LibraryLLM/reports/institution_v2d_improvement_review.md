# Improvement review

The existing Events V1 editor, presets, validators, cards, detail pages and native
dialog component supported tenant scope without a new product surface or theme.
The central product context resolver needed one Events destination helper, keeping
the accepted Global/Patron/Staff home behavior intact. A malformed optional Home
events response is now ignored instead of affecting the accepted catalogue.

The durable Part 2B/2C operation plan was the appropriate notification seam. It
provides canonical event identity and recovery, avoids duplicate business logic,
and permits delivery retries independent of domain receipts. The existing inbox
writer and unique dedupe index were retained instead of creating a parallel inbox.
Platform compatibility activity queries needed an explicit tenant-content exclusion.
The final route audit also found that Platform Overview counted every event row.
Its Global Events card now uses the existing global scope query; an integration
assertion verifies that tenant and ambiguous legacy-library rows are excluded.

Live QA found a concurrent-read integration issue: Events loaded alongside the
Staff summary while the library gate was held. Reads now wait on the same gate
and authorize/hydrate within it. A regression test reproduces that concurrency.
Uncommitted outbox rows also defer to prevent bounded-batch starvation. Frontend
hooks were made unconditional and the shared transport is memoized by library ID.

Appropriate future work, requiring separate approval: notification delivery metrics
and retention policy, supervised production migration, and a review of tenant
analytics or private-document RAG tenancy. These are recommendations only. No new
domain phase, tenant HNSW/KG build, rebuild controls or router research was started.

## Requested follow-up review

These are assessed recommendations, not implemented features. Each requires a
separately approved scope and must preserve canonical library authority.

| Idea | Assessment / boundary for a later phase |
|---|---|
| Due-soon scheduled notices | Reuse canonical tenant loan source and a supervised bounded scheduler; do not reuse legacy global work identity. |
| Overdue scheduled notices | Same boundary, plus per-day dedupe and reconciliation of corrected due dates. |
| Digest | Opt-in account delivery grouping with per-library access revalidation; avoid private subjects in summaries. |
| Email / push | External-delivery receipts, retry/backoff and secret-safe transport after inbox persistence; no exactly-once external guarantee. |
| Notification preferences | Account preferences with explicit library/type overrides; define mandatory notices separately. |
| Event RSVP | A new tenant-owned domain model needs membership and cancellation policies. |
| Event capacity / waitlist | Define canonical capacity and queue ownership; do not reuse lending stock counters. |
| Recurring events | Define series/occurrence UUIDs, timezone/DST and cancellation before recurrence. |
| Event attachments | Audit private file access, retention and ownership before introducing asset URLs. |
| Event reminders | Occurrence identity and current event/member status; cancel outstanding reminders on cancellation. |
| Staff notification preferences | Exact-library routing choices must preserve required operational accountability. |
| Outbox monitoring | Highest-priority operational follow-up: age, pending/retry/suppression counts and secret-free thresholds. |
| Dead-letter queue | Review/replay ownership and limits; retain original provenance and dedupe identity. Current retry metadata is inspectable. |
| Notification retention | Define retention and historical action safety before removing any user/audit history. |
| Event retention | Preserve published/cancelled provenance; define archiving independently of draft deletion. |
| High-volume public-event fanout | Avoid synchronous broadcasts; bounded opt-in fanout needs capacity tests and durable recipient snapshots. |
| Platform announcements | Explicit PLATFORM/global authority; tenant-internal announcements still require membership. |
| Emergency global notices | Separately audited global privilege, confirmation and delivery policy; no implicit library administration. |
| Notification search / filter | Bounded user-owned queries/indexes; never query others' inboxes through the bell. |
| Event calendar view | Presentation candidate using the same authorized event API; no competing event records. |

No item above was automatically implemented. This closure remains Events and
in-app canonical domain notifications only.
