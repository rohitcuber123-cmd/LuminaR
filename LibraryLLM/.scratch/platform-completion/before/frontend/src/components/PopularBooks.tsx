import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getPopularBooks, type BackendBook } from '../lib/api'
import { globalBookPresentation } from '../lib/bookPresentation'
import { BookCard } from './BookCard'
import { useHomeCatalogue, displayToHomeBook, homeCataloguePath } from './HomeCatalogueContext'
export function PopularBooks() {
  const context = useHomeCatalogue()

  const [books, setBooks] =
    useState<BackendBook[]>([])

  const [loading, setLoading] =
    useState(true)

  const [error, setError] =
    useState(false)


  useEffect(() => {
    if (context) return
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

  }, [context])

  const discover = !!context && context.data.source.catalogue_source === 'LIBRARY_LOCAL' && context.data.popular.length < 4
  const visibleBooks = context ? (discover ? context.data.new_arrivals : context.data.popular).map(displayToHomeBook) : books
  const visibleLoading = context ? false : loading
  const visibleError = context ? false : error



  return (
    <section className="mx-auto max-w-[90rem] px-6 py-16 md:px-10 md:py-24">

      <div className="mb-10 flex items-end justify-between border-b border-line pb-6">

        <h2 className="font-display text-[clamp(1.6rem,3.4vw,2.3rem)] text-ink">
          {discover ? 'Discover More' : 'Popular Right Now'}
        </h2>

        <Link
          to={homeCataloguePath(context, discover ? 'catalogue' : 'popular')}
          className="font-display shrink-0 text-[0.75rem] tracking-wide text-brand hover:underline"
        >
          View all
        </Link>

      </div>


      {/* LOADING */}

      {visibleLoading && (

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

      {!visibleLoading &&
        visibleError && (

          <div className="py-12 text-center">

            <p className="text-sm text-ink-soft">
              Unable to load popular books.
            </p>

          </div>
        )}


      {/* EMPTY */}

      {!visibleLoading &&
        !visibleError &&
        visibleBooks.length === 0 && (

          <div className="py-12 text-center">

            <p className="text-sm text-ink-soft">
              No popular books available.
            </p>

          </div>
        )}


      {/* BOOKS */}

      {!visibleLoading &&
        !visibleError &&
        visibleBooks.length > 0 && (

          <div className="grid grid-cols-2 gap-x-6 gap-y-12 sm:grid-cols-3 lg:grid-cols-4">

            {visibleBooks.map(
              (book, index) => (

                <BookCard
                  key={book.work_id}
                  book={context ? (discover ? context.data.new_arrivals : context.data.popular)[index] : globalBookPresentation(book)}
                  changed={context?.changed}
                />

              )
            )}

          </div>
        )}

    </section>
  )
}
