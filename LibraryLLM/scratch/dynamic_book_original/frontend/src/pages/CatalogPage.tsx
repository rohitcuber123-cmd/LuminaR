import { useState, useEffect, useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Search, X, AlertCircle, ChevronLeft, ChevronRight } from 'lucide-react'
import { BookCover } from '@/components/BookCover'
import { ForYou } from '@/components/ForYou'
import { CATEGORIES } from '@/data/categories'
import { PALETTES, type CoverVariant } from '@/data/books'
import { useLibraryStore } from '@/store/useLibraryStore'
import { useInView } from '@/lib/useInView'
import { showToast } from '@/components/Toast'
import { getBooks, searchBooks, issueBook, reserveBook, type BackendBook, type SearchResult } from '@/lib/api'
import { useBookActionState } from '@/hooks/useBookActionState'
import { useNavigate } from 'react-router-dom'

const ITEMS_PER_PAGE = 20
const SEARCH_DEBOUNCE_MS = 400

// Convert SearchResult to BackendBook format
function searchResultToBook(result: SearchResult): BackendBook {
  return {
    book_id: 0,
    work_id: result.work_id || '',
    title: result.title || 'Unknown Title',
    authors: result.authors || 'Unknown Author',
    subjects: result.subjects || '',
    description: null,
    average_rating: result.rating || 0,
    rating_count: result.rating_count || 0,
    reading_log_count: result.read_logs || 0,
    shelf_location: result.shelf_location || null,
    total_copies: result.physical_copies || 0,
    available_copies: result.available_physical_copies || 0,
    created_at: '',
  }
}

function CatalogBookCard({ book, index }: { book: BackendBook; index: number }) {
  const navigate = useNavigate()
  const { ref, inView } = useInView<HTMLDivElement>()
  const { toggleList, isInList, fetchUserData } = useLibraryStore()

  const stringId = book.work_id
  const inList = isInList(stringId)
  
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

  // Generate stable UI elements based on ID
  const paletteIndex = book.book_id % PALETTES.length
  const variants: CoverVariant[] = ['circle', 'ring', 'split', 'stripe']
  const variant = variants[book.book_id % variants.length]
  const displayCategory = book.subjects ? book.subjects.split(',')[0].trim() : 'Book'
  const displayAuthor = book.authors || 'Unknown Author'

  return (
    <div
      ref={ref}
      className={`group reveal-up ${inView ? 'is-visible' : ''}`}
      style={{ transitionDelay: `${(index % 4) * 90}ms` }}
    >
      <Link to={`/book/${book.work_id}`}>
        <p className="mb-3 truncate text-[0.68rem] uppercase tracking-wide text-ink-soft" title={displayCategory}>
          {displayCategory}
        </p>
        <div className="relative overflow-hidden rounded-[2px]">
          <BookCover
            title={book.title}
            author={displayAuthor}
            paletteIndex={paletteIndex}
            variant={variant}
            className="transition-transform duration-300 group-hover:-translate-y-1 group-hover:scale-[1.03]"
          />
        </div>
      </Link>

      <div className="mt-4">
        <Link to={`/book/${book.work_id}`}>
          <p className="font-display line-clamp-2 text-[0.95rem] leading-tight text-ink" title={book.title}>
            {book.title}
          </p>
          <p className="mt-1 truncate text-[0.8rem] text-ink-soft" title={displayAuthor}>
            {displayAuthor}
          </p>
        </Link>
        <p className={`mt-2 text-[0.72rem] font-medium ${adjustedAvailable === 0 ? 'text-ink-soft/70' : 'text-moss'}`}>
          {availability}
        </p>

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
            onClick={() => {
              toggleList(stringId)
              showToast(
                inList ? `Removed "${book.title}" from list` : `Added "${book.title}" to list`,
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

// Skeleton loader matching LuminaR theme
function CatalogSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-x-6 gap-y-12 sm:grid-cols-3 lg:grid-cols-4">
      {Array.from({ length: 8 }).map((_, i) => (
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



export function CatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  
  // URL state
  const pageParam = parseInt(searchParams.get('page') || '1', 10)
  const currentPage = isNaN(pageParam) || pageParam < 1 ? 1 : pageParam
  const categoryParam = searchParams.get('category') || 'All'

  // Local search input state
  const [searchInput, setSearchInput] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  // Data fetching state
  const [books, setBooks] = useState<BackendBook[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [isSearchMode, setIsSearchMode] = useState(false)

  // Debounce search input
  const debounceTimerRef = useRef<number | null>(null)

  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current)
    }

    debounceTimerRef.current = setTimeout(() => {
      setDebouncedSearch(searchInput.trim())
    }, SEARCH_DEBOUNCE_MS)

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current)
      }
    }
  }, [searchInput])

  // Fetch data (either search or normal catalog)
  useEffect(() => {
    let isMounted = true

    async function fetchData() {
      try {
        setLoading(true)
        setError('')
        
        const hasSearch = debouncedSearch.length > 0

        if (hasSearch) {
          // SEARCH MODE
          setIsSearchMode(true)
          
          try {
            const response = await searchBooks(
              debouncedSearch,
              50, // Get more results for search
              'LIB001',
              false, // Search all books
              true
            )
            
            if (isMounted) {
              let results = response.results.map(searchResultToBook)
              
              // Apply category filter if set
              if (categoryParam !== 'All') {
                results = results.filter(book => 
                  book.subjects && book.subjects.toLowerCase().includes(categoryParam.toLowerCase())
                )
              }
              
              setBooks(results)
              setTotalCount(results.length)
            }
          } catch (err: any) {
            if (isMounted) {
              console.error('Search error:', err)
              if (err.message.includes('session has expired') || err.message.includes('Not authenticated')) {
                setError('Please sign in to search the catalog.')
              } else {
                setError('Search temporarily unavailable. Please try again.')
              }
            }
          }
        } else {
          // NORMAL CATALOG MODE
          setIsSearchMode(false)
          
          const offset = (currentPage - 1) * ITEMS_PER_PAGE
          const response = await getBooks(ITEMS_PER_PAGE, offset)
          
          if (isMounted) {
            let results = response.results
            
            // Apply category filter if set
            if (categoryParam !== 'All') {
              // Note: This is client-side filtering since backend doesn't support it yet
              // In production, this should be moved to backend
              results = results.filter(book => 
                book.subjects && book.subjects.toLowerCase().includes(categoryParam.toLowerCase())
              )
            }
            
            setBooks(results)
            setTotalCount(categoryParam === 'All' ? response.count : results.length)
          }
        }
      } catch (err: any) {
        if (isMounted) {
          setError('Unable to load the catalog.')
        }
      } finally {
        if (isMounted) {
          setLoading(false)
        }
      }
    }

    fetchData()

    return () => {
      isMounted = false
    }
  }, [debouncedSearch, currentPage, categoryParam])

  const totalPages = Math.ceil(totalCount / ITEMS_PER_PAGE)

  function handlePageChange(newPage: number) {
    if (newPage < 1 || newPage > totalPages) return
    searchParams.set('page', newPage.toString())
    setSearchParams(searchParams)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function handleCategoryChange(category: string) {
    searchParams.set('category', category)
    searchParams.set('page', '1') // Reset to page 1
    setSearchParams(searchParams)
  }

  function clearSearch() {
    setSearchInput('')
    setDebouncedSearch('')
  }

  return (
    <section className="mx-auto max-w-[90rem] px-6 py-10 md:px-10 md:py-16">
      {/* Page header */}
      <div className="mb-10 border-b border-line pb-6">
        <h1 className="font-display text-[clamp(1.8rem,4vw,2.6rem)] text-ink">Catalog</h1>
        <p className="mt-2 text-sm text-ink-soft">
          {isSearchMode && debouncedSearch
            ? `Search results for "${debouncedSearch}"`
            : 'Browse our full collection — explore our latest catalog data.'}
        </p>
      </div>

      {/* Search bar */}
      <div className="mb-8 flex items-center gap-3 rounded-xl border border-line bg-panel px-4 py-3 transition-colors focus-within:border-brand">
        <Search className="h-4 w-4 shrink-0 text-ink-soft" />
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search by title, author, or subject..."
          className="w-full bg-transparent text-sm text-ink placeholder:text-ink-soft/60 focus:outline-none"
        />
        {searchInput && (
          <button onClick={clearSearch} className="text-ink-soft hover:text-ink transition-colors">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Personalized recommendations */}
      <div className="mb-12 -mx-6 md:-mx-10">
        <ForYou showViewAll={false} />
      </div>

      {/* Category filter */}
      <div className="mb-10">
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 text-[0.72rem] font-medium uppercase tracking-wider text-ink-soft">Category:</span>
          <button
            onClick={() => handleCategoryChange('All')}
            className={`font-display rounded-full px-3.5 py-1 text-[0.68rem] tracking-wide transition-colors ${
              categoryParam === 'All'
                ? 'bg-brand text-paper'
                : 'bg-panel text-ink-soft hover:bg-line'
            }`}
          >
            All
          </button>
          {CATEGORIES.map((cat) => (
            <button
              key={cat.name}
              onClick={() => handleCategoryChange(cat.name)}
              className={`font-display rounded-full px-3.5 py-1 text-[0.68rem] tracking-wide transition-colors ${
                categoryParam === cat.name
                  ? 'bg-brand text-paper'
                  : 'bg-panel text-ink-soft hover:bg-line'
              }`}
            >
              {cat.name}
            </button>
          ))}
        </div>
        
        {/* Note about format filters */}
        <p className="mt-4 text-[0.7rem] text-ink-soft/60 italic">
          Note: Format filtering (Book/eBook/Audiobook) requires database schema updates and is not yet available.
        </p>
      </div>

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
      ) : loading ? (
        <CatalogSkeleton />
      ) : books.length > 0 ? (
        <>
          <p className="mb-6 text-[0.78rem] text-ink-soft">
            {isSearchMode
              ? `Found ${books.length} ${books.length === 1 ? 'result' : 'results'}`
              : `Showing ${(currentPage - 1) * ITEMS_PER_PAGE + 1} - ${Math.min(currentPage * ITEMS_PER_PAGE, totalCount)} of ${totalCount} ${totalCount === 1 ? 'title' : 'titles'}`}
          </p>

          <div className="grid grid-cols-2 gap-x-6 gap-y-12 sm:grid-cols-3 lg:grid-cols-4">
            {books.map((book, i) => (
              <CatalogBookCard key={book.work_id || book.book_id} book={book} index={i} />
            ))}
          </div>

          {/* Pagination (only in normal mode) */}
          {!isSearchMode && totalPages > 1 && (
            <div className="mt-16 flex items-center justify-center gap-4 border-t border-line pt-8">
              <button
                onClick={() => handlePageChange(currentPage - 1)}
                disabled={currentPage === 1}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-line text-ink-soft transition-colors hover:border-ink hover:text-ink disabled:opacity-40 disabled:hover:border-line disabled:hover:text-ink-soft"
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              
              <span className="font-display text-sm text-ink-soft">
                Page <span className="text-ink">{currentPage}</span> of {totalPages}
              </span>

              <button
                onClick={() => handlePageChange(currentPage + 1)}
                disabled={currentPage === totalPages}
                className="flex h-9 w-9 items-center justify-center rounded-full border border-line text-ink-soft transition-colors hover:border-ink hover:text-ink disabled:opacity-40 disabled:hover:border-line disabled:hover:text-ink-soft"
                aria-label="Next page"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </>
      ) : (
        <div className="py-20 text-center">
          <p className="font-display text-xl text-ink-soft">No books found.</p>
          <p className="mt-2 text-sm text-ink-soft/70">
            {isSearchMode ? 'Try a different search term or clear filters.' : 'Check back later for new arrivals.'}
          </p>
        </div>
      )}
    </section>
  )
}