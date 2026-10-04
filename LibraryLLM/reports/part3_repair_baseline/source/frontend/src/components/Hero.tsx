import { Link } from 'react-router-dom'
import { BookCover } from '@/components/BookCover'
import { type BackendBook } from '@/lib/api'
import { PALETTES, type CoverVariant } from '@/data/books'

interface HeroProps {
  books: BackendBook[]
}

export function Hero({ books }: HeroProps) {
  // We double the books array for a continuous marquee effect
  const marqueeBooks = [...books, ...books]

  return (
    <section id="top" className="pt-16 pb-14 md:pt-24 md:pb-20">
      <div className="mx-auto max-w-[64rem] px-6 text-center">
        <p className="font-display mb-5 text-[0.75rem] tracking-[0.2em] text-brand">
          Public Library &middot; Open to All
        </p>
        <h1 className="font-display text-[clamp(2.4rem,8vw,4.6rem)] leading-[0.98] text-ink">
          Every Story
          <br />
          Waiting to Be Borrowed
        </h1>
        <p className="mx-auto mt-6 max-w-[38rem] text-[0.95rem] leading-relaxed text-ink-soft">
          Thousands of books, audiobooks, and research papers, all searchable in one place. Reserve a
          copy, place a hold, or start reading today — free with your library card.
        </p>
      </div>

      <div className="marquee-wrap mt-14 overflow-hidden">
        <div className="marquee-track flex w-max gap-4 md:gap-5">
          {marqueeBooks.map((book, i) => {
            const paletteIndex = book.book_id % PALETTES.length
            const variants: CoverVariant[] = ['circle', 'ring', 'split', 'stripe']
            const variant = variants[book.book_id % variants.length]

            return (
              <Link
                key={`${book.book_id}-${i}`}
                to={`/book/${book.work_id}`}
                className="w-[130px] shrink-0 sm:w-[160px] md:w-[190px] transition-transform hover:-translate-y-2 hover:scale-[1.02]"
              >
                <BookCover 
                  title={book.title} 
                  paletteIndex={paletteIndex} 
                  variant={variant} 
                />
              </Link>
            )
          })}
        </div>
      </div>
    </section>
  )
}
