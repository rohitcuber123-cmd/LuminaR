# Account / My Libraries audit — PASS

Provided account normal login identifies user 10, display name Rohit, global GENERAL_USER, verified email, active account. TEST is ACTIVE / PUBLIC_LIBRARY / PUBLIC; membership 22c6b77b-3f3f-47d9-a6aa-cd4e41dbeb35 is ACTIVE / GENERAL_USER / non-owner. No PlatformRoleAssignment is granted. No membership was created, changed or reassigned.

Before changing anything, /me/libraries on both Core instances already returned TEST and the account page/menu generated /libraries/e6d1e5b4-c48f-4b47-b96a-656a676fb8ae. A missing-membership discrepancy could not be reproduced. The reproduced access failure was Home loading on stale Core 8002, not authority or UUID generation. After the restart, both direct URL and normal UI render the same local Home. No email-specific workaround was introduced.

The generic refresh improvement refetches memberships when entering My Libraries or opening the account menu. Existing loaded rows remain available during a refresh; failed refreshes remain explicit errors and clear stale authority. Another session's cached rows are hidden. Existing post-mutation, login/session and focus refetches stay intact. Active groups remain Member libraries and Staff libraries, with Platform navigation separate.

| Audit item | Finding |
|---|---|
| ACTIVE membership filtering | API returned ACTIVE GENERAL_USER for user 10; direct context identical. |
| Public/private access mode | PUBLIC TEST visible; generic disposable tests cover both access modes. |
| Stale cache | Account entry/menu lacked their own refetch; both now refetch. Existing focus/session and mutation refresh preserved. |
| Legacy User.role authority | Grouping and links use LibraryMembership; generic global ADMIN with member role stays Patron. |
| Old activeLibrary projection | Account maps the full libraries array; header now resolves explicit URL instead of activeId. |
| First membership collapse | Account renders all; 103-row pagination test verifies complete traversal. Menu bounds groups with View all. |
| Status casing/lifecycle | Canonical ACTIVE only. Suspended library absent from API and direct context equally denied; no guessed status conversion. |
| Grouping owner/member | Owner ADMIN and LIBRARIAN are Staff; GENERAL_USER is member; Platform uses separate assignments. |
| Aliases/obsolete routes | Destination uses canonical library_id UUID; slug ggs is display metadata only. |
| Account ID type | actor_id resolves numeric 10; returned membership user_id=10. No string/int discrepancy. |
| Join/session refresh | Existing join/accept handlers await refresh and select context; actual UI mutation tests verify refetch. |
| Role/status changes and restore | InstitutionPanel.run awaits refresh. Account entry/menu/focus discover server changes and restored memberships. |
| Query/route loss | Canonical link enters the exact UUID; existing login deep-link tests preserve query/fragment. |
| Remembered selection hiding memberships | Remembered IDs never filter account rows; generic multi-role tests verify this. Wrong-session rows are hidden. |

Evidence: account_membership_navigation.json, navigation_context_browser.json, required regression tests and navigation_context_live_before/after.json. Development credentials were used only at runtime.
