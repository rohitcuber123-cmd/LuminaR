import { searchPaging, changeSearchContext, SEARCH_PAGE_SIZE } from '../lib/searchPaging'
import { useState, useEffect } from 'react'
import { Link, useSearchParams, useNavigate } from 'react-router-dom'
import { Search, AlertCircle, BookOpen, ArrowLeft } from 'lucide-react'
import { BookCover } from '@/components/BookCover'
import { BookSelectButton } from '@/components/BookSelectButton'
import { BookDiscoveryMenu } from '@/components/BookDiscoveryMenu'
import { useAssistantPageContext } from '@/hooks/useAssistantPageContext'
import { BookCapabilities } from '@/components/BookCapabilities'
import { PALETTES, type CoverVariant } from '@/data/books'
import { useLibraryStore } from '@/store/useLibraryStore'
import { showToast } from '@/components/Toast'
import { searchBooks, issueBook, reserveBook, type SearchResult, type BackendBook } from '@/lib/api'
import { useBookActionState } from '@/hooks/useBookActionState'
import { useInView } from '@/lib/useInView'

// Convert SearchResult to BackendBook-like structure for compatibility
function searchResultToBook(result: SearchResult): BackendBook {
  // CRITICAL: Preserve available_copies from search result
  // Do NOT default to 0 if the value exists
  const availableCopies = typeof result.available_physical_copies === 'number' 
    ? result.available_physical_copies 
    : 0
  
  const totalCopies = typeof result.physical_copies === 'number'
    ? result.physical_copies
    : 0

  return {
    book_id: 0, // not provided by search
    work_id: result.work_id || '',
    title: result.title || '', // Backend enrichment should provide title
    authors: result.authors || 'Unknown Author', // Keep fallback for authors
    subjects: result.subjects || '',
    description: null,
    average_rating: result.rating || 0,
    rating_count: result.rating_count || 0,
    reading_log_count: result.read_logs || 0,
    shelf_location: result.shelf_location || null,
    total_copies: totalCopies,
    available_copies: availableCopies,
    created_at: '',
    readable: result.readable,
    rag_available: result.rag_available,
  }
}

function SearchResultCard({ result, index }: { result: SearchResult; index: number }) {
  const navigate = useNavigate()
  const { ref, inView } = useInView<HTMLDivElement>()
  const { toggleList, isInList, fetchUserData } = useLibraryStore()

  const workId = result.work_id || ''
  const inList = isInList(workId)
  
  // Convert search result to book format for action state hook
  const book = searchResultToBook(result)
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
        await issueBook(workId)
        showToast(`Successfully borrowed "${result.title}"`, 'success')
      } else if (action === 'RESERVE') {
        await reserveBook(workId)
        showToast(`Reserved "${result.title}"`, 'success')
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
      ? 'Check availability'
      : adjustedAvailable === 1
        ? '1 copy available'
        : `${adjustedAvailable} copies available`

  // Generate stable UI elements (using a hash of work_id for consistency)
  const hashCode = (str: string) => {
    let hash = 0
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i)
      hash = (hash << 5) - hash + char
      hash = hash & hash
    }
    return Math.abs(hash)
  }

  const idHash = hashCode(workId)
  const paletteIndex = idHash % PALETTES.length
  const variants: CoverVariant[] = ['circle', 'ring', 'split', 'stripe']
  const variant = variants[idHash % variants.length]
  
  const displayCategory = result.subjects ? result.subjects.split(',')[0].trim() : 'Book'
  const displayAuthor = result.authors || 'Unknown Author'
  const displayTitle = result.title || 'Unknown Title'

  return (
    <div
      ref={ref}
      className={`group reveal-up ${inView ? 'is-visible' : ''}`}
      style={{ transitionDelay: `${(index % 4) * 90}ms` }}
    >
      <Link to={`/book/${workId}`}>
        <p className="mb-3 truncate text-[0.68rem] uppercase tracking-wide text-ink-soft" title={displayCategory}>
          {displayCategory}
        </p>
        <div className="relative overflow-hidden rounded-[2px]">
          <BookCover
            title={displayTitle}
            author={displayAuthor}
            paletteIndex={paletteIndex}
            variant={variant}
            className="transition-transform duration-300 group-hover:-translate-y-1 group-hover:scale-[1.03]"
          />
        </div>
      </Link>

      <div className="mt-4">
        <Link to={`/book/${workId}`}>
          <p className="font-display line-clamp-2 text-[0.95rem] leading-tight text-ink" title={displayTitle}>
            {displayTitle}
          </p>
          <p className="mt-1 truncate text-[0.8rem] text-ink-soft" title={displayAuthor}>
            {displayAuthor}
          </p>
        </Link>
        
        {/* Rating if available */}
        {result.rating !== undefined && result.rating !== null && result.rating > 0 && (
          <div className="mt-1.5 flex items-center gap-1.5">
            <div className="flex items-center gap-0.5">
              <span className="text-[0.75rem] text-brand">★</span>
              <span className="text-[0.72rem] font-medium text-ink">
                {result.rating.toFixed(1)}
              </span>
            </div>
            {result.rating_count !== undefined && result.rating_count !== null && result.rating_count > 0 && (
              <span className="text-[0.68rem] text-ink-soft">
                ({result.rating_count.toLocaleString()})
              </span>
            )}
          </div>
        )}
        
        <p className={`mt-2 text-[0.72rem] font-medium ${adjustedAvailable === 0 ? 'text-ink-soft/70' : 'text-moss'}`}>
          {availability}
        </p>

        <BookCapabilities book={book} />
        <BookSelectButton book={book} />
        <BookDiscoveryMenu workId={book.work_id} />
        <div className="mt-3 flex gap-2">
          <button
            onClick={handleAction}
            className="font-display rounded-sm bg-brand px-3 py-1.5 text-[0.62rem] tracking-wide text-paper transition-opacity hover:bg-brand-dark flex items-center justify-center"
          >
            {actionLoading
              ? 'PROCESSING...'
              : action === 'BORROW'
                ? 'BORROW'
                : action === 'RESERVE'
                  ? 'RESERVE'
                  : action === 'BORROWED'
                    ? 'BORROWED ✓'
                    : action === 'RESERVED'
                      ? 'RESERVED ✓'
                      : 'SIGN IN'}
          </button>
          <button
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              toggleList(workId)
              showToast(
                inList ? `Removed "${displayTitle}" from list` : `Added "${displayTitle}" to list`,
                inList ? 'info' : 'success',
              )
            }}
            className={`font-display rounded-sm border px-3 py-1.5 text-[0.62rem] tracking-wide transition-colors ${
              inList ? 'border-brand bg-brand/10 text-brand' : 'border-line text-ink-soft hover:border-brand hover:text-brand'
            }`}
          >
            {inList ? 'In List ✓' : 'Add to List'}
          </button>
        </div>
      </div>
    </div>
  )
}

// Skeleton loader
function SearchSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-x-6 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: SEARCH_PAGE_SIZE }).map((_, i) => (
        <div key={i} className="animate-pulse">
          <div className="mb-3 h-3 w-1/2 rounded bg-line" />
          <div className="aspect-[2/3] w-full rounded-[2px] bg-line/60" />
          <div className="mt-4 space-y-2">
            <div className="h-4 w-3/4 rounded bg-line" />
            <div className="h-3 w-1/2 rounded bg-line/60" />
            <div className="mt-2 h-3 w-1/3 rounded bg-line/40" />
          </div>
        </div>
      ))}
    </div>
  )
}

export function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  
  const { query, offset, library, available } = searchPaging(searchParams)
  
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  useAssistantPageContext({ work_ids: loading ? [] : results.flatMap(result => result.work_id ? [result.work_id] : []).slice(0, 4) })
  const [error, setError] = useState('')
  const [searchMeta, setSearchMeta] = useState<{
    system?: string
    timing_ms?: any
    has_more?: boolean
    next_offset?: number | null
  } | null>(null)

  useEffect(() => {
    if (!query.trim()) {
      setResults([])
      setError('')
      return
    }

    let isMounted = true
    const currentQuery = query // Capture query for this request

    async function performSearch() {
      try {
        setLoading(true)
        setError('')
        
        console.log('[Search] Searching for:', currentQuery)
        
        const response = await searchBooks(
          currentQuery,
          SEARCH_PAGE_SIZE,
          library,
          available,
          offset === 0,
          offset
        )
        
        // Prevent stale results: only update if this is still the active query
        if (isMounted && currentQuery === query) {
          console.log('[Search] Results received:', response.results?.length || 0)
          
          // Filter out results with missing critical data
          const validResults = (response.results || []).filter(r => {
            if (!r.title || !r.authors) {
              console.warn('[Search] Result missing metadata:', r.work_id, {
                title: r.title,
                authors: r.authors
              })
            }
            return r.work_id && r.title // Require at least work_id and title
          })
          
          if (validResults.length < (response.results?.length || 0)) {
            console.warn('[Search] Filtered out', 
              (response.results?.length || 0) - validResults.length, 
              'results with incomplete metadata'
            )
          }
          
          setResults(validResults)
          setSearchMeta({
            system: response.system,
            timing_ms: response.timing_ms,
            has_more: response.has_more,
            next_offset: response.next_offset,
          })
        } else if (!isMounted) {
          console.log('[Search] Component unmounted, ignoring results')
        } else {
          console.log('[Search] Stale results ignored. Current query:', query, 'Result query:', currentQuery)
        }
      } catch (err: any) {
        if (isMounted && currentQuery === query) {
          console.error('Search error:', err)
          if (err.message.includes('session has expired') || err.message.includes('Not authenticated')) {
            setError('Please sign in to use search.')
          } else if (err.message.includes('Search is temporarily unavailable') || err.message.includes('ECONNREFUSED')) {
            setError('Search is temporarily unavailable. Please try again later.')
          } else {
            setError(err.message || 'Search failed. Please try again.')
          }
        }
      } finally {
        if (isMounted && currentQuery === query) {
          setLoading(false)
        }
      }
    }

    performSearch()

    return () => {
      isMounted = false
    }
  }, [query, offset, library, available])

  function goToPage(nextOffset: number) {
    const next = new URLSearchParams(searchParams)
    next.set('offset', String(nextOffset))
    setSearchParams(next)
    document.getElementById('search-results')?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  }
  const hasQuery = query.trim().length > 0

  return (
    <section id="search-results" className="mx-auto max-w-[90rem] px-6 py-10 md:px-10 md:py-16">
      {/* Back button */}
      <Link
        to="/"
        className="mb-6 inline-flex items-center gap-2 text-[0.8rem] text-ink-soft transition-colors hover:text-brand"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Back to Home
      </Link>

      {/* Page header */}
      <div className="mb-10 border-b border-line pb-6">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand/10 text-brand">
            <Search className="h-5 w-5" />
          </div>
          <div className="flex-1">
            <h1 className="font-display text-[clamp(1.8rem,4vw,2.6rem)] text-ink">
              {hasQuery ? 'Search Results' : 'Search'}
            </h1>
            {hasQuery && (
              <p className="mt-2 text-sm text-ink-soft">
                Results for <span className="font-medium text-ink">"{query}"</span>
              </p>
            )}
            {!hasQuery && (
              <p className="mt-2 text-sm text-ink-soft">
          Enter a search query to find books using AI-powered semantic search
              </p>
            )}
          </div>
        </div>
      </div>

      {hasQuery && <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <label className="flex items-center gap-2 text-sm text-ink-soft">
          <input type="checkbox" checked={available} onChange={e => setSearchParams(changeSearchContext(searchParams, { available: String(e.target.checked) }))} />
          Available now
        </label>
        <nav aria-label="Search results pagination" className="flex items-center gap-3 text-sm">
          <button disabled={loading || offset === 0} onClick={() => goToPage(Math.max(0, offset - SEARCH_PAGE_SIZE))} className="assistant-button disabled:opacity-40">Previous</button>
          <button disabled={loading || !!error || !searchMeta?.has_more} onClick={() => goToPage(searchMeta?.next_offset ?? offset + SEARCH_PAGE_SIZE)} className="assistant-button disabled:opacity-40">Next Results</button>
        </nav>
      </div>}
      {/* Search info badge */}
      {searchMeta?.system && (
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-brand/20 bg-brand/5 px-3 py-1.5 text-[0.7rem] text-ink-soft">
          <BookOpen className="h-3 w-3 text-brand" />
          <span>
            Powered by {searchMeta.system} AI Search
            {searchMeta.timing_ms?.total && (
              <span className="ml-1.5 text-ink-soft/60">
                • {searchMeta.timing_ms.total.toFixed(0)}ms
              </span>
            )}
          </span>
        </div>
      )}

      {/* Results area */}
      {error ? (
        <div className="py-20 text-center flex flex-col items-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-brand/10 mb-4">
            <AlertCircle className="h-6 w-6 text-brand" />
          </div>
          <p className="font-display text-xl text-ink">{error}</p>
          <button 
            onClick={() => window.location.reload()}
            className="mt-6 rounded-md bg-brand px-5 py-2 text-sm font-medium text-paper transition-colors hover:bg-brand-dark"
          >
            Retry
          </button>
        </div>
      ) : !hasQuery ? (
        <div className="py-20 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-panel">
            <Search className="h-8 w-8 text-ink-soft" />
          </div>
          <p className="mt-6 font-display text-xl text-ink">Start your search</p>
          <p className="mt-2 text-sm text-ink-soft">
            Use the search bar above to find books by title, author, subject, or description
          </p>
        </div>
      ) : loading ? (
        <SearchSkeleton />
      ) : results.length > 0 ? (
        <>
          <p className="mb-6 text-[0.78rem] text-ink-soft">
            Results {offset + 1}–{offset + results.length}
          </p>

          <div className="grid grid-cols-1 gap-x-6 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
            {results.map((result, i) => (
              <SearchResultCard key={result.work_id || i} result={result} index={i} />
            ))}
          </div>
        </>
      ) : (
        <div className="py-20 text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-panel">
            <Search className="h-8 w-8 text-ink-soft" />
          </div>
          <p className="mt-6 font-display text-xl text-ink">No results found</p>
          <p className="mt-2 text-sm text-ink-soft">
            No books matched "<span className="font-medium">{query}</span>". Try a different search term.
          </p>
        </div>
      )}
    </section>
  )
}
