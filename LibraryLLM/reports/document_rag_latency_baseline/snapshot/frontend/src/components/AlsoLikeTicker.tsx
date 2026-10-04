import { Link } from 'react-router-dom'
import { Sun } from 'lucide-react'
import { BookCover } from '@/components/BookCover'
import { type BackendBook } from '@/lib/api'
import { PALETTES, type CoverVariant } from '@/data/books'

interface AlsoLikeTickerProps {
  spotlightBook?: BackendBook
}

const TICKER_ITEMS = Array.from({ length: 6 })

export function AlsoLikeTicker({ spotlightBook }: AlsoLikeTickerProps) {
  if (!spotlightBook) return null

  const displayAuthor = spotlightBook.authors || 'Unknown Author'
  const displayCategory = spotlightBook.subjects ? spotlightBook.subjects.split('|')[0].trim() : 'Book'
  
  const paletteIndex = spotlightBook.book_id % PALETTES.length
  const variants: CoverVariant[] = ['circle', 'ring', 'split', 'stripe']
  const variant = variants[spotlightBook.book_id % variants.length]

  return (
    <section className="overflow-hidden border-t border-line py-16 md:py-20">
      <div className="marquee-wrap overflow-hidden">
        <div className="ticker-track flex w-max items-center">
          {[...TICKER_ITEMS, ...TICKER_ITEMS].map((_, i) => (
            <span key={i} className="flex items-center">
              <span className="font-display px-6 text-[clamp(2rem,6vw,3.6rem)] leading-none text-ink md:px-8">
                You May Also Enjoy
              </span>
              <Sun className="animate-spin-slow h-8 w-8 shrink-0 text-brand md:h-10 md:w-10" strokeWidth={1.5} />
            </span>
          ))}
        </div>
      </div>

      <div className="mx-auto mt-16 grid max-w-[64rem] grid-cols-1 items-center gap-10 px-6 md:grid-cols-[minmax(0,15rem)_1fr] md:gap-16">
        <Link 
          to={`/book/${spotlightBook.work_id}`} 
          className="mx-auto w-[65%] rotate-[-4deg] transition-transform duration-500 hover:rotate-0 hover:scale-105 sm:w-[55%] md:w-full block"
        >
          <BookCover
            title={spotlightBook.title}
            author={displayAuthor}
            paletteIndex={paletteIndex}
            variant={variant}
            className="shadow-[0_18px_40px_rgba(0,0,0,0.18)]"
          />
        </Link>
        <div className="text-center md:text-left">
          <p className="font-display mb-4 text-[0.75rem] tracking-[0.2em] text-brand uppercase">Staff Pick</p>
          <p className="text-[1rem] leading-relaxed text-ink-soft">
            Every month our librarians surface a title that deserves a second look. This time, it's{' '}
            <Link to={`/book/${spotlightBook.work_id}`} className="text-ink font-medium hover:underline">{spotlightBook.title}</Link> by {displayAuthor} — pulled from the{' '}
            {displayCategory} shelf for readers chasing something quietly unforgettable. Reserve your
            copy before the hold list fills up.
          </p>
          <Link
            to={`/book/${spotlightBook.work_id}`}
            className="font-display mt-6 inline-block text-[0.78rem] tracking-wide text-brand hover:underline"
          >
            Explore this Pick &rarr;
          </Link>
        </div>
      </div>
    </section>
  )
}
