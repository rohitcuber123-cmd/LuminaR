import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { test, beforeEach, afterEach } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'
import type { LibraryBook, InventoryPreview } from '../src/lib/libraryInventory'

registerHooks({ load(url, context, nextLoad) { return url.endsWith('.css') ? { format: 'module', source: '', shortCircuit: true } : nextLoad(url, context) } })
const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage,
  HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, FormData: dom.window.FormData, File: dom.window.File, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
dom.window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
dom.window.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
const { render, screen, fireEvent, cleanup, waitFor, act } = await import('@testing-library/react')
const { MemoryRouter } = await import('react-router-dom')
const { LibraryInventoryPage, BookEditor } = await import('../src/pages/LibraryInventory.tsx')
const { LibraryCirculationPage, BookRequestControl } = await import('../src/pages/LibraryCirculation.tsx')
const { useInstitutionStore: store } = await import('../src/store/useInstitutionStore.ts')
const { useAuthStore: auth } = await import('../src/store/useAuthStore.ts')
const a = '11111111-1111-4111-8111-111111111111', b = '22222222-2222-4222-8222-222222222222', bookId = '33333333-3333-4333-8333-333333333333'
const library = (id = a, role: 'ADMIN' | 'LIBRARIAN' | 'GENERAL_USER' = 'ADMIN') => ({ library_id: id, name: id === a ? 'Aurora' : 'Orion', slug: 'library', description: null,
  library_type: 'PRIVATE_INSTITUTION' as const, access_mode: 'PRIVATE_CODE' as const,
  membership: { membership_id: b, library_id: id, user_id: 1, role, status: 'ACTIVE' as const, is_owner: role === 'ADMIN', joined_at: '2026-10-08T00:00:00Z' } })
const book = (patch: Partial<LibraryBook> = {}): LibraryBook => ({ library_book_id: bookId, library_id: a, accession_number: 'AUR-000001', title: 'Local Laboratory Manual',
  subjects: ['Systems'], authors: [], global_work_id: null, isbn_10: null, isbn_13: null, publisher: null, publication_year: null, edition: null, language: null,
  description: null, shelf_location: null, local_call_number: null, local_tags: [], acquisition_note: null, status: 'ACTIVE', needs_review: false,
  holding: { holding_id: b, library_id: a, library_book_id: bookId, total_copies: 1, available_copies: 1, shelf_location: null, call_number: null, quantity_semantics: 'INVENTORY_SNAPSHOT_NOT_CIRCULATION' }, ...patch })
const job = (patch: Partial<InventoryPreview> = {}): InventoryPreview => ({ import_id: bookId, library_id: a, filename: 'inventory.csv', status: 'PREVIEW', rows_total: 3, rows_valid: 2,
  rows_invalid: 1, global_matches: 0, new_library_records: 1, existing_holdings: 0, possible_duplicates: 1,
  rows: [{ row_number: 2, title: 'Local Manual', subjects: ['Systems'], classification: 'NEW_LOCAL' },
    { row_number: 3, title: 'Annual Report', classification: 'POSSIBLE_DUPLICATE', reason: 'This item may already exist; it remains separate.' },
    { row_number: 4, classification: 'INVALID', reason: 'MISSING_REQUIRED_SUBJECT' }], ...patch })
let calls: { path: string; method: string; body: Record<string, unknown> | FormData | undefined }[], rows: LibraryBook[], custom: ((path: string, method: string, body: unknown) => Response | Promise<Response> | undefined) | null
let original: typeof fetch
function mount(node: React.ReactNode) { return render(<MemoryRouter>{node}</MemoryRouter>) }
beforeEach(() => {
  localStorage.clear(); localStorage.setItem('luminar_token', 'token-a')
  auth.setState({ token: 'token-a', isAuthenticated: true, user: { user_id: 1, email: 'reader@example.com', role: 'GENERAL_USER' } })
  store.setState({ owner: 'reader@example.com', session: 'token-a', libraries: [library()], activeId: a, loading: false, error: null })
  calls = []; rows = [book()]; custom = null; original = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    const path = String(url), method = options.method || 'GET'
    const body = options.body instanceof FormData ? options.body : options.body ? JSON.parse(String(options.body)) : undefined
    calls.push({ path, method, body }); const result = custom?.(path, method, body); if (result) return result
    if (path.endsWith('/lending/config')) return Response.json({ state: 'CANONICAL' })
    if (path.includes('/me/loans')) return Response.json({ results: [loanRow], total: 1 })
    if (path.includes('requests') && method === 'GET') return Response.json({ results: [requestRow], total: 1, pending_counts: { BORROW: 1, RETURN: 2 } })
    if (path.includes('requests') || path.includes('/loans/') || path.includes('/staff/lending/')) return Response.json({ status: 'PENDING' })
    if (path.includes('/imports/preview')) return Response.json(job(), { status: 201 })
    if (path.includes('/imports/') && path.endsWith('/apply')) return Response.json({ import_id: bookId, library_id: a, status: 'PARTIAL', created_records: 2, increased_holdings: 0, skipped_existing: 0, invalid_rows: 1,
      rows: job().rows.map(row => ({ ...row, outcome: row.classification === 'INVALID' ? 'INVALID' : 'CREATED', accession_number: row.classification === 'INVALID' ? undefined : 'AUR-000002' })) })
    if (path.includes('/copies')) return Response.json({ results: [] })
    if (method === 'GET') return Response.json({ results: rows, total: rows.length, has_more: false, role: store.getState().libraries.find(l => l.library_id === store.getState().activeId)?.membership?.role || 'GENERAL_USER' })
    if (method === 'POST' || method === 'PATCH') { const saved = book({ ...(body as Partial<LibraryBook>), accession_number: 'AUR-000002' }); rows = [saved]; return Response.json(saved, { status: method === 'POST' ? 201 : 200 }) }
    return Response.json(book())
  }
})
afterEach(() => { cleanup(); globalThis.fetch = original })

const requestRow = { lending_request_id: bookId, loan_id: null, library_id: a, library_book_id: bookId, title: 'Local Laboratory Manual', accession_number: 'AUR-000001', status: 'PENDING', allocation_mode: 'AGGREGATE', requested_at: '2026-10-09T00:00:00Z', shelf_location: 'Room 2 / A', proposed_due_at: '2026-10-23T00:00:00Z', borrower: { name: 'Member Two', email: 'member@example.com', membership_status: 'ACTIVE' }, availability: { requestable: 0, pending_holds: 1, active_loans: 0 } }
const loanRow = { ...requestRow, loan_id: b, lending_request_id: undefined, status: 'ACTIVE', due_at: '2026-10-23T00:00:00Z', borrowed_at: '2026-10-09T00:00:00Z' }

test('member sees pending borrow and separate active loans/history', async () => {
  store.setState({ libraries: [library(a, 'GENERAL_USER')] }); mount(<LibraryCirculationPage />); await screen.findByText('Borrow Requests')
  assert.ok(screen.getByText(/PENDING APPROVAL/)); assert.ok(screen.getByText('Current Loans')); assert.ok(screen.getByText('Loan History'))
  assert.equal(screen.queryByRole('button', { name: 'Approve & Issue' }), null)
})
test('cancel own pending request requires confirmation and bound UUID/key', async () => {
  store.setState({ libraries: [library(a, 'GENERAL_USER')] }); mount(<LibraryCirculationPage />); fireEvent.click(await screen.findByRole('button', { name: 'Cancel Request' }))
  assert.equal(calls.filter(c => c.method === 'POST').length, 0)
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await waitFor(() => assert.ok(calls.some(c => c.path.endsWith(`/borrow-requests/${bookId}/cancel`) && !!(c.body as Record<string, unknown>).idempotency_key)))
})
test('return request explains loan remains active and sends loan UUID', async () => {
  store.setState({ libraries: [library(a, 'GENERAL_USER')] }); mount(<LibraryCirculationPage />); fireEvent.click(await screen.findByRole('button', { name: 'Request Return' }))
  assert.ok(screen.getByText(/Your loan stays active/)); fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await screen.findByText(/Return requested. Your loan remains active/)
  assert.ok(calls.some(c => c.path.includes(`/loans/${b}/return-request`)))
})
test('pending physical return stays current and blocks return/renew controls', async () => {
  custom = path => path.includes('/me/loans') ? Response.json({ results: [{ ...loanRow, pending_return_request_id: bookId, return_requested_at: '2026-10-09T02:00:00Z' }], total: 1 }) : undefined
  store.setState({ libraries: [library(a, 'GENERAL_USER')] }); mount(<LibraryCirculationPage />); assert.ok(await screen.findByText(/RETURN REQUESTED/))
  assert.ok((screen.getByRole('button', { name: 'Request Return' }) as HTMLButtonElement).disabled)
  assert.ok((screen.getByRole('button', { name: 'Renew Loan' }) as HTMLButtonElement).disabled)
})
test('renew sends expected stored due date and durable key', async () => {
  store.setState({ libraries: [library(a, 'GENERAL_USER')] }); mount(<LibraryCirculationPage />); fireEvent.click(await screen.findByRole('button', { name: 'Renew Loan' })); fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await waitFor(() => assert.ok(calls.some(c => c.path.endsWith('/renew') && (c.body as Record<string, unknown>).expected_due_at === loanRow.due_at)))
})
test('staff sees borrower identity/membership/shelf and counts', async () => {
  mount(<LibraryCirculationPage staff />); assert.ok(await screen.findByText('Borrow Requests (1)'))
  assert.ok(screen.getByText('Return Requests (2)')); assert.ok(screen.getByText(/member@example.com/)); assert.ok(screen.getByText('Room 2 / A')); assert.ok(screen.getByText(/0 requestable/))
})
test('approve issue dialog has borrower/accession/shelf/due preview', async () => {
  mount(<LibraryCirculationPage staff />); fireEvent.click(await screen.findByRole('button', { name: 'Approve & Issue' }))
  assert.ok(screen.getByText(/handing this book/)); assert.ok(screen.getByText(/Borrower: Member Two/)); assert.ok(screen.getByText(/Shelf \/ Location: Room 2/))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' })); await waitFor(() => assert.ok(calls.some(c => c.path.endsWith('/approve'))))
})
test('staff rejection allows bounded reason', async () => {
  mount(<LibraryCirculationPage staff />); fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))
  fireEvent.change(screen.getByLabelText('Reason (optional)'), { target: { value: 'Physical condition requires review' } }); fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await waitFor(() => assert.ok(calls.some(c => c.path.endsWith('/reject') && (c.body as Record<string, unknown>).reason === 'Physical condition requires review')))
})
test('return staff tab has physical receipt dialog', async () => {
  mount(<LibraryCirculationPage staff />); fireEvent.click(await screen.findByRole('button', { name: 'Return Requests (2)' }))
  fireEvent.click(await screen.findByRole('button', { name: 'Confirm Received' })); assert.ok(screen.getByText(/physically received and verified/))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm' })); await waitFor(() => assert.ok(calls.some(c => c.path.includes('/return-requests/') && c.path.endsWith('/confirm'))))
})
test('queue filters remain canonical-library scoped', async () => {
  mount(<LibraryCirculationPage staff />); await screen.findByRole('button', { name: 'Filter' })
  fireEvent.change(screen.getByLabelText('Title / Accession'), { target: { value: 'AUR-000001' } }); fireEvent.change(screen.getByLabelText('Borrower ID'), { target: { value: '2' } }); fireEvent.click(screen.getByRole('button', { name: 'Filter' }))
  await waitFor(() => assert.ok(calls.some(c => c.path.includes(`/libraries/${a}/staff/lending/borrow-requests?`) && c.path.includes('user_id=2') && c.path.includes('AUR-000001'))))
})
test('nonstaff cannot fetch staff queue despite global role', async () => {
  store.setState({ libraries: [library(a, 'GENERAL_USER')] }); auth.setState({ user: { user_id: 1, email: 'reader@example.com', role: 'ADMIN' } })
  mount(<LibraryCirculationPage staff />); assert.ok(screen.getByText(/Active staff membership is required/)); assert.equal(calls.length, 0)
})
test('logout clears circulation and membership admission', async () => {
  store.setState({ libraries: [library(a, 'GENERAL_USER')] }); mount(<LibraryCirculationPage />); await screen.findByRole('button', { name: 'Request Return' })
  act(() => store.setState({ libraries: [], activeId: null })); assert.equal(screen.queryByRole('button', { name: 'Request Return' }), null)
})
test('library switch discards queue/dialog and outstanding requests', async () => {
  mount(<LibraryCirculationPage staff />); fireEvent.click(await screen.findByRole('button', { name: 'Approve & Issue' }))
  act(() => store.setState({ libraries: [library(a), library(b)], activeId: b }))
  assert.equal(screen.queryByRole('dialog'), null); await screen.findByRole('heading', { name: 'Circulation', level: 1 })
  await waitFor(() => assert.ok(calls.some(c => c.path.startsWith(`/api/libraries/${b}/`))))
})
test('failed confirmation retains the same key for retry', async () => {
  let attempts = 0; custom = (path, method) => path.endsWith('/approve') && method === 'POST' ? ++attempts === 1 ? Response.json({ detail: 'Please refresh' }, { status: 409 }) : Response.json({ status: 'APPROVED' }) : undefined
  mount(<LibraryCirculationPage staff />); fireEvent.click(await screen.findByRole('button', { name: 'Approve & Issue' })); fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await screen.findAllByText(/Please refresh/); fireEvent.click(screen.getByRole('button', { name: 'Confirm' })); await waitFor(() => assert.equal(attempts, 2))
  const writes = calls.filter(c => c.path.endsWith('/approve')); assert.equal((writes[0].body as Record<string, unknown>).idempotency_key, (writes[1].body as Record<string, unknown>).idempotency_key)
})
test('unactivated library admin can review explicit cutover', async () => {
  custom = path => path.endsWith('/lending/config') ? Response.json({ state: 'LEGACY' }) : undefined
  mount(<LibraryCirculationPage staff />); fireEvent.click(await screen.findByRole('button', { name: 'Enable Approval Circulation' })); assert.ok(screen.getByText(/Active legacy loans require/))
})
test('unactivated member has no cutover authority', async () => {
  custom = path => path.endsWith('/lending/config') ? Response.json({ state: 'LEGACY' }) : undefined
  store.setState({ libraries: [library(a, 'GENERAL_USER')] }); mount(<LibraryCirculationPage />); await screen.findByText(/staff must reconcile/); assert.equal(screen.queryByRole('button', { name: 'Enable Approval Circulation' }), null)
})
test('inventory canonical request creates a hold using book UUID', async () => {
  store.setState({ libraries: [library(a, 'GENERAL_USER')] })
  rows = [Object.assign(book(), { availability: { total: 1, requestable: 1, pending_holds: 0, active_loans: 0, circulation_status: 'CIRCULATING' } })]
  mount(<LibraryInventoryPage />); fireEvent.click(await screen.findByRole('button', { name: 'Request Book' })); await screen.findByText(/Book requested. Awaiting librarian approval/)
  assert.ok(calls.some(c => c.path.endsWith('/borrow-requests') && (c.body as Record<string, unknown>).library_book_id === bookId))
})
test('request completion survives StrictMode effect replay and prevents duplicate submission', async () => {
  let refreshed = 0
  mount(<React.StrictMode><BookRequestControl libraryId={a} bookId={bookId} availability={{ requestable: 1, circulation_status: 'CIRCULATING' }} changed={() => { refreshed++ }} /></React.StrictMode>)
  fireEvent.click(screen.getByRole('button', { name: 'Request Book', exact: true }))
  const submitted = await screen.findByRole('button', { name: 'Request submitted', exact: true })
  assert.ok((submitted as HTMLButtonElement).disabled)
  assert.equal(refreshed, 1)
  assert.equal(calls.filter(c => c.path.endsWith('/borrow-requests') && c.method === 'POST').length, 1)
})
for (const status of ['REFERENCE_ONLY', 'TEMPORARILY_UNAVAILABLE', 'WITHDRAWN']) test(`${status} disables member request`, async () => {
  store.setState({ libraries: [library(a, 'GENERAL_USER')] })
  rows = [Object.assign(book(), { availability: { requestable: 0, pending_holds: 0, active_loans: 0, circulation_status: status } })]; mount(<LibraryInventoryPage />)
  assert.ok((await screen.findByRole('button', { name: 'Request Book' }) as HTMLButtonElement).disabled)
})
test('add book shows prominent shelf and stock defaults', () => {
  mount(<BookEditor libraryId={a} onSaved={() => {}} />); assert.ok(screen.getByText('Physical copy'))
  assert.equal((screen.getByLabelText('Circulation Status') as HTMLSelectElement).value, 'CIRCULATING')
  assert.equal(screen.getByLabelText('Shelf / Location').closest('details'), null)
})
test('canonical Manage Stock has no editable requestable count', async () => {
  custom = (path, method) => path.includes('/inventory/books') && method === 'GET' ? Response.json({ results: [book()], total: 1, role: 'ADMIN', lending_state: 'CANONICAL' }) : undefined
  mount(<LibraryInventoryPage />); fireEvent.click(await screen.findByRole('button', { name: 'Actions for AUR-000001' })); fireEvent.click(screen.getByRole('menuitem', { name: 'Manage Stock & Shelf' }))
  assert.ok(screen.getByLabelText('Total copies')); assert.equal(screen.queryByLabelText('Available inventory snapshot'), null)
  fireEvent.click(screen.getByRole('button', { name: 'Save Stock' })); await waitFor(() => assert.ok(calls.some(c => c.path.endsWith('/stock') && c.method === 'PUT')))
})

