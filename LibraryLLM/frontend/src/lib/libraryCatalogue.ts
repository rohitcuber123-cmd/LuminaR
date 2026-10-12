import { request, type BackendBook, type BooksResponse, type CategoriesResponse, type SearchResponse, type RecommendationsResponse } from './api'
import { institutionApi } from './institutions'
import type { Availability } from './libraryLending'

export type CatalogueSource = {
  library_id: string; library_name: string; catalogue_source: 'LIBRARY_LOCAL' | 'GLOBAL_FALLBACK'; local_book_count: number;
  capabilities: { physical_actions: boolean; reservations: boolean; local_search: boolean; global_discovery: boolean };
  circulation_state: string; discovery_notice: string | null
}
export type DisplayBook = {
  book_format?: 'PHYSICAL_ONLY'|'DIGITAL_ONLY'|'PHYSICAL_AND_DIGITAL'|'UNAVAILABLE';has_physical?:boolean;has_online?:boolean;online_asset_id?:string|null;
  display_id: string; library_id: string; library_book_id: string | null; global_work_id: string | null;
  title: string; authors: string[]; subjects: string[]; description?: string | null; cover_url: string | null;
  source: 'LIBRARY' | 'GLOBAL'; owned_by_current_library: boolean; accession_number: string | null;
  shelf_location: string | null; circulation_status: string | null; requestable_count: number | null;
  availability?: Availability | null; added_at?: string | null; cover_seed?: number | null;
  average_rating?: number | null; rating_count?: number | null; reading_log_count?: number | null; readable?: boolean; rag_available?: boolean;
  user_request_state: { id: string; status: string } | null;
  user_reservation_state: { id: string; status: string; queue_position: number | null; queue_length: number } | null;
  user_loan_state: { id: string; status: string; due_at?: string | null; return_requested: boolean } | null;
  actions: { request: boolean; reserve: boolean; cancel_request: boolean; cancel_reservation: boolean };
  popularity?: { score: number; loans: number; approved_requests: number; reservations: number; window_days: number }
}
export type SubjectCount = { subject: string; count: number; preview_book?: DisplayBook | null }
export type CatalogueHome = { source: CatalogueSource; featured: DisplayBook[]; for_you?: DisplayBook[]; new_arrivals: DisplayBook[]; popular: DisplayBook[]; subjects: SubjectCount[]; my_library: { pending_requests: number; active_loans: number; waiting_reservations: number }; popularity_window_days: number }
export type CataloguePage = { source: CatalogueSource; results: DisplayBook[]; total: number | null; has_more: boolean; offset: number; limit: number }
export type GenrePage = { source: CatalogueSource; results: SubjectCount[]; total: number; has_more: boolean; offset: number; limit: number }
export type CatalogueDetail = { source: CatalogueSource; book: DisplayBook }
export type CatalogueOperation = 'home' | 'books' | 'genres' | 'detail' | 'global-detail'
export const catalogueBase = (id: string) => `/libraries/${encodeURIComponent(id)}/catalogue`
const split = (value: unknown) => Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : typeof value === 'string' ? value.split(/[;|]/).map(v => v.trim()).filter(Boolean) : []
const noActions = () => ({ request: false, reserve: false, cancel_request: false, cancel_reservation: false })

/** Global physical-stock fields are deliberately discarded, even if legacy APIs supply them. */
export function globalDisplayBook(book: Partial<BackendBook> & { cover_url?: unknown }, libraryId: string): DisplayBook {
  return { display_id: book.work_id || String(book.book_id), library_id: libraryId, library_book_id: null,
    global_work_id: book.work_id || null, title: book.title || 'Untitled catalogue record', authors: split(book.authors), subjects: split(book.subjects),
    description: book.description, cover_url: typeof book.cover_url === 'string' && /^https?:\/\//.test(book.cover_url) ? book.cover_url : null,
    source: 'GLOBAL', owned_by_current_library: false, accession_number: null, shelf_location: null,
    circulation_status: null, requestable_count: null, availability: null,
    added_at: book.created_at, cover_seed: book.book_id || undefined, average_rating: book.average_rating, rating_count: book.rating_count,
    reading_log_count: book.reading_log_count, readable: book.readable, rag_available: book.rag_available,
    user_request_state: null, user_reservation_state: null, user_loan_state: null, actions: noActions() }
}

async function recommendationCandidates(signal: AbortSignal) {
  try {
    const response = await request<RecommendationsResponse>('/recommendation-api/recommendations?limit=50&offset=0',
      { signal: AbortSignal.any([signal, AbortSignal.timeout(8000)]) })
    return response.recommendations || []
  } catch (error) { if (signal.aborted) throw error; return [] }
}

function checkSource(source: CatalogueSource, libraryId: string) {
  if (source?.library_id !== libraryId || !['LIBRARY_LOCAL', 'GLOBAL_FALLBACK'].includes(source?.catalogue_source) || !Number.isInteger(source.local_book_count) || source.local_book_count < 0)
    throw new Error('Catalogue context changed. Refresh to load this library.')
  if ((source.catalogue_source === 'LIBRARY_LOCAL') !== (source.local_book_count > 0)) throw new Error('Catalogue source could not be verified. Try again.')
}

async function globalPage(id: string, source: CatalogueSource, params: URLSearchParams, signal: AbortSignal): Promise<CataloguePage> {
  const offset = Number(params.get('offset') || 0), limit = 20, sort = params.get('sort'), subject = params.get('subject') || '', author = params.get('author') || '', query = params.get('search') || subject || author
  let results: DisplayBook[], total: number | null, hasMore: boolean
  if (params.get('view') === 'for-you') {
    const response = await request<RecommendationsResponse>(`/recommendation-api/recommendations?limit=${limit}&offset=${offset}`, { signal })
    results = response.recommendations.map(book => globalDisplayBook({...book, book_id:book.book_id || 0,authors:book.authors || '',subjects:book.subjects || ''},id))
    total = response.total_ranked_candidates ?? offset + results.length; hasMore = response.has_more === true
  } else if (params.get('search')) {
    const response = await request<SearchResponse>('/search-api/search', { method: 'POST', signal,
      body: JSON.stringify({ query, limit: 10, offset: Math.min(40,offset), category:subject, author, library_id: 'LIB001', available_at_library: false, save_history: false }) })
    results = response.results.map(book => globalDisplayBook({ work_id: book.work_id, title: book.title || '', authors: book.authors || '', subjects: book.subjects || '',readable:book.readable,rag_available:book.rag_available,average_rating:book.rating ?? undefined,rating_count:book.rating_count ?? undefined,reading_log_count:book.read_logs ?? undefined }, id))
    total = response.total_ranked_candidates ?? offset + results.length
    hasMore = response.has_more === true
  } else {
    const path = `/api/books/?limit=${limit}&offset=${offset}&sort=${['new_arrivals','popular'].includes(sort || '') ? sort : 'catalogue'}&category=${encodeURIComponent(subject)}&author=${encodeURIComponent(author)}`
    const response = await request<BooksResponse>(path, { signal })
    results = response.results.map(book => globalDisplayBook(book, id)); total = response.count
    hasMore = response.has_more ?? (total !== null && offset + results.length < total)
  }
  return { source, results, total, has_more: hasMore, offset, limit: params.get('search') ? 10 : limit }
}

/** The only frontend source switch: pages consume normalized responses, never infer mode from result length. */
export async function loadCatalogue(operation: CatalogueOperation, id: string, filters: string, signal: AbortSignal): Promise<CatalogueHome | CataloguePage | GenrePage | CatalogueDetail> {
  const params = new URLSearchParams(filters), base = catalogueBase(id)
  if (operation === 'home') {
    const home = await institutionApi<CatalogueHome>(`${base}/home`, 'GET', undefined, signal); checkSource(home.source, id)
    const candidates = await recommendationCandidates(signal)
    if (home.source.catalogue_source === 'LIBRARY_LOCAL') {
      const scoped = await institutionApi<{ source: CatalogueSource; results: DisplayBook[] }>(`${base}/recommendations`, 'POST',
        { work_ids: candidates.map(book => book.work_id), limit: 10 }, signal)
      checkSource(scoped.source, id)
      if (scoped.source.catalogue_source !== 'LIBRARY_LOCAL') throw new Error('Catalogue collection changed. Refresh to load this library.')
      return { ...home, for_you: scoped.results }
    }
    const [featured, arrivals, popular, subjects] = await Promise.all([
      request<BooksResponse>('/api/books/?limit=12&offset=0', { signal }), request<BooksResponse>('/api/books/new-arrivals?limit=12', { signal }),
      request<BooksResponse>('/api/books/popular?limit=12', { signal }), request<CategoriesResponse>('/api/books/categories', { signal }),
    ])
    return { ...home, featured: featured.results.map(book => globalDisplayBook(book, id)), new_arrivals: arrivals.results.map(book => globalDisplayBook(book, id)),
      for_you: candidates.length ? candidates.slice(0, 10).map(book => globalDisplayBook({ ...book, authors: book.authors || '', subjects: book.subjects || '', book_id: book.book_id || 0 }, id)) : popular.results.slice(0, 10).map(book => globalDisplayBook(book, id)),
      popular: popular.results.map(book => globalDisplayBook(book, id)), subjects: subjects.categories.map(row => ({ subject: row.name, count: row.count,
        preview_book: row.preview_book ? globalDisplayBook({ ...row.preview_book, authors: row.preview_book.authors || '' }, id) : null })) }
  }
  if (operation === 'books') {
    const page = await institutionApi<CataloguePage>(`${base}/books?${params}`, 'GET', undefined, signal); checkSource(page.source, id)
    if (page.source.catalogue_source !== 'LIBRARY_LOCAL') return globalPage(id, page.source, params, signal)
    if (params.get('view') !== 'for-you') return page
    const candidates = await recommendationCandidates(signal)
    const scoped = await institutionApi<{source:CatalogueSource;results:DisplayBook[]}>(`${base}/recommendations`,'POST',{work_ids:candidates.map(b=>b.work_id),limit:50},signal)
    checkSource(scoped.source,id)
    if (scoped.source.catalogue_source !== 'LIBRARY_LOCAL') throw new Error('Catalogue collection changed. Refresh to load this library.')
    const rows = scoped.results.filter(book => (!params.get('subject') || book.subjects.includes(params.get('subject')!)) &&
      (!params.get('author') || book.authors.join('; ').toLowerCase().includes(params.get('author')!.toLowerCase())) &&
      (!params.get('circulation_status') || book.circulation_status === params.get('circulation_status')) &&
      (!params.get('search') || `${book.title} ${book.authors.join(' ')} ${book.subjects.join(' ')}`.toLowerCase().includes(params.get('search')!.toLowerCase())))
    const offset=Number(params.get('offset') || 0)
    return {source:scoped.source,results:rows.slice(offset,offset+20),total:rows.length,offset,limit:20,has_more:offset+20<rows.length}
  }
  if (operation === 'genres') {
    const page = await institutionApi<GenrePage>(`${base}/genres?${params}`, 'GET', undefined, signal); checkSource(page.source, id)
    if (page.source.catalogue_source === 'LIBRARY_LOCAL') return page
    const response = await request<CategoriesResponse>('/api/books/categories', { signal }), offset = Number(params.get('offset') || 0)
    const results = response.categories.slice(offset, offset + 50).map(row => ({ subject: row.name, count: row.count }))
    return { ...page, results, total: response.categories.length, has_more: offset + results.length < response.categories.length, offset }
  }
  const result = await institutionApi<{ source: CatalogueSource; book: DisplayBook | null }>(`${base}/${operation === 'detail' ? 'books' : 'global-books'}/${encodeURIComponent(params.get('id') || '')}`, 'GET', undefined, signal)
  checkSource(result.source, id)
  if (result.book) return { ...result, book: result.book }
  if (operation === 'detail') throw new Error('Book is not held by this library.')
  const book = await request<BackendBook>(`/api/books/${encodeURIComponent(params.get('id') || '')}`, { signal })
  return { source: result.source, book: globalDisplayBook(book, id) }
}
