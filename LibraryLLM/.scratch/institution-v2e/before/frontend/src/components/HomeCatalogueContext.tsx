import { createContext, useContext } from 'react'
import type { BackendBook } from '../lib/api'
import type { CatalogueHome, DisplayBook } from '../lib/libraryCatalogue'
import { patronPath } from '../lib/libraryWorkspace'

export function displayToHomeBook(book: DisplayBook): BackendBook {
  const seed = book.cover_seed ?? [...book.display_id].reduce((sum, c) => (sum * 31 + c.charCodeAt(0)) >>> 0, 0)
  return { book_id: seed, work_id: book.display_id, title: book.title, authors: book.authors.join('; '),
    subjects: book.subjects.join('|'), description: book.description || null, average_rating: 0,
    rating_count: 0, reading_log_count: 0, shelf_location: null, total_copies: 0, available_copies: 0,
    created_at: book.added_at || '' }
}
export type HomeCatalogue = { data: CatalogueHome; changed: () => void }
export const HomeCatalogueContext = createContext<HomeCatalogue | null>(null)
export const useHomeCatalogue = () => useContext(HomeCatalogueContext)
export function homeBookPath(context: HomeCatalogue | null, id: string) {
  if (!context) return `/book/${id}`
  const book = [...context.data.featured, ...context.data.new_arrivals, ...context.data.popular,
    ...(context.data.for_you || []), ...context.data.subjects.flatMap(s => s.preview_book ? [s.preview_book] : [])].find(b => b.display_id === id)
  return patronPath(context.data.source.library_id, `${book?.source === 'LIBRARY' ? 'books' : 'global-books'}/${encodeURIComponent(id)}`)
}
export const homeCataloguePath = (context: HomeCatalogue | null, section = 'catalogue') => context ? patronPath(context.data.source.library_id, section) :
  section === 'new-arrivals' ? '/catalog?sort=new_arrivals' : section === 'popular' ? '/catalog?sort=popular' : section.startsWith('catalogue?') ? '/catalog?' + section.split('?')[1] : '/catalog'
