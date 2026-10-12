import { Link } from 'react-router-dom'
import type { DisplayBook } from '../lib/libraryCatalogue'
import { bookAvailability,bookPath,bookSeed,capabilityBook,bookFormatLabel } from '../lib/bookPresentation'
import { DiscoveryBookFrame } from './DiscoveryBookFrame'
import { BookPersonalActions } from './BookPersonalActions'
import { BookCapabilities } from './BookCapabilities'
import { CatalogueBookActions } from './CatalogueBookActions'
import { useProductContext } from '../hooks/useProductContext'
import '../styles/product.css'

export function BookCard({book,changed=()=>{},rail=false}: {book:DisplayBook;changed?:()=>void;rail?:boolean}) {
  const owned=book.source==='LIBRARY' && book.owned_by_current_library
  const context=useProductContext(),path=context.personalPath(bookPath(book))
  return <article className={`product-book-card discovery-book group flex flex-col min-w-0${rail?' flex-shrink-0 w-[180px]':''}`} aria-label={book.title} data-library-book-id={owned ? book.library_book_id || undefined : undefined}>
    {!rail && <p className="mb-3 truncate text-[0.68rem] uppercase tracking-wide text-ink-soft" title={book.subjects[0]}>{book.subjects[0] || 'Book'}</p>}
    <DiscoveryBookFrame title={book.title} author={book.authors.join('; ')} seed={bookSeed(book)} path={path} coverUrl={book.cover_url} availability={bookAvailability(book)}>
      {owned && bookFormatLabel(book) && <span className="ui-badge">{bookFormatLabel(book)}</span>}
      {owned && book.shelf_location && <p className="mt-2 truncate text-xs text-ink-soft">Shelf {book.shelf_location}</p>}
      {book.average_rating != null && book.average_rating>0 && <p className="mt-2 text-xs text-ink-soft">★ {book.average_rating.toFixed(1)}{book.rating_count ? ` (${book.rating_count})` : ''}</p>}
      {book.global_work_id && <BookCapabilities book={capabilityBook(book)} />}
      <BookPersonalActions book={book} />
      {owned ? <CatalogueBookActions key={`${book.library_id}:${book.display_id}`} book={book} changed={changed} concise /> :
        <Link className="mt-3 w-full rounded-md bg-brand px-4 py-2 text-center text-xs font-medium text-paper hover:bg-brand-dark" to={path}>View Details</Link>}
    </DiscoveryBookFrame>
  </article>
}
