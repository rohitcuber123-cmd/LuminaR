import { chooseSelect } from './select-control'
import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { test, beforeEach, afterEach } from 'node:test'
import React from 'react'
import { JSDOM } from 'jsdom'
import type { Library, LibraryRole } from '../src/lib/institutions'

registerHooks({load(url, context, next) {return url.endsWith('.css') ? {format:'module',source:'',shortCircuit:true} : next(url,context)}})
const dom = new JSDOM('<html><body></body></html>',{url:'http://localhost'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,HTMLElement:dom.window.HTMLElement,Event:dom.window.Event,FormData:dom.window.FormData,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
dom.window.HTMLDialogElement.prototype.showModal = function(){this.setAttribute('open','')}
dom.window.HTMLDialogElement.prototype.close = function(){this.removeAttribute('open')}
const {render,screen,fireEvent,cleanup,waitFor,act} = await import('@testing-library/react')
const {MemoryRouter,Routes,Route,useLocation,Link} = await import('react-router-dom')
const {Header} = await import('../src/components/Header.tsx')
const {MyLibrariesPage} = await import('../src/pages/AccountPages.tsx')
const {ExploreLibrariesPage,PendingInvitationsPage} = await import('../src/pages/Institutions.tsx')
const {InstitutionPanel} = await import('../src/pages/InstitutionPanel.tsx')
const {WorkspaceRoute} = await import('../src/components/WorkspaceRoute.tsx')
const {useInstitutionStore:store} = await import('../src/store/useInstitutionStore.ts')
const {useAuthStore:auth} = await import('../src/store/useAuthStore.ts')
const {usePlatformStore:platform} = await import('../src/store/usePlatformStore.ts')
const a='11111111-1111-4111-8111-111111111111',b='22222222-2222-4222-8222-222222222222',c='33333333-3333-4333-8333-333333333333',d='44444444-4444-4444-8444-444444444444'
function library(id:string,role:LibraryRole):Library{return {library_id:id,name:`Library ${id===a?'A':id===b?'B':id===c?'C':'D'}`,slug:'display-alias',description:null,library_type:'PUBLIC_LIBRARY',access_mode:'PUBLIC',membership:{membership_id:id,library_id:id,user_id:1,role,status:'ACTIVE',is_owner:role==='ADMIN',joined_at:'2026-10-09T00:00:00Z'}}}
let rows:Library[], original:typeof fetch,calls:string[],mode:string
beforeEach(()=>{
 localStorage.clear();localStorage.setItem('luminar_token','navigation-test')
 auth.setState({token:'navigation-test',isAuthenticated:true,user:{user_id:1,email:'generic@example.com',name:'Generic',role:'ADMIN'}})
 rows=[library(a,'GENERAL_USER'),library(b,'GENERAL_USER'),library(c,'ADMIN'),library(d,'LIBRARIAN')]
 store.setState({owner:'generic@example.com',session:'navigation-test',libraries:rows,activeId:a,patronLibraryId:a,staffLibraryId:c,workspace:'PATRON',loading:false,error:null})
 platform.setState({session:'navigation-test',roles:[],loading:false,error:''})
 calls=[];mode='';original=globalThis.fetch
 globalThis.fetch=async (url,opts)=>{
  const p=String(url),method=opts?.method||'GET';calls.push(`${method} ${p}`)
  if(p.includes('/me/libraries'))return Response.json({results:rows,has_more:false})
  if(p.endsWith('/context')) {const row=rows.find(l=>p.includes(l.library_id));return Response.json({library:row,membership:row?.membership})}
  if(p.includes('/libraries?'))return Response.json({results:[{...library(a,'GENERAL_USER'),membership:mode==='join'?null:rows[0].membership}],total:1})
  if(p.endsWith('/join')){rows=[library(a,'GENERAL_USER')];return Response.json({library:rows[0],membership:rows[0].membership})}
  if(p.includes('/me/invitations'))return Response.json({results:mode==='invite'?[{invitation_id:d,library_id:a,library_name:'Library A',email_normalized:'generic@example.com',role:'LIBRARIAN',expires_at:'2099-01-01',status:'PENDING'}]:[],total:mode==='invite'?1:0})
  if(p.endsWith('/accept')){mode='';rows=[library(a,'LIBRARIAN')];return Response.json({library:rows[0],membership:rows[0].membership})}
  if(p.includes('/memberships?'))return Response.json({results:[{...library(b,'GENERAL_USER').membership,name:'Other',email:'other@example.com',is_owner:false}],total:1})
  if(p.includes('/memberships/')&&method==='PATCH'){rows=[library(c,'ADMIN'),library(b,'LIBRARIAN')];return Response.json({})}
  if(p.endsWith('/access'))return Response.json({access_code_set:false})
  return Response.json({results:[],total:0,unread_count:0})
 }
})
afterEach(async()=>{await act(async()=>{await Promise.resolve()});cleanup();globalThis.fetch=original})
function Position(){const loc=useLocation();return <output data-testid="position">{loc.pathname}</output>}
function header(path:string){render(<MemoryRouter initialEntries={[path]}><Header/><Position/><Link to={`/libraries/${b}/my-library`}>Switch B</Link></MemoryRouter>)}
function logo(){return screen.getByRole('link',{name:'LuminaR home',exact:true})}
function account(){render(<MemoryRouter initialEntries={['/account/libraries']}><MyLibrariesPage/></MemoryRouter>)}
test('test_logo_global_context_goes_root',()=>{for(const path of ['/','/search','/catalog','/account/profile','/account/libraries','/libraries','/libraries/register']){header(path);assert.equal(logo().getAttribute('href'),'/');cleanup()}})
test('test_logo_patron_home_stays_current_library',()=>{header(`/libraries/${b}`);assert.equal(logo().getAttribute('href'),`/libraries/${b}`)})
test('test_logo_patron_child_route_returns_library_home',()=>{header(`/libraries/${b}/books/${d}`);assert.equal(logo().getAttribute('href'),`/libraries/${b}`)})
for(const section of ['my-library','reservations','fees'])test(`test_logo_${section.replace('-','_')}_returns_same_library_home`,()=>{header(`/libraries/${b}/${section}`);fireEvent.click(logo());assert.equal(screen.getByTestId('position').textContent,`/libraries/${b}`)})
test('test_logo_library_switch_uses_new_library',()=>{header(`/libraries/${a}`);fireEvent.click(screen.getByRole('link',{name:'Switch B'}));assert.equal(logo().getAttribute('href'),`/libraries/${b}`)})
test('test_logo_does_not_use_stale_remembered_library',()=>{localStorage.setItem('luminar_workspace_contexts',JSON.stringify({owner:'generic@example.com',patronLibraryId:a}));header(`/libraries/${b}/fees`);assert.equal(logo().getAttribute('href'),`/libraries/${b}`)})
test('test_logo_staff_never_enters_patron_workspace',()=>{header(`/staff/libraries/${c}/inventory`);assert.equal(logo().getAttribute('href'),`/staff/libraries/${c}`)})
test('test_logo_platform_never_enters_tenant_workspace',()=>{header('/platform/catalogue');assert.equal(logo().getAttribute('href'),'/platform')})
for(const [name,label,section] of [['catalog','Browse Books','catalogue'],['new_arrivals','New Arrivals','new-arrivals'],['my_library','My Library','my-library']])test(`test_header_${name}_patron_context`,()=>{header(`/libraries/${b}/fees`);assert.equal(screen.getByRole('link',{name:label,exact:true}).getAttribute('href'),`/libraries/${b}/${section}`)})
test('test_account_page_displays_member_library',async()=>{account();await waitFor(()=>assert.equal(store.getState().loading,false));assert.ok(screen.getByRole('heading',{name:'Library A'}));assert.equal(screen.getAllByRole('link',{name:'Open Library',exact:true}).length,2)})
test('test_account_page_displays_staff_library',async()=>{account();await waitFor(()=>assert.equal(store.getState().loading,false));assert.ok(screen.getByText('Owner · Admin'));assert.ok(screen.getByText('Librarian'))})
test('test_member_open_library_uses_uuid',()=>{account();const card=screen.getAllByRole('article')[0].querySelector('a');assert.equal(card?.getAttribute('href'),`/libraries/${a}`)})
test('test_staff_manage_library_uses_uuid',()=>{account();assert.deepEqual(screen.getAllByRole('link',{name:'Open Staff Workspace'}).map(l=>l.getAttribute('href')),[`/staff/libraries/${c}`,`/staff/libraries/${d}`])})
test('test_account_page_does_not_use_legacy_role_authority',()=>{rows=[library(a,'GENERAL_USER')];store.setState({libraries:rows});account();assert.equal(screen.queryByRole('link',{name:'Open Staff Workspace'}),null);assert.equal(screen.getByRole('link',{name:'Open Library',exact:true}).getAttribute('href'),`/libraries/${a}`)})
test('test_multiple_member_libraries_all_render',()=>{account();assert.equal(screen.getAllByRole('link',{name:'Open Library',exact:true}).length,2)})
test('test_multiple_staff_libraries_all_render',()=>{account();assert.equal(screen.getAllByRole('link',{name:'Open Staff Workspace'}).length,2)})
test('test_membership_join_invalidates_account_libraries',async()=>{mode='join';rows=[];store.setState({libraries:[]});render(<MemoryRouter><ExploreLibrariesPage/><Position/></MemoryRouter>);fireEvent.click(await screen.findByRole('button',{name:'Join Library'}));await waitFor(()=>assert.equal(store.getState().libraries.length,1));assert.ok(calls.some(c=>c.startsWith('POST')&&c.endsWith('/join')));assert.ok(calls.some(c=>c.includes('/me/libraries')));assert.equal(store.getState().libraries[0].membership?.role,'GENERAL_USER')})
test('test_invitation_accept_invalidates_account_libraries',async()=>{mode='invite';render(<MemoryRouter><PendingInvitationsPage/></MemoryRouter>);fireEvent.click(await screen.findByRole('button',{name:'Accept',exact:true}));await waitFor(()=>assert.equal(store.getState().libraries[0].membership?.role,'LIBRARIAN'));assert.ok(calls.some(c=>c.includes('/me/libraries')))})
test('test_membership_role_change_invalidates_account_libraries',async()=>{store.setState({activeId:c,workspace:'STAFF'});render(<MemoryRouter><InstitutionPanel section="members"/></MemoryRouter>);chooseSelect(await screen.findByLabelText('Role for other@example.com'),'LIBRARIAN',fireEvent);await waitFor(()=>assert.equal(store.getState().libraries.find(l=>l.library_id===b)?.membership?.role,'LIBRARIAN'));assert.ok(calls.some(c=>c.startsWith('PATCH')&&c.includes('/memberships/')));assert.ok(calls.some(c=>c.includes('/me/libraries')))})
test('test_direct_url_and_account_navigation_consistent',async()=>{render(<MemoryRouter initialEntries={['/account/libraries']}><Position/><Routes><Route path="/account/libraries" element={<MyLibrariesPage/>}/><Route path="/libraries/:libraryId" element={<WorkspaceRoute><p>Authorized Patron</p></WorkspaceRoute>}/></Routes></MemoryRouter>);fireEvent.click(screen.getAllByRole('link',{name:'Open Library',exact:true})[1]);await screen.findByText('Authorized Patron');assert.equal(screen.getByTestId('position').textContent,`/libraries/${b}`);cleanup();render(<MemoryRouter initialEntries={[`/libraries/${b}`]}><Position/><Routes><Route path="/libraries/:libraryId" element={<WorkspaceRoute><p>Authorized Patron</p></WorkspaceRoute>}/></Routes></MemoryRouter>);await screen.findByText('Authorized Patron');assert.equal(screen.getByTestId('position').textContent,`/libraries/${b}`)})
test('test_remembered_context_does_not_hide_membership',()=>{store.setState({activeId:c,patronLibraryId:b,staffLibraryId:d});account();assert.equal(screen.getAllByRole('article').length,4)})
test('account entry refresh discovers newly available memberships',async()=>{store.setState({libraries:[]});account();await screen.findByRole('heading',{name:'Library B'});assert.ok(calls.some(c=>c.includes('/me/libraries')))})
test('account menu opening refetches stale membership discovery',async()=>{store.setState({libraries:[]});header('/');fireEvent.click(screen.getByRole('button',{name:/Open account menu/}));await screen.findByRole('menuitem',{name:/Library B/});assert.ok(calls.some(c=>c.includes('/me/libraries')))})
test('membership pages traverse every server page',async()=>{const all=Array.from({length:103},(_,i)=>library(`10000000-0000-4000-8000-${String(i).padStart(12,'0')}`,'GENERAL_USER'));globalThis.fetch=async url=>{const u=new URL(String(url),'http://localhost');const offset=Number(u.searchParams.get('offset'));return Response.json({results:all.slice(offset,offset+100),has_more:offset+100<all.length})};await act(async()=>{await store.getState().refresh()});assert.equal(store.getState().libraries.length,103)})
test('header context does not wait for remembered active projection',()=>{store.setState({libraries:[],activeId:null});header(`/libraries/${b}/new-arrivals`);assert.equal(logo().getAttribute('href'),`/libraries/${b}`);assert.equal(screen.getByRole('link',{name:'Browse Books'}).getAttribute('href'),`/libraries/${b}/catalogue`)})
test('account page never exposes another session memberships',async()=>{store.setState({session:'different-session',owner:null});account();assert.equal(screen.queryByRole('link',{name:'Open Library',exact:true}),null)})
test('patron header search uses URL rather than remembered tenant',async()=>{header(`/libraries/${b}/fees`);fireEvent.click(screen.getByRole('button',{name:'Search the catalog'}));fireEvent.change(screen.getByRole('searchbox'),{target:{value:'systems'}});fireEvent.submit(screen.getByRole('searchbox').closest('form')!);assert.equal(screen.getByTestId('position').textContent,`/libraries/${b}/catalogue`)})
