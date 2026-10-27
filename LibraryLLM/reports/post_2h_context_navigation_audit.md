# Post-Part-2H context and storage audit

18 central components/call sites inspected. There is one persisted workspace-context record (`luminar_workspace_contexts`) with an account owner, not a globally authoritative selected library. It and the obsolete `luminar_active_library` convenience key are removed on reset. The authenticated token/user pair is separately stored and watched. No additional tenant-return sessionStorage key was found.

| File | Concern | Classification | Expected behavior / repair |
|---|---|---|---|
| frontend/src/store/useInstitutionStore.ts | owner-scoped storage and current-session sequences | EXISTING_REUSED | Saved UUIDs revalidated against fresh active memberships; no selection guessed. |
| frontend/src/store/useAuthStore.ts | login/logout/token replacement | REPAIRED | Clear both tenant and Platform stores before publishing a new identity. |
| frontend/src/lib/sessionStorageSync.ts | cross-tab token/user pair | EXISTING_REUSED | Settled token-pair reconciliation; unrelated preferences preserved. |
| frontend/src/components/ProductSessionBoundary.tsx | all route layouts and return queries | CENTRAL_REPAIR | Remove invalid old return hints; replace old tenant route on identity change. |
| frontend/src/lib/productContext.ts | home/catalog/search/events/personal destination helpers | CENTRAL_REPAIR | Explicit URL first. Current-account return hints revalidate both membership and workspace role. |
| frontend/src/hooks/useProductContext.ts | shared page/header context | CENTRAL_REPAIR | Current-session authoritative memberships and Platform assignments, rather than remembered selections. |
| frontend/src/lib/authDestination.ts | login history/from destination | REPAIRED | Tenant returns go to AccountLanding with a safe explicit return_to. |
| frontend/src/components/WorkspaceRoute.tsx | AccountLanding and tenant guard | REPAIRED | Fresh membership resolves a tenant return; Platform-only accounts cannot inherit old Staff/Patron routes. |
| frontend/src/lib/institutions.ts | queued/in-flight tenant requests | REPAIRED | Session+UUID queues and stale success/error rejection after response. |
| frontend/src/store/usePlatformStore.ts | fresh explicit Platform permissions | EXISTING_REUSED | Session/version guards; no legacy User.role authority. |
| frontend/src/App.tsx | layouts and route lifecycle | REPAIRED | One boundary across auth/main/personal layouts; tenant route contents stay keyed by session. |
| frontend/src/components/Header.tsx | logo, Catalog, search and personal links | REPAIRED | Platform Catalog is /catalog with explicit Platform return; logo returns /platform. |
| frontend/src/components/AccountMenu.tsx | profile/libraries/sign-out links | EXISTING_REUSED | Shared context helpers and explicit separate Platform section. No tenant entry granted by Platform role. |
| frontend/src/components/GlobalCatalogue.tsx | global dataset and catalogue filters | GLOBAL_INTENTIONAL | Global content and ranking unchanged; query parameters retain explicit return context. |
| frontend/src/pages/CatalogPage.tsx | shared Catalog entry | EXISTING_REUSED | Authorized Staff context selects Staff catalogue; unowned old hints cannot redirect the page. |
| frontend/src/pages/ReadingListPage.tsx | personal reading data and return navigation | PERSONAL_WITH_RETURN_CONTEXT | Globally owned user data retains only authorized explicit return context. |
| frontend/src/components/BookCard.tsx | book/detail/personal actions | EXISTING_REUSED | Existing canonical presentation helpers; no palette/rendering/card rewrite. |
| frontend/src/components/LibrarySwitcher.tsx | Staff/Patron workspace choice | PRESENTATION_REPAIR | Shared searchable control; only that mode’s memberships and explicit navigation to the chosen UUID. |

The prior owner-scoped selection store already rejected late session/version results. The remaining gaps were the login `from` history URL, unchecked personal return hints, Platform Catalog routing, and post-response/error tenant API checks. These are repaired centrally without adding separate role conditions to each product page.

Explicit /catalog remains global. /catalog?workspace=platform carries an approved Platform return. Explicit Staff and Patron URLs remain route-authoritative and server-guarded. There is no first-of-many membership selection or new authority assignment through navigation.

Real account-switch tests and a delayed HTTP response test are in post_2h_browser.json and post_2h_account_race_browser.json. The late failure path and fresh role-demotion revalidation are also automated tests.
