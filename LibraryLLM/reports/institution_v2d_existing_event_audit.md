# Existing event path audit

Existing Events V1 uses the global events collection, immutable UUIDs, category presets, revision-checked atomic transitions, first-publication timestamps, bounded listing and account seen receipts. /platform/events requires explicit PlatformRoleAssignment. No tenant event routes, library_id or member visibility exist. The single local legacy event remains LEGACY_GLOBAL; migration requires an explicit GLOBAL decision. Existing useful fields and design are reused. No event mass fanout is introduced.

Baseline: `institution_v2d_baseline.json`; source copies captured before changes. Every matching production call site below is classified. Migration and QA scripts are classified separately by their dry-run/test purpose.

| File | Line | Classification | Existing path/call |
|---|---:|---|---|
| backend/main.py | 48 | LEGACY_GLOBAL | `from backend.services.event_service import ensure_indexes as ensure_event_indexes` |
| backend/routes/events.py | 8 | LEGACY_GLOBAL | `from backend.services import event_service as service` |
| backend/routes/events.py | 19 | LEGACY_GLOBAL | `router=APIRouter(prefix='/events',tags=['Events'])` |
| backend/routes/events.py | 20 | GLOBAL_PLATFORM | `staff_router=APIRouter(prefix='/platform/events',tags=['Staff events'],dependencies=[Depends(staff)])` |
| frontend/src/App.tsx | 40 | LEGACY_GLOBAL | `import { EventsPage } from '@/pages/EventsPage'` |
| frontend/src/App.tsx | 41 | LEGACY_GLOBAL | `import { EventDetailPage } from '@/pages/EventDetailPage'` |
| frontend/src/App.tsx | 42 | LEGACY_GLOBAL | `import { ManageEventsPage } from '@/pages/ManageEventsPage'` |
| frontend/src/App.tsx | 43 | LEGACY_GLOBAL | `import { EventEditorPage } from '@/pages/EventEditorPage'` |
| frontend/src/App.tsx | 44 | LEGACY_GLOBAL | `import { EventMonitor } from '@/components/events/EventMonitor'` |
| frontend/src/App.tsx | 54 | GLOBAL_PLATFORM | `function LegacyEventRedirect() { const { eventId = '' } = useParams(); return <Navigate to={'/platform/events/' + encodeURIComponent(eventId) + '/edit'} replace /> }` |
| frontend/src/App.tsx | 120 | LEGACY_GLOBAL | `<Route path="/events" element={<ProtectedRoute><EventsPage /></ProtectedRoute>} />` |
| frontend/src/App.tsx | 121 | LEGACY_GLOBAL | `<Route path="/events/:eventId" element={<ProtectedRoute><EventDetailPage /></ProtectedRoute>} />` |
| frontend/src/App.tsx | 131 | LEGACY_GLOBAL | `<Route path="events" element={<ManageEventsPage />} />` |
| frontend/src/App.tsx | 132 | LEGACY_GLOBAL | `<Route path="events/new" element={<EventEditorPage />} />` |
| frontend/src/App.tsx | 133 | LEGACY_GLOBAL | `<Route path="events/:eventId/edit" element={<EventEditorPage />} />` |
| frontend/src/App.tsx | 136 | GLOBAL_PLATFORM | `<Route path="/staff/events" element={<Navigate to="/platform/events" replace />} />` |
| frontend/src/App.tsx | 137 | GLOBAL_PLATFORM | `<Route path="/staff/events/new" element={<Navigate to="/platform/events/new" replace />} />` |
| frontend/src/App.tsx | 138 | LEGACY_GLOBAL | `<Route path="/staff/events/:eventId/edit" element={<LegacyEventRedirect />} />` |
| frontend/src/App.tsx | 287 | LEGACY_GLOBAL | `<EventMonitor />` |
| frontend/src/components/Footer.tsx | 6 | LEGACY_GLOBAL | `const links=[{label:'Catalog',to:context.cataloguePath},{label:'New Arrivals',to:context.libraryId ? '/libraries/'+context.libraryId+'/new-arrivals' : context.personalPath('/catalog?sort=new_arrivals')},{label:'Reading List',to:context.personalPath('/reading-list')},{label:'My Libraries',to:context.personalPath('/account/libraries')},{label:'Events & Announc` |
| frontend/src/components/Header.tsx | 14 | LEGACY_GLOBAL | `const links = [{ label: 'Graph Lab', to: '/experimental/kg' }, { label: 'Catalog', to: '/catalog' }, { label: 'New Arrivals', to: '/#new-arrivals' }, { label: 'Events', to: '/events' }, { label: 'About', to: '/#about' }, { label: 'Know More', to: '/llm' }]` |
| frontend/src/components/events/EventMonitor.tsx | 4 | LEGACY_GLOBAL | `import { eventApi, eventDelta, EVENTS_CHANGED } from '../../lib/events'` |
| frontend/src/components/events/EventMonitor.tsx | 9 | LEGACY_GLOBAL | `export function EventMonitor() {` |
| frontend/src/components/events/EventMonitor.tsx | 23 | LEGACY_GLOBAL | `const data = await eventApi.unseen(controller.signal)` |
| frontend/src/components/events/EventMonitor.tsx | 31 | LEGACY_GLOBAL | `if (fresh) showToast(fresh.title, 'info', { title: 'New library event', href: '/events/' + fresh.event_id, actionLabel: 'View Event', durationMs: 7000, scope: token })` |
| frontend/src/components/events/EventPublishSummary.tsx | 1 | LEGACY_GLOBAL | `import { categories, eventDate, type EventInput } from '../../lib/events'` |
| frontend/src/components/events/EventUI.tsx | 6 | LEGACY_GLOBAL | `import { categories, eventDate, author, type EventBook, type LibraryEvent, type EventCategory } from '../../lib/events'` |
| frontend/src/components/events/EventUI.tsx | 17 | LEGACY_GLOBAL | `return <article className={`event-card ${event.featured ? 'is-featured' : ''}`}><div className="event-card-top"><span className="event-icon"><EventIcon category={event.category} /></span><span className="event-category">{categories[event.category]}</span>{event.featured && <span className="event-tag">Featured</span>}</div><h2><Link to={context.personalPath('` |
| frontend/src/lib/eventPresets.ts | 2 | LEGACY_GLOBAL | `import type { EventCategory, EventInput } from './events'` |
| frontend/src/lib/events.ts | 18 | LEGACY_GLOBAL | `list: (query = '', signal?: AbortSignal) => coreRequest<EventPage>(`/events${query ? '?' + query : ''}`, { signal }),` |
| frontend/src/lib/events.ts | 19 | GLOBAL_PLATFORM | `detail: (id: string, staff = false, signal?: AbortSignal) => coreRequest<LibraryEvent>(`${staff ? '/platform' : ''}/events/${encodeURIComponent(id)}`, { signal }),` |
| frontend/src/lib/events.ts | 20 | GLOBAL_PLATFORM | `manage: (query = '', signal?: AbortSignal) => coreRequest<EventPage>(`/platform/events${query ? '?' + query : ''}`, { signal }),` |
| frontend/src/lib/events.ts | 21 | LEGACY_GLOBAL | `unseen: (signal?: AbortSignal) => coreRequest<UnseenEvents>('/events/unseen', { signal }),` |
| frontend/src/lib/events.ts | 22 | LEGACY_GLOBAL | `seen: (cursor: string, signal?: AbortSignal) => coreRequest<UnseenEvents>('/events/mark-seen', { method: 'POST', body: JSON.stringify({ cursor }), signal }),` |
| frontend/src/lib/events.ts | 23 | GLOBAL_PLATFORM | `create: (data: EventInput) => coreRequest<LibraryEvent>('/platform/events', { method: 'POST', body: JSON.stringify(data) }),` |
| frontend/src/lib/events.ts | 24 | GLOBAL_PLATFORM | `edit: (id: string, data: EventInput) => coreRequest<LibraryEvent>(`/platform/events/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(data) }),` |
| frontend/src/lib/events.ts | 25 | GLOBAL_PLATFORM | `action: (id: string, action: 'publish' \| 'cancel' \| 'archive' \| 'delete') => coreRequest<LibraryEvent \| { deleted: boolean }>(`/platform/events/${encodeURIComponent(id)}${action === 'delete' ? '' : '/' + action}`, { method: action === 'delete' ? 'DELETE' : 'POST' }),` |
| frontend/src/pages/EventDetailPage.tsx | 6 | LEGACY_GLOBAL | `import { categories, eventApi, eventDate, type LibraryEvent } from '../lib/events'` |
| frontend/src/pages/EventDetailPage.tsx | 7 | LEGACY_GLOBAL | `import { EventIcon, EventMeta, RelatedBook, EventSkeleton } from '../components/events/EventUI'` |
| frontend/src/pages/EventDetailPage.tsx | 10 | LEGACY_GLOBAL | `export function EventDetailPage() {` |
| frontend/src/pages/EventDetailPage.tsx | 17 | LEGACY_GLOBAL | `void eventApi.detail(eventId, false, controller.signal).then(event => { if (!controller.signal.aborted && useAuthStore.getState().token === token) setResult({ key, event }) }).catch(e => { if (!controller.signal.aborted) setResult({ key, error: e instanceof Error ? e.message : 'Event unavailable.' }) })` |
| frontend/src/pages/EventDetailPage.tsx | 21 | LEGACY_GLOBAL | `return <div className="events-shell event-detail"><Link className="event-link" to={context.personalPath('/events')}>← All events</Link>{error ? <div role="alert" className="event-empty"><p>{error}</p><button className="event-button" onClick={() => setRetry(v => v + 1)}>Retry</button></div> : !event ? <EventSkeleton /> : <>` |
| frontend/src/pages/EventDetailPage.tsx | 22 | GLOBAL_PLATFORM | `<header className="events-heading"><div><div className="event-card-top"><span className="event-icon"><EventIcon category={event.category} /></span><span className="event-category">{categories[event.category]}</span>{event.featured && <span className="event-tag">Featured</span>}</div><h1>{event.title}</h1><p>{event.summary}</p></div>{canManage && <Link classN` |
| frontend/src/pages/EventEditorPage.tsx | 4 | LEGACY_GLOBAL | `import { categories, eventApi, author, EVENTS_CHANGED, type EventInput, type EventBook, type EventCategory, type LibraryEvent } from '../lib/events'` |
| frontend/src/pages/EventEditorPage.tsx | 8 | LEGACY_GLOBAL | `import { EventPublishSummary } from '../components/events/EventPublishSummary'` |
| frontend/src/pages/EventEditorPage.tsx | 10 | LEGACY_GLOBAL | `import { EventSkeleton, EventIcon } from '../components/events/EventUI'` |
| frontend/src/pages/EventEditorPage.tsx | 25 | LEGACY_GLOBAL | `export function EventEditorPage() {` |
| frontend/src/pages/EventEditorPage.tsx | 35 | LEGACY_GLOBAL | `void (eventId ? eventApi.detail(eventId, true, controller.signal) : Promise.resolve(null)).then(event => {` |
| frontend/src/pages/EventEditorPage.tsx | 64 | LEGACY_GLOBAL | `const event = savedId ? await eventApi.edit(savedId, payload) : await eventApi.create(payload)` |
| frontend/src/pages/EventEditorPage.tsx | 67 | GLOBAL_PLATFORM | `if (andPublish) setPublish(true); else navigate('/platform/events')` |
| frontend/src/pages/EventEditorPage.tsx | 74 | GLOBAL_PLATFORM | `try { await eventApi.action(savedId, 'publish'); if (useAuthStore.getState().token !== token) return; window.dispatchEvent(new Event(EVENTS_CHANGED)); navigate('/platform/events') }` |
| frontend/src/pages/EventEditorPage.tsx | 89 | GLOBAL_PLATFORM | `<Link className="event-link" to="/platform/events">← Manage Events</Link>` |
| frontend/src/pages/EventEditorPage.tsx | 106 | GLOBAL_PLATFORM | `<div className="events-actions"><button className="event-button primary" disabled={disabled}>{busy ? 'Saving…' : loaded && loaded.status !== 'DRAFT' ? 'Save changes' : 'Save Draft'}</button>{(!loaded \|\| loaded.status === 'DRAFT') && <button type="button" className="event-button" disabled={disabled} onClick={() => void save(true)}>Publish Now</button>}<Link` |
| frontend/src/pages/EventsPage.tsx | 6 | LEGACY_GLOBAL | `import { categories, eventApi, type EventPage } from '../lib/events'` |
| frontend/src/pages/EventsPage.tsx | 7 | LEGACY_GLOBAL | `import { EventCard, EventSkeleton, EventPager } from '../components/events/EventUI'` |
| frontend/src/pages/EventsPage.tsx | 10 | LEGACY_GLOBAL | `export function EventsPage() {` |
| frontend/src/pages/EventsPage.tsx | 19 | LEGACY_GLOBAL | `void eventApi.list(query, controller.signal).then(async data => {` |
| frontend/src/pages/EventsPage.tsx | 24 | LEGACY_GLOBAL | `try { const seen = await eventApi.seen(data.seen_cursor, controller.signal); if (!controller.signal.aborted && useAuthStore.getState().token === token) useEventStore.getState().set(token \|\| '', seen.count) }` |
| frontend/src/pages/EventsPage.tsx | 32 | GLOBAL_PLATFORM | `return <div className="events-shell"><header className="events-heading"><div><span className="event-eyebrow">LUMINAR EVENTS</span><h1>Events &amp; Announcements</h1><p>Discover what’s happening at the library.</p></div>{canManage && <div className="events-actions"><Link className="event-button" to="/platform/events">Manage Events</Link><Link className="event` |
| frontend/src/pages/ManageEventsPage.tsx | 4 | LEGACY_GLOBAL | `import { eventApi, eventDate, categories, EVENTS_CHANGED, type EventPage, type LibraryEvent } from '../lib/events'` |
| frontend/src/pages/ManageEventsPage.tsx | 5 | LEGACY_GLOBAL | `import { EventPager, EventSkeleton } from '../components/events/EventUI'` |
| frontend/src/pages/ManageEventsPage.tsx | 6 | LEGACY_GLOBAL | `import { EventPublishSummary } from '../components/events/EventPublishSummary'` |
| frontend/src/pages/ManageEventsPage.tsx | 10 | LEGACY_GLOBAL | `export function ManageEventsPage() {` |
| frontend/src/pages/ManageEventsPage.tsx | 17 | LEGACY_GLOBAL | `useEffect(() => { const controller = new AbortController(); void eventApi.manage(query, controller.signal).then(data => { if (!controller.signal.aborted && useAuthStore.getState().token === token) setResult({ key, data }) }).catch(e => { if (!controller.signal.aborted) setResult({ key, error: e instanceof Error ? e.message : 'Unable to load events.' }) }); r` |
| frontend/src/pages/ManageEventsPage.tsx | 19 | LEGACY_GLOBAL | `async function action() { if (!confirmation \|\| lock.current) return; lock.current = true; setBusy(true); setError(''); try { await eventApi.action(confirmation.event.event_id, confirmation.action); if (useAuthStore.getState().token !== token) return; setConfirmation(null); setReload(v => v + 1); window.dispatchEvent(new Event(EVENTS_CHANGED)) } catch (e) {` |
| frontend/src/pages/ManageEventsPage.tsx | 21 | GLOBAL_PLATFORM | `return <div className="events-shell"><Link className="event-link" to="/events">← Events &amp; Announcements</Link><header className="events-heading"><div><span className="event-eyebrow">PLATFORM ADMIN</span><h1>Manage Events</h1><p>Prepare announcements, publish programs and keep their history.</p></div><Link className="event-button primary" to="/platform/ev` |
| frontend/src/pages/ManageEventsPage.tsx | 24 | GLOBAL_PLATFORM | `{!data && !(result.key === key && result.error) ? <EventSkeleton /> : data && <><div className="event-manage-list">{data.events.map(event => <article className="event-manage-row" key={event.event_id}><div><span className={`event-status ${event.status.toLowerCase()}`}>{event.status}</span>{event.featured && <span className="event-tag">Featured</span>}<h2>{eve` |

Legacy records are preserved; UNKNOWN/AMBIGUOUS provenance requires explicit operator review. New LIBRARY_TENANT routes and journal intents are documented in the final architecture reports.
