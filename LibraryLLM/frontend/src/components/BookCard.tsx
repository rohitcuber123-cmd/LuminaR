import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'
import type { DisplayBook } from '../lib/libraryCatalogue'
import { bookAvailability,bookPath,bookSeed,capabilityBook,bookFormatLabel } from '../lib/bookPresentation'
import { DiscoveryBookFrame } from './DiscoveryBookFrame'
import { BookPersonalActions } from './BookPersonalActions'
import { BookCapabilities } from './BookCapabilities'
import { CatalogueBookActions } from './CatalogueBookActions'
import { useProductContext } from '../hooks/useProductContext'
import {useInstitutionStore} from '../store/useInstitutionStore'
import {isLibraryStaff} from '../lib/libraryWorkspace'
import {resolveLibraryBookCapabilities} from '../lib/libraryBookCapabilities'
import { StatusPill } from './StatusPill'

export function BookCard({book,changed=()=>{},rail=false,children,detailPath}: {book:DisplayBook;changed?:()=>void;rail?:boolean;children?:ReactNode;detailPath?:string}) {
  const owned=book.source==='LIBRARY' && book.owned_by_current_library
  const context=useProductContext(),membership=useInstitutionStore(s=>s.libraries.find(l=>l.library_id===book.library_id)),staff=isLibraryStaff(membership),path=context.personalPath(detailPath || bookPath(book,staff))
  const capability=resolveLibraryBookCapabilities(book,membership?.membership)
  const physicalPrimary=capability.canRequestPhysical || capability.canJoinWaitlist || !!(book.user_request_state || book.user_reservation_state || book.user_loan_state)
  return <article className={`product-book-card discovery-book group flex flex-col min-w-0${rail?' flex-shrink-0 w-[180px]':''}`} aria-label={book.title} data-library-book-id={owned ? book.library_book_id || undefined : undefined}>
    {!rail && <p className="mb-3 truncate text-[0.68rem] uppercase tracking-wide text-ink-soft" title={book.subjects[0]}>{book.subjects[0] || 'Book'}</p>}
    <DiscoveryBookFrame title={book.title} author={book.authors.join('; ')} seed={bookSeed(book)} path={path} coverUrl={book.cover_url} availability={bookAvailability(book)}
      status={<StatusPill tone={owned ? capability.hasPhysical && capability.hasOnline ? 'combined' : capability.hasOnline ? 'online' : capability.hasPhysical ? 'physical' : 'neutral' : 'neutral'}>{owned ? bookFormatLabel(book) || 'Unavailable' : 'Global'}</StatusPill>}>
      <div className="book-card-meta mt-2 flex flex-col gap-1 min-h-[46px]">
        {capability.hasPhysical && book.shelf_location && <p className="truncate text-xs text-ink-soft">Shelf {book.shelf_location}</p>}
        {book.average_rating != null && book.average_rating>0 && <p className="text-xs text-ink-soft">★ {book.average_rating.toFixed(1)}{book.rating_count ? ` (${book.rating_count})` : ''}</p>}
      </div>
      <div className="book-card-actions">
        <BookPersonalActions book={book} overflow={(capability.readPath || capability.knowMorePath || book.global_work_id || !!book.search_reasons?.length) ? <>
          {capability.readPath && physicalPrimary && <Link to={capability.readPath}>Read Online</Link>}
          {capability.knowMorePath && <Link to={capability.knowMorePath}>Know More</Link>}
          {book.global_work_id && <BookCapabilities book={capabilityBook(book)} presentation={owned ? 'full' : 'overflow'} />}
          {!!book.search_reasons?.length && <details className="search-result-reasons"><summary>Why this result?</summary><ul>{book.search_reasons.slice(0,2).map(reason=><li key={reason}>{reason}</li>)}</ul></details>}
        </> : undefined} />
        <div className="book-card-primary">
          {owned && !staff ? <CatalogueBookActions key={`${book.library_id}:${book.display_id}`} book={book} changed={changed} concise /> :
            !owned && book.global_work_id ? <BookCapabilities book={capabilityBook(book)} presentation="primary" /> : null}
        </div>
      </div>
      {children}
    </DiscoveryBookFrame>
  </article>
}
