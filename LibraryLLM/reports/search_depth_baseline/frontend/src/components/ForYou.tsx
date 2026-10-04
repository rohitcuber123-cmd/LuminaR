import { useEffect, useState, useRef, useCallback } from 'react'
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
  getToken,
  type Recommendation,
  type BackendBook,
} from '@/lib/api'
import { PALETTES, type CoverVariant } from '@/data/books'
import { useLibraryStore } from '@/store/useLibraryStore'
import { useInView } from '@/lib/useInView'
import { showToast } from '@/components/Toast'
import { useBookActionState } from '@/hooks/useBookActionState'
import { ChevronRight } from 'lucide-react'

const REFRESH_INTERVAL = 5 * 60 * 1000 // 5 minutes
const RECOMMENDATION_LIMIT = 12

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
  const [books, setBooks] = useState<BackendBook[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const refreshIntervalRef = useRef<number | null>(null)
  const isMountedRef = useRef(true)
  const lastFetchRef = useRef<number>(0)

  const fetchRecommendations = useCallback(async (isRefresh = false) => {
    // Prevent duplicate rapid requests
    const now = Date.now()
    if (now - lastFetchRef.current < 1000) {
      console.log('[ForYou] Skipping duplicate request (too soon)')
      return
    }
    lastFetchRef.current = now

    if (isRefresh) {
      console.log('[ForYou] Refreshing recommendations')
      setIsRefreshing(true)
    } else {
      console.log('[ForYou] Fetching initial recommendations')
      setLoading(true)
    }

    try {
      setError(false)

      const token = getToken()

      // Try to get personalized recommendations if authenticated
      if (token) {
        try {
          console.log('[ForYou] Requesting personalized recommendations (limit: 12)')
          const response = await getRecommendations(RECOMMENDATION_LIMIT)
          
          if (!isMountedRef.current) return

          if (response.recommendations && response.recommendations.length > 0) {
            console.log(`[ForYou] Received ${response.recommendations.length} personalized recommendations`)
            let converted = response.recommendations.map(recommendationToBackendBook)
            converted = deduplicateBooks(converted)
            console.log(`[ForYou] After deduplication: ${converted.length} books`)
            setBooks(converted)
            setLoading(false)
            setIsRefreshing(false)
            return
          } else {
            console.log('[ForYou] Empty recommendation response, falling back to popular books')
          }
        } catch (err: any) {
          console.error('[ForYou] Recommendation API error:', err?.message || err)
          console.log('[ForYou] Falling back to popular books')
        }
      } else {
        console.log('[ForYou] User not authenticated, using popular books')
      }

      // Fallback to popular books
      if (!isMountedRef.current) return
      
      console.log('[ForYou] Fetching popular books fallback')
      const popularResponse = await getPopularBooks(RECOMMENDATION_LIMIT)
      
      if (isMountedRef.current) {
        console.log(`[ForYou] Received ${popularResponse.length} popular books`)
        const deduplicated = deduplicateBooks(popularResponse)
        setBooks(deduplicated)
      }
    } catch (err) {
      console.error('[ForYou] Failed to fetch recommendations and fallback:', err)
      if (isMountedRef.current) {
        setError(true)
      }
    } finally {
      if (isMountedRef.current) {
        setLoading(false)
        setIsRefreshing(false)
      }
    }
  }, [])

  useEffect(() => {
    isMountedRef.current = true

    // Initial fetch
    fetchRecommendations(false)

    // Set up refresh interval
    refreshIntervalRef.current = window.setInterval(() => {
      console.log('[ForYou] Auto-refresh triggered')
      fetchRecommendations(true)
    }, REFRESH_INTERVAL)

    return () => {
      isMountedRef.current = false
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current)
        refreshIntervalRef.current = null
      }
    }
  }, [fetchRecommendations])

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
            {Array.from({ length: 12 }).map((_, i) => (
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

  if (error || books.length === 0) {
    return null // Don't show section if no recommendations
  }

  return (
    <section 
      className="border-t border-line bg-panel py-16 md:py-20"
      style={{
        opacity: isRefreshing ? 0.7 : 1,
        transition: 'opacity 300ms ease-out'
      }}
    >
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

        <BookCarousel>
          {books.map((book, i) => (
            <ForYouCard key={`${book.work_id}-${i}`} book={book} index={i} />
          ))}
        </BookCarousel>
      </div>
    </section>
  )
}

