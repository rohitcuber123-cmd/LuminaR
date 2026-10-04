import { useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { BookCover } from './BookCover'
import { BookSelectButton } from './BookSelectButton'
import { BookConnectionGraph } from './BookConnectionGraph'
import type { KGBook, ReasonPath, RelatedBook } from '@/lib/knowledgeGraph'

const category: Record<string, string> = { author: 'Authors', subject: 'Subjects', series: 'Series', publisher: 'Publishers', language: 'Languages', era: 'Publication eras', topic: 'Description topics' }
export function WhyRelated({ paths, seedTitle, bookTitle }: { paths: ReasonPath[]; seedTitle?: string; bookTitle?: string }) {
  const [showConnection, setShowConnection] = useState(false)
  const connectionId = useId()
  const groups = new Map<string, Set<string>>()
  for (const path of paths) {
    const name = category[path.kind] ?? 'Other relationships'
    if (!groups.has(name)) groups.set(name, new Set())
    groups.get(name)!.add(path.label)
  }
  return <div className="mt-3"><details className="text-xs text-ink-soft"><summary className="cursor-pointer font-medium text-moss">Why related?</summary>
    <p className="mt-2">Shared knowledge-graph relationships:</p>
    {[...groups].map(([name, labels]) => <div key={name} className="mt-2"><h4 className="font-semibold">{name}</h4><ul className="mt-1 list-inside list-disc">{[...labels].map(label => <li key={label} className="break-words">{label}</li>)}</ul></div>)}
  </details>
    <button type="button" className="assistant-button mt-3" aria-expanded={showConnection} aria-controls={connectionId} onClick={() => setShowConnection(value => !value)}>{showConnection ? 'Hide connection' : 'Show connection'}</button>
    <div id={connectionId} hidden={!showConnection}>{showConnection && <BookConnectionGraph paths={paths} seedTitle={seedTitle} bookTitle={bookTitle} />}</div>
  </div>
}
export function RelatedBookCard({ book, seed }: { book: RelatedBook; seed?: KGBook }) {
  const hash = [...book.work_id].reduce((sum, char) => sum + char.charCodeAt(0), 0)
  const author = book.authors.join(' · ') || 'Author not recorded'
  return <article className="min-w-0 rounded-sm border border-line bg-paper p-4" aria-label={book.title}>
    <Link to={`/book/${encodeURIComponent(book.work_id)}`} className="flex gap-4">
      <div className="w-16 shrink-0"><BookCover title={book.title} author={author} paletteIndex={hash} variant="stripe" /></div>
      <div className="min-w-0"><h3 className="font-display break-words text-base leading-tight text-ink">{book.title}</h3><p className="mt-1 break-words text-xs text-ink-soft">{author}</p>
        {book.average_rating != null && book.average_rating > 0 && <p className="mt-2 text-xs">★ {book.average_rating.toFixed(1)}{book.rating_count != null && book.rating_count > 0 ? ` (${book.rating_count})` : ''}</p>}
        <p className={`mt-2 text-xs ${book.available_copies > 0 ? 'text-moss' : 'text-ink-soft'}`}>{book.available_copies > 0 ? `Available · ${book.available_copies} of ${book.total_copies} copies` : 'Currently unavailable'}</p>
        {book.shelf_location && <p className="mt-1 text-xs text-ink-soft">Shelf: {book.shelf_location}</p>}
      </div>
    </Link>
    <p className="mt-3 break-words text-xs text-ink-soft">Connected through: {[...new Set(book.reason_paths.map(path => path.label))].slice(0, 3).join(' · ')}</p>
    <div className="mt-2 flex flex-wrap items-center gap-2"><Link className="assistant-button" to={`/book/${encodeURIComponent(book.work_id)}`}>View</Link><BookSelectButton book={book} /></div>
    <WhyRelated paths={book.reason_paths} seedTitle={seed?.title} bookTitle={book.title} />
  </article>
}
