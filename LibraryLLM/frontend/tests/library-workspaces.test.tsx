import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { test, beforeEach, afterEach } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'
import type { Library, LibraryRole } from '../src/lib/institutions'

registerHooks({ load(url, context, nextLoad) { return url.endsWith('.css') ? { format: 'module', source: '', shortCircuit: true } : nextLoad(url, context) } })
const dom = new JSDOM('<html lang="en"><head><title>Workspace tests</title></head><body></body></html>', { url: 'http://localhost:5173' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, FormData: dom.window.FormData, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
dom.window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
dom.window.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
const { render, screen, fireEvent, cleanup, waitFor, act, within } = await import('@testing-library/react')
const { MemoryRouter, Routes, Route, useLocation } = await import('react-router-dom')
const { WorkspaceRoute, AdminLibraryRoute, LegacyWorkspaceRedirect, AccountLanding } = await import('../src/components/WorkspaceRoute.tsx')
const { StaffLibraryShell, PatronLibraryShell, StaffOverviewPage } = await import('../src/components/LibraryShells.tsx')
const { Header } = await import('../src/components/Header.tsx')
const { LibrarySwitcher } = await import('../src/components/LibrarySwitcher.tsx')
const { LibraryInventoryPage } = await import('../src/pages/LibraryInventory.tsx')
const { LibraryCirculationPage } = await import('../src/pages/LibraryCirculation.tsx')
const { MyLibrariesPage } = await import('../src/pages/AccountPages.tsx')
const { useInstitutionStore: store, patronCatalogueDestination } = await import('../src/store/useInstitutionStore.ts')
const { useAuthStore: auth } = await import('../src/store/useAuthStore.ts')
const { usePlatformStore } = await import('../src/store/usePlatformStore.ts')
const { workspaceDestination } = await import('../src/lib/authDestination.ts')
const { libraryWorkspaceHome } = await import('../src/lib/libraryWorkspace.ts')
const a = '11111111-1111-4111-8111-111111111111', b = '22222222-2222-4222-8222-222222222222', c = '33333333-3333-4333-8333-333333333333', d = '44444444-4444-4444-8444-444444444444'
const library = (id: string, role: LibraryRole): Library => ({ library_id: id, name: `Library ${id === a ? 'A' : id === b ? 'B' : id === c ? 'C' : 'D'}`, slug: 'workspace', description: null, library_type: 'PUBLIC_LIBRARY', access_mode: 'PUBLIC', membership: { membership_id: id, library_id: id, user_id: 1, role, status: 'ACTIVE', is_owner: id === a, joined_at: '2026-10-09T00:00:00Z' } })
let libraries: Library[], original: typeof fetch, calls: string[], empty: boolean, fail: boolean
beforeEach(() => {
  localStorage.clear(); localStorage.setItem('luminar_token', 'workspace-test')
  auth.setState({ token: 'workspace-test', isAuthenticated: true, loading: false, user: { user_id: 1, name: 'One Global Account', email: 'account@example.com', role: 'ADMIN' } })
  libraries = [library(a, 'ADMIN'), library(b, 'GENERAL_USER'), library(c, 'LIBRARIAN'), library(d, 'GENERAL_USER')]
  store.setState({ owner: 'account@example.com', session: 'workspace-test', libraries, activeId: a, patronLibraryId: b, staffLibraryId: a, workspace: 'STAFF', loading: false, error: null })
  usePlatformStore.setState({ roles: [], session: 'workspace-test', loading: false, error: '' })
  calls = []; empty = false; fail = false; original = globalThis.fetch
  globalThis.fetch = async url => {
    const path = String(url); calls.push(path)
    if (path.endsWith('/context')) { const row = libraries.find(l => path.includes(l.library_id)); return row ? Response.json({ library: row, membership: row.membership }) : Response.json({ detail: 'Active library membership required.' }, { status: 404 }) }
    if (path.includes('/me/libraries')) return Response.json({ results: libraries, has_more: false })
    if (path.includes('/inventory/books')) return fail ? Response.json({ detail: 'Collection unavailable.' }, { status: 503 }) : Response.json({ role: libraries.find(l => path.includes(l.library_id))?.membership?.role, lending_state: 'CANONICAL', results: empty ? [] : [{ library_book_id: d, title: 'Workspace Manual', subjects: ['Systems'], authors: [], accession_number: 'WS-1', status: 'ACTIVE', global_work_id: null, holding: { total_copies: 3, available_copies: 3, shelf_location: 'Room 2' }, availability: { requestable: 1, active_loans: 1, pending_holds: 1, circulation_status: 'CIRCULATING' } }], total: empty ? 0 : 1 })
    if (path.endsWith('/lending/config')) return Response.json({ state: 'CANONICAL' })
    if (path.includes('/staff/loans')) return Response.json({ results: [], total: 4 })
    if (path.includes('/requests?') || path.includes('-requests?')) return Response.json({ results: [], total: 0, pending_counts: { BORROW: 2, RETURN: 1 } })
    return Response.json({ results: [], total: 0, unread_count: 0 })
  }
})
afterEach(() => { cleanup(); globalThis.fetch = original })
function Position() { const loc = useLocation(); return <output data-testid="position">{loc.pathname + loc.search + loc.hash}</output> }
function mount(path: string, extra?: React.ReactNode) { return render(<MemoryRouter initialEntries={[path]}>{extra}<Position /><Routes>
  <Route path="/libraries/:libraryId" element={<WorkspaceRoute><p>Patron home content</p></WorkspaceRoute>} />
  <Route path="/libraries/:libraryId/catalogue" element={<WorkspaceRoute><LibraryInventoryPage /></WorkspaceRoute>} />
  <Route path="/libraries/:libraryId/my-library" element={<WorkspaceRoute><p>Patron account content</p></WorkspaceRoute>} />
  <Route path="/staff/libraries/:libraryId" element={<WorkspaceRoute staff><p>Staff home content</p></WorkspaceRoute>} />
  <Route path="/staff/libraries/:libraryId/inventory" element={<WorkspaceRoute staff><LibraryInventoryPage /></WorkspaceRoute>} />
  <Route path="/staff/libraries/:libraryId/circulation" element={<WorkspaceRoute staff><LibraryCirculationPage staff /></WorkspaceRoute>} />
  <Route path="/staff/libraries/:libraryId/members" element={<WorkspaceRoute staff><AdminLibraryRoute><p>Membership administration</p></AdminLibraryRoute></WorkspaceRoute>} />
  <Route path="/account/libraries" element={<MyLibrariesPage />} />
  <Route path="/account/continue" element={<AccountLanding />} />
  <Route path="/library-loans" element={<LegacyWorkspaceRedirect mode="PATRON" section="my-library" />} />
  <Route path="/library-circulation" element={<LegacyWorkspaceRedirect mode="STAFF" section="circulation" />} />
  <Route path="/" element={<p>Global home</p>} />
</Routes></MemoryRouter>) }

for (const role of ['ADMIN','LIBRARIAN','GENERAL_USER'] as const) test(`membership ${role} owns its explicit home independent of global role`, async () => {
  libraries = [library(a, role)]; store.setState({ libraries })
  mount(libraryWorkspaceHome(libraries[0])); await screen.findByText(role === 'GENERAL_USER' ? 'Patron home content' : 'Staff home content')
})
for (const section of ['', '/catalogue', '/my-library']) for (const id of [a,c]) test(`staff cannot use patron URL ${id}:${section}`, async () => {
  mount(`/libraries/${id}${section}`); await screen.findByText('Staff home content'); assert.equal(screen.queryByText('Patron home content'), null)
  assert.equal(screen.getByTestId('position').textContent, `/staff/libraries/${id}`)
})
for (const section of ['', '/inventory', '/circulation', '/members']) test(`patron cannot use staff URL ${section}`, async () => {
  mount(`/staff/libraries/${b}${section}`); await screen.findByText('Patron home content'); assert.equal(screen.getByTestId('position').textContent, `/libraries/${b}`)
  assert.ok(calls.every(path => !path.includes(`/libraries/${b}/staff/`)))
})
test('librarian cannot open membership administration despite global ADMIN', async () => { mount(`/staff/libraries/${c}/members`); await screen.findByText('Staff home content'); assert.equal(screen.queryByText('Membership administration'), null) })
test('unknown URL tenant fails closed with retry and library selector', async () => { mount('/libraries/99999999-9999-4999-8999-999999999999'); await screen.findByRole('alert'); assert.ok(screen.getByRole('button', { name: 'Retry' })); assert.equal(screen.queryByText('Patron home content'), null) })
test('wrong-session cached membership never mounts tenant content', () => { store.setState({ session: 'old-session' }); mount(`/staff/libraries/${a}`); assert.ok(screen.getByText('Loading library permissions…')); assert.equal(screen.queryByText('Staff home content'), null) })
test('same-tenant demotion unmounts staff content and resolves patron home', async () => { mount(`/staff/libraries/${a}`); await screen.findByText('Staff home content'); libraries = [library(a,'GENERAL_USER')]; act(() => store.setState({ libraries })); await screen.findByText('Patron home content') })
test('context changes preserve the other workspace selection', async () => {
  await store.getState().select(c); assert.equal(store.getState().patronLibraryId,b)
  await store.getState().select(d); assert.equal(store.getState().staffLibraryId,c)
  await store.getState().select(a); assert.equal(store.getState().patronLibraryId,d)
})
test('late cross-mode context may remember its mode but cannot replace route context', async () => {
  let finish!: (r:Response) => void
  globalThis.fetch = async url => String(url).includes(c) ? new Promise(resolve => { finish = resolve }) : Response.json({ library: libraries[1], membership: libraries[1].membership })
  const first = store.getState().select(c); await store.getState().select(b); finish(Response.json({ library: libraries[2], membership: libraries[2].membership })); await first
  assert.equal(store.getState().activeId,b); assert.equal(store.getState().staffLibraryId,c); assert.equal(store.getState().patronLibraryId,b)
})
test('late same-mode context cannot overwrite newer staff selection', async () => {
  let finish!: (r:Response) => void
  globalThis.fetch = async url => String(url).includes(c) ? new Promise(resolve => { finish=resolve }) : Response.json({ library: libraries[0], membership: libraries[0].membership })
  const first=store.getState().select(c); await store.getState().select(a); finish(Response.json({library:libraries[2],membership:libraries[2].membership})); await first
  assert.equal(store.getState().staffLibraryId,a)
})
test('refresh validates selected contexts without auto-selecting or discarding memberships', async () => { const pending=store.getState().refresh(); await store.getState().select(c); await pending; assert.equal(store.getState().libraries.length,4); assert.equal(store.getState().patronLibraryId,b) })
test('logout clears both contexts and storage', async () => { await store.getState().select(a); store.getState().reset(); assert.equal(store.getState().patronLibraryId,null); assert.equal(store.getState().staffLibraryId,null); assert.equal(localStorage.getItem('luminar_workspace_contexts'),null) })
test('another account cannot inherit stored contexts', async () => { await store.getState().select(a); globalThis.fetch=async()=>Response.json({results:[],has_more:false}); store.getState().syncSession('another@example.com','another-token'); assert.equal(store.getState().patronLibraryId,null); await waitFor(()=>assert.equal(store.getState().loading,false)); assert.deepEqual(store.getState().libraries,[]) })
test('promotion removes old patron selection for that same membership', async () => { libraries=libraries.map(l=>l.library_id===b?library(b,'LIBRARIAN'):l); await store.getState().select(b); assert.equal(store.getState().patronLibraryId,null); assert.equal(store.getState().staffLibraryId,b) })
test('global catalogue targets B even after staff switches A to C', async () => { await store.getState().select(c); assert.equal(patronCatalogueDestination(),`/libraries/${b}/catalogue`) })
test('global catalogue without explicit patron selection opens patron selector', () => { store.setState({patronLibraryId:null}); assert.equal(patronCatalogueDestination(),'/account/libraries?group=patron') })
for (const mode of ['staff','patron']) test(`${mode} switcher offers global and only its membership roles`, () => { render(<MemoryRouter><LibrarySwitcher staff={mode==='staff'} /></MemoryRouter>); fireEvent.click(screen.getByRole('combobox')); const options=screen.getAllByRole('option').map(n=>n.textContent); assert.deepEqual(options,mode==='staff'?['Global catalogue','Library A','Library C']:['Global catalogue','Library B','Library D']); assert.equal(screen.queryByLabelText('Active library'),null) })
for (const staff of [false, true]) test(`${staff ? 'staff' : 'patron'} with one library can switch to global without retaining route context`, () => {
  const id = staff ? a : b
  store.setState({ libraries: [library(id, staff ? 'ADMIN' : 'GENERAL_USER')] })
  render(<MemoryRouter initialEntries={[`${staff ? '/staff' : ''}/libraries/${id}?search=systems#books`]}><LibrarySwitcher staff={staff} /><Position /><Header /></MemoryRouter>)
  fireEvent.click(screen.getByRole('combobox'))
  fireEvent.click(screen.getByRole('option', { name: 'Global catalogue', exact: true }))
  assert.equal(screen.getByTestId('position').textContent, '/')
  assert.equal(screen.getByRole('link', { name: 'Catalog', exact: true }).getAttribute('href'), '/catalog')
  assert.equal(store.getState()[staff ? 'staffLibraryId' : 'patronLibraryId'], id)
})
test('global header shows Global selected and all active memberships', () => {
  render(<MemoryRouter><Header /></MemoryRouter>)
  const switcher = screen.getByRole('combobox', { name: 'Switch catalogue' })
  assert.equal(switcher.textContent, 'Global catalogue')
  fireEvent.click(switcher)
  assert.deepEqual(screen.getAllByRole('option').map(n => n.textContent), ['Global catalogue', 'Library A', 'Library B', 'Library C', 'Library D'])
})
for (const staff of [false, true]) test(`global dropdown remains available after a ${staff ? 'staff' : 'patron'} library round trip`, async () => {
  const id = staff ? a : b, path = `${staff ? '/staff' : ''}/libraries/${id}`
  render(<MemoryRouter><Header /><Position /><Routes>
    <Route path="/" element={<p>Global home</p>} />
    <Route path="/libraries/:libraryId" element={<WorkspaceRoute><LibrarySwitcher /></WorkspaceRoute>} />
    <Route path="/staff/libraries/:libraryId" element={<WorkspaceRoute staff><LibrarySwitcher staff /></WorkspaceRoute>} />
  </Routes></MemoryRouter>)
  fireEvent.click(screen.getByRole('combobox', { name: 'Switch catalogue' }))
  fireEvent.click(screen.getByRole('option', { name: staff ? 'Library A' : 'Library B', exact: true }))
  await screen.findByRole('combobox', { name: staff ? 'Switch staff library' : 'Switch patron library' })
  assert.equal(screen.getByTestId('position').textContent, path)
  fireEvent.click(screen.getByRole('combobox'))
  fireEvent.click(screen.getByRole('option', { name: 'Global catalogue', exact: true }))
  assert.equal(screen.getByTestId('position').textContent, '/')
  assert.equal(screen.getByRole('combobox', { name: 'Switch catalogue' }).textContent, 'Global catalogue')
})
test('global dropdown excludes memberships cached for another session', () => {
  store.setState({ session: 'another-session' })
  render(<MemoryRouter><Header /></MemoryRouter>)
  fireEvent.click(screen.getByRole('combobox', { name: 'Switch catalogue' }))
  assert.deepEqual(screen.getAllByRole('option').map(n => n.textContent), ['Global catalogue'])
})
test('legacy patron link uses remembered patron B while route context is staff A', async () => { mount('/library-loans'); await screen.findByText('Patron account content'); assert.equal(screen.getByTestId('position').textContent,`/libraries/${b}/my-library`) })
test('legacy staff link uses staff A after patron B was viewed', async () => { store.setState({activeId:b}); mount('/library-circulation'); await screen.findByRole('heading',{name:'Circulation'}); assert.ok(screen.getByTestId('position').textContent?.startsWith(`/staff/libraries/${a}/`)) })
for (const count of [0,1,4]) test(`login landing for ${count} memberships`, async () => { libraries=libraries.slice(0,count); store.setState({libraries}); mount('/account/continue'); await screen.findByText(count===0?'Global home':count===1?'Staff home content':'My libraries') })
test('login preserves library deep-link for fresh authority resolution', () => { const path=`/libraries/${b}/my-library?history=1#returns`;assert.equal(new URLSearchParams(workspaceDestination(path).split('?')[1]).get('return_to'),path);assert.ok(workspaceDestination(path).startsWith('/account/continue?')) })
for (const path of ['//evil.example','https://evil.example','/login','/staff/login','/dashboard','/account/continue','/\\evil']) test(`login rejects ambiguous destination ${path}`,()=>assert.equal(workspaceDestination(path),'/account/continue'))
test('avatar groups memberships with correct explicit destinations and concise roles', () => { render(<MemoryRouter><Header /></MemoryRouter>); fireEvent.click(screen.getByRole('button',{name:/Open account menu/})); const menu=screen.getByRole('menu'); assert.equal(within(menu).getByRole('menuitem',{name:/Library A/}).getAttribute('href'),`/staff/libraries/${a}`); assert.equal(within(menu).getByRole('menuitem',{name:/Library B/}).getAttribute('href'),`/libraries/${b}`); assert.ok(within(menu).getByText('Owner · Admin')); assert.ok(within(menu).getByText('Librarian')); assert.equal(screen.queryByLabelText('Active library'),null) })
test('avatar bounds each group and offers a view-all destination', () => { const more=Array.from({length:20},(_,i)=>library(`10000000-0000-4000-8000-${String(i).padStart(12,'0')}`,'GENERAL_USER')); store.setState({libraries:[...libraries,...more]}); render(<MemoryRouter><Header /></MemoryRouter>); fireEvent.click(screen.getByRole('button',{name:/Open account menu/})); assert.equal(screen.getAllByRole('menuitem',{name:/Member$/}).length,3); assert.ok(screen.getByRole('menuitem',{name:'View all patron libraries'})); assert.ok(screen.getByRole('menuitem',{name:'View all libraries'})) })
test('avatar arrows and Escape restore focus to the trigger', () => { render(<MemoryRouter><Header /></MemoryRouter>); const trigger=screen.getByRole('button',{name:/Open account menu/}); trigger.focus(); fireEvent.click(trigger); assert.equal(document.activeElement,screen.getByRole('menuitem',{name:'Profile'})); fireEvent.keyDown(screen.getByRole('menu'),{key:'ArrowDown'}); assert.equal(document.activeElement,screen.getByRole('menuitem',{name:'Saved / Reading list'})); fireEvent.keyDown(screen.getByRole('dialog'),{key:'Escape'}); assert.equal(screen.queryByRole('dialog'),null); assert.equal(document.activeElement,trigger) })
test('avatar outside click dismisses menu', () => { render(<MemoryRouter><Header /></MemoryRouter>); fireEvent.click(screen.getByRole('button',{name:/Open account menu/})); fireEvent.click(screen.getByRole('dialog'),{clientX:-1,clientY:-1}); assert.equal(screen.queryByRole('dialog'),null) })
test('staff-only account has no global My Library shortcut', () => { store.setState({libraries:[libraries[0],libraries[2]],patronLibraryId:null}); render(<MemoryRouter><Header /></MemoryRouter>); assert.equal(screen.queryByRole('link',{name:'My Library'}),null); assert.equal(screen.queryByRole('link',{name:'Admin Dashboard'}),null) })
test('header My Library shortcut binds to explicit patron B', () => { render(<MemoryRouter><Header /></MemoryRouter>); assert.equal(screen.getByRole('link',{name:'My Library'}).getAttribute('href'),`/libraries/${b}/my-library`) })
test('staff inventory exposes canonical available count with one row menu', async () => { mount(`/staff/libraries/${a}/inventory`); await screen.findByRole('heading',{name:'Workspace Manual'}); assert.ok(screen.getByRole('columnheader',{name:'Available to request'})); assert.equal(screen.queryByRole('button',{name:'Withdraw'}),null); assert.equal(screen.queryByRole('button',{name:'Request Book',exact:true}),null); fireEvent.click(screen.getByRole('button',{name:'Actions for WS-1'})); assert.ok(screen.getByRole('menuitem',{name:'Manage Stock & Shelf'})); assert.ok(screen.getByRole('menuitem',{name:'Withdraw'})) })
test('inventory details has metadata and shelf without personal requests', async () => { mount(`/staff/libraries/${a}/inventory`); fireEvent.click(await screen.findByRole('button',{name:'Actions for WS-1'})); fireEvent.click(screen.getByRole('menuitem',{name:'View details'})); assert.ok(screen.getByRole('dialog',{name:'Book details · WS-1'})); assert.ok(within(screen.getByRole('dialog')).getByText('Room 2')); assert.equal(screen.queryByRole('button',{name:'Request Book',exact:true}),null) })
test('empty staff inventory provides add/import without duplicate zero count', async () => { empty=true; mount(`/staff/libraries/${a}/inventory`); await screen.findByText('No active books in Library A'); assert.ok(screen.getByRole('button',{name:'Add First Book'})); assert.equal(screen.queryByText('0 records'),null) })
test('inventory errors expose retry without presenting an empty collection', async () => { fail=true; mount(`/staff/libraries/${a}/inventory`); await screen.findByRole('alert'); assert.ok(screen.getByRole('button',{name:'Retry'})); assert.equal(screen.queryByText('No active books in Library A'),null) })
test('patron inventory offers Request Book without staff controls', async () => { mount(`/libraries/${b}/catalogue`); await screen.findByRole('heading',{name:'Workspace Manual'}); assert.ok(screen.getByRole('button',{name:'Request Book',exact:true})); assert.equal(screen.queryByRole('button',{name:'Actions for WS-1'}),null) })
test('staff Loans tab uses operational endpoint and never personal loan read', async () => { mount(`/staff/libraries/${a}/circulation?tab=loans`); await screen.findByRole('button',{name:'Loans'}); await waitFor(()=>assert.ok(calls.some(p=>p.includes('/staff/loans?')))); assert.ok(calls.every(p=>!p.includes('/me/loans'))); assert.equal(screen.queryByRole('button',{name:'Renew Loan'}),null) })
test('overview shows real counters and role-specific operational navigation', async () => { render(<MemoryRouter initialEntries={[`/staff/libraries/${a}`]}><Routes><Route path="/staff/libraries/:libraryId" element={<StaffLibraryShell />}><Route index element={<StaffOverviewPage />} /></Route></Routes></MemoryRouter>); await screen.findByText('Current loans'); await screen.findByText('4'); assert.ok(screen.getByRole('link',{name:'Members & Staff'})); assert.equal(screen.queryByRole('link',{name:'My Library'}),null); assert.ok(calls.every(p=>p.includes(`/libraries/${a}/`))) })
test('empty overview provides concrete owner onboarding', async () => { empty=true; render(<MemoryRouter><Routes><Route element={<StaffLibraryShell />}><Route path="/" element={<StaffOverviewPage />} /></Route></Routes></MemoryRouter>); await screen.findByText('Welcome to Library A.'); assert.ok(screen.getByRole('link',{name:'Invite librarian'})); assert.ok(screen.getByRole('link',{name:'Add first book'})) })
test('patron shell contains focused navigation and no staff routes', () => { store.setState({activeId:b}); render(<MemoryRouter><PatronLibraryShell /></MemoryRouter>); assert.ok(screen.getByRole('navigation',{name:'Library activity'})); assert.equal(screen.queryByRole('link',{name:'Inventory'}),null); assert.equal(screen.queryByRole('link',{name:'Library Settings'}),null) })
test('workspace drawer opens, closes with Escape and restores focus', () => { render(<MemoryRouter><StaffLibraryShell /></MemoryRouter>); const trigger=screen.getByRole('button',{name:'Open workspace menu'}); trigger.focus(); fireEvent.click(trigger); assert.ok(screen.getByRole('dialog',{name:'Workspace menu'})); fireEvent.keyDown(screen.getByRole('dialog'),{key:'Escape'}); assert.equal(screen.queryByRole('dialog'),null); assert.equal(document.activeElement,trigger) })
test('avatar accessibility semantics pass axe structural checks', async () => { render(<MemoryRouter><Header /></MemoryRouter>); fireEvent.click(screen.getByRole('button',{name:/Open account menu/})); const axe=await import('axe-core'); const result=await axe.default.run(screen.getByRole('dialog'),{rules:{'color-contrast':{enabled:false}}}); assert.deepEqual(result.violations.map(v=>({id:v.id,description:v.description})),[]) })

test('same-tenant requests are sequenced and a cancelled queued read never reaches the server', async () => {
  const { institutionApi } = await import('../src/lib/institutions.ts')
  let release!: (r: Response) => void; const received: string[] = []
  globalThis.fetch = async url => { received.push(String(url)); return String(url).endsWith('/access') ? new Promise(resolve => { release=resolve }) : Response.json({}) }
  const first=institutionApi(`/libraries/${a}/access`)
  await waitFor(()=>assert.ok(release)); const controller=new AbortController()
  const next=institutionApi(`/libraries/${a}/lending/config`,'GET',undefined,controller.signal)
  controller.abort(); release(Response.json({})); await first
  await assert.rejects(next,{name:'AbortError'}); assert.equal(received.length,1)
})
test('queued tenant commands cannot run with a new account token', async () => {
  const { institutionApi } = await import('../src/lib/institutions.ts')
  let release!: (r: Response) => void; let received=0
  globalThis.fetch=async()=>{ received++; return new Promise(resolve=>{release=resolve}) }
  const first=institutionApi(`/libraries/${a}/access`); await waitFor(()=>assert.ok(release))
  const next=institutionApi(`/libraries/${a}/lending/borrow-requests`,'POST',{library_book_id:d})
  localStorage.setItem('luminar_token','new-account'); release(Response.json({})); await assert.rejects(first,{name:'AbortError'})
  await assert.rejects(next,{name:'AbortError'}); assert.equal(received,1)
})

for (const surface of ['patron-shell','staff-shell','inventory','inventory-actions'] as const) test(`${surface} passes axe structural accessibility checks`, async () => {
  if(surface==='patron-shell') { store.setState({activeId:b}); render(<MemoryRouter><main><PatronLibraryShell /></main></MemoryRouter>) }
  else if(surface==='staff-shell') render(<MemoryRouter><main><StaffLibraryShell /></main></MemoryRouter>)
  else { render(<MemoryRouter><main><LibraryInventoryPage /></main></MemoryRouter>); await screen.findByRole('heading',{name:'Workspace Manual'}); if(surface==='inventory-actions') fireEvent.click(screen.getByRole('button',{name:'Actions for WS-1'})) }
  const axe=await import('axe-core'); const result=await axe.default.run(surface==='inventory-actions'?screen.getByRole('dialog'):screen.getByRole('main'),{rules:{'color-contrast':{enabled:false}}})
  assert.deepEqual(result.violations.map(v=>({id:v.id,description:v.description})),[])
})

test('patron library selector filters out staff workspaces and supports searching', async () => {
  mount('/account/libraries?group=patron')
  assert.equal(screen.queryByRole('link',{name:'Open Staff Workspace'}),null)
  assert.equal(screen.getAllByRole('link',{name:'Open Library',exact:true}).length,2)
  fireEvent.change(screen.getByRole('searchbox'),{target:{value:'Library D'}})
  assert.equal(screen.getAllByRole('link',{name:'Open Library',exact:true}).length,1)
  fireEvent.click(screen.getByRole('button',{name:'All libraries'})); assert.ok(screen.getByRole('button',{name:'Staff workspaces'}))
})
