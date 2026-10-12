# Part 2F operational activity and audit presentation addendum

This continues the accepted Part 2F implementation. Operational and administrative event meanings remain separate; no domain phase was started.

| Surface | Existing implementation | Finding / decision |
| --- | --- | --- |
| Operational Activity | `LibraryActivity.tsx`, `ui-table` inside `ui-table-wrap` | The wrapper had overflow styling, but `ui-table` had no table/cell rules. Browser default cell spacing, raw uppercase events and full UUIDs produced adjacent text concatenation. Its pagination also bypassed the existing Staff Pager. |
| Audit / Activity | `InstitutionPanel.tsx`, `institution-table-wrap` | Accepted cell padding and dividers, but raw `User #id` identity. Converged with Operational Activity without changing its ADMIN-only authorization. |
| Inventory | `inventory-table`, shared workspace tokens | Accepted paper/header/divider/padding language. Reused these tokens in the shared Staff table variant; inventory capabilities unchanged. |
| Members & Staff | `institution-table-wrap` | Already displays name/email. Existing membership controls remain unchanged. |
| Analytics | `analytics-table` | Fixed table layout, bounded columns and readable padding; aggregate-only privacy remains unchanged. |
| Existing Staff UI | `StaffUI.Table` and `StaffUI.Pager` | Reused for both activity surfaces. Added optional table label, column widths and shared activity class, column-header scope and labeled pagination. Existing callers retain their defaults. |

`StaffActivityTable` is the one common presentation adapter. Operational columns are When, Event, Actor, Member / subject and Reference. Audit columns are When, Event and Actor. Table layout is fixed; dates, event descriptions and identities wrap within bounded columns. References use an eight-character prefix and four-character suffix, with the complete canonical value retained in the API, tooltip and screen-reader text. Canonical event codes remain tooltip metadata; display labels use sentence case only in React.

Both surfaces reuse paper/ink workspace tokens, 14px vertical and 16px horizontal cell padding, subtle row dividers, clear headings and the existing Staff Pager. At narrow widths, the named, keyboard-focusable region scrolls horizontally while the document stays within its viewport. The reference span establishes a relative containing block for its hidden accessible text: without it, an absolutely positioned screen-reader span could escape the scroll container. This was caught and repaired during the actual 1024px browser check.

Existing bounded offset/limit pagination is preserved. Neither surface had a filter toolbar; this addendum introduces no log-analysis filters, account directory API or impersonation control.

Evidence: `institution_v2f_activity_table_validation.json`, `institution_v2f_audit_identity_validation.json`, full Part 2F JUnit and full frontend regression logs. Live checks verify both pages at the six requested sizes, email identities, UUID geometry, native headers, complete accessible references, keyboard scrolling, visible focus, pagination, rendered contrast and axe WCAG 2.2 checks. Missing/deleted actors and system actors are verified with isolated backend/frontend fixtures rather than fabricated TEST history.
