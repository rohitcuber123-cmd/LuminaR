import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuthStore } from '../store/useAuthStore'
import { useEventStore } from '../store/useEventStore'
import { categories, eventApi, type EventPage } from '../lib/events'
import { EventCard, EventSkeleton, EventPager } from '../components/events/EventUI'
import './Events.css'

export function EventsPage() {
  const [params, setParams] = useSearchParams()
  const token = useAuthStore(s => s.token), role = useAuthStore(s => s.user?.role)
  const [retry, setRetry] = useState(0), [search, setSearch] = useState(params.get('query') || '')
  const [result, setResult] = useState<{ key: string; data?: EventPage; error?: string }>({ key: '' })
  const query = params.toString(), key = `${token}:${query}:${retry}`
  const page = Math.max(1, Number(params.get('page')) || 1), view = params.get('view') === 'past' ? 'past' : 'upcoming'
  useEffect(() => {
    const controller = new AbortController()
    void eventApi.list(query, controller.signal).then(async data => {
      if (controller.signal.aborted || useAuthStore.getState().token !== token) return
      setResult({ key, data })
      // Mark precisely the receipt from this successful page load, not "now".
      if (data.seen_cursor) {
        try { const seen = await eventApi.seen(data.seen_cursor, controller.signal); if (!controller.signal.aborted && useAuthStore.getState().token === token) useEventStore.getState().set(token || '', seen.count) }
        catch { /* Leave badge intact if mark-seen fails; reading still works. */ }
      }
    }).catch(e => { if (!controller.signal.aborted) setResult({ key, error: e instanceof Error ? e.message : 'Unable to load events.' }) })
    return () => controller.abort()
  }, [query, token, key])
  const data = result.key === key ? result.data : undefined, error = result.key === key ? result.error : undefined
  function filter(name: string, value: string) { const next = new URLSearchParams(params); if (value) next.set(name, value); else next.delete(name); next.delete('page'); setParams(next) }
  return <div className="events-shell"><header className="events-heading"><div><span className="event-eyebrow">AT YOUR LIBRARY</span><h1>Events &amp; Announcements</h1><p>Discover what’s happening at the library.</p></div>{(role === 'ADMIN' || role === 'LIBRARIAN') && <div className="events-actions"><Link className="event-button" to="/staff/events">Manage Events</Link><Link className="event-button primary" to="/staff/events/new">Create Event</Link></div>}</header>
    <div className="event-tabs" aria-label="Event views"><button aria-pressed={view === 'upcoming'} onClick={() => filter('view', 'upcoming')}>Upcoming</button><button aria-pressed={view === 'past'} onClick={() => filter('view', 'past')}>Past</button></div>
    <div className="event-filters"><label>Category<select aria-label="Event category" value={params.get('category') || ''} onChange={e => filter('category', e.target.value)}><option value="">All categories</option>{Object.entries(categories).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><form onSubmit={e => { e.preventDefault(); filter('query', search.trim()) }}><label>Search events<input aria-label="Search events" value={search} maxLength={120} placeholder="Title or announcement…" onChange={e => setSearch(e.target.value)} /></label><button className="event-button" type="submit">Search</button></form></div>
    {error ? <div role="alert" className="event-empty"><p>{error}</p><button className="event-button" onClick={() => setRetry(v => v + 1)}>Retry</button></div> : !data ? <EventSkeleton /> : <>
      {data.events.length ? <div className="event-grid">{data.events.map(event => <EventCard key={event.event_id} event={event} />)}</div> : <div className="event-empty"><h2>{params.get('query') || params.get('category') ? 'No events match your filters.' : view === 'past' ? 'No past events to show.' : 'No upcoming events right now.'}</h2><p>Check back for new library programs and announcements.</p></div>}
      <EventPager page={page} count={data.count} size={data.page_size} change={v => { const next = new URLSearchParams(params); next.set('page', String(v)); setParams(next) }} />
    </>}
  </div>
}
