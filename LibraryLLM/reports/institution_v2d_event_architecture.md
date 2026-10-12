# Institution Part 2D event architecture

Events V1 remains the shared renderer, schema, preset validator and atomic event
service. New tenant routes wrap that service with the existing current-account,
LibraryMembership and lifecycle guards. There is one events collection and one
event UUID namespace. Global and tenant APIs apply explicit, disjoint scope
queries; a work ID, title, legacy role or first membership never chooses tenancy.

New tenant records store `scope=LIBRARY`, canonical `library_id`, immutable
`event_id`, `visibility`, the existing content/schedule/category/related-global-
book fields, creator/updater IDs, timestamps and revision. Existing DRAFT,
PUBLISHED, CANCELLED and ARCHIVED transitions are retained. Past is derived from
the existing schedule; no competing completion state is introduced. Cancellation
records actor, timestamp and a required nonblank reason. Published and cancelled
records retain their identity and history. Only unpublished drafts may be deleted.

Current ACTIVE ADMIN and LIBRARIAN memberships may manage their library's events.
GENERAL_USER can read published member events and safe cancelled history, but
cannot create, edit, publish or cancel. PlatformRoleAssignment alone supplies no
tenant authority. Cross-library UUIDs return 404. Private institution events must
use LIBRARY_MEMBERS. PUBLIC is permitted only for a public library with public
access; authenticated eligible outsiders can read its PUBLIC publications. Drafts
and staff provenance remain restricted. Patron responses omit staff email/identity.

Tenant authorization and event writes hold the existing per-library mutation gate.
List/detail reads wait on that gate for up to 30 seconds, which avoids transient
503s when Staff shell summaries load concurrently. Interrupted mutations continue
to fail closed under the accepted operator recovery policy. Single-document event
changes use revision checks and journal-acknowledged writes; they do not claim a
cross-document Mongo transaction.

Canonical frontend routes:

- `/staff/libraries/:libraryId/events`
- `/staff/libraries/:libraryId/events/new`
- `/staff/libraries/:libraryId/events/:eventId`
- `/staff/libraries/:libraryId/events/:eventId/edit`
- `/libraries/:libraryId/events`
- `/libraries/:libraryId/events/:eventId`

Canonical backend paths use `/libraries/{library_id}/events` for staff-authorized
mutations and patron list/detail, with `/staff/events` for staff history reads.
Create, patch, publish, cancel, archive and draft delete reuse Events V1. List
queries have a maximum page size of 50, bounded page/query fields, escaped search
regexes and library/status/date indexes. The optional Patron Home section requests
three upcoming events and quietly omits empty/error results.

Header and footer use the central product context resolver's Events destination.
The established shared Events pages, cards, editor, presets, dialogs and theme
serve Global, Patron and Staff routes. Global `/events` and `/platform/events`
remain explicit global surfaces; the Platform Overview count uses the same global
scope query, so tenant publications cannot inflate its Global Events card. Global
management still requires the accepted
PlatformRoleAssignment. Tenant events do not enter the global badge or catalogue.

Legacy event migration is dry-run by default and needs a per-record approval plus
explicit legacy-to-canonical UUID mapping. The original local global event was
classified and preserved, with zero applied changes. No production apply path is
enabled. See the migration JSON, authorization JSON and pre-change call-site audit.
