import type { ReactNode } from 'react'
import { BookOpen } from 'lucide-react'
import { BookCover } from '@/components/BookCover'
import { BOOKS } from '@/data/books'

const SHOWCASE_BOOKS = [...BOOKS, ...BOOKS]

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      {/* ── Left decorative panel ── */}
      <div className="auth-panel-left relative hidden w-[45%] overflow-hidden bg-ink lg:block xl:w-[50%]">
        {/* Gradient overlays */}
        <div className="absolute inset-0 z-10 bg-gradient-to-b from-ink via-ink/60 to-ink" />

        {/* Vertical scrolling book covers */}
        <div className="absolute inset-0 flex gap-4 px-8 opacity-25">
          <div className="auth-marquee-up flex w-1/3 flex-col gap-4 pt-8">
            {SHOWCASE_BOOKS.slice(0, 8).map((book, i) => (
              <div key={`col1-${i}`} className="shrink-0">
                <BookCover
                  title={book.title}
                  paletteIndex={book.paletteIndex}
                  variant={book.variant}
                />
              </div>
            ))}
          </div>
          <div className="auth-marquee-down flex w-1/3 flex-col gap-4 pt-8">
            {SHOWCASE_BOOKS.slice(8, 16).map((book, i) => (
              <div key={`col2-${i}`} className="shrink-0">
                <BookCover
                  title={book.title}
                  paletteIndex={book.paletteIndex}
                  variant={book.variant}
                />
              </div>
            ))}
          </div>
          <div className="auth-marquee-up-slow flex w-1/3 flex-col gap-4 pt-8">
            {SHOWCASE_BOOKS.slice(4, 12).map((book, i) => (
              <div key={`col3-${i}`} className="shrink-0">
                <BookCover
                  title={book.title}
                  paletteIndex={book.paletteIndex}
                  variant={book.variant}
                />
              </div>
            ))}
          </div>
        </div>

        {/* Branding overlay */}
        <div className="relative z-20 flex h-full flex-col justify-between p-12">
          <div className="flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-brand" strokeWidth={1.75} />
            <span className="font-display text-[1.3rem] tracking-tight text-paper">
              Lumina<span className="text-brand">R</span>
            </span>
          </div>

          <div>
            <h2 className="font-display text-[clamp(2rem,4vw,3.2rem)] leading-[1.02] text-paper">
              Every Story
              <br />
              <span className="text-brand">Waiting</span> to
              <br />
              Be Borrowed
            </h2>
            <p className="mt-5 max-w-[20rem] text-sm leading-relaxed text-paper/45">
              41 million works. 5 million searchable embeddings. One library card away from your next
              great read.
            </p>
          </div>

          <p className="text-[0.68rem] text-paper/25">
            &copy; {new Date().getFullYear()} LuminaR Public Library
          </p>
        </div>
      </div>

      {/* ── Right form panel ── */}
      <div className="flex min-h-screen w-full flex-col items-center justify-center bg-paper px-6 py-12 lg:w-[55%] xl:w-[50%]">
        {/* Mobile logo */}
        <div className="mb-10 flex items-center gap-2 lg:hidden">
          <BookOpen className="h-5 w-5 text-brand" strokeWidth={1.75} />
          <span className="font-display text-[1.15rem] tracking-tight text-ink">
            Lumina<span className="text-brand">R</span>
          </span>
        </div>

        <div className="w-full max-w-[420px]">{children}</div>
      </div>
    </div>
  )
}
