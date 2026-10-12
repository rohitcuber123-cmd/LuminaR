import type { BackendBook, SearchResult, Recommendation } from './api'
import { globalDisplayBook, type DisplayBook } from './libraryCatalogue'
import { patronPath } from './libraryWorkspace'
import { validWorkId } from './assistant'
import { productBookPath } from './productContext'

export const bookSeed = (book: DisplayBook) => book.cover_seed ?? [...(book.global_work_id || book.display_id)].reduce((sum,c) => (sum * 31 + c.charCodeAt(0)) >>> 0, 0)
export const bookPath = (book: DisplayBook) => book.library_id ? patronPath(book.library_id,
  `${book.source === 'LIBRARY' ? 'books' : 'global-books'}/${encodeURIComponent(book.library_book_id || book.global_work_id || book.display_id)}`) : productBookPath(book.global_work_id || book.display_id, null)
export const personalBookKey = (book: DisplayBook) => book.global_work_id && validWorkId(book.global_work_id) ? book.global_work_id :
  book.source === 'LIBRARY' && book.library_id && book.library_book_id ? `local:${book.library_id}:${book.library_book_id}` : null
export const globalBookPresentation = (book: Partial<BackendBook>) => globalDisplayBook(book, '')
export function searchBookPresentation(result: SearchResult) {
  return globalBookPresentation({ book_id: 0, work_id: result.work_id || '', title: result.title || 'Untitled', authors: result.authors || '',
    subjects: result.subjects || '', average_rating: result.rating ?? undefined, rating_count: result.rating_count ?? undefined, reading_log_count: result.read_logs ?? undefined,
    readable: result.readable, rag_available: result.rag_available })
}
export const recommendationPresentation = (book: Recommendation) => globalBookPresentation({ ...book, book_id: book.book_id || 0,
  authors: book.authors || '', subjects: book.subjects || '' })
/** Asset flags are UI hints. Protected reader/RAG endpoints enforce entitlements. */
export function capabilityBook(book: DisplayBook): BackendBook {
  return { book_id: bookSeed(book), work_id: book.global_work_id || '', title: book.title, authors: book.authors.join('; '),
    subjects: book.subjects.join('|'), description: book.description || null, average_rating: book.average_rating || 0,
    rating_count: book.rating_count || 0, reading_log_count: book.reading_log_count || 0, shelf_location: null,
    total_copies: 0, available_copies: 0, created_at: book.added_at || '', readable: book.readable, rag_available: book.rag_available }
}
export function bookAvailability(book: DisplayBook) {
  if (book.source !== 'LIBRARY') return 'Global Catalogue'
  if (!book.owned_by_current_library) return 'Saved library book'
  if (book.has_online && book.has_physical === false) return 'Available online'
  if (book.circulation_status === 'REFERENCE_ONLY') return 'Reference Only'
  if (book.circulation_status === 'TEMPORARILY_UNAVAILABLE') return 'Temporarily unavailable'
  if (book.requestable_count == null) return 'View library details'
  return book.requestable_count > 0 ? 'Available now' : 'Currently unavailable'
}
export const bookFormatLabel = (book:DisplayBook) => book.book_format==='PHYSICAL_AND_DIGITAL'?'Physical + Online':book.book_format==='DIGITAL_ONLY'?'Online':book.book_format==='PHYSICAL_ONLY'?'Physical':null
