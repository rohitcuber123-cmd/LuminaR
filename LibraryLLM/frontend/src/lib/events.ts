import { coreRequest } from './api'
export const categories = { NEW_ARRIVALS: 'New Arrivals', BOOK_SALE: 'Book Sale', WORKSHOP: 'Workshop', AUTHOR_EVENT: 'Author Event', READING_CLUB: 'Reading Club', COMMUNITY_EVENT: 'Community Event', LIBRARY_PROGRAM: 'Library Program', LIBRARY_NOTICE: 'Library Notice', CLOSURE: 'Library Closure', EXHIBITION: 'Exhibition', OTHER: 'Other' } as const
export type EventCategory = keyof typeof categories
export type EventStatus = 'DRAFT' | 'PUBLISHED' | 'CANCELLED' | 'ARCHIVED'
export interface EventBook { work_id: string; title?: string | null; authors?: string | string[] | null }
export interface LibraryEvent {
  event_id: string; title: string; category: EventCategory; summary: string; description: string
  start_at: string | null; end_at: string | null; location: string | null; featured: boolean; status: EventStatus
  related_work_ids: string[]; related_books: EventBook[]; missing_related_work_ids?: string[]
  created_at: string; updated_at: string; published_at: string | null
  created_by?: { name?: string; email?: string } | null; updated_by?: { name?: string; email?: string } | null
}
export interface EventPage { events: LibraryEvent[]; count: number; page: number; page_size: number; has_more: boolean; seen_cursor?: string }
export interface UnseenEvents { count: number; count_capped: boolean; event_ids: string[]; seen_cursor: string; latest_event: Pick<LibraryEvent, 'event_id' | 'title' | 'category' | 'published_at'> | null }
export type EventInput = Pick<LibraryEvent, 'title' | 'category' | 'summary' | 'description' | 'start_at' | 'end_at' | 'location' | 'featured' | 'related_work_ids'>
export const EVENTS_CHANGED = 'luminar-events-changed'
export const eventApi = {
  list: (query = '', signal?: AbortSignal) => coreRequest<EventPage>(`/events${query ? '?' + query : ''}`, { signal }),
  detail: (id: string, staff = false, signal?: AbortSignal) => coreRequest<LibraryEvent>(`${staff ? '/staff' : ''}/events/${encodeURIComponent(id)}`, { signal }),
  manage: (query = '', signal?: AbortSignal) => coreRequest<EventPage>(`/staff/events${query ? '?' + query : ''}`, { signal }),
  unseen: (signal?: AbortSignal) => coreRequest<UnseenEvents>('/events/unseen', { signal }),
  seen: (cursor: string, signal?: AbortSignal) => coreRequest<UnseenEvents>('/events/mark-seen', { method: 'POST', body: JSON.stringify({ cursor }), signal }),
  create: (data: EventInput) => coreRequest<LibraryEvent>('/staff/events', { method: 'POST', body: JSON.stringify(data) }),
  edit: (id: string, data: EventInput) => coreRequest<LibraryEvent>(`/staff/events/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(data) }),
  action: (id: string, action: 'publish' | 'cancel' | 'archive' | 'delete') => coreRequest<LibraryEvent | { deleted: boolean }>(`/staff/events/${encodeURIComponent(id)}${action === 'delete' ? '' : '/' + action}`, { method: action === 'delete' ? 'DELETE' : 'POST' }),
}
export function eventDate(value: string | null) { return value ? new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : 'Announcement' }
export function author(book: EventBook) { return Array.isArray(book.authors) ? book.authors.join(', ') : book.authors || 'Author not recorded' }

export function eventDelta(observed: Set<string>, data: UnseenEvents, initialized: boolean) {
  const fresh = initialized && data.latest_event && !observed.has(data.latest_event.event_id) ? data.latest_event : null
  for (const id of data.event_ids) observed.add(id)
  while (observed.size > 1000) observed.delete(observed.values().next().value!)
  return fresh
}
