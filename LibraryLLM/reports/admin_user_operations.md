# Admin user operations

A. Original source: Mongo activity, written by create_activity only after successful issue/return/reserve/cancel/ready/fulfill/fine actions. The old Librarian table displayed date/type/description from /activity/all; Admin had only Staff Management and Books.

B. Target identity: activity.user_id remains canonical. API target_user_id is a readable alias. Email is mutable display/filter data, never ownership.

C. Actor identity: additive actor_user_id on new known writes. Self actions set actor=target; Admin-assisted return sets authenticated Admin actor and authoritative issue owner target. Automatic fine/ready events and unknown historical actors are null. Failures do not produce success audit events.

D. Email resolution: bounded operation page collects actor+target IDs, one users query hydrates current name/email/role. The current user record wins after an email change; no history rewrites. Recipient emails resolve exact case-insensitively to one canonical existing account.

E. Legacy missing targets: 0. Unresolvable current target accounts: 0. Preserve unknown target/ID without guessing ownership from title, dates, email similarity or current borrower.

F. Legacy unknown actors: 88 of 88; retained as null/Unknown actor.

G. Schema: admin_operation_schema.json. Book title hydrates new event snapshot, then linked issue/reservation/fine, then catalogue. Status/due/return reflect the current linked circulation source; occurred_at is the event timestamp. Old events are not migrated.

H. API (ADMIN only): GET /admin/operations; GET /admin/users?q=; GET /admin/users/{id}/activity; GET /admin/summary; POST /admin/operations/return/{issue_id}. Server revalidates the current account role. Existing owner-only /issues/return and Librarian access are unchanged.

I. Filters: user_id, literal case-insensitive current email substring (full email supported), exact work_id, literal case-insensitive title substring, and the eight real operation types. Legacy title filtering follows authoritative source IDs. Inputs are length-bounded and regex-escaped. React does not fetch all history to filter.

J. Pagination: default20/max50, nonnegative offset, newest created_at then activity_id. Browser uses20. The account drilldown shows bounded20-item summaries/counts for active loans, reservations, fines, recent operations and notices.

K. Grouping: optional user grouping within the current server page; it does not imply a full-user-history grouping. Clicking an email opens drilldown and filters by immutable ID. Notify User preselects that account in the composer.

L. Performance: first20-row page median 15.09ms; next page 15.06ms; email filter 10.41ms; drilldown 18.90ms. Local small-history samples, not a production capacity estimate. Batched source/users/books avoid N+1. Admin overview uses counts/aggregation rather than downloading circulation history.

Limitations: current activity88/loans38 baseline is small. Legacy title matching may collect many linked source IDs at larger scale; further load testing/search indexing is deferred. Offset pages are not a snapshot under concurrent new events. Existing max+1 activity integer allocation was not redesigned.
