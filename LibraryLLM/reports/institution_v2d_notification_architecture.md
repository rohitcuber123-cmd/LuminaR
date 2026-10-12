# Institution Part 2D notification architecture

The existing account-owned inbox, durable notice writer, unread counts,
mark-one/read-all, pagination and bell remain canonical. New notices carry
`scope=GLOBAL|PLATFORM|LIBRARY`; LIBRARY requires a canonical library UUID and
non-library scopes prohibit one. User ID owns every notice. Library name is
hydrated only while the current account has the required active membership.

Tenant notices include type, audience, canonical source type/UUID, original
operation/audit references, created/read/resolution timestamps and dedupe key.
Bodies are generic: no private loan titles, amounts, PDFs, RAG documents, access
codes or invitation secrets are copied into the inbox. The platform account
activity compatibility read excludes tenant notices, closing a privacy leak that
would otherwise appear when the new tenant writer began populating the inbox.

The bell remains an account inbox across libraries. Each item labels its own
source. A single source-based route resolver accepts only recognized type/audience
pairs and exact canonical routes. It does not use the selected library, first
membership, catalogue work ID or a stored arbitrary link. Clicking first fetches
fresh current authorization from `/notifications/{id}/action`; only then does it
mark the account-owned item read and navigate. Destination APIs independently
enforce membership. Missing/revoked membership, role changes and non-active
libraries retain safe history with `Library unavailable` and no actionable link.
Unresolved legacy sources remain labelled for review without fabricated tenancy.

New domain notices originate in existing Part 2B/2C committed operation plans.
They do not add stock, lending, queue or fee mutation logic. The existing journal
adds outbox intents from projected canonical audit effects before persisting its
immutable plan. Staff recipients are current active ADMIN/LIBRARIAN memberships
for that exact library; patron recipients are current GENERAL_USER membership
holders identified by the authoritative domain audit. Legacy User.role and
PlatformRoleAssignment do not expand that recipient set.

`institution_notification_outbox` stores deterministic UUIDs, audit/operation
provenance, recipient, attempts, next-attempt time and PENDING/DELIVERED/SUPPRESSED
state. Only a COMMITTED originating operation may dispatch. The existing durable
inbox dedupe index supplies exactly one stored notice per immutable audit and
recipient. The five-second bounded worker materializes at most 100 rows per scan,
uses backoff on failure, suppresses unavailable recipients, and defers uncommitted
origins so they cannot starve later batches. `notification_outbox_v2d.py` exposes
read-only status and an explicit bounded drain for local/operator recovery.

There is no synchronous post-commit notification callback to fail a successful
domain response. Retrying or losing the inbox acknowledgement does not rewrite the
domain receipt. The standalone Mongo deployment is documented honestly: this is
the accepted persisted-plan/replay model, not a multi-document ACID transaction.
Uncertain domain plans still require the existing operator recovery process.

Global reminders and platform messages remain in their accepted scopes. The old
hourly global-loan reminder worker is retained; it is not repurposed as a tenant
due-date scheduler. Event publication broadcasts, push/email delivery, notification
preferences and tenant reminder scheduling are outside this phase. Legacy notice
migration defaults to a bounded dry run; ambiguous sources remain unchanged.
