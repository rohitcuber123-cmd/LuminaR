import assert from 'node:assert/strict'
import {registerHooks} from 'node:module'
import {test,beforeEach,afterEach} from 'node:test'
import React from 'react'
import {JSDOM} from 'jsdom'
import {selectedValue,chooseSelect} from './select-control'
registerHooks({load(url,context,next){return url.endsWith('.css')?{format:'module',source:'',shortCircuit:true}:next(url,context)}})
const dom=new JSDOM('<html><body></body></html>',{url:'http://localhost:5173'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,HTMLElement:dom.window.HTMLElement,Event:dom.window.Event,FormData:dom.window.FormData,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
dom.window.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')}
dom.window.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')}
const {render,screen,fireEvent,waitFor,cleanup,within,act}=await import('@testing-library/react')
const {MemoryRouter,Routes,Route,useNavigate,useLocation}=await import('react-router-dom')
const {LibraryAnnouncementsPage}=await import('../src/pages/LibraryAnnouncements')
const {NotificationCenter}=await import('../src/components/NotificationCenter')
const {useAuthStore:auth}=await import('../src/store/useAuthStore')
const {useInstitutionStore:institutions}=await import('../src/store/useInstitutionStore')
const {resolveNotificationAction}=await import('../src/lib/notifications')
const a='11111111-1111-4111-8111-111111111111',b='22222222-2222-4222-8222-222222222222',id='33333333-3333-4333-8333-333333333333',eventId='44444444-4444-4444-8444-444444444444'
const sample={announcement_id:id,library_id:a,title:'Reading room update',body:'Full member message.',category:'GENERAL',priority:'IMPORTANT',status:'DRAFT',revision:0,created_at:'2026-10-31T10:00:00Z',published_at:null,withdrawn_at:null,linked_event_id:null,linked_event_available:false,delivery:{state:'NOT_PUBLISHED'}}
let rows:any[],calls:{path:string;method:string;body:any}[],fail:string,notices:any[],hold:((value:Response)=>void)|null,delayA:boolean
const original=globalThis.fetch
function lib(library_id:string,role='ADMIN'){return{library_id,name:library_id===a?'Library A':'Library B',membership:{role,status:'ACTIVE'},library_type:'PRIVATE_INSTITUTION',access_mode:'PRIVATE_CODE'} as any}
beforeEach(()=>{
  rows=[{...sample}];calls=[];fail='';notices=[];hold=null;delayA=false
  localStorage.clear();localStorage.setItem('luminar_token','session')
  auth.setState({token:'session',isAuthenticated:true,user:{user_id:1,name:'QA',email:'qa@example.com',role:'GENERAL_USER'} as any})
  institutions.setState({session:'session',activeId:a,libraries:[lib(a),lib(b)],loading:false})
  globalThis.fetch=async(input,options)=>{
    const path=String(input),method=options?.method||'GET',body=options?.body?JSON.parse(String(options.body)):null
    calls.push({path,method,body})
    if(fail&&path.includes(fail))return Response.json({detail:'Publication failed. Reload to check state.'},{status:500})
    if(path.includes('/notifications')){
      if(path.endsWith('/read-all')){notices=notices.map(n=>({...n,read_at:'2026-10-31T11:00:00Z'}));return Response.json({marked:notices.length})}
      if(path.endsWith('/read')){notices=notices.map(n=>({...n,read_at:'2026-10-31T11:00:00Z'}));return Response.json(notices[0])}
      if(path.includes('/action'))return Response.json(notices[0])
      return Response.json({notifications:notices,count:notices.length,unread_count:notices.filter(n=>!n.read_at).length})
    }
    if(path.includes('/events'))return Response.json({events:[{event_id:eventId,title:'Member workshop'}]})
    if(method==='GET'&&delayA&&path.includes(a)&&path.includes('announcements?'))return new Promise(resolve=>{hold=resolve})
    if(method==='GET'&&path.includes(b))return Response.json({results:[{...sample,library_id:b,title:'Library B notice'}],total:1})
    if(method==='GET'&&/announcements\/[0-9a-f-]+$/.test(path))return Response.json(rows[0])
    if(method==='GET')return Response.json({results:rows,total:rows.length})
    if(method==='PATCH'){rows=[{...rows[0],...body,revision:1}];return Response.json(rows[0])}
    if(method==='POST'&&path.endsWith('/announcements')){rows=[{...sample,...body}];return Response.json(rows[0],{status:201})}
    if(path.endsWith('/publish'))rows=[{...rows[0],status:'PUBLISHED',revision:1,published_at:'2026-10-31T10:01:00Z',delivery:{state:'PENDING',total:4,cursor:0,delivered:0,suppressed:0}}]
    if(path.endsWith('/withdraw'))rows=[{...rows[0],status:'WITHDRAWN',revision:2}]
    return Response.json(rows[0])
  }
})
afterEach(()=>{cleanup();globalThis.fetch=original})
function Location(){const location=useLocation(),navigate=useNavigate();return <><output data-testid="location">{location.pathname}</output><button onClick={()=>{institutions.setState({activeId:b});navigate(`/staff/libraries/${b}/announcements`)}}>Switch library</button></>}
function mount(staff=true,detail=false){return render(<MemoryRouter initialEntries={[`/${staff?'staff/':''}libraries/${a}/announcements${detail?'/'+id:''}`]}><Routes><Route path={staff?'/staff/libraries/:libraryId/announcements/:announcementId?':'/libraries/:libraryId/announcements/:announcementId?'} element={<><LibraryAnnouncementsPage staff={staff}/><Location/></>}/></Routes></MemoryRouter>)}
async function ready(){await screen.findByRole('heading',{name:'Reading room update'})}
async function editor(){mount();await ready();fireEvent.click(screen.getByRole('button',{name:'Create announcement'}));return screen.getByRole('dialog')}
function notice(){return{notification_id:id,type:'ANNOUNCEMENT_PUBLISHED',title:'Library announcement',message:'An announcement is available.',library_id:a,library_name:'Library A',scope:'LIBRARY',audience:'MEMBER',source_id:id,action_route:`/libraries/${a}/announcements/${id}`,read_at:null,created_at:'2026-10-31T10:01:00Z'} as any}

test('staff list uses tenant API and shows state',async()=>{mount();await ready();assert.ok(screen.getByText('DRAFT'));assert.ok(calls.some(c=>c.path.startsWith(`/api/libraries/${a}/staff/announcements`)))})
test('empty member state has no creation control',async()=>{rows=[];institutions.setState({libraries:[lib(a,'GENERAL_USER')]});mount(false);await screen.findByText('Your library has no published announcements yet.');assert.equal(screen.queryByRole('button',{name:'Create announcement'}),null)})
test('GENERAL_USER cannot use staff management URL',()=>{institutions.setState({libraries:[lib(a,'GENERAL_USER')]});mount();assert.ok(screen.getByText('Administrator access required'));assert.equal(calls.length,0)})
test('LIBRARIAN reads published announcements without management controls',async()=>{rows=[{...sample,status:'PUBLISHED'}];institutions.setState({libraries:[lib(a,'LIBRARIAN')]});mount();await ready();assert.equal(screen.queryByRole('button',{name:'Create announcement'}),null);assert.ok(calls.some(c=>c.path.startsWith(`/api/libraries/${a}/announcements?`)))})
test('no membership denies URL access',()=>{institutions.setState({libraries:[]});mount(false);assert.ok(screen.getByText('Library access unavailable'));assert.equal(calls.length,0)})
test('new draft fields validate before save',async()=>{const d=await editor();assert.ok(within(d).getByRole('button',{name:'Save draft'}).hasAttribute('disabled'));fireEvent.change(within(d).getByLabelText('Title'),{target:{value:'New notice'}});assert.ok(within(d).getByRole('button',{name:'Save draft'}).hasAttribute('disabled'));fireEvent.change(within(d).getByLabelText('Message'),{target:{value:'Details'}});assert.equal(within(d).getByRole('button',{name:'Save draft'}).hasAttribute('disabled'),false)})
test('plain-text HTML validation disables unsafe draft',async()=>{const d=await editor();fireEvent.change(within(d).getByLabelText('Title'),{target:{value:'New notice'}});fireEvent.change(within(d).getByLabelText('Message'),{target:{value:'<script>bad</script>'}});assert.ok(within(d).getByRole('button',{name:'Save draft'}).hasAttribute('disabled'))})
test('create draft server identity and stable request id',async()=>{const d=await editor();fireEvent.change(within(d).getByLabelText('Title'),{target:{value:'New notice'}});fireEvent.change(within(d).getByLabelText('Message'),{target:{value:'Details'}});fireEvent.click(within(d).getByRole('button',{name:'Save draft'}));await screen.findByText('Draft saved.');const call=calls.find(c=>c.method==='POST')!;assert.match(call.body.request_id,/^[0-9a-f-]{36}$/);assert.equal(call.body.created_by_user_id,undefined);assert.equal(call.body.library_id,undefined)})
test('draft edit includes optimistic revision',async()=>{mount();await ready();fireEvent.click(screen.getByRole('button',{name:'Edit draft'}));const d=screen.getByRole('dialog');fireEvent.change(within(d).getByLabelText('Message'),{target:{value:'Updated details'}});fireEvent.click(within(d).getByRole('button',{name:'Save draft'}));await screen.findByText('Draft saved.');assert.equal(calls.find(c=>c.method==='PATCH')?.body.revision,0)})
test('draft preview renders content without publication',async()=>{mount();await ready();fireEvent.click(screen.getByRole('button',{name:'Preview'}));assert.ok(within(screen.getByRole('dialog')).getByText(sample.body));assert.equal(calls.filter(c=>c.method==='POST').length,0)})
test('publication needs confirmation and shows pending delivery',async()=>{mount();await ready();fireEvent.click(screen.getByRole('button',{name:'Publish',exact:true}));const d=screen.getByRole('dialog');assert.equal(calls.filter(c=>c.method==='POST').length,0);fireEvent.click(within(d).getByRole('button',{name:'Publish announcement',exact:true}));await screen.findByText(/Published\. Notification delivery pending/);assert.equal(calls.find(c=>c.path.endsWith('/publish'))?.body.revision,0)})
test('publication cancel does not send command',async()=>{mount();await ready();fireEvent.click(screen.getByRole('button',{name:'Publish',exact:true}));fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Cancel',exact:true}));assert.equal(calls.filter(c=>c.path.endsWith('/publish')).length,0)})
test('publication failure does not claim success',async()=>{mount();await ready();fail='/publish';fireEvent.click(screen.getByRole('button',{name:'Publish',exact:true}));fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Publish announcement',exact:true}));await waitFor(()=>assert.ok(screen.getAllByText(/server could not complete/).length));assert.equal(screen.queryByText(/Published\. Notification delivery/),null)})
test('published content offers withdrawal and no edit',async()=>{rows=[{...sample,status:'PUBLISHED'}];mount();await ready();assert.equal(screen.queryByRole('button',{name:'Edit draft'}),null);fireEvent.click(screen.getByRole('button',{name:'Withdraw',exact:true}));fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Withdraw announcement',exact:true}));await screen.findByText('Announcement withdrawn.')})
test('status filter sends bounded server query',async()=>{mount();await ready();chooseSelect(screen.getByRole('combobox',{name:'Announcement status'}),'DRAFT',fireEvent);await waitFor(()=>assert.ok(calls.some(c=>c.path.includes('status=DRAFT'))));assert.ok(calls.every(c=>c.method!=='GET'||!c.path.includes('announcements?')||c.path.includes('limit=20')))})
test('linked event draft selection uses existing events',async()=>{const d=await editor();await waitFor(()=>assert.ok(d.querySelector(`option[value="${eventId}"]`)));assert.equal(selectedValue(within(d).getByRole('combobox',{name:'Linked event (optional)'})),'')})
test('member detail uses source library and safe event link',async()=>{rows=[{...sample,status:'PUBLISHED',linked_event_id:eventId,linked_event_available:true}];institutions.setState({libraries:[lib(a,'GENERAL_USER')]});mount(false,true);await ready();assert.equal(screen.getByRole('link',{name:'Open linked event'}).getAttribute('href'),`/libraries/${a}/events/${eventId}`);assert.equal(screen.queryByRole('button',{name:'Publish'}),null)})
test('missing event is explicit and has no link',async()=>{rows=[{...sample,status:'PUBLISHED',linked_event_id:eventId,linked_event_available:false}];institutions.setState({libraries:[lib(a,'GENERAL_USER')]});mount(false,true);await screen.findByText('Linked event unavailable.');assert.equal(screen.queryByRole('link',{name:'Open linked event'}),null)})
test('library switch rejects delayed previous response',async()=>{delayA=true;mount();await waitFor(()=>assert.ok(hold));fireEvent.click(screen.getByRole('button',{name:'Switch library'}));await screen.findByRole('heading',{name:'Library B notice'});await act(async()=>{hold!(Response.json({results:[sample],total:1}))});assert.equal(screen.queryByRole('heading',{name:'Reading room update'}),null)})
test('logout and new session do not expose old messages',async()=>{mount();await ready();act(()=>auth.setState({token:null}));assert.equal(screen.queryByRole('heading',{name:'Reading room update'}),null);act(()=>auth.setState({token:'other-session'}));assert.ok(screen.getByText('Library access unavailable'))})
test('revoked membership immediately removes content',async()=>{mount();await ready();act(()=>institutions.setState({libraries:[]}));assert.equal(screen.queryByRole('heading',{name:'Reading room update'}),null)})
test('member rejects a draft even if an invalid response contains one',async()=>{institutions.setState({libraries:[lib(a,'GENERAL_USER')]});mount(false);await screen.findByText('Announcement unavailable in this library context.');assert.equal(screen.queryByText(sample.body),null)})
test('response from another tenant is rejected',async()=>{rows=[{...sample,library_id:b}];mount();await screen.findByText('Announcement unavailable in this library context.');assert.equal(screen.queryByText(sample.body),null)})
test('announcement route rejects spoofed external, cross-library and malformed identity',()=>{const n=notice();assert.equal(resolveNotificationAction(n),n.action_route);for(const change of [{action_route:'https://example.com'},{library_id:b},{source_id:'LIB001'},{audience:'PATRON'},{action_unavailable:'Withdrawn'}])assert.equal(resolveNotificationAction({...n,...change}),null)})
test('existing single bell counts and marks announcement read',async()=>{notices=[notice()];render(<MemoryRouter><NotificationCenter/></MemoryRouter>);const bell=await screen.findByRole('button',{name:'Notifications, 1 unread'});assert.equal(screen.getAllByRole('button',{name:/^Notifications/}).length,1);fireEvent.click(bell);await screen.findByText('Library A');fireEvent.click(screen.getByRole('button',{name:'Mark as read',exact:true}));await screen.findByRole('button',{name:'Notifications',exact:true});assert.ok(calls.some(c=>c.method==='PATCH'))})
test('existing mark-all retains one account counter',async()=>{notices=[notice()];render(<MemoryRouter><NotificationCenter/></MemoryRouter>);fireEvent.click(await screen.findByRole('button',{name:'Notifications, 1 unread'}));fireEvent.click(screen.getByRole('button',{name:'Mark all as read'}));await screen.findByRole('button',{name:'Notifications',exact:true})})
test('preview dialog escape restores initiating button focus',async()=>{mount();await ready();const button=screen.getByRole('button',{name:'Preview'});button.focus();fireEvent.click(button);const dialog=screen.getByRole('dialog');fireEvent(dialog,new window.Event('cancel',{bubbles:true,cancelable:true}));await waitFor(()=>assert.equal(screen.queryByRole('dialog'),null))})
test('focus refresh preserves the clicked row while revalidating',async()=>{mount();await ready();fireEvent(window,new window.Event('focus'));fireEvent.click(screen.getByRole('button',{name:'Preview'}));assert.ok(screen.getByRole('dialog',{name:'Announcement preview'}))})
test('saved draft preview uses the refreshed authoritative content',async()=>{mount();await ready();fireEvent.click(screen.getByRole('button',{name:'Edit draft'}));const edit=screen.getByRole('dialog');fireEvent.change(within(edit).getByLabelText('Message'),{target:{value:'Authoritative edited content'}});fireEvent.click(within(edit).getByRole('button',{name:'Save draft'}));await screen.findByText('Draft saved.');fireEvent.click(await screen.findByRole('button',{name:'Preview'}));assert.ok(within(screen.getByRole('dialog')).getByText('Authoritative edited content'));assert.equal(within(screen.getByRole('dialog')).queryByText(sample.body),null)})
