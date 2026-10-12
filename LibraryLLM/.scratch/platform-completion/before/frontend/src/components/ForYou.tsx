import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { useAuthStore } from '../store/useAuthStore'
import { getRecommendations, getPopularBooks, type Recommendation, type BackendBook } from '../lib/api'
import { globalBookPresentation } from '../lib/bookPresentation'
import { BookCard } from './BookCard'
import { BookCarousel } from './BookCarousel'
import { useHomeCatalogue, displayToHomeBook, homeCataloguePath } from './HomeCatalogueContext'
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

export function ForYou({ showViewAll = true }: { showViewAll?: boolean }) {
  const context = useHomeCatalogue()
  const token = useAuthStore(state => state.token)
  const [page, setPage] = useState({ token, offset: 0 })
  const offset = page.token === token ? page.offset : 0
  const [books, setBooks] = useState<BackendBook[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [popular, setPopular] = useState(false)
  useEffect(() => {
    if (context) return
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
  }, [token, offset, context])
  function goToPage(next: number) {
    setPage({ token, offset: next })
    document.getElementById('for-you-results')?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }

  const visibleBooks = context ? (context.data.for_you || []).map(displayToHomeBook) : books
  const visibleLoading = context ? false : loading
  if (visibleLoading) {
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

  if (!context && (error || books.length === 0) && offset === 0) {
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
              to={homeCataloguePath(context, 'catalogue?view=for-you')}
              className="group flex items-center gap-1 text-xs font-medium text-ink-soft transition-colors hover:text-brand"
            >
              VIEW ALL
              <ChevronRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
            </Link>
          )}
        </div>

        <div className="mb-6 flex flex-wrap items-center justify-between gap-4 text-xs text-ink-soft">
          <p>{context ? context.data.source.catalogue_source === 'LIBRARY_LOCAL' ? 'Recommendations from your library’s collection' : 'Global Catalogue discoveries' : popular ? 'Popular books' : books.length ? `Recommendations ${offset + 1}–${offset + books.length}` : error ? 'Recommendations could not be loaded. Try Previous.' : 'No further recommendations.'}</p>
          {!context && !popular && <nav aria-label="Recommendation pagination" className="flex gap-3">
            <button className="assistant-button disabled:opacity-40" disabled={offset === 0} onClick={() => goToPage(Math.max(0, offset - RECOMMENDATION_LIMIT))}>Previous</button>
            <button className="assistant-button disabled:opacity-40" disabled={!hasMore || error} onClick={() => goToPage(offset + RECOMMENDATION_LIMIT)}>Next Recommendations</button>
          </nav>}
        </div>
        <BookCarousel>
          {visibleBooks.map((book, i) => (
            <BookCard key={`${book.work_id}-${i}`} book={context ? context.data.for_you![i] : globalBookPresentation(book)} changed={context?.changed} rail />
          ))}
        </BookCarousel>
      </div>
    </section>
  )
}

