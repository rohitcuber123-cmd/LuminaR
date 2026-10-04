import { useState, useEffect, lazy, Suspense } from 'react'
import { Link } from 'react-router-dom'
import {
  BookOpen,
  Calendar,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  CreditCard,
  History,
  Bookmark,
} from 'lucide-react'
import { useAuthStore } from '@/store/useAuthStore'
import { useLibraryStore } from '@/store/useLibraryStore'
import {
  getMyIssues,
  returnBook,
  getMyReservations,
  cancelReservation,
  getMyFines,
  payFine,
  getMyActivity,
} from '@/lib/api'
import { showToast } from '@/components/Toast'
import { BorrowedBookActions } from '@/components/BorrowedBookActions'
const LoanRenewalControl = lazy(() => import('@/components/LoanRenewalControl').then(m => ({ default: m.LoanRenewalControl })))

function isBookOverdue(dueDate?: string): boolean {
  if (!dueDate) return false
  return new Date(dueDate).getTime() < Date.now()
}

// --- Loading Skeleton ---
function ProfileSkeleton() {
  return (
    <section className="mx-auto max-w-[90rem] px-6 py-10 md:px-10 md:py-16">
      <div className="mb-10 border-b border-line pb-6">
        <div className="mb-2 h-8 w-48 rounded bg-line/60 animate-pulse" />
      </div>
      <div className="grid grid-cols-1 gap-12 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-12">
          {/* Borrowed Skeleton */}
          <div>
            <div className="mb-6 h-6 w-40 rounded bg-line/60 animate-pulse" />
            <div className="space-y-4">
              {[1, 2].map((i) => (
                <div key={i} className="flex gap-4 rounded-xl border border-line p-4">
                  <div className="h-24 w-16 rounded bg-line/60 animate-pulse" />
                  <div className="flex-1 space-y-3 py-1">
                    <div className="h-4 w-3/4 rounded bg-line animate-pulse" />
                    <div className="h-3 w-1/2 rounded bg-line/60 animate-pulse" />
                    <div className="h-8 w-32 rounded bg-line animate-pulse mt-4" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="space-y-12">
          {/* User Info Skeleton */}
          <div>
            <div className="mb-6 h-6 w-32 rounded bg-line/60 animate-pulse" />
            <div className="rounded-xl border border-line p-6">
              <div className="h-12 w-12 rounded-full bg-line animate-pulse mb-4" />
              <div className="h-4 w-1/2 rounded bg-line animate-pulse mb-2" />
              <div className="h-3 w-3/4 rounded bg-line/60 animate-pulse" />
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export function ProfilePage() {
  const { user } = useAuthStore()

  const [issues, setIssues] = useState<any[]>([])
  const [reservations, setReservations] = useState<any[]>([])
  const [fines, setFines] = useState<any[]>([])
  const [activities, setActivities] = useState<any[]>([])

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const loadData = async () => {
    try {
      setLoading(true)
      setError(false)

      const [issuesRes, resRes, finesRes, actRes] = await Promise.all<any>([
        getMyIssues(),
        getMyReservations(),
        getMyFines(),
        getMyActivity(),
      ])

      console.log('MY RESERVATIONS DEBUG', resRes)
      console.log('PROFILE RESERVATIONS', resRes.reservations)
      console.log(
        'MY RESERVATIONS DEBUG JSON',
        JSON.stringify(resRes),
      )

      setIssues(issuesRes.issues || [])
      setReservations(resRes.reservations || [])
      setFines(finesRes.fines || [])
      setActivities(actRes.activities || [])
    } catch (err) {
      console.error('Failed to load profile data:', err)
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // --- Handlers ---
  const handleReturn = async (issueId: number) => {
    try {
      setActionLoading(`return-${issueId}`)
      await returnBook(issueId)
      showToast('Book returned successfully.', 'success')
      void useLibraryStore.getState().fetchUserData()
      await loadData()
    } catch (err: any) {
      showToast(err.message || 'Failed to return book.', 'warning')
    } finally {
      setActionLoading(null)
    }
  }

  const handleCancelReservation = async (reservationId: number) => {
    try {
      setActionLoading(`cancel-${reservationId}`)
      await cancelReservation(reservationId)
      showToast('Reservation cancelled successfully.', 'success')
      void useLibraryStore.getState().fetchUserData()
      await loadData()
    } catch (err: any) {
      showToast(err.message || 'Failed to cancel reservation.', 'warning')
    } finally {
      setActionLoading(null)
    }
  }

  const handlePayFine = async (fineId: number) => {
    try {
      setActionLoading(`pay-${fineId}`)
      await payFine(fineId)
      showToast('Fine paid successfully.', 'success')
      await loadData()
    } catch (err: any) {
      showToast(err.message || 'Failed to pay fine.', 'warning')
    } finally {
      setActionLoading(null)
    }
  }

  if (loading) return <ProfileSkeleton />

  if (error) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center text-center px-6">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand/10 mb-4">
          <AlertCircle className="h-6 w-6 text-brand" />
        </div>
        <p className="font-display text-2xl text-ink">Unable to load your library</p>
        <p className="mt-2 text-sm text-ink-soft max-w-md">
          We encountered an error loading your profile data.
        </p>
        <button
          onClick={loadData}
          className="mt-6 rounded-md bg-brand px-5 py-2 text-sm font-medium text-paper transition-colors hover:bg-brand-dark"
        >
          RETRY
        </button>
      </div>
    )
  }

  // Derived filtered lists
  const activeIssues = issues.filter((i) => i.status === 'ISSUED')
  const activeReservations = reservations.filter(
    (r) => r.status === 'ACTIVE' || r.status === 'READY_FOR_PICKUP'
  )
  const unpaidFines = fines.filter((f) => f.status === 'UNPAID')

  return (
    <section className="mx-auto max-w-[90rem] px-6 py-10 md:px-10 md:py-16">
      <div className="mb-10 border-b border-line pb-6">
        <h1 className="font-display text-[clamp(1.8rem,4vw,2.6rem)] text-ink">My Library</h1>
      </div>

      <div className="grid grid-cols-1 gap-12 lg:grid-cols-3">
        {/* LEFT COLUMN: Main content */}
        <div className="lg:col-span-2 space-y-12">
          {/* CURRENTLY BORROWED */}
          <div>
            <h2 className="font-display mb-6 text-xl text-ink flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-brand" />
              Currently Borrowed
            </h2>

            {activeIssues.length === 0 ? (
              <div className="rounded-xl border border-dashed border-line p-8 text-center">
                <p className="text-sm text-ink-soft">No books currently borrowed.</p>
                <Link
                  to="/catalog"
                  className="mt-4 inline-block text-[0.75rem] font-medium text-brand hover:underline"
                >
                  Browse Catalog
                </Link>
              </div>
            ) : (
              <div className="space-y-4">
                {activeIssues.map((issue) => (
                  <div
                    key={issue.issue_id}
                    className="flex flex-col sm:flex-row gap-4 rounded-xl border border-line p-5 transition-colors hover:border-brand/30"
                  >
                    <div className="flex-1">
                      <Link to={`/book/${issue.work_id}`} className="group inline-block">
                        <p className="font-display text-lg text-ink group-hover:text-brand transition-colors">
                          {issue.title}
                        </p>
                      </Link>
                      
                      <div className="mt-3 flex flex-wrap gap-4 text-[0.8rem] text-ink-soft">
                        <div className="flex items-center gap-1.5">
                          <Calendar className="h-3.5 w-3.5" />
                          <span>Issued: {new Date(issue.issued_at).toLocaleDateString()}</span>
                        </div>
                        <div className={`flex items-center gap-1.5 ${isBookOverdue(issue.due_date) ? 'text-amber-600 font-medium' : 'text-brand'}`}>
                          <Clock className="h-3.5 w-3.5" />
                          <span>Due: {new Date(issue.due_date).toLocaleDateString()}</span>
                          {isBookOverdue(issue.due_date) && (
                            <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[0.65rem] font-semibold tracking-wider text-amber-600 uppercase">
                              OVERDUE
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex shrink-0 flex-wrap items-start gap-2.5 pt-2 sm:pt-0">
                      <BorrowedBookActions issue={issue} />
                      <Suspense fallback={<span className="text-xs text-ink-soft">Loading renewal…</span>}><LoanRenewalControl loan={issue} onRenewed={async () => {
                        showToast('Loan renewed successfully.', 'success')
                        void useLibraryStore.getState().fetchUserData()
                        await loadData()
                      }} /></Suspense>
                      <button
                        onClick={() => handleReturn(issue.issue_id)}
                        disabled={actionLoading === `return-${issue.issue_id}`}
                        className="font-display rounded-sm bg-brand px-4 py-2 text-[0.7rem] tracking-wide text-paper transition-colors hover:bg-brand-dark disabled:opacity-50"
                      >
                        {actionLoading === `return-${issue.issue_id}` ? 'RETURNING...' : 'RETURN BOOK'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* RESERVATIONS */}
          <div>
            <h2 className="font-display mb-6 text-xl text-ink flex items-center gap-2">
              <Clock className="h-5 w-5 text-brand" />
              Reservations
            </h2>

            {activeReservations.length === 0 ? (
              <div className="rounded-xl border border-dashed border-line p-8 text-center">
                <p className="text-sm text-ink-soft">No active reservations.</p>
              </div>
            ) : (
              <div className="space-y-4">
                {activeReservations.map((res) => (
                  <div
                    key={res.reservation_id}
                    className="flex flex-col sm:flex-row gap-4 rounded-xl border border-line p-5 transition-colors hover:border-brand/30"
                  >
                    <div className="flex-1">
                      <Link to={`/book/${res.work_id}`} className="group inline-block">
                        <p className="font-display text-lg text-ink group-hover:text-brand transition-colors">
                          {res.title}
                        </p>
                      </Link>
                      
                      <div className="mt-3 flex flex-wrap gap-4 text-[0.8rem] text-ink-soft">
                        <div className="flex items-center gap-1.5">
                          <Calendar className="h-3.5 w-3.5" />
                          <span>Reserved: {new Date(res.reserved_at).toLocaleDateString()}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          {res.status === 'READY_FOR_PICKUP' ? (
                            <CheckCircle className="h-3.5 w-3.5 text-moss" />
                          ) : (
                            <Clock className="h-3.5 w-3.5 text-amber-500" />
                          )}
                          <span className={res.status === 'READY_FOR_PICKUP' ? 'text-moss font-medium' : ''}>
                            {res.status.replace(/_/g, ' ')}
                          </span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="flex shrink-0 items-center sm:items-start pt-2 sm:pt-0">
                      <button
                        onClick={() => handleCancelReservation(res.reservation_id)}
                        disabled={actionLoading === `cancel-${res.reservation_id}`}
                        className="font-display rounded-sm border border-line px-4 py-2 text-[0.7rem] tracking-wide text-ink-soft transition-colors hover:border-brand hover:text-brand disabled:opacity-50"
                      >
                        {actionLoading === `cancel-${res.reservation_id}` ? 'CANCELLING...' : 'CANCEL RESERVATION'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          
          {/* READING LIST LINK */}
          <div>
            <Link
              to="/reading-list"
              className="group flex items-center justify-between rounded-xl border border-line bg-panel p-5 transition-colors hover:border-brand/30"
            >
              <div className="flex items-center gap-3 text-ink">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand/10 text-brand">
                  <Bookmark className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="font-display text-lg">Reading List</h3>
                  <p className="text-xs text-ink-soft">View and manage your saved books</p>
                </div>
              </div>
              <span className="font-display text-[0.7rem] tracking-wide text-brand group-hover:underline">
                VIEW READING LIST
              </span>
            </Link>
          </div>
        </div>

        {/* RIGHT COLUMN: Sidebar info */}
        <div className="space-y-10">
          {/* USER INFO */}
          <div>
            <h2 className="font-display mb-4 text-[0.75rem] tracking-widest text-ink-soft uppercase">
              User Information
            </h2>
            <div className="rounded-xl border border-line p-6">
              <p className="font-display text-xl text-ink">
                {user?.name || user?.full_name || 'Library User'}
              </p>
              <p className="mt-1 text-sm text-ink-soft">{user?.email}</p>
              {user?.role && (
                <span className="mt-3 inline-block rounded-full bg-brand/10 px-2.5 py-1 text-[0.65rem] font-medium uppercase tracking-wider text-brand">
                  {user.role.replace(/_/g, ' ')}
                </span>
              )}
            </div>
          </div>

          {/* FINES */}
          <div>
            <h2 className="font-display mb-4 text-[0.75rem] tracking-widest text-ink-soft uppercase flex items-center gap-2">
              <CreditCard className="h-4 w-4" />
              Fines & Fees
            </h2>
            
            {unpaidFines.length === 0 ? (
              <div className="rounded-xl border border-dashed border-line p-6 text-center">
                <p className="text-sm text-ink-soft">No outstanding fines.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {unpaidFines.map((fine) => (
                  <div key={fine.fine_id} className="rounded-xl border border-line p-4">
                    <div className="flex justify-between items-start mb-2">
                      <p className="font-medium text-ink truncate pr-2" title={fine.title}>
                        {fine.title}
                      </p>
                      <p className="font-display text-brand font-bold">${fine.amount.toFixed(2)}</p>
                    </div>
                    <p className="text-xs text-ink-soft mb-4">
                      {fine.overdue_days} days overdue
                    </p>
                    <button
                      onClick={() => handlePayFine(fine.fine_id)}
                      disabled={actionLoading === `pay-${fine.fine_id}`}
                      className="w-full font-display rounded-sm bg-ink px-4 py-2 text-[0.7rem] tracking-wide text-paper transition-colors hover:bg-ink-soft disabled:opacity-50"
                    >
                      {actionLoading === `pay-${fine.fine_id}` ? 'PROCESSING...' : 'PAY FINE'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* RECENT ACTIVITY */}
          <div>
            <h2 className="font-display mb-4 text-[0.75rem] tracking-widest text-ink-soft uppercase flex items-center gap-2">
              <History className="h-4 w-4" />
              Recent Activity
            </h2>
            
            {activities.length === 0 ? (
              <div className="rounded-xl border border-dashed border-line p-6 text-center">
                <p className="text-sm text-ink-soft">No recent activity.</p>
              </div>
            ) : (
              <div className="space-y-4 rounded-xl border border-line p-5">
                {activities.slice(0, 5).map((act) => (
                  <div key={act.activity_id} className="flex gap-3">
                    <div className="mt-0.5 flex shrink-0">
                      {act.activity_type.includes('RETURN') ? (
                        <CheckCircle className="h-4 w-4 text-moss" />
                      ) : act.activity_type.includes('CANCEL') ? (
                        <XCircle className="h-4 w-4 text-ink-soft" />
                      ) : act.activity_type.includes('FINE') ? (
                        <CreditCard className="h-4 w-4 text-brand" />
                      ) : (
                        <BookOpen className="h-4 w-4 text-brand" />
                      )}
                    </div>
                    <div>
                      <p className="text-sm text-ink leading-snug">{act.description}</p>
                      <p className="mt-0.5 text-[0.7rem] text-ink-soft">
                        {new Date(act.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}
