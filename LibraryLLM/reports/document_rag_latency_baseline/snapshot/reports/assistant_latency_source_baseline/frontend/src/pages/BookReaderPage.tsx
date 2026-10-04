import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getReadableBook, type ReadableBook } from '@/lib/api'

export function BookReaderPage() {
  const { workId } = useParams<{ workId: string }>()
  const [book, setBook] = useState<ReadableBook | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let cancelled = false
    setBook(null)
    setError('')
    if (workId) getReadableBook(workId).then(result => {
      if (!cancelled) setBook(result)
    }).catch((reason: unknown) => {
      if (!cancelled) setError(reason instanceof Error ? reason.message : 'Unable to load this book.')
    })
    return () => { cancelled = true }
  }, [workId])
  return (
    <article className="mx-auto max-w-3xl px-6 py-12">
      <Link className="text-sm text-brand" to={`/book/${encodeURIComponent(workId || '')}`}>← Back to book</Link>
      {error ? <p className="mt-8 text-red-700" role="alert">{error}</p> : !book ? (
        <p className="mt-8 text-ink-soft" role="status">Loading full text…</p>
      ) : <>
        <h1 className="mt-8 font-display text-3xl text-ink">{book.title}</h1>
        <p className="mt-2 text-ink-soft">{book.authors.join(', ')}</p>
        <div className="mt-10 whitespace-pre-wrap font-serif text-lg leading-8 text-ink">{book.text}</div>
      </>}
    </article>
  )
}
