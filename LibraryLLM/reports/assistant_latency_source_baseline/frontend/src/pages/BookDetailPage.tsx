import { useState, useEffect } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import {
  ArrowLeft,
  Calendar,
  Layers,
  BookOpen as BookIcon,
  AlertCircle,
} from 'lucide-react'
import { BookCover } from '@/components/BookCover'
import { BookSelectButton } from '@/components/BookSelectButton'
import { useAssistantPageContext } from '@/hooks/useAssistantPageContext'
import { BookCapabilities } from '@/components/BookCapabilities'
import { PALETTES, type CoverVariant } from '@/data/books'
import { useLibraryStore } from '@/store/useLibraryStore'
import { showToast } from '@/components/Toast'
import {
  getBook,
  issueBook,
  reserveBook,
  type BackendBook,
} from '@/lib/api'
import { useAuthStore } from '@/store/useAuthStore'
import { useBookActionState } from '@/hooks/useBookActionState'

// Skeleton loader matching LuminaR theme
function BookDetailSkeleton() {
  return (
    <section className="mx-auto max-w-[90rem] px-6 py-10 md:px-10 md:py-16">
      <div className="mb-8 h-5 w-32 rounded bg-line/60 animate-pulse" />

      <div className="grid grid-cols-1 gap-12 md:grid-cols-[minmax(0,18rem)_1fr] lg:gap-16">
        <div className="mx-auto w-[65%] md:w-full">
          <div className="aspect-[2/3] w-full rounded-[2px] bg-line/60 shadow-[0_18px_40px_rgba(0,0,0,0.15)] animate-pulse" />
        </div>

        <div>
          <div className="mb-2 h-3 w-20 rounded bg-line animate-pulse" />
          <div className="h-10 w-3/4 rounded bg-line animate-pulse" />
          <div className="mt-3 h-6 w-1/3 rounded bg-line/60 animate-pulse" />

          <div className="mt-8 flex gap-6">
            <div className="h-5 w-24 rounded bg-line/40 animate-pulse" />
            <div className="h-5 w-24 rounded bg-line/40 animate-pulse" />
            <div className="h-5 w-32 rounded bg-line/40 animate-pulse" />
          </div>

          <div className="mt-8 space-y-3 border-t border-line pt-8">
            <div className="h-4 w-full rounded bg-line/50 animate-pulse" />
            <div className="h-4 w-full rounded bg-line/50 animate-pulse" />
            <div className="h-4 w-2/3 rounded bg-line/50 animate-pulse" />
          </div>

          <div className="mt-8 flex gap-3">
            <div className="h-10 w-32 rounded bg-line animate-pulse" />
            <div className="h-10 w-40 rounded bg-line animate-pulse" />
          </div>
        </div>
      </div>
    </section>
  )
}

export function BookDetailPage() {
  const { workId } = useParams<{ workId: string }>()
  useAssistantPageContext({ work_id: workId })
  const navigate = useNavigate()

  // ============================================================
  // ALL HOOKS MUST BE CALLED BEFORE ANY CONDITIONAL RETURNS
  // ============================================================

  const { toggleList, isInList, fetchUserData } = useLibraryStore()
  const { isAuthenticated } = useAuthStore()

  const [book, setBook] = useState<BackendBook | null>(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)

  // ✅ CRITICAL FIX: Call useBookActionState UNCONDITIONALLY
  // Pass null book during loading - hook now handles this safely
  const { action, adjustedAvailable } = useBookActionState(book)

  // ============================================================
  // DATA LOADING
  // ============================================================

  const loadData = async () => {
    if (!workId) {
      setError(true)
      setLoading(false)
      return
    }

    try {
      setLoading(true)
      setError(false)

      const bookData = await getBook(workId)

      if (bookData && bookData.work_id) {
        setBook(bookData)
      } else {
        setError(true)
      }
    } catch (err) {
      console.error('Failed to load book details:', err)
      setError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [workId, isAuthenticated])

  // ============================================================
  // ACTION HANDLERS
  // ============================================================

  const handleBorrow = async () => {
    if (!isAuthenticated) {
      navigate('/login')
      return
    }

    try {
      setActionLoading(true)

      await issueBook(workId as string)

      showToast(
        `Successfully borrowed "${book?.title}"`,
        'success',
      )

      await Promise.all([loadData(), fetchUserData()])
    } catch (err: any) {
      showToast(
        err.message || 'Failed to borrow book.',
        'warning',
      )
    } finally {
      setActionLoading(false)
    }
  }

  const handleReserve = async () => {
    if (!isAuthenticated) {
      navigate('/login')
      return
    }

    try {
      setActionLoading(true)

      await reserveBook(workId as string)

      showToast(
        `Successfully reserved "${book?.title}"`,
        'success',
      )

      await Promise.all([loadData(), fetchUserData()])
    } catch (err: any) {
      showToast(
        err.message || 'Failed to reserve book.',
        'warning',
      )
    } finally {
      setActionLoading(false)
    }
  }

  // ============================================================
  // CONDITIONAL RENDERING (AFTER ALL HOOKS)
  // ============================================================
  if (loading && !book) {
    return <BookDetailSkeleton />
  }

  if (error || !book) {
    return (
      <div className="mx-auto max-w-[90rem] px-6 py-20 text-center md:px-10 flex flex-col items-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand/10 mb-4">
          <AlertCircle className="h-6 w-6 text-brand" />
        </div>

        <p className="font-display text-2xl text-ink">
          Book not found
        </p>

        <Link
          to="/catalog"
          className="mt-4 rounded-md bg-brand px-5 py-2 text-sm font-medium text-paper transition-colors hover:bg-brand-dark"
        >
          Return to Catalog
        </Link>
      </div>
    )
  }

  // ============================================================
  // DERIVED VALUES (Book is now guaranteed non-null)
  // ============================================================

  const stringId = book.work_id
  const inList = isInList(stringId)

  const availability =
    adjustedAvailable <= 0
      ? 'Currently unavailable'
      : `${adjustedAvailable} of ${book.total_copies} available`

  // Map backend fields
  const displayTitle = book.title
  const displayAuthor = book.authors || 'Unknown Author'
  const displayDescription =
    book.description || 'No description available.'
  const displayShelf =
    book.shelf_location || 'Not assigned'

  const displaySubjects = book.subjects
    ? book.subjects
        .split('|')
        .map(s => s.trim())
        .filter(Boolean)
    : []

  const primaryCategory =
    displaySubjects.length > 0
      ? displaySubjects[0]
      : 'Book'

  // Calculate deterministic visual properties for BookCover
  const paletteIndex =
    book.book_id % PALETTES.length

  const variants: CoverVariant[] = [
    'circle',
    'ring',
    'split',
    'stripe',
  ]

  const variant =
    variants[book.book_id % variants.length]

  // ============================================================
  // MAIN RENDER
  // ============================================================

  return (
    <section className="mx-auto max-w-[90rem] px-6 py-10 md:px-10 md:py-16">

      {/* Back link */}
      <Link
        to="/catalog"
        className="mb-8 inline-flex items-center gap-2 text-sm text-ink-soft transition-colors hover:text-brand"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to catalog
      </Link>

      <div className="grid grid-cols-1 gap-12 md:grid-cols-[minmax(0,18rem)_1fr] lg:gap-16">

        {/* Cover */}
        <div className="mx-auto w-[65%] md:w-full">
          <BookCover
            title={displayTitle}
            author={displayAuthor}
            paletteIndex={paletteIndex}
            variant={variant}
            className="shadow-[0_18px_40px_rgba(0,0,0,0.15)]"
          />
        </div>

        {/* Details */}
        <div>

          <p
            className="font-display mb-2 text-[0.72rem] tracking-[0.2em] text-brand uppercase truncate"
            title={primaryCategory}
          >
            {primaryCategory}
          </p>

          <h1 className="font-display text-[clamp(1.8rem,4vw,2.8rem)] leading-[1.05] text-ink">
            {displayTitle}
          </h1>

          <p className="mt-3 text-lg text-ink-soft">
            by {displayAuthor}
          </p>

          {/* Metadata */}
          <div className="mt-8 flex flex-wrap gap-6">

            <div className="flex items-center gap-2 text-sm text-ink-soft">
              <BookIcon className="h-4 w-4" />

              <span
                className={
                  adjustedAvailable > 0
                    ? 'text-moss font-medium'
                    : 'text-ink-soft/70'
                }
              >
                {availability}
              </span>
            </div>

            <div
              className="flex items-center gap-2 text-sm text-ink-soft"
              title="Shelf Location"
            >
              <Layers className="h-4 w-4" />
              <span>{displayShelf}</span>
            </div>

            <div
              className="flex items-center gap-2 text-sm text-ink-soft"
              title="Rating"
            >
              <span className="font-medium text-brand">
                ★
              </span>

              <span>
                {book.average_rating > 0
                  ? `${book.average_rating.toFixed(1)} (${book.rating_count})`
                  : 'No ratings yet'}
              </span>
            </div>

            <div
              className="flex items-center gap-2 text-sm text-ink-soft"
              title="Reading logs"
            >
              <Calendar className="h-4 w-4" />
              <span>
                {book.reading_log_count} reads
              </span>
            </div>

          </div>

          {/* Tags / Subjects */}
          {displaySubjects.length > 1 && (
            <div className="mt-6 flex flex-wrap gap-2">
              {displaySubjects
                .slice(1, 5)
                .map((subject, idx) => (
                  <span
                    key={idx}
                    className="rounded-full bg-brand/5 px-2.5 py-1 text-[0.65rem] uppercase tracking-wide text-brand/70 border border-brand/10"
                  >
                    {subject}
                  </span>
                ))}

              {displaySubjects.length > 5 && (
                <span className="rounded-full bg-line/40 px-2.5 py-1 text-[0.65rem] uppercase tracking-wide text-ink-soft">
                  +{displaySubjects.length - 5}
                </span>
              )}
            </div>
          )}

          {/* Description */}
          <div className="mt-8 border-t border-line pt-8">
            <p className="text-[0.95rem] leading-relaxed text-ink-soft whitespace-pre-line">
              {displayDescription}
            </p>
          </div>

          {/* Actions */}
          <BookCapabilities book={book} showUnavailable />
          <BookSelectButton book={book} />
          <div className="mt-8 flex flex-wrap gap-3">

            {action === 'SIGN_IN' ? (

              <button
                onClick={() => navigate('/login')}
                className="font-display rounded-sm bg-brand px-6 py-2.5 text-[0.75rem] tracking-wide text-paper transition-all hover:bg-brand-dark"
              >
                SIGN IN TO BORROW OR RESERVE
              </button>

            ) : action === 'BORROWED' ? (

              <Link
                to="/profile"
                className="font-display rounded-sm bg-brand/10 border border-brand/30 px-6 py-2.5 text-[0.75rem] tracking-wide text-brand transition-all hover:bg-brand/20 flex items-center justify-center"
              >
                BORROWED — VIEW IN MY LIBRARY
              </Link>

            ) : action === 'RESERVED' ? (

              <Link
                to="/profile"
                className="font-display rounded-sm border border-line px-6 py-2.5 text-[0.75rem] tracking-wide text-ink-soft transition-all hover:text-ink flex items-center justify-center"
              >
                RESERVED — VIEW IN MY LIBRARY
              </Link>

            ) : action === 'BORROW' ? (

              <button
                onClick={handleBorrow}
                disabled={actionLoading}
                className="font-display rounded-sm bg-brand px-6 py-2.5 text-[0.75rem] tracking-wide text-paper transition-all hover:bg-brand-dark disabled:opacity-50 flex items-center justify-center"
              >
                {actionLoading
                  ? 'PROCESSING...'
                  : 'BORROW'}
              </button>

            ) : (

              <button
                onClick={handleReserve}
                disabled={actionLoading}
                className="font-display rounded-sm border border-brand px-6 py-2.5 text-[0.75rem] tracking-wide text-brand transition-all hover:bg-brand/5 disabled:opacity-50 flex items-center justify-center"
              >
                {actionLoading
                  ? 'PROCESSING...'
                  : 'RESERVE'}
              </button>

            )}

            <button
              onClick={() => {
                toggleList(stringId)

                showToast(
                  inList
                    ? `Removed "${displayTitle}" from list`
                    : `Added "${displayTitle}" to list`,
                  inList
                    ? 'info'
                    : 'success',
                )
              }}
              className={`font-display rounded-sm border px-6 py-2.5 text-[0.75rem] tracking-wide transition-colors ${
                inList
                  ? 'border-brand bg-brand/10 text-brand'
                  : 'border-line text-ink-soft hover:border-brand hover:text-brand'
              }`}
            >
              {inList
                ? 'In Reading List ✓'
                : 'Add to Reading List'}
            </button>

          </div>
        </div>
      </div>
    </section>
  )
}
