import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { test, beforeEach, afterEach } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'
registerHooks({ load(url, context, nextLoad) { return url.endsWith('.css') ? { format: 'module', source: '', shortCircuit: true } : nextLoad(url, context) } })
const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
Object.assign(globalThis, { FormData: dom.window.FormData })
dom.window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
dom.window.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
const { render, screen, fireEvent, waitFor, cleanup, act, within } = await import('@testing-library/react')
const { MemoryRouter, Routes, Route } = await import('react-router-dom')
const { EventsPage } = await import('../src/pages/EventsPage.tsx')
const { EventDetailPage } = await import('../src/pages/EventDetailPage.tsx')
const { ManageEventsPage } = await import('../src/pages/ManageEventsPage.tsx')
const { EventEditorPage } = await import('../src/pages/EventEditorPage.tsx')
const { Header } = await import('../src/components/Header.tsx')
const { EventMonitor } = await import('../src/components/events/EventMonitor.tsx')
const { ToastContainer } = await import('../src/components/Toast.tsx')
const { useAuthStore: auth } = await import('../src/store/useAuthStore.ts')
const { useEventStore: events } = await import('../src/store/useEventStore.ts')
const { eventDelta } = await import('../src/lib/events.ts')
const { default: ProtectedRoute } = await import('../src/components/ProtectedRoute.tsx')
import type { LibraryEvent, UnseenEvents } from '../src/lib/events.ts'
const id = '12345678-1234-4123-8123-123456789012'
function event(fields: Partial<LibraryEvent> = {}): LibraryEvent { return { event_id: id, title: 'Library Workshop', category: 'WORKSHOP', summary: 'Learn together.', description: 'Workshop description.', status: 'PUBLISHED', featured: true, start_at: null, end_at: null, location: 'Main hall', related_work_ids: ['OL1W'], related_books: [{ work_id: 'OL1W', title: 'Dracula', authors: 'Bram Stoker' }], created_at: '2026-10-06T10:00:00Z', updated_at: '2026-10-06T10:00:00Z', published_at: '2026-10-06T10:00:00Z', created_by: { email: 'test@test.invalid' }, ...fields } }
let calls: { url: string; method: string; body: any }[] = [], rows: LibraryEvent[] = [], unseen: UnseenEvents, original: typeof fetch
let handler: ((url: string, method: string, body: any) => unknown) | null
function user(role: 'GENERAL_USER' | 'LIBRARIAN' | 'ADMIN' = 'GENERAL_USER', token = 'token-a') { localStorage.setItem('luminar_token', token); localStorage.setItem('luminar_user', JSON.stringify({ user_id: 1, role, email: 'test@test.invalid' })); auth.setState({ user: { user_id: 1, role, email: 'test@test.invalid' }, token, isAuthenticated: true }) }
beforeEach(() => {
  user(); events.setState({ scope: 'token-a', count: 0, revision: 0 }); calls = []; rows = [event()]; handler = null
  unseen = { count: 1, count_capped: false, event_ids: [id], seen_cursor: 'receipt', latest_event: event() }
  original = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    const path = String(url), method = options.method || 'GET', body = options.body ? JSON.parse(String(options.body)) : null
    calls.push({ url: path, method, body })
    let result = handler?.(path, method, body)
    if (result === undefined) {
      if (path.includes('/notifications')) result = { notifications: [], count: 0, unread_count: 0 }
      else if (path.includes('/books/capabilities')) result = { books: [] }
      else if (path.includes('/events/unseen')) result = unseen
      else if (path.includes('/events/mark-seen')) result = { ...unseen, count: 0, latest_event: null, event_ids: [] }
      else if (path.includes('/search')) result = { results: Array.from({ length: 13 }, (_, i) => ({ work_id: `OL${i + 1}W`, title: `Book ${i + 1}`, authors: 'Author' })) }
      else if (method === 'DELETE') result = { deleted: true }
      else if (method !== 'GET') result = event({ ...body, status: path.endsWith('/publish') ? 'PUBLISHED' : path.endsWith('/cancel') ? 'CANCELLED' : path.endsWith('/archive') ? 'ARCHIVED' : 'DRAFT' })
      else if (path.includes('/events/' + id)) result = rows[0]
      else result = { events: rows, count: rows.length, page: 1, page_size: 12, has_more: false, seen_cursor: 'receipt' }
    }
    return new Response(JSON.stringify(result), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }
})
afterEach(() => { cleanup(); globalThis.fetch = original })
function mount(path = '/events', header = false, monitor = false) { return render(<MemoryRouter initialEntries={[path]}>{header && <Header />}{monitor && <><EventMonitor /><ToastContainer /></>}<Routes><Route path="/events" element={<EventsPage />} /><Route path="/events/:eventId" element={<EventDetailPage />} /><Route path="/staff/events" element={<ManageEventsPage />} /><Route path="/staff/events/new" element={<EventEditorPage />} /><Route path="/staff/events/:eventId/edit" element={<EventEditorPage />} /><Route path="/book/:workId" element={<p>Book Detail destination</p>} /></Routes></MemoryRouter>) }
async function loaded() { await screen.findByText('Library Workshop') }

test('events_header_button_routes and badge caps on desktop', async () => { events.setState({ scope: 'token-a', count: 12 }); mount('/events', true); const link = screen.getByRole('link', { name: 'Events, 12 new' }); assert.equal(link.getAttribute('href'), '/events'); assert.ok(link.textContent?.includes('9+')); fireEvent.click(link); await loaded() })
test('events_badge_hidden_when_zero', () => { mount('/events', true); assert.equal(screen.queryByText('9+'), null); assert.equal(screen.getByRole('link', { name: 'Events' }).getAttribute('href'), '/events') })
test('mobile_events_header_badge uses existing menu', () => { events.setState({ scope: 'token-a', count: 3 }); mount('/events', true); fireEvent.click(screen.getByRole('button', { name: /menu/i })); const links = screen.getAllByRole('link', { name: /Events/ }); assert.equal(links.length, 2); assert.ok(links[1].textContent?.includes('3')) })
test('general_user_no_create_button and upcoming page mark receipt', async () => { mount(); await loaded(); assert.equal(screen.queryByRole('link', { name: 'Create Event' }), null); await waitFor(() => assert.ok(calls.some(c => c.url.endsWith('/events/mark-seen') && c.body.cursor === 'receipt'))); assert.equal(screen.getByRole('button', { name: 'Upcoming' }).getAttribute('aria-pressed'), 'true') })
for (const role of ['ADMIN', 'LIBRARIAN'] as const) test(`${role} create and manage links`, async () => { user(role); mount(); await loaded(); assert.equal(screen.getByRole('link', { name: 'Create Event' }).getAttribute('href'), '/staff/events/new'); assert.ok(screen.getByRole('link', { name: 'Manage Events' })) })
test('events_page_past and filters preserve backend URL', async () => { mount('/events?page=2'); await loaded(); fireEvent.click(screen.getByRole('button', { name: 'Past' })); await waitFor(() => assert.ok(calls.some(c => c.url.includes('view=past') && !c.url.includes('page=2')))); fireEvent.change(screen.getByLabelText('Event category'), { target: { value: 'BOOK_SALE' } }); await waitFor(() => assert.ok(calls.some(c => c.url.includes('category=BOOK_SALE')))); fireEvent.change(screen.getByLabelText('Search events'), { target: { value: 'Sale' } }); fireEvent.click(screen.getByRole('button', { name: 'Search' })); await waitFor(() => assert.ok(calls.some(c => c.url.includes('query=Sale')))) })
for (const [path, message] of [['/events','No upcoming events right now.'], ['/events?view=past','No past events to show.'], ['/events?query=missing','No events match your filters.']]) test(`event_empty_state ${path}`, async () => { rows = []; mount(path); await screen.findByText(message) })
test('event_detail and related_book_navigation, cancellation clear', async () => { rows = [event({ status: 'CANCELLED' })]; mount('/events/' + id); await loaded(); assert.ok(screen.getByText('Cancelled')); fireEvent.click(screen.getByRole('link', { name: /Dracula/ })); await screen.findByText('Book Detail destination') })
test('event_delta ignores login backlog and deduplicates', () => { const seen = new Set<string>(); assert.equal(eventDelta(seen, unseen, false), null); assert.equal(eventDelta(seen, unseen, true), null); const fresh = { ...unseen, event_ids: [id, 'new'], latest_event: { ...unseen.latest_event!, event_id: 'new' } }; assert.equal(eventDelta(seen, fresh, true)?.event_id, 'new'); assert.equal(eventDelta(seen, fresh, true), null) })
test('new_event_toast uses existing framework once; login backlog silent', async () => { mount('/events', false, true); await loaded(); await waitFor(() => assert.ok(calls.some(c => c.url.endsWith('/events/unseen')))); assert.equal(screen.queryByText('New library event'), null); unseen = { ...unseen, count: 2, event_ids: [id, 'new'], latest_event: { ...unseen.latest_event!, event_id: 'new', title: 'New Book Sale' } }; await act(async () => window.dispatchEvent(new Event('focus'))); await screen.findByText('New library event'); assert.equal(screen.getByRole('link', { name: 'View Event' }).getAttribute('href'), '/events/new'); await act(async () => window.dispatchEvent(new Event('focus'))); await waitFor(() => assert.equal(screen.getAllByText('New library event').length, 1)) })
test('account switch hides prior badge and scoped event toast', async () => { events.setState({ scope: 'token-a', count: 3 }); mount('/events', true); await loaded(); await act(async () => user('GENERAL_USER', 'token-b')); assert.equal(screen.queryByRole('link', { name: 'Events, 3 new' }), null) })
async function form() { user('LIBRARIAN'); mount('/staff/events/new'); await screen.findByLabelText('Event title'); fireEvent.change(screen.getByLabelText('Event title'), { target: { value: 'New Books This Week' } }); fireEvent.change(screen.getByLabelText('Event summary'), { target: { value: 'New titles arrived.' } }); fireEvent.change(screen.getByLabelText('Event description'), { target: { value: 'Explore the new collection.' } }) }
test('create_event_form and save_draft never publish implicitly', async () => { await form(); fireEvent.click(screen.getByRole('button', { name: 'Save Draft' })); await waitFor(() => assert.ok(calls.some(c => c.method === 'POST' && c.url.endsWith('/staff/events')))); assert.equal(calls.filter(c => c.url.endsWith('/publish')).length, 0); assert.equal(calls.find(c => c.method === 'POST' && c.url.endsWith('/staff/events'))!.body.category, 'NEW_ARRIVALS') })
test('publish_confirmation requires explicit confirmation', async () => { await form(); await chooseBook(); fireEvent.click(screen.getByRole('button', { name: 'Publish Now' })); await screen.findByRole('dialog', { name: 'Publish this event?' }); assert.equal(calls.filter(c => c.url.endsWith('/publish')).length, 0); fireEvent.click(screen.getByRole('button', { name: 'Publish event' })); await waitFor(() => assert.ok(calls.some(c => c.url.endsWith('/publish')))) })
test('published edit preserves status and uses PATCH', async () => { user('ADMIN'); mount('/staff/events/' + id + '/edit'); const title = await screen.findByLabelText('Event title'); await waitFor(() => assert.equal((title as HTMLInputElement).value, 'Library Workshop')); assert.equal(screen.queryByRole('button', { name: 'Publish Now' }), null); fireEvent.change(title, { target: { value: 'Corrected title' } }); fireEvent.click(screen.getByRole('button', { name: 'Save changes' })); await waitFor(() => assert.ok(calls.some(c => c.method === 'PATCH'))); assert.equal(calls.filter(c => c.url.endsWith('/publish')).length, 0) })
test('staff date validation prevents invalid write', async () => { await form(); fireEvent.change(screen.getByLabelText('Event Type'), { target: { value: 'OTHER' } }); fireEvent.change(screen.getByLabelText('Start date and time'), { target: { value: '2026-10-08T12:00' } }); fireEvent.change(screen.getByLabelText('End date and time'), { target: { value: '2026-10-07T12:00' } }); fireEvent.click(screen.getByRole('button', { name: 'Save Draft' })); await screen.findByRole('alert'); assert.equal(calls.filter(c => c.method === 'POST').length, 0) })
test('related_book_picker order, remove and limit', async () => { await form(); fireEvent.change(screen.getByLabelText('Search catalogue'), { target: { value: 'Books' } }); fireEvent.click(screen.getByRole('button', { name: 'Search catalogue' })); await screen.findByText('Book 13'); for (let i = 0; i < 12; i++) fireEvent.click(screen.getAllByRole('button', { name: 'Select book' }).find(b => !(b as HTMLButtonElement).disabled)!); assert.equal((screen.getByRole('button', { name: 'Select book' }) as HTMLButtonElement).disabled, true); await screen.findByText('Select no more than 12 related books.'); fireEvent.click(screen.getByRole('button', { name: 'Remove Book 1' })); fireEvent.click(screen.getByRole('button', { name: 'Save Draft' })); await waitFor(() => assert.ok(calls.some(c => c.method === 'POST' && c.url.endsWith('/staff/events')))); assert.deepEqual(calls.find(c => c.url.endsWith('/staff/events') && c.method === 'POST')!.body.related_work_ids, Array.from({ length: 11 }, (_, i) => 'OL' + (i + 2) + 'W')) })
for (const [status, button, action] of [['DRAFT','Publish','publish'],['DRAFT','Delete Draft','delete'],['PUBLISHED','Cancel Event','cancel'],['CANCELLED','Archive','archive']] as const) test(`manage ${action} explicit confirmation`, async () => { user('ADMIN'); rows = [event({ status })]; mount('/staff/events'); await loaded(); fireEvent.click(screen.getByRole('button', { name: button })); await screen.findByRole('dialog'); assert.equal(calls.filter(c => c.method !== 'GET').length, 0); fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: action === 'delete' ? 'Delete Draft' : action === 'publish' ? 'Publish event' : action === 'cancel' ? 'Cancel event' : 'Archive event' })); await waitFor(() => assert.ok(calls.some(c => action === 'delete' ? c.method === 'DELETE' : c.url.endsWith('/' + action)))) })
test('manage_events_statuses and archived history has no writes', async () => { user('ADMIN'); rows = [event({ status: 'ARCHIVED' })]; mount('/staff/events'); await loaded(); assert.ok(screen.getByText('History retained')); assert.equal(screen.queryByRole('button', { name: 'Publish' }), null); fireEvent.change(screen.getByLabelText('Event status'), { target: { value: 'DRAFT' } }); await waitFor(() => assert.ok(calls.some(c => c.url.includes('status=DRAFT')))) })

test('general user management deep link is blocked by existing role guard', async () => {
  render(<MemoryRouter initialEntries={['/staff/events/new']}><Routes><Route path="/staff/events/new" element={<ProtectedRoute allowedRoles={['ADMIN','LIBRARIAN']}><EventEditorPage /></ProtectedRoute>} /><Route path="/" element={<p>Reader destination</p>} /><Route path="/profile" element={<p>Reader destination</p>} /></Routes></MemoryRouter>)
  assert.equal(screen.queryByLabelText('Event title'), null)
  assert.equal(calls.filter(c => c.url.includes('/staff/events')).length, 0)
})

test('failed events load offers retry and succeeds without discarding filters', async () => {
  let failed = true
  globalThis.fetch = async (url, options) => {
    if (String(url).includes('/events?')) {
      if (failed) return Response.json({detail:'Temporary unavailable'}, {status:503})
      return Response.json({events:rows,count:1,page:1,page_size:12,has_more:false})
    }
    return original(url,options)
  }
  mount('/events?category=WORKSHOP')
  await screen.findByRole('alert'); failed=false
  fireEvent.click(screen.getByRole('button', {name:'Retry'})); await loaded()
  assert.equal((screen.getByLabelText('Event category') as HTMLSelectElement).value,'WORKSHOP')
})

test('late events response after account switch cannot change new account content', async () => {
  const pending: ((value:Response)=>void)[]=[]
  globalThis.fetch = async () => new Promise(resolve=>pending.push(resolve))
  mount(); await waitFor(()=>assert.equal(pending.length,1))
  await act(async()=>user('GENERAL_USER','token-b'))
  await waitFor(()=>assert.equal(pending.length,2))
  await act(async()=>pending[0](Response.json({events:[event({title:'Old account page'})],count:1,page:1,page_size:12})))
  assert.equal(screen.queryByText('Old account page'),null)
  await act(async()=>pending[1](Response.json({events:[event({title:'New account page'})],count:1,page:1,page_size:12})))
  await screen.findByText('New account page')
})

test('older poll cannot restore unseen badge after page acknowledgement', async () => {
  let resolvePoll: (value: Response) => void = () => {}
  let reads=0
  globalThis.fetch = async () => {
    reads++
    if (reads===1) return new Promise(resolve=>{resolvePoll=resolve})
    return Response.json({...unseen,count:0,event_ids:[],latest_event:null})
  }
  render(<MemoryRouter><EventMonitor /><ToastContainer /></MemoryRouter>)
  await waitFor(()=>assert.equal(reads,1))
  await act(async()=>events.getState().set('token-a',0))
  await act(async()=>resolvePoll(Response.json(unseen)))
  await waitFor(()=>assert.equal(reads,2))
  assert.equal(events.getState().count,0)
  assert.equal(screen.queryByText('New library event'),null)
})

const { EVENT_PRESETS, EVENT_PUBLISH_REQUIREMENTS, publishErrors, baseErrors } = await import('../src/lib/eventPresets.ts')
const { categories } = await import('../src/lib/events.ts')
async function chooseBook() {
  fireEvent.change(screen.getByLabelText('Search catalogue'), { target: { value: 'Books' } })
  fireEvent.click(screen.getByRole('button', { name: 'Search catalogue' }))
  await screen.findByText('Book 1')
  fireEvent.click(screen.getAllByRole('button', { name: 'Select book' })[0])
}
function type(category: string) { fireEvent.change(screen.getByLabelText('Event Type'), { target: { value: category } }) }
test('preset dropdown is first, defaults to New Arrivals and exposes all eleven canonical types', async () => {
  await form()
  const select = screen.getByLabelText('Event Type') as HTMLSelectElement
  assert.equal(select.value, 'NEW_ARRIVALS')
  assert.deepEqual(Array.from(select.options).map(o => o.textContent), Object.values(categories))
  assert.equal(document.querySelector('form.event-editor')?.querySelector('input,select,textarea'), select)
  assert.equal(Object.keys(EVENT_PRESETS).length, 11)
  assert.ok(screen.getByText('What kind of event are you publishing?'))
})
for (const [category, preset] of Object.entries(EVENT_PRESETS)) test(`preset layout and labels ${category}`, async () => {
  await form(); type(category)
  assert.ok(screen.getByText(preset.helper))
  assert.ok(screen.getByLabelText(preset.startLabel))
  assert.ok(screen.getByLabelText(preset.endLabel))
  const picker = document.querySelector('.event-picker')
  assert.equal(Boolean(picker), preset.booksMode !== 'hidden')
  if (picker) assert.ok(picker.querySelector('h2')?.textContent?.startsWith(preset.booksLabel))
  assert.equal(Boolean(document.querySelector('.event-schedule')?.closest('details')), preset.scheduleCollapsed)
  if (preset.booksMode === 'collapsed') assert.ok(picker?.closest('details'))
  if (preset.booksMode === 'prominent') assert.ok(document.querySelector('.event-picker')!.compareDocumentPosition(document.querySelector('.event-schedule')!) & dom.window.Node.DOCUMENT_POSITION_FOLLOWING)
  if (category === 'BOOK_SALE') assert.equal(screen.queryByText(/checkout|payment|buy now/i), null)
})
for (const category of ['NEW_ARRIVALS','READING_CLUB']) test(`${category} blocks empty publication but permits incomplete draft`, async () => {
  await form(); type(category)
  fireEvent.change(screen.getByLabelText('Event summary'), { target: { value: '' } })
  fireEvent.change(screen.getByLabelText('Event description'), { target: { value: '' } })
  fireEvent.click(screen.getByRole('button', { name: 'Publish Now' }))
  await screen.findByRole('alert')
  assert.equal(calls.filter(c => c.method !== 'GET').length, 0)
  fireEvent.click(screen.getByRole('button', { name: /Select at least one/ }))
  assert.equal(document.activeElement?.id, 'event-related_work_ids')
  fireEvent.click(screen.getByRole('button', { name: 'Save Draft' }))
  await waitFor(() => assert.ok(calls.some(c => c.method === 'POST')))
  assert.equal(calls.filter(c => c.url.endsWith('/publish')).length, 0)
})
test('Workshop Notice Workshop preserves title dates location description featured and selected books', async () => {
  await form(); type('WORKSHOP'); await chooseBook()
  fireEvent.change(screen.getByLabelText('Workshop Starts'), { target: { value: '2026-10-15T11:00' } })
  fireEvent.change(screen.getByLabelText('Workshop Ends'), { target: { value: '2026-10-15T12:00' } })
  fireEvent.change(screen.getByLabelText('Event location'), { target: { value: 'Room A' } })
  fireEvent.click(screen.getByLabelText('Featured event'))
  type('LIBRARY_NOTICE'); type('CLOSURE')
  assert.equal(screen.queryByRole('button', { name: 'Search catalogue' }), null)
  type('WORKSHOP')
  assert.equal((screen.getByLabelText('Workshop Starts') as HTMLInputElement).value, '2026-10-15T11:00')
  assert.equal((screen.getByLabelText('Workshop Ends') as HTMLInputElement).value, '2026-10-15T12:00')
  assert.equal((screen.getByLabelText('Event location') as HTMLInputElement).value, 'Room A')
  assert.equal((screen.getByLabelText('Event description') as HTMLTextAreaElement).value, 'Explore the new collection.')
  assert.equal((screen.getByLabelText('Featured event') as HTMLInputElement).checked, true)
  assert.ok(screen.getByRole('button', { name: 'Remove Book 1' }))
  fireEvent.click(screen.getByRole('button', { name: 'Save Draft' }))
  await waitFor(() => assert.ok(calls.some(c => c.method === 'POST')))
  assert.deepEqual(calls.find(c => c.method === 'POST' && c.url.endsWith('/staff/events'))?.body.related_work_ids, ['OL1W'])
})
test('Closure publish validation reports missing end then publishes without books', async () => {
  await form(); type('CLOSURE')
  fireEvent.change(screen.getByLabelText('Closure Starts'), { target: { value: '2026-10-15T10:00' } })
  fireEvent.click(screen.getByRole('button', { name: 'Publish Now' }))
  await screen.findByRole('button', { name: /Reopening or closure end/ })
  assert.equal(calls.filter(c => c.method !== 'GET').length, 0)
  fireEvent.change(screen.getByLabelText('Reopens / Closure Ends'), { target: { value: '2026-10-16T10:00' } })
  fireEvent.click(screen.getByRole('button', { name: 'Publish Now' }))
  await screen.findByRole('dialog', { name: 'Publish this event?' })
})
test('Author uses summary and description for speaker without adding schema fields', async () => {
  await form(); type('AUTHOR_EVENT')
  assert.ok(screen.getByText('Summary / Author or Speaker'))
  assert.ok(screen.getByText('Description / Speaker Details'))
  assert.equal(screen.queryByLabelText('Presenter'), null)
  fireEvent.click(screen.getByRole('button', { name: 'Save Draft' }))
  await waitFor(() => assert.ok(calls.some(c => c.method === 'POST')))
  assert.equal('presenter' in calls.find(c => c.method === 'POST')!.body, false)
})
test('publish summary includes type title dates location and book count', async () => {
  await form(); type('BOOK_SALE')
  fireEvent.change(screen.getByLabelText('Sale Starts'), { target: { value: '2026-10-15T10:00' } })
  fireEvent.change(screen.getByLabelText('Event location'), { target: { value: 'Sale hall' } })
  fireEvent.click(screen.getByRole('button', { name: 'Publish Now' }))
  const dialog = await screen.findByRole('dialog')
  for (const text of ['Book Sale','New Books This Week','Sale Starts','Sale hall','Linked books','0']) assert.ok(within(dialog).getByText(text))
  assert.equal(calls.filter(c => c.url.endsWith('/publish')).length, 0)
})
test('edit preset loads category; published type change requires confirmation and only PATCH', async () => {
  user('LIBRARIAN'); rows = [event({ start_at: '2026-10-15T10:00:00Z' })]
  mount('/staff/events/' + id + '/edit')
  await screen.findByLabelText('Workshop Starts')
  type('LIBRARY_NOTICE')
  await screen.findByRole('dialog', { name: 'Change published event type?' })
  assert.ok(screen.getByText('Change event type from Workshop to Library Notice?'))
  assert.equal((screen.getByLabelText('Event Type') as HTMLSelectElement).value, 'WORKSHOP')
  fireEvent.click(screen.getByRole('button', { name: 'Keep current type' }))
  assert.equal((screen.getByLabelText('Event Type') as HTMLSelectElement).value, 'WORKSHOP')
  type('COMMUNITY_EVENT'); fireEvent.click(screen.getByRole('button', { name: 'Change event type' }))
  assert.equal((screen.getByLabelText('Event Type') as HTMLSelectElement).value, 'COMMUNITY_EVENT')
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
  await waitFor(() => assert.ok(calls.some(c => c.method === 'PATCH')))
  assert.equal(calls.find(c => c.method === 'PATCH')!.body.category, 'COMMUNITY_EVENT')
  assert.equal(calls.filter(c => c.url.endsWith('/publish')).length, 0)
})
test('published category with unmet requirements cannot be saved', async () => {
  user('LIBRARIAN'); mount('/staff/events/' + id + '/edit'); await screen.findByLabelText('Event Type')
  type('CLOSURE'); fireEvent.click(screen.getByRole('button', { name: 'Change event type' }))
  fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
  await screen.findByRole('alert'); assert.equal(calls.filter(c => c.method === 'PATCH').length, 0)
})
test('preset shared requirement contract contains exactly the canonical categories', () => {
  assert.deepEqual(Object.keys(EVENT_PUBLISH_REQUIREMENTS), Object.keys(categories))
  for (const category of Object.keys(categories) as (keyof typeof categories)[]) {
    const input = { ...event({ category }), related_work_ids: [] }
    const errors = publishErrors(input)
    assert.equal(errors.some(e => e.field === 'related_work_ids'), EVENT_PUBLISH_REQUIREMENTS[category].min_books > 0)
  }
  assert.ok(baseErrors({ ...event(), title: '  ' }).some(e => e.field === 'title'))
})
