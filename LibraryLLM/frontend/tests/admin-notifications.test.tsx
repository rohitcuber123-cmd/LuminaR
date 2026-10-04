import assert from 'node:assert/strict'
import { test, beforeEach, afterEach } from 'node:test'
import { JSDOM } from 'jsdom'
import React from 'react'

const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173/admin' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
dom.window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
dom.window.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
const { render, screen, fireEvent, cleanup, waitFor, act, within } = await import('@testing-library/react')
const { MemoryRouter } = await import('react-router-dom')
const { NotificationCenter } = await import('../src/components/NotificationCenter')
const { noticeDelta } = await import('../src/lib/notifications')
const { AdminOperations, AdminNotifications, NotificationComposer } = await import('../src/pages/AdminOperations')
const { useAuthStore } = await import('../src/store/useAuthStore')
const { watchSessionStorage } = await import('../src/lib/sessionStorageSync')
const { OperationTypeFilter } = await import('../src/components/OperationTypeFilter')
const alice = { user_id: 2, email: 'alice@example.com', name: 'Alice' }
const admin = { user_id: 1, email: 'admin@example.com', name: 'Admin', role: 'ADMIN' as const }
const base = { notification_id: 'notice1', type: 'ADMIN_MESSAGE', title: 'Library notice', message: 'Please visit the circulation desk.', created_at: new Date().toISOString(), read_at: null }
let notices: typeof base[], calls: { url: string; body?: any; method?: string }[], original: typeof fetch, opsCount: number, directoryUsers: typeof alice[]
beforeEach(() => {
  localStorage.setItem('luminar_token', 'fixture'); useAuthStore.setState({ user: admin, token: 'fixture', isAuthenticated: true }); original = globalThis.fetch; notices = [base]; calls = []; opsCount = 40; directoryUsers = [alice]
  globalThis.fetch = async (url, options) => {
    const path = String(url), body = options?.body ? JSON.parse(String(options.body)) : undefined
    calls.push({ url: path, body, method: options?.method })
    if (path.includes('/notifications/read-all')) { notices = notices.map(n => ({ ...n, read_at: new Date().toISOString() })); return Response.json({ marked: notices.length }) }
    if (/\/notifications\/[^/]+\/read$/.test(path)) { notices = notices.map(n => ({ ...n, read_at: new Date().toISOString() })); return Response.json(notices[0]) }
    if (path.startsWith('/api/notifications?')) return Response.json({ notifications: notices, count: notices.length, unread_count: notices.filter(n => !n.read_at).length })
    if (path.startsWith('/api/admin/users?')) {
      const params = new URL(path, 'http://localhost').searchParams
      const matched = directoryUsers.filter(u => u.email.includes(params.get('q') || ''))
      const offset = Number(params.get('offset') || 0), limit = Number(params.get('limit') || 20)
      return Response.json({ users: matched.slice(offset, offset + limit), count: matched.length })
    }
    if (path.startsWith('/api/admin/users/2/activity')) return Response.json({ user: alice, loans: { count: 1, records: [{ title: 'Dracula' }] }, reservations: { count: 0, records: [] }, fines: { count: 0, records: [] }, notifications: { count: 0, records: [] } })
    if (path.startsWith('/api/admin/operations?')) return Response.json({ operations: [{ operation_id: '1', operation_type: 'BOOK_RETURNED', target_user_id: 2, target_user: alice, actor_user_id: 1, actor: admin, book: { work_id: 'OL1W', title: 'Dracula' }, occurred_at: base.created_at, source_ref: {} }], count: opsCount, operation_types: ['BOOK_ISSUED', 'BOOK_RETURNED'] })
    if (path.startsWith('/api/admin/notifications/sent')) return Response.json({ notifications: [], count: 0 })
    if (path === '/api/admin/notifications' && options?.method === 'POST') return Response.json({ recipient_count: 1 })
    throw new Error(`Unexpected API: ${path}`)
  }
})
afterEach(() => { cleanup(); globalThis.fetch = original })

test('another tab reconciles the completed login pair and cleans up pending logout sync', async () => {
  localStorage.removeItem('luminar_token'); localStorage.removeItem('luminar_user')
  let reconciled = 0
  const stop = watchSessionStorage(() => { reconciled++; useAuthStore.getState().initialize() })
  localStorage.setItem('luminar_token', 'bob-token')
  window.dispatchEvent(new dom.window.StorageEvent('storage', { key: 'luminar_token' }))
  assert.equal(reconciled, 0)
  localStorage.setItem('luminar_user', JSON.stringify({ user_id: 3, email: 'bob@example.com', role: 'GENERAL_USER' }))
  window.dispatchEvent(new dom.window.StorageEvent('storage', { key: 'luminar_user' }))
  await new Promise(resolve => setTimeout(resolve, 80))
  assert.equal(reconciled, 1); assert.equal(useAuthStore.getState().user?.user_id, 3)
  assert.equal(localStorage.getItem('luminar_token'), 'bob-token')
  window.dispatchEvent(new dom.window.StorageEvent('storage', { key: 'luminar_token' })); stop()
  await new Promise(resolve => setTimeout(resolve, 80)); assert.equal(reconciled, 1)
})

test('bell badge, panel, plain text and read state', async () => {
  notices = [{ ...base, message: '<img src=x onerror=alert(1)><script>alert(2)</script>' }]
  render(<NotificationCenter />); const bell = await screen.findByRole('button', { name: 'Notifications, 1 unread' }); fireEvent.click(bell)
  const panel = await screen.findByRole('region', { name: 'Notification Center' }); assert.ok(within(panel).getByText(notices[0].message)); assert.equal(panel.querySelector('img,script'), null)
  fireEvent.click(within(panel).getByRole('button', { name: 'Mark as read', exact: true })); await screen.findByRole('button', { name: 'Notifications', exact: true }); assert.equal(notices[0].read_at === null, false)
})

test('initial backlog has no toast flood and mark all is scoped request', async () => {
  notices = Array.from({ length: 20 }, (_, i) => ({ ...base, notification_id: String(i) })); render(<NotificationCenter />)
  fireEvent.click(await screen.findByRole('button', { name: 'Notifications, 20 unread' })); assert.equal(screen.queryByRole('status'), null)
  fireEvent.click(screen.getByRole('button', { name: 'Mark all as read' })); await screen.findByRole('button', { name: 'Notifications', exact: true }); assert.ok(calls.some(c => c.url === '/api/notifications/read-all' && c.method === 'POST' && !c.body))
})

test('new notification toasts once, close retains inbox and focus refresh', async () => {
  render(<NotificationCenter />); await screen.findByRole('button', { name: 'Notifications, 1 unread' }); notices.push({ ...base, notification_id: 'new', title: 'New notice' })
  await act(async () => window.dispatchEvent(new Event('focus'))); await screen.findByRole('status'); assert.ok(screen.getByText('New notice'))
  fireEvent.click(screen.getByRole('button', { name: 'Close notification toast' })); assert.equal(notices.length, 2)
  await act(async () => window.dispatchEvent(new Event('focus'))); assert.equal(screen.queryByRole('status'), null)
  fireEvent.click(screen.getByRole('button', { name: 'Notifications, 2 unread' })); await screen.findByRole('region', { name: 'Notification Center' }); assert.ok(screen.getByText('New notice'))
})

test('account switch clears previous inbox and toast', async () => {
  render(<NotificationCenter />); fireEvent.click(await screen.findByRole('button', { name: 'Notifications, 1 unread' })); await screen.findByText('Please visit the circulation desk.')
  notices = []; await act(async () => useAuthStore.setState({ user: { user_id: 3, email: 'bob@example.com', role: 'GENERAL_USER' }, token: 'bob-token' }))
  await waitFor(() => assert.equal(screen.queryByText('Please visit the circulation desk.'), null)); assert.equal(screen.queryByRole('status'), null)
})

test('toast ID detection stays bounded across repeated polls', () => {
  const seen = new Set<string>(); assert.equal(noticeDelta(seen, [base], false).length, 0)
  const added = Array.from({ length: 20 }, (_, i) => ({ ...base, notification_id: String(i) }))
  assert.equal(noticeDelta(seen, added, true).length, 20); assert.equal(noticeDelta(seen, added, true).length, 0)
})

test('admin shows target email and actor, server filters, grouping and pagination', async () => {
  render(<MemoryRouter><AdminOperations /></MemoryRouter>); await screen.findByRole('button', { name: 'alice@example.com', exact: true }); assert.ok(screen.getByText('admin@example.com')); assert.ok(screen.getByRole('cell', { name: 'BOOK RETURNED' }))
  fireEvent.change(screen.getByRole('textbox', { name: 'Search user email...' }), { target: { value: 'alice@' } })
  fireEvent.change(screen.getByRole('textbox', { name: 'Search book title or work ID' }), { target: { value: 'Dracula' } })
  fireEvent.click(screen.getByRole('combobox', { name: 'Operation type' })); fireEvent.click(screen.getByRole('option', { name: 'Book returned' }))
  await waitFor(() => assert.ok(calls.some(c => c.url.includes('email=alice%40') && c.url.includes('title=Dracula') && c.url.includes('operation_type=BOOK_RETURNED'))))
  fireEvent.click(screen.getByRole('button', { name: 'Group by user' })); await screen.findByRole('heading', { name: 'alice@example.com' })
  fireEvent.click(screen.getByRole('button', { name: 'Next', exact: true })); await waitFor(() => assert.ok(calls.some(c => c.url.includes('offset=20'))))
})

test('account drilldown exposes summaries and filters selected identity', async () => {
  render(<MemoryRouter><AdminOperations /></MemoryRouter>); fireEvent.click(await screen.findByRole('button', { name: 'alice@example.com', exact: true })); const dialog = await screen.findByRole('dialog', { name: 'Activity for alice@example.com' })
  assert.ok(within(dialog).getByRole('heading', { name: 'Current Loans (1)' })); assert.equal(dialog.textContent?.includes('password'), false)
  await waitFor(() => assert.ok(calls.some(c => c.url.includes('user_id=2'))))
})

test('admin composer picks authoritative account, validates fields and sends canonical IDs', async () => {
  render(<AdminNotifications />); fireEvent.click(screen.getByRole('button', { name: 'Send Notification' })); const dialog = screen.getByRole('dialog', { name: 'Send Notification' })
  assert.equal((within(dialog).getByRole('button', { name: 'Send', exact: true }) as HTMLButtonElement).disabled, true)
  fireEvent.click(await within(dialog).findByRole('button', { name: /alice@example.com/ })); fireEvent.change(within(dialog).getByRole('textbox', { name: 'Notification title' }), { target: { value: 'Library notice' } }); fireEvent.change(within(dialog).getByRole('textbox', { name: 'Notification message' }), { target: { value: 'Please visit the circulation desk.' } }); fireEvent.click(within(dialog).getByRole('button', { name: 'Send', exact: true }))
  await screen.findByText('Notification sent successfully.'); const sent = calls.find(c => c.url === '/api/admin/notifications' && c.method === 'POST')!; assert.deepEqual(sent.body.recipient_user_ids, [2]); assert.ok(sent.body.request_id); assert.equal(sent.body.user_id, undefined)
})

test('panel close and Escape restore focus to bell', async () => {
  render(<NotificationCenter />); const bell = await screen.findByRole('button', { name: 'Notifications, 1 unread' }); fireEvent.click(bell); await screen.findByRole('region', { name: 'Notification Center' }); fireEvent.keyDown(document, { key: 'Escape' }); assert.equal(screen.queryByRole('region', { name: 'Notification Center' }), null); assert.equal(document.activeElement, bell)
})

test('select all includes users beyond search results and sends every selected ID in bounded batches', async () => {
  directoryUsers = Array.from({ length: 73 }, (_, i) => ({ user_id: i + 10, email: `reader${i}@example.com`, name: `Reader ${i}` }))
  render(<AdminNotifications />); fireEvent.click(screen.getByRole('button', { name: 'Send Notification' }))
  const dialog = screen.getByRole('dialog', { name: 'Send Notification' })
  fireEvent.change(within(dialog).getByRole('textbox', { name: 'Recipient email' }), { target: { value: 'reader72@' } })
  fireEvent.click(within(dialog).getByRole('button', { name: 'Select all users' }))
  await within(dialog).findByText('73 selected')
  assert.equal(calls.some(c => c.method === 'POST'), false)
  assert.ok(calls.some(c => c.url.includes('limit=50&offset=50')))
  fireEvent.click(within(dialog).getByRole('button', { name: '+68 more' }))
  fireEvent.click(within(dialog).getByRole('button', { name: 'Remove reader72@example.com' }))
  fireEvent.change(within(dialog).getByRole('textbox', { name: 'Notification title' }), { target: { value: 'New arrivals' } })
  fireEvent.change(within(dialog).getByRole('textbox', { name: 'Notification message' }), { target: { value: 'Come see our new books.' } })
  fireEvent.click(within(dialog).getByRole('button', { name: 'Send', exact: true }))
  await screen.findByText('Notification sent successfully.')
  const sends = calls.filter(c => c.url === '/api/admin/notifications' && c.method === 'POST')
  assert.deepEqual(sends.map(c => c.body.recipient_user_ids.length), [50, 22])
  assert.deepEqual(sends.flatMap(c => c.body.recipient_user_ids), directoryUsers.slice(0, 72).map(u => u.user_id))
  assert.equal(sends[0].body.request_id, sends[1].body.request_id)
})

test('failed directory page preserves prior recipients and select all supports clear', async () => {
  directoryUsers = Array.from({ length: 73 }, (_, i) => ({ user_id: i + 10, email: `reader${i}@example.com`, name: `Reader ${i}` }))
  const mockFetch = globalThis.fetch
  globalThis.fetch = async (url, options) => String(url).includes('limit=50&offset=50') ? Response.json({ detail: 'Unavailable' }, { status: 503 }) : mockFetch(url, options)
  render(<NotificationComposer initial={[alice]} onClose={() => {}} onSent={() => {}} />)
  const dialog = screen.getByRole('dialog', { name: 'Send Notification' })
  fireEvent.click(within(dialog).getByRole('button', { name: 'Select all users' }))
  await within(dialog).findByRole('alert'); assert.ok(within(dialog).getByText('1 selected'))
  assert.ok(within(dialog).getByRole('button', { name: 'Remove alice@example.com' }))
  globalThis.fetch = mockFetch
  fireEvent.click(within(dialog).getByRole('button', { name: 'Select all users' }))
  await within(dialog).findByText('73 selected')
  fireEvent.click(within(dialog).getByRole('button', { name: 'Clear', exact: true }))
  await within(dialog).findByText('0 selected')
})

test('partial send retry continues remaining recipients with same UUID and blocks duplicate submit', async () => {
  directoryUsers = Array.from({ length: 73 }, (_, i) => ({ user_id: i + 10, email: `reader${i}@example.com`, name: `Reader ${i}` }))
  const mockFetch = globalThis.fetch; let fail = true
  const attempts: any[] = []
  globalThis.fetch = async (url, options) => {
    if (String(url) === '/api/admin/notifications' && options?.method === 'POST') {
      const body = JSON.parse(String(options.body)); attempts.push(body)
      if (body.recipient_user_ids[0] === 60 && fail) { fail = false; return Response.json({ detail: 'Temporary outage' }, { status: 503 }) }
    }
    return mockFetch(url, options)
  }
  render(<AdminNotifications />); fireEvent.click(screen.getByRole('button', { name: 'Send Notification' }))
  const dialog = screen.getByRole('dialog', { name: 'Send Notification' })
  fireEvent.click(within(dialog).getByRole('button', { name: 'Select all users' })); await within(dialog).findByText('73 selected')
  fireEvent.change(within(dialog).getByRole('textbox', { name: 'Notification title' }), { target: { value: 'Event' } })
  fireEvent.change(within(dialog).getByRole('textbox', { name: 'Notification message' }), { target: { value: 'Join us tomorrow.' } })
  const form = dialog.querySelector('form')!
  await act(async () => { fireEvent.submit(form); fireEvent.submit(form) })
  const error = await within(dialog).findByRole('alert'); assert.ok(error.textContent?.includes('50 of 73'))
  assert.equal(attempts.length, 2)
  assert.equal((within(dialog).getByRole('textbox', { name: 'Notification message' }) as HTMLTextAreaElement).disabled, true)
  fireEvent.click(within(dialog).getByRole('button', { name: 'Retry remaining' }))
  await screen.findByText('Notification sent successfully.')
  assert.equal(attempts.length, 3)
  assert.deepEqual(attempts[2].recipient_user_ids, attempts[1].recipient_user_ids)
  assert.equal(new Set(attempts.map(a => a.request_id)).size, 1)
})

test('themed operation filter supports keyboard selection, Escape and outside dismissal', () => {
  const selected: string[]=[]
  render(<OperationTypeFilter value="" types={['BOOK_ISSUED','BOOK_RENEWED']} onChange={value=>selected.push(value)} />)
  const trigger=screen.getByRole('combobox',{name:'Operation type'})
  fireEvent.keyDown(trigger,{key:'End'}); assert.equal(trigger.getAttribute('aria-expanded'),'true')
  assert.ok(screen.getByRole('listbox',{name:'Operation types'}))
  fireEvent.keyDown(trigger,{key:'Enter'}); assert.deepEqual(selected,['BOOK_RENEWED'])
  assert.equal(screen.queryByRole('listbox'),null)
  fireEvent.click(trigger); fireEvent.keyDown(trigger,{key:'Escape'}); assert.equal(screen.queryByRole('listbox'),null)
  fireEvent.click(trigger); fireEvent.pointerDown(document.body); assert.equal(screen.queryByRole('listbox'),null)
})

test('performed by displays verified reader and staff emails, explicitly labelled legacy readers and System', async () => {
  const mockFetch=globalThis.fetch
  globalThis.fetch=async(url,options)=>String(url).startsWith('/api/admin/operations?') ? Response.json({count:4,operation_types:['BOOK_ISSUED'],operations:[
    {operation_id:'1',operation_type:'BOOK_ISSUED',actor_user_id:2,actor:alice},
    {operation_id:'2',operation_type:'BOOK_RETURNED',actor_user_id:1,actor:admin},
    {operation_id:'3',operation_type:'RESERVATION_CANCELLED',actor_user_id:null,actor:null,performed_by:{kind:'LEGACY_READER',account:alice,user_id:2}},
    {operation_id:'4',operation_type:'RESERVATION_READY',actor_user_id:null,actor:null,performed_by:{kind:'SYSTEM',account:null,user_id:null}},
  ].map(r=>({...r,target_user_id:2,target_user:alice,book:{work_id:'OL1W',title:'Dracula'},occurred_at:base.created_at,source_ref:{}}))}) : mockFetch(url,options)
  render(<MemoryRouter><AdminOperations/></MemoryRouter>); await screen.findByText('User action')
  const rows=screen.getAllByRole('row').slice(1)
  assert.ok(within(rows[0]).getByRole('cell',{name:'alice@example.com User action'}))
  assert.ok(within(rows[1]).getByRole('cell',{name:'admin@example.com Staff-assisted action'}))
  assert.ok(within(rows[2]).getByRole('cell',{name:'alice@example.com Reader · actor not recorded'}))
  assert.ok(within(rows[3]).getByRole('cell',{name:'System Automatic circulation update'}))
  assert.equal(screen.queryByText('Unknown actor'),null)
})
