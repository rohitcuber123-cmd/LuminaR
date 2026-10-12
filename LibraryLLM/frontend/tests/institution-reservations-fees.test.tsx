import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { test, beforeEach, afterEach } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'
registerHooks({ load(url, context, nextLoad) { return url.endsWith('.css') ? { format: 'module', source: '', shortCircuit: true } : nextLoad(url, context) } })
const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage,
  HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, FormData: dom.window.FormData, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
dom.window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
dom.window.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
const { render, screen, fireEvent, cleanup, waitFor, act } = await import('@testing-library/react')
const { MemoryRouter } = await import('react-router-dom')
const { LibraryReservationsFeesPage: Page, ReservationControl } = await import('../src/pages/LibraryReservationsFees.tsx')
const { minorAmount } = await import('../src/lib/libraryReservationsFees.ts')
const { useInstitutionStore: store } = await import('../src/store/useInstitutionStore.ts')
const { useAuthStore: auth } = await import('../src/store/useAuthStore.ts')
const a = '11111111-1111-4111-8111-111111111111', b = '22222222-2222-4222-8222-222222222222', book = '33333333-3333-4333-8333-333333333333'
const library = (id = a, role: 'ADMIN' | 'LIBRARIAN' | 'GENERAL_USER' = 'ADMIN') => ({ library_id: id, name: id === a ? 'Aurora' : 'Orion', slug: 'library', description: null, library_type: 'PUBLIC_LIBRARY' as const, access_mode: 'PUBLIC' as const,
  membership: { membership_id: b, library_id: id, user_id: 1, role, status: 'ACTIVE' as const, is_owner: role === 'ADMIN', joined_at: '2026-10-09T00:00:00Z' } })
const policy = { policy_id: b, version: 1, rate_minor_per_day: 500, currency: 'INR', grace_days: 0, overdue_enabled: true, charge_stop_policy: 'PHYSICAL_RECEIPT' }
const reservation = { reservation_id: b, library_id: a, library_book_id: book, title: 'Local Manual', accession_number: 'AUR-1', status: 'WAITING', queue_position: 2, queue_length: 3, requested_at: '2026-10-09T01:00:00Z', borrower: { name: 'Member One', email: 'member@example.com' }, availability: { requestable: 0 } }
const fee = { fee_id: book, library_id: a, loan_id: b, title: 'Local Manual', accession_number: 'AUR-1', status: 'OPEN', fee_type: 'OVERDUE', currency: 'INR', original_amount_minor: 1500, current_amount_minor: 1500, balance_minor: 1500, paid_amount_minor: 0, policy_snapshot: policy, calculation: { kind: 'FINAL', due_at: '2026-10-06T01:00:00Z', physical_received_at: '2026-10-09T01:00:00Z' }, created_at: '2026-10-09T01:00:00Z', borrower: { name: 'Member One', email: 'member@example.com' } }
let calls: { path: string; method: string; body: Record<string, unknown> }[], original: typeof fetch, custom: ((path: string, method: string) => Response | Promise<Response> | undefined) | null
function mount(node: React.ReactNode) { return render(<MemoryRouter>{node}</MemoryRouter>) }
beforeEach(() => {
  localStorage.clear(); localStorage.setItem('luminar_token', 'token')
  auth.setState({ token: 'token', isAuthenticated: true, user: { user_id: 1, email: 'reader@example.com', role: 'GENERAL_USER' } })
  store.setState({ owner: 'reader@example.com', session: 'token', libraries: [library()], activeId: a, loading: false, error: null })
  calls = []; original = globalThis.fetch; custom = null
  globalThis.fetch = async (url, options = {}) => {
    const path = String(url), method = options.method || 'GET', body = options.body ? JSON.parse(String(options.body)) : {}
    calls.push({ path, method, body }); const value = custom?.(path, method); if (value) return value
    if (method !== 'GET') return Response.json({ status: 'PARTIALLY_PAID' })
    if (path.endsWith('/config')) return Response.json({ state: 'CANONICAL' })
    if (path.endsWith('/reservation-status')) return Response.json({ state: 'CANONICAL', reservation: null })
    if (path.includes('/settings/fee-policy')) return Response.json({ current: policy })
    if (path.includes(`/fees/${book}`)) return Response.json({ ...fee, ledger: [{ entry_id: b, entry_type: 'CHARGE', amount_minor: 1500, reason: 'Overdue return', created_at: fee.created_at }] })
    if (path.includes('/fees?')) return Response.json({ results: [fee], total: 1, estimates: [] })
    return Response.json({ results: [reservation], total: 1 })
  }
})
afterEach(() => { cleanup(); globalThis.fetch = original })

test('unavailable local book joins waitlist only after confirmation', async () => {
  mount(<ReservationControl libraryId={a} bookId={book} unavailable changed={() => {}} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Join Waitlist' })); assert.equal(calls.filter(c => c.method === 'POST').length, 0)
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' })); await waitFor(() => assert.ok(calls.some(c => c.method === 'POST' && c.body.library_book_id === book && c.body.idempotency_key)))
})
test('own waitlist position and cancellation are shown', async () => {
  custom = path => path.endsWith('/reservation-status') ? Response.json({ state: 'CANONICAL', reservation }) : undefined
  mount(<ReservationControl libraryId={a} bookId={book} unavailable changed={() => {}} />)
  assert.ok(await screen.findByText('Reserved · Position: 2 of 3')); fireEvent.click(screen.getByRole('button', { name: 'Cancel Reservation' })); fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await waitFor(() => assert.ok(calls.some(c => c.path.endsWith(`/reservations/${b}/cancel`))))
})
test('converted reservation links to borrow request without new reserve action', async () => {
  custom = path => path.endsWith('/reservation-status') ? Response.json({ state: 'CANONICAL', reservation: { ...reservation, status: 'CONVERTED', lending_request_id: book } }) : undefined
  mount(<ReservationControl libraryId={a} bookId={book} unavailable changed={() => {}} />)
  assert.ok(await screen.findByRole('link', { name: 'View Borrow Request' })); assert.equal(screen.queryByRole('button', { name: 'Join Waitlist' }), null)
})
test('pending borrow and active loan hide reserve action', async () => {
  custom = path => path.endsWith('/reservation-status') ? Response.json({ state: 'CANONICAL', pending_request_id: b, active_loan: true }) : undefined
  mount(<ReservationControl libraryId={a} bookId={book} unavailable changed={() => {}} />)
  await screen.findByRole('link', { name: 'View Borrow Request' }); assert.equal(screen.queryByRole('button', { name: 'Join Waitlist' }), null)
})
test('member reservations scoped list includes own position and cancel', async () => {
  store.setState({ libraries: [library(a, 'GENERAL_USER'), library(b, 'GENERAL_USER')] }); mount(<Page />); assert.ok(await screen.findByText('2 of 3')); assert.ok(screen.getByRole('button', { name: 'Cancel Reservation' }))
  assert.ok(calls.some(c => c.path.includes(`/libraries/${a}/me/reservations`))); assert.equal(screen.queryByText('member@example.com'), null)
})
test('staff reservation queue shows safe member information', async () => {
  mount(<Page staff />); assert.ok(await screen.findByText(/member@example.com/)); assert.ok(screen.getByText('0 requestable')); assert.ok(screen.getByRole('button', { name: 'Filter' }))
})
test('member fees show library desk text and no financial staff controls', async () => {
  store.setState({ libraries: [library(a, 'GENERAL_USER')] }); mount(<Page fees />); await screen.findByRole('button', { name: 'View Fee Details' })
  assert.ok(screen.getByText(/Payment is handled by the library/)); assert.equal(screen.queryByRole('button', { name: 'Record Payment' }), null); assert.equal(screen.queryByText(/Pay Online/), null)
})
test('fee details contain immutable history and physical timestamp', async () => {
  store.setState({ libraries: [library(a, 'GENERAL_USER')] }); mount(<Page fees />); fireEvent.click(await screen.findByRole('button', { name: 'View Fee Details' })); assert.ok(await screen.findByText('Immutable history')); assert.ok(screen.getByText(/Physically received:/)); assert.ok(screen.getByText(/Overdue return/))
})
test('manual staff payment records exact minor units with stable UUID', async () => {
  mount(<Page staff fees />); fireEvent.click(await screen.findByRole('button', { name: 'Record Payment' })); assert.ok(screen.getByText(/No online payment is processed/))
  fireEvent.change(screen.getByLabelText('Amount (INR)'), { target: { value: '5.25' } }); fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await screen.findByText(/Manual payment record saved/); assert.ok(calls.some(c => c.body.amount_minor === 525 && c.body.method === 'CASH' && c.body.idempotency_key))
})
test('librarian can record but cannot adjust waive or configure policy', async () => {
  store.setState({ libraries: [library(a, 'LIBRARIAN')] }); mount(<Page staff fees />); await screen.findByRole('button', { name: 'Record Payment' })
  for (const name of ['Waive Fee', 'Adjust Fee', 'Create Policy Version']) assert.equal(screen.queryByRole('button', { name }), null)
})
test('waiver requires reason and preserves fee identity', async () => {
  mount(<Page staff fees />); fireEvent.click(await screen.findByRole('button', { name: 'Waive Fee' })); assert.ok((screen.getByRole('button', { name: 'Confirm' }) as HTMLButtonElement).disabled)
  fireEvent.change(screen.getByLabelText('Reason (required)'), { target: { value: 'Library delay' } }); fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await waitFor(() => assert.ok(calls.some(c => c.path.endsWith(`/fees/${book}/waive`) && c.body.reason === 'Library delay')))
})
test('adjustment creates explicit credit and reason', async () => {
  mount(<Page staff fees />); fireEvent.click(await screen.findByRole('button', { name: 'Adjust Fee' })); fireEvent.change(screen.getByLabelText('Amount (INR)'), { target: { value: '1' } }); fireEvent.change(screen.getByLabelText('Reason (required)'), { target: { value: 'Approved credit' } }); fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await waitFor(() => assert.ok(calls.some(c => c.path.endsWith('/adjust') && c.body.amount_minor === 100 && c.body.direction === 'CREDIT')))
})
test('policy change creates version for future loans', async () => {
  mount(<Page staff fees />); fireEvent.click(await screen.findByRole('button', { name: 'Create Policy Version' })); assert.ok(screen.getByText(/Existing loans and charges keep/))
  fireEvent.change(screen.getByLabelText('Daily rate (INR)'), { target: { value: '7' } }); fireEvent.change(screen.getByLabelText('Grace days'), { target: { value: '2' } }); fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await waitFor(() => assert.ok(calls.some(c => c.method === 'POST' && c.path.endsWith('/fee-policy') && c.body.rate_minor_per_day === 700 && c.body.grace_days === 2)))
})
test('library switch closes pending financial dialog and clears old records', async () => {
  mount(<Page staff fees />); fireEvent.click(await screen.findByRole('button', { name: 'Waive Fee' }))
  custom = path => path.includes(`/libraries/${b}/`) && path.includes('/fees?') ? Response.json({ results: [], total: 0 }) : undefined
  await act(async () => { store.setState({ libraries: [library(a), library(b)], activeId: b }) })
  await screen.findByText('No final fees in this view.'); assert.equal(screen.queryByRole('dialog'), null); assert.equal(screen.queryByText('Local Manual'), null)
})
test('late response from old library cannot replace new library records', async () => {
  let release!: (r: Response) => void
  custom = path => path.includes(`/libraries/${a}/me/reservations?`) ? new Promise(resolve => { release = resolve }) : path.includes(`/libraries/${b}/me/reservations?`) ? Response.json({ results: [], total: 0 }) : undefined
  store.setState({ libraries: [library(a, 'GENERAL_USER'), library(b, 'GENERAL_USER')] }); mount(<Page />); await waitFor(() => assert.ok(release)); await act(async () => { store.setState({ libraries: [library(a, 'GENERAL_USER'), library(b, 'GENERAL_USER')], activeId: b }) }); await screen.findByText('No reservations in this view.')
  await act(async () => { release(Response.json({ results: [reservation], total: 1 })) }); assert.equal(screen.queryByText('Local Manual'), null)
})
test('global admin role does not grant tenant staff UI', () => {
  store.setState({ libraries: [library(a, 'GENERAL_USER')] }); auth.setState({ user: { user_id: 1, email: 'reader@example.com', role: 'ADMIN' } }); mount(<Page staff fees />); assert.ok(screen.getByText(/Active staff membership is required/)); assert.equal(calls.length, 0)
})
test('decimal conversion is exact and rejects unsafe precision', () => {
  assert.equal(minorAmount('0.29'), 29); assert.equal(minorAmount('9000000.01'), 900000001)
  for (const value of ['1.005', '-2', 'NaN', '1e9', '10000000001']) assert.throws(() => minorAmount(value))
})
