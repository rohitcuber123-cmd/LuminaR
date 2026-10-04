import assert from 'node:assert/strict'
import { test, beforeEach, afterEach } from 'node:test'
import { JSDOM } from 'jsdom'
import React, { useState } from 'react'

const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173/profile' })
Object.assign(globalThis, { window: dom.window, document: dom.window.document, localStorage: dom.window.localStorage, HTMLElement: dom.window.HTMLElement, Event: dom.window.Event, IS_REACT_ACT_ENVIRONMENT: true })
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true })
const { render, screen, fireEvent, cleanup, waitFor, act } = await import('@testing-library/react')
const { MemoryRouter } = await import('react-router-dom')
const { LoanRenewalControl } = await import('../src/components/LoanRenewalControl')
const { ProfilePage } = await import('../src/pages/ProfilePage')
const { NotificationCenter } = await import('../src/components/NotificationCenter')
const { noticeDelta } = await import('../src/lib/notifications')
const { AdminOperations } = await import('../src/pages/AdminOperations')
const { useAuthStore } = await import('../src/store/useAuthStore')
const { returnBook } = await import('../src/lib/api')
const alice = { user_id: 2, email: 'alice@example.com', name: 'Alice', role: 'GENERAL_USER' as const }
const settings = { eligible: true, enabled: true, days: 14, max_renewals: 1, renewal_count: 0, remaining_renewals: 1, reason: null, message: null }
const initial = { issue_id: 1, user_id: 2, work_id: 'OL1W', title: 'Dracula', issued_at: '2027-01-01T12:00:00Z', due_date: '2027-01-15T12:00:00Z', status: 'ISSUED', renewal: settings }
let loan: any, notices: any[], calls: { path: string; body?: any; method?: string }[], original: typeof fetch, blocked: boolean, hold: boolean, release: (() => void) | undefined
const base = { notification_id: 'due', type: 'DUE_SOON', title: 'Book due soon', message: 'Dracula is due in 2 days.', created_at: initial.issued_at, read_at: null, resolved_at: null, resolution_reason: null }
beforeEach(() => {
  localStorage.setItem('luminar_token','alice-token'); useAuthStore.setState({ user: alice, token: 'alice-token', isAuthenticated: true });
  loan = structuredClone(initial);notices=[structuredClone(base)];calls=[];original=globalThis.fetch;blocked=false;hold=false;release=undefined
  globalThis.fetch = async (url,opts) => {
    const path=String(url), body=opts?.body ? JSON.parse(String(opts.body)):undefined;calls.push({path,body,method:opts?.method})
    if (path.endsWith('/renew') || path.includes('/admin/operations/renew/')) {
      if(hold)await new Promise<void>(resolve=>{release=resolve})
      if(blocked)return Response.json({detail:{code:'RENEWAL_BLOCKED_BY_RESERVATION',message:'Another reader is waiting for this book.'}},{status:409})
      loan={...loan,due_date:'2027-01-29T12:00:00Z',renewal:{...settings,eligible:false,renewal_count:1,remaining_renewals:0,reason:'RENEWAL_LIMIT_REACHED',message:'This loan has used all available renewals.'}}
      notices=notices.map(n=>n.type==='ADMIN_MESSAGE'?n:{...n,resolved_at:initial.issued_at,resolution_reason:'LOAN_RENEWED'})
      return Response.json({issue_id:1,work_id:'OL1W',old_due_date:initial.due_date,new_due_date:loan.due_date,renewal_count:1,remaining_renewals:0,status:'ISSUED',idempotent_replay:false})
    }
    if(path.startsWith('/api/issues/return/')){loan={...loan,status:'RETURNED'};notices=notices.map(n=>n.type==='ADMIN_MESSAGE'?n:{...n,resolved_at:initial.issued_at,resolution_reason:'LOAN_RETURNED'});return Response.json({issue:loan})}
    if(path.startsWith('/api/notifications?'))return Response.json({notifications:notices,count:notices.length,unread_count:notices.filter(n=>!n.read_at&&!n.resolved_at).length})
    if(path==='/api/issues/my')return Response.json({issues:[loan]})
    if(path==='/api/reservations/my')return Response.json({reservations:[]})
    if(path==='/api/fines/my')return Response.json({fines:[]})
    if(path==='/api/activity/my')return Response.json({activities:[]})
    if(path==='/api/reading-list/my')return Response.json({items:[]})
    if(path.startsWith('/api/admin/operations?'))return Response.json({count:1,operation_types:['BOOK_RENEWED'],operations:[{operation_id:'1',operation_type:'BOOK_RENEWED',target_user_id:2,target_user:alice,actor_user_id:2,actor:alice,book:{work_id:'OL1W',title:'Dracula'},occurred_at:initial.issued_at,old_due_date:initial.due_date,new_due_date:'2027-01-29T12:00:00Z',status:'ISSUED',source_ref:{issue_id:1}}]})
    throw new Error('Unexpected API '+path)
  }
})
afterEach(()=>{cleanup();globalThis.fetch=original})
function Harness(){const [current,setCurrent]=useState(loan);return <><p>Due: {current.due_date}</p><LoanRenewalControl loan={current} onRenewed={()=>setCurrent({...loan})}/></>}

test('eligible loan shows configured renewal count and button',()=>{
 render(<LoanRenewalControl loan={loan} onRenewed={()=>{}}/>);assert.ok(screen.getByText('Renewals: 0 / 1'));assert.equal((screen.getByRole('button',{name:'Renew'}) as HTMLButtonElement).disabled,false)
})
test('ineligible loan disables renewal with authoritative friendly reason',()=>{
 loan.renewal={...settings,eligible:false,reason:'RENEWAL_OVERDUE',message:'Overdue loans cannot be renewed.'};render(<LoanRenewalControl loan={loan} onRenewed={()=>{}}/>);assert.equal((screen.getByRole('button',{name:'Renew'}) as HTMLButtonElement).disabled,true);assert.ok(screen.getByText('Overdue loans cannot be renewed.'))
})
test('renew loading disables double-click and sends pinned due date without owner',async()=>{
 hold=true;render(<Harness/>);const button=screen.getByRole('button',{name:'Renew'});fireEvent.click(button);fireEvent.click(button)
 await screen.findByRole('button',{name:'Renewing…'});assert.equal((button as HTMLButtonElement).disabled,true)
 assert.equal(calls.filter(c=>c.path.endsWith('/renew')).length,1);const payload=calls[0].body;assert.equal(payload.expected_due_date,initial.due_date);assert.ok(payload.request_id);assert.equal(payload.user_id,undefined)
 await act(async()=>release!());await screen.findByText('Renewals: 1 / 1')
})
test('success refreshes due date and configured count and disables further renewal',async()=>{
 render(<Harness/>);fireEvent.click(screen.getByRole('button',{name:'Renew'}));await screen.findByText('Due: 2027-01-29T12:00:00Z');assert.ok(screen.getByText('Renewals: 1 / 1'));assert.equal((screen.getByRole('button',{name:'Renew'}) as HTMLButtonElement).disabled,true)
})
test('server reservation-block message is shown and retry keeps idempotency UUID',async()=>{
 blocked=true;render(<Harness/>);fireEvent.click(screen.getByRole('button',{name:'Renew'}));assert.equal((await screen.findByRole('alert')).textContent,'Another reader is waiting for this book.')
 fireEvent.click(screen.getByRole('button',{name:'Renew'}));await waitFor(()=>assert.equal(calls.filter(c=>c.path.endsWith('/renew')).length,2));assert.equal(calls[0].body.request_id,calls[1].body.request_id)
})
test('Admin-assisted control uses protected Admin endpoint',async()=>{
 render(<LoanRenewalControl assisted loan={loan} onRenewed={()=>{}}/>);fireEvent.click(screen.getByRole('button',{name:'Renew'}));await waitFor(()=>assert.ok(calls.some(c=>c.path==='/api/admin/operations/renew/1')))
})
test('Profile integrates renewal and reloads authoritative loan due date',async()=>{
 render(<MemoryRouter><ProfilePage/></MemoryRouter>);fireEvent.click(await screen.findByRole('button',{name:'Renew'}));await screen.findByText('Renewals: 1 / 1');assert.ok(screen.getByText('Due: '+new Date('2027-01-29T12:00:00Z').toLocaleDateString()))
})
test('Admin operations shows renewal snapshots and renewal type filter',async()=>{
 render(<MemoryRouter><AdminOperations/></MemoryRouter>);await screen.findByRole('cell',{name:/BOOK RENEWED/});fireEvent.click(screen.getByRole('combobox',{name:'Operation type'}));fireEvent.click(screen.getByRole('option',{name:'Book renewed'}));await waitFor(()=>assert.ok(calls.some(c=>c.path.includes('operation_type=BOOK_RENEWED'))))
})
test('resolved reminder remains in history without unread styling or toast',async()=>{
 notices=[{...base,resolved_at:initial.issued_at,resolution_reason:'LOAN_RENEWED'}];render(<NotificationCenter/>);fireEvent.click(await screen.findByRole('button',{name:'Notifications',exact:true}));await screen.findByText('Resolved — loan renewed');assert.equal(document.querySelector('.notification-unread'),null);assert.equal(screen.queryByRole('status'),null);assert.equal(noticeDelta(new Set(),notices,true).length,0)
})
test('return event refresh resolves warning while leaving Admin message unread and unchanged',async()=>{
 notices.push({...base,notification_id:'admin',type:'ADMIN_MESSAGE',title:'Admin note',message:'Visit the desk.'});render(<NotificationCenter/>);fireEvent.click(await screen.findByRole('button',{name:'Notifications, 2 unread'}));await act(async()=>{await returnBook(1)});await screen.findByRole('button',{name:'Notifications, 1 unread'});await screen.findByText('Resolved — loan returned');assert.ok(screen.getByText('Visit the desk.'));assert.equal(notices[1].resolved_at,null)
})
