import { useAuthStore } from '../store/useAuthStore'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { BookCover } from '@/components/BookCover'
import { BookSelectButton } from '@/components/BookSelectButton'
import { BookDiscoveryMenu } from '@/components/BookDiscoveryMenu'
import { BookCarousel } from '@/components/BookCarousel'
import {
  getRecommendations,
  getPopularBooks,
  issueBook,
  reserveBook,
  type Recommendation,
  type BackendBook,
} from '@/lib/api'
import { PALETTES, type CoverVariant } from '@/data/books'
import { useLibraryStore } from '@/store/useLibraryStore'
import { useInView } from '@/lib/useInView'
import { showToast } from '@/components/Toast'
import { useBookActionState } from '@/hooks/useBookActionState'
import { ChevronRight } from 'lucide-react'

const RECOMMENDATION_LIMIT = 10

// Convert Recommendation to BackendBook format for compatibility
function recommendationToBackendBook(rec: Recommendation): BackendBook {
  return {
    book_id: rec.book_id || 0,
    work_id: rec.work_id,
    title: rec.title || 'Unknown Title',
    authors: rec.authors || 'Unknown Author',
    subjects: rec.subjects || '',
    description: null,
    average_rating: rec.average_rating || 0,
    rating_count: 0,
    reading_log_count: 0,
    shelf_location: rec.shelf_location || null,
    total_copies: rec.total_copies || 0,
    available_copies: rec.available_copies || 0,
    created_at: '',
  }
}

// Deduplicate by work_id
function deduplicateBooks(books: BackendBook[]): BackendBook[] {
  const seen = new Set<string>()
  return books.filter(book => {
    if (seen.has(book.work_id)) {
      return false
    }
    seen.add(book.work_id)
    return true
  })
}

function ForYouCard({
  book,
  index,
}: {
  book: BackendBook
  index: number
}) {
  const { ref, inView } = useInView<HTMLDivElement>()
  const navigate = useNavigate()
  const { fetchUserData } = useLibraryStore()

  const stringId = book.work_id

  const { action, adjustedAvailable } = useBookActionState(book)
  const [actionLoading, setActionLoading] = useState(false)

  const handleAction = async (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()

    if (action === 'SIGN_IN') {
      navigate('/login')
      return
    }

    if (action === 'BORROWED' || action === 'RESERVED') {
      navigate('/profile')
      return
    }

    try {
      setActionLoading(true)
      if (action === 'BORROW') {
        await issueBook(stringId)
        showToast(`Successfully borrowed "${book.title}"`, 'success')
      } else if (action === 'RESERVE') {
        await reserveBook(stringId)
        showToast(`Reserved "${book.title}"`, 'success')
      }
      await fetchUserData()
    } catch (err: any) {
      showToast(err.message || `Failed to ${action.toLowerCase()} book.`, 'warning')
    } finally {
      setActionLoading(false)
    }
  }

  const availability =
    adjustedAvailable === 0
      ? 'All copies on loan'
      : adjustedAvailable === book.total_copies
        ? 'Available now'
        : `${adjustedAvailable} of ${book.total_copies} available`

  const paletteIndex = book.book_id % PALETTES.length
  const variants: CoverVariant[] = ['circle', 'ring', 'split', 'stripe']
  const variantIndex = book.book_id % variants.length

  const actionText = {
    'BORROW': 'Borrow',
    'RESERVE': 'Reserve',
    'BORROWED': 'Borrowed',
    'RESERVED': 'Reserved',
    'SIGN_IN': 'Sign in',
  }[action] || 'Borrow'

  return (
    <div
      ref={ref}
      className="group relative flex-shrink-0 w-[180px] flex flex-col transition-opacity duration-300"
      style={{
        opacity: inView ? 1 : 0,
        transitionDelay: `${Math.min(index * 50, 300)}ms`,
      }}
    >
      <Link
        to={`/book/${stringId}`}
        className="block flex-1 flex flex-col"
      >
        <div className="mb-4 transform transition-transform duration-300 group-hover:-translate-y-2 group-hover:scale-[1.02]">
          <BookCover
            title={book.title}
            author={book.authors}
            paletteIndex={paletteIndex}
            variant={variants[variantIndex]}
            className="shadow-[0_12px_32px_rgba(0,0,0,0.12)] group-hover:shadow-[0_18px_40px_rgba(0,0,0,0.18)]"
          />
        </div>

        <div className="space-y-2 flex-1">
          <h3 className="line-clamp-2 min-h-[2.5rem] text-sm font-medium leading-snug text-ink transition-colors group-hover:text-brand">
            {book.title}
          </h3>

          <p className="text-xs text-ink-soft line-clamp-2 min-h-[2rem]">
            {book.authors}
          </p>

          <p className="text-xs text-ink-soft">
            {availability}
          </p>
        </div>
      </Link>

      <BookSelectButton book={book} />
        <BookDiscoveryMenu workId={book.work_id} />

      <button
        onClick={handleAction}
        disabled={actionLoading}
        className={`mt-3 w-full rounded-md px-4 py-2 text-xs font-medium transition-all duration-200 ${
          action === 'BORROW'
            ? 'bg-brand text-paper hover:bg-brand-dark'
            : action === 'RESERVE'
              ? 'bg-ink-soft text-paper hover:bg-ink'
              : action === 'BORROWED' || action === 'RESERVED'
                ? 'bg-line text-ink-soft cursor-default'
                : 'bg-brand text-paper hover:bg-brand-dark'
        } ${actionLoading ? 'opacity-50 cursor-wait' : ''}`}
      >
        {actionLoading ? 'Loading...' : actionText}
      </button>
    </div>
  )
}

export function ForYou({ showViewAll = true }: { showViewAll?: boolean }) {
  const token = useAuthStore(state => state.token)
  const [page, setPage] = useState({ token, offset: 0 })
  const offset = page.token === token ? page.offset : 0
  const [books, setBooks] = useState<BackendBook[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [popular, setPopular] = useState(false)
  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true); setError(false)
      try {
        if (token) {
          try {
            const response = await getRecommendations(RECOMMENDATION_LIMIT, offset)
            if (cancelled) return
            if (response.recommendations.length || offset > 0) {
              setBooks(deduplicateBooks(response.recommendations.map(recommendationToBackendBook)))
              setHasMore(response.has_more === true); setPopular(false)
              return
            }
          } catch (failure) { if (offset > 0) throw failure }
        }
        const fallback = await getPopularBooks(RECOMMENDATION_LIMIT)
        if (!cancelled) { setBooks(deduplicateBooks(fallback)); setHasMore(false); setPopular(true) }
      } catch { if (!cancelled) { setError(true); setBooks([]); setHasMore(false) } }
      finally { if (!cancelled) setLoading(false) }
    }
    void load()
    return () => { cancelled = true }
  }, [token, offset])
  function goToPage(next: number) {
    setPage({ token, offset: next })
    document.getElementById('for-you-results')?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }

  if (loading) {
    return (
      <section className="border-t border-line bg-panel py-16 md:py-20">
        <div className="mx-auto max-w-screen-2xl px-6 md:px-12">
          <div className="mb-10 flex items-center justify-between">
            <h2 className="font-display text-[0.8rem] tracking-[0.25em] text-ink-soft">
              FOR YOU
            </h2>
          </div>

          <BookCarousel>
            {Array.from({ length: RECOMMENDATION_LIMIT }).map((_, i) => (
              <div key={i} className="flex-shrink-0 w-[180px] animate-pulse">
                <div className="mb-4 aspect-[2/3] rounded-[2px] bg-line/60" />
                <div className="space-y-2">
                  <div className="h-4 w-3/4 rounded bg-line" />
                  <div className="h-3 w-1/2 rounded bg-line/60" />
                  <div className="h-3 w-2/3 rounded bg-line/40" />
                </div>
              </div>
            ))}
          </BookCarousel>
        </div>
      </section>
    )
  }

  if ((error || books.length === 0) && offset === 0) {
    return null // Don't show section if no recommendations
  }

  return (
    <section id="for-you-results" className="border-t border-line bg-panel py-16 md:py-20">
      <div className="mx-auto max-w-screen-2xl px-6 md:px-12">
        <div className="mb-10 flex items-center justify-between">
          <h2 className="font-display text-[0.8rem] tracking-[0.25em] text-ink-soft">
            FOR YOU
          </h2>

          {showViewAll && (
            <Link
              to="/catalog"
              className="group flex items-center gap-1 text-xs font-medium text-ink-soft transition-colors hover:text-brand"
            >
              VIEW ALL
              <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
          )}
        </div>

        <div className="mb-6 flex flex-wrap items-center justify-between gap-4 text-xs text-ink-soft">
          <p>{popular ? 'Popular books' : books.length ? `Recommendations ${offset + 1}–${offset + books.length}` : error ? 'Recommendations could not be loaded. Try Previous.' : 'No further recommendations.'}</p>
          {!popular && <nav aria-label="Recommendation pagination" className="flex gap-3">
            <button className="assistant-button disabled:opacity-40" disabled={offset === 0} onClick={() => goToPage(Math.max(0, offset - RECOMMENDATION_LIMIT))}>Previous</button>
            <button className="assistant-button disabled:opacity-40" disabled={!hasMore || error} onClick={() => goToPage(offset + RECOMMENDATION_LIMIT)}>Next Recommendations</button>
          </nav>}
        </div>
        <BookCarousel>
          {books.map((book, i) => (
            <ForYouCard key={`${book.work_id}-${i}`} book={book} index={i} />
          ))}
        </BookCarousel>
      </div>
    </section>
  )
}

