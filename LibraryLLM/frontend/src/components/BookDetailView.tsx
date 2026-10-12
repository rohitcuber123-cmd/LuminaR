import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, BookOpen, Layers, Calendar } from 'lucide-react'
import type { DisplayBook } from '../lib/libraryCatalogue'
import { bookSeed, capabilityBook, bookAvailability, bookFormatLabel } from '../lib/bookPresentation'
import { BookCoverArt } from './BookCoverArt'
import { BookPersonalActions } from './BookPersonalActions'
import { BookCapabilities } from './BookCapabilities'
import '../styles/product.css'

/** The mature global detail composition, with explicit tenant facts/actions injected. */
export function BookDetailView({book,backPath,notice,physicalActions,relatedActions,related,resources}: {
  book:DisplayBook; backPath:string; notice?:ReactNode; physicalActions?:ReactNode; relatedActions?:ReactNode; related?:ReactNode; resources?:ReactNode
}) {
  const owned = book.source === 'LIBRARY' && book.owned_by_current_library
  return <section className="book-detail-view mx-auto max-w-[90rem] px-6 py-10 md:px-10 md:py-16" data-book-context={owned?'LIBRARY':'GLOBAL'}>
    <Link to={backPath} className="mb-8 inline-flex items-center gap-2 text-sm text-ink-soft transition-colors hover:text-brand"><ArrowLeft size={16} aria-hidden="true" />{book.library_id ? 'Browse Books' : 'Back to catalog'}</Link>
    {notice}
    <div className="grid grid-cols-1 gap-12 md:grid-cols-[minmax(0,18rem)_1fr] lg:gap-16">
      <div className="mx-auto w-[65%] md:w-full"><BookCoverArt title={book.title} author={book.authors.join('; ')} seed={bookSeed(book)} url={book.cover_url} className="shadow-[0_18px_40px_rgba(0,0,0,0.15)]" /></div>
      <div className="book-detail-body"><p className="font-display mb-2 text-[0.72rem] tracking-[0.2em] text-brand uppercase break-words">{book.subjects[0] || 'Book'}</p>
        <h1 className="font-display text-[clamp(1.8rem,4vw,2.8rem)] leading-[1.05] text-ink">{book.title}</h1>
        <p className="mt-3 text-lg text-ink-soft">by {book.authors.join('; ') || 'Author not recorded'}</p>
        <div className="mt-8 flex flex-wrap gap-6 text-sm text-ink-soft"><span className="flex items-center gap-2"><BookOpen size={16} aria-hidden="true" />
          <span className={owned && (book.requestable_count || 0)>0 ? 'text-moss font-medium' : ''}>{owned && book.requestable_count != null && book.circulation_status === 'CIRCULATING' ? `${book.requestable_count} available to request` : bookAvailability(book)}</span></span>
          {owned && book.has_physical !== false && <span className="flex items-center gap-2"><Layers size={16} aria-hidden="true" />{book.shelf_location || 'Shelf not recorded'}</span>}
          {book.average_rating != null && <span>★ {book.average_rating>0 ? `${book.average_rating.toFixed(1)} (${book.rating_count || 0})` : 'No ratings yet'}</span>}
          {book.reading_log_count != null && <span className="flex items-center gap-2"><Calendar size={16} aria-hidden="true" />{book.reading_log_count.toLocaleString()} reads</span>}
        </div>
        {owned && <dl className="book-facts">{bookFormatLabel(book)&&<div><dt>Format</dt><dd>{bookFormatLabel(book)}</dd></div>}<div><dt>Accession</dt><dd>{book.accession_number || 'Not recorded'}</dd></div>{book.has_physical !== false && <div><dt>Circulation status</dt><dd>{book.circulation_status === 'CIRCULATING' ? 'Circulating' : bookAvailability(book)}</dd></div>}
          {book.availability && <div><dt>Copies</dt><dd>{book.availability.total} total · {book.availability.active_loans} on loan · {book.availability.pending_holds} pending</dd></div>}</dl>}
        {!!book.subjects.length && <div className="mt-6 flex flex-wrap gap-2">{book.subjects.slice(1,9).map(s=><span key={s} className="rounded-full bg-brand/5 px-2.5 py-1 text-[0.65rem] uppercase tracking-wide text-brand border border-brand/10 break-words">{s}</span>)}</div>}
        <div className="mt-8 border-t border-line pt-8"><p className="book-description text-[0.95rem] leading-relaxed text-ink-soft whitespace-pre-line">{book.description || 'No description available.'}</p></div>
        {book.global_work_id && <BookCapabilities book={capabilityBook(book)} showUnavailable />}
        {owned ? physicalActions : book.library_id && <p className="mt-6 text-sm text-ink-soft">Not currently held by this library.</p>}
        <div className="book-detail-actions flex flex-wrap items-center gap-3"><BookPersonalActions book={book} detailed />{relatedActions}</div>
        {resources}
      </div>
    </div>{related}
  </section>
}
export function BookDetailSkeleton() {
  return <section className="book-detail-view mx-auto max-w-[90rem] px-6 py-10 md:px-10 md:py-16" aria-label="Loading book details" role="status"><div className="mb-8 h-5 w-32 rounded bg-line/60 animate-pulse" /><div className="grid grid-cols-1 gap-12 md:grid-cols-[minmax(0,18rem)_1fr] lg:gap-16"><div className="mx-auto w-[65%] md:w-full aspect-[2/3] rounded bg-line animate-pulse" /><div className="space-y-8"><div className="h-10 w-3/4 bg-line animate-pulse" /><div className="h-6 w-1/3 bg-line animate-pulse" /><div className="h-24 bg-line/50 animate-pulse" /></div></div></section>
}
