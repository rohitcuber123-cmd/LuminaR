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
const { render, screen, cleanup, waitFor, act } = await import('@testing-library/react')
const { MemoryRouter, Routes, Route, useLocation } = await import('react-router-dom')
const { LibraryCirculationPage } = await import('../src/pages/LibraryCirculation.tsx')
const { useInstitutionStore: store, patronCatalogueDestination } = await import('../src/store/useInstitutionStore.ts')
const { useAuthStore: auth } = await import('../src/store/useAuthStore.ts')
const { usePlatformStore } = await import('../src/store/usePlatformStore.ts')
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
function Position() { const loc=useLocation(); return <output data-testid="position">{loc.pathname+loc.search}</output> }
const { PlatformRoute, ManagementRedirect } = await import('../src/components/ManagementRoutes.tsx')
function compat(admin=false) { return render(<MemoryRouter initialEntries={['/old']}><Position/><Routes><Route path="/old" element={<ManagementRedirect admin={admin}/>}/><Route path="*" element={<p>Destination</p>}/></Routes></MemoryRouter>) }
for (const label of ['ADMIN','LIBRARIAN','GENERAL_USER'] as const) test(`${label} label cannot enter Platform Console`,()=>{
 auth.setState({user:{user_id:1,email:'account@example.com',role:label}})
 render(<MemoryRouter><PlatformRoute><p>Platform tools</p></PlatformRoute></MemoryRouter>)
 assert.ok(screen.getByText('Platform access required'));assert.equal(screen.queryByText('Platform tools'),null)
})
test('approved assignment admits console and revocation removes tools',()=>{
 usePlatformStore.setState({roles:['PLATFORM_ADMIN']})
 render(<MemoryRouter><PlatformRoute><p>Platform tools</p></PlatformRoute></MemoryRouter>)
 assert.ok(screen.getByText('Platform tools'))
 act(()=>usePlatformStore.setState({roles:[]}));assert.equal(screen.queryByText('Platform tools'),null)
})
test('old platform session grants no console access',()=>{
 usePlatformStore.setState({roles:['PLATFORM_ADMIN'],session:'previous-token'})
 render(<MemoryRouter><PlatformRoute><p>Platform tools</p></PlatformRoute></MemoryRouter>)
 assert.ok(screen.getByText('Checking platform permissions…'));assert.equal(screen.queryByText('Platform tools'),null)
})
for (const legacy of ['staff','librarian','admin']) {
 test(`${legacy} with several memberships opens selector despite remembered context`,async()=>{
  compat(legacy==='admin');await waitFor(()=>assert.equal(screen.getByTestId('position').textContent,'/account/libraries?group=staff'))
 })
 test(`${legacy} with one staff membership chooses canonical home`,async()=>{
  store.setState({libraries:[library(c,'LIBRARIAN'),library(b,'GENERAL_USER')]});compat(legacy==='admin')
  await waitFor(()=>assert.equal(screen.getByTestId('position').textContent,`/staff/libraries/${c}`))
 })
 test(`${legacy} with no staff membership denies legacy role`,()=>{
  store.setState({libraries:[library(b,'GENERAL_USER')]});compat(legacy==='admin')
  assert.ok(screen.getByText('Staff membership required'));assert.equal(screen.getByTestId('position').textContent,'/old')
 })
}
test('legacy admin resolves explicit platform assignment',async()=>{
 usePlatformStore.setState({roles:['PLATFORM_ADMIN']});compat(true)
 await waitFor(()=>assert.equal(screen.getByTestId('position').textContent,'/platform'))
})
test('legacy librarian remains local for platform account',async()=>{
 usePlatformStore.setState({roles:['PLATFORM_ADMIN']});compat()
 await waitFor(()=>assert.equal(screen.getByTestId('position').textContent,'/account/libraries?group=staff'))
})
test('platform refresh fails closed while pending',async()=>{
 let finish!: (value:Response)=>void
 globalThis.fetch=()=>new Promise(resolve=>{finish=resolve})
 usePlatformStore.setState({roles:['PLATFORM_ADMIN']})
 let pending!:Promise<void>;act(()=>{pending=usePlatformStore.getState().refresh()})
 assert.deepEqual(usePlatformStore.getState().roles,[])
 await act(async()=>{finish(Response.json({roles:[]}));await pending})
 assert.deepEqual(usePlatformStore.getState().roles,[])
})
test('late response never restores previous identity grants',async()=>{
 let finish!: (value:Response)=>void
 globalThis.fetch=()=>new Promise(resolve=>{finish=resolve})
 let pending!:Promise<void>;act(()=>{pending=usePlatformStore.getState().refresh()})
 usePlatformStore.getState().reset()
 await act(async()=>{finish(Response.json({roles:['PLATFORM_ADMIN']}));await pending})
 assert.deepEqual(usePlatformStore.getState().roles,[])
})

const sampleLoan={loan_id:d,user_id:1,library_book_id:d,lending_request_id:'',library_id:b,title:'Own loan',accession_number:'OWN-1',status:'ACTIVE',allocation_mode:'QUANTITY',shelf_location:'Room 2',due_at:'2027-01-01T12:00:00Z'}
test('patron keeps canonical controls for own loan',async()=>{
 store.setState({activeId:b,workspace:'PATRON'})
 globalThis.fetch=async url=>String(url).endsWith('/lending/config')?Response.json({state:'CANONICAL'}):Response.json({results:[sampleLoan],total:1})
 render(<MemoryRouter><LibraryCirculationPage/></MemoryRouter>)
 await screen.findByRole('button',{name:'Request Return',exact:true})
 assert.ok(screen.getByRole('button',{name:'Renew Loan',exact:true}))
 assert.equal(screen.queryByRole('button',{name:'Renew for member',exact:true}),null)
})
test('staff assisted controls exclude own personal legacy loan',async()=>{
 globalThis.fetch=async url=>String(url).endsWith('/lending/config')?Response.json({state:'CANONICAL'}):Response.json({results:[{...sampleLoan,library_id:a}],total:1})
 render(<MemoryRouter initialEntries={['/staff?tab=loans']}><LibraryCirculationPage staff/></MemoryRouter>)
 await screen.findByText('Own loan')
 assert.equal(screen.queryByRole('button',{name:'Renew for member',exact:true}),null)
 assert.equal(screen.queryByRole('button',{name:'Receive physical return',exact:true}),null)
})

test('malformed platform response fails closed and exposes retryable error',async()=>{
 globalThis.fetch=async()=>Response.json({roles:null})
 await act(async()=>usePlatformStore.getState().refresh())
 assert.deepEqual(usePlatformStore.getState().roles,[])
 assert.ok(usePlatformStore.getState().error)
})
