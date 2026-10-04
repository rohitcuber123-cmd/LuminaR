import { Routes, Route } from 'react-router-dom'
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
import { useAuthStore } from '@/store/useAuthStore'
import { useLibraryStore } from '@/store/useLibraryStore'
import { ReadingListPage } from '@/pages/ReadingListPage'
import { ProfilePage } from '@/pages/ProfilePage'
import { LLMPage } from '@/pages/LLMPage'
import { LoginPage } from '@/pages/LoginPage'
import { SignUpPage } from '@/pages/SignUpPage'
import { VerifyOTPPage } from '@/pages/VerifyOTPPage'
import { AdminPlaceholder } from '@/pages/AdminPlaceholder'
import { LibrarianPlaceholder } from '@/pages/LibrarianPlaceholder'


function DashboardLayout() {
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

          <Route
            path="/reading-list"
            element={<ReadingListPage />}
          />

          <Route
            path="/profile"
            element={
              <ProtectedRoute allowedRoles={['GENERAL_USER', 'ADMIN', 'LIBRARIAN']}>
                <ProfilePage />
              </ProtectedRoute>
            }
          />

          {/* ── Role-protected dashboards ── */}

          <Route
            path="/admin"
            element={
              <ProtectedRoute allowedRoles={['ADMIN']}>
                <AdminPlaceholder />
              </ProtectedRoute>
            }
          />

          <Route
            path="/librarian"
            element={
              <ProtectedRoute allowedRoles={['LIBRARIAN']}>
                <LibrarianPlaceholder />
              </ProtectedRoute>
            }
          />

        </Routes>
      </main>

      <Footer />

      <AIChatWidget />

      <ToastContainer />

    </div>
  )
}


function LLMLayout() {
  return (
    <div className="h-screen overflow-hidden bg-paper">
      <Header />
      <LLMPage />
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
  const { isAuthenticated, initialize } = useAuthStore()
  const { fetchUserData, clearUserData } = useLibraryStore()

  useEffect(() => {
    initialize()
  }, [])

  useEffect(() => {
    if (isAuthenticated) {
      fetchUserData()
    } else {
      clearUserData()
    }
  }, [isAuthenticated])

  return (
    <>
      <ScrollToHash />
      <Routes>

      {/* ── Public auth pages (no Header/Footer) ── */}
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