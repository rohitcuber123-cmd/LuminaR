import { StatePanel } from './components/WorkspaceUI'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Header } from '@/components/Header'
import { Footer } from '@/components/Footer'
import { AIChatWidget } from '@/components/AIChatWidget'
import { ToastContainer } from '@/components/Toast'
import ProtectedRoute from '@/components/ProtectedRoute'
import { WorkspaceRoute, AdminLibraryRoute, LegacyWorkspaceRedirect, AccountLanding } from '@/components/WorkspaceRoute'
import { StaffLibraryShell, PatronLibraryShell, StaffOverviewPage } from '@/components/LibraryShells'
import { AccountProfilePage, MyLibrariesPage } from '@/pages/AccountPages'
import { LibraryActivityPage } from '@/pages/LibraryActivity'
import { InstitutionPanel } from '@/pages/InstitutionPanel'
import { useEffect, useRef } from 'react'
import { useLocation, useParams, useNavigate } from 'react-router-dom'
import { withProductContext } from '@/lib/productContext'

import { Home } from '@/pages/Home'
import { CatalogPage } from '@/pages/CatalogPage'
import { SearchPage } from '@/pages/SearchPage'
import { BookDetailPage } from '@/pages/BookDetailPage'
import { BookReaderPage } from '@/pages/BookReaderPage'
import { BORROW_STATE_CHANGED } from '@/lib/api'
import { useAuthStore } from '@/store/useAuthStore'
import { watchSessionStorage } from '@/lib/sessionStorageSync'
import { useAssistantStore } from '@/store/useAssistantStore'
import { useLibraryStore } from '@/store/useLibraryStore'
import { ReadingListPage } from '@/pages/ReadingListPage'
import { LegacyProfilePage } from '@/pages/ProfilePage'
import { LLMPage } from '@/pages/LLMPage'
import { LoginPage } from '@/pages/LoginPage'
import { StaffLoginPage } from '@/pages/StaffLoginPage'
import { AccountSetupPage } from '@/pages/AccountSetupPage'
import { SignUpPage } from '@/pages/SignUpPage'
import { VerifyOTPPage } from '@/pages/VerifyOTPPage'
import { PlatformRoute, ManagementRedirect } from '@/components/ManagementRoutes'
import { PlatformShell, PlatformOverview, PlatformCatalogue, PlatformAccountsPage, PlatformNotificationsPage, PlatformHistoryPage, PlatformAuthorityReview } from '@/pages/PlatformConsole'
import { usePlatformStore } from '@/store/usePlatformStore'
import { PlatformLibrariesPage, PlatformLibraryDetailPage } from '@/pages/PlatformLibraries'
import { KnowledgeGraphPage } from '@/pages/KnowledgeGraphPage'
import { EventsPage } from '@/pages/EventsPage'
import { EventDetailPage } from '@/pages/EventDetailPage'
import { ManageEventsPage } from '@/pages/ManageEventsPage'
import { EventEditorPage } from '@/pages/EventEditorPage'
import { EventMonitor } from '@/components/events/EventMonitor'
import { ExploreLibrariesPage, RegisterLibraryPage, PendingInvitationsPage, InvitationPage } from '@/pages/Institutions'
import { LibraryCataloguePage, LibraryCatalogueGenres, LibraryCatalogueDetail } from '@/pages/LibraryCatalogue'
import { useInstitutionStore } from '@/store/useInstitutionStore'
import { LibraryInventoryPage } from '@/pages/LibraryInventory'
import { LibraryCirculationPage } from '@/pages/LibraryCirculation'
import { LibraryReservationsFeesPage } from '@/pages/LibraryReservationsFees'
import { LibraryAnalyticsPage } from '@/pages/LibraryAnalyticsPage'
import '@/styles/workspaces.css'


function LegacyEventRedirect() { const { eventId = '' } = useParams(); return <Navigate to={'/platform/events/' + encodeURIComponent(eventId) + '/edit'} replace /> }

function DashboardLayout() {
  const location = useLocation(), { pathname } = location, navigate = useNavigate()
  const sessionToken = useAuthStore(s => s.token)
  const previousSession = useRef(sessionToken)
  useEffect(() => {
    if(previousSession.current && previousSession.current !== sessionToken) {
      const clean=withProductContext(location.pathname+location.search+location.hash,{kind:'GLOBAL',libraryId:null})
      if(clean !== location.pathname+location.search+location.hash) navigate(clean,{replace:true})
    }
    previousSession.current=sessionToken
  },[sessionToken,location.pathname,location.search,location.hash,navigate])
  const staffPage = pathname.startsWith('/staff/') || pathname.startsWith('/platform')
  const workspacePage = staffPage || /^\/libraries\/[^/]+/.test(pathname) && pathname !== '/libraries/register'
  const accountGateway = pathname.startsWith('/account/') || pathname.startsWith('/invitations') || pathname === '/libraries' || pathname === '/libraries/register'
  return (
    <div className={`min-h-screen bg-paper${accountGateway ? ' workspace-gateway' : ''}${workspacePage ? ' workspace-surface' : ''}`}>

      <Header />

      <main id="main-content" tabIndex={-1}>
        <Routes key={sessionToken || 'signed-out'}>
          <Route path="/library-inventory" element={<ProtectedRoute><LegacyWorkspaceRedirect section="inventory" /></ProtectedRoute>} />
          <Route path="/legacy-library-history" element={<Navigate to="/account/history" replace />} />
          <Route path="/library-loans" element={<ProtectedRoute><LegacyWorkspaceRedirect mode="PATRON" section="my-library" /></ProtectedRoute>} />
          <Route path="/library-circulation" element={<ProtectedRoute><LegacyWorkspaceRedirect mode="STAFF" section="circulation" /></ProtectedRoute>} />
          <Route path="/library-reservations" element={<ProtectedRoute><LegacyWorkspaceRedirect mode="PATRON" section="reservations" /></ProtectedRoute>} />
          <Route path="/library-fees" element={<ProtectedRoute><LegacyWorkspaceRedirect mode="PATRON" section="fees" /></ProtectedRoute>} />
          <Route path="/library-circulation/reservations" element={<ProtectedRoute><LegacyWorkspaceRedirect mode="STAFF" section="reservations" /></ProtectedRoute>} />
          <Route path="/library-circulation/fees" element={<ProtectedRoute><LegacyWorkspaceRedirect mode="STAFF" section="fees" /></ProtectedRoute>} />
          <Route path="/account/profile" element={<ProtectedRoute><AccountProfilePage /></ProtectedRoute>} />
          <Route path="/account/libraries" element={<ProtectedRoute><MyLibrariesPage /></ProtectedRoute>} />
          <Route path="/account/continue" element={<ProtectedRoute><AccountLanding /></ProtectedRoute>} />
          <Route path="/account/history" element={<ProtectedRoute><LegacyProfilePage /></ProtectedRoute>} />
          <Route path="/libraries" element={<ProtectedRoute><ExploreLibrariesPage /></ProtectedRoute>} />
          <Route path="/libraries/register" element={<ProtectedRoute><RegisterLibraryPage /></ProtectedRoute>} />
          <Route path="/libraries/:libraryId" element={<ProtectedRoute><WorkspaceRoute><PatronLibraryShell /></WorkspaceRoute></ProtectedRoute>}>
            <Route index element={<Home context="library" />} />
            <Route path="catalogue" element={<LibraryCataloguePage />} />
            <Route path="search" element={<LibraryCataloguePage />} />
            <Route path="new-arrivals" element={<LibraryCataloguePage arrivals />} />
            <Route path="popular" element={<LibraryCataloguePage popular />} />
            <Route path="genres" element={<LibraryCatalogueGenres />} />
            <Route path="books/:bookId" element={<LibraryCatalogueDetail />} />
            <Route path="global-books/:bookId" element={<LibraryCatalogueDetail global />} />
            <Route path="my-library" element={<LibraryCirculationPage />} />
            <Route path="loans" element={<LibraryCirculationPage />} />
            <Route path="reservations" element={<LibraryReservationsFeesPage />} />
            <Route path="fees" element={<LibraryReservationsFeesPage fees />} />
            <Route path="events" element={<EventsPage />} />
            <Route path="events/:eventId" element={<EventDetailPage />} />
          </Route>
          <Route path="/staff/libraries/:libraryId" element={<ProtectedRoute><WorkspaceRoute staff><StaffLibraryShell /></WorkspaceRoute></ProtectedRoute>}>
            <Route index element={<StaffOverviewPage />} />
            <Route path="inventory" element={<LibraryInventoryPage />} />
            <Route path="circulation" element={<LibraryCirculationPage staff />} />
            <Route path="reservations" element={<LibraryReservationsFeesPage staff />} />
            <Route path="fees" element={<LibraryReservationsFeesPage staff fees />} />
            <Route path="events" element={<ManageEventsPage />} />
            <Route path="events/new" element={<EventEditorPage />} />
            <Route path="events/:eventId" element={<EventDetailPage staff />} />
            <Route path="events/:eventId/edit" element={<EventEditorPage />} />
            <Route path="analytics" element={<LibraryAnalyticsPage />} />
            <Route path="members" element={<AdminLibraryRoute><InstitutionPanel section="members" /></AdminLibraryRoute>} />
            <Route path="activity" element={<LibraryActivityPage />} />
            <Route path="settings" element={<InstitutionPanel section="settings" />} />
            <Route path="audit" element={<AdminLibraryRoute><InstitutionPanel section="audit" /></AdminLibraryRoute>} />
          </Route>
          <Route path="/staff/legacy-admin" element={<ProtectedRoute><ManagementRedirect admin /></ProtectedRoute>} />
          <Route path="/staff/legacy-librarian" element={<ProtectedRoute><ManagementRedirect /></ProtectedRoute>} />
          <Route path="/invitations" element={<ProtectedRoute><PendingInvitationsPage /></ProtectedRoute>} />
          <Route path="/invitations/:invitationId" element={<InvitationPage />} />
          <Route path="/events" element={<ProtectedRoute><EventsPage /></ProtectedRoute>} />
          <Route path="/events/:eventId" element={<ProtectedRoute><EventDetailPage /></ProtectedRoute>} />
          <Route path="/platform" element={<ProtectedRoute><PlatformRoute><PlatformShell /></PlatformRoute></ProtectedRoute>}>
            <Route index element={<PlatformOverview />} />
            <Route path="libraries" element={<PlatformLibrariesPage />} />
            <Route path="libraries/:libraryId" element={<PlatformLibraryDetailPage />} />
            <Route path="catalogue" element={<PlatformCatalogue />} />
            <Route path="accounts" element={<PlatformAccountsPage />} />
            <Route path="notifications" element={<PlatformNotificationsPage />} />
            <Route path="history" element={<PlatformHistoryPage />} />
            <Route path="migration-review" element={<PlatformAuthorityReview />} />
            <Route path="events" element={<ManageEventsPage />} />
            <Route path="events/new" element={<EventEditorPage />} />
            <Route path="events/:eventId/edit" element={<EventEditorPage />} />
          </Route>
          <Route path="/staff" element={<ProtectedRoute><ManagementRedirect /></ProtectedRoute>} />
          <Route path="/staff/events" element={<Navigate to="/platform/events" replace />} />
          <Route path="/staff/events/new" element={<Navigate to="/platform/events/new" replace />} />
          <Route path="/staff/events/:eventId/edit" element={<LegacyEventRedirect />} />

          <Route
            path="/"
            element={<Home />}
          />

          <Route
            path="/catalog"
            element={<CatalogPage />}
          />

          <Route
            path="/search"
            element={<SearchPage />}
          />
          <Route path="/experimental/kg" element={<ProtectedRoute><KnowledgeGraphPage /></ProtectedRoute>} />

          <Route
            path="/book/:workId"
            element={<BookDetailPage />}
          />
          <Route path="/book/:workId/read" element={<ProtectedRoute><BookReaderPage /></ProtectedRoute>} />

          <Route
            path="/reading-list"
            element={<ProtectedRoute><ReadingListPage /></ProtectedRoute>}
          />

          <Route
            path="/profile"
            element={
              <ProtectedRoute><LegacyWorkspaceRedirect mode="PATRON" section="my-library" /></ProtectedRoute>
            }
          />

          {/* ── Backward-compatible redirects for old bookmarks & aliases ── */}
          <Route path="/dashboard" element={<ProtectedRoute><AccountLanding /></ProtectedRoute>} />
          <Route path="/my-library" element={<Navigate to="/profile" replace />} />
          <Route path="/library" element={<Navigate to="/profile" replace />} />

          {/* ── Management compatibility redirects ── */}

          <Route
            path="/admin"
            element={
              <ProtectedRoute><ManagementRedirect admin /></ProtectedRoute>
            }
          />

          <Route
            path="/librarian"
            element={
              <ProtectedRoute><ManagementRedirect /></ProtectedRoute>
            }
          />

          <Route path="*" element={<section className="global-page"><StatePanel title="Page not found">Use the navigation to return to your catalogue or library.</StatePanel></section>} />
        </Routes>
      </main>

      {!workspacePage && <Footer />}

      {!staffPage && <AIChatWidget />}


    </div>
  )
}


function LLMLayout() {
  return (
    <div className="h-screen overflow-hidden bg-paper">
      <Header />
      <LLMPage />
      <AIChatWidget />
    </div>
  )
}

function ScrollToHash() {
  const { pathname, hash } = useLocation()

  useEffect(() => {
    if (hash) {
      setTimeout(() => {
        const id = hash.replace('#', '')
        const element = document.getElementById(id)
        if (element) {
          element.scrollIntoView({ behavior: 'smooth' })
        }
      }, 100) // Small delay to ensure DOM is painted
    } else {
      window.scrollTo(0, 0)
    }
  }, [pathname, hash])

  return null
}

function App() {
  const { isAuthenticated, token, initialize, logout } = useAuthStore()
  const owner = useAuthStore(state => state.user?.email ?? null)
  useEffect(() => { usePlatformStore.getState().syncSession(isAuthenticated ? token : null) }, [isAuthenticated, token])
  useEffect(() => { useInstitutionStore.getState().syncSession(isAuthenticated ? owner : null, token) }, [isAuthenticated, owner, token])
  useEffect(() => {
    const refresh = () => { if (isAuthenticated) { void useInstitutionStore.getState().refresh(); void usePlatformStore.getState().refresh() } }
    window.addEventListener('focus', refresh)
    window.addEventListener('luminar-platform-access-denied', refresh)
    return () => {window.removeEventListener('focus', refresh);window.removeEventListener('luminar-platform-access-denied', refresh)}
  }, [isAuthenticated])
  useEffect(() => { useAssistantStore.getState().syncSession(isAuthenticated ? owner : null, token) }, [isAuthenticated, owner, token])
  const { fetchUserData, clearUserData } = useLibraryStore()

  useEffect(() => {
    initialize()
  }, [initialize])

  useEffect(() => {
    if (isAuthenticated) {
      fetchUserData()
    } else {
      clearUserData()
    }
  }, [isAuthenticated, token, fetchUserData, clearUserData])

  useEffect(() => {
    const expire = () => { logout(); clearUserData() }
    const refresh = () => { if (isAuthenticated) void fetchUserData() }
    const onStorage = (event: StorageEvent) => {
      if (event.key === BORROW_STATE_CHANGED) refresh()
    }
    const stopSessionSync = watchSessionStorage(() => { clearUserData(); initialize() })
    window.addEventListener('luminar-session-expired', expire)
    window.addEventListener(BORROW_STATE_CHANGED, refresh)
    window.addEventListener('storage', onStorage)
    window.addEventListener('focus', refresh)
    return () => {
      window.removeEventListener('luminar-session-expired', expire)
      window.removeEventListener(BORROW_STATE_CHANGED, refresh)
      window.removeEventListener('storage', onStorage)
      stopSessionSync()
      window.removeEventListener('focus', refresh)
    }
  }, [isAuthenticated, fetchUserData, logout, clearUserData, initialize])

  return (
    <>
      <EventMonitor />
      <ToastContainer />
      <ScrollToHash />
      <Routes>

      {/* ── Public auth pages (no Header/Footer) ── */}
      <Route path="/staff/login" element={<StaffLoginPage />} />
      <Route path="/account/setup" element={<AccountSetupPage />} />
      <Route path="/staff/setup" element={<Navigate to="/account/setup" replace />} />
      <Route
        path="/login"
        element={<LoginPage />}
      />

      <Route
        path="/signup"
        element={<SignUpPage />}
      />

      <Route
        path="/verify-otp"
        element={<VerifyOTPPage />}
      />

      {/* ── Dedicated LLM workspace ── */}
      <Route
        path="/llm"
        element={<LLMLayout />}
      />

      {/* ── Normal LuminaR website ── */}
      <Route
        path="/*"
        element={<DashboardLayout />}
      />

    </Routes>
    </>
  )
}


export default App
