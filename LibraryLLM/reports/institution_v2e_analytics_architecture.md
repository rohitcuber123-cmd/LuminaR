# Institution Part 2E — tenant analytics architecture

One read-only `GET /libraries/{canonical_uuid}/analytics?range=7d|30d|90d|all`
serves the Staff Analytics page. The default activity range is 30 UTC calendar
days including today through the response's `generated_at` instant. Snapshot
counts remain current regardless of the range. The selected time interval is
start-inclusive and end-exclusive. All-time totals have no lower date bound;
their trend table is explicitly limited to the latest 90 UTC calendar days.
Only days represented by persisted source records appear. Empty days are not
presented as fabricated activity. No library timezone setting is introduced.

## Authority and privacy

Every request parses a UUID and calls the accepted `require_library_staff`
boundary. It resolves the current active verified account, active library and
current ADMIN/LIBRARIAN membership, invitation provenance where applicable,
retained mutation gate and circulation recovery state. It repeats that guard
before returning private aggregates. Token/global/legacy roles do not grant
tenant authority. GENERAL_USER is denied. Platform authority without an
independent staff membership is denied, including private institutions.

ADMIN sees aggregate membership role counts, aggregate waiver/settlement totals
and aggregate notification-outbox health. LIBRARIAN sees ordinary collection,
circulation, reservations, events and operational fee counts/balances/payments;
role breakdowns, waiver/settlement details and outbox health are null and their
capability flags false. Both see only the total number of active memberships.
Membership counts describe membership records rather than behavioural profiles.

No member names, emails, identifiers, fee rows, loan titles associated with
members, reading lists, AI selections, private documents, RAG data, messages,
conversation content or member rankings are returned. The only title list is
bounded local book-level popularity with aggregate signals. No export endpoint,
impersonation, tracking system or tenant mutation capability is added.

## Read-only coherence

Analytics never calls lending `access_locked`, lazy expiry, reservation queue
advancement, catalogue `read_context` or other routines that insert mutation
locks or perform maintenance. It only issues find/aggregation reads. Existing
retained gates and recovery states fail closed; it does not remove them.

Before and after aggregation, constant-sized server-side signatures cover the
append-only tenant audit generation and tenant event count/revision/update
generation. Canonical cutover configurations are also compared. Accepted
inventory, membership, lending, reservation and fee writers persist audits;
Events writers increment atomic revisions. A concurrent completed write or
authority/configuration change returns 503 for refresh. An active/interrupted
gate returns the centralized 503 policy. Mid-read revocation denies access.
This is optimistic consistency under the accepted writer invariants, not a
standalone MongoDB multi-document snapshot transaction.

Part 2D delivery acknowledgements occur independently of the domain journal.
Outbox counts are a separately sampled, ADMIN-only operational health view.
No outbox contents or recipient identities are read into the payload.

## Canonical source decisions

| Metrics | Authoritative source and semantics |
| --- | --- |
| Active local records, local/global links, subjects | `institution_library_books`, exact library UUID and ACTIVE status. No global books query. Subject values deduplicated per local record; top 20 only. |
| Holding quantity | ACTIVE local records joined to `institution_holdings` by exact UUID and local book identity. Quantity sums physical holding units rather than holding-row count. |
| Requestable units | Accepted Part 2B pure projection semantics: holding total minus pending BORROW holds, ACTIVE loans, explicit unavailable stock and unavailable copy conditions. Waiting queues have priority. Reference/unavailable records are not requestable. COPY allocations are verified against known/available copy counts. Inconsistent allocations fail closed. |
| Recent acquisitions / acquisition trend | Persisted creation time of accepted ACTIVE and retained WITHDRAWN local records. Withdrawal preserves actual acquisition history; incomplete PROVISIONING records are excluded. Current collection cards/subjects remain ACTIVE-only. No inferred historical stock series. |
| Circulation snapshot | Canonical Part 2B request and loan status only. Pending BORROW and RETURN requests remain separate. Analytics does not expire persisted pending requests. |
| Circulation activity | Persisted `institution_audit` events for request creation/approval/rejection, confirmed physical returns and renewals. Each event must join its exact library COMMITTED journal operation. Unattributed/uncommitted audits are excluded. Current renewal counts never become a synthetic historical series. |
| Reservation snapshot | Part 2C WAITING + CONVERTED are active; CONVERTED is ready for staff-reviewed borrowing. Average queue depth averages nonempty WAITING queues only. |
| Reservation activity | Canonical committed RESERVATION_CREATED/FULFILLED/CANCELLED/EXPIRED audits. No global-work-ID tenancy inference. |
| Fees | Integer minor-unit fees and immutable CHARGE/CREDIT/WAIVER/PAYMENT_RECORD ledger. Aggregate balances are verified against the ledger before presentation. Current accepted currency is INR with 100 minor units per major. No float conversion. |
| Assessed / payment / waived totals | Fee original assessment amounts at actual fee creation; desk payment and waiver amounts at actual ledger entry creation. Payment records are manual desk records, not payment processing. |
| Settled total | ADMIN-only COMMITTED FEE_PAID audit amount at the actual fully-paid transition. Partially paid balances do not count as settled. |
| Events | Exact LIBRARY scope + UUID in shared Events V1. First `published_at` remains historical even when cancelled/archived. The accepted lifecycle publishes only once from DRAFT, so that field is authoritative publication history; no repeated publication sequence is invented. Cancelled count uses persisted cancellation time; completed means currently PUBLISHED with effective end in the past. No RSVP/attendance metric exists. |
| Active memberships | Current ACTIVE membership records scoped to UUID. ADMIN-only aggregate role breakdown; no reading/financial profile. |
| Popular books | Existing Home signals/statuses and weights: ACTIVE/RETURNED loans at borrowed time ×8; APPROVED/COMPLETED BORROW requests at review time ×2; WAITING/CONVERTED/FULFILLED reservations at requested time ×1. Analytics applies the selected range. Local ACTIVE books with holdings only, top 10, no member ranking. Home's accepted fixed 90-day ranking is unchanged. |
| Outbox health | Exact UUID Part 2D PENDING/retry-required/DELIVERED/SUPPRESSED counters only. ADMIN-only. |

If circulation or reservations/fees have not completed canonical cutover, those
metrics are unavailable with explicit null values and a reason. They are never
replaced by legacy global lending records or fabricated zeroes. Canonical empty
libraries with known configurations correctly report zero.

Money totals are serialized as decimal integer strings so JavaScript cannot
silently lose precision in an installation-wide sum. Counting and grouping stay
in MongoDB. The response contains no complete collection/loan/fee/member lists.
Fractional minor units and MongoDB int64-to-double overflow are rejected rather
than presented as exact monetary totals.

## Query, index and cache design

Each root query and correlated lookup explicitly includes library UUID. MongoDB
facets/groups/counts return constant-sized totals and bounded lists: subjects
20, popular books 10, trend dates 90. Every analytics aggregation has a 10-second
server execution bound and does not spill to disk. Very large all-time datasets
can require a narrower range rather than unbounded request execution.

Accepted tenant indexes suffice: local records by library/status/creation,
holdings by library/local book, loans by library/borrow date/local book,
requests by library/type/status/request date and library/review date/local
book, reservations by library/request date/local book, fee ledger by
library/fee/date, audit by library/date, memberships by library/status/role,
and outbox by library/operation. No speculative analytics indexes were added.

Measured empty-allocation correlated lookups initially dominated the isolated
3,000-record benchmark. Constant indexed existence probes now omit those empty
lookups, preserving the coherence barrier and exact stock semantics. Benchmarks
and execution plans are in `institution_v2e_backend_benchmark.json`; all checked
root predicates use IXSCAN and no global catalogue query is performed.

No cache is implemented. Current records are re-read and authorization is
fresh on every request. Responses send `Cache-Control: no-store`. There is no
library-keyed cache that could accidentally serve another tenant.

## Evidence

`tests/institution_v2e/` uses real MongoDB in a random isolated disposable
database, production account/membership/lifecycle guards and exact canonical
fixtures. Assertions cover role boundaries, revocation, lifecycle, same global
work in separate libraries, exact snapshots/activity/money, committed-only
history, UTC boundaries, privacy, copy projection, no mutation commands,
no lazy expiry, read coherence, bounded lists and indexed larger-tenant reads.
The TEST library and production catalogue are never mutated by this suite.

No ranking/router/Assistant/RAG/HNSW/KG changes or builds are part of this code.
