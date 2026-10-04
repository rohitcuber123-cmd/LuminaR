import { useEffect, useState } from 'react'
import { Hero } from '@/components/Hero'
import { ForYou } from '@/components/ForYou'
import { PopularBooks } from '@/components/PopularBooks'
import { CategoryExplorer } from '@/components/CategoryExplorer'
import { AlsoLikeTicker } from '@/components/AlsoLikeTicker'
import { NewArrivals } from '@/components/NewArrivals'
import { getBooks, type BackendBook } from '@/lib/api'
import { AlertCircle, Loader2 } from 'lucide-react'


function HomeSkeleton() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center text-ink-soft">
      <Loader2 className="h-8 w-8 animate-spin text-brand" />

      <p className="mt-4 font-display text-sm uppercase tracking-widest">
        Loading Library...
      </p>
    </div>
  )
}


export function Home() {

  const [books, setBooks] =
    useState<BackendBook[]>([])

  const [loading, setLoading] =
    useState(true)

  const [error, setError] =
    useState(false)


  useEffect(() => {

    let cancelled = false


    async function loadHeroBooks() {

      try {

        setLoading(true)
        setError(false)

        /*
         * Only fetch a small number of books for the Hero
         * and AlsoLikeTicker.
         *
         * PopularBooks, CategoryExplorer and NewArrivals
         * fetch their own database-driven data.
         */
        const response =
          await getBooks(12, 0)


        if (!cancelled) {

          if (
            response &&
            response.results &&
            response.results.length > 0
          ) {

            setBooks(
              response.results
            )

          } else {

            setError(true)

          }

        }

      } catch (err) {

        console.error(
          'Failed to load Home books:',
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


    loadHeroBooks()


    return () => {

      cancelled = true

    }

  }, [])


  if (loading) {

    return <HomeSkeleton />

  }


  if (
    error ||
    books.length === 0
  ) {

    return (

      <div
        className="
          flex
          min-h-[70vh]
          flex-col
          items-center
          justify-center
          px-6
          text-center
          text-ink
        "
      >

        <div
          className="
            mb-4
            flex
            h-12
            w-12
            items-center
            justify-center
            rounded-2xl
            bg-brand/10
          "
        >

          <AlertCircle
            className="
              h-6
              w-6
              text-brand
            "
          />

        </div>


        <p
          className="
            font-display
            text-2xl
          "
        >
          Unable to load the library
        </p>


        <p
          className="
            mt-2
            max-w-md
            text-sm
            text-ink-soft
          "
        >
          We're having trouble connecting to
          the database. Please try again later.
        </p>


        <button
          onClick={() =>
            window.location.reload()
          }

          className="
            mt-6
            rounded-md
            bg-brand
            px-5
            py-2
            text-sm
            font-medium
            text-paper
            transition-colors
            hover:bg-brand-dark
          "
        >
          Retry Connection
        </button>

      </div>

    )

  }


  /*
   * Use one real database book for the
   * "You May Also Enjoy" section.
   */
  const spotlightBook =
    books[5] ?? books[0]


  return (

    <>

      {/* Hero uses real database books */}
      <Hero
        books={books}
      />


      {/* Personalized recommendations */}
      <ForYou />


      {/* Popular books fetch themselves */}
      <PopularBooks />


      {/* Categories fetch themselves */}
      <CategoryExplorer />


      {/* Real database spotlight book */}
      <AlsoLikeTicker
        spotlightBook={
          spotlightBook
        }
      />


      {/* New arrivals fetch themselves */}
      <NewArrivals />

    </>

  )

}