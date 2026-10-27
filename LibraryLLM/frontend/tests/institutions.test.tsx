import { chooseSelect } from './select-control'
import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { test, beforeEach, afterEach } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'
import type { Library, Invitation, LibraryRole, MemberRow } from '../src/lib/institutions'

registerHooks({ load(url, context, nextLoad) { return url.endsWith('.css') ? { format: 'module', source: '', shortCircuit: true } : nextLoad(url, context) } })
const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, FormData: dom.window.FormData, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
dom.window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
dom.window.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
const { render, screen, fireEvent, cleanup, waitFor, act, within } = await import('@testing-library/react')
const { MemoryRouter, Routes, Route } = await import('react-router-dom')
const { RegisterLibraryPage, ExploreLibrariesPage, PendingInvitationsPage, InvitationPage } = await import('../src/pages/Institutions.tsx')
const { InstitutionPanel } = await import('../src/pages/InstitutionPanel.tsx')
const { LibrarySwitcher } = await import('../src/components/LibrarySwitcher.tsx')
const { default: ProtectedRoute } = await import('../src/components/ProtectedRoute.tsx')
const { useInstitutionStore: store } = await import('../src/store/useInstitutionStore.ts')
const { useAuthStore: auth } = await import('../src/store/useAuthStore.ts')
const id = '11111111-1111-4111-8111-111111111111', id2 = '22222222-2222-4222-8222-222222222222'
const library = (patch: Partial<Library> = {}): Library => ({ library_id: id, name: 'Aurora Public Library', slug: 'aurora-library', description: 'Books for our community.', library_type: 'PUBLIC_LIBRARY', access_mode: 'PUBLIC', address: { city: 'Hyderabad', region: 'Telangana' }, ...patch })
const member = (role: LibraryRole = 'ADMIN', owner = true): NonNullable<Library['membership']> => ({ membership_id: id2, library_id: id, user_id: 1, role, status: 'ACTIVE', is_owner: owner, joined_at: '2026-10-08T10:00:00Z' })
const invitation = (patch: Partial<Invitation> = {}): Invitation => ({ invitation_id: id2, library_id: id, library_name: 'Orion Research', email_normalized: 'staff@example.com', role: 'LIBRARIAN', status: 'PENDING', invited_by_user_id: 1, expires_at: '2026-10-15T10:00:00Z', ...patch })
let calls: { url: string; method: string; body: Record<string, unknown> | undefined }[]
let rows: Library[], invites: Invitation[], members: MemberRow[], handler: ((path: string, method: string, body: Record<string, unknown> | undefined) => Response | undefined) | null, original: typeof fetch

function scoped(role: LibraryRole = 'ADMIN', owner = true, privateLibrary = true) {
  const row = library({ access_mode: privateLibrary ? 'PRIVATE_CODE' : 'PUBLIC', library_type: privateLibrary ? 'PRIVATE_INSTITUTION' : 'PUBLIC_LIBRARY', membership: member(role, owner) })
  store.setState({ owner: 'reader@example.com', session: 'token-a', libraries: [row], activeId: id, loading: false, error: null }); rows = [row]
  return row
}
function mount(component: React.ReactNode, path = '/') { return render(<MemoryRouter initialEntries={[path]}>{component}</MemoryRouter>) }
beforeEach(() => {
  localStorage.clear(); localStorage.setItem('luminar_token', 'token-a')
  auth.setState({ user: { user_id: 1, email: 'reader@example.com', role: 'GENERAL_USER' }, token: 'token-a', isAuthenticated: true, loading: false })
  store.setState({ owner: 'reader@example.com', session: 'token-a', libraries: [], activeId: null, patronLibraryId: null, staffLibraryId: null, workspace: null, loading: false, error: null })
  calls = []; rows = []; invites = [invitation()]; members = [{ ...member(), name: 'Owner', email: 'owner@example.com' }, { ...member('LIBRARIAN', false), membership_id: id, user_id: 2, name: 'Staff', email: 'staff@example.com' }]; handler = null
  original = globalThis.fetch
  globalThis.fetch = async (url, options = {}) => {
    const path = String(url), method = options.method || 'GET', body = options.body ? JSON.parse(String(options.body)) : undefined
    calls.push({ url: path, method, body })
    const result = handler?.(path, method, body); if (result) return result
    if (path === '/api/libraries/register') { const row = library({ membership: member() }); rows = [row]; return Response.json({ library: row, membership: row.membership }, { status: 201 }) }
    if (path.includes('/context') || path.endsWith('/join')) { const row = rows.find(r => path.includes(r.library_id)) || library(); const updated = { ...row, membership: row.membership || member('GENERAL_USER', false) }; rows = [...rows.filter(r => r.library_id !== updated.library_id), updated]; return Response.json({ library: updated, membership: updated.membership }) }
    if (path.startsWith('/api/me/libraries')) return Response.json({ results: rows.filter(r => r.membership), has_more: false })
    if (path.startsWith('/api/me/invitations')) return Response.json({ results: invites, total: invites.length })
    if (path.startsWith('/api/libraries?')) return Response.json({ results: rows, total: rows.length, has_more: false })
    if (path.includes('/memberships')) return Response.json(method === 'GET' ? { results: members, total: members.length } : {})
    if (path.includes('/audit')) return Response.json({ results: [], total: 0 })
    if (path.endsWith('/access')) return Response.json({ access_code_set: true, access_code_changed_at: '2026-10-08T10:00:00Z', access_code_changed_by: 1 })
    if (path.endsWith('/accept')) { const row = library({ membership: member('LIBRARIAN', false) }); rows = [row]; return Response.json({ library: row, membership: row.membership }) }
    if (path.includes('/invitations')) return Response.json(method === 'GET' ? { results: invites, total: invites.length } : { invitation: invitation(), invite_token: 'x'.repeat(43) })
    return Response.json({})
  }
})
afterEach(() => { cleanup(); globalThis.fetch = original })

test('registration shows public/private choices and hides public codes', () => {
  mount(<RegisterLibraryPage />)
  assert.ok(screen.getByLabelText('Public Library'))
  assert.ok(screen.getByLabelText('Private Institution'))
  assert.equal(screen.queryByLabelText('New Access Code'), null)
  fireEvent.click(screen.getByLabelText('Private Institution'))
  assert.equal(screen.getByLabelText('New Access Code').getAttribute('type'), 'password')
  fireEvent.change(screen.getByLabelText('New Access Code'), { target: { value: 'secret passphrase' } })
  fireEvent.click(screen.getByLabelText('Public Library'))
  assert.equal(screen.queryByLabelText('New Access Code'), null)
})

for (const privateLibrary of [false, true]) test(`registration success (${privateLibrary ? 'private' : 'public'}) selects owner library without global role escalation`, async () => {
  mount(<Routes><Route path="/" element={<RegisterLibraryPage />} /><Route path="/staff/libraries/:libraryId" element={<p>Institution administration</p>} /></Routes>)
  fireEvent.change(screen.getByLabelText('Library Name'), { target: { value: 'Aurora Library' } })
  fireEvent.change(screen.getByLabelText(/Library Slug/), { target: { value: 'aurora-library' } })
  if (privateLibrary) {
    fireEvent.click(screen.getByLabelText('Private Institution'))
    for (const label of ['New Access Code', 'Confirm Access Code']) fireEvent.change(screen.getByLabelText(label), { target: { value: 'shared institution code' } })
  }
  fireEvent.click(screen.getByRole('button', { name: 'Register Library' }))
  await screen.findByText('Institution administration')
  const call = calls.find(c => c.url === '/api/libraries/register')!
  assert.equal(call.body?.access_mode, privateLibrary ? 'PRIVATE_CODE' : 'PUBLIC')
  assert.equal('owner_user_id' in call.body!, false)
  assert.equal(auth.getState().user?.role, 'GENERAL_USER')
  assert.equal(store.getState().activeId, id)
  assert.equal(localStorage.getItem('luminar_workspace_contexts')?.includes('shared institution code'), false)
})

test('registration mismatch is accessible and does not submit', () => {
  mount(<RegisterLibraryPage />); fireEvent.click(screen.getByLabelText('Private Institution'))
  fireEvent.change(screen.getByLabelText('New Access Code'), { target: { value: 'secret123' } })
  fireEvent.change(screen.getByLabelText('Confirm Access Code'), { target: { value: 'different123' } })
  fireEvent.submit(screen.getByRole('button', { name: 'Register Library' }).closest('form')!)
  assert.ok(screen.getByRole('alert').textContent?.includes('do not match'))
  assert.equal(calls.length, 0)
})

test('discovery cards show public join, private code, member enter, suspended contact', async () => {
  rows = [library(), library({ library_id: id2, name: 'Orion Research', access_mode: 'PRIVATE_CODE' }), library({ library_id: 'member', name: 'Member Library', membership: member('GENERAL_USER', false) }), library({ library_id: 'suspended', name: 'Suspended Library', membership: { ...member(), status: 'SUSPENDED' } })]
  mount(<ExploreLibrariesPage />)
  await screen.findByText('Orion Research')
  assert.ok(screen.getByRole('button', { name: 'Join Library' }))
  assert.ok(screen.getByRole('button', { name: 'Enter Access Code' }))
  assert.ok(screen.getByRole('button', { name: 'Open Library' }))
  assert.ok((screen.getByRole('button', { name: 'Contact library staff' }) as HTMLButtonElement).disabled)
})

for (const kind of ['public', 'private', 'mine']) test(`discovery ${kind} filter and library search use scoped discovery`, async () => {
  mount(<ExploreLibrariesPage />); await screen.findByText('0 libraries found')
  chooseSelect(screen.getByLabelText('Library filter'),kind,fireEvent)
  fireEvent.change(screen.getByLabelText('Search libraries'), { target: { value: 'Hyderabad' } }); fireEvent.click(screen.getByRole('button', { name: 'Search' }))
  await waitFor(() => assert.ok(calls.some(c => c.url.includes(`kind=${kind}&search=Hyderabad`))))
  assert.ok(calls.every(c => !c.url.startsWith('/search-api')))
})

test('private join dialog reports wrong code and clears secret on successful join', async () => {
  rows = [library({ access_mode: 'PRIVATE_CODE' })]
  handler = (path, _method, body) => path.endsWith('/join') && body?.access_code === 'wrong-code' ? Response.json({ detail: 'Invalid access code.' }, { status: 403 }) : undefined
  mount(<Routes><Route path="/" element={<ExploreLibrariesPage />} /><Route path="/libraries/:id" element={<p>Library entered</p>} /></Routes>)
  await screen.findByText('Aurora Public Library'); fireEvent.click(screen.getByRole('button', { name: 'Enter Access Code' }))
  const dialog = screen.getByRole('dialog'); assert.ok(dialog)
  fireEvent.change(screen.getByLabelText('Institution Access Code'), { target: { value: 'wrong-code' } }); fireEvent.click(within(dialog).getByRole('button', { name: 'Join Library' }))
  await screen.findByText('Invalid access code.')
  fireEvent.change(screen.getByLabelText('Institution Access Code'), { target: { value: 'correct institution secret' } }); fireEvent.click(within(dialog).getByRole('button', { name: 'Join Library' }))
  await screen.findByText('Library entered')
  assert.equal(store.getState().activeId, id)
  assert.equal(screen.queryByLabelText('Institution Access Code'), null)
  assert.ok(!JSON.stringify(localStorage).includes('correct institution secret'))
})

test('public join sends no code and adds switcher membership', async () => {
  rows = [library()]; mount(<ExploreLibrariesPage />); await screen.findByText('Aurora Public Library')
  fireEvent.click(screen.getByRole('button', { name: 'Join Library' }))
  await waitFor(() => assert.equal(store.getState().activeId, id))
  assert.deepEqual(calls.find(c => c.url.endsWith('/join'))?.body, {})
})

test('empty local switcher keeps global catalogue available', () => {
  mount(<LibrarySwitcher />)
  assert.equal((screen.getByLabelText('Switch patron library') as HTMLSelectElement).disabled, false)
  assert.equal(screen.queryByLabelText('Active library'), null)
})
test('refresh does not silently select a library', async () => {
  rows = [library({ membership: member('LIBRARIAN', false) })]
  await act(async () => { await store.getState().refresh() })
  assert.equal(store.getState().activeId, null)
  mount(<LibrarySwitcher staff />)
  assert.equal((screen.getByLabelText('Switch staff library') as HTMLSelectElement).disabled, false)
})
test('explicit patron selection revalidates context and preserves staff identity', async () => {
  const a = scoped(), b = library({ library_id: id2, name: 'Orion Research', membership: member('GENERAL_USER', false) })
  rows = [a, b]; store.setState({ libraries: rows, staffLibraryId: id, patronLibraryId: null })
  await act(async () => { await store.getState().select(id2) })
  assert.equal(store.getState().staffLibraryId, id)
  assert.ok(calls.some(c => c.url === `/api/libraries/${id2}/context`))
  assert.deepEqual(JSON.parse(localStorage.getItem('luminar_workspace_contexts')!), { owner: 'reader@example.com', patronLibraryId: id2, staffLibraryId: id })
})

test('account changes and logout clear previous institution authority immediately', async () => {
  scoped(); localStorage.setItem('luminar_active_library', JSON.stringify({ owner: 'reader@example.com', library_id: id }))
  rows = []; await act(async () => store.getState().syncSession('other@example.com', 'token-b'))
  assert.equal(store.getState().activeId, null); assert.deepEqual(store.getState().libraries, [])
  await act(async () => store.getState().syncSession(null, null))
  assert.equal(localStorage.getItem('luminar_active_library'), null)
})

test('stale request from previous account cannot populate new switcher', async () => {
  let finish: ((value: Response) => void) | undefined
  globalThis.fetch = () => new Promise<Response>(resolve => { finish = resolve })
  const pending = store.getState().refresh(); store.getState().reset()
  finish!(Response.json({ results: [library({ membership: member() })], has_more: false }))
  await pending
  assert.deepEqual(store.getState().libraries, []); assert.equal(store.getState().activeId, null)
})

for (const role of ['ADMIN', 'LIBRARIAN'] as const) test(`${role} can rotate private code with membership-preservation confirmation`, async () => {
  scoped(role, role === 'ADMIN'); mount(<InstitutionPanel />); await screen.findByText('Access Code: SET')
  fireEvent.click(screen.getByRole('button', { name: 'Change Access Code' }))
  assert.ok(screen.getByText(/Existing members will remain members/))
  assert.equal(screen.queryByLabelText('Old Access Code'), null)
  for (const label of ['New Access Code', 'Confirm Access Code']) fireEvent.change(screen.getByLabelText(label), { target: { value: 'new private entry code' } })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm Change' }))
  await screen.findByText('Access settings updated.')
  assert.equal(calls.find(c => c.url.endsWith('/access-code'))?.method, 'PUT')
  assert.equal(screen.queryByLabelText('New Access Code'), null)
})

test('general member has no code or staff settings', () => {
  scoped('GENERAL_USER', false); mount(<InstitutionPanel />)
  assert.equal(screen.queryByRole('button', { name: 'Change Access Code' }), null)
  assert.equal(screen.queryByRole('button', { name: 'Add Staff' }), null)
  assert.equal(calls.length, 0)
})

test('librarian has code rotation but no staff actions or access-mode change', async () => {
  scoped('LIBRARIAN', false); mount(<InstitutionPanel />); await screen.findByText('Access Code: SET')
  assert.equal(screen.queryByRole('button', { name: 'Add Staff' }), null)
  assert.equal(screen.queryByRole('button', { name: 'Change to Public Library' }), null)
  assert.ok(!calls.some(c => /memberships|invitations|audit/.test(c.url)))
})

test('non-owner admin can invite only librarian and cannot change owner membership', async () => {
  scoped('ADMIN', false); mount(<InstitutionPanel />); await screen.findByText('Access Code: SET')
  fireEvent.click(screen.getByLabelText('Staff Role'))
  assert.deepEqual(screen.getAllByRole('option').map(o => o.textContent), ['Librarian'])
  fireEvent.keyDown(screen.getByLabelText('Staff Role'),{key:'Escape'})
  assert.equal(screen.queryByLabelText('Role for owner@example.com'), null)
  assert.equal(within(screen.getByLabelText('Role for staff@example.com')).queryByRole('option', { name: 'Admin' }), null)
})

test('owner invites admin by email and copy link is shown once', async () => {
  scoped(); mount(<InstitutionPanel />); await screen.findByText('Access Code: SET')
  fireEvent.change(screen.getByLabelText('Staff Email'), { target: { value: 'new@example.com' } }); chooseSelect(screen.getByLabelText('Staff Role'),'ADMIN',fireEvent)
  fireEvent.click(screen.getByRole('button', { name: 'Add Staff' }))
  await screen.findByRole('dialog', { name: 'Copy Invite Link' })
  assert.ok((screen.getByLabelText('Invite Link') as HTMLInputElement).value.includes('#token='))
  assert.ok(!JSON.stringify(localStorage).includes('x'.repeat(43)))
  fireEvent.click(screen.getByRole('button', { name: 'Close dialog' }))
  assert.equal(screen.queryByLabelText('Invite Link'), null)
  assert.ok(calls.some(c => c.method === 'POST' && c.body?.role === 'ADMIN' && c.body.email === 'new@example.com'))
})

for (const privateLibrary of [false, true]) test(`${privateLibrary ? 'private to public' : 'public to private'} requires explicit access confirmation`, async () => {
  scoped('ADMIN', true, privateLibrary); mount(<InstitutionPanel />)
  await waitFor(() => assert.equal((screen.getByRole('button', { name: privateLibrary ? 'Change to Public Library' : 'Change to Private Institution' }) as HTMLButtonElement).disabled, false))
  if (!privateLibrary) assert.equal(screen.queryByRole('button', { name: 'Change Access Code' }), null)
  fireEvent.click(screen.getByRole('button', { name: privateLibrary ? 'Change to Public Library' : 'Change to Private Institution' }))
  if (!privateLibrary) for (const label of ['New Access Code', 'Confirm Access Code']) fireEvent.change(screen.getByLabelText(label), { target: { value: 'private entry passphrase' } })
  fireEvent.click(screen.getByRole('button', { name: 'Confirm Change' }))
  await waitFor(() => assert.ok(calls.some(c => c.url.endsWith('/access') && c.method === 'PUT')))
  const call = calls.find(c => c.url.endsWith('/access') && c.method === 'PUT')!
  assert.equal(call.body?.access_mode, privateLibrary ? 'PUBLIC' : 'PRIVATE_CODE')
  assert.equal('access_code' in call.body!, !privateLibrary)
})

test('staff suspension uses canonical library and membership IDs', async () => {
  scoped(); mount(<InstitutionPanel />); await screen.findByText('Access Code: SET')
  fireEvent.click(screen.getByRole('button', { name: 'Suspend' })); fireEvent.click(screen.getByRole('button', { name: 'Confirm' }))
  await screen.findByText('Membership updated.')
  assert.ok(calls.some(c => c.url === `/api/libraries/${id}/memberships/${id}` && c.body?.status === 'SUSPENDED'))
})

test('pending invitation accept refreshes memberships', async () => {
  mount(<PendingInvitationsPage />); await screen.findByText('Orion Research'); fireEvent.click(screen.getByRole('button', { name: 'Accept' }))
  await waitFor(() => assert.ok(calls.some(c => c.url === `/api/invitations/${id2}/accept`)))
  assert.ok(calls.some(c => c.url.startsWith('/api/me/libraries')))
})

test('new-account invitation consumes fragment token in authenticated POST body', async () => {
  mount(<Routes><Route path="/invitations/:invitationId" element={<InvitationPage />} /><Route path="/staff/libraries/:libraryId" element={<p>Explore after acceptance</p>} /></Routes>, `/invitations/${id2}#token=${'z'.repeat(43)}`)
  fireEvent.click(screen.getByRole('button', { name: 'Accept Invitation' })); await screen.findByText('Explore after acceptance')
  const call = calls.find(c => c.url.endsWith('/accept'))!
  assert.equal(call.body?.token, 'z'.repeat(43)); assert.ok(!call.url.includes('z'.repeat(43)))
  assert.ok(!JSON.stringify(localStorage).includes('z'.repeat(43)))
})

test('library admin route admits a global reader through active membership', () => {
  scoped(); mount(<ProtectedRoute libraryRoles={['ADMIN']}><p>Institution admin</p></ProtectedRoute>)
  assert.ok(screen.getByText('Institution admin'))
})

test('new library admin dashboard does not call legacy global staff APIs', async () => {
  scoped(); mount(<InstitutionPanel section="settings" />); await screen.findByText('Access Code: SET')
  assert.ok(calls.every(c => !/\/admin\/|\/staff\/|\/issues\/|\/inventory\//.test(c.url)))
})
