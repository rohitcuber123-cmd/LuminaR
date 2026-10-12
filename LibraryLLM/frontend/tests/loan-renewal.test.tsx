import assert from 'node:assert/strict'
import { test, beforeEach, afterEach } from 'node:test'
import { JSDOM } from 'jsdom'
import React from 'react'

const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173/admin' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, sessionStorage: dom.window.sessionStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
dom.window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
dom.window.HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }
const { render, screen, cleanup } = await import('@testing-library/react')
const { MemoryRouter } = await import('react-router-dom')
const { LegacyOperationHistory } = await import('../src/pages/PlatformOperations')
const { useAuthStore } = await import('../src/store/useAuthStore')
const { LegacyProfilePage } = await import('../src/pages/ProfilePage')
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
    if (path.startsWith('/api/platform/users?')) {
      const params = new URL(path, 'http://localhost').searchParams
      const matched = directoryUsers.filter(u => u.email.includes(params.get('q') || ''))
      const offset = Number(params.get('offset') || 0), limit = Number(params.get('limit') || 20)
      return Response.json({ users: matched.slice(offset, offset + limit), count: matched.length })
    }
    if (path.startsWith('/api/platform/users/2/activity')) return Response.json({ user: alice, loans: { count: 1, records: [{ title: 'Dracula' }] }, reservations: { count: 0, records: [] }, fines: { count: 0, records: [] }, notifications: { count: 0, records: [] } })
    if (path.startsWith('/api/platform/operations?')) return Response.json({ operations: [{ operation_id: '1', operation_type: 'BOOK_RETURNED', target_user_id: 2, target_user: alice, actor_user_id: 1, actor: admin, book: { work_id: 'OL1W', title: 'Dracula' }, occurred_at: base.created_at, source_ref: {} }], count: opsCount, operation_types: ['BOOK_ISSUED', 'BOOK_RETURNED'] })
    if (path.startsWith('/api/platform/notifications/sent')) return Response.json({ notifications: [], count: 0 })
    if (path === '/api/platform/notifications' && options?.method === 'POST') return Response.json({ recipient_count: 1 })
    throw new Error(`Unexpected API: ${path}`)
  }
})
afterEach(() => { cleanup(); globalThis.fetch = original })

test('historical operations cannot renew or receive canonical loans',async()=>{
 const previous=globalThis.fetch
 globalThis.fetch=async(url,options)=>String(url).includes('/platform/operations?') ? Response.json({count:1,operation_types:['BOOK_ISSUED'],operations:[{operation_id:'1',operation_type:'BOOK_ISSUED',status:'ISSUED',target_user_id:2,target_user:alice,actor_user_id:1,actor:admin,book:{work_id:'OL1W',title:'Dracula'},due_at:new Date().toISOString(),occurred_at:base.created_at,source_ref:{issue_id:1}}]}) : previous(url,options)
 render(<MemoryRouter><LegacyOperationHistory/></MemoryRouter>);await screen.findByRole('cell',{name:'Dracula'})
 assert.equal(screen.queryByRole('button',{name:/Renew|Process return/}),null)
 assert.equal(calls.filter(c=>c.method==='POST').length,0)
})
test('personal legacy history has no circulation mutation controls',async()=>{
 globalThis.fetch=async(url)=>{
 const path=String(url);calls.push({url:path})
 if(path.includes('/issues/my'))return Response.json({issues:[{issue_id:1,title:'Dracula',status:'ISSUED',due_date:new Date().toISOString()}]})
 if(path.includes('/reservations/my'))return Response.json({reservations:[]})
 if(path.includes('/fines/my'))return Response.json({fines:[]})
 return Response.json({activities:[]})
 }
 render(<MemoryRouter><LegacyProfilePage/></MemoryRouter>);await screen.findByText('Dracula')
 assert.equal(screen.queryByRole('button',{name:/Renew|Return|Pay|Cancel/}),null)
 assert.ok(calls.every(c=>!c.method||c.method==='GET'))
})
