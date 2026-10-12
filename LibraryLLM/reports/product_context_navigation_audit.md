# Product context navigation audit

193 actual JSX destinations, navigation calls and navigation descriptor properties inspected with the TypeScript parser. 25 call sites changed to preserve an explicit workspace return context. Classification concerns intent, not an authority grant.

URL context wins. Explicit global URLs without return parameters remain global. Staff and Patron personal pages carry distinct UUID return parameters; Platform uses workspace=platform. Authentication and session changes clear return parameters. Memberships validate access and may correct a staff account away from patron presentation; no first-membership selection supplies Home context. Single-option compatibility redirects remain bounded to exactly one membership; multiple memberships open the chooser.

|FILE|COMPONENT / LINE|CURRENT DESTINATION|CLASSIFICATION|EXPECTED DESTINATION|FIXED|
|---|---|---|---|---|---|
|frontend/src/App.tsx|LegacyEventRedirect:54|to={'/platform/events/' + encodeURIComponent(eventId) + '/edit'}|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/App.tsx|DashboardLayout:63|navigate(clean,{replace:true})|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/App.tsx|DashboardLayout:78|to="/account/history"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/App.tsx|DashboardLayout:136|to="/platform/events"|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/App.tsx|DashboardLayout:137|to="/platform/events/new"|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/App.tsx|DashboardLayout:176|to="/profile"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/App.tsx|DashboardLayout:177|to="/profile"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/App.tsx|App:295|to="/account/setup"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/AIChatWidget.tsx|AIChatWidget:86|navigate(product.personalPath(productBookPath(id,product.libraryId)))|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/AIChatWidget.tsx|AIChatWidget:169|to="/login"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/components/AccountMenu.tsx|AccountMenu:20|to={context.personalPath(to)}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/AccountMenu.tsx|AccountMenu:23|link('/account/profile', 'Profile', true)|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/AccountMenu.tsx|AccountMenu:23|link('/reading-list', 'Saved / Reading list')|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/AccountMenu.tsx|AccountMenu:23|link('/account/libraries', 'My libraries')|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/AccountMenu.tsx|AccountMenu:24|link('/platform', 'Platform Administration')|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/components/AccountMenu.tsx|AccountMenu:24|to={libraryWorkspaceHome(l)}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/AccountMenu.tsx|AccountMenu:24|link('/account/libraries?group=patron', 'View all patron libraries')|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/AccountMenu.tsx|AccountMenu:25|to={libraryWorkspaceHome(l)}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/AccountMenu.tsx|AccountMenu:25|link('/account/libraries?group=staff', 'View all staff workspaces')|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/AccountMenu.tsx|AccountMenu:26|link('/invitations', 'Pending Invitations')|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/AccountMenu.tsx|AccountMenu:26|link('/libraries', 'Explore Libraries')|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/AccountMenu.tsx|AccountMenu:26|link('/libraries/register', 'Register a Library')|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/components/AccountMenu.tsx|AccountMenu:26|link('/account/libraries', 'View all libraries')|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/AccountMenu.tsx|AccountMenu:27|navigate('/login')|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/components/AlsoLikeTicker.tsx|AlsoLikeTicker:44|to={productNavigation.personalPath(homeBookPath(context, spotlightBook.work_id))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/AlsoLikeTicker.tsx|AlsoLikeTicker:60|to={productNavigation.personalPath(homeBookPath(context, spotlightBook.work_id))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/AlsoLikeTicker.tsx|AlsoLikeTicker:65|to={productNavigation.personalPath(homeBookPath(context, spotlightBook.work_id))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/BookCapabilities.tsx|BookCapabilities:13|to={'/login?next='+encodeURIComponent(location.pathname+location.search)}|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/components/BookCapabilities.tsx|BookCapabilities:16|to={context.personalPath('/book/'+encodeURIComponent(book.work_id)+'/read')}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/BookCapabilities.tsx|BookCapabilities:17|to={context.personalPath('/llm?book='+encodeURIComponent(book.work_id))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/BookCard.tsx|BookCard:22|to={path}|CONTEXT_AWARE_REQUIRED|Destination already prepared by scoped parent/navigation model; external/document URLs retain existing entitlement guard.|YES|
|frontend/src/components/BookConnectionGraph.tsx|BookConnectionGraph:50|to={context.personalPath(/experimental/kg?seed=${encodeURIComponent(target)})}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/BookDetailView.tsx|BookDetailView:17|to={backPath}|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/BookDiscoveryMenu.tsx|BookDiscoveryMenu:9|to={context.personalPath(withPatronContext(/book/${encodeURIComponent(workId)}?related=1#more-like-this, libraryId \|\| context.libraryId))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/BookPersonalActions.tsx|save:18|navigate(/login?next=${encodeURIComponent(location.pathname + location.search)})|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/components/BorrowedBookActions.tsx|BorrowedBookActions:27|to={/book/${encodeURIComponent(issue.work_id)}/read}|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/BorrowedBookActions.tsx|BorrowedBookActions:35|to={/llm?book=${encodeURIComponent(issue.work_id)}}|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/CatalogueBookActions.tsx|CatalogueBookActions:32|to={bookPath(book)}|CONTEXT_AWARE_REQUIRED|Shared product destination preserves explicit workspace context.|YES|
|frontend/src/components/CatalogueBookActions.tsx|CatalogueBookActions:33|to={patronPath(book.library_id, 'my-library')}|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/components/CategoryExplorer.tsx|handleCategoryClick:171|navigate(context ? patronPath(context.data.source.library_id, catalogue?subject=${encodeURIComponent(categoryName)}) : /catalog?category=${encodeURIComponent(categoryName)})|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/components/CategoryExplorer.tsx|CategoryExplorer:194|to={productNavigation.personalPath(homeBookPath(context, activeBook.work_id))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/DiscoveryBookFrame.tsx|DiscoveryBookFrame:9|to={path}|CONTEXT_AWARE_REQUIRED|Destination already prepared by scoped parent/navigation model; external/document URLs retain existing entitlement guard.|YES|
|frontend/src/components/Footer.tsx|Footer:6|to:context.cataloguePath|CONTEXT_AWARE_REQUIRED|Central resolver: staff /staff/libraries/:id; patron /libraries/:id; platform /platform; explicit global /.|YES|
|frontend/src/components/Footer.tsx|Footer:6|to:context.libraryId ? '/libraries/'+context.libraryId+'/new-arrivals' : context.personalPath('/catalog?sort=new_arrivals')|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/Footer.tsx|Footer:6|to:context.personalPath('/reading-list')|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/Footer.tsx|Footer:6|to:context.personalPath('/account/libraries')|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/Footer.tsx|Footer:6|to:context.personalPath('/events')|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/Footer.tsx|Footer:6|to:context.personalPath('/llm')|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/Footer.tsx|Footer:7|to={context.homePath}|CONTEXT_AWARE_REQUIRED|Central resolver: staff /staff/libraries/:id; patron /libraries/:id; platform /platform; explicit global /.|YES|
|frontend/src/components/Footer.tsx|Footer:7|to={link.to}|CONTEXT_AWARE_REQUIRED|Destination already prepared by scoped parent/navigation model; external/document URLs retain existing entitlement guard.|YES|
|frontend/src/components/ForYou.tsx|ForYou:127|to={productNavigation.personalPath(homeCataloguePath(context, 'catalogue?view=for-you'))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/Header.tsx|module:14|to: '/experimental/kg'|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/Header.tsx|module:14|to: '/catalog'|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/Header.tsx|module:14|to: '/#new-arrivals'|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/Header.tsx|module:14|to: '/events'|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/Header.tsx|module:14|to: '/#about'|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/Header.tsx|module:14|to: '/llm'|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/Header.tsx|Header:23|to: patronPath(scopedPatronId, 'catalogue')|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/components/Header.tsx|Header:23|to: patronPath(scopedPatronId, 'new-arrivals')|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/components/Header.tsx|Header:23|to: context.personalPath(link.to)|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/Header.tsx|Header:24|to: scopedPatronId ? patronPath(scopedPatronId, 'my-library') : selectedPatron ? patronPath(selectedPatron.library_id, 'my-library') : patrons.length === 1 ? patronPath(patrons[0].library_id, 'my-library') : '/account/libraries?group=patron'|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/components/Header.tsx|Header:25|to={link.to}|CONTEXT_AWARE_REQUIRED|Destination already prepared by scoped parent/navigation model; external/document URLs retain existing entitlement guard.|YES|
|frontend/src/components/Header.tsx|Header:26|href="#main-content"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/components/Header.tsx|Header:26|to={context.homePath}|CONTEXT_AWARE_REQUIRED|Central resolver: staff /staff/libraries/:id; patron /libraries/:id; platform /platform; explicit global /.|YES|
|frontend/src/components/Header.tsx|Header:29|to={context.personalPath('/reading-list')}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/Header.tsx|Header:30|to="/login"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/components/Header.tsx|Header:30|to="/signup"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/components/Header.tsx|Header:32|navigate(scopedPatronId ? patronPath(scopedPatronId, catalogue?search=${encodeURIComponent(search.trim())}) : context.personalPath(/search?q=${encodeURIComponent(search.trim())}))|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/Header.tsx|Header:33|to="/login"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/components/Header.tsx|Header:33|to="/signup"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/components/Hero.tsx|Hero:48|to={productNavigation.personalPath(homeBookPath(context, book.work_id))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/LibraryShells.tsx|StaffLibraryShell:47|to={staffPath(id, path)}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/LibraryShells.tsx|StaffLibraryShell:50|to={staffPath(id)}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/LibraryShells.tsx|StaffOverviewPage:57|to={staffPath(library.library_id, 'inventory?action=add')}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/LibraryShells.tsx|StaffOverviewPage:57|to={staffPath(library.library_id, 'inventory?action=import')}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/LibraryShells.tsx|StaffOverviewPage:57|to={staffPath(library.library_id, 'members')}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/LibraryShells.tsx|StaffOverviewPage:57|to={staffPath(library.library_id, 'inventory?action=add')}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/LibraryShells.tsx|StaffOverviewPage:57|to={staffPath(library.library_id, 'inventory?action=import')}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/LibraryShells.tsx|StaffOverviewPage:57|to={staffPath(library.library_id, 'circulation')}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/LibraryShells.tsx|StaffOverviewPage:57|to={staffPath(library.library_id, 'circulation?tab=return')}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/LibraryShells.tsx|StaffOverviewPage:57|to={staffPath(library.library_id, 'members')}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/LibraryShells.tsx|PatronLibraryShell:66|to={patronPath(id)}|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/components/LibraryShells.tsx|PatronLibraryShell:68|to={patronPath(id, 'my-library')}|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/components/LibraryShells.tsx|PatronLibraryShell:68|to={patronPath(id, 'reservations')}|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/components/LibraryShells.tsx|PatronLibraryShell:68|to={patronPath(id, 'fees')}|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/components/LibrarySwitcher.tsx|LibrarySwitcher:10|navigate(libraryWorkspaceHome(row))|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/ManagementRoutes.tsx|PlatformRoute:10|to="/login"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/components/ManagementRoutes.tsx|PlatformRoute:13|to="/account/libraries"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/ManagementRoutes.tsx|ManagementRedirect:21|to="/platform"|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/components/ManagementRoutes.tsx|ManagementRedirect:23|to={libraryWorkspaceHome(memberships[0])}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/ManagementRoutes.tsx|ManagementRedirect:24|to="/account/libraries?group=staff"|OBSOLETE|Compatibility redirect only, or read-only historical account page; no independent dashboard.|NO|
|frontend/src/components/ManagementRoutes.tsx|ManagementRedirect:25|to="/account/libraries"|OBSOLETE|Compatibility redirect only, or read-only historical account page; no independent dashboard.|NO|
|frontend/src/components/MoreLikeThisSection.tsx|MoreLikeThisSection:20|to="/login"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/components/MoreLikeThisSection.tsx|MoreLikeThisSection:26|to={context.personalPath(/experimental/kg?seed=${encodeURIComponent(workId)})}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/NewArrivals.tsx|NewArrivals:15|to={productNavigation.personalPath(homeCataloguePath(context,'new-arrivals'))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/PopularBooks.tsx|PopularBooks:91|to={productNavigation.personalPath(homeCataloguePath(context, discover ? 'catalogue' : 'popular'))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/ProtectedRoute.tsx|ProtectedRoute:9|to="/login"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/components/ProtectedRoute.tsx|ProtectedRoute:13|to="/account/libraries"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/ProtectedRoute.tsx|ProtectedRoute:14|to={libraryWorkspaceHome(library)}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/RelatedBookCard.tsx|RelatedBookCard:33|to={context.personalPath(productBookPath(book.work_id,context.libraryId))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/RelatedBookCard.tsx|RelatedBookCard:42|to={context.personalPath(productBookPath(book.work_id,context.libraryId))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/Toast.tsx|ToastContainer:53|to={toast.href}|CONTEXT_AWARE_REQUIRED|Destination already prepared by scoped parent/navigation model; external/document URLs retain existing entitlement guard.|YES|
|frontend/src/components/WorkspaceRoute.tsx|WorkspaceRoute:22|to="/account/libraries"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/WorkspaceRoute.tsx|WorkspaceRoute:24|to="/account/libraries"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/components/WorkspaceRoute.tsx|WorkspaceRoute:25|to={libraryWorkspaceHome(library)}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/WorkspaceRoute.tsx|AdminLibraryRoute:30|to={libraryWorkspaceHome(library)}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/WorkspaceRoute.tsx|LegacyWorkspaceRedirect:38|to={isLibraryStaff(library) ? staffPath(library.library_id, section === 'catalogue' ? 'inventory' : section) : patronPath(library.library_id, section === 'inventory' ? 'catalogue' : section)}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/WorkspaceRoute.tsx|LegacyWorkspaceRedirect:39|to="/account/libraries"|OBSOLETE|Compatibility redirect only, or read-only historical account page; no independent dashboard.|NO|
|frontend/src/components/WorkspaceRoute.tsx|AccountLanding:46|to="/platform"|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/components/WorkspaceRoute.tsx|AccountLanding:47|to={libraries.length === 1 ? libraryWorkspaceHome(libraries[0]) : libraries.length ? '/account/libraries' : '/'}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/components/assistant/AssistantTurn.tsx|ReadingListView:90|to={context.personalPath(productBookPath(book.work_id,context.libraryId))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/assistant/AssistantTurn.tsx|AssistantTurn:152|to={context.personalPath(productBookPath(book.work_id,context.libraryId))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/assistant/AssistantTurn.tsx|AssistantTurn:238|to={response.intent === 'USER_FEES' ? '/libraries/'+account.library_id+'/fees' : '/libraries/'+account.library_id+'/reservations'}|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/components/events/EventUI.tsx|RelatedBook:13|to={context.personalPath(productBookPath(book.work_id,context.libraryId))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/events/EventUI.tsx|EventCard:17|to={context.personalPath('/events/' + event.event_id)}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/components/events/EventUI.tsx|EventCard:17|to={context.personalPath('/events/' + event.event_id)}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/lib/nav.ts|getRoleNavLinks:4|to: '/account/libraries'|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/AccountPages.tsx|AccountProfilePage:13|to={context.personalPath('/account/libraries')}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/pages/AccountPages.tsx|AccountProfilePage:13|to={context.personalPath('/reading-list')}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/pages/AccountPages.tsx|AccountProfilePage:13|to={context.personalPath('/account/history')}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/pages/AccountPages.tsx|AccountProfilePage:13|to="/platform"|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/AccountPages.tsx|MyLibrariesPage:25|to={libraryWorkspaceHome(l)}|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/pages/AccountPages.tsx|MyLibrariesPage:26|to="/libraries"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/AccountPages.tsx|MyLibrariesPage:26|to="/libraries/register"|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/pages/AccountSetupPage.tsx|AccountSetupPage:24|to="/login"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/pages/BookReaderPage.tsx|BookReaderPage:14|to={context.personalPath(productBookPath(workId,context.libraryId))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/pages/EventDetailPage.tsx|EventDetailPage:21|to={context.personalPath('/events')}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/pages/EventDetailPage.tsx|EventDetailPage:22|to={'/platform/events/' + event.event_id + '/edit'}|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/EventEditorPage.tsx|save:67|navigate('/platform/events')|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/EventEditorPage.tsx|publishSaved:74|navigate('/platform/events')|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/EventEditorPage.tsx|EventEditorPage:89|to="/platform/events"|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/EventEditorPage.tsx|EventEditorPage:106|to="/platform/events"|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/EventsPage.tsx|EventsPage:32|to="/platform/events"|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/EventsPage.tsx|EventsPage:32|to="/platform/events/new"|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/Home.tsx|GlobalHomeData:211|window.location.reload()|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/InstitutionPanel.tsx|InstitutionPanel:16|to="/libraries"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/Institutions.tsx|submit:40|navigate(libraryWorkspaceHome(activeLibrary(useInstitutionStore.getState())))|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/pages/Institutions.tsx|enter:83|navigate(libraryWorkspaceHome(activeLibrary(useInstitutionStore.getState())))|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/pages/Institutions.tsx|ExploreLibrariesPage:86|to="/account/libraries"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/Institutions.tsx|ExploreLibrariesPage:86|to="/libraries/register"|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/pages/Institutions.tsx|respond:117|navigate(libraryWorkspaceHome(library))|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/pages/Institutions.tsx|PendingInvitationsPage:125|to="/libraries"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/Institutions.tsx|InvitationPage:133|window.location.pathname + window.location.search|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/Institutions.tsx|respond:141|navigate(libraryWorkspaceHome(library))|STAFF_WORKSPACE|Explicit selected library Staff Workspace; active membership required.|NO|
|frontend/src/pages/Institutions.tsx|InvitationPage:146|to="/login"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/pages/Institutions.tsx|InvitationPage:146|to="/signup"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/pages/KnowledgeGraphPage.tsx|KnowledgeGraphPage:103|to={context.personalPath(productBookPath(selectedBook.work_id,context.libraryId))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/pages/KnowledgeGraphPage.tsx|KnowledgeGraphPage:107|to={context.personalPath(productBookPath(book.work_id,context.libraryId))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/pages/KnowledgeGraphPage.tsx|KnowledgeGraphPage:107|to={context.personalPath(productBookPath(book.work_id,context.libraryId))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/pages/LLMPage.tsx|LLMPage:1500|to={product.homePath}|CONTEXT_AWARE_REQUIRED|Central resolver: staff /staff/libraries/:id; patron /libraries/:id; platform /platform; explicit global /.|YES|
|frontend/src/pages/LibraryCatalogue.tsx|LibraryCataloguePage:32|to={patronPath(library.library_id,'genres')}|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/pages/LibraryCatalogue.tsx|LibraryCataloguePage:35|to={/search?q=${encodeURIComponent(search \|\| subject \|\| params.get('author') \|\| '')}}|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/LibraryCatalogue.tsx|LibraryCatalogueGenres:45|navigate(patronPath(library.library_id,catalogue${value ? '?subject='+encodeURIComponent(value) : ''}))|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/pages/LibraryCirculation.tsx|LibraryCirculationPage:39|to="/libraries"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/LibraryCirculation.tsx|Circulation:145|to="/account/history"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/LibraryCirculation.tsx|BookRequestControl:176|to={patronPath(libraryId, 'my-library')}|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/pages/LibraryInventory.tsx|LibraryInventoryPage:28|to="/libraries"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/LibraryInventory.tsx|InventoryDetails:98|href={productContext.cataloguePath}|CONTEXT_AWARE_REQUIRED|Central resolver: staff /staff/libraries/:id; patron /libraries/:id; platform /platform; explicit global /.|YES|
|frontend/src/pages/LibraryInventory.tsx|BookEditor:131|href={productContext.cataloguePath}|CONTEXT_AWARE_REQUIRED|Central resolver: staff /staff/libraries/:id; patron /libraries/:id; platform /platform; explicit global /.|YES|
|frontend/src/pages/LibraryInventory.tsx|InventoryImport:147|href="data:text/csv;charset=utf-8,title%2Csubject%0AOperating%20Systems%20Laboratory%20Manual%2COperating%20Systems%0A"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/LibraryReservationsFees.tsx|LibraryReservationsFeesPage:18|to="/libraries"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/LibraryReservationsFees.tsx|LibraryAccount:83|to={staff ? '/library-circulation' : '/library-loans'}|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/LibraryReservationsFees.tsx|ReservationControl:118|to="/library-loans"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/LoginPage.tsx|LoginPage:28|to={workspaceDestination(from)}|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/LoginPage.tsx|handleSubmit:57|navigate(workspaceDestination(from), { replace: true })|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/LoginPage.tsx|handleSubmit:63|navigate("/verify-otp", { state: { email } })|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/LoginPage.tsx|LoginPage:182|to="/signup"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/pages/ManageEventsPage.tsx|ManageEventsPage:21|to="/events"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/ManageEventsPage.tsx|ManageEventsPage:21|to="/platform/events/new"|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/ManageEventsPage.tsx|ManageEventsPage:24|to={'/platform/events/' + event.event_id + '/edit'}|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/ManageEventsPage.tsx|ManageEventsPage:24|to={'/events/' + event.event_id}|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/PlatformConsole.tsx|PlatformShell:17|to={'/platform' + (s.path ? '/' + s.path : '')}|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/PlatformConsole.tsx|PlatformShell:19|to="/platform"|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/PlatformConsole.tsx|PlatformOverview:26|to="/platform/libraries"|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/PlatformConsole.tsx|PlatformOverview:26|to={productContext.personalPath('/account/libraries?group=staff')}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/pages/PlatformConsole.tsx|PlatformCatalogue:53|to={productContext.personalPath('/book/' + encodeURIComponent(row.work_id))}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/pages/PlatformLibraries.tsx|PlatformLibrariesPage:43|to={'/platform/libraries/'+row.library_id}|PATRON_WORKSPACE|Explicit library target or invitation/discovery; workspace route verifies role and corrects staff away from patron.|NO|
|frontend/src/pages/PlatformLibraries.tsx|PlatformLibraryDetailPage:81|to="/platform/libraries"|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/PlatformOperations.tsx|LegacyOperationHistory:124|to={/book/${encodeURIComponent(r.book.work_id)}}|GLOBAL_INTENTIONAL|Canonical Platform Console route; explicit platform authority required.|NO|
|frontend/src/pages/ProfilePage.tsx|LegacyProfilePage:23|to={context.personalPath('/account/libraries?group=patron')}|PERSONAL_WITH_RETURN_CONTEXT|Preserve explicit URL workspace return context through centralized product resolver.|YES|
|frontend/src/pages/ProfilePage.tsx|ProfilePage:25|to="/my-library"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/ReadingListPage.tsx|ReadingListPage:21|to={context.cataloguePath}|CONTEXT_AWARE_REQUIRED|Central resolver: staff /staff/libraries/:id; patron /libraries/:id; platform /platform; explicit global /.|YES|
|frontend/src/pages/SignUpPage.tsx|SignUpPage:19|to="/"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/SignUpPage.tsx|handleSubmit:60|navigate('/verify-otp', { state: { email } })|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/SignUpPage.tsx|SignUpPage:194|to="/login"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/pages/StaffLoginPage.tsx|StaffLoginPage:30|to={workspaceDestination()}|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/StaffLoginPage.tsx|submit:37|navigate(workspaceDestination(), { replace: true })|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/VerifyOTPPage.tsx|VerifyOTPPage:33|to="/"|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|
|frontend/src/pages/VerifyOTPPage.tsx|VerifyOTPPage:38|to="/signup"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/pages/VerifyOTPPage.tsx|handleSubmit:86|navigate('/login', { replace: true, state: { verified: true }, })|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/pages/VerifyOTPPage.tsx|handleResend:126|navigate('/login', { replace: true })|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/pages/VerifyOTPPage.tsx|VerifyOTPPage:222|to="/signup"|GLOBAL_INTENTIONAL|Authentication clears previous context, or same-page accessible anchor.|NO|
|frontend/src/store/useAssistantStore.ts|module:80|window.location.pathname + window.location.search|GLOBAL_INTENTIONAL|Explicit global route or authentication destination; no library inference.|NO|

The readNow compatibility helper in lib/readNow.ts has no production call sites (repository-wide reference check); current BookCapabilities and BookReaderPage use the shared context hook. No blind replacement of root/global authentication or external document links was made.

## Part 2F.1 canonical collection supplement

The 193-entry accepted audit above remains the baseline. This closure rechecked the actual collection entry points below. Seven live navigation scenarios pass in `institution_v2f1_staff_catalog_browser.json`; return parameters preserve personal navigation and never supply tenant authority.

| FILE | COMPONENT | CURRENT DESTINATION | CLASSIFICATION | EXPECTED DESTINATION | FIXED |
|---|---|---|---|---|---|
| frontend/src/components/Header.tsx | Staff Catalog | centralized cataloguePath | STAFF_WORKSPACE | /staff/libraries/current UUID/inventory | YES |
| frontend/src/components/Header.tsx | Staff Search | centralized searchPath | STAFF_WORKSPACE | current inventory with bounded search | YES |
| frontend/src/components/Header.tsx | Staff New Arrivals | centralized newArrivalsPath | STAFF_WORKSPACE | current inventory with newest ordering | YES |
| frontend/src/components/Header.tsx | Patron Browse | centralized cataloguePath | PATRON_WORKSPACE | /libraries/current UUID/catalogue | YES |
| frontend/src/pages/CatalogPage.tsx | old staff_library URL | canonical redirect only | OBSOLETE | Staff inventory; cannot render global as Staff Catalog | YES |
| frontend/src/pages/LibraryInventory.tsx | optional global reference lookup | explicit /catalog in a new tab | GLOBAL_INTENTIONAL | global catalogue for reference selection | YES |
| frontend/src/lib/productContext.ts | shared catalogue/new arrivals/search destinations | URL context and validated UUID | CONTEXT_AWARE_REQUIRED | Staff, Patron, Platform or explicit Global destination | YES |

Staff Reading List return resolves to Staff Overview; Patron Reading List return resolves to Patron Home. An explicit global Catalog resolves Home to `/`. No first-membership guess is used.
