# Full frontend route inventory

| Route | Component / purpose | Context | Data | Authority | Classification | Overlap | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| /library-inventory | {<ProtectedRoute><LegacyWorkspaceRedirect section="inventory" /></ProtectedRoute>} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:67 |
| /legacy-library-history | {<Navigate to="/account/history" replace />} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:68 |
| /library-loans | {<ProtectedRoute><LegacyWorkspaceRedirect mode="PATRON" section="my-library" /></ProtectedRoute>} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:69 |
| /library-circulation | {<ProtectedRoute><LegacyWorkspaceRedirect mode="STAFF" section="circulation" /></ProtectedRoute>} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:70 |
| /library-reservations | {<ProtectedRoute><LegacyWorkspaceRedirect mode="PATRON" section="reservations" /></ProtectedRoute>} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:71 |
| /library-fees | {<ProtectedRoute><LegacyWorkspaceRedirect mode="PATRON" section="fees" /></ProtectedRoute>} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:72 |
| /library-circulation/reservations | {<ProtectedRoute><LegacyWorkspaceRedirect mode="STAFF" section="reservations" /></ProtectedRoute>} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:73 |
| /library-circulation/fees | {<ProtectedRoute><LegacyWorkspaceRedirect mode="STAFF" section="fees" /></ProtectedRoute>} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:74 |
| /account/profile | {<ProtectedRoute><AccountProfilePage /></ProtectedRoute>} | ACCOUNT | personal / institution APIs | authenticated session | CANONICAL | see feature parity matrix | frontend/src/App.tsx:75 |
| /account/libraries | {<ProtectedRoute><MyLibrariesPage /></ProtectedRoute>} | ACCOUNT | personal / institution APIs | authenticated session | CANONICAL | see feature parity matrix | frontend/src/App.tsx:76 |
| /account/continue | {<ProtectedRoute><AccountLanding /></ProtectedRoute>} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:77 |
| /account/history | {<ProtectedRoute><LegacyProfilePage /></ProtectedRoute>} | ACCOUNT | personal / institution APIs | authenticated session | CANONICAL | see feature parity matrix | frontend/src/App.tsx:78 |
| /libraries | {<ProtectedRoute><ExploreLibrariesPage /></ProtectedRoute>} | ACCOUNT | personal / institution APIs | authenticated session | CANONICAL | see feature parity matrix | frontend/src/App.tsx:79 |
| /libraries/register | {<ProtectedRoute><RegisterLibraryPage /></ProtectedRoute>} | ACCOUNT | personal / institution APIs | authenticated session | CANONICAL | see feature parity matrix | frontend/src/App.tsx:80 |
| /libraries/:libraryId | {<ProtectedRoute><WorkspaceRoute><PatronLibraryShell /></WorkspaceRoute></ProtectedRoute>} | PATRON | library catalogue/lending/reservations/fees | LibraryMembership GENERAL_USER | CANONICAL | Home / catalogue / detail counterparts | frontend/src/App.tsx:81 |
| /libraries/:libraryId/ (index) | {<Home context="library" />} | PATRON | library catalogue/lending/reservations/fees | LibraryMembership GENERAL_USER | CANONICAL | Home / catalogue / detail counterparts | frontend/src/App.tsx:82 |
| /libraries/:libraryId/catalogue | {<LibraryCataloguePage />} | PATRON | library catalogue/lending/reservations/fees | LibraryMembership GENERAL_USER | CANONICAL | Home / catalogue / detail counterparts | frontend/src/App.tsx:83 |
| /libraries/:libraryId/search | {<LibraryCataloguePage />} | PATRON | library catalogue/lending/reservations/fees | LibraryMembership GENERAL_USER | CANONICAL | Home / catalogue / detail counterparts | frontend/src/App.tsx:84 |
| /libraries/:libraryId/new-arrivals | {<LibraryCataloguePage arrivals />} | PATRON | library catalogue/lending/reservations/fees | LibraryMembership GENERAL_USER | CANONICAL | Home / catalogue / detail counterparts | frontend/src/App.tsx:85 |
| /libraries/:libraryId/popular | {<LibraryCataloguePage popular />} | PATRON | library catalogue/lending/reservations/fees | LibraryMembership GENERAL_USER | CANONICAL | Home / catalogue / detail counterparts | frontend/src/App.tsx:86 |
| /libraries/:libraryId/genres | {<LibraryCatalogueGenres />} | PATRON | library catalogue/lending/reservations/fees | LibraryMembership GENERAL_USER | CANONICAL | Home / catalogue / detail counterparts | frontend/src/App.tsx:87 |
| /libraries/:libraryId/books/:bookId | {<LibraryCatalogueDetail />} | PATRON | library catalogue/lending/reservations/fees | LibraryMembership GENERAL_USER | CANONICAL | Home / catalogue / detail counterparts | frontend/src/App.tsx:88 |
| /libraries/:libraryId/global-books/:bookId | {<LibraryCatalogueDetail global />} | PATRON | library catalogue/lending/reservations/fees | LibraryMembership GENERAL_USER | CANONICAL | Home / catalogue / detail counterparts | frontend/src/App.tsx:89 |
| /libraries/:libraryId/my-library | {<LibraryCirculationPage />} | PATRON | library catalogue/lending/reservations/fees | LibraryMembership GENERAL_USER | CANONICAL | Home / catalogue / detail counterparts | frontend/src/App.tsx:90 |
| /libraries/:libraryId/loans | {<LibraryCirculationPage />} | PATRON | library catalogue/lending/reservations/fees | LibraryMembership GENERAL_USER | CANONICAL | Home / catalogue / detail counterparts | frontend/src/App.tsx:91 |
| /libraries/:libraryId/reservations | {<LibraryReservationsFeesPage />} | PATRON | library catalogue/lending/reservations/fees | LibraryMembership GENERAL_USER | CANONICAL | Home / catalogue / detail counterparts | frontend/src/App.tsx:92 |
| /libraries/:libraryId/fees | {<LibraryReservationsFeesPage fees />} | PATRON | library catalogue/lending/reservations/fees | LibraryMembership GENERAL_USER | CANONICAL | Home / catalogue / detail counterparts | frontend/src/App.tsx:93 |
| /staff/libraries/:libraryId | {<ProtectedRoute><WorkspaceRoute staff><StaffLibraryShell /></WorkspaceRoute></ProtectedRoute>} | STAFF | tenant APIs | LibraryMembership ADMIN/LIBRARIAN | CANONICAL | see feature parity matrix | frontend/src/App.tsx:95 |
| /staff/libraries/:libraryId/ (index) | {<StaffOverviewPage />} | STAFF | tenant APIs | LibraryMembership ADMIN/LIBRARIAN | CANONICAL | see feature parity matrix | frontend/src/App.tsx:96 |
| /staff/libraries/:libraryId/inventory | {<LibraryInventoryPage />} | STAFF | tenant APIs | LibraryMembership ADMIN/LIBRARIAN | CANONICAL | see feature parity matrix | frontend/src/App.tsx:97 |
| /staff/libraries/:libraryId/circulation | {<LibraryCirculationPage staff />} | STAFF | tenant APIs | LibraryMembership ADMIN/LIBRARIAN | CANONICAL | see feature parity matrix | frontend/src/App.tsx:98 |
| /staff/libraries/:libraryId/reservations | {<LibraryReservationsFeesPage staff />} | STAFF | tenant APIs | LibraryMembership ADMIN/LIBRARIAN | CANONICAL | see feature parity matrix | frontend/src/App.tsx:99 |
| /staff/libraries/:libraryId/fees | {<LibraryReservationsFeesPage staff fees />} | STAFF | tenant APIs | LibraryMembership ADMIN/LIBRARIAN | CANONICAL | see feature parity matrix | frontend/src/App.tsx:100 |
| /staff/libraries/:libraryId/members | {<AdminLibraryRoute><InstitutionPanel section="members" /></AdminLibraryRoute>} | STAFF | tenant APIs | LibraryMembership ADMIN/LIBRARIAN | CANONICAL | see feature parity matrix | frontend/src/App.tsx:101 |
| /staff/libraries/:libraryId/activity | {<LibraryActivityPage />} | STAFF | tenant APIs | LibraryMembership ADMIN/LIBRARIAN | CANONICAL | see feature parity matrix | frontend/src/App.tsx:102 |
| /staff/libraries/:libraryId/settings | {<InstitutionPanel section="settings" />} | STAFF | tenant APIs | LibraryMembership ADMIN/LIBRARIAN | CANONICAL | see feature parity matrix | frontend/src/App.tsx:103 |
| /staff/libraries/:libraryId/audit | {<AdminLibraryRoute><InstitutionPanel section="audit" /></AdminLibraryRoute>} | STAFF | tenant APIs | LibraryMembership ADMIN/LIBRARIAN | CANONICAL | see feature parity matrix | frontend/src/App.tsx:104 |
| /staff/legacy-admin | {<ProtectedRoute><ManagementRedirect admin /></ProtectedRoute>} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:106 |
| /staff/legacy-librarian | {<ProtectedRoute><ManagementRedirect /></ProtectedRoute>} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:107 |
| /invitations | {<ProtectedRoute><PendingInvitationsPage /></ProtectedRoute>} | ACCOUNT | personal / institution APIs | authenticated session | CANONICAL | see feature parity matrix | frontend/src/App.tsx:108 |
| /invitations/:invitationId | {<InvitationPage />} | ACCOUNT | personal / institution APIs | authenticated session | CANONICAL | see feature parity matrix | frontend/src/App.tsx:109 |
| /events | {<ProtectedRoute><EventsPage /></ProtectedRoute>} | GLOBAL | global catalogue / search / RAG / events / KG | public reads or authenticated feature guard | CANONICAL | see feature parity matrix | frontend/src/App.tsx:110 |
| /events/:eventId | {<ProtectedRoute><EventDetailPage /></ProtectedRoute>} | GLOBAL | global catalogue / search / RAG / events / KG | public reads or authenticated feature guard | CANONICAL | see feature parity matrix | frontend/src/App.tsx:111 |
| /platform | {<ProtectedRoute><PlatformRoute><PlatformShell /></PlatformRoute></ProtectedRoute>} | PLATFORM | platform APIs | PlatformRoleAssignment | CANONICAL | see feature parity matrix | frontend/src/App.tsx:112 |
| /platform/ (index) | {<PlatformOverview />} | PLATFORM | platform APIs | PlatformRoleAssignment | CANONICAL | see feature parity matrix | frontend/src/App.tsx:113 |
| /platform/libraries | PlatformLibrariesPage | PLATFORM | safe platform directory/lifecycle/audit API | PlatformRoleAssignment | CANONICAL | single existing PlatformShell | frontend/src/App.tsx |
| /platform/libraries/:libraryId | PlatformLibraryDetailPage | PLATFORM | safe platform directory/lifecycle/audit API | PlatformRoleAssignment | CANONICAL | single existing PlatformShell | frontend/src/App.tsx |
| /platform/catalogue | {<PlatformCatalogue />} | PLATFORM | platform APIs | PlatformRoleAssignment | CANONICAL | see feature parity matrix | frontend/src/App.tsx:114 |
| /platform/accounts | {<PlatformAccountsPage />} | PLATFORM | platform APIs | PlatformRoleAssignment | CANONICAL | see feature parity matrix | frontend/src/App.tsx:115 |
| /platform/notifications | {<PlatformNotificationsPage />} | PLATFORM | platform APIs | PlatformRoleAssignment | CANONICAL | see feature parity matrix | frontend/src/App.tsx:116 |
| /platform/history | {<PlatformHistoryPage />} | PLATFORM | platform APIs | PlatformRoleAssignment | CANONICAL | see feature parity matrix | frontend/src/App.tsx:117 |
| /platform/migration-review | {<PlatformAuthorityReview />} | PLATFORM | platform APIs | PlatformRoleAssignment | CANONICAL | see feature parity matrix | frontend/src/App.tsx:118 |
| /platform/events | {<ManageEventsPage />} | PLATFORM | platform APIs | PlatformRoleAssignment | CANONICAL | see feature parity matrix | frontend/src/App.tsx:119 |
| /platform/events/new | {<EventEditorPage />} | PLATFORM | platform APIs | PlatformRoleAssignment | CANONICAL | see feature parity matrix | frontend/src/App.tsx:120 |
| /platform/events/:eventId/edit | {<EventEditorPage />} | PLATFORM | platform APIs | PlatformRoleAssignment | CANONICAL | see feature parity matrix | frontend/src/App.tsx:121 |
| /staff | {<ProtectedRoute><ManagementRedirect /></ProtectedRoute>} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:123 |
| /staff/events | {<Navigate to="/platform/events" replace />} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:124 |
| /staff/events/new | {<Navigate to="/platform/events/new" replace />} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:125 |
| /staff/events/:eventId/edit | {<LegacyEventRedirect />} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:126 |
| / | {<Home />} | GLOBAL | global catalogue / search / RAG / events / KG | public reads or authenticated feature guard | CANONICAL | see feature parity matrix | frontend/src/App.tsx:128 |
| /catalog | {<CatalogPage />} | GLOBAL | global catalogue / search / RAG / events / KG | public reads or authenticated feature guard | CANONICAL | see feature parity matrix | frontend/src/App.tsx:133 |
| /search | {<SearchPage />} | GLOBAL | global catalogue / search / RAG / events / KG | public reads or authenticated feature guard | CANONICAL | see feature parity matrix | frontend/src/App.tsx:138 |
| /experimental/kg | {<ProtectedRoute><KnowledgeGraphPage /></ProtectedRoute>} | GLOBAL | global catalogue / search / RAG / events / KG | public reads or authenticated feature guard | CANONICAL | see feature parity matrix | frontend/src/App.tsx:142 |
| /book/:workId | {<BookDetailPage />} | GLOBAL | global catalogue / search / RAG / events / KG | public reads or authenticated feature guard | CANONICAL | see feature parity matrix | frontend/src/App.tsx:144 |
| /book/:workId/read | {<ProtectedRoute><BookReaderPage /></ProtectedRoute>} | ACCOUNT | protected digital reader API | authenticated session + existing digital entitlement | CANONICAL | see feature parity matrix | frontend/src/App.tsx:148 |
| /reading-list | {<ProtectedRoute><ReadingListPage /></ProtectedRoute>} | ACCOUNT | personal / institution APIs | authenticated session | CANONICAL | see feature parity matrix | frontend/src/App.tsx:150 |
| /profile | {
               <ProtectedRoute><LegacyWorkspaceRedirect mode="PATRON" section="my-library" /></ProtectedRoute>
             } | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:155 |
| /dashboard | {<ProtectedRoute><AccountLanding /></ProtectedRoute>} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:163 |
| /my-library | {<Navigate to="/profile" replace />} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:164 |
| /library | {<Navigate to="/profile" replace />} | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:165 |
| /admin | {
               <ProtectedRoute><ManagementRedirect admin /></ProtectedRoute>
             } | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:169 |
| /librarian | {
               <ProtectedRoute><ManagementRedirect /></ProtectedRoute>
             } | ACCOUNT | redirect / membership list | authenticated session + destination guard | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:176 |
| * | {<section className="global-page"><StatePanel title="Page not found">Use the navigation to return to your catalogue or library.</StatePanel></section>} | GLOBAL | global catalogue / search / RAG / events / KG | public reads or authenticated feature guard | CANONICAL | see feature parity matrix | frontend/src/App.tsx:183 |
| /staff/login | {<StaffLoginPage />} | ACCOUNT | auth / setup APIs | public login or authenticated setup token | CANONICAL | see feature parity matrix | frontend/src/App.tsx:280 |
| /account/setup | {<AccountSetupPage />} | ACCOUNT | auth / setup APIs | public login or authenticated setup token | CANONICAL | see feature parity matrix | frontend/src/App.tsx:281 |
| /staff/setup | {<Navigate to="/account/setup" replace />} | ACCOUNT | auth / setup APIs | public login or authenticated setup token | COMPATIBILITY | see feature parity matrix | frontend/src/App.tsx:282 |
| /login | {<LoginPage />} | ACCOUNT | auth / setup APIs | public login or authenticated setup token | CANONICAL | see feature parity matrix | frontend/src/App.tsx:283 |
| /signup | {<SignUpPage />} | ACCOUNT | auth / setup APIs | public login or authenticated setup token | CANONICAL | see feature parity matrix | frontend/src/App.tsx:288 |
| /verify-otp | {<VerifyOTPPage />} | ACCOUNT | auth / setup APIs | public login or authenticated setup token | CANONICAL | see feature parity matrix | frontend/src/App.tsx:293 |
| /llm | {<LLMLayout />} | GLOBAL | global catalogue / search / RAG / events / KG | public reads or authenticated feature guard | CANONICAL | see feature parity matrix | frontend/src/App.tsx:299 |
| /* | {<DashboardLayout />} | GLOBAL | global catalogue / search / RAG / events / KG | public reads or authenticated feature guard | CANONICAL | see feature parity matrix | frontend/src/App.tsx:305 |
