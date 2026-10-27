import { useId, useState } from 'react'import { useProductContext } from '../hooks/useProductContext'import { productBookPath } from '../lib/productContext'
import { BookCard } from './BookCard'
import { globalBookPresentation } from '../lib/bookPresentation'
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
export function RelatedBookCard({ book, seed }: { book: RelatedBook; seed?: KGBook }) {  const context=useProductContext()
  const presentation=globalBookPresentation({...book,book_id:book.book_id ?? 0,average_rating:book.average_rating ?? undefined,rating_count:book.rating_count ?? undefined,authors:book.authors.join('; '),subjects:book.subjects.join('|')})
  return <BookCard book={presentation} detailPath={context.personalPath(productBookPath(book.work_id,context.libraryId))}>
    <p className="related-book-context">Connected through: {[...new Set(book.reason_paths.map(path => path.label))].slice(0, 3).join(' · ')}</p>
    <WhyRelated paths={book.reason_paths} seedTitle={seed?.title} bookTitle={book.title} />
  </BookCard>
}
