import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useAuthStore } from '../store/useAuthStore'
import { categories, eventApi, eventDate, type LibraryEvent } from '../lib/events'
import { EventIcon, EventMeta, RelatedBook, EventSkeleton } from '../components/events/EventUI'
import './Events.css'

export function EventDetailPage() {
  const { eventId = '' } = useParams(), token = useAuthStore(s => s.token), role = useAuthStore(s => s.user?.role)
  const [retry, setRetry] = useState(0), [result, setResult] = useState<{ key: string; event?: LibraryEvent; error?: string }>({ key: '' })
  const key = `${token}:${eventId}:${retry}`
  useEffect(() => {
    const controller = new AbortController()
    void eventApi.detail(eventId, false, controller.signal).then(event => { if (!controller.signal.aborted && useAuthStore.getState().token === token) setResult({ key, event }) }).catch(e => { if (!controller.signal.aborted) setResult({ key, error: e instanceof Error ? e.message : 'Event unavailable.' }) })
    return () => controller.abort()
  }, [eventId, token, key])
  const event = result.key === key ? result.event : undefined, error = result.key === key ? result.error : undefined
  return <div className="events-shell event-detail"><Link className="event-link" to="/events">← All events</Link>{error ? <div role="alert" className="event-empty"><p>{error}</p><button className="event-button" onClick={() => setRetry(v => v + 1)}>Retry</button></div> : !event ? <EventSkeleton /> : <>
    <header className="events-heading"><div><div className="event-card-top"><span className="event-icon"><EventIcon category={event.category} /></span><span className="event-category">{categories[event.category]}</span>{event.featured && <span className="event-tag">Featured</span>}</div><h1>{event.title}</h1><p>{event.summary}</p></div>{(role === 'ADMIN' || role === 'LIBRARIAN') && <Link className="event-button" to={'/staff/events/' + event.event_id + '/edit'}>Edit event</Link>}</header>
    {event.status === 'CANCELLED' && <div role="status" className="event-cancelled"><strong>Cancelled</strong><p>This event has been cancelled. Please do not attend the original program.</p></div>}
    <EventMeta event={event} /><div className="event-description">{event.description || 'More details will be shared by library staff.'}</div>
    {event.related_books.length > 0 && <section className="event-related"><span className="event-eyebrow">EXPLORE THE CATALOGUE</span><h2>{event.category === 'NEW_ARRIVALS' ? 'New this week' : 'Related books'}</h2><div className="event-books">{event.related_books.map(book => <RelatedBook key={book.work_id} book={book} />)}</div></section>}
    {!!event.missing_related_work_ids?.length && <p className="event-muted">Some linked books are no longer in the catalogue.</p>}
    <p className="event-muted">Published {eventDate(event.published_at)}</p>
  </>}</div>
}
