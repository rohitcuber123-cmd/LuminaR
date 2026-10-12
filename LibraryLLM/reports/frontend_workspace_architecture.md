# LuminaR workspace architecture

The old interface placed product navigation, one active-library selector, exploration,
registration, invitations, inventory, personal loans, circulation and administration
in persistent horizontal navigation. A global role could suggest the wrong library workspace.

The new product header contains global navigation, search, saved books, notifications
and the avatar. The permanent institution strip is removed. The avatar groups active
patron memberships separately from staff memberships and bounds each preview to three.
The searchable My libraries page provides the complete list. Library selection belongs
inside the corresponding workspace; no broad global tenant selector remains.

## Authority and contexts

ACTIVE GENERAL_USER opens the patron workspace. ACTIVE ADMIN (including owner) and
LIBRARIAN open the staff workspace. The account's global role never overrides a library
membership. No dual membership role or impersonation mode was added. Owner remains an
ADMIN membership carrying existing owner status.

WorkspaceRoute resolves the URL tenant through /libraries/:id/context before mounting
tenant content. A wrong-mode URL redirects to the membership's actual home. Admin-only
members/audit screens also check the local membership. Every backend operation continues
to enforce its own tenant authorization. Convenience state never grants permissions.

The institution store keeps patronLibraryId and staffLibraryId independently, owned by
the account identity and current session. activeId is only a compatibility projection
of the mounted URL tenant. Logout/account changes invalidate pending selections and
refreshes, clear both contexts and remove the old luminar_active_library storage key.
Only same-owner saved convenience state can be restored; server refresh revalidates it.
Selection sequence counters prevent late requests from routing to a stale tenant.
Abort/session checks discard queued work for an old account. Frontend requests to the
same institution are sequenced because existing canonical reads use a library lock;
different institutions remain independent. Cross-client lock contention remains a
server concern and existing busy/error responses remain authoritative.

## Navigation and landing

Patron routes start /libraries/:libraryId and offer Home, Browse Books, My Library,
Reservations and Fees. Staff routes start /staff/libraries/:libraryId and offer Overview,
Inventory, Circulation, Reservations, Fees and Settings; ADMIN additionally sees Members
& Staff and Audit / Activity. Existing Reservations/Fees were already present in the
baseline and were preserved, with narrow personal-role guards. No future module began.

Staff desktop navigation uses a 232px sidebar at CSS widths >=1024; smaller screens use
a native dialog drawer. Overview uses actual inventory totals, queues, current loans
and authorized membership counts. Noncanonical circulation displays Not enabled.
An empty library offers Add first book, Upload inventory and authorized staff invitation.

Successful owner registration opens Staff Overview; accepted staff invitations open
Staff Overview; general membership join opens Patron Home. Login preserves an authorized
deep link including query/hash. Wrong-mode deep links are corrected by the route guard.
One active membership lands at its actual home; multiple memberships land at My libraries;
no memberships land at global home. Legacy institution aliases resolve through the
appropriate local context or library selector. Original global platform staff tools
remain explicitly available from Account Profile under their existing global-role guard.

## Narrow backend compatibility

require_library_patron centralizes the existing ACTIVE GENERAL_USER rule. Lending,
reservation and fee personal access resolves this rule through existing access_locked
paths. Borrow/cancel-own/return-request/renew and personal requests/loans/reservations/fees
reject ADMIN/LIBRARIAN in that same library. Operational staff access still uses the
existing staff guard. A GET staff/loans route reuses the existing rows service to give
staff an operational Loans view. Stock, physical receipt, return-pending, renewal,
idempotency, journal, reservation and fee algorithms were preserved.

## Scope and evidence

Search/recommendation pages received only the patron catalogue destination adapter.
Assistant selection defaults use only patronLibraryId; model/router/knowledge algorithms
were not changed. Exact source hashes and file paths are in frontend_workspace_manifest.json.
All 999 prior report hashes and production collection counts match the captured baseline.
The isolated browser fixture was cleaned. No commit, deployment or production migration occurred.
