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
const { LibraryInventoryPage, BookEditor, InventoryImport } = await import('../src/pages/LibraryInventory.tsx')
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
function minimalForm() {
  fireEvent.change(screen.getByLabelText('Title *'), { target: { value: ' Operating Systems Laboratory Manual ' } })
  fireEvent.change(screen.getByLabelText(/Subject \/ Genre \*/), { target: { value: 'Operating Systems; Lab' } })
}
async function uploadFile(text = 'title,subject\nManual,Systems\n') {
  const file = new File([text], 'inventory.csv', { type: 'text/csv' })
  fireEvent.change(screen.getByLabelText('Inventory file'), { target: { files: [file] } })
  fireEvent.submit(screen.getByRole('button', { name: 'Preview Inventory' }).closest('form')!)
  await screen.findByText('Inventory preview')
}
beforeEach(() => {
  localStorage.clear(); localStorage.setItem('luminar_token', 'token-a')
  auth.setState({ token: 'token-a', isAuthenticated: true, user: { user_id: 1, email: 'reader@example.com', role: 'GENERAL_USER' } })
  store.setState({ owner: 'reader@example.com', session: 'token-a', libraries: [library()], activeId: a, loading: false, error: null })
  calls = []; rows = [book()]; custom = null; original = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    const path = String(url), method = options.method || 'GET'
    const body = options.body instanceof FormData ? options.body : options.body ? JSON.parse(String(options.body)) : undefined
    calls.push({ path, method, body }); const result = custom?.(path, method, body); if (result) return result
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

test('inventory reads current UUID library and distinguishes inventory snapshots', async () => {
  mount(<LibraryInventoryPage />); await screen.findByText('Local Laboratory Manual')
  assert.ok(screen.getByRole('heading', { name: 'Inventory' }))
  assert.ok(calls[0].path.includes(`/libraries/${a}/inventory/books`))
  assert.ok(screen.getByText(/Inventory counts are snapshots/))
  assert.equal(screen.queryByRole('button', { name: /Borrow|Read Now/ }), null)
})

test('only title and subject are required; all optional metadata can be empty', async () => {
  let saved: LibraryBook | null = null
  mount(<BookEditor libraryId={a} onSaved={row => { saved = row }} />)
  const required = [...document.querySelectorAll<HTMLInputElement>('input[required]')]
  assert.deepEqual(required.map(input => input.name), ['title', 'subjects', 'copies'])
  minimalForm(); fireEvent.click(screen.getByRole('button', { name: 'Save New Book' }))
  await waitFor(() => assert.ok(saved))
  const body = calls[0].body as Record<string, unknown>
  assert.equal(body.title, 'Operating Systems Laboratory Manual'); assert.deepEqual(body.subjects, ['Operating Systems', 'Lab'])
  assert.equal(body.isbn, null); assert.equal(body.global_work_id, null); assert.deepEqual(body.authors, [])
  assert.equal(body.copies, 1); assert.equal('accession_number' in body, false); assert.equal('library_id' in body, false)
})

for (const [label, field, value] of [['Author(s)', 'authors', 'Forouzan'], ['ISBN', 'isbn', '9780306406157'], ['Publisher', 'publisher', 'Institution Press'],
  ['Publication Year', 'publication_year', '2020'], ['Edition', 'edition', '2'], ['Language', 'language', 'Telugu'], ['Description', 'description', 'Local text']]) {
  test(`optional ${label} is accepted without other optional fields`, async () => {
    mount(<BookEditor libraryId={a} onSaved={() => {}} />); minimalForm(); fireEvent.change(screen.getByLabelText(label === 'Author(s)' ? /^Author\(s\)/ : label), { target: { value } })
    fireEvent.click(screen.getByRole('button', { name: 'Save New Book' })); await waitFor(() => assert.equal(calls.length, 1))
    const actual = (calls[0].body as Record<string, unknown>)[field]
    assert.deepEqual(actual, field === 'authors' ? [value] : field === 'publication_year' ? Number(value) : value)
  })
}

test('missing meaningful subject shows row-independent form error', () => {
  mount(<BookEditor libraryId={a} onSaved={() => {}} />)
  fireEvent.change(screen.getByLabelText('Title *'), { target: { value: 'Manual' } })
  fireEvent.change(screen.getByLabelText(/Subject \/ Genre \*/), { target: { value: ' ; ' } })
  fireEvent.submit(screen.getByRole('button', { name: 'Save New Book' }).closest('form')!)
  assert.ok(screen.getByRole('alert').textContent?.includes('Subject / Genre')); assert.equal(calls.length, 0)
})

test('add without work ID displays generated accession after save', async () => {
  mount(<LibraryInventoryPage />); await screen.findByText('Local Laboratory Manual')
  fireEvent.click(screen.getByRole('button', { name: 'Add Book' })); minimalForm()
  fireEvent.click(screen.getByRole('button', { name: 'Save New Book' }))
  await screen.findByText(/Book added successfully. Format:/)
  assert.equal((calls.find(call => call.method === 'POST')!.body as Record<string, unknown>).global_work_id, null)
})

test('accession is readonly during metadata edit and never sent in payload', async () => {
  mount(<BookEditor libraryId={a} initial={book()} onSaved={() => {}} />)
  assert.equal((screen.getByLabelText('Accession number') as HTMLInputElement).readOnly, true)
  fireEvent.click(screen.getByRole('button', { name: 'Save Book' })); await waitFor(() => assert.ok(calls.length))
  assert.equal(calls[0].method, 'PATCH'); assert.equal('accession_number' in (calls[0].body as object), false)
})

test('local and global badges are plain text and do not expose digital content', async () => {
  rows = [book(), book({ library_book_id: b, title: '<script>Private report</script>', global_work_id: 'OL-Systems' })]
  mount(<LibraryInventoryPage />); await screen.findByText('<script>Private report</script>')
  assert.ok(screen.getByText('Library record')); assert.ok(screen.getByText('Global linked'))
  assert.equal(document.querySelector('script'), null)
})

test('inventory search and local/review filters remain bound to selected library', async () => {
  mount(<LibraryInventoryPage />); await screen.findByText('Local Laboratory Manual')
  fireEvent.change(screen.getByLabelText('Search library inventory'), { target: { value: 'QA 77' } })
  fireEvent.click(screen.getByRole('button', { name: 'Search' })); await waitFor(() => assert.ok(calls.some(c => c.path.includes('search=QA%2077'))))
  fireEvent.change(screen.getByLabelText('Record filter'), { target: { value: 'review' } })
  await waitFor(() => assert.ok(calls.some(c => c.path.includes('kind=review'))))
  assert.ok(calls.every(c => c.path.includes(`/libraries/${a}/`)))
})

test('general member can read inventory but sees no write controls', async () => {
  store.setState({ libraries: [library(a, 'GENERAL_USER')] })
  mount(<LibraryInventoryPage />); await screen.findByText('Local Laboratory Manual')
  for (const name of ['Add Book', 'Upload Inventory', 'Edit', 'Quantities', 'Withdraw', 'Link Global Catalogue Book']) assert.equal(screen.queryByRole('button', { name }), null)
})

test('outsider/no membership does not fetch or display private inventory', () => {
  store.setState({ libraries: [], activeId: null })
  mount(<LibraryInventoryPage />)
  assert.ok(screen.getByText(/Select a library with active membership/)); assert.equal(calls.length, 0)
})

test('server membership denial clears inventory and form admission', async () => {
  custom = () => Response.json({ detail: 'Library resource not found.' }, { status: 404 })
  mount(<LibraryInventoryPage />); await screen.findByRole('alert')
  assert.equal(screen.queryByText('Local Laboratory Manual'), null)
  assert.equal((screen.getByRole('button', { name: 'Add Book' }) as HTMLButtonElement).disabled, true)
})

test('switching library refreshes inventory and discards stale private response', async () => {
  let resolveOld!: (value: Response) => void
  custom = path => path.includes(`/libraries/${a}/`) ? new Promise(resolve => { resolveOld = resolve }) : Response.json({ results: [book({ library_id: b, title: 'Orion Manual', accession_number: 'ORI-000001' })], total: 1, has_more: false, role: 'ADMIN' })
  mount(<LibraryInventoryPage />); await waitFor(() => assert.ok(resolveOld))
  await act(async () => store.setState({ libraries: [library(), library(b)], activeId: b }))
  await screen.findByText('Orion Manual')
  await act(async () => resolveOld(Response.json({ results: [book({ title: 'Aurora confidential old response' })], total: 1, has_more: false, role: 'ADMIN' })))
  assert.equal(screen.queryByText('Aurora confidential old response'), null); assert.ok(screen.getByText('Orion Manual'))
})

test('logout immediately removes private inventory', async () => {
  mount(<LibraryInventoryPage />); await screen.findByText('Local Laboratory Manual')
  await act(async () => store.getState().reset())
  assert.equal(screen.queryByText('Local Laboratory Manual'), null)
})

test('upload help and minimal template require only title/subject', () => {
  mount(<InventoryImport libraryId={a} onCommitted={() => {}} />)
  assert.ok(screen.getByText('title')); assert.ok(screen.getByText('subject or genre'))
  assert.ok(screen.getByRole('link', { name: 'Download minimal template' }).getAttribute('href')?.includes('title%2Csubject'))
})

test('minimum dataset preview shows classifications, duplicates, row errors and no allocated accession', async () => {
  mount(<InventoryImport libraryId={a} onCommitted={() => {}} />); await uploadFile()
  assert.ok(screen.getByText('2 valid')); assert.ok(screen.getByText('1 invalid')); assert.ok(screen.getByText('1 possible duplicates'))
  assert.ok(screen.getByText('NEW LOCAL')); assert.ok(screen.getByText('POSSIBLE DUPLICATE')); assert.ok(screen.getByText('MISSING_REQUIRED_SUBJECT'))
  assert.ok(screen.getAllByText('Assigned on creation').length); assert.ok(calls[0].body instanceof FormData)
  assert.equal(calls.length, 1)
})

test('mixed dataset preview displays global and local paths', async () => {
  custom = path => path.includes('/preview') ? Response.json(job({ global_matches: 1, rows: [{ row_number: 2, title: 'Linked', classification: 'GLOBAL_MATCH' }, { row_number: 3, title: 'Local', classification: 'NEW_LOCAL' }] })) : undefined
  mount(<InventoryImport libraryId={a} onCommitted={() => {}} />); await uploadFile()
  assert.ok(screen.getByText('GLOBAL MATCH')); assert.ok(screen.getByText('NEW LOCAL'))
})

test('confirm import sends bound ID and explicit duplicate policy and preserves result after refresh', async () => {
  mount(<LibraryInventoryPage />); await screen.findByText('Local Laboratory Manual')
  fireEvent.click(screen.getByRole('button', { name: 'Upload Inventory' })); await uploadFile()
  fireEvent.change(screen.getByLabelText('Existing holding policy'), { target: { value: 'increase_quantity' } })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm Import' }))
  await screen.findByText(/PARTIAL: 2 created/)
  await waitFor(() => assert.ok(calls.filter(c => c.method === 'GET').length >= 2))
  assert.ok(screen.getByText('Import result'))
  const apply = calls.find(c => c.path.endsWith('/apply'))!
  assert.equal(apply.path, `/api/libraries/${a}/inventory/imports/${bookId}/apply`)
  assert.deepEqual(apply.body, { existing_policy: 'increase_quantity' })
})

test('apply permission failure remains an actionable error without fake success', async () => {
  custom = path => path.endsWith('/apply') ? Response.json({ detail: 'Insufficient library permissions.' }, { status: 403 }) : undefined
  mount(<InventoryImport libraryId={a} onCommitted={() => {}} />); await uploadFile()
  fireEvent.click(screen.getByRole('button', { name: 'Confirm Import' })); await screen.findByRole('alert')
  assert.equal(screen.queryByText('Import result'), null)
})

test('withdraw confirmation preserves accession and uses canonical identifiers', async () => {
  mount(<LibraryInventoryPage />); await screen.findByText('Local Laboratory Manual')
  fireEvent.click(screen.getByRole('button', { name: 'Actions for AUR-000001' })); fireEvent.click(screen.getByRole('menuitem', { name: 'Withdraw' })); await screen.findByRole('dialog')
  assert.ok(screen.getByText(/history and accession number will be preserved/))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm Withdraw' }))
  await screen.findByText(/Book withdrawn. Its accession will never be reused/)
  assert.ok(calls.some(c => c.method === 'DELETE' && c.path.endsWith(`/books/${bookId}`)))
})

test('later global link uses separate validated action and preserves local identity', async () => {
  mount(<LibraryInventoryPage />); await screen.findByText('Local Laboratory Manual')
  fireEvent.click(screen.getByRole('button', { name: 'Actions for AUR-000001' })); fireEvent.click(screen.getByRole('menuitem', { name: 'Link Global Catalogue Book' }))
  fireEvent.change(screen.getByLabelText('Catalogue reference'), { target: { value: 'OL-Systems' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save Global Link' }))
  await screen.findByText(/local identity and accession preserved/)
  assert.deepEqual(calls.find(c => c.path.endsWith('/global-link'))?.body, { global_work_id: 'OL-Systems' })
})
