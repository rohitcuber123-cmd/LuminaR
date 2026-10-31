# Part 2J source-contract review

Status: REQUIRES_APPROVAL. `tests.institution_v2j.test_diagnostics::test_existing_staff_status_unchanged` still fails, unchanged. Its page assertion compares raw SHA256 with the J baseline.

Expected: `874adf27e1efd90899d4ba8c7d7019872af7d1e69627446de825210f27d62765`. Actual accepted O page: `51f58263f2c06fda2bb3f6669de94a735af2d0b97e3cf4497bc154c1375adfd3`.

The original page was recovered from the preserved pre-O copy and matches the J hash exactly. `institution_v2o1_j_page_review.diff` contains the complete J-to-O page diff. J's completion/changed-files evidence describes an operator-only read diagnostics phase that intentionally left existing staff/runtime paths untouched. Whole-file identity proved that phase's non-interference. It also pinned security-sensitive code, but cannot express the later authorized UX evolution. No documentation found establishes permanent byte immutability as a product requirement. This purpose assessment is an inference from J's explicit scope and code; it does not grant approval to alter its frozen test.

Complete intentional differences (all six diff hunks):

| Difference | Classification and review |
|---|---|
| Import `stageProgress`; remove unsupported CANCELLED label; handle missing/invalid dates | AUTHORIZED PART 2O UX CHANGE. No new backend job state or operation. |
| Remount session on current role as well as tenant/token | AUTHORIZED PART 2O UX CHANGE + SECURITY-SENSITIVE CHANGE. Revocation clears mounted status; authority still rechecked server-side. |
| Guard every load by staff role/visibility; add 10-second deadline, abort sequencing and visibility cleanup; retain 3-second active polling | AUTHORIZED PART 2O UX CHANGE + SECURITY-SENSITIVE CHANGE. Bounds requests and prevents stale/session/library responses. |
| Use validated stage counters, indeterminate unknown totals and explicit stage/publication distinction | AUTHORIZED PART 2O UX CHANGE. No invented overall completion or worker health. |
| Condition last-good claim on artifact verification; show latest attempt timestamps and unavailable worker activity | AUTHORIZED PART 2O UX CHANGE. Retained pointer alone is not called validated. |
| Show durable heartbeat and accessible progress explanation | AUTHORIZED PART 2O UX CHANGE. Durable records are distinguished from native process liveness. |

The existing explicit Admin `build()` action, confirmation/abort handling, tenant transport and backend routes are unchanged. The three existing backend hashes remain exact J matches. No unrelated or suspicious/unexplained page hunk was found. No page or transport edit was made in O.1. The separate O progress helper is also byte-identical to the O.1 starting checkpoint.

Current enforcement remains the original whole-page assertion plus all backend/frontend/browser security checks. Additional passing tests cannot make a raw mismatching SHA equal. Restoring the J page would discard accepted O functionality and is outside this task's preservation requirement. The exact candidate patch is offered for explicit approval only.
