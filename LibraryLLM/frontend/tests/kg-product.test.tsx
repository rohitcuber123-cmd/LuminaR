import assert from 'node:assert/strict'
import { test, beforeEach, afterEach } from 'node:test'
import { JSDOM } from 'jsdom'
import React from 'react'

const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173/book/OL1W' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
const { render, screen, fireEvent, cleanup, waitFor, within, act } = await import('@testing-library/react')
const { MemoryRouter, Routes, Route } = await import('react-router-dom')
const { BookDetailPage } = await import('../src/pages/BookDetailPage')
const { useAssistantStore } = await import('../src/store/useAssistantStore')
const { useAuthStore } = await import('../src/store/useAuthStore')
const { BookDiscoveryMenu } = await import('../src/components/BookDiscoveryMenu')
const { WhyRelated } = await import('../src/components/RelatedBookCard')
const seed = { book_id: 91, work_id: 'OL1W', title: 'Current Book', authors: 'Current Author', subjects: 'Finance', description: 'Current description', average_rating: 4, rating_count: 2, reading_log_count: 1, shelf_location: 'A', total_copies: 3, available_copies: 2 }
const paths = [
  { nodes: ['OL1W', 'subject:finance', 'OL2W'], kind: 'subject', label: 'Personal finance', contribution: .6, catalogue_degree: 4, provenance: [] },
  { nodes: ['OL1W', 'author:writer', 'OL2W'], kind: 'author', label: 'Shared Writer', contribution: .2, catalogue_degree: 3, provenance: [] },
]
const related = { seed_work_id: 'OL1W', seed: { work_id: 'OL1W', title: seed.title, authors: ['Current Author'], subjects: ['Finance'] }, graph_version: 'v1', recommendations: [{ book_id: 2, work_id: 'OL2W', title: 'Related Book', authors: ['Shared Writer'], subjects: ['Personal finance'], average_rating: 4.5, rating_count: 7, shelf_location: 'LIVE-B', available_copies: 0, total_copies: 9, score: .8, reason_paths: paths }], has_more: false }
let original: typeof fetch
let calls: string[]
let status: number
let empty: boolean
let release: ((response: Response) => void) | null
let delayed: boolean
beforeEach(() => {
  localStorage.setItem('luminar_token', 'fixture-token')
  useAuthStore.setState({ isAuthenticated: true }); useAssistantStore.setState({ selected: [{ work_id: 'OL99W', title: 'Keep selected' }], messages: [], busy: false, open: false })
  original = globalThis.fetch; calls = []; status = 200; empty = false; release = null; delayed = false
  globalThis.fetch = async url => {
    calls.push(String(url))
    if (String(url).includes('/kg/books/')) {
      if (delayed) return new Promise(resolve => { release = resolve })
      return new Response(JSON.stringify(status === 200 ? { ...related, recommendations: empty ? [] : related.recommendations } : { detail: 'Technical stale graph detail' }), { status })
    }
    if (String(url).startsWith('/api/books/')) return new Response(JSON.stringify(seed), { status: 200 })
    throw new Error(`Unexpected request: ${url}`)
  }
})
afterEach(() => { cleanup(); globalThis.fetch = original })
async function mount(entry = '/book/OL1W') { render(<MemoryRouter initialEntries={[entry]}><Routes><Route path="/book/:workId" element={<BookDetailPage />} /></Routes></MemoryRouter>); await screen.findByRole('heading', { name: 'Current Book' }) }
async function explore() { fireEvent.click(screen.getByRole('button', { name: 'More Like This', exact: true })); return screen.findByRole('region', { name: 'More Like This' }) }
test('test_book_detail_more_like_this_button', async () => { await mount(); assert.ok(screen.getByRole('button', { name: 'Add to Reading List' })); assert.ok(screen.getByRole('button', { name: 'More Like This' })); assert.equal(calls.some(url => url.includes('/kg/')), false) })
test('test_button_uses_current_work_id', async () => { await mount(); await explore(); await screen.findByRole('article', { name: 'Related Book' }); assert.ok(calls.includes('/api/kg/books/OL1W/more-like-this?limit=10')); assert.equal(calls.some(url => url.includes('91')), false) })
test('test_click_does_not_change_selected_tray', async () => { await mount(); const selected = [...useAssistantStore.getState().selected]; await explore(); await screen.findByRole('article', { name: 'Related Book' }); assert.deepEqual(useAssistantStore.getState().selected, selected); assert.equal(useAssistantStore.getState().messages.length, 0) })
test('test_loading_state', async () => { await mount(); delayed = true; await explore(); assert.ok(screen.getByRole('status')); assert.match(screen.getByRole('status').textContent || '', /Finding related books/); await act(async () => release?.(new Response(JSON.stringify(related)))) })
test('test_results_render_inline', async () => { await mount(); const section = await explore(); await screen.findByRole('article', { name: 'Related Book' }); assert.ok(within(section).getByRole('article', { name: 'Related Book' })); assert.ok(screen.getByRole('heading', { name: 'Current Book' })); assert.equal(document.activeElement, section) })
test('test_results_use_existing_book_cards', async () => { await mount(); await explore(); const card = await screen.findByRole('article', { name: 'Related Book' }); assert.ok(within(card).getByText('LuminaR')); assert.ok(within(card).getByRole('button', { name: 'Select Related Book' })); assert.ok(within(card).getByText('Currently unavailable')); assert.ok(within(card).getByText('Shelf: LIVE-B')); assert.equal(within(card).queryByText(/Similarity/), null) })
test('test_why_related_expands', async () => { await mount(); await explore(); await screen.findByRole('article', { name: 'Related Book' }); const summary = screen.getByText('Why related?'); fireEvent.click(summary); assert.equal(summary.closest('details')?.open, true); assert.ok(screen.getByText('Shared knowledge-graph relationships:')) })
test('test_reasons_group_by_type', async () => { await mount(); await explore(); await screen.findByRole('article', { name: 'Related Book' }); assert.ok(screen.getByRole('heading', { name: 'Subjects' })); assert.ok(screen.getByRole('heading', { name: 'Authors' })); assert.equal(screen.queryByRole('heading', { name: 'Series' }), null) })
test('test_empty_state', async () => { await mount(); empty = true; await explore(); await screen.findByText('No graph relationships are available for this title yet.'); assert.ok(screen.getByRole('button', { name: 'Try Recommend Similar' })); assert.equal(calls.some(url => url.includes('recommendation') || url.includes('assistant')), false) })
test('test_try_normal_recommendation_separate', async () => { await mount(); empty = true; await explore(); const button = await screen.findByRole('button', { name: 'Try Recommend Similar' }); const oldSend = useAssistantStore.getState().send; let request: unknown; useAssistantStore.setState({ send: async (...args) => { request = args } }); try { fireEvent.click(button); assert.deepEqual(request, ['Recommend Similar', { work_id: 'OL1W' }, { action: 'RECOMMEND_SIMILAR', action_work_ids: ['OL1W'] }]); assert.equal(useAssistantStore.getState().selected[0].work_id, 'OL99W') } finally { useAssistantStore.setState({ send: oldSend }) } })
test('test_graph_lab_link', async () => { await mount(); await explore(); await screen.findByRole('article', { name: 'Related Book' }); assert.equal(screen.getByRole('link', { name: 'Explore full graph →' }).getAttribute('href'), '/experimental/kg?seed=OL1W') })
test('test_mobile_action_row', async () => { await mount(); const row = screen.getByRole('button', { name: 'More Like This' }).parentElement!; assert.ok(row.classList.contains('flex-wrap')); assert.ok(within(row).getByRole('button', { name: 'BORROW', exact: true })); assert.ok(within(row).getByRole('button', { name: 'Add to Reading List' })) })
test('test_no_qwen_request', async () => { await mount(); await explore(); await screen.findByRole('article', { name: 'Related Book' }); assert.deepEqual(calls, ['/api/books/OL1W', '/api/kg/books/OL1W/more-like-this?limit=10']) })
test('stale graph shows friendly refresh message and hides technical detail', async () => { await mount(); status = 409; await explore(); await screen.findByRole('alert'); assert.equal(screen.getByRole('alert').textContent, 'Related-book data for this title is being refreshed.'); assert.ok(screen.getByRole('button', { name: 'Retry related books' })) })
test('hide aborts pending result and prevents late reappearance', async () => { await mount(); delayed = true; await explore(); fireEvent.click(screen.getByRole('button', { name: 'Hide related books' })); await act(async () => release?.(new Response(JSON.stringify(related)))); await waitFor(() => assert.equal(screen.queryByRole('region', { name: 'More Like This' }), null)) })
test('small-card discovery menu preserves canonical book destination', () => { render(<MemoryRouter><BookDiscoveryMenu workId="OL1W" /></MemoryRouter>); assert.equal(screen.getByRole('link', { name: 'More Like This' }).getAttribute('href'), '/book/OL1W?related=1#more-like-this') })
test('card discovery destination opts into inline KG loading', async () => { await mount('/book/OL1W?related=1'); await screen.findByRole('article', { name: 'Related Book' }); assert.ok(calls.some(url => url.includes('/kg/books/OL1W'))) })
test('Show connection reveals the exact book pair and shared features without another request or tray change', async () => {
  await mount(); await explore()
  const card = await screen.findByRole('article', { name: 'Related Book' })
  const beforeCalls = [...calls]; const beforeSelected = [...useAssistantStore.getState().selected]
  const button = within(card).getByRole('button', { name: 'Show connection', exact: true })
  assert.equal(button.getAttribute('aria-expanded'), 'false')
  fireEvent.click(button)
  const graph = within(card).getByRole('img', { name: 'Connection map: Current Book to Related Book' })
  assert.match(graph.textContent || '', /Personal finance/)
  assert.match(graph.textContent || '', /Shared Writer/)
  assert.equal(within(card).getByRole('link', { name: 'Explore this book in Graph Lab →' }).getAttribute('href'), '/experimental/kg?seed=OL2W')
  assert.deepEqual(calls, beforeCalls); assert.deepEqual(useAssistantStore.getState().selected, beforeSelected)
  assert.equal(button.getAttribute('aria-expanded'), 'true')
  fireEvent.click(within(card).getByRole('button', { name: 'Hide connection' }))
  assert.equal(within(card).queryByRole('img'), null)
})
test('connection buttons operate independently and do not show another book pair', () => {
  render(<MemoryRouter><WhyRelated paths={paths} seedTitle="Seed" bookTitle="First" /><WhyRelated paths={[{ ...paths[0], nodes: ['OL1W', 'topic:history', 'OL3W'], kind: 'topic', label: 'Medical history' }]} seedTitle="Seed" bookTitle="Second" /></MemoryRouter>)
  fireEvent.click(screen.getAllByRole('button', { name: 'Show connection' })[1])
  assert.equal(screen.queryByRole('img', { name: 'Connection map: Seed to First' }), null)
  assert.ok(screen.getByRole('img', { name: 'Connection map: Seed to Second' }))
  assert.equal(screen.getAllByRole('button', { name: 'Show connection' }).length, 1)
})
test('missing reason paths show an empty connection message without inventing edges', () => {
  render(<MemoryRouter><WhyRelated paths={[]} bookTitle="Sparse book" /></MemoryRouter>)
  fireEvent.click(screen.getByRole('button', { name: 'Show connection' }))
  assert.ok(screen.getByText('No connection map is available for this book.'))
  assert.equal(screen.queryByRole('img'), null)
})
