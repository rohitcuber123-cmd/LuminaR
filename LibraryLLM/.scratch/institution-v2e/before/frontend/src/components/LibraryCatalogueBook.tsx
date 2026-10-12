import type { DisplayBook } from '../lib/libraryCatalogue'
import { bookSeed } from '../lib/bookPresentation'
import { patronPath } from '../lib/libraryWorkspace'
import { BookCoverArt } from './BookCoverArt'
import { BookCard } from './BookCard'
import { BookDetailView } from './BookDetailView'
import { CatalogueBookActions } from './CatalogueBookActions'
export { CatalogueBookActions } from './CatalogueBookActions'
/** Typed tenant adapters; all visual/personal composition is shared. */
export function CatalogueCover({book}: {book:DisplayBook}) {
  return <div className="catalogue-cover" aria-label={`Cover for ${book.title}`}><BookCoverArt title={book.title} author={book.authors.join('; ')} seed={bookSeed(book)} url={book.cover_url} /></div>
}
export function LibraryCatalogueBook({book,changed,detailed=false,rail=false}: {book:DisplayBook;changed:()=>void;detailed?:boolean;rail?:boolean}) {
  return detailed ? <BookDetailView book={book} backPath={patronPath(book.library_id,'catalogue')} physicalActions={<CatalogueBookActions book={book} changed={changed} />} /> : <BookCard book={book} changed={changed} rail={rail} />
}
