import assert from 'node:assert/strict'
import {registerHooks} from 'node:module'
import {test,beforeEach,afterEach} from 'node:test'
import {readFileSync} from 'node:fs'
import React from 'react'
import {JSDOM} from 'jsdom'
registerHooks({load(url,context,next){return url.endsWith('.css')?{format:'module',source:'',shortCircuit:true}:next(url,context)}})
const dom=new JSDOM('<html><body></body></html>',{url:'http://localhost:5173'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,HTMLElement:dom.window.HTMLElement,Event:dom.window.Event,FormData:dom.window.FormData,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
dom.window.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')}
dom.window.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')}
const {render,screen,fireEvent,waitFor,cleanup,within}=await import('@testing-library/react')
const {MemoryRouter,Routes,Route,useLocation}=await import('react-router-dom')
const {Header}=await import('../src/components/Header')
const {EventsPage}=await import('../src/pages/EventsPage')
const {ManageEventsPage}=await import('../src/pages/ManageEventsPage')
const {EventDetailPage}=await import('../src/pages/EventDetailPage')
const {EventEditorPage}=await import('../src/pages/EventEditorPage')
const {NotificationCenter}=await import('../src/components/NotificationCenter')
const {resolveNotificationAction:resolve}=await import('../src/lib/notifications')
const {eventApiFor}=await import('../src/lib/events')
const {useAuthStore:auth}=await import('../src/store/useAuthStore')
const {useInstitutionStore:institutions}=await import('../src/store/useInstitutionStore')
const {usePlatformStore:platform}=await import('../src/store/usePlatformStore')
const a='11111111-1111-4111-8111-111111111111',b='22222222-2222-4222-8222-222222222222',id='33333333-3333-4333-8333-333333333333'
const row={event_id:id,library_id:a,scope:'LIBRARY',visibility:'LIBRARY_MEMBERS',title:'Library gathering',category:'OTHER',summary:'A member gathering',description:'Full details.',start_at:'2026-12-01T12:00:00Z',end_at:null,location:'Reading room',featured:false,status:'PUBLISHED',related_work_ids:[],related_books:[],created_at:'2026-10-10T12:00:00Z',updated_at:'2026-10-10T12:00:00Z',published_at:'2026-10-10T12:00:00Z'}
const notice={notification_id:id,type:'BORROW_REQUEST_APPROVED',title:'Borrow request approved',message:'Your request is approved.',created_at:'2026-10-10T12:00:00Z',read_at:null,scope:'LIBRARY',library_id:b,library_name:'Library B',audience:'PATRON',action_route:`/libraries/${b}/my-library`,action_unavailable:null} as const
const original=globalThis.fetch
let calls:{path:string;method:string;body:any}[]=[]
let notices:any[]=[];let resultRow:any=row
beforeEach(()=>{calls=[];notices=[];resultRow={...row};localStorage.clear();localStorage.setItem('luminar_token','session');auth.setState({token:'session',isAuthenticated:true,user:{user_id:1,name:'QA',email:'qa@example.com',role:'GENERAL_USER'} as any});institutions.setState({session:'session',libraries:[{library_id:a,name:'Library A',library_type:'PUBLIC_LIBRARY',access_mode:'PUBLIC',membership:{role:'GENERAL_USER',status:'ACTIVE'}} as any],loading:false,error:''});platform.setState({session:'session',roles:[],loading:false,error:''})
 globalThis.fetch=async(input,options)=>{const path=String(input),method=options?.method||'GET',body=options?.body?JSON.parse(String(options.body)):null;calls.push({path,method,body})
  if(path.includes('/notifications/'))return Response.json(notices[0]||notice)
  if(path.includes('/notifications?'))return Response.json({notifications:notices,count:notices.length,unread_count:notices.filter(n=>!n.read_at).length})
  if(/\/events\/[0-9a-f-]+(?:\/|$)/.test(path))return Response.json(resultRow)
  if(method==='POST' && path.endsWith('/events'))return Response.json({...resultRow,status:'DRAFT'}, {status:201})
  if(path.includes('/events'))return Response.json({events:[resultRow],count:1,page:1,page_size:12,has_more:false})
  return Response.json({roles:[],libraries:[],results:[]})
 }})
afterEach(()=>{cleanup();globalThis.fetch=original})
function Location(){const value=useLocation();return <output data-testid="location">{value.pathname+value.search}</output>}
function mount(node:React.ReactNode,path='/',route='*'){return render(<MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={node}/></Routes><Location/></MemoryRouter>)}

test('test_patron_events_header_context',()=>{mount(<Header/>,`/libraries/${a}/catalogue`);assert.equal(screen.getByRole('link',{name:'Events'}).getAttribute('href'),`/libraries/${a}/events`)})
test('test_global_events_outside_library',()=>{mount(<Header/>,'/catalog');assert.equal(screen.getByRole('link',{name:'Events'}).getAttribute('href'),'/events')})
test('test_staff_events_header_context',()=>{mount(<Header/>,`/staff/libraries/${a}/inventory`);assert.equal(screen.getByRole('link',{name:'Events'}).getAttribute('href'),`/staff/libraries/${a}/events`)})
test('test_staff_events_route',()=>{const app=readFileSync(new URL('../src/App.tsx',import.meta.url),'utf8');assert.match(app,/<Route path="events" element={<ManageEventsPage/);assert.match(app,/<Route path="events\/new" element={<EventEditorPage/);assert.match(app,/<Route path="events\/:eventId" element={<EventDetailPage staff/);assert.match(readFileSync(new URL('../src/components/LibraryShells.tsx',import.meta.url),'utf8'),/label: 'Events', path: 'events'/)})
test('test_patron_events_fetch_current_library_and_no_controls',async()=>{mount(<EventsPage/>,`/libraries/${a}/events`,'/libraries/:libraryId/events');await screen.findByText('Library gathering');assert.ok(calls.some(c=>c.path===`/api/libraries/${a}/events`));assert.equal(screen.queryByRole('link',{name:'Create Event'}),null);assert.equal(screen.getByRole('link',{name:'View event →'}).getAttribute('href'),`/libraries/${a}/events/${id}`)})
test('test_tenant_cancelled_detail_retains_reason',async()=>{resultRow={...row,status:'CANCELLED',cancellation_reason:'Venue closed.'};mount(<EventDetailPage/>,`/libraries/${a}/events/${id}`,'/libraries/:libraryId/events/:eventId');await screen.findByText('Venue closed.');assert.equal(screen.getByRole('link',{name:'← All events'}).getAttribute('href'),`/libraries/${a}/events`)})
test('test_staff_event_cancel_requires_reason',async()=>{mount(<ManageEventsPage/>,`/staff/libraries/${a}/events`,'/staff/libraries/:libraryId/events');await screen.findByText('Library gathering');fireEvent.click(screen.getByRole('button',{name:'Cancel Event'}));const dialog=screen.getByRole('dialog');const confirm=within(dialog).getByRole('button',{name:'Cancel event'});assert.equal(confirm.hasAttribute('disabled'),true);fireEvent.change(within(dialog).getByLabelText('Cancellation reason'),{target:{value:'Venue closed.'}});fireEvent.click(confirm);await waitFor(()=>assert.ok(calls.some(c=>c.path.endsWith('/cancel')&&c.body.reason==='Venue closed.')))})
test('test_staff_event_tabs_scope_server_query',async()=>{mount(<ManageEventsPage/>,`/staff/libraries/${a}/events`,'/staff/libraries/:libraryId/events');await screen.findByText('Library gathering');fireEvent.click(screen.getByRole('button',{name:'Draft'}));await waitFor(()=>assert.ok(calls.some(c=>c.path.includes(`/libraries/${a}/staff/events?status=DRAFT`))))})
test('test_tenant_event_editor_member_default',async()=>{mount(<EventEditorPage/>,`/staff/libraries/${a}/events/new`,'/staff/libraries/:libraryId/events/new');const visibility=await screen.findByRole('combobox',{name:'Event visibility'});assert.equal((visibility as HTMLSelectElement).value,'LIBRARY_MEMBERS');assert.ok(screen.getByRole('link',{name:'← Manage Events'}).getAttribute('href')?.includes(a))})
test('test_private_event_editor_has_no_public_choice',async()=>{institutions.setState({libraries:[{library_id:a,name:'Private',library_type:'PRIVATE_INSTITUTION',access_mode:'PRIVATE_CODE',membership:{role:'ADMIN',status:'ACTIVE'}} as any]});mount(<EventEditorPage/>,`/staff/libraries/${a}/events/new`,'/staff/libraries/:libraryId/events/new');const visibility=await screen.findByRole('combobox',{name:'Event visibility'});assert.equal(within(visibility).queryByRole('option',{name:'Public'}),null)})
test('test_notification_patron_route',()=>assert.equal(resolve(notice),`/libraries/${b}/my-library`))
test('test_notification_staff_route',()=>assert.equal(resolve({...notice,type:'BORROW_REQUEST_CREATED',audience:'STAFF',action_route:`/staff/libraries/${b}/circulation`}),`/staff/libraries/${b}/circulation`))
test('test_notification_uses_own_library_not_active_context',()=>{assert.equal(resolve(notice),`/libraries/${b}/my-library`);assert.equal(resolve({...notice,action_route:`/libraries/${a}/my-library`}),null)})
test('test_notification_rejects_global_legacy_external_or_unavailable',()=>{for(const variant of [{scope:'GLOBAL'},{scope:'LEGACY_AMBIGUOUS'},{library_id:'LIB001'},{action_route:'https://example.com'},{action_unavailable:'Library unavailable'},{audience:'STAFF'}])assert.equal(resolve({...notice,...variant} as any),null)})
test('test_notification_bell_library_label_and_read',async()=>{notices=[notice];mount(<NotificationCenter/>);await waitFor(()=>assert.ok(screen.getByRole('button',{name:'Notifications, 1 unread'})));fireEvent.click(screen.getByRole('button',{name:'Notifications, 1 unread'}));await screen.findByText('Library B');fireEvent.click(screen.getByRole('button',{name:'Mark as read'}));await waitFor(()=>assert.ok(calls.some(c=>c.path.endsWith('/read')&&c.method==='PATCH')))})
test('test_notification_click_routes_by_source_library',async()=>{notices=[notice];mount(<NotificationCenter/>,`/libraries/${a}/events`);await waitFor(()=>assert.ok(screen.getByRole('button',{name:'Notifications, 1 unread'})));fireEvent.click(screen.getByRole('button',{name:'Notifications, 1 unread'}));fireEvent.click(await screen.findByRole('button',{name:'Open Borrow request approved in Library B'}));await waitFor(()=>assert.equal(screen.getByTestId('location').textContent,`/libraries/${b}/my-library`));assert.ok(calls.some(c=>c.path.endsWith('/action')))})
test('test_notification_fresh_revocation_does_not_navigate',async()=>{notices=[notice];mount(<NotificationCenter/>,`/libraries/${a}/events`);await waitFor(()=>assert.ok(screen.getByRole('button',{name:'Notifications, 1 unread'})));fireEvent.click(screen.getByRole('button',{name:'Notifications, 1 unread'}));const open=await screen.findByRole('button',{name:'Open Borrow request approved in Library B'});notices=[{...notice,action_unavailable:'Library unavailable',action_route:null}];fireEvent.click(open);await screen.findByText('Library unavailable');assert.equal(screen.getByTestId('location').textContent,`/libraries/${a}/events`)})
test('test_bell_escape_restores_focus',async()=>{mount(<NotificationCenter/>);const bell=screen.getByRole('button',{name:'Notifications'});fireEvent.click(bell);await screen.findByRole('region',{name:'Notification Center'});fireEvent.keyDown(document,{key:'Escape'});assert.equal(screen.queryByRole('region',{name:'Notification Center'}),null);assert.equal(document.activeElement,bell)})
test('test_event_ui_responsive_shared_rules',()=>{const css=readFileSync(new URL('../src/pages/Events.css',import.meta.url),'utf8');assert.match(css,/@media/);assert.match(css,/min-width:0/);assert.match(css,/flex-wrap:wrap/);assert.match(css,/focus-visible/)})
test('test_notification_ui_responsive_shared_rules',()=>{const css=readFileSync(new URL('../src/components/Notifications.css',import.meta.url),'utf8');assert.match(css,/max-width:calc\(100vw - 32px\)/);assert.match(css,/100dvh/);assert.match(css,/min-height:44px/);assert.match(css,/focus-visible/)})
test('test_tenant_event_transport_does_not_use_platform_authority',async()=>{await eventApiFor(a).create({...row});await eventApiFor(a).action(id,'publish');assert.ok(calls.every(c=>c.path.startsWith(`/api/libraries/${a}/`)));assert.ok(!calls.some(c=>c.path.includes('/platform/')))})
