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
const { render, screen, cleanup, fireEvent, act, within } = await import('@testing-library/react')
const { MemoryRouter } = await import('react-router-dom')
const { useAuthStore: auth } = await import('../src/store/useAuthStore')
const { useInstitutionStore: store } = await import('../src/store/useInstitutionStore')
const { usePlatformStore } = await import('../src/store/usePlatformStore')
const { LibraryCataloguePage } = await import('../src/pages/LibraryCatalogue')
const { Home } = await import('../src/pages/Home')
const LibraryCatalogueHome = () => <Home context="library" />
class Observer { observe() {} disconnect() {} unobserve() {} }
Object.assign(globalThis, { ResizeObserver: Observer, IntersectionObserver: Observer })
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
    const id = path.includes(b) ? b : a
    if (path.includes('/catalogue/recommendations')) return Response.json({source:payload(id).source,results:payload(id).featured})
    if (path.startsWith('/recommendation-api')) return Response.json({recommendations:[]})
    if (path.includes('/catalogue/home')) return failure ? Response.json({ detail: 'Unavailable' }, { status: 503 }) : Response.json(payload(id))
    if (path.includes('/catalogue/books?')) {
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

const { catalogueChanged } = await import('../src/lib/catalogueInvalidation')
test('successful Add Book emits the scoped source invalidation', async () => {
  const { BookEditor } = await import('../src/pages/LibraryInventory')
  let changed=''; const handler=(event:Event)=>{changed=(event as CustomEvent).detail.library_id}
  window.addEventListener('luminar:catalogue-changed',handler)
  try {
    mount(<BookEditor libraryId={a} onSaved={()=>{}} />)
    fireEvent.change(screen.getByLabelText('Title *'),{target:{value:'First Manual'}})
    fireEvent.change(screen.getByLabelText(/Subject \/ Genre \*/),{target:{value:'Networks'}})
    await act(async()=>{fireEvent.click(screen.getByRole('button',{name:'Save New Book'}))})
    assert.equal(changed,a)
  } finally { window.removeEventListener('luminar:catalogue-changed',handler) }
})
test('transient tenant read lock retries without changing scope', async () => {
  const { institutionApi } = await import('../src/lib/institutions')
  let attempts=0
  globalThis.fetch=async url => { assert.equal(String(url), `/api/libraries/${a}/context`); attempts++; return attempts===1?Response.json({detail:'Update in progress'},{status:503}):Response.json({library_id:a}) }
  assert.deepEqual(await institutionApi(`/libraries/${a}/context`),{library_id:a})
  assert.equal(attempts,2)
})
test('tenant mutation is not automatically replayed on an unavailable response', async () => {
  const { institutionApi } = await import('../src/lib/institutions')
  let attempts=0; globalThis.fetch=async()=>{attempts++;return Response.json({detail:'Unavailable'},{status:503})}
  await assert.rejects(institutionApi(`/libraries/${a}/lending/borrow-requests`,'POST',{}))
  assert.equal(attempts,1)
})
test('test_add_book_invalidation_switches_existing_fallback_home', async () => {
  fallback = true; mount(<LibraryCatalogueHome />)
  await screen.findAllByRole('heading', { name: 'Global Atlas' })
  fallback = false; act(() => catalogueChanged(a))
  await screen.findAllByRole('heading', { name: 'A Book 0' })
  assert.equal(screen.queryByRole('heading', { name: 'Global Atlas' }), null)
})
test('test_import_invalidation_refreshes_scoped_browse', async () => {
  fallback = true; mount(<LibraryCataloguePage />)
  await screen.findAllByRole('heading', { name: 'Global Atlas' })
  fallback = false; act(() => catalogueChanged(a))
  await screen.findAllByRole('heading', { name: 'A Book 0' })
  assert.equal(screen.queryByRole('heading', { name: 'Global Atlas' }), null)
})
test('test_other_library_invalidation_is_ignored', async () => {
  mount(<LibraryCatalogueHome />); await screen.findAllByRole('heading', { name: 'A Book 0' })
  const count = calls.length; act(() => catalogueChanged(b))
  assert.equal(calls.length, count)
})
test('test_returning_browser_session_refreshes_authoritative_source', async () => {
  fallback = true; mount(<LibraryCatalogueHome />); await screen.findAllByRole('heading', { name: 'Global Atlas' })
  fallback = false; act(() => window.dispatchEvent(new window.Event('focus')))
  await screen.findAllByRole('heading', { name: 'A Book 0' })
})
test('test_header_mobile_navigation', async () => {
  mount(<Header />, `/libraries/${a}`); fireEvent.click(screen.getByRole('button', { name: 'Toggle menu' }))
  const dialog = screen.getByRole('dialog', { name: 'LuminaR navigation' })
  assert.ok(within(dialog).getByRole('link', { name: 'Browse Books' }))
  assert.ok(within(dialog).getByRole('link', { name: 'Events' }))
})
test('test_global_catalog_outside_workspace_is_global', () => {
  mount(<Header />, '/catalog')
  assert.equal(screen.getByRole('link', { name: 'Catalog' }).getAttribute('href'), '/catalog')
})

