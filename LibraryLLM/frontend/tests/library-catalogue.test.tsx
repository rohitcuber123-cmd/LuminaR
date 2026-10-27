import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { test, beforeEach, afterEach } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'
import type { DisplayBook, CatalogueHome, CatalogueSource } from '../src/lib/libraryCatalogue'
registerHooks({ load(url, context, nextLoad) { return url.endsWith('.css') ? { format: 'module', source: '', shortCircuit: true } : nextLoad(url, context) } })
const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage,
  HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, FormData: dom.window.FormData, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
dom.window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
dom.window.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
const { render, screen, cleanup, fireEvent, waitFor, act } = await import('@testing-library/react')
const { MemoryRouter, useLocation } = await import('react-router-dom')
const { useAuthStore: auth } = await import('../src/store/useAuthStore')
const { useInstitutionStore: store } = await import('../src/store/useInstitutionStore')
const { usePlatformStore } = await import('../src/store/usePlatformStore')
const { globalDisplayBook, loadCatalogue } = await import('../src/lib/libraryCatalogue')
const { LibraryCatalogueBook, CatalogueCover } = await import('../src/components/LibraryCatalogueBook')
const { LibraryCataloguePage, LibraryCatalogueGenres } = await import('../src/pages/LibraryCatalogue')
const { Home } = await import('../src/pages/Home')
const LibraryCatalogueHome = () => <Home context="library" />
class Observer { observe() {} disconnect() {} unobserve() {} }
Object.assign(globalThis, { ResizeObserver: Observer, IntersectionObserver: Observer })
const { PatronLibraryShell, StaffCatalogueSummary } = await import('../src/components/LibraryShells')
const { Header } = await import('../src/components/Header')
const a = '11111111-1111-4111-8111-111111111111', b = '22222222-2222-4222-8222-222222222222'
const library = (id: string) => ({ library_id: id, name: id === a ? 'Library A' : 'Library B', slug: id, description: null,
  library_type: 'PUBLIC_LIBRARY' as const, access_mode: 'PUBLIC' as const, membership: { membership_id: id, library_id: id, user_id: 1,
    role: 'GENERAL_USER' as const, status: 'ACTIVE' as const, is_owner: false, joined_at: '2026-10-09T00:00:00Z' } })
const source = (id: string, local = true): CatalogueSource => ({ library_id: id, library_name: id === a ? 'Library A' : 'Library B',
  catalogue_source: local ? 'LIBRARY_LOCAL' : 'GLOBAL_FALLBACK', local_book_count: local ? 4 : 0,
  capabilities: { physical_actions: local, reservations: local, local_search: local, global_discovery: !local }, circulation_state: 'CANONICAL', discovery_notice: null })
const local = (id = a, n = 0): DisplayBook => ({ display_id: `${id}-${n}`, library_id: id, library_book_id: `${id}-${n}`, global_work_id: n ? null : 'OL1W',
  title: `${id === a ? 'A' : 'B'} Book ${n}`, authors: ['Ada'], subjects: n < 2 ? ['Networking'] : ['Mathematics'], cover_url: null,
  source: 'LIBRARY', owned_by_current_library: true, accession_number: `LIB-${n}`, shelf_location: `${id === a ? 'A' : 'B'} / Shelf ${n}`,
  circulation_status: 'CIRCULATING', requestable_count: 2, user_request_state: null, user_reservation_state: null, user_loan_state: null,
  actions: { request: true, reserve: false, cancel_request: false, cancel_reservation: false } })
const globalBook = { book_id: 9, work_id: 'OL1W', title: 'Global Atlas', authors: 'Global Author', subjects: 'Networking', shelf_location: 'FAKE SHELF', available_copies: 999, total_copies: 999 }
let original: typeof fetch, calls: { path: string; options?: RequestInit }[], fallback: boolean, failure: boolean, popularity: boolean
function payload(id: string): CatalogueHome {
  const empty = fallback || id === b, books = empty ? [] : Array.from({ length: 4 }, (_, n) => local(id, n))
  return { source: source(id, !empty), featured: books, new_arrivals: [...books].reverse(), popular: popularity ? books.slice(0, 1) : [],
    subjects: empty ? [] : [{ subject: 'Networking', count: 2 }, { subject: 'Mathematics', count: 2 }],
    my_library: { pending_requests: 1, active_loans: 2, waiting_reservations: 0 }, popularity_window_days: 90 }
}
beforeEach(() => {
  localStorage.clear(); localStorage.setItem('luminar_token', 'catalogue-test')
  auth.setState({ token: 'catalogue-test', isAuthenticated: true, user: { user_id: 1, name: 'Account', email: 'account@example.com', role: 'ADMIN' } })
  store.setState({ libraries: [library(a), library(b)], session: 'catalogue-test', activeId: a, patronLibraryId: a, staffLibraryId: null,
    workspace: 'PATRON', loading: false, error: null, owner: 'account@example.com' })
  usePlatformStore.setState({ session: 'catalogue-test', roles: [], loading: false, error: '' })
  original = globalThis.fetch; calls = []; fallback = false; failure = false; popularity = false
  globalThis.fetch = async (url, options) => {
    const path = String(url); calls.push({ path, options })
    if (path.includes('/events?')) return Response.json({ events: [], total: 0, page: 1, page_size: 3 })
    const id = path.includes(b) ? b : a
    if (path.includes('/catalogue/recommendations')) return Response.json({ source: payload(id).source, results: payload(id).featured })
    if (path.startsWith('/recommendation-api')) return Response.json({ recommendations: [] })
    if (path.includes('/catalogue/home')) return failure ? Response.json({ detail: 'Unavailable' }, { status: 503 }) : Response.json(payload(id))
    if ((path.includes('/catalogue/books?') || path.includes('/catalogue/search?'))) {
      const data = payload(id), params = new URL(path, 'http://localhost').searchParams
      let rows = data.featured
      if (params.get('subject')) rows = rows.filter(row => row.subjects.includes(params.get('subject')!))
      if (params.get('search') === 'unknown') rows = []
      if (params.get('sort') === 'new_arrivals') rows = data.new_arrivals
      if (params.get('sort') === 'popular') rows = data.popular
      return Response.json({ source: data.source, results: rows, total: rows.length, has_more: false, offset: 0, limit: 20 })
    }
    if (path.includes('/catalogue/genres?')) { const data = payload(id); return Response.json({ source: data.source, results: data.subjects, total: data.subjects.length, has_more: false, offset: 0, limit: 50 }) }
    if (path.startsWith('/api/books/categories')) return Response.json({ count: 1, categories: [{ name: 'Global Subject', count: 500 }] })
    if (path.startsWith('/api/books/')) return Response.json({ count: 1, results: [globalBook] })
    if (path.startsWith('/search-api/search')) return Response.json({ results: [globalBook], has_more: false, total_ranked_candidates: 1 })
    if (options?.method === 'POST') return Response.json({ status: 'PENDING' })
    return Response.json({ results: [], total: 0, unread_count: 0 })
  }
})
afterEach(() => { cleanup(); globalThis.fetch = original })
const mount = (child: React.ReactNode, path = '/') => render(<MemoryRouter initialEntries={[path]}>{child}</MemoryRouter>)
const card = (book: DisplayBook, detailed = false) => mount(<LibraryCatalogueBook book={book} changed={() => {}} detailed={detailed} />)
const global = () => globalDisplayBook(globalBook, a)

test('test_local_book_card', () => { card(local()); assert.ok(screen.getByText('Available now')); assert.ok(screen.getByText('Shelf A / Shelf 0')); assert.ok(screen.getByRole('button', { name: 'Request Book' })) })
test('test_global_fallback_book_card', () => { card(global()); assert.ok(screen.getByText('Global Catalogue')); assert.ok(screen.getByRole('heading', {name:'Global Atlas'}).closest('a')) })
test('test_global_book_no_fake_ownership', () => { const row = global(); assert.equal(row.owned_by_current_library, false); assert.equal(row.library_book_id, null); assert.equal(row.requestable_count, null); assert.equal(row.shelf_location, null) })
test('test_fallback_no_request_button', () => { card({ ...global(), actions: { request: true, reserve: true, cancel_request: true, cancel_reservation: true } }); assert.equal(screen.queryByRole('button', { name: /Request/ }), null) })
test('test_fallback_no_reservation_button', () => { card(global()); assert.equal(screen.queryByRole('button', { name: /Waitlist|Reserve/ }), null) })
test('test_global_book_no_shelf', () => { card(global()); assert.equal(screen.queryByText('Shelf / Location'), null); assert.equal(screen.queryByText('FAKE SHELF'), null); assert.equal(screen.queryByText(/999.*available/), null) })
test('test_local_only_book', () => { card(local(a, 1)); assert.ok(screen.getByRole('heading', { name: 'A Book 1' })); assert.ok(screen.getByText('LuminaR')) })
test('test_missing_cover_fallback', () => { mount(<CatalogueCover book={{ ...local(), cover_url: 'https://example.invalid/cover.jpg' }} />); fireEvent.error(screen.getByRole('img')); assert.equal(document.querySelector('img'), null); assert.ok(screen.getByRole('img', {name:/Cover for/})); assert.ok(screen.getByText('LuminaR')) })
test('test_reference_only_book', () => { card({ ...local(), circulation_status: 'REFERENCE_ONLY', requestable_count: 0 }); assert.ok(screen.getByText('Reference Only')); assert.equal(screen.queryByRole('button', { name: 'Request Book' }), null) })
test('test_temporarily_unavailable_book', () => { card({ ...local(), circulation_status: 'TEMPORARILY_UNAVAILABLE', requestable_count: 0 }); assert.ok(screen.getByText('Temporarily unavailable')); assert.equal(screen.queryByRole('button', { name: /Request Book|Waitlist/ }), null) })
test('test_local_book_request_button', async () => { card(local()); fireEvent.click(screen.getByRole('button', { name: 'Request Book' })); await waitFor(() => assert.ok(calls.some(c => c.path.includes(`/libraries/${a}/lending/borrow-requests`) && c.options?.method === 'POST'))); const call = calls.find(c => c.options?.method === 'POST')!; assert.equal(JSON.parse(String(call.options?.body)).library_book_id, local().library_book_id) })
test('test_local_book_reservation_button', async () => { card({ ...local(), requestable_count: 0, actions: { request: false, reserve: true, cancel_request: false, cancel_reservation: false } }); fireEvent.click(screen.getByRole('button', { name: 'Join Waitlist' })); fireEvent.click(screen.getByRole('button', { name: 'Confirm' })); await waitFor(() => assert.ok(calls.some(c => c.path.endsWith(`/libraries/${a}/reservations`) && c.options?.method === 'POST'))) })
test('pending and loan states come from one hydrated response', () => { card({ ...local(), actions: { request: false, reserve: false, cancel_request: true, cancel_reservation: false }, user_request_state: { id: 'request1', status: 'PENDING' } }, true); assert.ok(screen.getByText(/Awaiting librarian approval/)); assert.ok(screen.getByRole('button', { name: 'Cancel Request' })); assert.equal(calls.length, 0) })
test('queue position is hydrated without per-card requests', () => { card({ ...local(), user_reservation_state: { id: 'reservation1', status: 'WAITING', queue_position: 2, queue_length: 3 } }, true); assert.ok(screen.getByText('Reservation position 2 of 3')); assert.equal(calls.length, 0) })
test('active loan state uses this library and suppresses another borrow', () => { card({ ...local(), actions: { request: false, reserve: false, cancel_request: false, cancel_reservation: false }, user_loan_state: { id: 'loan1', status: 'ACTIVE', due_at: '2026-10-23T00:00:00Z', return_requested: false } }, true); assert.ok(screen.getByText(/On loan to you/)); assert.equal(screen.getByRole('link', { name: 'My Library', exact: true }).getAttribute('href'), `/libraries/${a}/my-library`); assert.equal(screen.queryByRole('button', { name: 'Request Book' }), null); assert.equal(calls.length, 0) })
test('test_featured_rail_local', async () => { mount(<LibraryCatalogueHome key="home" />); await screen.findByRole('heading', { name: 'FOR YOU' }); assert.equal(document.querySelectorAll('#for-you-results article').length, 4); assert.equal(calls.filter(c => c.path.startsWith('/api/books')).length, 0) })
test('test_small_collection_not_padded', async () => { mount(<LibraryCatalogueHome key="home" />); await screen.findByRole('heading', { name: 'FOR YOU' }); assert.equal(document.querySelectorAll('#for-you-results article').length, 4); assert.equal(screen.queryByText('Global Atlas'), null) })
test('test_featured_rail_global_fallback', async () => { fallback = true; mount(<LibraryCatalogueHome key="home" />); await screen.findByRole('heading', { name: 'FOR YOU' }); assert.ok(screen.getByText(/while your library builds its collection/)); assert.equal(screen.queryByRole('button', { name: 'Request Book' }), null) })
test('test_popular_no_fake_activity', async () => { mount(<LibraryCatalogueHome key="home" />); await screen.findByRole('heading', { name: 'FOR YOU' }); assert.equal(screen.queryByRole('heading', { name: 'Popular Right Now' }), null) })
test('test_popular_from_real_tenant_activity', async () => { popularity = true; mount(<LibraryCatalogueHome key="home" />); await screen.findByRole('heading', { name: 'FOR YOU' }); assert.ok(screen.getByRole('heading', {name: 'Discover More'})); assert.equal(screen.queryByRole('heading', {name: 'Popular Right Now'}), null) })
test('test_local_new_arrivals', async () => { mount(<LibraryCataloguePage key="arrivals" arrivals />); await screen.findByRole('article', { name: 'A Book 3' }); assert.equal(calls.find(c => c.path.includes('/catalogue/books?'))?.path.includes('sort=new_arrivals'), true) })
test('test_local_genres', async () => { function Position(){return <output data-testid="genre-url">{useLocation().pathname+useLocation().search}</output>} mount(<><Position/><LibraryCatalogueGenres key="genres" /></>); fireEvent.click(await screen.findByRole('button',{name:'Networking 2 books'})); assert.equal(screen.getByTestId('genre-url').textContent, `/libraries/${a}/catalogue?subject=Networking`) })
test('test_local_genre_counts', async () => { mount(<LibraryCatalogueHome key="home" />); await screen.findByRole('button', { name: 'Networking' }); assert.ok(screen.getByRole('button', { name: 'Mathematics' })) })
test('test_local_search', async () => { mount(<LibraryCataloguePage key="browse" />, '/?search=Networking'); await screen.findByRole('article', { name: 'A Book 0' }); assert.ok(calls.some(c => c.path.includes(`/libraries/${a}/catalogue/search?search=Networking`))); assert.equal(calls.filter(c => c.path === '/search-api/search').length, 0) })
test('test_global_fallback_search', async () => { fallback = true; mount(<LibraryCataloguePage key="browse" />, '/?search=Networking'); await screen.findByRole('article', { name: 'Global Atlas' }); const call = calls.find(c => c.path === '/search-api/search')!; assert.ok(call); assert.equal(JSON.parse(String(call.options?.body)).available_at_library, false); assert.equal(JSON.parse(String(call.options?.body)).save_history, false); assert.equal(screen.queryByRole('button', { name: 'Request Book' }), null) })
test('test_local_no_result_no_fake_ownership', async () => { mount(<LibraryCataloguePage key="browse" />, '/?search=unknown'); await screen.findByText('No books match all selected filters.'); assert.ok(screen.getByRole('link', { name: 'Search all LuminaR' })); assert.equal(calls.some(c => c.path === '/search-api/search'), false) })
test('test_staff_catalogue_summary', () => { mount(<StaffCatalogueSummary source={source(a)} retry={() => {}} />); assert.ok(screen.getByText('4 local books')); assert.ok(screen.getByText('Library collection')); assert.equal(screen.queryByText(/HNSW|vector|builder|KG edge/), null) })
test('test_empty_staff_catalogue_summary', () => { mount(<StaffCatalogueSummary source={source(b, false)} retry={() => {}} />); assert.ok(screen.getByText('0 local books')); assert.ok(screen.getByText('Discovery fallback')); assert.ok(screen.getByText('LuminaR global catalogue')) })
test('test_platform_authority_does_not_change_catalogue_actions', () => { usePlatformStore.setState({ roles: ['PLATFORM_ADMIN'] }); const row = library(a); store.setState({ libraries: [{ ...row, membership: { ...row.membership, role: 'ADMIN' } }], workspace: 'STAFF', staffLibraryId: a }); card(local()); assert.equal(screen.queryByRole('button', { name: 'Request Book' }), null) })
for (const [name, component] of [['home', <LibraryCatalogueHome key="home" />], ['genres', <LibraryCatalogueGenres key="genres" />], ['arrivals', <LibraryCataloguePage key="arrivals" arrivals />], ['popular', <LibraryCataloguePage key="popular" popular />]] as const) {
  test(`test_library_switch_reloads_${name}`, async () => { mount(component); await waitFor(() => assert.ok(calls.some(c => c.path.includes(a)))); act(() => store.setState({ activeId: b, patronLibraryId: b })); await waitFor(() => assert.ok(calls.some(c => c.path.includes(b)))); await waitFor(() => assert.equal(screen.queryByRole('article', { name: 'A Book 0' }), null)); assert.equal(screen.queryByText('A / Shelf 0'), null) })
}
test('test_stale_catalogue_response_discarded', async () => {
  let release!: (response: Response) => void
  const previous = globalThis.fetch
  globalThis.fetch = async (url, options) => String(url).includes(a) && String(url).includes('/catalogue/home') ? new Promise<Response>(resolve => { release = resolve }) : previous(url, options)
  mount(<LibraryCatalogueHome key="home" />); await waitFor(() => assert.ok(release)); act(() => store.setState({ activeId: b, patronLibraryId: b })); await screen.findByText('Library B · Discover your next read')
  await act(async () => { release(Response.json(payload(a))); await Promise.resolve() })
  assert.ok(screen.getByText('Library B · Discover your next read')); assert.equal(screen.queryByRole('article', { name: 'A Book 0' }), null)
})
test('failure shows retry and never substitutes global books', async () => { failure = true; mount(<LibraryCatalogueHome key="home" />); await screen.findByText('Unable to load this library catalogue'); assert.ok(screen.getByRole('button', { name: 'Retry' })); assert.equal(calls.some(c => c.path.startsWith('/api/books')), false) })
test('shared Home keeps the original recommendation carousel', async () => { mount(<LibraryCatalogueHome />); await screen.findByRole('heading', {name:'FOR YOU'}); assert.ok(document.querySelector('#for-you-results .scroll-smooth')); assert.equal(document.querySelectorAll('.catalogue-rail').length,0) })

test('wrong-library source fails closed', async () => { globalThis.fetch = async () => Response.json(payload(b)); await assert.rejects(() => loadCatalogue('home', a, '', new AbortController().signal), /context changed/) })
test('header search stays scoped inside patron workspace', async () => {
  function Position() { return <output data-testid="position">{useLocation().pathname + useLocation().search}</output> }
  mount(<><Header /><Position /></>, `/libraries/${a}`); fireEvent.click(screen.getByRole('button', { name: 'Search the catalog' })); fireEvent.change(screen.getByLabelText('Search catalogue for Library A'), { target: { value: 'Networking' } }); fireEvent.click(screen.getByRole('button', { name: 'Search', exact: true })); await waitFor(() => assert.equal(screen.getByTestId('position').textContent, `/libraries/${a}/catalogue?search=Networking`))
})

for (const [surface, component] of [['home', <LibraryCatalogueHome key="home" />], ['browse', <LibraryCataloguePage key="browse" />], ['genres', <LibraryCatalogueGenres key="genres" />]] as const) test(`catalogue ${surface} passes axe structural accessibility checks`, async () => {
  const view = mount(component)
  if(surface==='home') await screen.findByRole('heading', {name:'FOR YOU'}); else await screen.findByText(/4 local books in Library A/)
  const axe = await import('axe-core')
  const result = await axe.default.run(view.container, { rules: { 'color-contrast': { enabled: false }, region: { enabled: false } } })
  assert.deepEqual(result.violations.map(v => ({ id: v.id, description: v.description })), [])
})


const readyHome = async () => { mount(<Home context="library" />); await screen.findByRole('heading', {name:'FOR YOU'}) }
const localRailIds = (selector: string) => Array.from(document.querySelectorAll(selector)).map(e => e.getAttribute('data-library-book-id'))

test('test_library_home_reuses_global_home_components', async () => { await readyHome(); assert.ok(document.querySelector('#top .marquee-track')); assert.ok(document.querySelector('#for-you-results .scroll-smooth')); assert.ok(document.querySelector('#new-arrivals')); assert.ok(screen.getByRole('heading',{name:'Browse by Category'})) })
test('test_no_separate_explore_library_home', async () => { await readyHome(); assert.equal(screen.queryByRole('heading',{name:'Explore Library A'}),null); assert.equal(document.querySelector('.catalogue-hero'),null); assert.equal(screen.queryByRole('heading',{name:'Featured Collection'}),null); assert.equal(screen.queryByRole('textbox'),null) })
test('test_global_and_library_home_share_visual_shell', async () => { await readyHome(); const localClasses=Array.from(document.querySelectorAll('section')).map(e=>e.className); cleanup(); mount(<Home />); await screen.findByRole('heading',{name:'Popular Right Now'}); await waitFor(()=>assert.equal(document.querySelectorAll('.animate-pulse').length,0)); assert.deepEqual(Array.from(document.querySelectorAll('section')).map(e=>e.className),localClasses) })
test('test_empty_library_uses_global_books', async () => { fallback=true; await readyHome(); assert.ok(document.querySelector('#top a[href*="global-books/OL1W"]')); assert.ok(calls.some(c=>c.path.startsWith('/api/books/?'))); assert.ok(screen.getByRole('heading',{name:'Popular Right Now'})) })
test('test_empty_library_global_books_not_owned', async () => { fallback=true; await readyHome(); assert.equal(document.querySelectorAll('[data-library-book-id]').length,0); assert.equal(screen.queryByRole('button',{name:/Request Book|Join Waitlist/}),null); assert.equal(screen.queryByText('Available now'),null) })
test('test_local_collection_replaces_global_home_data', async () => { fallback=true; const view=mount(<Home context="library" />); await screen.findByRole('heading',{name:'FOR YOU'}); const before=Array.from(document.querySelectorAll('section')).map(e=>e.className); fallback=false; const { catalogueChanged }=await import('../src/lib/catalogueInvalidation'); act(()=>catalogueChanged(a)); await waitFor(()=>assert.ok(document.querySelector(`#top a[href*="/books/${a}-0"]`))); assert.deepEqual(Array.from(view.container.querySelectorAll('section')).map(e=>e.className),before); assert.equal(document.querySelector('a[href*="global-books"]'),null) })
test('test_local_source_replaces_showcase_rail', async () => { await readyHome(); assert.equal(localRailIds('#top [data-library-book-id]').length,8); assert.ok(localRailIds('#top [data-library-book-id]').every(id=>id?.startsWith(a))) })
test('test_local_source_replaces_for_you', async () => { await readyHome(); assert.deepEqual(localRailIds('#for-you-results article'),Array.from({length:4},(_,i)=>local(a,i).library_book_id)) })
test('test_local_source_replaces_new_arrivals', async () => { await readyHome(); assert.deepEqual(localRailIds('#new-arrivals [data-library-book-id]'),Array.from({length:4},(_,i)=>local(a,3-i).library_book_id)) })
test('test_local_source_replaces_popular', async () => { popularity=true; await readyHome(); assert.equal(screen.queryByRole('heading',{name:'Popular Right Now'}),null); assert.ok(screen.getByRole('heading',{name:'Discover More'})); assert.equal(document.querySelector('a[href*="global-books"]'),null) })
test('test_local_source_replaces_genres', async () => { await readyHome(); await screen.findByRole('button',{name:'Networking'}); assert.equal(screen.queryByRole('button',{name:'Global Subject'}),null); assert.equal(calls.some(c=>c.path.startsWith('/api/books/categories')),false) })
test('test_local_source_replaces_browse', async () => { mount(<LibraryCataloguePage />); await screen.findByRole('article',{name:'A Book 0'}); assert.equal(document.querySelectorAll('article[data-library-book-id]').length,4); assert.equal(document.querySelector('.institution-table-wrap'),null) })
test('test_local_source_replaces_search', async () => { mount(<LibraryCataloguePage />, '/?search=unknown'); await screen.findByText('No books match all selected filters.'); assert.equal(calls.some(c=>c.path === '/search-api/search'),false); assert.ok(calls.some(c=>c.path.includes(`/libraries/${a}/catalogue/search?`))); assert.equal(screen.queryByRole('article'),null) })
test('test_local_source_replaces_view_all', async () => { await readyHome(); const viewLinks=screen.getAllByRole('link',{name:/VIEW ALL|View all/}); assert.ok(viewLinks.length>=3); assert.ok(viewLinks.every(link=>link.getAttribute('href')?.startsWith(`/libraries/${a}/`))) })
test('test_no_global_filler_in_local_primary_rails', async () => { await readyHome(); assert.equal(calls.filter(c=>c.path.startsWith('/api/books')).length,0); assert.equal(document.querySelector('a[href*="global-books"]'),null); assert.equal(screen.queryByText('Global Atlas'),null) })
test('test_small_local_collection_stays_small', async () => { await readyHome(); assert.equal(document.querySelectorAll('#for-you-results article').length,4); assert.equal(document.querySelectorAll('#new-arrivals [data-library-book-id]').length,4) })
test('test_global_nonowned_no_request', () => { card({...global(),actions:{request:true,reserve:true,cancel_request:false,cancel_reservation:false}}); assert.equal(screen.queryByRole('button',{name:'Request Book'}),null) })
test('test_global_nonowned_no_reservation', () => { card({...global(),actions:{request:true,reserve:true,cancel_request:false,cancel_reservation:false}}); assert.equal(screen.queryByRole('button',{name:'Join Waitlist'}),null) })
test('test_global_nonowned_no_shelf', () => { card(global()); assert.equal(screen.queryByText(/FAKE SHELF|Shelf /),null); assert.equal(screen.queryByText('Available now'),null) })
test('test_local_owned_request_button', async () => { card(local()); fireEvent.click(screen.getByRole('button',{name:'Request Book'})); await waitFor(()=>assert.ok(calls.some(c=>c.path.endsWith('/lending/borrow-requests')&&c.options?.method==='POST'))); assert.equal(calls.some(c=>c.path.includes('/issue')),false) })
test('test_local_owned_waitlist', async () => { card({...local(),requestable_count:0,actions:{request:false,reserve:true,cancel_request:false,cancel_reservation:false}}); fireEvent.click(screen.getByRole('button',{name:'Join Waitlist'})); assert.ok(screen.getByRole('dialog')); fireEvent.click(screen.getByRole('button',{name:'Confirm'})); await waitFor(()=>assert.ok(calls.some(c=>c.path.endsWith('/reservations')&&c.options?.method==='POST'))) })
test('test_book_card_shared_visual_component', async () => { card(global()); const cover=document.querySelector('article .aspect-\\[2\\/3\\]')?.className; assert.ok(cover); cleanup(); mount(<Home />); await screen.findByRole('heading',{name:'FOR YOU'}); await waitFor(()=>assert.equal(document.querySelectorAll('.animate-pulse').length,0)); assert.equal(document.querySelector('#for-you-results .aspect-\\[2\\/3\\]')?.className,cover) })
test('test_context_catalog_navigation', () => { mount(<Header />,`/libraries/${a}`); assert.equal(screen.getByRole('link',{name:'Browse Books'}).getAttribute('href'),`/libraries/${a}/catalogue`) })
test('test_context_new_arrivals_navigation', () => { mount(<Header />,`/libraries/${a}`); assert.equal(screen.getByRole('link',{name:'New Arrivals'}).getAttribute('href'),`/libraries/${a}/new-arrivals`) })
test('test_patron_switcher_preserved', () => { mount(<PatronLibraryShell />,`/libraries/${a}`); assert.ok(screen.getByRole('combobox')); assert.ok(screen.getByRole('navigation',{name:'Library activity'})); assert.equal(screen.queryByRole('navigation',{name:'Patron workspace'}),null); assert.ok(screen.getByRole('link',{name:'Fees'})); assert.ok(screen.getByRole('link',{name:'Reservations'})) })
test('test_admin_librarian_staff_only', async () => { const {libraryWorkspaceHome}=await import('../src/lib/libraryWorkspace'); for(const role of ['ADMIN','LIBRARIAN'] as const) { const row=library(a); assert.equal(libraryWorkspaceHome({...row,membership:{...row.membership,role}}),`/staff/libraries/${a}`) }; assert.equal(libraryWorkspaceHome(library(a)),`/libraries/${a}`) })
test('test_global_home_unchanged', async () => { mount(<Home />); await screen.findByRole('heading',{name:/Every Story.*Waiting to Be Borrowed/}); await screen.findByRole('heading',{name:'Popular Right Now'}); assert.equal(calls.some(c=>c.path.includes('/catalogue/home')),false); assert.ok(calls.some(c=>c.path==='/api/books/?limit=12&offset=0')); assert.ok(calls.some(c=>c.path.startsWith('/recommendation-api/recommendations?limit=10'))); assert.ok((await screen.findByRole('link',{name:'VIEW ALL'})).getAttribute('href')==='/catalog?sort=popular') })

