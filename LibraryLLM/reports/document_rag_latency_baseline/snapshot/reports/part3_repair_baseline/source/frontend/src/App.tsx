import { Routes, Route, Navigate } from 'react-router-dom'
import { Header } from '@/components/Header'
import { Footer } from '@/components/Footer'
import { AIChatWidget } from '@/components/AIChatWidget'
import { ToastContainer } from '@/components/Toast'
import ProtectedRoute from '@/components/ProtectedRoute'
import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'

import { Home } from '@/pages/Home'
import { CatalogPage } from '@/pages/CatalogPage'
import { SearchPage } from '@/pages/SearchPage'
import { BookDetailPage } from '@/pages/BookDetailPage'
import { BookReaderPage } from '@/pages/BookReaderPage'
import { BORROW_STATE_CHANGED } from '@/lib/api'
import { useAuthStore } from '@/store/useAuthStore'
import { useAssistantStore } from '@/store/useAssistantStore'
import { useLibraryStore } from '@/store/useLibraryStore'
import { ReadingListPage } from '@/pages/ReadingListPage'
import { ProfilePage } from '@/pages/ProfilePage'
import { LLMPage } from '@/pages/LLMPage'
import { LoginPage } from '@/pages/LoginPage'
import { StaffLoginPage } from '@/pages/StaffLoginPage'
import { StaffSetupPage } from '@/pages/StaffSetupPage'
import { SignUpPage } from '@/pages/SignUpPage'
import { VerifyOTPPage } from '@/pages/VerifyOTPPage'
import { StaffDashboard } from '@/pages/StaffDashboard'
import { ReaderDashboard } from '@/pages/CorePages'


function DashboardLayout() {
  const { pathname } = useLocation()
  const staffPage = pathname === '/admin' || pathname === '/librarian'
  return (
    <div className="min-h-screen bg-paper">

      <Header />

      <main>
        <Routes>

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
              <ProtectedRoute allowedRoles={['GENERAL_USER', 'ADMIN', 'LIBRARIAN']}>
                <ProfilePage />
              </ProtectedRoute>
            }
          />

          {/* ── Backward-compatible redirects for old bookmarks & aliases ── */}
          <Route path="/dashboard" element={<ProtectedRoute><ReaderDashboard /></ProtectedRoute>} />
          <Route path="/my-library" element={<Navigate to="/profile" replace />} />
          <Route path="/library" element={<Navigate to="/profile" replace />} />

          {/* ── Role-protected dashboards ── */}

          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={['ADMIN']}>
                <StaffDashboard admin />
              </ProtectedRoute>
            }
          />

          <Route
            path="/librarian"
            element={
              <ProtectedRoute allowedRoles={['ADMIN', 'LIBRARIAN']}>
                <StaffDashboard />
              </ProtectedRoute>
            }
          />

        </Routes>
      </main>

      {!staffPage && <Footer />}

      {!staffPage && <AIChatWidget />}

      <ToastContainer />

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
  useEffect(() => { useAssistantStore.getState().syncOwner(isAuthenticated ? owner : null) }, [isAuthenticated, owner])
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
      if (event.key === 'luminar_token' || event.key === 'luminar_user' || event.key === null) {
        clearUserData()
        initialize()
      }
    }
    window.addEventListener('luminar-session-expired', expire)
    window.addEventListener(BORROW_STATE_CHANGED, refresh)
    window.addEventListener('storage', onStorage)
    window.addEventListener('focus', refresh)
    return () => {
      window.removeEventListener('luminar-session-expired', expire)
      window.removeEventListener(BORROW_STATE_CHANGED, refresh)
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('focus', refresh)
    }
  }, [isAuthenticated, fetchUserData, logout, clearUserData, initialize])

  return (
    <>
      <ScrollToHash />
      <Routes>

      {/* ── Public auth pages (no Header/Footer) ── */}
      <Route path="/staff/login" element={<StaffLoginPage />} />
      <Route path="/staff/setup" element={<StaffSetupPage />} />
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
