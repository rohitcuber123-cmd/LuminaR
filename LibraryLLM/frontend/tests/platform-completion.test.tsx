import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {registerHooks} from 'node:module'
import {test,beforeEach,afterEach} from 'node:test'
import React from 'react'
import {JSDOM} from 'jsdom'
registerHooks({load(url,ctx,next){return url.endsWith('.css')?{format:'module',source:'',shortCircuit:true}:next(url,ctx)}})
const dom=new JSDOM('<!doctype html><html><body></body></html>',{url:'http://localhost:5173'})
Object.assign(globalThis,{window:dom.window,document:dom.window.document,localStorage:dom.window.localStorage,sessionStorage:dom.window.sessionStorage,HTMLElement:dom.window.HTMLElement,Event:dom.window.Event,FormData:dom.window.FormData,IS_REACT_ACT_ENVIRONMENT:true})
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true})
dom.window.HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')}
dom.window.HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')}
const {render,screen,fireEvent,waitFor,cleanup,act}=await import('@testing-library/react')
const {MemoryRouter}=await import('react-router-dom')
const {resolveProductContext:resolve,resolveProductHomeDestination:home,withProductContext:withContext}=await import('../src/lib/productContext')
const {Header}=await import('../src/components/Header')
const {AccountMenu}=await import('../src/components/AccountMenu')
const {BookCover}=await import('../src/components/BookCover')
const {BookCard}=await import('../src/components/BookCard')
const {PlatformLibrariesPage,PlatformLibraryDetailPage}=await import('../src/pages/PlatformLibraries')
const {PlatformRoute}=await import('../src/components/ManagementRoutes')
const {useAuthStore:auth}=await import('../src/store/useAuthStore')
const {usePlatformStore:platform}=await import('../src/store/usePlatformStore')
const {useInstitutionStore:institutions}=await import('../src/store/useInstitutionStore')
const {globalDisplayBook}=await import('../src/lib/libraryCatalogue')
const a='11111111-1111-4111-8111-111111111111',b='22222222-2222-4222-8222-222222222222'
const original=globalThis.fetch
let calls:{path:string;method:string;body:any}[]=[]
const row={library_id:a,name:'TEST',slug:'test',status:'ACTIVE',library_type:'PUBLIC_LIBRARY',access_mode:'PUBLIC',owner:{name:'Owner',email:'owner@example.com',user_id:1},created_at:new Date().toISOString(),updated_at:new Date().toISOString(),counts:{members:1,staff:1,local_books:150}}
beforeEach(()=>{localStorage.clear();calls=[];localStorage.setItem('luminar_token','session');auth.setState({token:'session',isAuthenticated:true,user:{user_id:1,email:'qa@example.com',name:'QA',role:'GENERAL_USER'} as any})
 platform.setState({session:'session',roles:[],loading:false,error:''});institutions.setState({session:'session',libraries:[],loading:false,error:''})
 globalThis.fetch=async(input,options)=>{const path=String(input);calls.push({path,method:options?.method||'GET',body:options?.body?JSON.parse(String(options.body)):null})
  if(path.includes('/audit'))return Response.json({results:[],total:0,limit:20,offset:0})
  if(path.startsWith('/api/platform/libraries/'))return Response.json({library:row,cutover:{circulation:'CANONICAL',reservations:'CANONICAL',fees:'CANONICAL'},tenant_internals_require_membership:true,audit:{results:[],total:0}})
  if(path.startsWith('/api/platform/libraries'))return Response.json({results:[row],total:51,has_more:true})
  if(path==='/api/me/platform-access')return Response.json({roles:[]})
  return Response.json({results:[],items:[],libraries:[],notifications:[]})
 }})
afterEach(()=>{cleanup();globalThis.fetch=original})
function mount(node:React.ReactNode,path='/'){return render(<MemoryRouter initialEntries={[path]}>{node}</MemoryRouter>)}
for(const [name,path,role,expected] of [
 ['test_staff_logo_returns_current_staff_workspace',`/staff/libraries/${a}/inventory?patron_library=${b}`,'ADMIN',`/staff/libraries/${a}`],
 ['test_owner_logo_does_not_open_patron_workspace',`/libraries/${a}`,'ADMIN',`/staff/libraries/${a}`],
 ['test_librarian_logo_does_not_open_patron_workspace',`/libraries/${a}`,'LIBRARIAN',`/staff/libraries/${a}`],
 ['test_patron_logo_returns_current_patron_library',`/libraries/${a}/books/id`,'GENERAL_USER',`/libraries/${a}`],
 ['test_global_logo_returns_root','/catalog','ADMIN','/'],
 ['test_staff_personal_return_context',`/reading-list?staff_library=${a}`,'ADMIN',`/staff/libraries/${a}`],
 ['test_patron_personal_return_context',`/reading-list?patron_library=${a}`,'GENERAL_USER',`/libraries/${a}`],
 ['test_platform_home_is_overview',`/platform/libraries/${a}?patron_library=${b}`,'ADMIN','/platform'],
] as const)test(name,()=>{
 institutions.setState({libraries:[{library_id:a,name:'TEST',membership:{role,status:'ACTIVE'}} as any]})
 mount(<Header/>,path);assert.equal(screen.getByRole('link',{name:'LuminaR home'}).getAttribute('href'),expected)
})
test('test_explicit_global_context_clears_library_return',()=>{assert.equal(home(resolve('/catalog')), '/');assert.equal(withContext('/reading-list?staff_library='+a,{kind:'GLOBAL',libraryId:null}),'/reading-list')})
test('test_canonical_auth_routes_clear_library_return_context',()=>{for(const path of ['/login','/signup','/staff/login','/verify-otp','/account/setup','/staff/setup']){assert.equal(home(resolve(path,`?staff_library=${a}`)),'/');assert.equal(withContext(path,{kind:'STAFF_LIBRARY',libraryId:a}),path)}})
test('test_logout_clears_return_context',async()=>{mount(<AccountMenu/>,`/reading-list?staff_library=${a}`);fireEvent.click(screen.getByRole('button',{name:/Open account menu/}));fireEvent.click(screen.getByRole('menuitem',{name:'Sign Out'}));await waitFor(()=>assert.equal(auth.getState().token,null));assert.equal(home(resolve('/login',`?staff_library=${a}`)),'/')})
test('test_account_switch_clears_return_context',()=>{const app=readFileSync(new URL('../src/App.tsx',import.meta.url),'utf8');assert.match(app,/previousSession.current !== sessionToken/);assert.match(app,/kind:'GLOBAL',libraryId:null/);assert.equal(home(resolve('/account/profile','')), '/')})
test('test_library_switch_updates_return_context',()=>{assert.equal(home(resolve(`/staff/libraries/${b}/inventory`,`?staff_library=${a}`)),`/staff/libraries/${b}`)})
test('test_no_first_membership_context_guess',()=>{localStorage.setItem('luminar_patron_library',a);institutions.setState({libraries:[{library_id:a,membership:{role:'ADMIN',status:'ACTIVE'}} as any]});mount(<Header/>,'/catalog');assert.equal(screen.getByRole('link',{name:'LuminaR home'}).getAttribute('href'),'/')})
test('test_ambiguous_return_context_fails_to_global',()=>{assert.equal(home(resolve('/reading-list',`?staff_library=${a}&patron_library=${b}`)),'/')})
test('test_old_global_navigation_context_audit',()=>{for(const file of ['AIChatWidget','RelatedBookCard','Hero','ForYou','NewArrivals','PopularBooks','CategoryExplorer','AlsoLikeTicker'])assert.match(readFileSync(new URL(`../src/components/${file}.tsx`,import.meta.url),'utf8'),/personalPath\(/)})
for(const [name,title,author] of [
 ['test_book_cover_long_title','Logical aspects of computational linguistics','Long Author'],
 ['test_book_cover_short_title','The Tower',''],['test_book_cover_multiple_authors','Managing God’s Money — The Basics, Workbook','Author One; Author Two'],
 ['test_book_cover_missing_author','Money 1988',undefined],['test_book_cover_local_only','The Glasgow novel, 1870-1970','Author'],['test_book_cover_linked_local','Linked record','Two Authors'],
] as const)test(name,()=>{render(<BookCover title={title} author={author} paletteIndex={1} variant="ring"/>);assert.ok(screen.getByRole('img',{name:new RegExp(title.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'))}));assert.equal(document.querySelector('.book-cover-title')?.getAttribute('title'),title);assert.equal(document.querySelectorAll('.book-cover-author').length,author?1:0)})
test('test_book_cover_shared_component',()=>{assert.match(readFileSync(new URL('../src/components/DiscoveryBookFrame.tsx',import.meta.url),'utf8'),/BookCoverArt/);assert.match(readFileSync(new URL('../src/components/BookCoverArt.tsx',import.meta.url),'utf8'),/BookCover/)})
test('test_book_cover_no_duplicate_title_backplate',()=>{render(<BookCover title="Money 1988" author="Two Authors" paletteIndex={0} variant="stripe"/>);assert.equal(document.querySelectorAll('.book-cover-text-scrim').length,0);for(const sel of ['.book-cover-title','.book-cover-author','.book-cover-brand'])assert.equal((document.querySelector(sel) as HTMLElement).style.backgroundColor,'')})
test('test_book_cover_text_layer_above_decoration',()=>{render(<BookCover title="The Tower" paletteIndex={1} variant="ring"/>);const root=document.querySelector('.book-cover-art')!;assert.ok(root.lastElementChild!.classList.contains('book-cover-content'))})
for(const owned of [false,true])test(owned?'test_library_card_action_layout':'test_recommendation_card_action_layout',()=>{const record=globalDisplayBook({book_id:1,work_id:'OL1W',title:'A shared title',authors:'Author',subjects:'Subject'} as any,'');const book={...record,...(owned?{source:'LIBRARY',library_id:a,library_book_id:b,display_id:b,global_work_id:null,owned_by_current_library:true,requestable_count:1,circulation_status:'CIRCULATING',actions:{request:true}}:{})} as any;mount(<BookCard book={book} rail/>);assert.ok(screen.getByRole('article',{name:'A shared title'}));assert.equal(screen.getByRole('button',{name:'Add to Reading List'}).closest('.book-personal-actions')!=null,true)})
test('test_mobile_book_card_no_overflow',()=>{const css=readFileSync(new URL('../src/styles/product.css',import.meta.url),'utf8');assert.match(css,/\.book-personal-actions \{ display:flex;flex-wrap:wrap/);assert.match(css,/\.product-book-card \{ min-width:0/);assert.match(css,/\.assistant-launcher.is-compact/);assert.match(css,/scroll-snap-type:x proximity/)})
test('test_platform_avatar_menu_entry',()=>{platform.setState({roles:['PLATFORM_ADMIN']});mount(<AccountMenu/>);fireEvent.click(screen.getByRole('button',{name:/Open account menu/}));assert.ok(screen.getByRole('group',{name:'Platform'}).contains(screen.getByRole('menuitem',{name:'Platform Administration'})));assert.equal(screen.getByRole('group',{name:'Staff workspaces'}).contains(screen.getByRole('menuitem',{name:'Platform Administration'})),false)})
test('test_platform_libraries_requires_platform_admin',()=>{mount(<PlatformRoute><PlatformLibrariesPage/></PlatformRoute>,'/platform/libraries');assert.ok(screen.getByText('Platform access required'));assert.equal(calls.some(c=>c.path.includes('/platform/libraries')),false)})
test('test_platform_admin_search_filters_and_pagination',async()=>{mount(<PlatformLibrariesPage/>,'/platform/libraries');await screen.findByRole('link',{name:'View TEST'});fireEvent.change(screen.getByRole('searchbox'),{target:{value:'TEST'}});fireEvent.click(screen.getByRole('button',{name:'Search'}));await waitFor(()=>assert.ok(calls.some(c=>c.path.includes('q=TEST'))));fireEvent.change(screen.getByRole('combobox',{name:'Library status'}),{target:{value:'SUSPENDED'}});await waitFor(()=>assert.ok(calls.some(c=>c.path.includes('status=SUSPENDED'))));fireEvent.change(screen.getByRole('combobox',{name:'Library type'}),{target:{value:'PRIVATE_INSTITUTION'}});await waitFor(()=>assert.ok(calls.some(c=>c.path.includes('library_type=PRIVATE_INSTITUTION'))));await screen.findByRole('link',{name:'View TEST'});fireEvent.click(screen.getByRole('button',{name:'Next',exact:true}));await waitFor(()=>assert.ok(calls.some(c=>c.path.includes('offset=20'))))})
test('test_platform_library_detail_has_no_tenant_controls',async()=>{mount(<PlatformLibraryDetailPage/>,'/platform/libraries/'+a);await screen.findByText('Library identity');for(const name of ['Add Book','Confirm Return','Fee waiver','Invite Staff','Rotate Access Code'])assert.equal(screen.queryByRole('button',{name}),null)})
test('test_platform_confirmation_reason_and_escape',async()=>{mount(<PlatformLibraryDetailPage/>,'/platform/libraries/'+a);await screen.findByRole('button',{name:'Suspend Library'});fireEvent.click(screen.getByRole('button',{name:'Suspend Library'}));const dialog=screen.getByRole('dialog',{name:'Suspend Library'});assert.equal((screen.getAllByRole('button',{name:'Suspend Library'}).at(-1) as HTMLButtonElement).disabled,true);fireEvent.change(screen.getByLabelText('Reason (required)'),{target:{value:'Review'}});assert.equal((screen.getAllByRole('button',{name:'Suspend Library'}).at(-1) as HTMLButtonElement).disabled,false);fireEvent.keyDown(dialog,{key:'Escape'});assert.equal(screen.queryByRole('dialog'),null)})
test('test_platform_route_responsive',()=>{const css=readFileSync(new URL('../src/styles/workspaces.css',import.meta.url),'utf8');assert.match(css,/platform-library-table/);assert.match(css,/platform-library-facts/);assert.match(css,/minmax\(min\(100%,220px\),1fr\)/)})
test('test_platform_role_revocation_rechecks_backend',async()=>{platform.setState({roles:['PLATFORM_ADMIN']});await act(async()=>platform.getState().refresh());assert.deepEqual(platform.getState().roles,[]);mount(<PlatformRoute><p>Forbidden</p></PlatformRoute>,'/platform/libraries');assert.equal(screen.queryByText('Forbidden'),null)})
