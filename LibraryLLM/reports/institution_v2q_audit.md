# Part2Q preimplementation audit

Current checkpoint: Part2P.1 final evidence reports2997 backend passed,0 failed,20 skipped;1012 frontend passed,0 failed,0 skipped. These are prior executed results, not the fresh2Q baseline. Fresh2Q baseline runs are separate and must finish before existing application owners are edited.

| Capability | Classification | Actual owner / finding |
|---|---|---|
| Global Events lifecycle | IMPLEMENTED_VERIFIED | event_service.py; original Events tests preserved in2P.1 full run |
| Institution Events and visibility | IMPLEMENTED_VERIFIED | library_event_service.py and library_events.py; canonical library UUID and current membership gate |
| Event staff authority | IMPLEMENTED_VERIFIED | require_library_staff permits ADMIN and LIBRARIAN; preserve this existing matrix |
| Announcements | IMPLEMENTED_VERIFIED | library_announcement_service.py; separate ADMIN-only publication authority |
| Specific-member announcements | IMPLEMENTED_VERIFIED | Part2P.1 source and executed80 backend/24 frontend tests; bounded picker and recipient-filtered reads |
| Shared inbox, bell and read state | IMPLEMENTED_VERIFIED | notification_service.py, tenant_notification_service.py, NotificationCenter.tsx |
| Event registration / RSVP | MISSING | No registration fields/routes/UI in current Event schemas, tenant route owner, EventsPage or EventDetailPage |
| Capacity / registration closure | MISSING | No server seat ledger or registration controls in existing Event schemas |
| Attendance | MISSING | No event participant attendance records or controls |
| Member event participation dashboard | MISSING | Existing upcoming/past/cancelled discovery only; extend this page |
| Event registration analytics | MISSING | Existing event discovery is not an attendance/registration ledger |
| QR/waitlist/certificates/reminders/calendar | PLANNED | Future feasibility only; no automatic implementation |

## Required implementation boundary

Extend the current tenant Event owners; preserve global Event contracts and discovery behavior. Keep current institution Event ADMIN/LIBRARIAN authority rather than copying announcements' stricter ADMIN-only rule. Current active verified membership and invitation proof remain mandatory for participation. A public visible event is not authority to register without eligible membership.

Capacity must be authoritative and crash-safe. Prefer one atomic event-scoped registration/configuration ledger update under the existing durable library mutation gate, shared with membership revocation and Event changes. Unique stable account identity and CONFIRMED/CANCELLED lifecycle; cancellation and attendance must retain server actor/time. Capacity reductions below confirmed count should reject without deleting valid seats. Registration defaults closed for legacy events; explicit unlimited capacity requires staff opt-in. Reject cancelled/archived/expired/deadline-closed events. Existing published events cannot be deleted through draft deletion.

Registration success and durable notification intent must commit together; inbox insertion must be retryable through the existing bounded tenant notification worker and stable event/member/version dedupe. Do not add another inbox/worker or external email. Significant date/time/location/cancellation changes need version-aware bounded delivery; nonessential edits should not broadcast. Notification navigation must revalidate current private-library membership and source identity.

Integrate member registration/cancellation/status/capacity and own history into existing Event pages. Add current-authority staff roster/search/attendance controls to existing Event management/detail. Abort stale requests and clear state on library/session/role changes. Preserve all original tests; add capacity concurrency, revoke/cancel races, restart/error/idempotency, private isolation, browser and accessibility checks. No production authentication/telemetry changes, automatic rebuilding, commit or deployment.

## Current execution state

Only audit and baseline tooling are created so far. No RSVP application code has been applied. Fresh backend/frontend/build/lint checks run in owned disposable fallback databases and separate2Q report namespaces; existing2P/2P.1 evidence is preserved. Do not claim2Q PASS from historical2P.1 counts.
