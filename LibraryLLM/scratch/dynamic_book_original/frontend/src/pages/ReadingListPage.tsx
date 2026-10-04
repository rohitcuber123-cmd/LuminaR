import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookCover } from '@/components/BookCover'
import { useLibraryStore } from '@/store/useLibraryStore'
import { showToast } from '@/components/Toast'
import { BookOpen, Trash2 } from 'lucide-react'
import { getReadingList } from '@/lib/api'
import { PALETTES, type CoverVariant } from '@/data/books'

export function ReadingListPage() {
  const { removeFromList, readingList, fetchUserData } = useLibraryStore()
  const [books, setBooks] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    async function loadList() {
      try {
        setLoading(true)
        const res = await getReadingList()
        if (mounted) {
          setBooks(res.items || [])
        }
      } catch (err) {
        console.error('Failed to load reading list', err)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    loadList()
    return () => {
      mounted = false
    }
  }, [readingList.length]) // re-run if length changes, though removing will also update it locally

  return (
    <section className="mx-auto max-w-[90rem] px-6 py-10 md:px-10 md:py-16">
      <div className="mb-10 border-b border-line pb-6">
        <h1 className="font-display text-[clamp(1.8rem,4vw,2.6rem)] text-ink">My Reading List</h1>
        <p className="mt-2 text-sm text-ink-soft">
          {!loading && books.length > 0
            ? `${books.length} ${books.length === 1 ? 'book' : 'books'} saved for later.`
            : 'Your reading list is empty.'}
        </p>
      </div>

      {loading ? (
        <div className="py-20 text-center">
          <p className="font-display text-xl text-ink-soft">Loading...</p>
        </div>
      ) : books.length > 0 ? (
        <div className="grid grid-cols-2 gap-x-6 gap-y-12 sm:grid-cols-3 lg:grid-cols-4">
          {books.map((book) => {
            const paletteIndex = book.book_id ? book.book_id % PALETTES.length : 0
            const variants: CoverVariant[] = ['circle', 'ring', 'split', 'stripe']
            const variant = variants[book.book_id ? book.book_id % variants.length : 0]
            const displayAuthor = book.authors || 'Unknown Author'
            const workId = book.work_id

            return (
              <div key={workId} className="group relative">
                <Link to={`/book/${workId}`}>
                  <BookCover
                    title={book.title}
                    author={displayAuthor}
                    paletteIndex={paletteIndex}
                    variant={variant}
                    className="transition-transform duration-300 group-hover:-translate-y-1 group-hover:scale-[1.03]"
                  />
                  <p className="font-display mt-4 text-[0.95rem] leading-tight text-ink">{book.title}</p>
                  <p className="mt-1 text-[0.8rem] text-ink-soft">{displayAuthor}</p>
                </Link>

                <button
                  onClick={async () => {
                    try {
                      await removeFromList(workId)
                      showToast(`Removed "${book.title}" from list`, 'info')
                      await fetchUserData() // refetch the global state so it syncs perfectly
                    } catch (err: any) {
                      showToast(err.message || 'Failed to remove from reading list', 'warning')
                    }
                  }}
                  className="mt-3 flex items-center gap-1.5 text-[0.72rem] text-ink-soft transition-colors hover:text-brand"
                >
                  <Trash2 className="h-3 w-3" />
                  Remove
                </button>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="flex flex-col items-center py-20 text-center">
          <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-panel">
            <BookOpen className="h-8 w-8 text-ink-soft/50" />
          </div>
          <p className="font-display text-xl text-ink-soft">Nothing here yet</p>
          <p className="mt-2 max-w-[24rem] text-sm text-ink-soft/70">
            Start building your reading list by browsing the catalog and adding books you'd like to read.
          </p>
          <Link
            to="/catalog"
            className="font-display mt-6 inline-block rounded-sm bg-brand px-6 py-2.5 text-[0.75rem] tracking-wide text-paper transition-colors hover:bg-brand-dark"
          >
            Browse Catalog
          </Link>
        </div>
      )}
    </section>
  )
}
