import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookCover } from '@/components/BookCover'
import {
  getPopularBooks,
  issueBook,
  reserveBook,
  type BackendBook,
} from '@/lib/api'
import { PALETTES, type CoverVariant } from '@/data/books'
import { useLibraryStore } from '@/store/useLibraryStore'
import { useInView } from '@/lib/useInView'
import { showToast } from '@/components/Toast'
import { useBookActionState } from '@/hooks/useBookActionState'
import { useNavigate } from 'react-router-dom'


function PopularBookCard({
  book,
  index,
}: {
  book: BackendBook
  index: number
}) {

  const {
    ref,
    inView,
  } = useInView<HTMLDivElement>()

  const navigate = useNavigate()

  const {
    toggleList,
    isInList,
    fetchUserData,
  } = useLibraryStore()


  const stringId =
    book.work_id

  const inList =
    isInList(stringId)

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
      : adjustedAvailable ===
        book.total_copies
        ? 'Available now'
        : `${adjustedAvailable} of ${book.total_copies} available`


  const paletteIndex =
    book.book_id %
    PALETTES.length

  const variants: CoverVariant[] = [
    'circle',
    'ring',
    'split',
    'stripe',
  ]

  const variant =
    variants[
    book.book_id %
    variants.length
    ]

  const displayCategory =
    book.subjects
      ? book.subjects
        .split('|')[0]
        .trim()
      : 'Book'

  const displayAuthor =
    book.authors ||
    'Unknown Author'


  return (
    <div
      ref={ref}
      className={`group reveal-up ${inView ? 'is-visible' : ''
        }`}
      style={{
        transitionDelay:
          `${(index % 4) * 90}ms`,
      }}
    >

      <Link
        to={`/book/${book.work_id}`}
      >

        <p
          className="mb-3 truncate text-[0.68rem] uppercase tracking-wide text-ink-soft"
          title={displayCategory}
        >
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


          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex translate-y-3 items-center justify-center gap-2 bg-gradient-to-t from-ink/85 to-transparent px-3 pb-3 pt-8 opacity-0 transition-all duration-300 group-hover:translate-y-0 group-hover:opacity-100">

            <span
              className="font-display pointer-events-auto cursor-pointer rounded-sm bg-brand px-3 py-1.5 text-[0.62rem] tracking-wide text-paper transition-opacity hover:opacity-90 flex items-center justify-center"
              onClick={handleAction}
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
            </span>


            <span
              className="font-display pointer-events-auto cursor-pointer rounded-sm border border-paper/70 px-3 py-1.5 text-[0.62rem] tracking-wide text-paper transition-opacity hover:opacity-90"
              onClick={(e) => {

                e.preventDefault()
                e.stopPropagation()

                toggleList(
                  stringId
                )

                showToast(
                  inList
                    ? `Removed "${book.title}" from list`
                    : `Added "${book.title}" to list`,
                  inList
                    ? 'info'
                    : 'success'
                )
              }}
            >
              {
                inList
                  ? 'In List ✓'
                  : 'Add to List'
              }
            </span>

          </div>

        </div>

      </Link>


      <Link
        to={`/book/${book.work_id}`}
      >

        <p
          className="font-display mt-4 truncate text-[0.95rem] leading-tight text-ink"
          title={book.title}
        >
          {book.title}
        </p>

        <p
          className="mt-1 truncate text-[0.8rem] text-ink-soft"
          title={displayAuthor}
        >
          {displayAuthor}
        </p>

      </Link>


      <p
        className={`mt-2 text-[0.72rem] font-medium ${adjustedAvailable === 0
            ? 'text-ink-soft/70'
            : 'text-moss'
          }`}
      >
        {availability}
      </p>

    </div>
  )
}


// ============================================================
// COMPONENT
// ============================================================

export function PopularBooks() {

  const [books, setBooks] =
    useState<BackendBook[]>([])

  const [loading, setLoading] =
    useState(true)

  const [error, setError] =
    useState(false)


  useEffect(() => {

    let cancelled = false


    async function loadPopularBooks() {

      try {

        setLoading(true)
        setError(false)

        const results =
          await getPopularBooks(12)

        if (!cancelled) {

          setBooks(results)
        }

      } catch (err) {

        console.error(
          'Failed to load popular books:',
          err
        )

        if (!cancelled) {

          setError(true)
        }

      } finally {

        if (!cancelled) {

          setLoading(false)
        }
      }
    }


    loadPopularBooks()


    return () => {

      cancelled = true
    }

  }, [])


  return (
    <section className="mx-auto max-w-[90rem] px-6 py-16 md:px-10 md:py-24">

      <div className="mb-10 flex items-end justify-between border-b border-line pb-6">

        <h2 className="font-display text-[clamp(1.6rem,3.4vw,2.3rem)] text-ink">
          Popular Right Now
        </h2>

        <Link
          to="/catalog"
          className="font-display shrink-0 text-[0.75rem] tracking-wide text-brand hover:underline"
        >
          View all
        </Link>

      </div>


      {/* LOADING */}

      {loading && (

        <div className="grid grid-cols-2 gap-x-6 gap-y-12 sm:grid-cols-3 lg:grid-cols-4">

          {Array.from({
            length: 12,
          }).map((_, index) => (

            <div
              key={index}
              className="animate-pulse"
            >

              <div className="mb-3 h-3 w-20 rounded bg-line" />

              <div className="aspect-[2/3] rounded-[2px] bg-line" />

              <div className="mt-4 h-4 w-4/5 rounded bg-line" />

              <div className="mt-2 h-3 w-3/5 rounded bg-line" />

              <div className="mt-2 h-3 w-2/5 rounded bg-line" />

            </div>

          ))}

        </div>
      )}


      {/* ERROR */}

      {!loading &&
        error && (

          <div className="py-12 text-center">

            <p className="text-sm text-ink-soft">
              Unable to load popular books.
            </p>

          </div>
        )}


      {/* EMPTY */}

      {!loading &&
        !error &&
        books.length === 0 && (

          <div className="py-12 text-center">

            <p className="text-sm text-ink-soft">
              No popular books available.
            </p>

          </div>
        )}


      {/* BOOKS */}

      {!loading &&
        !error &&
        books.length > 0 && (

          <div className="grid grid-cols-2 gap-x-6 gap-y-12 sm:grid-cols-3 lg:grid-cols-4">

            {books.map(
              (book, index) => (

                <PopularBookCard
                  key={book.book_id}
                  book={book}
                  index={index}
                />

              )
            )}

          </div>
        )}

    </section>
  )
}