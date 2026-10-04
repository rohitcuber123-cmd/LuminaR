import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookCover } from '@/components/BookCover'
import {
  getNewArrivals,
  type BackendBook,
} from '@/lib/api'
import {
  PALETTES,
  type CoverVariant,
} from '@/data/books'
import { BookSelectButton } from '@/components/BookSelectButton'


export function NewArrivals() {

  const [books, setBooks] =
    useState<BackendBook[]>([])

  const [loading, setLoading] =
    useState(true)

  const [error, setError] =
    useState(false)


  useEffect(() => {

    let cancelled = false


    async function loadNewArrivals() {

      try {

        setLoading(true)
        setError(false)

        const results =
          await getNewArrivals(12)

        if (!cancelled) {

          setBooks(results)
        }

      } catch (err) {

        console.error(
          'Failed to load new arrivals:',
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


    loadNewArrivals()


    return () => {

      cancelled = true
    }

  }, [])


  return (
    <section
      id="new-arrivals"
      className="mx-auto max-w-[90rem] px-6 py-16 md:px-10 md:py-20"
    >

      <div className="mb-10 flex items-end justify-between border-b border-line pb-6">

        <h2 className="font-display text-[clamp(1.6rem,3.4vw,2.3rem)] text-ink">
          New Arrivals
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

        <div className="no-scrollbar flex gap-6 overflow-x-auto pb-2">

          {Array.from({
            length: 12,
          }).map((_, index) => (

            <div
              key={index}
              className="w-[150px] shrink-0 animate-pulse sm:w-[180px]"
            >

              <div className="aspect-[2/3] rounded-[2px] bg-line" />

              <div className="mt-3 h-4 w-4/5 rounded bg-line" />

              <div className="mt-2 h-3 w-3/5 rounded bg-line" />

            </div>

          ))}

        </div>
      )}


      {/* ERROR */}

      {!loading &&
        error && (

          <div className="py-12 text-center">

            <p className="text-sm text-ink-soft">
              Unable to load new arrivals.
            </p>

          </div>
        )}


      {/* EMPTY */}

      {!loading &&
        !error &&
        books.length === 0 && (

          <div className="py-12 text-center">

            <p className="text-sm text-ink-soft">
              No new arrivals available.
            </p>

          </div>
        )}


      {/* BOOKS */}

      {!loading &&
        !error &&
        books.length > 0 && (

          <div className="no-scrollbar flex gap-6 overflow-x-auto pb-2">

            {books.map((book) => {

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

              const displayAuthor =
                book.authors ||
                'Unknown Author'


              const displayDate =
                new Date(
                  book.created_at
                ).toLocaleDateString(
                  undefined,
                  {
                    month: 'short',
                    year: 'numeric',
                  }
                )


              return (
                <div
                  key={book.book_id}
                  className="w-[150px] shrink-0 sm:w-[180px]"
                >
                  <Link
                    to={`/book/${book.work_id}`}
                    className="group block"
                  >

                  <BookCover
                    title={book.title}
                    author={displayAuthor}
                    paletteIndex={paletteIndex}
                    variant={variant}
                    className="shadow-[0_4px_12px_rgba(0,0,0,0.08)] transition-transform duration-300 group-hover:-translate-y-1"
                  />


                  <p
                    className="font-display mt-3 truncate text-[0.85rem] leading-tight text-ink"
                    title={book.title}
                  >
                    {book.title}
                  </p>


                  <p className="mt-1 text-[0.72rem] text-ink-soft">
                    Added {displayDate}
                  </p>

                  </Link>

                  <BookSelectButton book={book} />

                </div>

              )
            })}

          </div>
        )}

    </section>
  )
}
