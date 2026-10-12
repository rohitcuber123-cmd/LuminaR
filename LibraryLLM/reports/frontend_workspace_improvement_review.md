# Post-implementation workspace improvement review

The overhaul is complete. These recommendations do not authorize or implement future modules. No unresolved critical defect was found in the verified scope.

## 1. Global header link count

TITLE: Global header link count

WHY: Product destinations compete with task navigation.

CURRENT LIMITATION: Seven desktop links remain for existing product access.

RECOMMENDATION: Use navigation analytics to consider grouping secondary About/Know More/Graph Lab links; retain search and role-aware My Library.

PRIORITY: MEDIUM

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 2. Unified mobile app drawer

TITLE: Unified mobile app drawer

WHY: Two clear navigation scopes still cost an extra tap.

CURRENT LIMITATION: Product menu and workspace drawer are separate.

RECOMMENDATION: Consider one mobile shell that clearly groups global destinations and the current workspace, without mixing tenant contexts.

PRIORITY: MEDIUM

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 3. Single Account landing

TITLE: Single Account landing

WHY: Account information and library memberships are related.

CURRENT LIMITATION: Profile and My libraries have separate routes.

RECOMMENDATION: Consider an Account hub linking both; preserve bookmarked routes as aliases.

PRIORITY: LOW

IMPLEMENT: LATER

BREAKING: NO

## 4. Searchable library switchers

TITLE: Searchable library switchers

WHY: Native selects become difficult with many memberships.

CURRENT LIMITATION: Workspace selects are role-filtered but not searchable; My libraries is searchable.

RECOMMENDATION: Add a keyboard accessible searchable picker when membership scale justifies it, keeping separate patron/staff contexts.

PRIORITY: MEDIUM

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 5. Collapsible sidebar groups

TITLE: Collapsible sidebar groups

WHY: Future approved modules could lengthen staff navigation.

CURRENT LIMITATION: Current eight ADMIN destinations fit the sidebar.

RECOMMENDATION: Keep the current simple list; add grouped collapsible sections only after more modules are explicitly approved.

PRIORITY: LOW

IMPLEMENT: LATER

BREAKING: NO

## 6. Additional operational Overview cards

TITLE: Additional operational Overview cards

WHY: Staff may want time-sensitive exceptions.

CURRENT LIMITATION: Overview contains real inventory, queues and current loans; no invented metrics.

RECOMMENDATION: Consider authorized overdue/exception cards using existing server data after agreeing useful definitions.

PRIORITY: MEDIUM

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 7. Onboarding checklist

TITLE: Onboarding checklist

WHY: Owners benefit from knowing the next concrete task.

CURRENT LIMITATION: An empty library has Add/Upload/Invite actions, without persistent progress tracking.

RECOMMENDATION: Consider a dismissible checklist for inventory, staff and existing circulation activation, derived from real state.

PRIORITY: MEDIUM

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 8. Notifications and avatar badges

TITLE: Notifications and avatar badges

WHY: Alert visibility and account navigation need distinct purposes.

CURRENT LIMITATION: Notifications remain a visible product control; invitations are in the avatar.

RECOMMENDATION: Retain notification visibility; consider an invitation badge in the avatar using existing pending counts, without adding notification tenancy.

PRIORITY: LOW

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 9. Global My Library shortcut

TITLE: Global My Library shortcut

WHY: Patrons need quick access to personal circulation.

CURRENT LIMITATION: Shortcut is visible only with patron memberships and resolves a patron context or selector.

RECOMMENDATION: Retain the shortcut and monitor its use; never bind it to staff selection.

PRIORITY: LOW

IMPLEMENT: LATER

BREAKING: NO

## 10. Per-library branding

TITLE: Per-library branding

WHY: Institution identity may matter for large deployments.

CURRENT LIMITATION: Selected name and membership badge distinguish workspaces.

RECOMMENDATION: Assess branding requirements separately; no branding engine is needed for this overhaul.

PRIORITY: NICE_TO_HAVE

IMPLEMENT: LATER

BREAKING: NO

## 11. Dark mode compatibility

TITLE: Dark mode compatibility

WHY: Theme consistency needs dedicated contrast verification.

CURRENT LIMITATION: This phase follows the current paper theme.

RECOMMENDATION: Audit every token, dialog and chart before introducing a separately approved dark theme.

PRIORITY: NICE_TO_HAVE

IMPLEMENT: LATER

BREAKING: NO

## 12. Keyboard navigation

TITLE: Keyboard navigation

WHY: Frequent staff work benefits from predictable focus.

CURRENT LIMITATION: Core menus, drawers and dialogs support keyboard/focus behavior.

RECOMMENDATION: Consider discoverable shortcuts and repeat real-browser keyboard checks for future controls.

PRIORITY: LOW

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 13. Screen reader semantics

TITLE: Screen reader semantics

WHY: Automated checks do not establish the complete spoken experience.

CURRENT LIMITATION: Five axe surfaces and named landmarks/labels passed; no user study.

RECOMMENDATION: Perform NVDA/VoiceOver task walkthroughs for inventory actions and return handling, correcting any observed announcements.

PRIORITY: MEDIUM

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 14. Large inventory table performance

TITLE: Large inventory table performance

WHY: Very large tenant collections may expose rendering and paging costs.

CURRENT LIMITATION: Existing server paging is preserved; no large fixture rendering benchmark was added.

RECOMMENDATION: Benchmark a large isolated tenant before adding virtualization; retain accessible table semantics and server filtering.

PRIORITY: MEDIUM

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 15. Route-based code splitting

TITLE: Route-based code splitting

WHY: Initial downloads include many infrequently visited routes.

CURRENT LIMITATION: Main JavaScript remains 675.72 kB after minification.

RECOMMENDATION: Lazy-load route modules with consistent fallbacks and preserved deep links, starting with staff/account pages.

PRIORITY: HIGH

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 16. Main bundle size

TITLE: Main bundle size

WHY: Lower startup cost matters on mobile connections.

CURRENT LIMITATION: Build retains its >500 kB chunk warning; main gzip is 184.69 kB.

RECOMMENDATION: Measure imports and dependency chunks, then reduce unused initial-route code; do not silence the warning.

PRIORITY: HIGH

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 17. Loading skeleton consistency

TITLE: Loading skeleton consistency

WHY: Stable placeholders can reduce perceived layout movement.

CURRENT LIMITATION: Shared StatePanel loading text is consistent; skeletons are not universal.

RECOMMENDATION: Introduce reusable card/table skeletons with aria-busy and reduced-motion support after measuring useful placements.

PRIORITY: LOW

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 18. Route error boundaries

TITLE: Route error boundaries

WHY: Unexpected render failures should permit local recovery.

CURRENT LIMITATION: Data failures have retryable states; not every route has a dedicated render boundary.

RECOMMENDATION: Add route-level error boundaries and safe diagnostics while retaining account/tenant isolation.

PRIORITY: HIGH

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 19. Breadcrumb consistency

TITLE: Breadcrumb consistency

WHY: Users should recognize their location across page scopes.

CURRENT LIMITATION: Staff has selected-library/current-section breadcrumbs; patron uses its focused navigation.

RECOMMENDATION: Consider consistent optional breadcrumbs on deeper patron/detail screens, without restoring a second global navigation strip.

PRIORITY: LOW

IMPLEMENT: NEXT_PHASE

BREAKING: NO

## 20. Legacy global-role UI clarity

TITLE: Legacy global-role UI clarity

WHY: Original platform staff permissions differ from institution memberships.

CURRENT LIMITATION: Legacy platform tools remain under their original global-role guards and an explicit Account Profile link.

RECOMMENDATION: Continue labelling platform staff tools distinctly; audit old direct bookmarks before any future migration or retirement.

PRIORITY: MEDIUM

IMPLEMENT: NEXT_PHASE

BREAKING: NO

