## A. Final result

PASS — existing global behavior preserved; institution-specific selection added to the existing announcement system.

## B. Previous user selector audit

PlatformOperations UserPicker/NotificationComposer remains unchanged. The global PLATFORM_ADMIN sender supports many selected accounts in batches of50, API1–50 per request, ID/email resolution, stable-ID dedupe and resumable batch retries. Read institution_v2p1_selector_audit.md for source ownership and history.

## C. Root cause of missing option

The institution announcement interface in2P deliberately provided ALL_ACTIVE_MEMBERS only. The older selector still works on the separate privileged Platform surface; no backend contract was replaced.

## D. All-members mode

Legacy/default audience continues the existing current-eligible-members snapshot, bounded worker, retry and inbox behavior. Older rows without audience remain compatible only when they have no selected recipient.

## E. Specific-member mode

Exactly one canonical account ID is mandatory. Missing/invalid selection fails validation; an old client cannot accidentally convert a targeted draft to all-members. Published scope remains immutable. Existing global multi-recipient functionality is preserved unchanged.

## F. Email search and resolution

ADMIN-only membership-first Mongo lookup; escaped literal name/email matching,2–120 characters,10 UI results,20 API maximum, limit+1 and3-second server execution ceiling. No global total or all-email download. Duplicate/changed emails do not change the selected canonical user_id. Selection creates an in-app notice; no SMTP delivery is claimed or added.

## G. Backend authorization

Canonical UUID/current account/current institution ADMIN permission; same-library active membership, verified eligible account and accepted invitation proof checked at save/publication/delivery. Platform-only authority, other-library staff, private outsiders, forged email/IDs and unavailable recipients fail closed.

## H. Targeted delivery

Existing insert_notice, dedupe key institution/announcement/account/type, publication snapshot/cursor, shared account inbox and tenant worker reused. Specific publication snapshots one recipient. Delivery also checks scope to reject a corrupt overbroad snapshot. Concurrent and repeated requests create one copy.

## I. Announcement visibility

Ordinary member list/count/pagination and detail enforce all-member or own specific-member scope. Forwarded private URLs return404. ADMIN-only management/history can inspect all library announcements; a library admin using the member API still receives ordinary recipient filtering. Safe notification navigation applies the same audience predicate. Withdrawal retains only a generic unavailable receipt.

## J. Read/unread

Existing shared bell and read APIs retained. Real browser verifies recipient0→1→0, refresh persistence, nonrecipient0 unchanged and Library B previous unread count unchanged.

## K. Staff frontend

Recipient scope on the existing editor; debounced bounded picker with loading/no-results/error/selected confirmation/clear, ARIA combobox/listbox and keyboard controls. Explicit recipient shown in preview and confirmation. Library/session/role/membership change unmounts picker, aborts pending searches and clears selection. Unavailable published recipient keeps immutable history without draft-edit advice.

## L. Member frontend

Only all-member and own targeted announcements appear. Own targeted messages are labeled Private message for you; no management or directory controls.

## M. Event notification preservation

Existing Events, event-linked navigation, shared inbox, lending reminders and all2P lifecycle/read behavior preserved. Original sources and tests remain unchanged.

## N. Security tests

80 new real-Mongo recipient tests,75 installed-guard mutations, original84 announcement tests,51 global notification operation tests and full tenant/private/RAG/native/security suites passed. Isolated authenticated-mode fixture:16 checks, including targeted query/delivery and denied telemetry writes/database drop.

## O. Frontend tests

1012 passed / 0 failed / 0 skipped. Existing988 baseline preserved; new recipient workflows included in npm test. Initial and final raw logs retained.

## P. Real browser QA

Actual Chromium 151.0.7922.34;28 checks. Two disposable private libraries, separate accounts, actual JWT/ASGI/Mongo bridge, scoped member email selection, one copy, forwarded URL404, read refresh, all-member preservation, actual staff switcher, keyboard and mobile widths. Focused picker axe scan:zero violations. Unrelated Search/RAG/recommendation network surfaces stubbed as explicitly recorded. Owned DB/files removed.

## Q. Full regression

Backend2997 passed / 0 failed / 20 skipped; frontend1012 passed / 0 failed / 0 skipped. Production build and lintPASS/PASS. Existing lint warnings16; new warnings0. No suppressed tests/new hash exceptions. Original backend inventory plus recipient suite executed, Events current-date driver preserves existing assertions.

## R. Preservation

See institution_v2p1_preservation.json: full protected source pins, prior report checks, native/global/private artifact metadata, live Mongo digests and index definitions. No production auth/telemetry activation, automatic/global rebuild, commit or deployment. Live environment ownership remains UNKNOWN.

## S. Exact files changed

Source/test/script paths and SHA256 values are in institution_v2p1_changed_files.json. Existing uncommitted2P work was not reset. All generated2P.1 evidence paths and hashes are included in its evidence_files array.

## T. Remaining limitations

Tenant specific mode selects exactly one current eligible member; global Platform multi-recipient batching remains unchanged. This is in-app delivery only. Bounded substring member lookup uses existing membership/account indexes and a server execution ceiling; it is not an unbounded global directory. ADMIN management/history access is intentionally broader than member reads. Browser API uses a real ASGI bridge rather than a deployed remote server; no production accounts are used.

## U. Next recommendation

Review the local diff and evidence. Stop after2P.1; no next phase, deployment or commit started.

## Final QA

```json
{
  "PART_2P1_RESULT": "PASS",
  "ALL_MEMBERS_DELIVERY": "PASS",
  "SPECIFIC_MEMBER_DELIVERY": "PASS",
  "EMAIL_MEMBER_PICKER": "PASS",
  "TARGETED_VISIBILITY": "PASS",
  "RECIPIENT_ISOLATION": "PASS",
  "CROSS_TENANT_ACCESS": "DENIED",
  "DUPLICATE_DELIVERY": "PREVENTED",
  "READ_UNREAD": "PASS",
  "EXISTING_EVENTS": "PRESERVED",
  "NOTIFICATION_BELL": "PASS",
  "BACKEND_TESTS": {
    "passed": 2997,
    "failed": 0,
    "skipped": 20
  },
  "FRONTEND_TESTS": {
    "passed": 1012,
    "failed": 0,
    "skipped": 0
  },
  "BROWSER_QA": "PASS",
  "PRODUCTION_BUILD": "PASS",
  "NEW_REGRESSIONS": 0,
  "GLOBAL_HNSW_REBUILT": "NO",
  "GLOBAL_KG_REBUILT": "NO",
  "PRODUCTION_AUTH_CHANGED": "NO",
  "PRODUCTION_TELEMETRY_ENABLED": "NO"
}
```
